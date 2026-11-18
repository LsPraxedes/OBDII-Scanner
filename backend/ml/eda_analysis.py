"""
Análise Exploratória dos Dados (EDA — CRISP-DM, Semana 6).

Funções puras sobre o DataFrame já preparado por `backend.ml.data_preparation.prepare_dataset`:
estatísticas descritivas com percentis, comparação por regime operacional, matriz de
correlação e limiares normais preliminares do veículo (base para a Semana 7).
"""

from typing import Any

import pandas as pd

from backend.ml.data_preparation import REGIME_DRIVING, REGIME_IDLE

STATS_COLUMNS = ["rpm", "temperature", "speed", "acceleration_ms2"]
CORRELATION_COLUMNS = ["rpm", "temperature", "speed", "acceleration_ms2"]
THRESHOLD_COLUMNS = ["rpm", "temperature", "speed", "acceleration_ms2", "rpm_per_speed"]
COMPARED_REGIMES = (REGIME_IDLE, REGIME_DRIVING)
GLOBAL_SCOPE = "global"

PERCENTILES = [0.05, 0.25, 0.50, 0.75, 0.95, 0.99]
PERCENTILE_LABELS = {"5%": "P05", "25%": "P25", "50%": "P50", "75%": "P75", "95%": "P95", "99%": "P99"}


def _existing_columns(df: pd.DataFrame, columns: list[str]) -> list[str]:
    """Filtra apenas as colunas presentes no DataFrame, preservando a ordem."""
    return [column for column in columns if column in df.columns]


def describe_with_percentiles(df: pd.DataFrame, columns: list[str] | None = None) -> pd.DataFrame:
    """
    Equivalente ao `describe()` do Pandas acrescido dos percentis P05, P95 e P99.
    """
    selected = _existing_columns(df, columns or STATS_COLUMNS)
    if df.empty or not selected:
        return pd.DataFrame(columns=selected)
    numeric = df[selected].apply(pd.to_numeric, errors="coerce").astype("float64")
    summary = numeric.describe(percentiles=PERCENTILES)
    return summary.rename(index=PERCENTILE_LABELS)


def describe_by_regime(
    df: pd.DataFrame,
    columns: list[str] | None = None,
    regimes: tuple[str, ...] = COMPARED_REGIMES,
) -> dict[str, pd.DataFrame]:
    """
    Estatísticas descritivas separadas por regime operacional (padrão: `idle` vs. `driving`).
    """
    if "regime" not in df.columns:
        return {regime: pd.DataFrame() for regime in regimes}
    return {
        regime: describe_with_percentiles(df.loc[df["regime"] == regime], columns)
        for regime in regimes
    }


def regime_distribution(df: pd.DataFrame) -> pd.DataFrame:
    """
    Contagem e participação percentual de cada regime operacional no conjunto limpo.
    """
    if df.empty or "regime" not in df.columns:
        return pd.DataFrame(columns=["regime", "count", "share_pct"])
    counts = df["regime"].value_counts().rename_axis("regime").reset_index(name="count")
    counts["share_pct"] = (100.0 * counts["count"] / counts["count"].sum()).round(2)
    return counts


def compute_correlation_matrix(
    df: pd.DataFrame,
    columns: list[str] | None = None,
) -> pd.DataFrame:
    """
    Matriz de correlação de Pearson entre RPM, temperatura, velocidade e aceleração.
    """
    selected = _existing_columns(df, columns or CORRELATION_COLUMNS)
    if df.empty or not selected:
        return pd.DataFrame(index=selected, columns=selected, dtype="float64")
    numeric = df[selected].apply(pd.to_numeric, errors="coerce").astype("float64")
    return numeric.corr(method="pearson")


def compute_normal_thresholds(
    df: pd.DataFrame,
    columns: list[str] | None = None,
    regimes: tuple[str, ...] = COMPARED_REGIMES,
) -> pd.DataFrame:
    """
    Limiares normais preliminares por escopo (global e por regime) e variável:
    faixa normal = [P05, P95]; P99 sinaliza o limite de alerta preliminar.
    """
    selected = _existing_columns(df, columns or THRESHOLD_COLUMNS)
    output_columns = ["scope", "variable", "samples", "min", "p05", "p50", "p95", "p99", "max"]
    if df.empty or not selected:
        return pd.DataFrame(columns=output_columns)

    scopes: list[tuple[str, pd.DataFrame]] = [(GLOBAL_SCOPE, df)]
    if "regime" in df.columns:
        scopes.extend((regime, df.loc[df["regime"] == regime]) for regime in regimes)

    rows: list[dict[str, Any]] = []
    for scope, subset in scopes:
        for variable in selected:
            values = pd.to_numeric(subset[variable], errors="coerce").dropna()
            if values.empty:
                continue
            quantiles = values.quantile([0.05, 0.50, 0.95, 0.99])
            rows.append(
                {
                    "scope": scope,
                    "variable": variable,
                    "samples": int(values.size),
                    "min": float(values.min()),
                    "p05": float(quantiles.loc[0.05]),
                    "p50": float(quantiles.loc[0.50]),
                    "p95": float(quantiles.loc[0.95]),
                    "p99": float(quantiles.loc[0.99]),
                    "max": float(values.max()),
                }
            )
    return pd.DataFrame(rows, columns=output_columns)


def build_eda_summary(df: pd.DataFrame) -> dict[str, Any]:
    """
    Consolida todos os artefatos da EDA em um único dicionário (CLI, frontend e relatório).
    """
    return {
        "global_stats": describe_with_percentiles(df),
        "regime_stats": describe_by_regime(df),
        "regime_distribution": regime_distribution(df),
        "correlation": compute_correlation_matrix(df),
        "thresholds": compute_normal_thresholds(df),
    }
