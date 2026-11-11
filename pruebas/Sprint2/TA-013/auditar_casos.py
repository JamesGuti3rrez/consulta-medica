"""Inventario, muestreo estratificado y auditoría técnica TA-013.

La auditoría reutiliza los validadores del backend. No realiza ni certifica una
validación clínica por profesionales.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "backend"
DEFAULT_CASE_DIR = ROOT / "data" / "cases" / "curated"
DEFAULT_REVIEW_DIR = ROOT / "data" / "cases" / "reviews"
DEFAULT_OUTPUT_DIR = ROOT / "pruebas" / "Sprint2" / "TA-013" / "resultados"
SPECIALTIES = (
    "medicina_interna",
    "pediatria",
    "cirugia_general",
    "ginecologia_obstetricia",
    "emergencias",
)
REVIEW_KEYS = {"clinical_review", "assessment", "review", "disposition"}
REVIEWER_KEYS = {
    "reviewer",
    "reviewed_by",
    "reviewer_role",
    "professional_title",
    "professional_license",
    "credentials",
}
CASE_ID_IN_MESSAGE = re.compile(r"\b[A-Z]{3,5}-\d{3}\b")

sys.path.insert(0, str(BACKEND))

from jsonschema import Draft202012Validator  # noqa: E402

from server.cases.consistency import review_case  # noqa: E402
from server.cases.rules import check_batch_rules  # noqa: E402
from server.cases.validator import load_schema  # noqa: E402


INVENTORY_FIELDS = [
    "origin",
    "case_id",
    "specialty",
    "status",
    "schema_version",
    "source_dataset",
    "source_item_id",
    "source_license",
    "curated_by",
    "curated_at",
    "file",
    "fingerprint",
    "clinical_review_status",
    "review_evidence_files",
    "reviewer_metadata",
    "duplicate_case_id_within_origin",
    "duplicate_source_record",
    "same_case_id_across_stores",
    "matching_content_across_stores",
    "load_error",
]


def _fingerprint(document: Any) -> str:
    encoded = json.dumps(
        document, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return str(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _walk(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def load_review_index(
    review_dir: Path,
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Indexa documentación por caso; no interpreta autoría como credencial clínica."""
    index: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"files": set(), "review_found": False, "reviewer_metadata": set()}
    )
    errors: list[str] = []
    if not review_dir.is_dir():
        return index, [f"No existe la carpeta de revisiones: {review_dir}"]
    for path in sorted(review_dir.rglob("*.json")):
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{path.relative_to(ROOT)}: {type(exc).__name__}: {exc}")
            continue
        for node in _walk(document):
            case_id = node.get("case_id")
            if not isinstance(case_id, str):
                continue
            record = index[case_id]
            record["files"].add(str(path.relative_to(ROOT)))
            if REVIEW_KEYS.intersection(node):
                record["review_found"] = True
            for key in REVIEWER_KEYS:
                value = node.get(key)
                if isinstance(value, (str, int, float)) and str(value).strip():
                    record["reviewer_metadata"].add(f"{key}={value}")
    return index, errors


def _record_from_document(
    document: Any,
    origin: str,
    file_name: str,
    review_index: dict[str, dict[str, Any]],
    load_error: str = "",
) -> dict[str, Any]:
    case = document if isinstance(document, dict) else {}
    raw_case_id = case.get("case_id")
    case_id = raw_case_id if isinstance(raw_case_id, str) and raw_case_id else Path(file_name).stem
    review = review_index.get(case_id, {})
    source = case.get("source")
    provenance = case.get("provenance")
    source = source if isinstance(source, dict) else {}
    provenance = provenance if isinstance(provenance, dict) else {}
    return {
        "origin": origin,
        "case_id": case_id,
        "specialty": _text(case.get("specialty", "")),
        "status": _text(case.get("status", "")),
        "schema_version": _text(case.get("schema_version", "")),
        "source_dataset": _text(source.get("dataset", "")),
        "source_item_id": _text(source.get("item_id", "")),
        "source_license": _text(source.get("license", "")),
        "curated_by": _text(provenance.get("curated_by", "")),
        "curated_at": _text(provenance.get("curated_at", "")),
        "file": file_name,
        "fingerprint": _fingerprint(document) if not load_error else "",
        "clinical_review_status": (
            "documented_review_expertise_unverified"
            if review.get("review_found")
            else "no_documented_review_found"
        ),
        "review_evidence_files": sorted(review.get("files", set())),
        "reviewer_metadata": sorted(review.get("reviewer_metadata", set())),
        "duplicate_case_id_within_origin": False,
        "duplicate_source_record": False,
        "same_case_id_across_stores": False,
        "matching_content_across_stores": False,
        "load_error": load_error,
    }


def load_local_records(
    case_dir: Path, review_index: dict[str, dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not case_dir.is_dir():
        raise FileNotFoundError(f"No existe la carpeta de casos: {case_dir}")
    records: list[dict[str, Any]] = []
    documents: dict[str, Any] = {}
    for path in sorted(case_dir.glob("*.json")):
        relative = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            records.append(
                _record_from_document(
                    {}, "local", relative, review_index,
                    f"{type(exc).__name__}: {exc}",
                )
            )
            continue
        record = _record_from_document(document, "local", relative, review_index)
        records.append(record)
        documents[record["file"]] = document
    return records, documents


def load_remote_records(
    review_index: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Consulta Supabase únicamente cuando se selecciona explícitamente --include-supabase."""
    from server.cases.supabase import SupabaseCaseRepository
    from server.config import settings

    repository = SupabaseCaseRepository(
        settings.supabase_url, settings.supabase_secret_key
    )
    cases = repository.list_cases()
    return [
        _record_from_document(
            case,
            "supabase",
            f"casos_curados/{case['case_id']}",
            review_index,
        )
        for case in cases
    ]


def mark_duplicates(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_origin_case: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    by_origin_source: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    by_case_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_origin_case[(record["origin"], str(record["case_id"]))].append(record)
        dataset = record.get("source_dataset")
        item_id = record.get("source_item_id")
        if dataset and item_id:
            by_origin_source[
                (record["origin"], str(dataset), str(item_id))
            ].append(record)
        by_case_id[str(record["case_id"])].append(record)

    for group in by_origin_case.values():
        if len(group) > 1:
            for record in group:
                record["duplicate_case_id_within_origin"] = True
    for group in by_origin_source.values():
        if len(group) > 1:
            for record in group:
                record["duplicate_source_record"] = True
    for group in by_case_id.values():
        origins = {record["origin"] for record in group}
        if {"local", "supabase"} <= origins:
            fingerprints = {record["fingerprint"] for record in group}
            for record in group:
                record["same_case_id_across_stores"] = True
                record["matching_content_across_stores"] = len(fingerprints) == 1
    return records


def write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: json.dumps(value, ensure_ascii=False)
                    if isinstance(value, (list, dict))
                    else value
                    for key, value in row.items()
                }
            )


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def run_inventory(args: argparse.Namespace) -> int:
    review_index, review_errors = load_review_index(args.review_dir)
    records, _ = load_local_records(args.case_dir, review_index)
    if args.include_supabase:
        records.extend(load_remote_records(review_index))
    mark_duplicates(records)

    summary = {
        "task": "TA-013",
        "records": len(records),
        "counts_by_origin": dict(Counter(row["origin"] for row in records)),
        "counts_by_specialty": dict(
            Counter(row["specialty"] or "(sin especialidad)" for row in records)
        ),
        "review_scan_errors": review_errors,
        "clinical_validation": (
            "No se declara ningún caso clínicamente validado. "
            "La documentación localizada no acredita por sí sola la competencia del revisor."
        ),
        "records_detail": records,
    }
    write_json(args.output_dir / "inventario_casos.json", summary)
    write_csv(args.output_dir / "inventario_casos.csv", INVENTORY_FIELDS, records)
    print(f"Registros inventariados: {len(records)}")
    print(f"Por origen: {summary['counts_by_origin']}")
    print(f"JSON: {args.output_dir / 'inventario_casos.json'}")
    print(f"CSV:  {args.output_dir / 'inventario_casos.csv'}")
    if review_errors:
        print(f"Advertencia: errores al leer {len(review_errors)} archivo(s) de revisión.")
    return 0


def allocate_strata(
    groups: dict[str, list[dict[str, Any]]], sample_size: int, seed: int
) -> list[dict[str, Any]]:
    """Muestrea proporcionalmente usando el déficit de cuota y una semilla fija."""
    nonempty = [name for name in SPECIALTIES if groups.get(name)]
    available = sum(len(groups[name]) for name in nonempty)
    target = min(sample_size, available)
    if target <= 0 or not nonempty:
        return []

    quotas = {
        name: target * len(groups[name]) / available
        for name in nonempty
    }
    allocations = {
        name: 1 if target >= len(nonempty) else 0
        for name in nonempty
    }

    while sum(allocations.values()) < target:
        eligible = [name for name in nonempty if allocations[name] < len(groups[name])]
        if not eligible:
            break
        eligible.sort(key=lambda name: (-(quotas[name] - allocations[name]), name))
        allocations[eligible[0]] += 1

    rng = random.Random(seed)
    selected: list[dict[str, Any]] = []
    for name in nonempty:
        members = sorted(groups[name], key=lambda row: str(row["case_id"]))
        selected.extend(rng.sample(members, allocations[name]))
    return sorted(selected, key=lambda row: (row.get("specialty", ""), str(row["case_id"])))


def run_sample(args: argparse.Namespace) -> int:
    inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
    records = inventory.get("records_detail")
    if not isinstance(records, list):
        raise ValueError(f"El inventario no contiene records_detail: {args.inventory}")
    eligible = [
        row for row in records
        if row.get("origin") == "local"
        and not row.get("load_error")
        and row.get("case_id")
        and row.get("specialty") in SPECIALTIES
    ]
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in eligible:
        groups[row["specialty"]].append(row)
    selected = allocate_strata(groups, args.size, args.seed)
    result = {
        "task": "TA-013",
        "method": "muestreo aleatorio estratificado proporcional",
        "seed": args.seed,
        "requested_sample_size": args.size,
        "selected_sample_size": len(selected),
        "population_size": len(eligible),
        "population_by_specialty": {
            specialty: len(groups.get(specialty, [])) for specialty in SPECIALTIES
        },
        "sample_by_specialty": dict(Counter(row["specialty"] for row in selected)),
        "case_ids": [row["case_id"] for row in selected],
        "records": selected,
        "clinical_review_note": (
            "La selección no constituye revisión clínica experta ni certifica los casos."
        ),
    }
    write_json(args.output, result)
    print(f"Población local elegible: {len(eligible)}")
    print(f"Muestra seleccionada: {len(selected)} (semilla {args.seed})")
    print(f"Por especialidad: {result['sample_by_specialty']}")
    print(f"JSON: {args.output}")
    if len(selected) < args.size:
        print("Aviso: el catálogo contiene menos casos elegibles que el tamaño solicitado.")
    return 0


def _finding(
    case_id: str, code: str, severity: str, message: str, path: str = ""
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "code": code,
        "severity": severity,
        "path": path,
        "message": message,
    }


def run_audit(args: argparse.Namespace) -> int:
    review_index, review_errors = load_review_index(args.review_dir)
    records, documents_by_file = load_local_records(args.case_dir, review_index)
    if args.sample_file:
        manifest = json.loads(args.sample_file.read_text(encoding="utf-8"))
        case_ids = manifest.get("case_ids")
        if not isinstance(case_ids, list) or not all(isinstance(item, str) for item in case_ids):
            raise ValueError(f"Muestra inválida: {args.sample_file}")
        selected_ids = set(case_ids)
        available_ids = {str(row["case_id"]) for row in records}
        absent = selected_ids - available_ids
        if absent:
            raise ValueError(f"Casos de la muestra no encontrados localmente: {sorted(absent)}")
        sample_records = manifest.get("records")
        if isinstance(sample_records, list) and all(
            isinstance(item, dict) and isinstance(item.get("file"), str)
            for item in sample_records
        ):
            selected_files = {item["file"] for item in sample_records}
            records = [row for row in records if row["file"] in selected_files]
        else:
            records = [row for row in records if str(row["case_id"]) in selected_ids]
        selected_files = {row["file"] for row in records}
        documents_by_file = {
            key: value for key, value in documents_by_file.items() if key in selected_files
        }

    schema_validator = Draft202012Validator(load_schema())
    case_results: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    valid_documents: list[dict[str, Any]] = []
    for row in records:
        case_id = str(row["case_id"])
        if row.get("load_error"):
            finding = _finding(case_id, "JSON001", "error", row["load_error"])
            findings.append(finding)
            case_results.append(
                {
                    "case_id": case_id,
                    "specialty": row.get("specialty", ""),
                    "schema_valid": False,
                    "status": "bloqueado",
                    "finding_count": 1,
                    "clinical_review_status": row["clinical_review_status"],
                    "expert_clinical_review_verified": False,
                }
            )
            continue

        case = documents_by_file[row["file"]]
        schema_errors = sorted(
            schema_validator.iter_errors(case),
            key=lambda error: (list(map(str, error.absolute_path)), error.message),
        )
        if schema_errors:
            case_findings = [
                _finding(
                    case_id,
                    "SCHEMA",
                    "error",
                    error.message,
                    ".".join(map(str, error.absolute_path)),
                )
                for error in schema_errors
            ]
            schema_valid = False
            status = "bloqueado"
        else:
            schema_valid = True
            valid_documents.append(case)
            report = review_case(case)
            case_findings = [
                _finding(
                    case_id,
                    item["code"],
                    item["severity"],
                    item["message"],
                    item["path"],
                )
                for item in report["findings"]
            ]
            status = report["status"]

        findings.extend(case_findings)
        case_results.append(
            {
                "case_id": case_id,
                "specialty": row.get("specialty", ""),
                "schema_valid": schema_valid,
                "status": status,
                "finding_count": len(case_findings),
                "clinical_review_status": row["clinical_review_status"],
                "expert_clinical_review_verified": False,
            }
        )

    batch_findings: list[dict[str, Any]] = []
    batch_ids = {case["case_id"] for case in valid_documents}
    for message in check_batch_rules(valid_documents):
        match = CASE_ID_IN_MESSAGE.search(message)
        case_id = match.group(0) if match and match.group(0) in batch_ids else ""
        code = message.split(maxsplit=1)[0]
        batch_findings.append(_finding(case_id, code, "error", message))
    findings.extend(batch_findings)

    summary = {
        "task": "TA-013",
        "scope": "Validación técnica automática; no sustituye revisión clínica experta.",
        "source": str(args.sample_file) if args.sample_file else str(args.case_dir),
        "cases_processed": len(case_results),
        "cases_by_specialty": dict(
            Counter(row["specialty"] or "(sin especialidad)" for row in case_results)
        ),
        "schema_valid_cases": sum(row["schema_valid"] for row in case_results),
        "finding_count": len(findings),
        "findings_by_severity": dict(Counter(item["severity"] for item in findings)),
        "batch_finding_count": len(batch_findings),
        "review_scan_errors": review_errors,
        "cases": case_results,
        "findings": findings,
        "clinical_validation": (
            "No se certifica clínicamente ningún caso. "
            "expert_clinical_review_verified permanece false."
        ),
    }
    write_json(args.output_dir / "auditoria_ta013.json", summary)
    write_csv(
        args.output_dir / "auditoria_casos.csv",
        [
            "case_id", "specialty", "schema_valid", "status", "finding_count",
            "clinical_review_status", "expert_clinical_review_verified",
        ],
        case_results,
    )
    write_csv(
        args.output_dir / "auditoria_hallazgos.csv",
        ["case_id", "code", "severity", "path", "message"],
        findings,
    )
    print(f"Casos auditados: {len(case_results)}")
    print(f"Hallazgos: {len(findings)}; por severidad: {summary['findings_by_severity']}")
    print(f"JSON: {args.output_dir / 'auditoria_ta013.json'}")
    print(f"CSV casos: {args.output_dir / 'auditoria_casos.csv'}")
    print(f"CSV hallazgos: {args.output_dir / 'auditoria_hallazgos.csv'}")
    return 1 if any(item["severity"] == "error" for item in findings) else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    inventory = subparsers.add_parser(
        "inventory", help="Genera inventario local y opcionalmente remoto."
    )
    inventory.add_argument("--case-dir", type=Path, default=DEFAULT_CASE_DIR)
    inventory.add_argument("--review-dir", type=Path, default=DEFAULT_REVIEW_DIR)
    inventory.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    inventory.add_argument(
        "--include-supabase",
        action="store_true",
        help="Consulta Supabase en modo de solo lectura; requiere configuración local.",
    )
    inventory.set_defaults(handler=run_inventory)

    sample = subparsers.add_parser(
        "sample", help="Selecciona una muestra estratificada reproducible."
    )
    sample.add_argument(
        "--inventory", type=Path, default=DEFAULT_OUTPUT_DIR / "inventario_casos.json"
    )
    sample.add_argument(
        "--output", type=Path, default=DEFAULT_OUTPUT_DIR / "muestra_estratificada.json"
    )
    sample.add_argument("--size", type=int, default=43)
    sample.add_argument("--seed", type=int, default=20261106)
    sample.set_defaults(handler=run_sample)

    audit = subparsers.add_parser(
        "audit", help="Audita el catálogo local completo o una muestra."
    )
    audit.add_argument("--case-dir", type=Path, default=DEFAULT_CASE_DIR)
    audit.add_argument("--review-dir", type=Path, default=DEFAULT_REVIEW_DIR)
    audit.add_argument("--sample-file", type=Path)
    audit.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    audit.set_defaults(handler=run_audit)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "size", 1) < 1:
        parser.error("--size debe ser al menos 1")
    try:
        return args.handler(args)
    except (OSError, json.JSONDecodeError, ValueError, RuntimeError) as exc:
        print(f"TA-013 detenido ({type(exc).__name__}): {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
