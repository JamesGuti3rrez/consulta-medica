from __future__ import annotations

import json
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any

from server.cases.rules import check_batch_rules, check_case_rules
from server.cases.validator import validate_case_document
from .medqa_selection import _build_case

REPO_ROOT = Path(__file__).resolve().parents[3]
# Fecha fija del lote: regenerar otro día debe producir exactamente los mismos JSON.
BATCH_DATE = "2026-10-08"
CREATED_BY = "case_preparation.transform.medqa_final_review"
CANDIDATES_PATH = REPO_ROOT / "data" / "interim" / "medqa_candidatos.jsonl"
OUTPUT_DIR = REPO_ROOT / "data" / "cases" / "validated_second_pass"
CURATED_OUTPUT_DIR = REPO_ROOT / "data" / "cases" / "curated"
REJECTED_OUTPUT_DIR = REPO_ROOT / "data" / "cases" / "rejected"
VALIDATED_OUTPUT_DIR = REPO_ROOT / "data" / "cases" / "validated"
FINAL_SELECTION_PATH = REPO_ROOT / "data" / "cases" / "final_selection" / "medqa_final_10.json"
SELECTION_REVIEW_PATH = REPO_ROOT / "data" / "cases" / "reviews" / "second_pass_selection.json"
CLINICAL_REVIEW_PATH = REPO_ROOT / "data" / "cases" / "reviews" / "clinical_coherence_review.json"
LEGACY_CURATION_SUMMARY_PATH = REPO_ROOT / "data" / "cases" / "reviews" / "curation_summary.json"
LEGACY_SELECTION_INDEX_PATH = (
    REPO_ROOT / "data" / "cases" / "validated" / "medqa_selected_cases_index.json"
)
LEGACY_SELECTION_AUDIT_PATH = (
    REPO_ROOT / "data" / "cases" / "reviews" / "legacy_selection_audit.json"
)
CURATION_SUMMARY_PATH = (
    REPO_ROOT / "data" / "cases" / "reviews" / "medqa_second_pass_curation_summary.json"
)
# Datos de curación del lote (selección, traducción, revisión y ajustes de cada caso). Viven en data/,
# no en el código: case_preparation/ no guarda datos de casos (arquitectura del repositorio, §9.3).
CURATION_INPUT_PATH = REPO_ROOT / "data" / "cases" / "reviews" / "medqa_lote_curacion.json"
_CURATION_INPUT = json.loads(CURATION_INPUT_PATH.read_text(encoding="utf-8"))
SELECTED_CASES: list[dict[str, Any]] = _CURATION_INPUT["selected_cases"]
SPANISH_SOURCE_TEXT: dict[str, dict[str, Any]] = _CURATION_INPUT["spanish_source_text"]
CLINICAL_SOURCES: dict[str, dict[str, str]] = _CURATION_INPUT["clinical_sources"]
CLINICAL_REVIEW: dict[str, dict[str, Any]] = _CURATION_INPUT["clinical_review"]
CLINICAL_OVERRIDES: dict[str, dict[str, Any]] = _CURATION_INPUT["clinical_overrides"]
LEGACY_CASES_TO_REJECT: dict[str, str] = _CURATION_INPUT["legacy_cases_to_reject"]
INVALIDATED_LEGACY_CURATIONS: set[str] = set(_CURATION_INPUT["invalidated_legacy_curations"])


def _load_selected_sources(path: Path) -> dict[str, dict[str, Any]]:
    wanted_ids = {case["candidate_id"] for case in SELECTED_CASES}
    selected: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            candidate_id = record.get("candidate_id")
            if candidate_id not in wanted_ids:
                continue

            existing = selected.get(candidate_id)
            if existing is None or len(record.get("options", [])) > len(existing.get("options", [])):
                selected[candidate_id] = record
            elif len(record.get("options", [])) == len(existing.get("options", [])):
                for key in ("question", "options", "answer", "answer_text"):
                    if record.get(key) != existing.get(key):
                        raise ValueError(f"Variantes incompatibles para el registro fuente {candidate_id}.")

    missing = wanted_ids - selected.keys()
    if missing:
        raise FileNotFoundError(f"No se encontraron candidatos fuente seleccionados: {sorted(missing)}")
    return selected


def _validate_case(case: dict[str, Any]) -> None:
    validate_case_document(case)
    errors = check_case_rules(case)
    if errors:
        raise ValueError(f"{case['case_id']} incumple reglas cruzadas: {errors}")


def curate_ai_reviewed_case(case: dict[str, Any], clinical_review: dict[str, Any]) -> dict[str, Any]:
    if not clinical_review.get("assessment") or not clinical_review.get("disposition"):
        raise ValueError(f"Falta una evaluación clínica asistida para {case.get('case_id')}.")

    curated_case = deepcopy(case)
    curated_case["status"] = "curado"
    curated_case["provenance"]["curated_by"] = "curacion_asistida_por_ia"
    curated_case["provenance"]["curated_at"] = BATCH_DATE
    _validate_case(curated_case)
    return curated_case


def _write_ai_curated_cases(case_index: list[dict[str, Any]]) -> None:
    CURATED_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CURATION_SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    index_by_id = {item["case_id"]: item for item in case_index}
    expected_ids = {item["case_id"] for item in SELECTED_CASES}
    if set(index_by_id) != expected_ids:
        raise ValueError("El lote de revisión no coincide con los diez casos seleccionados.")

    curated_records: list[dict[str, Any]] = []
    for case_id in sorted(expected_ids, key=lambda value: int(value.rsplit("-", 1)[1])):
        source_path = OUTPUT_DIR / f"{case_id}.json"
        case = json.loads(source_path.read_text(encoding="utf-8"))
        review = CLINICAL_REVIEW[case_id]
        curated_case = curate_ai_reviewed_case(case, review)
        destination = CURATED_OUTPUT_DIR / source_path.name
        destination.write_text(
            json.dumps(curated_case, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        curated_records.append(
            {
                "case_id": case_id,
                "status": "curado",
                "curated_by": curated_case["provenance"]["curated_by"],
                "disposition": review["disposition"],
                "confidence": review["confidence"],
                "review": review["assessment"],
                "source_review": "clinical_coherence_review.json",
            }
        )

    summary = {
        "dataset": "MedQA",
        "status": "curado_con_revision_asistida_por_ia",
        "method": "curacion_asistida_por_ia",
        "curated_count": len(curated_records),
        "curated_at": BATCH_DATE,
        "source_dir": "data/cases/validated_second_pass",
        "curated_dir": "data/cases/curated",
        "cases": curated_records,
    }
    CURATION_SUMMARY_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _invalidate_legacy_curations() -> None:
    REJECTED_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    review_records: list[dict[str, Any]] = []
    for case_id, reason in LEGACY_CASES_TO_REJECT.items():
        filename = f"{case_id}.json"
        source_path = next(
            (
                directory / filename
                for directory in (VALIDATED_OUTPUT_DIR, CURATED_OUTPUT_DIR, REJECTED_OUTPUT_DIR)
                if (directory / filename).exists()
            ),
            None,
        )
        if source_path is None:
            raise FileNotFoundError(f"No se encontró el caso legado {case_id} para auditarlo.")

        case = json.loads(source_path.read_text(encoding="utf-8"))
        rejected_case = deepcopy(case)
        rejected_case["status"] = "rechazado"
        rejected_case["provenance"]["curated_by"] = None
        rejected_case["provenance"]["curated_at"] = None
        rejected_case["provenance"]["rejection_reason"] = reason
        validate_case_document(rejected_case)
        (REJECTED_OUTPUT_DIR / filename).write_text(
            json.dumps(rejected_case, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        for directory in (VALIDATED_OUTPUT_DIR, CURATED_OUTPUT_DIR):
            stale_path = directory / filename
            if stale_path.exists():
                stale_path.unlink()

        review_path = SELECTION_REVIEW_PATH.parent / filename
        if case_id not in INVALIDATED_LEGACY_CURATIONS and review_path.exists():
            previous_review = json.loads(review_path.read_text(encoding="utf-8"))
            previous_review["accepted"] = False
            previous_review["decision"] = "rechazado_por_reglas_automatizadas"
            previous_review["reason"] = reason
            previous_review["reviewer"] = "auditoria_automatica_de_datos"
            review_path.write_text(
                json.dumps(previous_review, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            review_records.append(previous_review)
            continue

        review_record = {
            "case_id": case_id,
            "reviewed_at": BATCH_DATE,
            "accepted": False,
            "decision": (
                "curacion_anterior_invalidada"
                if case_id in INVALIDATED_LEGACY_CURATIONS
                else "rechazado_por_reglas_automatizadas"
            ),
            "reason": reason,
            "reviewer": "auditoria_automatica_de_datos",
        }
        review_path.write_text(
            json.dumps(review_record, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        review_records.append(review_record)

    invalidated_ids = sorted(INVALIDATED_LEGACY_CURATIONS)
    rejected_ids = sorted(set(LEGACY_CASES_TO_REJECT) - INVALIDATED_LEGACY_CURATIONS)
    LEGACY_CURATION_SUMMARY_PATH.write_text(
        json.dumps(
            {
                "dataset": "MedQA",
                "status": "lote_anterior_rechazado_o_curacion_invalidada",
                "reviewed_count": len(LEGACY_CASES_TO_REJECT),
                "accepted_count": 0,
                "rejected_count": len(LEGACY_CASES_TO_REJECT),
                "invalidated_count": len(invalidated_ids),
                "accepted_case_ids": [],
                "rejected_case_ids": sorted(LEGACY_CASES_TO_REJECT),
                "invalidated_case_ids": invalidated_ids,
                "reason": (
                    "Se retiraron seis curaciones heurísticas por datos demográficos o especialidades sin "
                    "respaldo. Cuatro entradas adicionales son resúmenes de estudios, no casos de pacientes. "
                    "Las diez se conservan en rechazados y no se mezclan con el lote curado actual."
                ),
                "generated_at": BATCH_DATE,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    index_path = next(
        (
            path
            for path in (LEGACY_SELECTION_INDEX_PATH, LEGACY_SELECTION_AUDIT_PATH)
            if path.exists()
        ),
        None,
    )
    if index_path is not None:
        legacy_index = json.loads(index_path.read_text(encoding="utf-8"))
        legacy_index["status"] = "rechazado"
        legacy_index["decision"] = "seleccion_anterior_retirada_por_auditoria"
        legacy_index["rejected_case_ids"] = sorted(LEGACY_CASES_TO_REJECT)
        legacy_index["invalidated_case_ids"] = invalidated_ids
        legacy_index["accepted_count"] = 0
        legacy_index["rejected_count"] = len(LEGACY_CASES_TO_REJECT)
        LEGACY_SELECTION_AUDIT_PATH.write_text(
            json.dumps(legacy_index, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        if index_path != LEGACY_SELECTION_AUDIT_PATH:
            index_path.unlink()


def build_reviewed_cases() -> dict[str, Any]:
    sources = _load_selected_sources(CANDIDATES_PATH)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    FINAL_SELECTION_PATH.parent.mkdir(parents=True, exist_ok=True)
    SELECTION_REVIEW_PATH.parent.mkdir(parents=True, exist_ok=True)

    case_index: list[dict[str, Any]] = []
    built_cases: list[dict[str, Any]] = []
    for position, selection in enumerate(SELECTED_CASES, start=1):
        candidate = dict(sources[selection["candidate_id"]])
        candidate.update({key: value for key, value in selection.items() if key != "rationale"})
        candidate.update(CLINICAL_OVERRIDES[selection["case_id"]])
        translation = SPANISH_SOURCE_TEXT[selection["candidate_id"]]
        if len(translation["options"]) != len(candidate["options"]):
            raise ValueError(f"La traducción de opciones no coincide con la fuente para {selection['case_id']}.")
        candidate["question_translation_es"] = translation["question"]
        candidate["options_translation_es"] = translation["options"]
        case = _build_case(candidate, position)
        case["provenance"].update({"created_by": CREATED_BY, "created_at": BATCH_DATE, "validated_at": BATCH_DATE})
        _validate_case(case)
        built_cases.append(case)
        output_path = OUTPUT_DIR / f"{case['case_id']}.json"
        output_path.write_text(json.dumps(case, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        case_index.append(
            {
                "case_id": case["case_id"],
                "candidate_id": selection["candidate_id"],
                "specialty": case["specialty"],
                "source_answer": candidate["answer"],
                "source_answer_text": candidate["answer_text"],
                "clinical_diagnosis": case["protected"]["diagnosis"]["name"],
                "rationale": selection["rationale"],
                "clinical_review": CLINICAL_REVIEW[selection["case_id"]],
                "schema_valid": True,
            }
        )

    selected_ids = [case["case_id"] for case in case_index]
    suffixes = [int(case_id.rsplit("-", 1)[1]) for case_id in selected_ids]
    if len(set(selected_ids)) != len(selected_ids) or sorted(suffixes) != list(range(1, len(case_index) + 1)):
        raise ValueError("Los IDs del lote deben ser únicos y numerados consecutivamente del 001 al total.")

    case_index.sort(key=lambda case: int(case["case_id"].rsplit("-", 1)[1]))
    batch_errors = check_batch_rules(built_cases)
    if batch_errors:
        raise ValueError(f"El lote incumple reglas cruzadas: {batch_errors}")
    _write_ai_curated_cases(case_index)
    _invalidate_legacy_curations()
    specialty_counts = dict(Counter(case["specialty"] for case in case_index))
    review_counts = dict(Counter(case["clinical_review"]["disposition"] for case in case_index))
    manifest = {
        "dataset": "MedQA",
        "status": "curado_con_revision_asistida_por_ia",
        "selection_criteria": [
            "10 preguntas fuente únicas; selección entre variantes con opciones y clave completas",
            "edad y sexo derivados del texto original, sin valores por defecto",
            "especialidad asignada según el escenario clínico, no palabras incidentales",
            "pregunta, opciones y respuesta originales preservadas en evaluación protegida",
            "hallazgos y respuestas cotejados con la fuente reparada; pruebas y tratamiento contrastados con guías identificadas",
            "tratamiento educativo sujeto a evaluación clínica individual; sin convertirlo en prescripción",
            "figuras y datos no disponibles señalados como limitación, no reconstruidos",
        ],
        "selected_case_ids": [case["case_id"] for case in case_index],
        "specialty_counts": specialty_counts,
        "validation": {
            "schema_ok": True,
            "unique_source_items": len({case["candidate_id"] for case in case_index}),
            "total_validated": len(case_index),
            "source_dir": "data/cases/validated_second_pass",
        },
        "clinical_review": (
            "Lote curado mediante revisión asistida por IA y fuentes identificadas. Cada caso conserva "
            "sus incertidumbres, alertas y necesidades de confirmación. PED-010 se sustituyó por una fuente "
            "pediátrica completa sin imagen faltante."
        ),
        "clinical_review_counts": review_counts,
    }
    FINAL_SELECTION_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    SELECTION_REVIEW_PATH.write_text(
        json.dumps(
            {
                "dataset": "MedQA",
                "status": "ai_assisted_curation_completed",
                "selected_count": len(case_index),
                "specialty_counts": specialty_counts,
                "clinical_review_counts": review_counts,
                "clinical_sources": CLINICAL_SOURCES,
                "cases": case_index,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    CLINICAL_REVIEW_PATH.write_text(
        json.dumps(
            {
                "review_type": "AI-assisted curation and content/source-fidelity review",
                "review_status": "ai_assisted_curation_completed",
                "audit_round": 2,
                "reviewed_at": BATCH_DATE,
                "method": (
                    "Second-pass audit: compare each generated case with the repaired MedQA source, "
                    "answer, and options; verify clinical-summary fidelity, Spanish adaptation, differential "
                    "risk links, diagnostic fit, missing evidence, red flags, tests, and general treatment "
                    "recommendations against the linked references. Original English source text is retained."
                ),
                "educational_use": "curated_for_educational_simulation",
                "case_status_counts": review_counts,
                "clinical_sources": CLINICAL_SOURCES,
                "cases": case_index,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "written": len(case_index),
        "curated": len(case_index),
        "case_ids": [case["case_id"] for case in case_index],
        "specialty_counts": specialty_counts,
        "schema_valid": True,
        "curation_method": "curacion_asistida_por_ia",
    }


if __name__ == "__main__":
    print(json.dumps(build_reviewed_cases(), ensure_ascii=False, indent=2))
