"""
CLI de treinamento e avaliação CRISP-DM do Isolation Forest (Fase 3 — Semana 7).

Carrega `vehicle_data.db` via `load_telemetry_from_sqlite()`, executa a preparação
determinística da Semana 6, treina o pipeline `IsolationForest`, imprime o relatório
de avaliação (métricas no conjunto limpo, top anomalias reais e validação com anomalias
sintéticas físicas) e serializa o artefato `.pkl` pronto para a Semana 8.
"""

import argparse
import os
from pathlib import Path
import sys
from typing import Any

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.config import ANOMALY_MODEL_PATH  # noqa: E402
from backend.ml.anomaly_model import (  # noqa: E402
    DEFAULT_CONTAMINATION,
    DEFAULT_N_ESTIMATORS,
    DEFAULT_RANDOM_STATE,
    AnomalyModelArtifact,
    evaluate_anomaly_model,
    save_model_artifact,
    train_anomaly_model,
)
from backend.ml.data_preparation import (  # noqa: E402
    default_sqlite_path,
    load_telemetry_from_sqlite,
    prepare_dataset,
)
from scripts.run_eda import format_quality_report  # noqa: E402


def format_training_and_evaluation_report(
    artifact: AnomalyModelArtifact,
    evaluation: dict[str, Any],
    model_path: Path,
) -> str:
    """
    Formata o relatório CRISP-DM de Modelagem e Avaliação (Semana 7) para o terminal.
    """
    meta = artifact.training_metadata
    score_info = meta.get("score_summary", {})
    lines = [
        "",
        "=" * 78,
        " RELATÓRIO DE MODELAGEM E AVALIAÇÃO (CRISP-DM — Semana 7: Isolation Forest)",
        "=" * 78,
        " Algoritmo ............................... RobustScaler + IsolationForest",
        f" Atributos ({len(artifact.feature_columns)}) .......................... {', '.join(artifact.feature_columns)}",
        f" Hiperparâmetros ......................... n_estimators={artifact.n_estimators}, "
        f"contamination={artifact.contamination}, random_state={artifact.random_state}",
        f" Amostras limpas (total) ................. {meta.get('prepared_clean_count', 0)}",
        f" Amostras motor desligado (excluídas) .... {meta.get('excluded_engine_off_count', 0)}",
        f" Amostras motor em operação (treino) ..... {meta.get('active_engine_count', 0)}",
        f" Anomalias detectadas no trajeto real .... {evaluation['real_anomalies_count']} "
        f"({evaluation['real_anomaly_rate_pct']:.2f}%)",
        " Distribuição de anomaly_score (treino) .. "
        f"min={score_info.get('min', 0.0):.4f} | P01={score_info.get('p01', 0.0):.4f} | "
        f"P05={score_info.get('p05', 0.0):.4f} | P50={score_info.get('p50', 0.0):.4f} | "
        f"P95={score_info.get('p95', 0.0):.4f} | max={score_info.get('max', 0.0):.4f}",
        f" Artefato serializado (.pkl) ............. {model_path}",
    ]

    regime_df = evaluation.get("regime_breakdown")
    lines.append("\n--- DESEMPENHO POR REGIME OPERACIONAL (MOTOR EM OPERAÇÃO) ---")
    if regime_df is None or regime_df.empty:
        lines.append("(sem dados)")
    else:
        lines.append(regime_df.round(4).to_string(index=False))

    top_df = evaluation.get("top_real_anomalies")
    lines.append(f"\n--- TOP {len(top_df) if top_df is not None else 0} ANOMALIAS DETECTADAS NO TRAJETO REAL ---")
    if top_df is None or top_df.empty:
        lines.append("(nenhuma anomalia detectada)")
    else:
        lines.append(top_df.round(3).to_string(index=False))

    synth_df = evaluation.get("synthetic_by_category")
    lines.append(
        "\n--- VALIDAÇÃO COM ANOMALIAS SINTÉTICAS FÍSICAS "
        f"(Taxa Global: {evaluation['synthetic_detected_count']}/{evaluation['synthetic_samples']} "
        f"= {evaluation['synthetic_detection_rate_pct']:.2f}%) ---"
    )
    if synth_df is None or synth_df.empty:
        lines.append("(sem dados sintéticos)")
    else:
        lines.append(synth_df.round(4).to_string(index=False))

    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """
    Interpreta os argumentos de linha de comando para treinamento do Isolation Forest.
    """
    parser = argparse.ArgumentParser(
        description="Treinamento CRISP-DM (Semana 7): Isolation Forest sobre vehicle_data.db e geração de .pkl.",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=default_sqlite_path(),
        help="Caminho do banco SQLite (padrão: vehicle_data.db na raiz do projeto).",
    )
    parser.add_argument(
        "--model-out",
        type=Path,
        default=ANOMALY_MODEL_PATH,
        help="Caminho de saída do artefato .pkl treinado.",
    )
    parser.add_argument(
        "--contamination",
        type=float,
        default=DEFAULT_CONTAMINATION,
        help="Proporção esperada de anomalias no treino (padrão: 0.02).",
    )
    parser.add_argument(
        "--n-estimators",
        type=int,
        default=DEFAULT_N_ESTIMATORS,
        help="Número de árvores do Isolation Forest (padrão: 200).",
    )
    parser.add_argument(
        "--random-state",
        type=int,
        default=DEFAULT_RANDOM_STATE,
        help="Semente determinística do modelo (padrão: 42).",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=10,
        help="Quantidade de anomalias mais severas do trajeto real a exibir (padrão: 10).",
    )
    args = parser.parse_args(argv)
    if not (0.0 < args.contamination <= 0.5):
        parser.error("--contamination deve estar no intervalo (0.0, 0.5].")
    if args.n_estimators < 1:
        parser.error("--n-estimators deve ser maior ou igual a 1.")
    if args.top_k < 1:
        parser.error("--top-k deve ser maior ou igual a 1.")
    return args


def main(argv: list[str] | None = None) -> int:
    """
    Ponto de entrada da CLI de treinamento: carrega o banco, prepara os dados,
    treina e avalia o Isolation Forest e salva o artefato `.pkl`.
    """
    args = parse_args(argv)
    raw_df = load_telemetry_from_sqlite(args.db)
    if raw_df.empty:
        print(f"Nenhum registro de telemetria encontrado em: {args.db}", file=sys.stderr)
        return 1

    prepared_df, report = prepare_dataset(raw_df, include_estimated_timestamp=False)
    print(format_quality_report(report))
    if prepared_df.empty:
        print("Todos os registros foram removidos pelas regras de limpeza.", file=sys.stderr)
        return 1

    try:
        artifact = train_anomaly_model(
            prepared_df,
            contamination=args.contamination,
            n_estimators=args.n_estimators,
            random_state=args.random_state,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    artifact.training_metadata["data_quality_report"] = report.to_dict()
    evaluation = evaluate_anomaly_model(prepared_df, artifact, top_k=args.top_k)
    artifact.training_metadata["synthetic_validation"] = {
        "samples": evaluation["synthetic_samples"],
        "detected": evaluation["synthetic_detected_count"],
        "detection_rate_pct": evaluation["synthetic_detection_rate_pct"],
        "by_category": evaluation["synthetic_by_category"].to_dict(orient="records"),
    }

    saved_path = save_model_artifact(artifact, args.model_out)
    print(format_training_and_evaluation_report(artifact, evaluation, saved_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
