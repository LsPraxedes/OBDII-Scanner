from datetime import datetime, timedelta, timezone
import sqlite3

import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from backend.ml.data_preparation import (
    REGIME_DRIVING,
    REGIME_ENGINE_OFF,
    REGIME_IDLE,
    REGIME_UNKNOWN,
    add_estimated_timestamp,
    classify_operating_regime,
    clean_telemetry,
    flag_4g_bursts,
    load_telemetry_from_sqlite,
    prepare_dataset,
)
from backend.ml.eda_analysis import (
    build_eda_summary,
    compute_correlation_matrix,
    compute_normal_thresholds,
    describe_by_regime,
    describe_with_percentiles,
    regime_distribution,
)
from scripts.run_eda import main as run_eda_main

BASE_TS = datetime(2026, 11, 16, 18, 0, 0, tzinfo=timezone.utc)


def _make_records(rows: list[tuple[float, float, float, float | None]]) -> pd.DataFrame:
    """
    Cria DataFrame sintético a partir de tuplas (offset_s, rpm, temperature, speed).
    """
    return pd.DataFrame(
        [
            {
                "id": index + 1,
                "rpm": rpm,
                "temperature": temperature,
                "speed": speed,
                "timestamp": (BASE_TS + timedelta(seconds=offset)).isoformat(),
            }
            for index, (offset, rpm, temperature, speed) in enumerate(rows)
        ]
    )


def test_clean_telemetry_removes_physical_outliers_and_reports_by_rule():
    """
    Remove sentinela 255 km/h, RPM negativo/excessivo, temperatura impossível e duplicatas,
    contabilizando cada regra no Relatório de Qualidade dos Dados.
    """
    df = _make_records(
        [
            (0, 900.0, 85.0, 0.0),
            (1, 950.0, 86.0, 255.0),  # sentinela 0xFF
            (2, -10.0, 86.0, 10.0),  # rpm < 0
            (3, 9000.0, 86.0, 10.0),  # rpm > 8000
            (4, 2000.0, 200.0, 30.0),  # temperatura > 140
            (5, 2100.0, 87.0, 300.0),  # velocidade > 220
            (6, 2200.0, 87.0, None),  # velocidade nula é permitida
        ]
    )
    df = pd.concat([df, df.iloc[[0]].assign(id=99)], ignore_index=True)  # duplicata

    clean_df, report = clean_telemetry(df)

    assert report.raw_count == 8
    assert report.clean_count == 2
    assert report.removed_count == 6
    assert report.removed_by_rule["duplicates"] == 1
    assert report.removed_by_rule["speed_sentinel_255"] == 1
    assert report.removed_by_rule["rpm_out_of_range"] == 2
    assert report.removed_by_rule["temperature_out_of_range"] == 1
    assert report.removed_by_rule["speed_out_of_range"] == 1
    assert 255.0 not in clean_df["speed"].tolist()
    assert (clean_df["rpm"] >= 0).all()
    assert clean_df["timestamp"].is_monotonic_increasing
    assert str(clean_df["timestamp"].dt.tz) == "UTC"


def test_clean_telemetry_sorts_by_timestamp_and_id():
    """
    Ordena cronologicamente por ["timestamp", "id"] mesmo com entrada desordenada.
    """
    df = _make_records([(2, 1000.0, 85.0, 5.0), (0, 900.0, 85.0, 0.0), (1, 950.0, 85.0, 2.0)])
    clean_df, _ = clean_telemetry(df)
    assert clean_df["rpm"].tolist() == [900.0, 950.0, 1000.0]


def test_burst_rows_are_kept_but_time_derivatives_are_nan():
    """
    Pacotes em rajada (dt < 0,25 s) permanecem no dataset, mas aceleração e ΔRPM ficam NaN.
    Após queda longa de sinal (dt > 2,5 s) as derivadas também são anuladas.
    """
    df = _make_records(
        [
            (0.0, 1000.0, 85.0, 10.0),
            (1.0, 1200.0, 85.0, 13.6),  # +1 m/s em 1 s -> 1 m/s²
            (20.0, 1500.0, 85.0, 20.0),  # queda longa de sinal
            (20.01, 1550.0, 85.0, 22.0),  # rajada
            (20.02, 1600.0, 85.0, 24.0),  # rajada
            (21.0, 1650.0, 85.0, 27.6),  # normal
        ]
    )
    prepared, report = prepare_dataset(df)

    assert len(prepared) == 6
    assert prepared["is_burst"].tolist() == [False, False, False, True, True, False]
    assert prepared["is_long_gap"].tolist() == [False, False, True, False, False, False]
    assert report.burst_count == 2
    assert report.long_gap_count == 1
    assert prepared.loc[1, "acceleration_ms2"] == pytest.approx(1.0)
    assert prepared.loc[1, "rpm_delta"] == pytest.approx(200.0)
    for row in (0, 2, 3, 4):
        assert pd.isna(prepared.loc[row, "acceleration_ms2"])
        assert pd.isna(prepared.loc[row, "rpm_delta"])
    assert report.derivative_valid_count == 2


def test_rpm_per_speed_only_above_five_kmh():
    """
    A razão RPM/velocidade só é calculada com velocidade > 5 km/h.
    """
    df = _make_records([(0, 900.0, 85.0, 0.0), (1, 1500.0, 85.0, 5.0), (2, 2000.0, 85.0, 40.0)])
    prepared, _ = prepare_dataset(df)
    assert pd.isna(prepared.loc[0, "rpm_per_speed"])
    assert pd.isna(prepared.loc[1, "rpm_per_speed"])
    assert prepared.loc[2, "rpm_per_speed"] == pytest.approx(50.0)


def test_classify_operating_regime():
    """
    Classifica engine_off (RPM < 300 parado), idle (speed ≤ 2), driving (speed > 2,
    inclusive motor apagado em movimento para não suprimir alerta) e unknown.
    """
    df = pd.DataFrame(
        {
            "rpm": [0.0, 950.0, 900.0, 2500.0, 0.0, 1000.0],
            "speed": [0.0, 0.0, 2.0, 40.0, 40.0, np.nan],
        }
    )
    result = classify_operating_regime(df)
    assert result["regime"].tolist() == [
        REGIME_ENGINE_OFF,
        REGIME_IDLE,
        REGIME_IDLE,
        REGIME_DRIVING,
        REGIME_DRIVING,
        REGIME_UNKNOWN,
    ]


def test_estimated_timestamp_reconstructs_burst_group():
    """
    O último pacote da rajada fica ancorado na chegada; os anteriores recuam 1 s,
    sem ultrapassar o último horário real conhecido (compressão uniforme).
    """
    df = _make_records(
        [
            (0.0, 1000.0, 85.0, 10.0),
            (10.0, 1000.0, 85.0, 10.0),  # líder após falha
            (10.01, 1000.0, 85.0, 10.0),
            (10.02, 1000.0, 85.0, 10.0),
        ]
    )
    clean_df, _ = clean_telemetry(df)
    result = add_estimated_timestamp(flag_4g_bursts(clean_df))
    est_offsets = [(ts - BASE_TS).total_seconds() for ts in result["timestamp_est"]]
    assert est_offsets == pytest.approx([0.0, 8.02, 9.02, 10.02])
    assert result["is_timestamp_estimated"].tolist() == [False, True, True, False]

    compressed = _make_records(
        [(0.0, 1000.0, 85.0, 10.0), (1.0, 1000.0, 85.0, 10.0), (1.01, 1000.0, 85.0, 10.0), (1.02, 1000.0, 85.0, 10.0)]
    )
    clean_df, _ = clean_telemetry(compressed)
    result = add_estimated_timestamp(flag_4g_bursts(clean_df))
    est = result["timestamp_est"]
    assert est.is_monotonic_increasing
    assert est.iloc[1] > est.iloc[0]


def test_load_telemetry_from_sqlite_missing_and_existing(tmp_path):
    """
    Retorna DataFrame vazio com colunas esperadas se o .db não existir e carrega um .db temporário.
    """
    missing = load_telemetry_from_sqlite(tmp_path / "nao_existe.db")
    assert missing.empty
    assert {"id", "rpm", "temperature", "speed", "timestamp"} <= set(missing.columns)

    db_path = tmp_path / "telemetry.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "CREATE TABLE telemetry (id INTEGER PRIMARY KEY, rpm FLOAT, temperature FLOAT, "
            "speed FLOAT, timestamp DATETIME)"
        )
        conn.executemany(
            "INSERT INTO telemetry (rpm, temperature, speed, timestamp) VALUES (?, ?, ?, ?)",
            [
                (900.0, 85.0, 0.0, "2026-11-16 18:00:00.000000"),
                (1500.0, 86.0, 255.0, "2026-11-16 18:00:01.000000"),
            ],
        )
    loaded = load_telemetry_from_sqlite(db_path)
    assert len(loaded) == 2

    empty_db = tmp_path / "vazio.db"
    sqlite3.connect(empty_db).close()
    assert load_telemetry_from_sqlite(empty_db).empty


def test_correlation_matrix_and_eda_statistics():
    """
    Matriz de correlação 4x4 simétrica com diagonal 1; percentis e limiares coerentes.
    """
    rows = []
    for second in range(60):
        speed = 0.0 if second < 20 else float(second)
        rpm = 950.0 + (second % 3) if second < 20 else 800.0 + 40.0 * second
        rows.append((float(second), rpm, 85.0 + (second % 4), speed))
    prepared, _ = prepare_dataset(_make_records(rows))

    corr = compute_correlation_matrix(prepared)
    assert corr.shape == (4, 4)
    assert np.allclose(np.diag(corr.to_numpy()), 1.0)
    assert np.allclose(corr.to_numpy(), corr.to_numpy().T, equal_nan=True)
    assert corr.loc["rpm", "speed"] > 0.9

    stats = describe_with_percentiles(prepared)
    assert {"P05", "P95", "P99", "mean", "std"} <= set(stats.index)

    by_regime = describe_by_regime(prepared)
    assert by_regime[REGIME_IDLE].loc["count", "rpm"] == 20
    assert by_regime[REGIME_DRIVING].loc["count", "rpm"] == 40

    distribution = regime_distribution(prepared)
    assert distribution["share_pct"].sum() == pytest.approx(100.0)

    thresholds = compute_normal_thresholds(prepared)
    assert set(thresholds["scope"]) == {"global", REGIME_IDLE, REGIME_DRIVING}
    assert (thresholds["p05"] <= thresholds["p95"]).all()
    assert (thresholds["p95"] <= thresholds["p99"]).all()

    summary = build_eda_summary(prepared)
    assert set(summary) == {"global_stats", "regime_stats", "regime_distribution", "correlation", "thresholds"}


def test_eda_functions_handle_empty_dataframe():
    """
    Funções da EDA não lançam exceções com DataFrame vazio.
    """
    prepared, report = prepare_dataset(pd.DataFrame())
    assert prepared.empty
    assert report.raw_count == 0
    assert describe_with_percentiles(prepared).empty
    assert compute_normal_thresholds(prepared).empty
    assert regime_distribution(prepared).empty


def test_run_eda_cli_exports_clean_csv(tmp_path, capsys):
    """
    A CLI audita um .db temporário e exporta o CSV limpo sem o registro sentinela.
    """
    db_path = tmp_path / "telemetry.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "CREATE TABLE telemetry (id INTEGER PRIMARY KEY, rpm FLOAT, temperature FLOAT, "
            "speed FLOAT, timestamp DATETIME)"
        )
        conn.executemany(
            "INSERT INTO telemetry (rpm, temperature, speed, timestamp) VALUES (?, ?, ?, ?)",
            [
                (900.0, 85.0, 0.0, "2026-11-16 18:00:00.000000"),
                (950.0, 85.0, 255.0, "2026-11-16 18:00:01.000000"),
                (1800.0, 86.0, 20.0, "2026-11-16 18:00:02.000000"),
                (2000.0, 86.0, 25.0, "2026-11-16 18:00:03.000000"),
            ],
        )

    output_dir = tmp_path / "clean"
    exit_code = run_eda_main(["--db", str(db_path), "--export-clean", "--output-dir", str(output_dir)])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "RELATÓRIO DE QUALIDADE DOS DADOS" in captured.out
    exported = list(output_dir.glob("telemetry_clean_*.csv"))
    assert len(exported) == 1
    exported_df = pd.read_csv(exported[0])
    assert len(exported_df) == 3
    assert 255.0 not in exported_df["speed"].tolist()

    assert run_eda_main(["--db", str(tmp_path / "ausente.db")]) == 1


def _run_eda_page_for_apptest(sample_days: list[dict], sample_data: list[dict]) -> None:
    """
    Executa a página EDA com a API mockada dentro do AppTest.
    """
    from unittest.mock import patch

    from frontend.views.eda import render_eda_page

    with (
        patch("frontend.views.common.fetch_telemetry_days", return_value=sample_days),
        patch("frontend.views.common.fetch_telemetry", return_value=sample_data),
    ):
        render_eda_page()


def test_eda_page_renders_crispdm_sections():
    """
    A página EDA renderiza sem exceções e exibe as seções da Semana 6
    (Bruto vs. Limpo, correlação, regimes e limiares), inclusive com outlier 255 km/h.
    """
    sample_data = []
    for second in range(30):
        speed = 0.0 if second < 10 else float(second)
        sample_data.append(
            {
                "id": second + 1,
                "rpm": 950.0 if second < 10 else 800.0 + 40.0 * second,
                "temperature": 85.0 + (second % 3),
                "speed": 255.0 if second == 15 else speed,
                "timestamp": (BASE_TS + timedelta(seconds=second)).isoformat(),
            }
        )
    sample_days = [
        {
            "date": "2026-11-16",
            "count": len(sample_data),
            "first_timestamp": sample_data[0]["timestamp"],
            "last_timestamp": sample_data[-1]["timestamp"],
        }
    ]

    at = AppTest.from_function(
        _run_eda_page_for_apptest,
        kwargs={"sample_days": sample_days, "sample_data": sample_data},
    )
    at.run(timeout=30)
    assert not at.exception, f"Falha na página EDA: {at.exception}"

    markdown_text = " ".join(element.value for element in at.markdown)
    assert "Qualidade dos Dados: Bruto vs. Limpo" in markdown_text
    assert "Matriz de Correlação" in markdown_text
    assert "Comparação por Regime Operacional" in markdown_text
    assert "Limiares Normais Preliminares" in markdown_text

    metric_values = {metric.label: metric.value for metric in at.metric}
    assert metric_values["Registros brutos"] == "30"
    assert metric_values["Registros limpos"] == "29"
