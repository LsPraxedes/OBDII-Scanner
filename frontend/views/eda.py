import altair as alt
import streamlit as st

from frontend.telemetry_utils import downsample_for_chart
from frontend.views.common import select_and_load_day_dataframe


def render_eda_page() -> None:
    """
    Renderiza a página preparatória de Análise de Padrões (EDA — Fase 3 / Semana 6),
    conectando os gráficos descritivos aos dados reais já armazenados no banco.
    """
    st.subheader("Análise de Padrões e Comportamento Normal (EDA)")
    st.info(
        "Estrutura visual preparatória para a **Fase 3 (Semana 6 — CRISP-DM)**. "
        "As estatísticas e distribuições abaixo já usam seus dados reais coletados; "
        "os limiares de normalidade do motor serão consolidados na Semana 6."
    )

    selected_date, df = select_and_load_day_dataframe(
        selectbox_label="Base de dados do dia para EDA",
        empty_days_message="Sem dados disponíveis no backend para exibir a análise exploratória.",
    )
    if selected_date is None or df.empty:
        return

    st.write("**Resumo Estatístico das Variáveis (Pandas CRISP-DM)**")
    stats_cols = ["rpm", "temperature", "speed", "acceleration_ms2"]
    stats_df = df[stats_cols].describe().round(2)
    st.dataframe(stats_df, use_container_width=True)

    plot_df = downsample_for_chart(df)
    hist_specs = [
        ("rpm", "Distribuição de RPM", "RPM", "#FF4B4B", 25),
        ("temperature", "Distribuição de Temperatura (°C)", "Temperatura (°C)", "#FFAA00", 20),
        ("speed", "Distribuição de Velocidade (km/h)", "Velocidade (km/h)", "#0068C9", 20),
    ]
    cols = st.columns(3)
    for col_widget, (col_name, heading, x_title, color, maxbins) in zip(cols, hist_specs):
        with col_widget:
            st.write(f"**{heading}**")
            clean_col = plot_df[[col_name]].dropna()
            if clean_col.empty:
                st.info(f"Sem leituras de {col_name} no dia.")
            else:
                hist_chart = (
                    alt.Chart(clean_col)
                    .mark_bar(color=color, opacity=0.8)
                    .encode(
                        x=alt.X(f"{col_name}:Q", bin=alt.Bin(maxbins=maxbins), title=x_title),
                        y=alt.Y("count()", title="Amostras"),
                    )
                    .properties(height=220)
                )
                st.altair_chart(hist_chart, use_container_width=True)

    st.write("**Dispersão Térmica: Temperatura vs RPM**")
    thermal_df = plot_df[["rpm", "temperature"]].dropna()
    if not thermal_df.empty:
        thermal_chart = (
            alt.Chart(thermal_df)
            .mark_circle(size=35, opacity=0.55, color="#FF7F0E")
            .encode(
                x=alt.X("rpm:Q", title="Rotação (RPM)"),
                y=alt.Y("temperature:Q", title="Temperatura (°C)"),
            )
            .interactive()
            .properties(height=260)
        )
        st.altair_chart(thermal_chart, use_container_width=True)

    with st.expander("Espaço Reservado — Matriz de Correlação e Limiares Normais (Semana 6)"):
        st.write(
            "Na Semana 6 serão definidas aqui as faixas operacionais normais do VW Polo "
            "(marcha lenta, regime térmico, trocas de marcha) para treinar o modelo."
        )
