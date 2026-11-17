from datetime import date

import pandas as pd
import streamlit as st

from frontend.telemetry_utils import (
    fetch_telemetry,
    fetch_telemetry_days,
    local_day_to_utc_range,
    prepare_telemetry_dataframe,
)


def select_and_load_day_dataframe(
    selectbox_label: str,
    empty_days_message: str,
) -> tuple[date | None, pd.DataFrame]:
    """
    Renderiza o seletor de dias disponíveis na API e retorna a data escolhida
    junto do respectivo DataFrame já tratado em ordem cronológica.
    """
    days = fetch_telemetry_days()
    if not days:
        st.info(empty_days_message)
        return None, pd.DataFrame()

    day_options = {
        f"{item['date']} ({item['count']} registros)": date.fromisoformat(str(item["date"]))
        for item in days
    }
    selected_label = st.selectbox(selectbox_label, list(day_options.keys()))
    selected_date = day_options[selected_label]

    start_utc, end_utc = local_day_to_utc_range(selected_date)
    raw_data = fetch_telemetry(
        limit=50000,
        start_time=start_utc,
        end_time=end_utc,
        timeout_seconds=10.0,
    )
    df = prepare_telemetry_dataframe(raw_data)
    if df.empty:
        st.warning("Nenhum registro encontrado para a data selecionada.")
        return selected_date, pd.DataFrame()

    return selected_date, df
