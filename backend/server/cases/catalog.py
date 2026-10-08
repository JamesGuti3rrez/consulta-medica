"""Carga de casos curados desde el catálogo JSON versionado."""

import json
from pathlib import Path
from typing import Any

from .validator import validate_case_document

CURATED_CASES_DIR = Path(__file__).resolve().parents[3] / "data" / "cases" / "curated"


def load_curated_cases(directory: Path | str = CURATED_CASES_DIR) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for case_path in sorted(Path(directory).glob("*.json")):
        with case_path.open("r", encoding="utf-8") as handle:
            case = json.load(handle)
        if not isinstance(case, dict):
            raise ValueError(f"El archivo de caso debe contener un objeto JSON: {case_path}")
        validate_case_document(case)
        if case["status"] == "curado":
            cases.append(case)
    return cases


def to_student_case(case: dict[str, Any]) -> dict[str, Any]:
    public = case["public"]
    student_case = {
        "case_id": case["case_id"],
        "specialty": case["specialty"],
        "patient": {
            "alias": public["patient"]["alias"],
            "age_years": public["patient"]["age_years"],
            "sex": public["patient"]["sex"],
        },
        "chief_complaint": {
            "label": public["chief_complaint"]["label"],
            "text": public["chief_complaint"]["text"],
        },
        "items": [
            {
                "label": item["label"],
                "text": item["text"],
            }
            for item in public["items"]
        ],
        "allergies_recorded": public["allergies_recorded"],
    }
    if public["allergies_recorded"]:
        student_case["allergies"] = public["allergies"]
    return student_case
