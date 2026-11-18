import altair as alt
import pandas as pd
import streamlit as st

from backend.ml.data_preparation import CLEANING_RULE_LABELS, DataQualityReport, prepare_dataset
from backend.ml.eda_analysis import (
    compute_correlation_matrix,
    compute_normal_thresholds,
    describe_by_regime,
    regime_distribution,
)
from frontend.telemetry_utils import downsample_for_chart
from frontend.views.common import select_and_load_day_dataframe

VARIABLE_LABELS = {
    "rpm": "RPM",
    "temperature": "Temperatura (°C)",
    "speed": "Velocidade (km/h)",
    "acceleration_ms2": "Aceleração (m/s²)",
    "rpm_per_speed": "RPM/Velocidade",
}
REGIME_LABELS = {
    "global": "Global",
    "engine_off": "Motor desligado",
    "idle": "Marcha lenta",
    "driving": "Em movimento",
    "unknown": "Indeterminado",
}


def render_eda_page() -> None:
    """
    Renderiza a página de Análise de Padrões (EDA — Fase 3 / Semana 6): estatísticas
    descritivas dos dados reais e, abaixo, o pipeline CRISP-DM de limpeza com qualidade
    dos dados, correlação, comparação por regime e limiares normais preliminares.
    """
    st.subheader("Análise de Padrões e Comportamento Normal (EDA)")
    st.info(
        "**Fase 3 (Semana 6 — CRISP-DM: Entendimento e Preparação dos Dados).** "
        "As distribuições iniciais usam os dados brutos do dia; a seção de preparação "
        "abaixo aplica a limpeza física, trata rajadas 4G e consolida os limiares normais."
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

    st.divider()
    st.subheader("Preparação CRISP-DM — Semana 6")
    prepared_df, quality_report = prepare_dataset(df, include_estimated_timestamp=False)
    render_quality_panel(df, prepared_df, quality_report)
    if prepared_df.empty:
        st.warning("Todos os registros do dia foram removidos pelas regras de limpeza.")
        return

    render_correlation_heatmap(prepared_df)
    render_regime_comparison(prepared_df)
    render_thresholds_table(prepared_df)


def render_quality_panel(
    raw_df: pd.DataFrame,
    prepared_df: pd.DataFrame,
    quality_report: DataQualityReport,
) -> None:
    """
    Painel Bruto vs. Limpo: contagens do Relatório de Qualidade dos Dados,
    remoções por regra e comparação das faixas de cada variável antes/depois.
    """
    st.write("**Qualidade dos Dados: Bruto vs. Limpo**")
    metric_cols = st.columns(4)
    metric_cols[0].metric("Registros brutos", quality_report.raw_count)
    metric_cols[1].metric(
        "Registros limpos",
        quality_report.clean_count,
        delta=f"-{quality_report.removed_count}" if quality_report.removed_count else None,
        delta_color="inverse",
    )
    metric_cols[2].metric("Rajadas 4G (mantidas)", quality_report.burst_count)
    metric_cols[3].metric("Derivadas confiáveis", quality_report.derivative_valid_count)

    st.caption(
        "Rajadas 4G: pacotes retidos durante falhas de sinal e entregues em lote "
        "(dt < 0,25 s). As leituras são mantidas, mas aceleração e ΔRPM são anuladas nelas, "
        "pois o horário registrado é o de chegada no servidor e não o da leitura CAN."
    )

    rules_df = pd.DataFrame(
        [
            {"Regra de limpeza": CLEANING_RULE_LABELS.get(rule, rule), "Registros removidos": count}
            for rule, count in quality_report.removed_by_rule.items()
        ]
    )
    comparison_rows = []
    for column, label in VARIABLE_LABELS.items():
        if column not in raw_df.columns or column == "acceleration_ms2":
            continue
        raw_values = pd.to_numeric(raw_df[column], errors="coerce")
        clean_values = prepared_df[column]
        comparison_rows.append(
            {
                "Variável": label,
                "Mín. bruto": raw_values.min(),
                "Máx. bruto": raw_values.max(),
                "Mín. limpo": clean_values.min(),
                "Máx. limpo": clean_values.max(),
                "Média bruta": raw_values.mean(),
                "Média limpa": clean_values.mean(),
            }
        )

    left, right = st.columns(2)
    with left:
        st.dataframe(rules_df, use_container_width=True, hide_index=True)
    with right:
        st.dataframe(pd.DataFrame(comparison_rows).round(2), use_container_width=True, hide_index=True)


def render_correlation_heatmap(prepared_df: pd.DataFrame) -> None:
    """
    Heatmap Altair da matriz de correlação de Pearson (RPM, temperatura, velocidade, aceleração).
    """
    st.write("**Matriz de Correlação (Pearson)**")
    corr = compute_correlation_matrix(prepared_df)
    if corr.empty or corr.isna().all().all():
        st.info("Amostras insuficientes para calcular a matriz de correlação.")
        return

    labeled = corr.rename(index=VARIABLE_LABELS, columns=VARIABLE_LABELS)
    long_df = labeled.reset_index(names="var_x").melt(
        id_vars="var_x", var_name="var_y", value_name="correlation"
    )
    long_df["label"] = long_df["correlation"].map(lambda value: "—" if pd.isna(value) else f"{value:.2f}")
    order = list(labeled.columns)

    base = alt.Chart(long_df).encode(
        x=alt.X("var_x:N", sort=order, title=None),
        y=alt.Y("var_y:N", sort=order, title=None),
    )
    heatmap = base.mark_rect().encode(
        color=alt.Color(
            "correlation:Q",
            scale=alt.Scale(scheme="redblue", domain=[-1, 1], reverse=True),
            title="r",
        ),
        tooltip=[
            alt.Tooltip("var_x:N", title="Variável X"),
            alt.Tooltip("var_y:N", title="Variável Y"),
            alt.Tooltip("correlation:Q", title="r", format=".3f"),
        ],
    )
    text = base.mark_text(fontSize=13).encode(text="label:N")
    st.altair_chart((heatmap + text).properties(height=300), use_container_width=True)


def render_regime_comparison(prepared_df: pd.DataFrame) -> None:
    """
    Comparação por regime operacional: distribuição das amostras, boxplot de RPM
    e estatísticas descritivas de marcha lenta vs. em movimento.
    """
    st.write("**Comparação por Regime Operacional**")
    distribution = regime_distribution(prepared_df)
    distribution["regime"] = distribution["regime"].map(lambda value: REGIME_LABELS.get(value, value))
    distribution = distribution.rename(
        columns={"regime": "Regime", "count": "Amostras", "share_pct": "Participação (%)"}
    )

    left, right = st.columns([1, 2])
    with left:
        st.dataframe(distribution, use_container_width=True, hide_index=True)
    with right:
        box_df = downsample_for_chart(prepared_df[["regime", "rpm"]].dropna()).copy()
        box_df["regime_label"] = box_df["regime"].map(lambda value: REGIME_LABELS.get(value, value))
        box_chart = (
            alt.Chart(box_df)
            .mark_boxplot(extent="min-max")
            .encode(
                x=alt.X("regime_label:N", title="Regime"),
                y=alt.Y("rpm:Q", title="Rotação (RPM)"),
                color=alt.Color("regime_label:N", legend=None),
            )
            .properties(height=240)
        )
        st.altair_chart(box_chart, use_container_width=True)

    regime_stats = describe_by_regime(prepared_df, columns=["rpm", "temperature", "speed"])
    stats_cols = st.columns(len(regime_stats))
    for col_widget, (regime, stats) in zip(stats_cols, regime_stats.items()):
        with col_widget:
            st.write(f"*{REGIME_LABELS.get(regime, regime)}*")
            if stats.empty or stats.loc["count"].max() == 0:
                st.info("Sem amostras neste regime.")
            else:
                st.dataframe(
                    stats.rename(columns=VARIABLE_LABELS).round(2),
                    use_container_width=True,
                )


def render_thresholds_table(prepared_df: pd.DataFrame) -> None:
    """
    Tabela de limiares normais preliminares do veículo (faixa P05–P95 e alerta P99).
    """
    st.write("**Limiares Normais Preliminares do Veículo**")
    thresholds = compute_normal_thresholds(prepared_df)
    if thresholds.empty:
        st.info("Amostras insuficientes para estimar os limiares normais.")
        return

    table = thresholds.copy()
    table["scope"] = table["scope"].map(lambda value: REGIME_LABELS.get(value, value))
    table["variable"] = table["variable"].map(lambda value: VARIABLE_LABELS.get(value, value))
    table = table.rename(
        columns={
            "scope": "Escopo",
            "variable": "Variável",
            "samples": "Amostras",
            "min": "Mín.",
            "p05": "P05 (limite inf.)",
            "p50": "Mediana",
            "p95": "P95 (limite sup.)",
            "p99": "P99 (alerta)",
            "max": "Máx.",
        }
    )
    st.dataframe(table.round(2), use_container_width=True, hide_index=True)
    st.caption(
        "Faixa normal preliminar = [P05, P95] por regime. Esses limiares descrevem o "
        "comportamento observado e servirão de referência para o modelo da Semana 7."
    )
