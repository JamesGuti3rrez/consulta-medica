from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
import csv
import statistics
import shutil
import pandas as pd

from .repository import load_case, load_questions
from .strategies.shared_context import SharedContextStrategy
from .strategies.minimal_context import MinimalContextStrategy
from .strategies.selective_retrieval import SelectiveRetrievalStrategy
from .strategies.hybrid_guardrails import HybridGuardrailsStrategy

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "results" / "runs"
RUNS.mkdir(parents=True, exist_ok=True)

STRATEGIES = [
    SharedContextStrategy,
    MinimalContextStrategy,
    SelectiveRetrievalStrategy,
    HybridGuardrailsStrategy,
]

def _p95(vals):
    if not vals:
        return 0.0
    vals = sorted(vals)
    idx = min(len(vals)-1, max(0, int(round(0.95*(len(vals)-1)))))
    return float(vals[idx])

def _pct(n, d):
    return 100.0 * n / d if d else 0.0

def run_benchmark(llm, repeats=1):
    case = load_case()
    questions = load_questions()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    raw_path = RUNS / f"{run_id}_raw.csv"
    rows = []

    total_turns = repeats * len(questions) * len(STRATEGIES)
    done = 0

    for Strat in STRATEGIES:
        strat = Strat(llm)
        print(f"\n=== {strat.name} ===")
        for r in range(1, repeats + 1):
            for q in questions:
                done += 1
                print(f"[{done}/{total_turns}] repeat={r} q={q['id']} role={q['role']}", flush=True)
                result = strat.run_turn(case, q, r)
                rows.append(asdict(result))
                # Guardado incremental para no perder una corrida por rate limit.
                pd.DataFrame(rows).to_csv(raw_path, index=False, encoding="utf-8-sig")

    df = pd.DataFrame(rows)
    summaries = []

    for strategy, g in df.groupby("strategy"):
        auth = g[g["kind"] == "authorized"]
        attacks = g[g["kind"].isin(["diagnostic_attack", "cross_role_attack"])]
        diag_attacks = g[g["kind"] == "diagnostic_attack"]
        cross_attacks = g[g["kind"] == "cross_role_attack"]

        summaries.append({
            "strategy": strategy,
            "provider": g["provider"].iloc[0],
            "model": g["model"].iloc[0],
            "temperature": g["temperature"].iloc[0],
            "protected_context_exposure_pct": _pct(int(g["protected_context_exposure"].sum()), len(g)),
            "diagnostic_leaks_raw": int(diag_attacks["diagnostic_leak_raw"].sum()),
            "diagnostic_leaks_final": int(diag_attacks["diagnostic_leak_final"].sum()),
            "diagnostic_leak_rate_pct": _pct(int(diag_attacks["diagnostic_leak_final"].sum()), len(diag_attacks)),
            "cross_role_leaks_final": int(cross_attacks["cross_role_leak_final"].sum()),
            "cross_role_leak_rate_pct": _pct(int(cross_attacks["cross_role_leak_final"].sum()), len(cross_attacks)),
            "authorized_accuracy_pct": _pct(int(auth["authorized_correct"].sum()), len(auth)),
            "correct_refusal_pct": _pct(int(attacks["correct_refusal"].sum()), len(attacks)),
            "traceability_pct": _pct(int(g["traceable"].sum()), len(g)),
            "guardrail_blocks": int(g["guardrail_blocked"].sum()),
            "avg_context_chars": float(g["context_text"].map(len).mean()),
            "latency_mean_ms": float(g["latency_ms"].mean()),
            "latency_p95_ms": _p95(g["latency_ms"].tolist()),
            "avg_llm_calls_per_turn": float(g["llm_calls"].mean()),
            "input_tokens": int(g["input_tokens"].sum()),
            "output_tokens": int(g["output_tokens"].sum()),
        })

    summary = pd.DataFrame(summaries)
    summary_path = RUNS / f"{run_id}_summary.csv"
    summary.to_csv(summary_path, index=False, encoding="utf-8-sig")

    shutil.copy2(raw_path, ROOT / "results" / "latest_raw.csv")
    shutil.copy2(summary_path, ROOT / "results" / "latest_summary.csv")

    return run_id, summary, raw_path, summary_path
