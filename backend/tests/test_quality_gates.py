from __future__ import annotations

import json
from pathlib import Path

from case_preparation.quality_gates import evaluate_batch, evaluate_case

CASES_DIR = Path(__file__).resolve().parents[2] / "data" / "cases"


def _load(folder: str, case_id: str) -> dict:
    return json.loads((CASES_DIR / folder / f"{case_id}.json").read_text(encoding="utf-8"))


def test_accepts_curated_case_and_reports_warnings():
    case = _load("curated", "GOB-004")
    result = evaluate_case(case)
    assert result.accepted
    assert result.errors == [] and result.warnings == []
    case["public"]["items"][0]["text"] = "Exploración: cérvix en fresa."
    result = evaluate_case(case)
    assert result.accepted
    assert result.warnings and result.warnings[0].startswith("W01")


def test_rejects_case_that_breaks_the_schema():
    case = _load("curated", "MED-007")
    del case["protected"]["diagnosis"]
    result = evaluate_case(case)
    assert not result.accepted
    assert result.errors[0].startswith("ESQUEMA protected")


def test_rejects_case_that_breaks_cross_rules():
    result = evaluate_case(_load("rejected", "CIR-007"))
    assert not result.accepted
    assert any(error.startswith("R12") for error in result.errors)


def test_batch_rejects_repeated_source_question():
    case = _load("curated", "MED-007")
    assert evaluate_batch([case, dict(case, case_id="MED-011")]) == [
        "R09 MED-011 reutiliza la pregunta fuente de MED-007"
    ]
