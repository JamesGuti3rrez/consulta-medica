from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def load_case(case_id: str) -> dict[str, Any]:
    path = ROOT / "data" / "cases" / f"{case_id}.json"
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_all_cases() -> list[dict[str, Any]]:
    cases = []
    for path in sorted((ROOT / "data" / "cases").glob("*.json")):
        with path.open("r", encoding="utf-8") as f:
            cases.append(json.load(f))
    return cases


def load_questions(name: str) -> list[dict[str, Any]]:
    path = ROOT / "data" / "questions" / f"{name}.json"
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def evidence_catalog(case: dict[str, Any]) -> dict[str, dict[str, Any]]:
    catalog: dict[str, dict[str, Any]] = {}
    for section_name in ["initial_presentation", "patient_knowledge", "laboratory_data", "radiology_data", "specialist_data"]:
        section = case.get(section_name, {})
        for item in _walk_facts(section):
            eid = item.get("evidence_id")
            if eid:
                catalog[eid] = item
    return catalog


def _walk_facts(obj: Any):
    if isinstance(obj, dict):
        if "evidence_id" in obj and "value" in obj:
            yield obj
        for v in obj.values():
            yield from _walk_facts(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_facts(v)
