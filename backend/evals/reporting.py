from __future__ import annotations

import csv
import json
import os
import tempfile
from pathlib import Path
from collections import Counter
from statistics import mean

METRICS = ("precision", "recall", "hit", "abstention", "ragas_context_precision",
           "ragas_context_recall", "ragas_faithfulness", "ragas_response_relevancy")


def aggregate(rows):
    summaries = []
    for specialty in ["ALL", *sorted({row["specialty"] for row in rows})]:
        for k in sorted({row["k"] for row in rows}):
            group = [row for row in rows if row["k"] == k and
                     (specialty == "ALL" or row["specialty"] == specialty)]
            scored = [row for row in group if row["retrieval_status"] == "ok"]
            summary = {"specialty": specialty, "k": k, "queries": len(group),
                       "retrieval_errors": len(group) - len(scored),
                       "answerable_queries": sum(bool(row["expected_evidence_ids"]) for row in scored),
                       "negative_queries": sum(not row["expected_evidence_ids"] for row in scored),
                       "security_failures": sum(row["security_failure"] for row in group)}
            for key in METRICS:
                values = [row[key] for row in scored if row.get(key) is not None]
                summary[key] = mean(values) if values else None
                summary[key + "_n"] = len(values)
            positive = [row["precision"] for row in scored if row["expected_evidence_ids"]]
            summary["precision_answerable"] = mean(positive) if positive else None
            summaries.append(summary)
    return summaries


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            # Evitar fórmulas al abrir consultas en una hoja de cálculo.
            encoded = {key: json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict))
                       else "'" + value if isinstance(value, str) and value.startswith(("=", "+", "-", "@"))
                       else value for key, value in row.items()}
            writer.writerow(encoded)


def write_charts(output, summaries):
    os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "consulta-medica-matplotlib"))
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return "unavailable: instale el extra evals"
    for k in sorted({row["k"] for row in summaries}):
        group = [row for row in summaries if row["k"] == k and row["specialty"] != "ALL"]
        fig, axes = plt.subplots(1, 2, figsize=(14, 6), constrained_layout=True)
        for axis, metrics in zip(axes, [("precision_answerable", "recall", "hit"),
                                        ("ragas_context_precision", "ragas_context_recall", "abstention")]):
            for index, metric in enumerate(metrics):
                positions = [x + (index - 1) * .24 for x in range(len(group))]
                axis.bar(positions, [row[metric] if row[metric] is not None else float('nan') for row in group],
                         width=.24, label=metric)
            axis.set_xticks(range(len(group)), [row["specialty"].replace("_", " ") for row in group],
                            rotation=25, ha="right", fontsize=8)
            axis.set_ylim(0, 1.08)
            axis.legend(fontsize=8)
            axis.grid(axis="y", alpha=.2)
        axes[0].set_title(f"Recuperación sobre consultas con referencia · k={k}")
        axes[1].set_title("RAGAS por IDs y abstención en consultas negativas")
        fig.savefig(output / f"comparison_k{k}.svg")
        plt.close(fig)
    return "ok; valores no aplicables se omiten en CSV (sin puntuación)"


def export(output, rows, traces, metadata):
    summaries = aggregate(rows)
    configured_rows = [{**row, "run_started_at": metadata["started_at"],
                        "retriever": metadata["retriever"]["class"],
                        "ragas_config": metadata.get("ragas", {})} for row in rows]
    write_csv(output / "queries.csv", configured_rows)
    write_csv(output / "summary.csv", summaries)
    (output / "traces.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in traces), encoding="utf-8")
    metadata["charts"] = write_charts(output, summaries)
    (output / "run.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    errors = Counter(error for row in rows if row["k"] == max(metadata["ks"]) for error in row["errors"])
    lines = ["# Informe de ejecución TA-023", "", f"Fecha: {metadata['started_at']}.", "",
             f"Estado: `{metadata.get('status', 'not_recorded')}`. "
             "Los promedios corresponden únicamente a las consultas completas exportadas.", "",
             f"Perfil: `{metadata['profile']}`. Recuperador efectivo: `{metadata['retriever']['class']}`.", "",
             f"{len(traces)} consultas, {len({row['case_id'] for row in rows})} casos y "
             f"{len({row['specialty'] for row in rows})} especialidades. k={metadata['ks']}.", "",
             "| Especialidad | k | P@k (con referencia) | Recall@k | Hit@k | Abstención | Fallos seguridad |",
             "|---|---:|---:|---:|---:|---:|---:|"]
    def fmt(value):
        return "N/A" if value is None else f"{value:.4f}"
    for row in summaries:
        lines.append(f"| {row['specialty']} | {row['k']} | {fmt(row['precision_answerable'])} | "
                     f"{fmt(row['recall'])} | {fmt(row['hit'])} | {fmt(row['abstention'])} | {row['security_failures']} |")
    lines += ["", "Errores por consulta a k máximo: `" + json.dumps(dict(errors), ensure_ascii=False) + "`.", "",
              "Estados RAGAS por IDs: `" + json.dumps(dict(Counter(row['ragas_ids_status'] for row in rows))) + "`.", "",
              "Estados de respuesta RAGAS (una evaluación por consulta, repetida en filas k): `" +
              json.dumps(dict(Counter(row['ragas_response_status'] for row in rows if row['k'] == max(metadata['ks'])))) + "`.", "",
              "La precisión usa k como denominador; retornar menos de k evidencias reduce P@k aunque todas sean relevantes. "
              "Recall y Hit excluyen consultas sin referencia; abstención solo usa esas consultas. "
              "summary.csv también incluye P@k de todas las consultas y los tamaños de cada denominador.", "",
              "Los fallos de seguridad invalidan la corrida aunque los promedios sean altos. Los errores de servicio "
              "no se convierten en recuperaciones vacías exitosas ni en ceros de calidad.", "",
              "Las métricas de respuestas usan el contexto de k máximo y el contexto público inicial. "
              "Fidelidad no demuestra corrección médica. Sin juez no se afirma ausencia de alucinaciones. "
              "No se generan ni contabilizan hechos sintéticos de agentes.", "",
              "Los contextos y respuestas permanecen en memoria: las trazas exportan IDs y hashes. "
              "La configuración, versiones, hashes del código y dataset están en run.json. "
              "El arnés no crea sesiones ni escribe casos o datos en Supabase.", ""]
    if metadata["retriever"]["class"] == "CaseEvidenceRetriever":
        lines += ["Esta corrida mide el fallback real de JSON: orden de origen y score constante 1. "
                  "No demuestra calidad de embeddings, LightRAG ni pgvector. Ejecutar el perfil configurado "
                  "con el índice/servicios del despliegue para medir esas rutas.", ""]
    (output / "report.md").write_text("\n".join(lines), encoding="utf-8")
    return summaries
