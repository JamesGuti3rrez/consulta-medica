import json
from typing import Any

ROLE_KEYS = {
    "patient": ["initial_presentation", "patient"],
    "assistant": ["initial_presentation", "patient"],
    "laboratory": ["laboratory"],
    "radiologist": ["radiology"],
    "specialist": ["initial_presentation", "patient", "specialist"],
}

def _collect_evidence_ids(obj: Any) -> list[str]:
    ids: list[str] = []
    if isinstance(obj, dict):
        if "evidence_id" in obj:
            ids.append(str(obj["evidence_id"]))
        for v in obj.values():
            ids.extend(_collect_evidence_ids(v))
    elif isinstance(obj, list):
        for v in obj:
            ids.extend(_collect_evidence_ids(v))
    return ids

def build_minimal_context(case: dict, role: str) -> tuple[str, list[str]]:
    view = {k: case[k] for k in ROLE_KEYS.get(role, []) if k in case}
    return json.dumps(view, ensure_ascii=False), _collect_evidence_ids(view)

def build_shared_context(case: dict, role: str) -> tuple[str, list[str]]:
    return json.dumps(case, ensure_ascii=False), _collect_evidence_ids(case)

def authorized_evidence_for_role(case: dict, role: str) -> set[str]:
    _, ids = build_minimal_context(case, role)
    return set(ids)

def protected_terms(case: dict) -> list[str]:
    p = case["protected_evaluation"]
    return [p["diagnosis"], *p.get("synonyms", [])]
