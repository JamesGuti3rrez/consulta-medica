from __future__ import annotations

import argparse
import json
from pathlib import Path

from .adapters.medqa import extract_medqa_candidates
from .sources.fetch import fetch_dataset
from .sources.registry import SOURCE_DEFINITIONS
from .transform.medqa_final_review import build_reviewed_cases
from .transform.medqa_selection import build_selected_cases


def main() -> int:
    parser = argparse.ArgumentParser(description="Pipeline de preparación de casos del proyecto.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    sources_parser = subparsers.add_parser("sources", help="Obtiene datasets fuente")
    sources_subparsers = sources_parser.add_subparsers(dest="source_command", required=True)

    fetch_parser = sources_subparsers.add_parser("fetch", help="Descarga un dataset fuente")
    fetch_parser.add_argument("--dataset", required=True, choices=sorted(SOURCE_DEFINITIONS.keys()))

    adapters_parser = subparsers.add_parser("adapters", help="Adaptadores de entrada")
    adapters_subparsers = adapters_parser.add_subparsers(dest="adapter_command", required=True)

    extract_parser = adapters_subparsers.add_parser("extract", help="Extrae candidatos desde un dataset")
    extract_parser.add_argument("--dataset", required=True, choices=["medqa"])
    extract_parser.add_argument("--input-dir", type=Path, default=None)
    extract_parser.add_argument("--output", type=Path, default=None)

    transform_parser = subparsers.add_parser("transform", help="Transforma candidatos en casos canónicos")
    transform_parser.add_argument("--dataset", required=True, choices=["medqa"])
    transform_parser.add_argument("--input", type=Path, default=None)
    transform_parser.add_argument("--output-dir", type=Path, default=None)
    transform_parser.add_argument("--count", type=int, default=10)

    subparsers.add_parser("curation", help="Genera y cura el lote MedQA con la revisión clínica asistida registrada")

    args = parser.parse_args()
    if args.command == "sources" and args.source_command == "fetch":
        fetch_dataset(args.dataset)
        return 0

    if args.command == "adapters" and args.adapter_command == "extract":
        result = extract_medqa_candidates(raw_root=args.input_dir, output_path=args.output)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.command == "transform":
        repo_root = Path(__file__).resolve().parents[2]
        input_path = args.input or repo_root / "data" / "interim" / "medqa_candidatos.jsonl"
        output_dir = args.output_dir or repo_root / "data" / "cases" / "validated"
        result = build_selected_cases(input_path=input_path, output_dir=output_dir, count=args.count)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.command == "curation":
        result = build_reviewed_cases()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    parser.error("Comando no soportado")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
