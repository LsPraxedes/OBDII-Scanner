"""
Pipeline determinístico de preparação dos dados de telemetria (CRISP-DM — Semana 6).

Etapas:
1. Carregamento seguro do SQLite (`vehicle_data.db`), tolerante à ausência do arquivo.
2. Normalização (tipos numéricos, timestamp em UTC, ordenação por ["timestamp", "id"]).
3. Limpeza com filtros físicos do VW Polo Track e Relatório de Qualidade dos Dados.
4. Marcação de rajadas 4G (pacotes entregues em lote pelo MQTT após falha de rede).
5. Engenharia de atributos (aceleração, ΔRPM, RPM/velocidade) e regime operacional.

Observação sobre o timestamp: o horário é atribuído pelo backend na CHEGADA do pacote,
não no instante da leitura CAN. Por isso, em rajadas (`dt < 0,25 s`) as leituras são
mantidas (valores instantâneos válidos), mas os atributos derivados do tempo são anulados.
"""

from dataclasses import dataclass, field
from pathlib import Path
import sqlite3
from typing import Any

import numpy as np
import pandas as pd

from backend.config import BASE_DIR, DATABASE_URL

# --- Limites físicos plausíveis do VW Polo Track (1.0 MPI) ---
RPM_RANGE = (0.0, 8000.0)
SPEED_RANGE = (0.0, 220.0)
TEMPERATURE_RANGE = (-20.0, 140.0)
SPEED_SENTINEL_KMH = 255.0  # 0xFF retornado quando o PID 0x0D não possui dado válido

# --- Parâmetros temporais ---
KMH_TO_MS = 3.6
BURST_DT_SECONDS = 0.25  # mesma semântica de MIN_ACCEL_DT_SECONDS no frontend
MAX_DERIVATIVE_DT_SECONDS = 2.5  # acima disso há falha de rede/sessão: derivada não confiável
MAX_PHYSICAL_ACCEL_MS2 = 15.0
NOMINAL_SAMPLE_PERIOD_SECONDS = 1.0  # firmware publica a cada 1000 ms

# --- Regimes operacionais ---
ENGINE_OFF_MAX_RPM = 300.0
IDLE_MAX_SPEED_KMH = 2.0
RPM_PER_SPEED_MIN_KMH = 5.0
REGIME_ENGINE_OFF = "engine_off"
REGIME_IDLE = "idle"
REGIME_DRIVING = "driving"
REGIME_UNKNOWN = "unknown"

RAW_COLUMNS = ["id", "rpm", "temperature", "speed", "timestamp"]
NUMERIC_COLUMNS = ["rpm", "temperature", "speed"]

# Ordem de aplicação das regras de limpeza (também é a ordem do relatório)
CLEANING_RULES = [
    "invalid_timestamp",
    "duplicates",
    "missing_required_values",
    "speed_sentinel_255",
    "rpm_out_of_range",
    "speed_out_of_range",
    "temperature_out_of_range",
]

# Rótulos em português das regras (exibição no terminal e no dashboard)
CLEANING_RULE_LABELS = {
    "invalid_timestamp": "Timestamp inválido",
    "duplicates": "Registros duplicados",
    "missing_required_values": "RPM/temperatura ausentes",
    "speed_sentinel_255": "Velocidade sentinela 255 km/h",
    "rpm_out_of_range": "RPM fora de [0, 8000]",
    "speed_out_of_range": "Velocidade fora de [0, 220] km/h",
    "temperature_out_of_range": "Temperatura fora de [-20, 140] °C",
}


@dataclass
class DataQualityReport:
    """
    Relatório de Qualidade dos Dados: contagens antes/depois da limpeza,
    remoções por regra e quantidade de rajadas 4G detectadas no conjunto limpo.
    """

    raw_count: int = 0
    clean_count: int = 0
    removed_by_rule: dict[str, int] = field(default_factory=lambda: {rule: 0 for rule in CLEANING_RULES})
    burst_count: int = 0
    long_gap_count: int = 0
    derivative_valid_count: int = 0

    @property
    def removed_count(self) -> int:
        """Total de registros removidos pelas regras de limpeza."""
        return self.raw_count - self.clean_count

    def to_dict(self) -> dict[str, Any]:
        """Serializa o relatório em dicionário (CLI, frontend e relatórios)."""
        return {
            "raw_count": self.raw_count,
            "clean_count": self.clean_count,
            "removed_count": self.removed_count,
            "removed_by_rule": dict(self.removed_by_rule),
            "burst_count": self.burst_count,
            "long_gap_count": self.long_gap_count,
            "derivative_valid_count": self.derivative_valid_count,
        }


def default_sqlite_path(database_url: str = DATABASE_URL) -> Path:
    """
    Extrai o caminho do arquivo SQLite a partir da string de conexão SQLAlchemy.
    """
    prefix = "sqlite:///"
    if database_url.startswith(prefix):
        return Path(database_url[len(prefix) :])
    return BASE_DIR / "vehicle_data.db"


def empty_telemetry_dataframe() -> pd.DataFrame:
    """Retorna um DataFrame vazio com o contrato de colunas da tabela `telemetry`."""
    return pd.DataFrame({column: pd.Series(dtype="float64") for column in RAW_COLUMNS})


def load_telemetry_from_sqlite(db_path: Path | str | None = None) -> pd.DataFrame:
    """
    Carrega a tabela `telemetry` do SQLite em modo somente leitura.
    Retorna DataFrame vazio (com as colunas esperadas) se o arquivo ou a tabela não existirem.
    """
    target_path = Path(db_path) if db_path is not None else default_sqlite_path()
    if not target_path.exists():
        return empty_telemetry_dataframe()

    try:
        uri = f"file:{target_path.resolve().as_posix()}?mode=ro"
        with sqlite3.connect(uri, uri=True) as conn:
            df = pd.read_sql_query(
                "SELECT id, rpm, temperature, speed, timestamp FROM telemetry",
                conn,
            )
    except (sqlite3.Error, pd.errors.DatabaseError):
        return empty_telemetry_dataframe()
    return df


def normalize_raw_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Padroniza tipos (numéricos e timestamp UTC) e ordena cronologicamente por
    ["timestamp", "id"], preservando colunas extras já existentes.
    """
    result = df.copy()
    for column in RAW_COLUMNS:
        if column not in result.columns:
            result[column] = np.nan

    # format="ISO8601" aceita strings com e sem microssegundos na mesma coluna
    # (a inferência pelo primeiro elemento descartaria as demais como NaT).
    if pd.api.types.is_datetime64_any_dtype(result["timestamp"]):
        result["timestamp"] = pd.to_datetime(result["timestamp"], utc=True)
    else:
        result["timestamp"] = pd.to_datetime(
            result["timestamp"], utc=True, errors="coerce", format="ISO8601"
        )
    for column in NUMERIC_COLUMNS:
        result[column] = pd.to_numeric(result[column], errors="coerce").astype("float64")

    sort_columns = ["timestamp", "id"] if result["id"].notna().any() else ["timestamp"]
    return result.sort_values(by=sort_columns, ascending=True, na_position="last").reset_index(drop=True)


def _out_of_range(series: pd.Series, bounds: tuple[float, float]) -> pd.Series:
    """Máscara de valores não nulos fora do intervalo fechado [mínimo, máximo]."""
    low, high = bounds
    return series.notna() & ((series < low) | (series > high))


def clean_telemetry(df: pd.DataFrame) -> tuple[pd.DataFrame, DataQualityReport]:
    """
    Aplica as regras de limpeza em sequência e contabiliza as remoções por regra.
    A velocidade é opcional (pode ser nula), mas RPM e temperatura são obrigatórios.
    """
    report = DataQualityReport(raw_count=int(len(df)))
    data = normalize_raw_dataframe(df)

    def drop(mask: pd.Series, rule: str) -> None:
        nonlocal data
        report.removed_by_rule[rule] = int(mask.sum())
        data = data.loc[~mask].reset_index(drop=True)

    drop(data["timestamp"].isna(), "invalid_timestamp")
    drop(data.duplicated(subset=["timestamp", *NUMERIC_COLUMNS], keep="first"), "duplicates")
    drop(data["rpm"].isna() | data["temperature"].isna(), "missing_required_values")
    drop(data["speed"] == SPEED_SENTINEL_KMH, "speed_sentinel_255")
    drop(_out_of_range(data["rpm"], RPM_RANGE), "rpm_out_of_range")
    drop(_out_of_range(data["speed"], SPEED_RANGE), "speed_out_of_range")
    drop(_out_of_range(data["temperature"], TEMPERATURE_RANGE), "temperature_out_of_range")

    report.clean_count = int(len(data))
    return data, report


def flag_4g_bursts(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula o intervalo entre chegadas (`dt_seconds`) e marca:
    - `is_burst`: pacote entregue em rajada (`dt < 0,25 s`) após atraso/falha de rede;
    - `is_long_gap`: intervalo acima de 2,5 s (queda de sinal ou nova sessão).
    """
    result = df.copy()
    dt_seconds = result["timestamp"].diff().dt.total_seconds()
    result["dt_seconds"] = dt_seconds
    result["is_burst"] = (dt_seconds < BURST_DT_SECONDS).fillna(False).astype(bool)
    result["is_long_gap"] = (dt_seconds > MAX_DERIVATIVE_DT_SECONDS).fillna(False).astype(bool)
    return result


def add_engineered_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Gera atributos para a modelagem:
    - `acceleration_ms2`: Δv/Δt em m/s², somente com Δt confiável e |a| ≤ 15 m/s²;
    - `rpm_delta`: variação de RPM entre amostras consecutivas confiáveis;
    - `rpm_per_speed`: RPM/velocidade quando `speed > 5 km/h` (assinatura da marcha).
    Atributos derivados do tempo são NaN em rajadas 4G e após quedas longas de sinal.
    """
    result = df if "is_burst" in df.columns else flag_4g_bursts(df)
    result = result.copy()
    nan_series = pd.Series(np.nan, index=result.index, dtype="float64")

    dt_seconds = result["dt_seconds"]
    derivative_valid = (
        dt_seconds.notna()
        & (dt_seconds > 0)
        & ~result["is_burst"]
        & ~result["is_long_gap"]
    )
    result["derivative_valid"] = derivative_valid.astype(bool)

    speed_ms = result["speed"] / KMH_TO_MS
    raw_accel = speed_ms.diff() / dt_seconds
    acceleration = raw_accel.where(derivative_valid & (raw_accel.abs() <= MAX_PHYSICAL_ACCEL_MS2))
    result["acceleration_ms2"] = acceleration.astype("float64")

    result["rpm_delta"] = result["rpm"].diff().where(derivative_valid).astype("float64")

    moving = result["speed"] > RPM_PER_SPEED_MIN_KMH
    rpm_per_speed = nan_series.copy()
    rpm_per_speed.loc[moving] = result.loc[moving, "rpm"] / result.loc[moving, "speed"]
    result["rpm_per_speed"] = rpm_per_speed
    return result


def classify_operating_regime(df: pd.DataFrame) -> pd.DataFrame:
    """
    Classifica cada amostra no regime operacional:
    - `engine_off`: RPM < 300 (motor desligado ou sem rotação);
    - `driving`: velocidade > 2 km/h;
    - `idle`: motor ligado com velocidade ≤ 2 km/h (marcha lenta);
    - `unknown`: motor ligado sem leitura de velocidade.
    """
    result = df.copy()
    engine_off = result["rpm"] < ENGINE_OFF_MAX_RPM
    driving = ~engine_off & (result["speed"] > IDLE_MAX_SPEED_KMH)
    idle = ~engine_off & (result["speed"] <= IDLE_MAX_SPEED_KMH)
    result["regime"] = np.select(
        [engine_off, driving, idle],
        [REGIME_ENGINE_OFF, REGIME_DRIVING, REGIME_IDLE],
        default=REGIME_UNKNOWN,
    )
    return result


def add_estimated_timestamp(
    df: pd.DataFrame,
    sample_period_seconds: float = NOMINAL_SAMPLE_PERIOD_SECONDS,
) -> pd.DataFrame:
    """
    Reconstrução ESTIMADA do horário de leitura em rajadas (alternativa D, apenas para EDA).

    Cada grupo = pacote líder (primeiro após a falha) + pacotes em rajada. O último pacote
    fica ancorado no seu horário de chegada e os anteriores recuam `sample_period_seconds`
    cada, sem ultrapassar o último horário real conhecido antes do grupo (nesse caso, o
    espaçamento é comprimido uniformemente). Nunca deve ser usado no treinamento do modelo.
    """
    result = df if "is_burst" in df.columns else flag_4g_bursts(df)
    result = result.copy()
    result["timestamp_est"] = result["timestamp"]
    result["is_timestamp_estimated"] = False
    if result.empty:
        return result

    is_burst = result["is_burst"].to_numpy()
    timestamps = result["timestamp"].tolist()
    estimated = list(timestamps)
    flags = [False] * len(result)
    period = pd.Timedelta(seconds=sample_period_seconds)

    index = 0
    total = len(result)
    while index < total:
        end = index
        while end + 1 < total and is_burst[end + 1]:
            end += 1
        size = end - index + 1
        if size > 1:
            last_ts = timestamps[end]
            step = period
            if index > 0:
                available = last_ts - timestamps[index - 1]
                step = min(period, available / size)
            for offset, row in enumerate(range(index, end + 1)):
                steps_back = size - 1 - offset
                estimated[row] = last_ts - step * steps_back
                flags[row] = steps_back > 0
        index = end + 1

    result["timestamp_est"] = pd.to_datetime(pd.Series(estimated, index=result.index), utc=True)
    result["is_timestamp_estimated"] = flags
    return result


def prepare_dataset(
    df: pd.DataFrame,
    include_estimated_timestamp: bool = True,
) -> tuple[pd.DataFrame, DataQualityReport]:
    """
    Orquestra o pipeline completo (limpeza → rajadas → atributos → regime) e devolve
    o DataFrame limpo e enriquecido junto do Relatório de Qualidade dos Dados.
    """
    clean_df, report = clean_telemetry(df)
    prepared = flag_4g_bursts(clean_df)
    prepared = add_engineered_features(prepared)
    prepared = classify_operating_regime(prepared)
    if include_estimated_timestamp:
        prepared = add_estimated_timestamp(prepared)

    report.burst_count = int(prepared["is_burst"].sum())
    report.long_gap_count = int(prepared["is_long_gap"].sum())
    report.derivative_valid_count = int(prepared["derivative_valid"].sum())
    return prepared, report
