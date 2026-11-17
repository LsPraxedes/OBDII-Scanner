import altair as alt
import pandas as pd
import streamlit as st

from frontend.telemetry_utils import build_overview_detail_charts
from frontend.views.common import select_and_load_day_dataframe


def render_history_page() -> None:
    """
    Renderiza a página de histórico por data, com barra de rolagem/seleção temporal
    interativa sem resets, resumo da viagem e exportação CSV.
    """
    st.subheader("Histórico de Telemetria por Dia")
    st.caption(
        "Explore viagens completas do dia atual ou de datas anteriores sem interferência "
        "da atualização automática. Arraste o seletor no gráfico superior para dar zoom e rolar."
    )

    selected_date, df = select_and_load_day_dataframe(
        selectbox_label="Selecione a data para análise",
        empty_days_message=(
            "Nenhum dia encontrado no banco ou API indisponível. "
            "Verifique se o backend FastAPI está em execução."
        ),
    )
    if selected_date is None or df.empty:
        return

    filtered_df = df
    if len(df) >= 2:
        min_dt = df["local_timestamp"].iloc[0].to_pydatetime()
        max_dt = df["local_timestamp"].iloc[-1].to_pydatetime()
        if min_dt < max_dt:
            start_sel, end_sel = st.slider(
                "Recorte de horário no dia (BRT / UTC-3)",
                min_value=min_dt,
                max_value=max_dt,
                value=(min_dt, max_dt),
                format="HH:mm:ss",
            )
            mask = (df["local_timestamp"] >= pd.Timestamp(start_sel)) & (
                df["local_timestamp"] <= pd.Timestamp(end_sel)
            )
            sliced = df.loc[mask]
            if not sliced.empty:
                filtered_df = sliced

    duration_s = 0.0
    if len(filtered_df) >= 2:
        duration_s = max(
            0.0,
            float(
                (filtered_df["timestamp"].iloc[-1] - filtered_df["timestamp"].iloc[0]).total_seconds()
            ),
        )

    cols = st.columns(5)
    cols[0].metric("Amostras no Trecho", f"{len(filtered_df)}")
    cols[1].metric("Duração da Janela", f"{duration_s / 60.0:.1f} min")

    max_rpm = filtered_df["rpm"].dropna().max()
    cols[2].metric(
        "RPM Máximo",
        f"{int(round(max_rpm))} RPM" if pd.notna(max_rpm) else "--",
    )

    max_speed = filtered_df["speed"].dropna().max()
    cols[3].metric(
        "Velocidade Máxima",
        f"{int(round(max_speed))} km/h" if pd.notna(max_speed) else "--",
    )

    max_temp = filtered_df["temperature"].dropna().max()
    cols[4].metric(
        "Temp. Máxima",
        f"{int(round(max_temp))} °C" if pd.notna(max_temp) else "--",
    )

    metrics_spec = [
        ("rpm", "Rotação (RPM)", "#FF4B4B"),
        ("speed", "Velocidade (km/h)", "#0068C9"),
        ("temperature", "Temperatura (°C)", "#FFAA00"),
        ("acceleration_ms2", "Aceleração (m/s²)", "#00B050"),
    ]
    st.altair_chart(
        build_overview_detail_charts(filtered_df, metrics_spec),
        use_container_width=True,
    )

    st.subheader("Relação RPM vs Velocidade no Trecho")
    gear_df = filtered_df.dropna(subset=["speed", "rpm"])
    if gear_df.empty:
        st.info("Sem pares válidos de RPM e Velocidade neste recorte.")
    else:
        gear_chart = (
            alt.Chart(gear_df[["speed", "rpm"]])
            .mark_circle(size=45, opacity=0.65, color="#7B61FF")
            .encode(
                x=alt.X("speed:Q", title="Velocidade (km/h)"),
                y=alt.Y("rpm:Q", title="Rotação (RPM)"),
                tooltip=[
                    alt.Tooltip("speed:Q", title="Velocidade (km/h)", format=".1f"),
                    alt.Tooltip("rpm:Q", title="RPM", format=".0f"),
                ],
            )
            .interactive()
            .properties(height=280)
        )
        st.altair_chart(gear_chart, use_container_width=True)

    csv_bytes = filtered_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Exportar Trecho em CSV",
        data=csv_bytes,
        file_name=f"telemetria_{selected_date.isoformat()}.csv",
        mime="text/csv",
    )

    with st.expander("Ver Dados Tabulares do Trecho"):
        st.dataframe(filtered_df.iloc[::-1].head(200).reset_index(drop=True), use_container_width=True)
