import altair as alt
import pandas as pd
import streamlit as st

from frontend.telemetry_utils import downsample_for_chart
from frontend.views.common import select_and_load_day_dataframe


def render_ai_diagnostics_page() -> None:
    """
    Renderiza o esqueleto visual da futura página de Diagnóstico Preditivo (IA)
    prevista para as Semanas 7 e 8 (Isolation Forest e Alertas em Tempo Real).
    """
    st.subheader("Diagnóstico Preditivo e Detecção de Anomalias (IA)")
    st.warning(
        "Página em preparação (Visualizador-First): o modelo **Isolation Forest** (`.pkl`) "
        "e os alertas em tempo real serão integrados nas **Semanas 7 e 8 (Fases 3 e 4)**."
    )

    cols = st.columns(4)
    cols[0].metric("Modelo Preditivo", value="Não carregado", delta="Previsto Semana 7")
    cols[1].metric("Índice de Saúde do Motor", value="-- %")
    cols[2].metric("Anomalias Detectadas", value="0")
    cols[3].metric("Status do Monitor IA", value="Aguardando Fase 4")

    st.subheader("Linha do Tempo de Anomalias (Prévia de Estrutura)")
    _, df = select_and_load_day_dataframe(
        selectbox_label="Sessão de referência para visualização",
        empty_days_message=(
            "Conecte o backend para carregar a série base onde o score de anomalia será sobreposto."
        ),
    )
    if not df.empty:
        plot_df = downsample_for_chart(df)
        base_chart = (
            alt.Chart(plot_df[["local_timestamp", "rpm"]].dropna())
            .mark_line(color="#6C757D")
            .encode(
                x=alt.X("local_timestamp:T", title="Horário (BRT)"),
                y=alt.Y("rpm:Q", title="RPM (Série Base para Sobreposição IA)"),
            )
            .interactive()
            .properties(height=220)
        )
        st.altair_chart(base_chart, use_container_width=True)
        st.caption(
            "Quando o modelo for implantado no backend (Semana 8), os pontos anômalos "
            "e o score de anomalia do Isolation Forest serão destacados sobre esta linha do tempo."
        )

    st.subheader("Feed de Alertas Preditivos (Contrato Visual Futuro)")
    empty_alerts_df = pd.DataFrame(
        columns=[
            "Timestamp (BRT)",
            "Severidade",
            "Tipo de Anomalia",
            "Score Isolation Forest",
            "RPM",
            "Temperatura (°C)",
            "Velocidade (km/h)",
            "Status",
        ]
    )
    st.dataframe(empty_alerts_df, use_container_width=True)
    st.caption(
        "Estrutura de colunas reservada para os alertas gerados pelo endpoint preditivo na Semana 8."
    )
