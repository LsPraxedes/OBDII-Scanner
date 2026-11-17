import time
from typing import Any

import pandas as pd
import streamlit as st

from frontend.telemetry_utils import (
    REFRESH_INTERVAL_SECONDS,
    build_interactive_line_chart,
    fetch_telemetry,
    format_metric_delta,
    get_connection_status,
    prepare_telemetry_dataframe,
)


def render_connection_banner(latest_timestamp: pd.Timestamp) -> None:
    """
    Exibe o indicador visual de status da conexão 4G/MQTTS do veículo.
    """
    is_online, elapsed_seconds = get_connection_status(latest_timestamp)
    if is_online:
        st.success(
            f"🟢 Veículo Conectado / Online (Transmissão 4G Ativa) — "
            f"Última leitura há {elapsed_seconds:.1f} s"
        )
    else:
        st.error(
            f"🔴 Sinal Desconectado / Carro Desligado — "
            f"Última leitura há {elapsed_seconds:.1f} s"
        )


def _render_kpis(latest: pd.Series, previous: pd.Series | None) -> None:
    """
    Renderiza os 4 cartões de métricas instantâneas (RPM, Temperatura, Velocidade e Aceleração).
    """
    st.subheader("Últimas Leituras")
    cols = st.columns(4)

    rpm_val, rpm_delta = format_metric_delta(
        latest.get("rpm"),
        previous.get("rpm") if previous is not None else None,
        "RPM",
        decimals=0,
    )
    temp_val, temp_delta = format_metric_delta(
        latest.get("temperature"),
        previous.get("temperature") if previous is not None else None,
        "°C",
        decimals=0,
    )
    speed_val, speed_delta = format_metric_delta(
        latest.get("speed"),
        previous.get("speed") if previous is not None else None,
        "km/h",
        decimals=0,
    )
    accel_val, accel_delta = format_metric_delta(
        latest.get("acceleration_ms2"),
        previous.get("acceleration_ms2") if previous is not None else None,
        "m/s²",
        decimals=2,
        signed_value=True,
    )

    cols[0].metric("Conta-giros", value=rpm_val, delta=rpm_delta)
    cols[1].metric("Temperatura", value=temp_val, delta=temp_delta)
    cols[2].metric("Velocidade", value=speed_val, delta=speed_delta)
    cols[3].metric("Aceleração Atual", value=accel_val, delta=accel_delta)


def render_dashboard(data: list[dict[str, Any]], interactive_mode: bool = False) -> None:
    """
    Renderiza os indicadores em tempo real, gráficos cronológicos, aceleração
    instantânea e relação RPM x Velocidade no Streamlit.
    """
    df = prepare_telemetry_dataframe(data)
    if df.empty:
        st.error("🔴 Sinal Desconectado / Carro Desligado")
        st.info(
            "Nenhum dado recebido ainda. Verifique o backend FastAPI, "
            "a conexão do ESP32 no veículo ou ligue o scripts/mock_car.py."
        )
        return

    latest = df.iloc[-1]
    previous = df.iloc[-2] if len(df) >= 2 else None

    render_connection_banner(latest["timestamp"])
    _render_kpis(latest, previous)

    plot_df = df
    if interactive_mode and len(df) >= 2:
        st.info(
            "Modo de inspeção pausado: use o controle de janela abaixo ou o scroll/arraste "
            "sobre os gráficos para navegar sem voltar ao início."
        )
        min_dt = df["local_timestamp"].iloc[0].to_pydatetime()
        max_dt = df["local_timestamp"].iloc[-1].to_pydatetime()
        if min_dt < max_dt:
            selected_start, selected_end = st.slider(
                "Recorte da janela carregada (BRT)",
                min_value=min_dt,
                max_value=max_dt,
                value=(min_dt, max_dt),
                format="HH:mm:ss",
            )
            mask = (df["local_timestamp"] >= pd.Timestamp(selected_start)) & (
                df["local_timestamp"] <= pd.Timestamp(selected_end)
            )
            filtered = df.loc[mask]
            if not filtered.empty:
                plot_df = filtered

    st.subheader("Histórico Recente")
    chart_specs = [
        ("rpm", "Engine RPM", "#FF4B4B", None),
        ("temperature", "Temperatura (°C)", "#FFAA00", None),
        (
            "speed",
            "Velocidade (km/h)",
            "#0068C9",
            "Aguardando leituras válidas do sensor de velocidade (PID 0x0D).",
        ),
        (
            "acceleration_ms2",
            "Aceleração Instantânea (m/s²)",
            "#00B050",
            "Aguardando ao menos duas leituras consecutivas de velocidade para calcular a aceleração.",
        ),
    ]
    chart_df = plot_df.set_index("local_timestamp")
    for col_name, label, color, empty_msg in chart_specs:
        if empty_msg is not None and plot_df[col_name].dropna().empty:
            st.write(f"**{label}**")
            st.info(empty_msg)
            continue

        if interactive_mode:
            st.altair_chart(
                build_interactive_line_chart(plot_df, col_name, label, color),
                use_container_width=True,
            )
        else:
            st.write(f"**{label}**")
            st.line_chart(chart_df[col_name], color=color)

    st.subheader("Análise de Condução (RPM vs Velocidade)")
    st.caption(
        "A dispersão entre rotação do motor e velocidade destaca visualmente as "
        "faixas lineares correspondentes às marchas engatadas no veículo."
    )
    gear_df = plot_df.dropna(subset=["speed", "rpm"])
    if gear_df.empty:
        st.info("Sem pares válidos de RPM e Velocidade para plotar a relação de marchas.")
    else:
        scatter_df = gear_df[["speed", "rpm"]].rename(
            columns={"speed": "Velocidade (km/h)", "rpm": "Rotação (RPM)"}
        )
        st.scatter_chart(
            scatter_df,
            x="Velocidade (km/h)",
            y="Rotação (RPM)",
            color="#7B61FF",
        )

    with st.expander("Ver Dados Tabulares"):
        display_df = plot_df.iloc[::-1].head(10).reset_index(drop=True)
        st.dataframe(display_df, use_container_width=True)


def render_live_page(live_limit: int = 300, auto_refresh: bool = True) -> None:
    """
    Controla o fluxo da página de monitoramento em tempo real com suporte a pausa para inspeção.
    """
    placeholder = st.empty()

    if auto_refresh:
        while True:
            data = fetch_telemetry(limit=live_limit)
            with placeholder.container():
                render_dashboard(data, interactive_mode=False)
            time.sleep(REFRESH_INTERVAL_SECONDS)
    else:
        data = fetch_telemetry(limit=live_limit)
        with placeholder.container():
            render_dashboard(data, interactive_mode=True)
        if st.button("Atualizar Manualmente"):
            st.rerun()
