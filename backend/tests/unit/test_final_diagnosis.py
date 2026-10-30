"""TA-012: normalización, coincidencia completa, sinónimos y ambigüedad."""
import json
from pathlib import Path

import pytest

from server.engine.evaluation import ClinicalEvaluationEngine
from server.engine.evaluation.diagnosis import grade_diagnosis, normalize_diagnosis

DIAGNOSIS = {"name": "Migraña sin signos de alarma", "synonyms": ["Migraña", "Cefalea migrañosa"]}


@pytest.mark.parametrize(("value", "expected"), [
    ("  MIGRAÑA   SIN SIGNOS DE ALARMA. ", "migrana sin signos de alarma"),
    ("cefalea\tMIGRAÑOSA", "cefalea migranosa"), ("Mi diagnóstico final es: MIGRAÑA.", "migrana"),
    ("Dx: migraña", "migrana"), ("migran\u0303a", "migrana"), ("Mi diagnóstico: Migraña", "migrana"),
    (None, ""), ("... — ", ""),
])
def test_normalizes_unicode_case_accents_spacing_punctuation_and_prefix(value, expected):
    assert normalize_diagnosis(value) == expected


@pytest.mark.parametrize(("value", "status", "code"), [
    ("Migraña sin signos de alarma", "correct", "reference_match"),
    ("  MIGRAÑA SIN SIGNOS DE ALARMA!!! ", "correct", "reference_match"),
    ("cefalea MIGRAÑOSA", "correct", "synonym_match"),
    ("Mi diagnóstico final es: Migraña.", "correct", "synonym_match"),
    ("Meningitis", "incorrect", "no_match"),
    ("No es migraña", "incorrect", "no_match"),
    ("Migrañ", "incorrect", "no_match"),
    ("migraña sin", "incorrect", "no_match"),
    ("", "empty", "empty_input"), (None, "empty", "empty_input"), ("...", "empty", "empty_input"),
    ("Migraña o meningitis", "ambiguous", "multiple_answers"),
    ("Migraña / meningitis", "ambiguous", "multiple_answers"),
    ("Migraña; cefalea tensional", "ambiguous", "multiple_answers"),
    ("Migraña y meningitis", "ambiguous", "multiple_answers"),
    ("Posible migraña", "ambiguous", "uncertain_answer"),
    ("¿Migraña?", "ambiguous", "uncertain_answer"),
])
def test_grading_matrix(value, status, code):
    result = grade_diagnosis(value, DIAGNOSIS)
    assert result["status"] == status
    assert result["reason_code"] == code
    assert result["score"] == (100 if status == "correct" else 0)
    assert result["max_score"] == 100
    assert result["requires_review"] == (status == "ambiguous")
    assert result["reason"] and result["version"] == "1.0.0"


def test_shared_label_is_not_automatically_accepted():
    result = grade_diagnosis("Migraña", DIAGNOSIS, [{"name": "Migraña"}])
    assert result["status"] == "ambiguous"
    assert result["reason_code"] == "shared_label"
    assert result["score"] == 0


@pytest.mark.parametrize("operation", ["evaluate_diagnosis", "report"])
@pytest.mark.parametrize(("phase", "finished_at"), [("anamnesis", None), ("cierre", None),
    ("finalizada", None), ("diagnostico", "2026-10-28T10:00:00+00:00")])
def test_open_session_is_rejected_before_reading_protected(operation, phase, finished_at):
    class Repository:
        def get_protected(self, case_id):
            pytest.fail("No debe leer protected antes del cierre.")
        def get_conversation_case(self, case_id):
            pytest.fail("No debe construir el reporte antes del cierre.")
    engine = ClinicalEvaluationEngine(Repository())
    session = {"phase": phase, "finished_at": finished_at, "case_id": "MED-900"}
    with pytest.raises(ValueError):
        getattr(engine, operation)(session, []) if operation == "report" else engine.evaluate_diagnosis(session)


CASES = [json.loads(path.read_text(encoding="utf-8")) for path in
         sorted((Path(__file__).resolve().parents[3] / "data/cases/curated").glob("*.json"))]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["case_id"])
def test_all_curated_diagnoses_and_synonyms_are_accepted(case):
    protected = case["protected"]
    for label in [protected["diagnosis"]["name"], *protected["diagnosis"]["synonyms"]]:
        result = grade_diagnosis(label.upper(), protected["diagnosis"], protected["differentials"])
        assert result["status"] == "correct", (case["case_id"], label, result)

