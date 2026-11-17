import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3
import sys
import time
from typing import Any

import pandas as pd
import requests

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.config import API_URL, BASE_DIR, DATABASE_URL  # noqa: E402

SESSION_BREAK_THRESHOLD_S = 60.0


def sqlite_path_from_url(database_url: str = DATABASE_URL) -> Path:
    """
    Extrai o caminho do arquivo SQLite a partir da string de conexão SQLAlchemy.
    """
    prefix = "sqlite:///"
    if database_url.startswith(prefix):
        return Path(database_url[len(prefix) :])
    return BASE_DIR / "vehicle_data.db"


def fetch_from_api(
    api_url: str = API_URL,
    limit: int = 1000,
    timeout_seconds: float = 3.0,
) -> tuple[list[dict[str, Any]], int | None]:
    """
    Consulta os registros recentes de telemetria via endpoint REST do FastAPI.
    """
    response = requests.get(api_url, params={"limit": limit}, timeout=timeout_seconds)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        raise ValueError("Resposta inesperada da API: esperado uma lista JSON.")
    return payload, None


def fetch_from_sqlite(
    db_path: Path | None = None,
    limit: int = 1000,
) -> tuple[list[dict[str, Any]], int]:
    """
    Lê os registros mais recentes diretamente do banco SQLite e retorna também
    a contagem total de linhas persistidas na tabela telemetry.
    """
    target_path = db_path or sqlite_path_from_url()
    if not target_path.exists():
        raise FileNotFoundError(f"Banco SQLite não encontrado em: {target_path}")

    with sqlite3.connect(target_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        table_exists = cursor.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='telemetry'"
        ).fetchone()
        if not table_exists:
            return [], 0

        total_count = int(cursor.execute("SELECT COUNT(*) FROM telemetry").fetchone()[0])
        rows = cursor.execute(
            "SELECT id, rpm, temperature, speed, timestamp "
            "FROM telemetry ORDER BY timestamp DESC, id DESC LIMIT ?",
            (limit,),
        ).fetchall()

    return [dict(row) for row in rows], total_count


def load_telemetry_source(
    source: str = "auto",
    api_url: str = API_URL,
    db_path: Path | None = None,
    limit: int = 1000,
) -> tuple[list[dict[str, Any]], int | None, str]:
    """
    Carrega os dados de telemetria a partir da API local ou do banco SQLite,
    com fallback automático no modo 'auto'.
    """
    if source == "api":
        records, total = fetch_from_api(api_url=api_url, limit=limit)
        return records, total, f"API REST ({api_url})"

    if source == "sqlite":
        target_path = db_path or sqlite_path_from_url()
        records, total = fetch_from_sqlite(db_path=target_path, limit=limit)
        return records, total, f"SQLite ({target_path})"

    try:
        records, total = fetch_from_api(api_url=api_url, limit=limit)
        return records, total, f"API REST ({api_url})"
    except requests.exceptions.RequestException:
        target_path = db_path or sqlite_path_from_url()
        records, total = fetch_from_sqlite(db_path=target_path, limit=limit)
        return records, total, f"SQLite fallback ({target_path})"


def analyze_telemetry_records(
    records: list[dict[str, Any]],
    expected_interval_s: float = 1.0,
    gap_threshold_s: float | None = None,
    total_db_count: int | None = None,
) -> dict[str, Any]:
    """
    Analisa uma lista de registros de telemetria para calcular frequência média
    de recepção (Hz) e detectar perda de pacotes ou saltos anômalos de timestamp.
    """
    if expected_interval_s <= 0:
        raise ValueError("expected_interval_s deve ser maior que zero.")

    threshold_s = (
        gap_threshold_s if gap_threshold_s is not None else max(2.5, expected_interval_s * 2.5)
    )

    if not records:
        return {
            "total_records": total_db_count if total_db_count is not None else 0,
            "analyzed_records": 0,
            "first_timestamp": None,
            "last_timestamp": None,
            "duration_seconds": 0.0,
            "avg_frequency_hz": 0.0,
            "effective_frequency_hz": 0.0,
            "mean_interval_s": None,
            "median_interval_s": None,
            "min_interval_s": None,
            "max_interval_s": None,
            "gap_threshold_s": threshold_s,
            "expected_interval_s": expected_interval_s,
            "anomalous_gaps": [],
            "session_breaks_count": 0,
            "duplicate_or_reordered_count": 0,
            "estimated_missed_packets": 0,
            "estimated_packet_loss_pct": 0.0,
            "null_speed_count": 0,
        }

    df = pd.DataFrame(records)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df = df.dropna(subset=["timestamp"])

    if df.empty:
        return analyze_telemetry_records(
            [],
            expected_interval_s=expected_interval_s,
            gap_threshold_s=threshold_s,
            total_db_count=total_db_count,
        )

    sort_cols = ["timestamp", "id"] if "id" in df.columns else ["timestamp"]
    df = df.sort_values(by=sort_cols, ascending=True).reset_index(drop=True)

    analyzed_count = len(df)
    total_records = total_db_count if total_db_count is not None else analyzed_count
    null_speed_count = int(df["speed"].isna().sum()) if "speed" in df.columns else analyzed_count

    first_ts = df["timestamp"].iloc[0]
    last_ts = df["timestamp"].iloc[-1]
    duration_seconds = max(0.0, float((last_ts - first_ts).total_seconds()))

    if analyzed_count < 2:
        return {
            "total_records": total_records,
            "analyzed_records": analyzed_count,
            "first_timestamp": first_ts.isoformat(),
            "last_timestamp": last_ts.isoformat(),
            "duration_seconds": duration_seconds,
            "avg_frequency_hz": 0.0,
            "effective_frequency_hz": 0.0,
            "mean_interval_s": None,
            "median_interval_s": None,
            "min_interval_s": None,
            "max_interval_s": None,
            "gap_threshold_s": threshold_s,
            "expected_interval_s": expected_interval_s,
            "anomalous_gaps": [],
            "session_breaks_count": 0,
            "duplicate_or_reordered_count": 0,
            "estimated_missed_packets": 0,
            "estimated_packet_loss_pct": 0.0,
            "null_speed_count": null_speed_count,
        }

    deltas = df["timestamp"].diff().dt.total_seconds().iloc[1:]
    avg_frequency_hz = (analyzed_count - 1) / duration_seconds if duration_seconds > 0 else 0.0

    # Separa pausas longas entre sessões distintas (ex: carro desligado > 60s)
    active_deltas = deltas[deltas <= SESSION_BREAK_THRESHOLD_S]
    session_breaks_count = int((deltas > SESSION_BREAK_THRESHOLD_S).sum())
    if not active_deltas.empty and active_deltas.mean() > 0:
        effective_frequency_hz = float(1.0 / active_deltas.mean())
    else:
        effective_frequency_hz = avg_frequency_hz

    duplicate_or_reordered_count = int((deltas <= 0).sum())

    anomalous_gaps: list[dict[str, Any]] = []
    estimated_missed_packets = 0
    for idx, delta_val in deltas.items():
        delta_float = float(delta_val)
        if delta_float > threshold_s:
            is_session_break = delta_float > SESSION_BREAK_THRESHOLD_S
            missed = (
                0
                if is_session_break
                else max(1, round(delta_float / expected_interval_s) - 1)
            )
            estimated_missed_packets += missed
            anomalous_gaps.append(
                {
                    "index": int(idx),
                    "from_ts": df["timestamp"].iloc[idx - 1].isoformat(),
                    "to_ts": df["timestamp"].iloc[idx].isoformat(),
                    "delta_s": round(delta_float, 3),
                    "estimated_missed_packets": missed,
                    "is_session_break": is_session_break,
                }
            )

    denominator = analyzed_count + estimated_missed_packets
    packet_loss_pct = (estimated_missed_packets / denominator * 100.0) if denominator > 0 else 0.0

    return {
        "total_records": total_records,
        "analyzed_records": analyzed_count,
        "first_timestamp": first_ts.isoformat(),
        "last_timestamp": last_ts.isoformat(),
        "duration_seconds": round(duration_seconds, 3),
        "avg_frequency_hz": round(avg_frequency_hz, 4),
        "effective_frequency_hz": round(effective_frequency_hz, 4),
        "mean_interval_s": round(float(deltas.mean()), 4),
        "median_interval_s": round(float(deltas.median()), 4),
        "min_interval_s": round(float(deltas.min()), 4),
        "max_interval_s": round(float(deltas.max()), 4),
        "gap_threshold_s": threshold_s,
        "expected_interval_s": expected_interval_s,
        "anomalous_gaps": anomalous_gaps,
        "session_breaks_count": session_breaks_count,
        "duplicate_or_reordered_count": duplicate_or_reordered_count,
        "estimated_missed_packets": estimated_missed_packets,
        "estimated_packet_loss_pct": round(packet_loss_pct, 2),
        "null_speed_count": null_speed_count,
    }


def format_e2e_report(summary: dict[str, Any], source_label: str) -> str:
    """
    Formata o relatório sumarizado de verificação ponta a ponta (E2E) para exibição no terminal.
    """
    lines = [
        "=" * 72,
        "RELATÓRIO DE VERIFICAÇÃO E2E — TELEMETRIA VEICULAR",
        "=" * 72,
        f"Gerado em (UTC):           {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        f"Fonte dos dados:           {source_label}",
        f"Total de registros salvos: {summary['total_records']}",
        f"Registros analisados:      {summary['analyzed_records']}",
        f"Registros sem speed (PID): {summary['null_speed_count']}",
    ]

    if summary["analyzed_records"] == 0:
        lines.append("-" * 72)
        lines.append("Status: Nenhum registro disponível para análise.")
        lines.append("=" * 72)
        return "\n".join(lines)

    lines.extend(
        [
            f"Primeira leitura (UTC):    {summary['first_timestamp']}",
            f"Última leitura (UTC):      {summary['last_timestamp']}",
            f"Duração da janela:         {summary['duration_seconds']:.2f} s",
            "-" * 72,
            f"Frequência média (janela): {summary['avg_frequency_hz']:.3f} Hz",
            f"Frequência ativa (<=60s):  {summary['effective_frequency_hz']:.3f} Hz",
        ]
    )

    if summary["mean_interval_s"] is not None:
        lines.extend(
            [
                f"Intervalo médio / mediano: {summary['mean_interval_s']:.3f} s / "
                f"{summary['median_interval_s']:.3f} s",
                f"Intervalo mín. / máx.:     {summary['min_interval_s']:.3f} s / "
                f"{summary['max_interval_s']:.3f} s",
            ]
        )

    lines.extend(
        [
            "-" * 72,
            f"Limiar de salto anômalo:   > {summary['gap_threshold_s']:.2f} s "
            f"(esperado: {summary['expected_interval_s']:.2f} s)",
            f"Saltos anômalos totais:    {len(summary['anomalous_gaps'])} "
            f"(pausas de sessão > 60s: {summary['session_breaks_count']})",
            f"Timestamps <= 0s (dup.):   {summary['duplicate_or_reordered_count']}",
            f"Pacotes perdidos (est.):   {summary['estimated_missed_packets']} "
            f"({summary['estimated_packet_loss_pct']:.2f}%)",
        ]
    )

    intra_session_gaps = [g for g in summary["anomalous_gaps"] if not g["is_session_break"]]
    if intra_session_gaps:
        lines.append("-" * 72)
        lines.append("Principais saltos intra-sessão detectados (até 5 mais recentes):")
        for gap in intra_session_gaps[-5:]:
            lines.append(
                f"  - Δt = {gap['delta_s']:.3f} s | perdidos ~{gap['estimated_missed_packets']} | "
                f"{gap['from_ts']} -> {gap['to_ts']}"
            )
    elif summary["session_breaks_count"] > 0:
        lines.append("-" * 72)
        lines.append("Observação: Apenas pausas longas entre sessões (> 60s) detectadas.")
    else:
        lines.append("-" * 72)
        lines.append("Status do fluxo: Contínuo e sem perda de pacotes detectada.")

    lines.append("=" * 72)
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """
    Configura e interpreta os argumentos de linha de comando do script E2E.
    """
    parser = argparse.ArgumentParser(
        description="Verifica integridade, frequência (Hz) e perdas de pacotes na telemetria E2E."
    )
    parser.add_argument(
        "--source",
        choices=["auto", "api", "sqlite"],
        default="auto",
        help="Fonte dos dados: api, sqlite ou auto (tenta API e faz fallback para SQLite).",
    )
    parser.add_argument("--api-url", default=API_URL, help="URL do endpoint GET /api/v1/telemetry.")
    parser.add_argument(
        "--db-path",
        type=Path,
        default=None,
        help="Caminho opcional para o arquivo SQLite (padrão: backend.config.DATABASE_URL).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=1000,
        help="Quantidade máxima de registros recentes a analisar (padrão: 1000).",
    )
    parser.add_argument(
        "--expected-interval",
        type=float,
        default=1.0,
        help="Intervalo nominal entre pacotes em segundos (1.0 para ESP32, 0.5 para mock_car).",
    )
    parser.add_argument(
        "--gap-threshold",
        type=float,
        default=None,
        help="Limiar em segundos para sinalizar salto anômalo (padrão: 2.5 * expected-interval).",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Mantém o script escutando continuamente e atualizando o relatório no terminal.",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=2.0,
        help="Intervalo de atualização em segundos no modo --watch (padrão: 2.0).",
    )
    args = parser.parse_args(argv)
    if args.expected_interval <= 0:
        parser.error("--expected-interval deve ser maior que zero.")
    if args.poll_interval <= 0:
        parser.error("--poll-interval deve ser maior que zero.")
    return args


def main(argv: list[str] | None = None) -> int:
    """
    Executa a coleta e impressão do relatório de verificação E2E em modo único ou contínuo.
    """
    args = parse_args(argv)
    try:
        while True:
            records, total_db_count, source_label = load_telemetry_source(
                source=args.source,
                api_url=args.api_url,
                db_path=args.db_path,
                limit=args.limit,
            )
            summary = analyze_telemetry_records(
                records=records,
                expected_interval_s=args.expected_interval,
                gap_threshold_s=args.gap_threshold,
                total_db_count=total_db_count,
            )
            print(format_e2e_report(summary, source_label))

            if not args.watch:
                break
            time.sleep(args.poll_interval)
    except KeyboardInterrupt:
        print("\nMonitoramento E2E encerrado pelo usuário.")
    except Exception as exc:
        print(f"Erro ao executar verificação E2E: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
