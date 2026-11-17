from datetime import date, datetime, timedelta, timezone

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from frontend.app import (
    compute_acceleration,
    format_metric_delta,
    get_connection_status,
    local_day_to_utc_range,
    prepare_telemetry_dataframe,
)
from frontend.telemetry_utils import (
    build_interactive_line_chart,
    build_overview_detail_charts,
    downsample_for_chart,
)
from scripts.verify_e2e import analyze_telemetry_records


def test_prepare_dataframe_single_record_no_index_error():
    """
    Garante que um único registro não gere IndexError e deixe aceleração como NaN.
    """
    data = [
        {
            "id": 1,
            "rpm": 900.0,
            "temperature": 88.0,
            "speed": 0.0,
            "timestamp": "2026-10-20T12:00:00",
        }
    ]
    df = prepare_telemetry_dataframe(data)
    assert len(df) == 1
    assert pd.isna(df.iloc[0]["acceleration_ms2"])

    val, delta = format_metric_delta(df.iloc[-1]["rpm"], None, "RPM", decimals=0)
    assert val == "900 RPM"
    assert delta is None


def test_prepare_dataframe_sorts_chronologically_and_computes_acceleration():
    """
    Valida ordenação crescente de timestamps e cálculo correto de Δv/Δt em m/s².
    """
    # Simula resposta da API em ordem decrescente (mais recente primeiro)
    data = [
        {
            "id": 2,
            "rpm": 2500.0,
            "temperature": 90.0,
            "speed": 36.0,  # 10 m/s
            "timestamp": "2026-10-20T12:00:02",
        },
        {
            "id": 1,
            "rpm": 1200.0,
            "temperature": 89.0,
            "speed": 0.0,  # 0 m/s
            "timestamp": "2026-10-20T12:00:00",
        },
    ]
    df = prepare_telemetry_dataframe(data)
    assert list(df["id"]) == [1, 2]
    assert pd.isna(df.iloc[0]["acceleration_ms2"])
    # Δv = 10 m/s em Δt = 2 s -> 5.0 m/s²
    assert df.iloc[1]["acceleration_ms2"] == pytest.approx(5.0)


def test_compute_acceleration_handles_null_speed_and_zero_dt():
    """
    Garante proteção contra velocidade nula (Optional[float]), timestamps idênticos,
    rajadas 4G (dt < 0.25 s) e picos não-físicos de velocidade (ex: sentinela 255 km/h).
    """
    df = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2026-10-20T12:00:00.000Z",
                    "2026-10-20T12:00:00.000Z",  # dt == 0
                    "2026-10-20T12:00:01.000Z",  # speed nula
                    "2026-10-20T12:00:02.000Z",  # base 0 km/h
                    "2026-10-20T12:00:02.012Z",  # rajada 12ms -> NaN
                    "2026-10-20T12:00:03.012Z",  # salto sentinela 255 km/h -> NaN (> 15 m/s²)
                ]
            ),
            "speed": [36.0, 36.0, None, 0.0, 14.0, 255.0],
        }
    )
    result = compute_acceleration(df)
    assert result["acceleration_ms2"].isna().all()


def test_verify_e2e_rejects_non_positive_expected_interval():
    """
    Garante falha explícita ao passar expected_interval_s <= 0 para análise E2E.
    """
    with pytest.raises(ValueError, match="expected_interval_s"):
        analyze_telemetry_records([], expected_interval_s=0.0)


def test_connection_status_online_and_offline_thresholds():
    """
    Valida transição do badge de conexão no limiar exato de 5 segundos.
    """
    now = datetime(2026, 10, 20, 12, 0, 10, tzinfo=timezone.utc)

    online_ts = pd.Timestamp("2026-10-20 12:00:06")  # 4s atrás (naive UTC do SQLite)
    is_online, elapsed = get_connection_status(online_ts, now_utc=now)
    assert is_online is True
    assert elapsed == pytest.approx(4.0)

    offline_ts = pd.Timestamp("2026-10-20 12:00:05")  # exatamente 5s atrás
    is_online, elapsed = get_connection_status(offline_ts, now_utc=now)
    assert is_online is False
    assert elapsed == pytest.approx(5.0)


def test_verify_e2e_analysis_frequency_and_packet_loss():
    """
    Valida cálculo de frequência média (Hz) e detecção de saltos anômalos no verify_e2e.
    """
    base = datetime(2026, 10, 20, 15, 0, 0, tzinfo=timezone.utc)
    # Sequência com salto de 4s entre o pacote 2 e 3 (~3 pacotes perdidos a 1 Hz)
    offsets = [0, 1, 2, 6, 7]
    records = [
        {
            "id": idx + 1,
            "rpm": 2000.0,
            "temperature": 90.0,
            "speed": 50.0 if idx != 1 else None,
            "timestamp": (base + timedelta(seconds=offset)).isoformat(),
        }
        for idx, offset in enumerate(offsets)
    ]

    summary = analyze_telemetry_records(
        records,
        expected_interval_s=1.0,
        gap_threshold_s=2.5,
        total_db_count=50,
    )
    assert summary["total_records"] == 50
    assert summary["analyzed_records"] == 5
    assert summary["duration_seconds"] == pytest.approx(7.0)
    assert summary["avg_frequency_hz"] == pytest.approx(4 / 7, rel=1e-3)
    assert len(summary["anomalous_gaps"]) == 1
    assert summary["anomalous_gaps"][0]["delta_s"] == pytest.approx(4.0)
    assert summary["estimated_missed_packets"] == 3
    assert summary["null_speed_count"] == 1


def _run_dashboard_for_apptest(sample_data: list[dict]) -> None:
    """
    Função auxiliar isolada em arquivo para execução via Streamlit AppTest.
    """
    from frontend.app import render_dashboard

    render_dashboard(sample_data)


def test_render_dashboard_handles_empty_single_and_multi_records():
    """
    Executa render_dashboard no motor real do Streamlit (AppTest) para validar
    0 registros, 1 registro (sem IndexError) e múltiplos registros com aceleração.
    """
    # 1. Lista vazia
    at_empty = AppTest.from_function(_run_dashboard_for_apptest, kwargs={"sample_data": []})
    at_empty.run()
    assert not at_empty.exception
    assert len(at_empty.error) == 1

    # 2. Apenas 1 registro e speed nulo (caso que causava IndexError / TypeError)
    single_sample = [
        {
            "id": 1,
            "rpm": 950.0,
            "temperature": 85.0,
            "speed": None,
            "timestamp": "2026-10-20T12:00:00Z",
        }
    ]
    at_single = AppTest.from_function(
        _run_dashboard_for_apptest,
        kwargs={"sample_data": single_sample},
    )
    at_single.run()
    assert not at_single.exception
    assert len(at_single.metric) == 4
    assert at_single.metric[0].value == "950 RPM"
    assert at_single.metric[2].value == "--"
    assert at_single.metric[3].value == "--"

    # 3. Múltiplos registros recentes (Online < 5s)
    now_iso = datetime.now(timezone.utc).isoformat()
    prev_iso = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    multi_sample = [
        {
            "id": 2,
            "rpm": 2600.0,
            "temperature": 91.0,
            "speed": 54.0,
            "timestamp": now_iso,
        },
        {
            "id": 1,
            "rpm": 2000.0,
            "temperature": 90.0,
            "speed": 36.0,
            "timestamp": prev_iso,
        },
    ]
    at_multi = AppTest.from_function(
        _run_dashboard_for_apptest,
        kwargs={"sample_data": multi_sample},
    )
    at_multi.run()
    assert not at_multi.exception
    assert len(at_multi.success) == 1
    assert "Veículo Conectado / Online" in at_multi.success[0].value
    assert len(at_multi.metric) == 4
    assert "m/s²" in at_multi.metric[3].value


def test_local_day_to_utc_range_and_downsample():
    """
    Valida conversão de dia local (UTC-3) para janela UTC e amostragem segura para gráficos.
    """
    start_utc, end_utc = local_day_to_utc_range(date(2026, 11, 16), tz_offset_minutes=-180)
    assert start_utc == datetime(2026, 11, 16, 3, 0, 0, tzinfo=timezone.utc)
    assert end_utc.date() == date(2026, 11, 17)
    assert end_utc.hour == 2

    df = pd.DataFrame({"x": list(range(100))})
    sampled = downsample_for_chart(df, max_points=20)
    assert len(sampled) <= 21
    assert sampled.iloc[0]["x"] == 0
    assert sampled.iloc[-1]["x"] == 99


def test_altair_chart_builders_compile_specs():
    """
    Verifica a geração dos gráficos Altair interativos e Overview + Detail.
    """
    df = prepare_telemetry_dataframe(
        [
            {
                "id": 1,
                "rpm": 950.0,
                "temperature": 88.0,
                "speed": 0.0,
                "timestamp": "2026-11-16T18:00:00Z",
            },
            {
                "id": 2,
                "rpm": 2100.0,
                "temperature": 90.0,
                "speed": 36.0,
                "timestamp": "2026-11-16T18:00:02Z",
            },
        ]
    )
    single_chart = build_interactive_line_chart(df, "rpm", "RPM", "#FF4B4B")
    assert "$schema" in single_chart.to_dict()

    combined = build_overview_detail_charts(
        df,
        [("rpm", "RPM", "#FF4B4B"), ("speed", "Velocidade (km/h)", "#0068C9")],
    )
    assert "vconcat" in combined.to_dict()


def _run_all_pages_for_apptest(page_name: str, sample_days: list[dict], sample_data: list[dict]) -> None:
    """
    Executa cada nova página modular com mock da API dentro do AppTest.
    """
    from unittest.mock import patch

    from frontend.views.ai_diagnostics import render_ai_diagnostics_page
    from frontend.views.eda import render_eda_page
    from frontend.views.history import render_history_page
    from frontend.views.live import render_dashboard

    with (
        patch("frontend.views.common.fetch_telemetry_days", return_value=sample_days),
        patch("frontend.views.common.fetch_telemetry", return_value=sample_data),
    ):
        if page_name == "live_paused":
            render_dashboard(sample_data, interactive_mode=True)
        elif page_name == "history":
            render_history_page()
        elif page_name == "eda":
            render_eda_page()
        elif page_name == "ai":
            render_ai_diagnostics_page()


def test_new_views_render_cleanly_in_streamlit():
    """
    Garante renderização sem exceções nas páginas Pausa Ao Vivo, Histórico, EDA e Diagnóstico IA.
    """
    sample_days = [
        {
            "date": "2026-11-16",
            "count": 2,
            "first_timestamp": "2026-11-16T18:00:00",
            "last_timestamp": "2026-11-16T18:00:02",
        }
    ]
    sample_data = [
        {
            "id": 2,
            "rpm": 2200.0,
            "temperature": 91.0,
            "speed": 36.0,
            "timestamp": "2026-11-16T18:00:02",
        },
        {
            "id": 1,
            "rpm": 950.0,
            "temperature": 89.0,
            "speed": 0.0,
            "timestamp": "2026-11-16T18:00:00",
        },
    ]

    for page_key in ("live_paused", "history", "eda", "ai"):
        at = AppTest.from_function(
            _run_all_pages_for_apptest,
            kwargs={
                "page_name": page_key,
                "sample_days": sample_days,
                "sample_data": sample_data,
            },
        )
        at.run()
        assert not at.exception, f"Falha na página {page_key}: {at.exception}"
