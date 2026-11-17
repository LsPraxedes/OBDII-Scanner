from datetime import date, datetime, time, timedelta, timezone
import os
import sys
from typing import Any

import altair as alt
import pandas as pd
import requests

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.config import API_URL  # noqa: E402

CONNECTION_TIMEOUT_SECONDS = 5.0
REFRESH_INTERVAL_SECONDS = 0.5
KMH_TO_MS = 3.6
DEFAULT_TZ_OFFSET_MINUTES = -180
BRT_TZ = timezone(timedelta(minutes=DEFAULT_TZ_OFFSET_MINUTES))
MAX_CHART_POINTS = 3000

alt.data_transformers.disable_max_rows()


def fetch_telemetry(
    api_url: str = API_URL,
    limit: int = 100,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    timeout_seconds: float = 3.0,
) -> list[dict[str, Any]]:
    """
    Busca registros de telemetria na API REST do backend FastAPI com suporte
    a limite de amostras e filtro opcional de intervalo temporal.
    """
    params: dict[str, Any] = {"limit": limit}
    if start_time is not None:
        params["start_time"] = start_time.isoformat()
    if end_time is not None:
        params["end_time"] = end_time.isoformat()

    try:
        response = requests.get(api_url, params=params, timeout=timeout_seconds)
        if response.status_code == 200:
            payload = response.json()
            if isinstance(payload, list):
                return payload
    except requests.exceptions.RequestException:
        pass
    return []


def fetch_telemetry_days(
    api_url: str = API_URL,
    tz_offset_minutes: int = DEFAULT_TZ_OFFSET_MINUTES,
    timeout_seconds: float = 3.0,
) -> list[dict[str, Any]]:
    """
    Consulta os dias disponíveis no histórico do banco de dados via API REST.
    """
    days_url = f"{api_url.rstrip('/')}/days"
    try:
        response = requests.get(
            days_url,
            params={"tz_offset_minutes": tz_offset_minutes},
            timeout=timeout_seconds,
        )
        if response.status_code == 200:
            payload = response.json()
            if isinstance(payload, list):
                return payload
    except requests.exceptions.RequestException:
        pass
    return []


def local_day_to_utc_range(
    target_date: date,
    tz_offset_minutes: int = DEFAULT_TZ_OFFSET_MINUTES,
) -> tuple[datetime, datetime]:
    """
    Converte uma data civil no fuso local para o intervalo [início, fim] em UTC.
    """
    local_tz = timezone(timedelta(minutes=tz_offset_minutes))
    start_local = datetime.combine(target_date, time.min, tzinfo=local_tz)
    end_local = datetime.combine(target_date, time.max, tzinfo=local_tz)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def compute_acceleration(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula a aceleração instantânea (m/s²) a partir de leituras consecutivas
    de velocidade (km/h) e timestamp já ordenados cronologicamente.
    """
    result = df.copy()
    nan_series = pd.Series(float("nan"), index=result.index, dtype="float64")

    if len(result) < 2 or "speed" not in result.columns or "timestamp" not in result.columns:
        result["acceleration_ms2"] = nan_series
        return result

    delta_time_s = result["timestamp"].diff().dt.total_seconds()
    speed_ms = pd.to_numeric(result["speed"], errors="coerce") / KMH_TO_MS
    delta_speed_ms = speed_ms.diff()

    # Evita divisão por zero ou valores infinitos em timestamps idênticos/inválidos
    valid_mask = (delta_time_s > 0) & delta_speed_ms.notna()
    acceleration = nan_series.copy()
    acceleration.loc[valid_mask] = delta_speed_ms.loc[valid_mask] / delta_time_s.loc[valid_mask]
    result["acceleration_ms2"] = acceleration
    return result


def prepare_telemetry_dataframe(data: list[dict[str, Any]]) -> pd.DataFrame:
    """
    Converte os dados recebidos da API em DataFrame padronizado, ordenado em
    ordem cronológica crescente (esquerda -> direita) e enriquecido com aceleração
    e horário local (BRT / UTC-3) para exibição nos gráficos.
    """
    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data)
    if "timestamp" not in df.columns:
        return pd.DataFrame()

    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df = df.dropna(subset=["timestamp"])
    if df.empty:
        return df

    for column in ("rpm", "temperature", "speed"):
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")
        else:
            df[column] = float("nan")

    sort_columns = ["timestamp", "id"] if "id" in df.columns else ["timestamp"]
    df = df.sort_values(by=sort_columns, ascending=True).reset_index(drop=True)
    df["local_timestamp"] = df["timestamp"].dt.tz_convert(BRT_TZ).dt.tz_localize(None)
    return compute_acceleration(df)


def get_connection_status(
    latest_timestamp: pd.Timestamp,
    now_utc: datetime | None = None,
    timeout_seconds: float = CONNECTION_TIMEOUT_SECONDS,
) -> tuple[bool, float]:
    """
    Verifica se o veículo está conectado ao vivo comparando o timestamp da
    última leitura com o horário UTC atual (limite padrão de 5 segundos).
    """
    ts = pd.Timestamp(latest_timestamp)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    else:
        ts = ts.tz_convert("UTC")

    reference = pd.Timestamp(now_utc or datetime.now(timezone.utc))
    if reference.tzinfo is None:
        reference = reference.tz_localize("UTC")
    else:
        reference = reference.tz_convert("UTC")

    elapsed_seconds = max(0.0, float((reference - ts).total_seconds()))
    return elapsed_seconds < timeout_seconds, elapsed_seconds


def format_metric_delta(
    current: Any,
    previous: Any,
    unit: str,
    decimals: int = 0,
    signed_value: bool = False,
) -> tuple[str, str | None]:
    """
    Formata valor e variação (delta) para os cards st.metric de forma segura,
    tratando ausência de registro anterior (len == 1) ou valores nulos.
    """
    if current is None or pd.isna(current):
        return "--", None

    current_float = float(current)
    if decimals == 0:
        current_display = int(round(current_float))
        value_str = f"{current_display:+d} {unit}" if signed_value else f"{current_display} {unit}"
    else:
        sign_fmt = "+" if signed_value else ""
        value_str = f"{current_float:{sign_fmt}.{decimals}f} {unit}"

    if previous is None or pd.isna(previous):
        return value_str, None

    previous_float = float(previous)
    if decimals == 0:
        diff_int = int(round(current_float)) - int(round(previous_float))
        return value_str, f"{diff_int:+d} {unit}"

    diff_float = current_float - previous_float
    return value_str, f"{diff_float:+.{decimals}f} {unit}"


def downsample_for_chart(df: pd.DataFrame, max_points: int = MAX_CHART_POINTS) -> pd.DataFrame:
    """
    Reduz uniformemente a quantidade de pontos para renderização fluida no navegador
    caso o intervalo selecionado ultrapasse o limite configurado.
    """
    if len(df) <= max_points or max_points < 2:
        return df
    step = max(1, len(df) // max_points)
    sampled = df.iloc[::step].copy()
    if sampled.index[-1] != df.index[-1]:
        sampled = pd.concat([sampled, df.iloc[[-1]]])
    return sampled


def build_interactive_line_chart(
    df: pd.DataFrame,
    y_col: str,
    y_title: str,
    color: str,
    x_col: str = "local_timestamp",
    height: int = 230,
) -> alt.Chart:
    """
    Cria um gráfico de linha Altair com zoom horizontal e arraste (pan) interativo.
    """
    plot_df = downsample_for_chart(df[[x_col, y_col]].dropna())
    zoom_pan = alt.selection_interval(bind="scales", encodings=["x"])
    return (
        alt.Chart(plot_df)
        .mark_line(color=color)
        .encode(
            x=alt.X(f"{x_col}:T", title="Horário (BRT)"),
            y=alt.Y(f"{y_col}:Q", title=y_title),
            tooltip=[
                alt.Tooltip(f"{x_col}:T", title="Horário", format="%H:%M:%S"),
                alt.Tooltip(f"{y_col}:Q", title=y_title, format=".2f"),
            ],
        )
        .add_params(zoom_pan)
        .properties(height=height)
    )


def build_overview_detail_charts(
    df: pd.DataFrame,
    metrics_spec: list[tuple[str, str, str]],
    x_col: str = "local_timestamp",
) -> alt.VConcatChart:
    """
    Constrói painel Altair no padrão Visão Geral + Detalhe: um seletor arrastável
    no gráfico superior atua como barra de rolagem e zoom para todos os gráficos abaixo.
    """
    plot_df = downsample_for_chart(df)
    brush = alt.selection_interval(encodings=["x"])

    overview_col = "speed" if not plot_df["speed"].dropna().empty else "rpm"
    overview_title = "Velocidade (km/h) — Arraste para rolar/ampliar" if overview_col == "speed" else "RPM — Arraste para rolar/ampliar"

    overview = (
        alt.Chart(plot_df[[x_col, overview_col]].dropna())
        .mark_area(color="#4C78A8", opacity=0.35, line={"color": "#4C78A8"})
        .encode(
            x=alt.X(f"{x_col}:T", title="Visão Geral da Janela (arraste para selecionar trecho)"),
            y=alt.Y(f"{overview_col}:Q", title=overview_title),
        )
        .add_params(brush)
        .properties(height=95)
    )

    detail_charts: list[alt.Chart] = []
    for col, title, color in metrics_spec:
        col_df = plot_df[[x_col, col]].dropna()
        if col_df.empty:
            continue
        detail = (
            alt.Chart(col_df)
            .mark_line(color=color)
            .encode(
                x=alt.X(
                    f"{x_col}:T",
                    title="Horário (BRT)",
                    scale=alt.Scale(domain=brush),
                ),
                y=alt.Y(f"{col}:Q", title=title),
                tooltip=[
                    alt.Tooltip(f"{x_col}:T", title="Horário", format="%H:%M:%S"),
                    alt.Tooltip(f"{col}:Q", title=title, format=".2f"),
                ],
            )
            .properties(height=175)
        )
        detail_charts.append(detail)

    if not detail_charts:
        return alt.vconcat(overview).resolve_scale(x="independent")

    return alt.vconcat(overview, *detail_charts).resolve_scale(x="independent")
