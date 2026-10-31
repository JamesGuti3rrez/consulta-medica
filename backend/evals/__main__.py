from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
from dataclasses import replace
from datetime import datetime
from importlib.metadata import distributions
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from server.config import ROOT_DIR, settings
from .telemetry import configure_external_tracing, evaluation_tracing

# .env ya fue leído: respetar su trazado antes de importar LangGraph/RAGAS.
# main() permite cambiarlo explícitamente para una ejecución mediante CLI.
configure_external_tracing(settings.langsmith_tracing and bool(settings.langsmith_api_key))

from server.cases.catalog import CURATED_CASES_DIR
from server.cases.source import build_case_repository
from server.rag.factory import build_retriever
from .dataset import digest, load_dataset
from .ragas_bridge import RagasEvaluator
from .reporting import export
from .runner import HashedRetrievalLogger, evaluate


def now():
    try:
        return datetime.now(ZoneInfo("America/Lima")).isoformat()
    except ZoneInfoNotFoundError:
        from datetime import timedelta, timezone
        return datetime.now(timezone(timedelta(hours=-5))).isoformat()


def main():
    parser = argparse.ArgumentParser(description="TA-023: benchmark del recuperador real, sin sesiones")
    parser.add_argument("--dataset", type=Path, default=Path(__file__).parent / "datasets/clinical_v1.json")
    parser.add_argument("--k", type=int, nargs="+", default=[3, 5])
    parser.add_argument("--ragas", choices=["off", "ids", "llm"], default="off")
    parser.add_argument("--generate-responses", action="store_true")
    parser.add_argument("--limit", type=int, help="Evalúa solo las primeras N consultas para una corrida breve")
    parser.add_argument("--langsmith", action=argparse.BooleanOptionalAction, default=None,
                        help="Activa/desactiva trazas LangSmith; por defecto usa LANGSMITH_TRACING de .env")
    parser.add_argument("--profile", choices=["configured", "local"], default="configured")
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "results" / datetime.now().strftime("%Y%m%d-%H%M%S"))
    args = parser.parse_args()
    if any(k < 1 or k > 20 for k in args.k):
        parser.error("k debe estar entre 1 y 20")
    if args.limit is not None and args.limit < 1:
        parser.error("--limit debe ser positivo")
    tracing_requested = settings.langsmith_tracing if args.langsmith is None else args.langsmith
    tracing_enabled = tracing_requested and bool(settings.langsmith_api_key)
    configure_external_tracing(tracing_enabled)
    ks = sorted(set(args.k))
    output = args.output.resolve()
    # Ningún artefacto clínico se publica en carpetas servidas al estudiante ni sobre fuentes.
    for restricted in (ROOT_DIR / "frontend", ROOT_DIR / "data", ROOT_DIR / "backend/server",
                       ROOT_DIR / "backend/tests", ROOT_DIR / "backend/evals/datasets"):
        if output == restricted.resolve() or output.is_relative_to(restricted.resolve()):
            parser.error("Ubicación de salida reservada; use backend/evals/results o un directorio privado")
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        parser.error("La salida debe estar vacía para no sobrescribir una corrida anterior")
    config = settings if args.profile == "configured" else replace(
        settings, case_store="local", rag_backend="local", rag_service_url="")
    metadata = {"started_at": now(), "profile": args.profile, "ks": ks, "limit": args.limit,
                "external_tracing": ("enabled; LangSmith" if tracing_enabled else "disabled; local artifacts only"),
                "langsmith_project": settings.langsmith_project if tracing_enabled else None,
                "langsmith_tracing_requested": tracing_requested,
                "python": platform.python_version(), "dataset_sha256": hashlib.sha256(args.dataset.read_bytes()).hexdigest(),
                "case_store": config.case_store, "generate_responses": args.generate_responses,
                "packages": {dist.metadata["Name"]: dist.version for dist in distributions()},
                "code_sha256": digest({str(path.relative_to(ROOT_DIR)): hashlib.sha256(path.read_bytes()).hexdigest()
                                       for folder in (ROOT_DIR / "backend/server", ROOT_DIR / "backend/evals")
                                       for path in sorted(folder.rglob("*.py"))})}
    try:
        metadata["git_commit"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT_DIR, text=True).strip()
        metadata["git_dirty"] = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT_DIR, text=True).strip())
    except (OSError, subprocess.SubprocessError):
        metadata["git_commit"] = None
    partial_rows, partial_traces = [], []
    evaluator = None

    def on_complete(index, total, test_id, rows, traces):
        # Copiar solo al completar una consulta: nunca exportar una consulta a medias.
        partial_rows[:] = rows
        partial_traces[:] = traces
        print(f"[{index}/{total}] {test_id} completada", flush=True)

    try:
        print(f"Salida: {output}", flush=True)
        if tracing_requested and not settings.langsmith_api_key:
            print("LangSmith desactivado: falta LANGSMITH_API_KEY; se conservan las trazas locales.", flush=True)
        print("Validando referencias contra el almacén de casos configurado...", flush=True)
        repository = build_case_repository(CURATED_CASES_DIR, config=config)
        records = load_dataset(args.dataset, repository, limit=args.limit)
        metadata["selected_test_ids"] = [record["test_id"] for record in records]
        retriever = build_retriever(repository, config=config, log_path=output / "retrieval.jsonl")
        metadata["retriever"] = {"class": type(retriever).__name__, "requested_backend": config.rag_backend,
                                 "embedded_enabled": config.rag_embedded_enabled,
                                 "http_configured": bool(config.rag_service_url), "top_k": max(ks)}
        if hasattr(retriever, "service"):
            retriever.service.logger = HashedRetrievalLogger(output / "retrieval.jsonl")
            metadata["retriever"]["health"] = retriever.service.health()
        if hasattr(retriever, "_provider"):
            metadata["retriever"]["embedding"] = retriever._provider.metadata.as_dict()
        metadata["cases_sha256"] = {record["case_id"]: record["case_sha256"] for record in records}
        evaluator = RagasEvaluator(args.ragas)
        print(f"{len(records)} consultas; {type(retriever).__name__}; RAGAS={args.ragas}; "
              f"LangSmith={'activado' if tracing_enabled else 'desactivado'}.", flush=True)
        if args.generate_responses:
            print("Generación y evaluación de respuestas activadas; la carga inicial de embeddings puede tardar.", flush=True)
        with evaluation_tracing(enabled=tracing_enabled, project_name=settings.langsmith_project):
            rows, traces = evaluate(records, repository, retriever, ks, evaluator,
                                    generate_responses=args.generate_responses, on_complete=on_complete)
        metadata["ragas"] = evaluator.config
        metadata["finished_at"] = now()
        metadata["status"] = ("security_failure" if any(row["security_failure"] for row in rows) else
                              "retrieval_errors" if any(row["retrieval_status"] != "ok" for row in rows) else "ok")
        export(output, rows, traces, metadata)
    except KeyboardInterrupt:
        metadata.update(status="interrupted", completed_queries=len(partial_traces), finished_at=now())
        if evaluator is not None:
            metadata["ragas"] = evaluator.config
        if partial_rows:
            export(output, partial_rows, partial_traces, metadata)
        else:
            (output / "run.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nInterrumpido: {len(partial_traces)} consultas completas guardadas en {output}", flush=True)
        return 130
    except Exception as exc:
        # No cuerpos de proveedores, secretos ni texto protegido en los errores exportados.
        metadata.update(status="initialization_or_run_error", exception_type=type(exc).__name__, finished_at=now())
        (output / "run.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        print(f"Evaluación incompleta ({type(exc).__name__}); consulte {output / 'run.json'}")
        return 2
    print(f"{len(records)} consultas; {metadata['retriever']['class']}; {metadata['status']}; {output}")
    return 0 if metadata["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
