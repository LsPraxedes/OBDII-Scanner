import argparse
from datetime import timedelta, timezone
import os
from pathlib import Path
import sys

import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.config import BASE_DIR  # noqa: E402
from backend.ml.data_preparation import (  # noqa: E402
    CLEANING_RULE_LABELS,
    DataQualityReport,
    default_sqlite_path,
    load_telemetry_from_sqlite,
    prepare_dataset,
)
from backend.ml.eda_analysis import build_eda_summary  # noqa: E402

DEFAULT_OUTPUT_DIR = BASE_DIR / "data" / "clean"
BRT_TZ = timezone(timedelta(hours=-3))


def format_quality_report(report: DataQualityReport) -> str:
    """
    Formata o Relatório de Qualidade dos Dados para exibição no terminal.
    """
    lines = [
        "=" * 72,
        " RELATÓRIO DE QUALIDADE DOS DADOS (CRISP-DM — Semana 6)",
        "=" * 72,
        f" Registros brutos ........................ {report.raw_count}",
        f" Registros limpos ........................ {report.clean_count}",
        f" Registros removidos ..................... {report.removed_count}",
    ]
    for rule, count in report.removed_by_rule.items():
        lines.append(f"   - {CLEANING_RULE_LABELS.get(rule, rule):<38} {count}")
    lines.extend(
        [
            f" Rajadas 4G (dt < 0,25 s, mantidas) ...... {report.burst_count}",
            f" Quedas longas de sinal (dt > 2,5 s) ..... {report.long_gap_count}",
            f" Amostras com derivadas confiáveis ....... {report.derivative_valid_count}",
        ]
    )
    return "\n".join(lines)


def format_eda_summary(summary: dict) -> str:
    """
    Formata as tabelas da EDA (estatísticas, regimes, correlação e limiares) em texto.
    """
    sections = [
        ("ESTATÍSTICAS GLOBAIS (describe + P05/P95/P99)", summary["global_stats"]),
        ("DISTRIBUIÇÃO POR REGIME OPERACIONAL", summary["regime_distribution"]),
    ]
    for regime, stats in summary["regime_stats"].items():
        sections.append((f"ESTATÍSTICAS — REGIME '{regime}'", stats))
    sections.extend(
        [
            ("MATRIZ DE CORRELAÇÃO (PEARSON)", summary["correlation"]),
            ("LIMIARES NORMAIS PRELIMINARES (faixa P05–P95, alerta P99)", summary["thresholds"]),
        ]
    )

    blocks: list[str] = []
    for title, table in sections:
        body = "(sem dados)" if table is None or table.empty else table.round(3).to_string()
        blocks.append(f"\n--- {title} ---\n{body}")
    return "\n".join(blocks)


def export_clean_dataset(df: pd.DataFrame, output_dir: Path) -> Path:
    """
    Exporta o dataset limpo em CSV numa pasta ignorada pelo Git (padrão: data/clean/).
    O nome do arquivo usa o intervalo de datas locais (BRT) cobertas pelos dados.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    local_dates = df["timestamp"].dt.tz_convert(BRT_TZ).dt.date
    first_day, last_day = local_dates.min(), local_dates.max()
    suffix = f"{first_day}" if first_day == last_day else f"{first_day}_{last_day}"
    target = output_dir / f"telemetry_clean_{suffix}.csv"
    df.to_csv(target, index=False)
    return target


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """
    Interpreta os argumentos de linha de comando da auditoria EDA.
    """
    parser = argparse.ArgumentParser(
        description="Auditoria CRISP-DM (Semana 6): limpeza, qualidade dos dados e EDA do vehicle_data.db.",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=default_sqlite_path(),
        help="Caminho do banco SQLite (padrão: vehicle_data.db na raiz do projeto).",
    )
    parser.add_argument(
        "--export-clean",
        action="store_true",
        help="Exporta o dataset limpo e enriquecido em CSV na pasta de saída.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Pasta de saída do CSV limpo (padrão: data/clean/, ignorada pelo Git).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """
    Ponto de entrada da CLI: carrega o SQLite, executa o pipeline e imprime a auditoria.
    """
    args = parse_args(argv)
    raw_df = load_telemetry_from_sqlite(args.db)
    if raw_df.empty:
        print(f"Nenhum registro de telemetria encontrado em: {args.db}", file=sys.stderr)
        return 1

    prepared_df, report = prepare_dataset(raw_df)
    print(format_quality_report(report))
    if prepared_df.empty:
        print("Todos os registros foram removidos pelas regras de limpeza.", file=sys.stderr)
        return 1

    print(format_eda_summary(build_eda_summary(prepared_df)))

    if args.export_clean:
        target = export_clean_dataset(prepared_df, args.output_dir)
        print(f"\nDataset limpo exportado em: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
