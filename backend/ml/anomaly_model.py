"""
Modelagem e avaliação de anomalias veiculares com Scikit-Learn (CRISP-DM — Semana 7).

Etapas:
1. Reutilização do dataset preparado por `backend.ml.data_preparation.prepare_dataset`.
2. Filtragem do regime `engine_off` no treino para modelar apenas o motor em operação.
3. Extração determinística da matriz de atributos (`FEATURE_COLUMNS`), tratando `NaN` de
   `rpm_per_speed` em marcha lenta (usando o piso físico `RPM_PER_SPEED_MIN_KMH = 5,0 km/h`)
   e derivadas ausentes em rajadas 4G (`0,0`) sem descartar amostras válidas.
4. Treinamento determinístico com `Pipeline(RobustScaler(5%, 95%) + IsolationForest(random_state=42))`.
5. Inferência híbrida com penalização monotônica fora do envelope observado de treino
   (corrigindo a saturação de fronteira das árvores de isolamento acima do máximo de treino)
   e validação física com anomalias sintéticas (superaquecimento > 108 °C, sobre-rotação em
   marcha lenta e relação `rpm/speed` incoerente).
6. Serialização e carregamento do artefato `.pkl` com metadados e limiares para a Semana 8.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pickle
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import RobustScaler

from backend.config import ANOMALY_MODEL_PATH
from backend.ml.data_preparation import (
    REGIME_DRIVING,
    REGIME_ENGINE_OFF,
    RPM_PER_SPEED_MIN_KMH,
    DataQualityReport,
    add_engineered_features,
    classify_operating_regime,
    flag_4g_bursts,
    normalize_raw_dataframe,
    prepare_dataset,
)
from backend.ml.eda_analysis import compute_normal_thresholds

# --- Hiperparâmetros padrão do Isolation Forest (determinísticos) ---
DEFAULT_CONTAMINATION = 0.02
DEFAULT_N_ESTIMATORS = 200
DEFAULT_RANDOM_STATE = 42
ROBUST_QUANTILE_RANGE = (5.0, 95.0)
OVERHEATING_MIN_CELSIUS = 108.0

# Parâmetros de atenuação contínua de score fora do envelope de treino [min, max]
OUT_OF_ENVELOPE_DEADBAND = 0.20
OUT_OF_ENVELOPE_PENALTY_WEIGHT = 0.08

# --- Ordem canônica dos atributos de entrada do modelo ---
FEATURE_COLUMNS = [
    "rpm",
    "temperature",
    "speed",
    "rpm_per_speed",
    "is_driving",
    "acceleration_ms2",
    "rpm_delta",
]

SYNTHETIC_CATEGORY_LABELS = {
    "overheating": "Superaquecimento (> 108 °C)",
    "idle_overrev": "Sobre-rotação em marcha lenta",
    "gear_mismatch": "Relação RPM/velocidade incoerente",
}


@dataclass
class AnomalyModelArtifact:
    """
    Artefato serializável (`.pkl`) contendo o pipeline treinado do Isolation Forest,
    a lista ordenada de atributos, hiperparâmetros, limiares normais da EDA, fronteiras
    de envelope por atributo e metadados do treinamento para consumo na Semana 8.
    """

    pipeline: Pipeline
    feature_columns: list[str] = field(default_factory=lambda: list(FEATURE_COLUMNS))
    contamination: float = DEFAULT_CONTAMINATION
    n_estimators: int = DEFAULT_N_ESTIMATORS
    random_state: int = DEFAULT_RANDOM_STATE
    score_threshold: float = 0.0
    normal_thresholds: list[dict[str, Any]] = field(default_factory=list)
    feature_bounds: dict[str, dict[str, float]] = field(default_factory=dict)
    training_metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Converte os metadados do artefato em dicionário inspecionável."""
        return {
            "feature_columns": list(self.feature_columns),
            "contamination": self.contamination,
            "n_estimators": self.n_estimators,
            "random_state": self.random_state,
            "score_threshold": self.score_threshold,
            "normal_thresholds": list(self.normal_thresholds),
            "feature_bounds": dict(self.feature_bounds),
            "training_metadata": dict(self.training_metadata),
        }


def filter_active_engine(df: pd.DataFrame) -> pd.DataFrame:
    """
    Remove registros com `regime == "engine_off"` (RPM < 300) para que o modelo
    aprenda apenas a distribuição do motor em funcionamento (`idle`, `driving`, `unknown`).
    """
    if df.empty:
        return df.copy()
    prepared = _ensure_engineered_columns(df)
    active = prepared.loc[prepared["regime"] != REGIME_ENGINE_OFF].copy()
    return active.reset_index(drop=True)


def _ensure_engineered_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Garante que o DataFrame possua as colunas de engenharia de atributos e regime
    da Semana 6 sem descartar linhas já limpas nem usar `timestamp_est`.
    """
    required = {"regime", "rpm_per_speed", "acceleration_ms2", "rpm_delta"}
    if required.issubset(df.columns):
        return df
    normalized = normalize_raw_dataframe(df)
    flagged = flag_4g_bursts(normalized)
    engineered = add_engineered_features(flagged)
    return classify_operating_regime(engineered)


def build_feature_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """
    Extrai de forma determinística a matriz numérica `X` (`FEATURE_COLUMNS`):
    - `rpm_per_speed` ausente em marcha lenta (`speed <= 5 km/h`) é imputado de forma
      contínua usando o piso físico `RPM_PER_SPEED_MIN_KMH` (`rpm / max(speed, 5,0)`),
      preservando a sensibilidade à sobre-rotação com o veículo parado sem descartar linhas;
    - `acceleration_ms2` e `rpm_delta` ausentes em rajadas 4G ou quedas longas de sinal
      são preenchidos com `0.0` (regime estacionário neutro);
    - `is_driving` codifica em `1.0` o regime `driving` e `0.0` caso contrário.
    """
    if df.empty:
        return pd.DataFrame(columns=FEATURE_COLUMNS, dtype="float64")

    prepared = _ensure_engineered_columns(df)
    features = pd.DataFrame(index=prepared.index)
    rpm = pd.to_numeric(prepared["rpm"], errors="coerce").fillna(0.0).astype("float64")
    temperature = (
        pd.to_numeric(prepared["temperature"], errors="coerce").fillna(0.0).astype("float64")
    )
    speed = pd.to_numeric(prepared["speed"], errors="coerce").fillna(0.0).astype("float64")

    effective_speed = np.maximum(speed.clip(lower=0.0), RPM_PER_SPEED_MIN_KMH)
    fallback_ratio = np.where(rpm > 0.0, rpm / effective_speed, 0.0)
    raw_ratio = pd.to_numeric(prepared["rpm_per_speed"], errors="coerce")
    rpm_per_speed = raw_ratio.fillna(pd.Series(fallback_ratio, index=prepared.index)).astype("float64")

    features["rpm"] = rpm
    features["temperature"] = temperature
    features["speed"] = speed
    features["rpm_per_speed"] = rpm_per_speed
    features["is_driving"] = (prepared["regime"] == REGIME_DRIVING).astype("float64")
    features["acceleration_ms2"] = (
        pd.to_numeric(prepared["acceleration_ms2"], errors="coerce").fillna(0.0).astype("float64")
    )
    features["rpm_delta"] = (
        pd.to_numeric(prepared["rpm_delta"], errors="coerce").fillna(0.0).astype("float64")
    )
    features = features.replace([np.inf, -np.inf], 0.0)
    return features[FEATURE_COLUMNS]


def build_anomaly_pipeline(
    contamination: float = DEFAULT_CONTAMINATION,
    n_estimators: int = DEFAULT_N_ESTIMATORS,
    random_state: int = DEFAULT_RANDOM_STATE,
) -> Pipeline:
    """
    Constrói o pipeline Scikit-Learn com escalonamento robusto pela faixa P05–P95
    (`RobustScaler(quantile_range=(5.0, 95.0))`) seguido do `IsolationForest` determinístico.
    """
    return Pipeline(
        steps=[
            ("scaler", RobustScaler(quantile_range=ROBUST_QUANTILE_RANGE)),
            (
                "detector",
                IsolationForest(
                    n_estimators=n_estimators,
                    contamination=contamination,
                    random_state=random_state,
                    n_jobs=1,
                ),
            ),
        ]
    )


def _compute_feature_bounds(feature_matrix: pd.DataFrame) -> dict[str, dict[str, float]]:
    """
    Calcula os limites observados (`min`, `p05`, `p50`, `p95`, `p99`, `max`) e a escala
    robusta (`max(p95 - p05, 1.0)`) de cada atributo da matriz de treinamento.
    """
    bounds: dict[str, dict[str, float]] = {}
    for column in feature_matrix.columns:
        series = pd.to_numeric(feature_matrix[column], errors="coerce").dropna()
        if series.empty:
            continue
        quantiles = series.quantile([0.05, 0.50, 0.95, 0.99])
        p05 = float(quantiles.loc[0.05])
        p95 = float(quantiles.loc[0.95])
        bounds[column] = {
            "min": float(series.min()),
            "p05": p05,
            "p50": float(quantiles.loc[0.50]),
            "p95": p95,
            "p99": float(quantiles.loc[0.99]),
            "max": float(series.max()),
            "scale": max(p95 - p05, 1.0),
        }
    return bounds


def _compute_out_of_envelope_penalty(
    feature_matrix: pd.DataFrame,
    feature_bounds: dict[str, dict[str, float]],
) -> np.ndarray:
    """
    Calcula a penalização monotônica para amostras que extrapolam o envelope `[min, max]`
    observado no conjunto de treino (onde as árvores do Isolation Forest saturam por não
    possuírem limiares de corte fora do domínio de treino). Para qualquer amostra dentro
    do domínio de treino, a penalização é estritamente `0.0`.
    """
    total_excess = np.zeros(len(feature_matrix), dtype="float64")
    if not feature_bounds or feature_matrix.empty:
        return total_excess

    for column, stats in feature_bounds.items():
        if column not in feature_matrix.columns or column == "is_driving":
            continue
        values = feature_matrix[column].to_numpy(dtype="float64")
        scale = max(float(stats.get("scale", 1.0)), 1.0)
        low_excess = np.maximum(0.0, float(stats["min"]) - values) / scale
        high_excess = np.maximum(0.0, values - float(stats["max"])) / scale
        total_excess += low_excess + high_excess

    effective_excess = np.maximum(0.0, total_excess - OUT_OF_ENVELOPE_DEADBAND)
    return OUT_OF_ENVELOPE_PENALTY_WEIGHT * effective_excess


def prepare_training_dataframe(
    raw_or_prepared_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, DataQualityReport | None]:
    """
    Executa `prepare_dataset(..., include_estimated_timestamp=False)` quando o DataFrame
    ainda é bruto e devolve `(prepared_df, active_engine_df, quality_report)`.
    """
    required_prepared = {"regime", "rpm_per_speed", "acceleration_ms2", "rpm_delta", "is_burst"}
    if required_prepared.issubset(raw_or_prepared_df.columns):
        prepared_df = raw_or_prepared_df.copy()
        if "timestamp_est" in prepared_df.columns:
            prepared_df = prepared_df.drop(
                columns=["timestamp_est", "is_timestamp_estimated"], errors="ignore"
            )
        report = None
    else:
        prepared_df, report = prepare_dataset(raw_or_prepared_df, include_estimated_timestamp=False)

    active_df = filter_active_engine(prepared_df)
    return prepared_df, active_df, report


def train_anomaly_model(
    df: pd.DataFrame,
    contamination: float = DEFAULT_CONTAMINATION,
    n_estimators: int = DEFAULT_N_ESTIMATORS,
    random_state: int = DEFAULT_RANDOM_STATE,
) -> AnomalyModelArtifact:
    """
    Treina o pipeline `IsolationForest` sobre as amostras com motor em funcionamento
    (`regime != "engine_off"`) e retorna o `AnomalyModelArtifact` completo.
    """
    prepared_df, active_df, report = prepare_training_dataframe(df)
    if active_df.empty:
        raise ValueError("Nenhuma amostra com motor em funcionamento disponível para treinar o modelo.")

    feature_matrix = build_feature_matrix(active_df)
    pipeline = build_anomaly_pipeline(
        contamination=contamination,
        n_estimators=n_estimators,
        random_state=random_state,
    )
    pipeline.fit(feature_matrix)

    scores = pipeline.decision_function(feature_matrix)
    labels = pipeline.predict(feature_matrix)
    anomaly_count = int((labels == -1).sum())
    quantiles = np.quantile(scores, [0.01, 0.05, 0.50, 0.95])
    regime_counts = {
        str(regime): int(count) for regime, count in active_df["regime"].value_counts().items()
    }
    thresholds_df = compute_normal_thresholds(active_df)
    feature_bounds = _compute_feature_bounds(feature_matrix)

    metadata: dict[str, Any] = {
        "trained_at_utc": datetime.now(timezone.utc).isoformat(),
        "prepared_clean_count": int(len(prepared_df)),
        "active_engine_count": int(len(active_df)),
        "excluded_engine_off_count": int(len(prepared_df) - len(active_df)),
        "training_anomaly_count": anomaly_count,
        "training_anomaly_rate_pct": round(100.0 * anomaly_count / len(active_df), 2),
        "regime_counts": regime_counts,
        "score_summary": {
            "min": float(scores.min()),
            "p01": float(quantiles[0]),
            "p05": float(quantiles[1]),
            "p50": float(quantiles[2]),
            "p95": float(quantiles[3]),
            "max": float(scores.max()),
        },
    }
    if report is not None:
        metadata["data_quality_report"] = report.to_dict()

    return AnomalyModelArtifact(
        pipeline=pipeline,
        feature_columns=list(FEATURE_COLUMNS),
        contamination=contamination,
        n_estimators=n_estimators,
        random_state=random_state,
        score_threshold=0.0,
        normal_thresholds=thresholds_df.to_dict(orient="records"),
        feature_bounds=feature_bounds,
        training_metadata=metadata,
    )


def _extract_pipeline(model: AnomalyModelArtifact | Pipeline) -> Pipeline:
    """Extrai o objeto `Pipeline` tanto de um `AnomalyModelArtifact` quanto diretamente."""
    return model.pipeline if isinstance(model, AnomalyModelArtifact) else model


def predict_anomalies(
    df: pd.DataFrame,
    model: AnomalyModelArtifact | Pipeline,
    ignore_engine_off: bool = True,
) -> pd.DataFrame:
    """
    Executa a inferência sobre um DataFrame (bruto ou preparado) e anexa:
    - `anomaly_score`: score contínuo do `decision_function` ajustado pela distância
      fora do envelope de treino (negativo = anômalo);
    - `anomaly_label`: `1` para operação normal e `-1` para anomalia;
    - `is_anomaly`: booleano (`True` quando `anomaly_label == -1`).

    Se `ignore_engine_off=True`, amostras com `regime == "engine_off"` são marcadas
    como não anômalas (`is_anomaly = False`), evitando falsos positivos ao desligar o motor.
    """
    prepared = _ensure_engineered_columns(df).copy()
    if prepared.empty:
        prepared["anomaly_score"] = pd.Series(dtype="float64")
        prepared["anomaly_label"] = pd.Series(dtype="int64")
        prepared["is_anomaly"] = pd.Series(dtype="bool")
        return prepared

    pipeline = _extract_pipeline(model)
    feature_matrix = build_feature_matrix(prepared)
    raw_scores = pipeline.decision_function(feature_matrix).astype("float64")

    if isinstance(model, AnomalyModelArtifact) and model.feature_bounds:
        penalty = _compute_out_of_envelope_penalty(feature_matrix, model.feature_bounds)
        threshold = float(model.score_threshold)
    else:
        penalty = np.zeros(len(feature_matrix), dtype="float64")
        threshold = 0.0

    scores = raw_scores - penalty
    labels = np.where(scores < threshold, -1, 1).astype("int64")

    if ignore_engine_off and "regime" in prepared.columns:
        engine_off_mask = (prepared["regime"] == REGIME_ENGINE_OFF).to_numpy()
        labels = np.where(engine_off_mask, 1, labels)

    prepared["anomaly_score"] = scores
    prepared["anomaly_label"] = labels
    prepared["is_anomaly"] = labels == -1
    return prepared


def generate_synthetic_anomalies(
    base_timestamp: datetime | None = None,
) -> pd.DataFrame:
    """
    Gera um conjunto determinístico de anomalias sintéticas fisicamente fundamentadas
    (dentro das faixas de sensor válidas da Semana 6, porém mecanicamente anômalas):
    1. `overheating`: temperatura do arrefecimento > 108 °C;
    2. `idle_overrev`: sobre-rotação severa em marcha lenta (velocidade = 0 km/h);
    3. `gear_mismatch`: relação `rpm/speed` fisicamente incoerente (patinação/falha).
    """
    anchor = base_timestamp or datetime(2026, 11, 16, 20, 0, 0, tzinfo=timezone.utc)
    synthetic_specs: list[tuple[str, float, float, float, str]] = [
        # (category, rpm, temperature, speed, description)
        ("overheating", 960.0, 112.0, 0.0, "Superaquecimento em marcha lenta (112 °C)"),
        ("overheating", 1050.0, 118.0, 0.0, "Superaquecimento severo em marcha lenta (118 °C)"),
        ("overheating", 2400.0, 115.0, 38.0, "Superaquecimento em condução urbana (115 °C)"),
        ("overheating", 3100.0, 126.0, 52.0, "Superaquecimento crítico sob carga (126 °C)"),
        ("idle_overrev", 3600.0, 89.0, 0.0, "Sobre-rotação em marcha lenta (3600 RPM parado)"),
        ("idle_overrev", 4300.0, 90.0, 0.0, "Sobre-rotação em marcha lenta (4300 RPM parado)"),
        ("idle_overrev", 5100.0, 91.0, 0.0, "Sobre-rotação em marcha lenta (5100 RPM parado)"),
        ("idle_overrev", 5800.0, 93.0, 1.0, "Corte de giro quase parado (5800 RPM a 1 km/h)"),
        ("gear_mismatch", 5200.0, 88.0, 10.0, "RPM/velocidade extremo (5200 RPM a 10 km/h -> 520)"),
        ("gear_mismatch", 4900.0, 89.0, 12.0, "RPM/velocidade extremo (4900 RPM a 12 km/h -> 408)"),
        ("gear_mismatch", 5600.0, 90.0, 14.0, "RPM/velocidade extremo (5600 RPM a 14 km/h -> 400)"),
        ("gear_mismatch", 950.0, 85.0, 115.0, "RPM de marcha lenta em alta velocidade (950 RPM a 115 km/h)"),
    ]

    rows: list[dict[str, Any]] = []
    for index, (category, rpm, temperature, speed, description) in enumerate(synthetic_specs):
        # Espaçamento de 5 s (> 2,5 s) para que cada anomalia sintética seja avaliada
        # pelo seu estado físico instantâneo sem contaminar a derivada da seguinte.
        rows.append(
            {
                "id": 9000 + index + 1,
                "category": category,
                "description": description,
                "rpm": rpm,
                "temperature": temperature,
                "speed": speed,
                "timestamp": (anchor + timedelta(seconds=index * 5)).isoformat(),
            }
        )
    raw_synthetic = pd.DataFrame(rows)
    prepared_synthetic = _ensure_engineered_columns(raw_synthetic)
    prepared_synthetic["category"] = raw_synthetic["category"].to_numpy()
    prepared_synthetic["description"] = raw_synthetic["description"].to_numpy()
    return prepared_synthetic


def evaluate_anomaly_model(
    df: pd.DataFrame,
    model: AnomalyModelArtifact | Pipeline,
    top_k: int = 10,
) -> dict[str, Any]:
    """
    Executa a avaliação CRISP-DM do modelo treinado:
    1. Métricas e distribuição de anomalias por regime no dataset real (motor ligado);
    2. Top-K anomalias reais de menor `anomaly_score` no trajeto;
    3. Validação contra anomalias sintéticas físicas (`overheating`, `idle_overrev`,
       `gear_mismatch`), calculando a taxa de detecção por categoria e global.
    """
    _, active_df, _ = prepare_training_dataframe(df)
    scored_real = predict_anomalies(active_df, model, ignore_engine_off=True)

    real_anomalies = scored_real.loc[scored_real["is_anomaly"]].sort_values(
        by="anomaly_score", ascending=True
    )
    top_columns = [
        col
        for col in [
            "id",
            "timestamp",
            "regime",
            "rpm",
            "temperature",
            "speed",
            "rpm_per_speed",
            "acceleration_ms2",
            "rpm_delta",
            "anomaly_score",
        ]
        if col in real_anomalies.columns
    ]
    top_anomalies_df = real_anomalies[top_columns].head(top_k).reset_index(drop=True)

    regime_breakdown_rows: list[dict[str, Any]] = []
    if not scored_real.empty and "regime" in scored_real.columns:
        for regime, group in scored_real.groupby("regime", sort=False):
            total = int(len(group))
            detected = int(group["is_anomaly"].sum())
            regime_breakdown_rows.append(
                {
                    "regime": str(regime),
                    "samples": total,
                    "anomalies": detected,
                    "anomaly_rate_pct": round(100.0 * detected / total, 2) if total else 0.0,
                    "score_min": float(group["anomaly_score"].min()),
                    "score_p50": float(group["anomaly_score"].median()),
                }
            )
    regime_breakdown_df = pd.DataFrame(regime_breakdown_rows)

    synthetic_df = generate_synthetic_anomalies()
    scored_synthetic = predict_anomalies(synthetic_df, model, ignore_engine_off=True)

    category_rows: list[dict[str, Any]] = []
    for category, group in scored_synthetic.groupby("category", sort=False):
        total = int(len(group))
        detected = int(group["is_anomaly"].sum())
        category_rows.append(
            {
                "category": str(category),
                "label": SYNTHETIC_CATEGORY_LABELS.get(str(category), str(category)),
                "samples": total,
                "detected": detected,
                "detection_rate_pct": round(100.0 * detected / total, 2) if total else 0.0,
                "mean_score": float(group["anomaly_score"].mean()),
                "min_score": float(group["anomaly_score"].min()),
            }
        )
    synthetic_summary_df = pd.DataFrame(category_rows)

    total_real = int(len(scored_real))
    detected_real = int(scored_real["is_anomaly"].sum()) if total_real else 0
    total_synth = int(len(scored_synthetic))
    detected_synth = int(scored_synthetic["is_anomaly"].sum()) if total_synth else 0

    return {
        "real_samples": total_real,
        "real_anomalies_count": detected_real,
        "real_anomaly_rate_pct": round(100.0 * detected_real / total_real, 2) if total_real else 0.0,
        "regime_breakdown": regime_breakdown_df,
        "top_real_anomalies": top_anomalies_df,
        "synthetic_samples": total_synth,
        "synthetic_detected_count": detected_synth,
        "synthetic_detection_rate_pct": (
            round(100.0 * detected_synth / total_synth, 2) if total_synth else 0.0
        ),
        "synthetic_by_category": synthetic_summary_df,
        "synthetic_predictions": scored_synthetic,
    }


def save_model_artifact(
    artifact: AnomalyModelArtifact,
    model_path: Path | str = ANOMALY_MODEL_PATH,
) -> Path:
    """
    Serializa o `AnomalyModelArtifact` em disco no formato `.pkl`.
    Cria diretórios pais automaticamente caso não existam.
    """
    target = Path(model_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb") as file_obj:
        pickle.dump(artifact, file_obj, protocol=pickle.HIGHEST_PROTOCOL)
    return target


def load_model_artifact(
    model_path: Path | str = ANOMALY_MODEL_PATH,
) -> AnomalyModelArtifact:
    """
    Carrega e valida o `AnomalyModelArtifact` a partir de um arquivo `.pkl`.
    """
    target = Path(model_path)
    if not target.exists():
        raise FileNotFoundError(f"Artefato do modelo não encontrado em: {target}")
    with target.open("rb") as file_obj:
        artifact = pickle.load(file_obj)
    if not isinstance(artifact, AnomalyModelArtifact):
        raise TypeError(f"Artefato inválido em {target}: esperado AnomalyModelArtifact.")
    return artifact
