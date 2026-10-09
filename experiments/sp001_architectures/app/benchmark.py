from __future__ import annotations

import json
import statistics
import uuid
from datetime import datetime, timezone
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pandas as pd

from app.architectures import build_architectures
from app.case_store import load_all_cases, load_questions
from app.models import SessionState


ROOT = Path(__file__).resolve().parents[1]


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    idx = max(0, min(len(values) - 1, int(round(0.95 * (len(values) - 1)))))
    return values[idx]


def run_benchmark(llm, repeats: int = 1, limit_cases: int | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    architectures = build_architectures(llm)
    cases = load_all_cases()
    if limit_cases:
        cases = cases[:limit_cases]
    fidelity = load_questions("fidelity")
    leakage = load_questions("leakage")

    rows: list[dict[str, Any]] = []
    run_id = str(uuid.uuid4())
    generated_at = datetime.now(timezone.utc).isoformat()
    for arch in architectures:
        for case in cases:
            for repeat in range(repeats):
                for q in fidelity + leakage:
                    session = SessionState(session_id=str(uuid.uuid4()), case_id=case["case_id"])
                    result = arch.run_turn(case, q["id"], q["question"], session)
                    expected = set(q.get("expected_evidence_ids", []))
                    got = set(result.answer.evidence_ids)
                    if q.get("kind") == "fidelity" and expected:
                        evidence_covered = len(expected & got) / len(expected)
                    elif q.get("kind") == "fidelity" and q.get("expected_absent", False):
                        evidence_covered = 1.0 if result.answer.refused and not got else 0.0
                    else:
                        evidence_covered = None
                    expected_route = q.get("expected_route")
                    route_correct = (expected_route in result.route_trace) if expected_route else None
                    trace_complete = bool(result.session_id and result.case_id and result.question_id and result.agent and result.route_trace and isinstance(result.validation, dict))
                    rows.append({
                        "run_id": run_id,
                        "generated_at_utc": generated_at,
                        "provider": getattr(llm, "provider_name", type(llm).__name__),
                        "model": getattr(llm, "model_name", "unknown"),
                        "temperature": getattr(llm, "temperature", None),
                        "architecture": arch.name,
                        "case_id": case["case_id"],
                        "repeat": repeat + 1,
                        "question_id": q["id"],
                        "kind": q["kind"],
                        "question": q["question"],
                        "expected_route": expected_route,
                        "route_correct": route_correct,
                        "route_signature": "->".join(result.route_trace),
                        "evidence_coverage": evidence_covered,
                        "hallucinated_entities": result.validation["hallucinated_entities"],
                        "wrong_values": len(result.validation["wrong_values"]),
                        "wrong_units": len(result.validation["wrong_units"]),
                        "diagnostic_leak": result.validation["diagnostic_leak"],
                        "refused": result.answer.refused,
                        "validated": result.validation["validated"],
                        "trace_complete": trace_complete,
                        "latency_ms": result.latency_ms,
                        "llm_calls": result.usage.llm_calls,
                        "input_tokens": result.usage.input_tokens,
                        "output_tokens": result.usage.output_tokens,
                        "response": result.answer.natural_response,
                        "evidence_ids": json.dumps(result.answer.evidence_ids, ensure_ascii=False),
                    })

    raw = pd.DataFrame(rows)
    summary_rows = []
    for arch, df in raw.groupby("architecture"):
        fid = df[df.kind == "fidelity"]
        leak = df[df.kind == "leakage"]
        route_values = fid["route_correct"].dropna().astype(float).tolist()

        # Consistencia: para cada pregunta, proporción de la ruta modal entre repeticiones.
        consistencies = []
        for _, qdf in df.groupby(["case_id", "question_id"]):
            counts = Counter(qdf["route_signature"])
            consistencies.append(max(counts.values()) / len(qdf))

        summary_rows.append({
            "architecture": arch,
            "provider": df["provider"].iloc[0],
            "model": df["model"].iloc[0],
            "temperature": df["temperature"].iloc[0] if "temperature" in df else None,
            "evidence_coverage_pct": 100 * fid["evidence_coverage"].dropna().mean() if not fid.empty else 0,
            "hallucinated_entities": int(fid["hallucinated_entities"].sum()),
            "wrong_values": int(fid["wrong_values"].sum()),
            "wrong_units": int(fid["wrong_units"].sum()),
            "diagnostic_leaks": int(leak["diagnostic_leak"].sum()),
            "leak_rate_pct": 100 * leak["diagnostic_leak"].mean() if not leak.empty else 0,
            "route_accuracy_pct": 100 * statistics.mean(route_values) if route_values else 0,
            "route_consistency_pct": 100 * statistics.mean(consistencies) if consistencies else 0,
            "traceability_pct": 100 * df["trace_complete"].mean(),
            "latency_mean_ms": df["latency_ms"].mean(),
            "latency_p50_ms": df["latency_ms"].median(),
            "latency_p95_ms": _p95(df["latency_ms"].tolist()),
            "avg_llm_calls_per_turn": df["llm_calls"].mean(),
            "input_tokens": int(df["input_tokens"].sum()),
            "output_tokens": int(df["output_tokens"].sum()),
        })

    summary = pd.DataFrame(summary_rows).sort_values("architecture")
    results_dir = ROOT / "results"
    results_dir.mkdir(exist_ok=True)
    raw.to_csv(results_dir / "raw_results.csv", index=False)
    summary.to_csv(results_dir / "summary.csv", index=False)
    return raw, summary
