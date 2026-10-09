from __future__ import annotations

from typing import Any
from app.routing import normalize

REQUIRED_SECTIONS = [
    "case_id",
    "initial_presentation",
    "patient_knowledge",
    "laboratory_data",
    "radiology_data",
    "specialist_data",
    "protected_evaluation",
]


def validate_progressive_case(case: dict[str, Any]) -> dict[str, Any]:
    missing_sections = [k for k in REQUIRED_SECTIONS if k not in case]
    protected = case.get("protected_evaluation", {})
    terms = [protected.get("diagnosis", "")]
    terms += protected.get("diagnosis_synonyms", [])
    terms += protected.get("protected_terms", [])

    initial_text = normalize(str(case.get("initial_presentation", {})))
    exposed_terms = [str(t) for t in terms if str(t).strip() and normalize(str(t)) in initial_text]

    revealable_fact_count = 0
    evidence_ids: set[str] = set()
    duplicate_evidence_ids: list[str] = []

    def walk(obj: Any):
        nonlocal revealable_fact_count
        if isinstance(obj, dict):
            if "evidence_id" in obj and "value" in obj:
                revealable_fact_count += 1
                eid = str(obj["evidence_id"])
                if eid in evidence_ids:
                    duplicate_evidence_ids.append(eid)
                evidence_ids.add(eid)
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)

    for section in ["initial_presentation", "patient_knowledge", "laboratory_data", "radiology_data", "specialist_data"]:
        walk(case.get(section, {}))

    valid = not missing_sections and not exposed_terms and not duplicate_evidence_ids and revealable_fact_count > 0
    return {
        "case_id": case.get("case_id", "UNKNOWN"),
        "valid": valid,
        "missing_sections": missing_sections,
        "initial_answer_exposed": bool(exposed_terms),
        "exposed_terms": exposed_terms,
        "duplicate_evidence_ids": duplicate_evidence_ids,
        "revealable_fact_count": revealable_fact_count,
    }
