import os
import sys

import streamlit as st

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from frontend.telemetry_utils import (  # noqa: E402, F401
    CONNECTION_TIMEOUT_SECONDS,
    KMH_TO_MS,
    REFRESH_INTERVAL_SECONDS,
    compute_acceleration,
    fetch_telemetry,
    fetch_telemetry_days,
    format_metric_delta,
    get_connection_status,
    local_day_to_utc_range,
    prepare_telemetry_dataframe,
)
from frontend.views.ai_diagnostics import render_ai_diagnostics_page  # noqa: E402
from frontend.views.eda import render_eda_page  # noqa: E402
from frontend.views.history import render_history_page  # noqa: E402
from frontend.views.live import (  # noqa: E402, F401
    render_connection_banner,
    render_dashboard,
    render_live_page,
)

PAGE_LIVE = "📡 Tempo Real"
PAGE_HISTORY = "📅 Histórico & Viagens"
PAGE_EDA = "📊 Análise de Padrões (EDA)"
PAGE_AI = "🤖 Diagnóstico Preditivo (IA)"


def main() -> None:
    """
    Ponto de entrada da aplicação Streamlit com navegação lateral modular entre
    tempo real, histórico por dia e páginas preparatórias das Fases 3 e 4.
    """
    st.set_page_config(
        page_title="Central de Análise Veicular Preditiva",
        page_icon="🚗",
        layout="wide",
    )

    st.title("Central de Análise Veicular Preditiva")
    st.write("Telemetria veicular em tempo real via OBD-II (CAN 500 kbaud) e MQTTS 4G.")

    st.sidebar.header("Navegação")
    selected_page = st.sidebar.radio(
        "Selecione a visão",
        [PAGE_LIVE, PAGE_HISTORY, PAGE_EDA, PAGE_AI],
    )

    if selected_page == PAGE_LIVE:
        st.sidebar.header("Controles ao Vivo")
        live_limit = st.sidebar.selectbox(
            "Janela ao vivo (amostras)",
            options=[100, 300, 600, 1200, 1800, 3000, 5000],
            index=1,
        )
        auto_refresh = st.sidebar.checkbox("Auto-Refresh (Ao Vivo)", value=True)
        st.sidebar.caption(
            "Desmarque Auto-Refresh para pausar a tela e rolar/dar zoom nos gráficos sem resetar."
        )
        render_live_page(live_limit=live_limit, auto_refresh=auto_refresh)
    elif selected_page == PAGE_HISTORY:
        render_history_page()
    elif selected_page == PAGE_EDA:
        render_eda_page()
    elif selected_page == PAGE_AI:
        render_ai_diagnostics_page()


if __name__ == "__main__":
    main()
