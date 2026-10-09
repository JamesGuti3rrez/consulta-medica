from __future__ import annotations

import argparse
import json
import uuid

from dotenv import load_dotenv

from app.architectures import build_architectures
from app.benchmark import run_benchmark
from app.case_store import load_all_cases
from app.llm import make_provider
from app.models import SessionState


load_dotenv()


def cmd_demo(args):
    llm = make_provider(args.provider, args.model)
    architectures = {a.name: a for a in build_architectures(llm)}
    arch = architectures[args.architecture]
    case = load_all_cases()[0]
    session = SessionState(session_id="DEMO-001", case_id=case["case_id"])
    result = arch.run_turn(case, "DEMO", args.question, session)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2, default=list))


def cmd_benchmark(args):
    llm = make_provider(args.provider, args.model)
    _, summary = run_benchmark(llm, repeats=args.repeats, limit_cases=args.limit_cases)
    print(summary.to_string(index=False))
    print("\nCSV guardados en results/raw_results.csv y results/summary.csv")


def main():
    parser = argparse.ArgumentParser(description="Benchmark de arquitecturas multiagente para Paciente Virtual Adaptativo")
    sub = parser.add_subparsers(dest="command", required=True)

    demo = sub.add_parser("demo")
    demo.add_argument("--provider", choices=["mock", "groq"], default="mock")
    demo.add_argument("--model", default=None)
    demo.add_argument("--architecture", choices=["supervisor", "stategraph", "handoffs", "supervisor_handoffs"], default="stategraph")
    demo.add_argument("--question", default="¿Cuál es el resultado de la troponina?")
    demo.set_defaults(func=cmd_demo)

    bench = sub.add_parser("benchmark")
    bench.add_argument("--provider", choices=["mock", "groq"], default="mock")
    bench.add_argument("--model", default=None)
    bench.add_argument("--repeats", type=int, default=1)
    bench.add_argument("--limit-cases", type=int, default=None)
    bench.set_defaults(func=cmd_benchmark)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
