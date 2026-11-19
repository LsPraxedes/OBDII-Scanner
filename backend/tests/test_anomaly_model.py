from datetime import datetime, timedelta, timezone
import sqlite3

import numpy as np
import pandas as pd
import pytest

from backend.ml.anomaly_model import (
    FEATURE_COLUMNS,
    AnomalyModelArtifact,
    build_feature_matrix,
    evaluate_anomaly_model,
    filter_active_engine,
    generate_synthetic_anomalies,
    load_model_artifact,
    predict_anomalies,
    save_model_artifact,
    train_anomaly_model,
)
from backend.ml.data_preparation import REGIME_ENGINE_OFF, prepare_dataset
from scripts.train_model import main as train_model_main

BASE_TS = datetime(2026, 11, 16, 18, 0, 0, tzinfo=timezone.utc)


def _build_realistic_telemetry_dataframe(n_idle: int = 80, n_driving: int = 120) -> pd.DataFrame:
    """
    Constrói um dataset determinístico representativo do VW Polo Track:
    - Amostras de motor desligado (`engine_off`, RPM = 0);
    - Amostras de marcha lenta (`idle`, ~950 RPM, 87–89 °C, 0 km/h);
    - Amostras em movimento (`driving`, 1800–3200 RPM, 84–87 °C, 25–55 km/h),
      incluindo pacotes em rajada 4G (`dt = 0.01 s`) para validar imputação de derivadas.
    """
    rows: list[dict] = []
    current_offset = 0.0
    record_id = 1

    # 5 amostras de motor desligado (devem ser filtradas do treino)
    for _ in range(5):
        rows.append(
            {
                "id": record_id,
                "rpm": 0.0,
                "temperature": 84.0,
                "speed": 0.0,
                "timestamp": (BASE_TS + timedelta(seconds=current_offset)).isoformat(),
            }
        )
        record_id += 1
        current_offset += 1.0

    # Marcha lenta (~950 RPM, 88 °C, 0 km/h)
    for idx in range(n_idle):
        rows.append(
            {
                "id": record_id,
                "rpm": 945.0 + float((idx * 7) % 35),
                "temperature": 87.0 + float(idx % 3),
                "speed": 0.0,
                "timestamp": (BASE_TS + timedelta(seconds=current_offset)).isoformat(),
            }
        )
        record_id += 1
        current_offset += 1.0

    # Em movimento (~2000–3100 RPM, 85 °C, 28–50 km/h, rpm_per_speed ~ 60–72)
    for idx in range(n_driving):
        speed = 28.0 + float((idx * 3) % 22)
        ratio = 63.0 + float(idx % 7)
        rpm = speed * ratio
        # A cada 25 amostras simula uma rajada 4G (dt = 0.01 s)
        dt = 0.01 if (idx > 0 and idx % 25 == 0) else 1.0
        current_offset += dt
        rows.append(
            {
                "id": record_id,
                "rpm": rpm,
                "temperature": 84.0 + float(idx % 4),
                "speed": speed,
                "timestamp": (BASE_TS + timedelta(seconds=current_offset)).isoformat(),
            }
        )
        record_id += 1

    return pd.DataFrame(rows)


def test_feature_extraction_handles_idle_and_bursts_without_nans():
    """
    A matriz de atributos não deve conter NaN mesmo em marcha lenta (onde `rpm_per_speed`
    é NaN) e em rajadas 4G (onde `acceleration_ms2` e `rpm_delta` são NaN), e `filter_active_engine`
    deve excluir apenas as amostras com `regime == "engine_off"`.
    """
    raw_df = _build_realistic_telemetry_dataframe(n_idle=30, n_driving=50)
    prepared_df, report = prepare_dataset(raw_df, include_estimated_timestamp=False)

    assert "timestamp_est" not in prepared_df.columns
    assert report.burst_count >= 1

    active_df = filter_active_engine(prepared_df)
    assert len(active_df) == 80
    assert REGIME_ENGINE_OFF not in set(active_df["regime"])

    features = build_feature_matrix(active_df)
    assert list(features.columns) == FEATURE_COLUMNS
    assert len(features) == 80
    assert not features.isna().any().any()

    # Em marcha lenta, rpm_per_speed usa o piso físico (5 km/h) e is_driving vale 0.0
    idle_mask = active_df["regime"] == "idle"
    assert (features.loc[idle_mask, "rpm_per_speed"] == active_df.loc[idle_mask, "rpm"] / 5.0).all()
    assert (features.loc[idle_mask, "is_driving"] == 0.0).all()

    # Em movimento, is_driving vale 1.0 e rpm_per_speed > 0
    driving_mask = active_df["regime"] == "driving"
    assert (features.loc[driving_mask, "is_driving"] == 1.0).all()
    assert (features.loc[driving_mask, "rpm_per_speed"] > 0.0).all()


def test_training_is_deterministic_with_random_state_42():
    """
    Dois treinamentos com `random_state=42` sobre o mesmo dataset devem produzir
    exatamente os mesmos scores e rótulos de anomalia.
    """
    raw_df = _build_realistic_telemetry_dataframe(n_idle=60, n_driving=90)
    artifact_a = train_anomaly_model(raw_df, contamination=0.03, random_state=42)
    artifact_b = train_anomaly_model(raw_df, contamination=0.03, random_state=42)

    pred_a = predict_anomalies(raw_df, artifact_a)
    pred_b = predict_anomalies(raw_df, artifact_b)

    assert np.allclose(pred_a["anomaly_score"].to_numpy(), pred_b["anomaly_score"].to_numpy())
    assert pred_a["is_anomaly"].tolist() == pred_b["is_anomaly"].tolist()
    assert artifact_a.training_metadata["active_engine_count"] == 150
    assert artifact_a.training_metadata["excluded_engine_off_count"] == 5


def test_save_and_load_model_artifact_roundtrip(tmp_path):
    """
    Salva o artefato `.pkl` em `tmp_path`, recarrega do disco e verifica integridade
    dos metadados e igualdade exata das predições.
    """
    raw_df = _build_realistic_telemetry_dataframe(n_idle=50, n_driving=70)
    artifact = train_anomaly_model(raw_df, contamination=0.02, random_state=42)

    pkl_path = tmp_path / "models" / "test_isolation_forest.pkl"
    saved_path = save_model_artifact(artifact, pkl_path)
    assert saved_path.exists()

    loaded = load_model_artifact(saved_path)
    assert isinstance(loaded, AnomalyModelArtifact)
    assert loaded.feature_columns == FEATURE_COLUMNS
    assert loaded.random_state == 42
    assert loaded.to_dict()["contamination"] == pytest.approx(0.02)

    before = predict_anomalies(raw_df, artifact)
    after = predict_anomalies(raw_df, loaded)
    assert np.allclose(before["anomaly_score"].to_numpy(), after["anomaly_score"].to_numpy())
    assert before["is_anomaly"].tolist() == after["is_anomaly"].tolist()

    with pytest.raises(FileNotFoundError):
        load_model_artifact(tmp_path / "inexistente.pkl")


def test_model_detects_synthetic_physical_anomalies_vs_normal_samples():
    """
    O modelo deve classificar amostras normais de marcha lenta e condução como normais
    (`is_anomaly == False`) e detectar as anomalias sintéticas físicas extremas
    (superaquecimento > 108 °C, sobre-rotação em marcha lenta e `rpm/speed` incoerente).
    """
    raw_df = _build_realistic_telemetry_dataframe(n_idle=100, n_driving=150)
    artifact = train_anomaly_model(raw_df, contamination=0.02, random_state=42)

    normal_probes = pd.DataFrame(
        [
            {
                "id": 1,
                "rpm": 955.0,
                "temperature": 88.0,
                "speed": 0.0,
                "timestamp": (BASE_TS + timedelta(seconds=500)).isoformat(),
            },
            {
                "id": 2,
                "rpm": 2300.0,
                "temperature": 85.0,
                "speed": 35.0,
                "timestamp": (BASE_TS + timedelta(seconds=510)).isoformat(),
            },
            {
                "id": 3,
                "rpm": 0.0,
                "temperature": 85.0,
                "speed": 0.0,
                "timestamp": (BASE_TS + timedelta(seconds=520)).isoformat(),
            },
        ]
    )
    normal_predictions = predict_anomalies(normal_probes, artifact)
    assert normal_predictions["is_anomaly"].tolist() == [False, False, False]

    synthetic_df = generate_synthetic_anomalies()
    assert set(synthetic_df["category"]) == {"overheating", "idle_overrev", "gear_mismatch"}
    assert (synthetic_df.loc[synthetic_df["category"] == "overheating", "temperature"] > 108.0).all()

    evaluation = evaluate_anomaly_model(raw_df, artifact, top_k=5)
    assert evaluation["synthetic_samples"] == len(synthetic_df)
    assert evaluation["synthetic_detection_rate_pct"] >= 90.0

    # Os scores médios das anomalias sintéticas devem ser inferiores aos das amostras normais
    synth_scores = evaluation["synthetic_predictions"]["anomaly_score"]
    normal_scores = normal_predictions.iloc[:2]["anomaly_score"]
    assert float(synth_scores.mean()) < float(normal_scores.min())


def test_train_model_cli_end_to_end(tmp_path, capsys):
    """
    Executa a CLI `scripts/train_model.py` sobre um SQLite temporário, verifica o
    relatório impresso no terminal e confirma a criação do arquivo `.pkl`.
    """
    raw_df = _build_realistic_telemetry_dataframe(n_idle=40, n_driving=60)
    db_path = tmp_path / "vehicle_test.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "CREATE TABLE telemetry (id INTEGER PRIMARY KEY, rpm FLOAT, temperature FLOAT, "
            "speed FLOAT, timestamp DATETIME)"
        )
        conn.executemany(
            "INSERT INTO telemetry (id, rpm, temperature, speed, timestamp) VALUES (?, ?, ?, ?, ?)",
            [
                (int(row["id"]), float(row["rpm"]), float(row["temperature"]), float(row["speed"]), str(row["timestamp"]))
                for _, row in raw_df.iterrows()
            ],
        )

    model_out = tmp_path / "isolation_forest_cli.pkl"
    exit_code = train_model_main(
        [
            "--db",
            str(db_path),
            "--model-out",
            str(model_out),
            "--contamination",
            "0.03",
            "--top-k",
            "5",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert model_out.exists()
    assert "RELATÓRIO DE QUALIDADE DOS DADOS" in captured.out
    assert "RELATÓRIO DE MODELAGEM E AVALIAÇÃO (CRISP-DM — Semana 7: Isolation Forest)" in captured.out
    assert "VALIDAÇÃO COM ANOMALIAS SINTÉTICAS FÍSICAS" in captured.out

    loaded = load_model_artifact(model_out)
    assert loaded.training_metadata["active_engine_count"] == 100
    assert "synthetic_validation" in loaded.training_metadata

    # Banco inexistente deve retornar código 1 e parâmetros CLI inválidos devem ser rejeitados
    assert train_model_main(["--db", str(tmp_path / "nao_existe.db"), "--model-out", str(model_out)]) == 1
    with pytest.raises(SystemExit):
        train_model_main(["--contamination", "0"])
