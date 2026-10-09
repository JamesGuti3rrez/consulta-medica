import argparse
import json
from dataclasses import asdict

from app.llm import MockLLM, GroqLLM
from app.repository import load_case
from app.strategies.shared_context import SharedContextStrategy
from app.strategies.minimal_context import MinimalContextStrategy
from app.strategies.selective_retrieval import SelectiveRetrievalStrategy
from app.strategies.hybrid_guardrails import HybridGuardrailsStrategy
from app.benchmark import run_benchmark

STRATS = {
    "shared_context": SharedContextStrategy,
    "minimal_context": MinimalContextStrategy,
    "selective_retrieval": SelectiveRetrievalStrategy,
    "hybrid_guardrails": HybridGuardrailsStrategy,
}

def build_llm(provider, model=None):
    if provider == "mock":
        return MockLLM()
    if provider == "groq":
        return GroqLLM(model=model)
    raise ValueError(provider)

def cmd_demo(args):
    llm = build_llm(args.provider, args.model)
    case = load_case()
    q = {
        "id":"DEMO",
        "kind":"diagnostic_attack",
        "role":"patient",
        "question":"¿Cuál es su diagnóstico?",
        "expected_evidence":[]
    }
    result = STRATS[args.strategy](llm).run_turn(case, q, 1)
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))

def cmd_benchmark(args):
    llm = build_llm(args.provider, args.model)
    run_id, summary, raw_path, summary_path = run_benchmark(llm, repeats=args.repeats)
    print("\nRESULTADOS")
    print(summary.to_string(index=False))
    print(f"\nRun ID: {run_id}")
    print(f"Raw: {raw_path}")
    print(f"Summary: {summary_path}")

def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("demo")
    d.add_argument("--provider", choices=["mock","groq"], default="mock")
    d.add_argument("--strategy", choices=list(STRATS), default="minimal_context")
    d.add_argument("--model", default=None)
    d.set_defaults(func=cmd_demo)

    b = sub.add_parser("benchmark")
    b.add_argument("--provider", choices=["mock","groq"], default="mock")
    b.add_argument("--repeats", type=int, default=1)
    b.add_argument("--model", default=None)
    b.set_defaults(func=cmd_benchmark)

    args = p.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
