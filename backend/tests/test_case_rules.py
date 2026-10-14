from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from server.cases.catalog import load_curated_cases, to_student_case
from server.cases.rules import check_batch_rules, check_case_rules, check_case_warnings

CASES_DIR = Path(__file__).resolve().parents[2] / "data" / "cases"


def _load(folder: str, case_id: str) -> dict:
    return json.loads((CASES_DIR / folder / f"{case_id}.json").read_text(encoding="utf-8"))


def _codes(case: dict) -> set[str]:
    return {error.split(" ", 1)[0] for error in check_case_rules(case)}


@pytest.fixture
def case() -> dict:
    return _load("curated", "MED-007")


def test_all_curated_cases_pass_rules():
    cases = [json.loads(path.read_text(encoding="utf-8")) for path in sorted((CASES_DIR / "curated").glob("*.json"))]
    assert sum(case["source"]["dataset"] == "MedQA" for case in cases) == 10
    assert sum(case["source"]["dataset"] == "sintetico" for case in cases) == 3
    assert {case["case_id"]: check_case_rules(case) for case in cases} == {case["case_id"]: [] for case in cases}
    assert check_batch_rules(cases) == []


def test_rules_catch_the_defect_that_rejected_ped_003():
    assert "R06" in _codes(_load("rejected", "PED-003"))


def test_r01_prefix_must_match_specialty(case):
    case["specialty"] = "emergencias"
    assert "R01" in _codes(case)


def test_r02_evidence_ids_unique_and_own(case):
    case["public"]["items"].append(deepcopy(case["public"]["items"][0]))
    assert "R02" in _codes(case)
    other = deepcopy(case)
    other["public"]["items"] = [dict(other["public"]["items"][0], evidence_id="CIR-005.historia.otro")]
    assert "R02" in _codes(other)


def test_r03_key_questions_cite_existing_evidence(case):
    case["protected"]["evaluation"]["key_questions"][0]["evidence_ids"] = ["MED-007.historia.no_existe"]
    assert "R03" in _codes(case)


def test_r03_differentials_cite_existing_evidence(case):
    case["protected"]["differentials"][0]["discard_evidence_ids"] = ["MED-007.historia.no_existe"]
    assert "R03" in _codes(case)


def test_curated_differentials_cite_the_data_that_discards_them():
    # Decisión 0002: todos los diferenciales de los casos curados tienen un dato que los descarta.
    for path in sorted((CASES_DIR / "curated").glob("*.json")):
        case = json.loads(path.read_text(encoding="utf-8"))
        without = [item["name"] for item in case["protected"]["differentials"] if not item["discard_evidence_ids"]]
        assert without == [], (case["case_id"], without)


def test_r15_applies_to_every_curated_case_not_only_synthetic(case):
    # Un caso de MedQA curado con un diferencial que nada descarta no llega a un solo diagnóstico.
    assert case["source"]["dataset"] == "MedQA" and case["status"] == "curado"
    case["protected"]["differentials"][0]["discard_evidence_ids"] = []
    assert "R15" in _codes(case)
    # Un caso aún no curado puede tener diferenciales pendientes de completar.
    case["status"] = "validado"
    case["provenance"].update({"curated_by": None, "curated_at": None})
    assert "R15" not in _codes(case)


def test_r04_diagnosis_not_visible(case):
    case["title"] = f"Caso de {case['protected']['diagnosis']['name']}"
    assert "R04" in _codes(case)


def test_r05_allergies_consistent(case):
    case["public"]["allergies_recorded"] = True
    case["public"].pop("allergies", None)
    assert "R05" in _codes(case)


def test_r06_age_and_sex_match_specialty(case):
    case["public"]["patient"]["age_years"] = 12
    assert "R06" in _codes(case)
    gyn = _load("curated", "GOB-003")
    gyn["public"]["patient"]["sex"] = "masculino"
    assert "R06" in _codes(gyn)


def test_r07_provenance_matches_status(case):
    case["provenance"]["curated_at"] = None
    assert "R07" in _codes(case)


def test_r08_license_matches_source(case):
    case["source"]["license"] = "CC-BY-4.0"
    assert "R08" in _codes(case)


def test_r09_r10_batch_rules(case):
    duplicate = deepcopy(case)
    codes = {error.split(" ", 1)[0] for error in check_batch_rules([case, duplicate])}
    assert codes == {"R09", "R10"}


def test_catalog_refuses_case_that_breaks_rules(tmp_path, case):
    case["specialty"] = "emergencias"
    (tmp_path / "MED-007.json").write_text(json.dumps(case, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="R01"):
        load_curated_cases(tmp_path)


def test_r11_differentials_must_stay_in_protected(case):
    differential = case["protected"]["differentials"][0]["name"]
    case["public"]["items"][0]["text"] += f" Se sospecha {differential}."
    assert "R11" in _codes(case)


def test_r12_rejects_multiple_choice_leftovers(case):
    case["public"]["items"][0]["text"] += " ¿Cuál de los siguientes es el tratamiento?"
    assert "R12" in _codes(case)


def test_r13_rejects_figures_not_in_source(case):
    case["public"]["items"][0]["text"] += " Glucosa de 999 mg/dL."
    assert "R13" in _codes(case)


def test_r13_accepts_source_figures_written_in_words_or_without_leading_zero():
    gyn = _load("curated", "GOB-003")  # la fuente dice «Thirty minutes»; el caso, «30 minutos»
    eyelid = _load("curated", "MED-008")  # la fuente dice «.5cm»; el caso, «0,5 cm»
    assert "R13" not in _codes(gyn)
    assert "R13" not in _codes(eyelid)


def test_w01_warns_about_exam_in_public_without_blocking():
    surgical = _load("curated", "CIR-006")
    assert check_case_warnings(surgical) == []
    surgical["public"]["items"][0]["text"] += " Tiene crepitantes en la base pulmonar derecha."
    assert check_case_rules(surgical) == []
    assert [warning.split(" ", 1)[0] for warning in check_case_warnings(surgical)] == ["W01"]


def test_r14_mode_must_match_owner(case):
    exam = next(item for item in case["on_request"] if item["reveal_policy"]["owner"] == "medico_asistente")
    exam["reveal_policy"]["mode"] = "al_preguntar"
    assert "R14" in _codes(case)


def test_r14_patient_and_assistant_use_agreed_topics(case):
    patient = next(item for item in case["on_request"] if item["reveal_policy"]["owner"] == "paciente")
    patient["reveal_policy"]["requires"] = ["tema_inventado"]
    assert "R14" in _codes(case)


def test_curated_cases_reveal_history_on_request():
    for path in sorted((CASES_DIR / "curated").glob("*.json")):
        case = json.loads(path.read_text(encoding="utf-8"))
        assert case["on_request"], case["case_id"]
        assert all("ya están incluidos en la historia pública" not in item.get("text", "") for item in case["on_request"])
        assert len(case["protected"]["evaluation"]["key_questions"]) >= 2, case["case_id"]


def test_items_with_value_and_unit_instead_of_text(case):
    case["public"]["items"].append({
        "evidence_id": "MED-007.vital.frecuencia_cardiaca",
        "category": "signo_vital",
        "label": "Frecuencia cardiaca",
        "value": 74,
        "unit": "/min",
    })
    assert check_case_warnings(case) == check_case_warnings(_load("curated", "MED-007"))
    assert to_student_case(case)["items"][-1] == {"label": "Frecuencia cardiaca", "text": "74 /min"}


def test_curated_diagnoses_have_synonyms_to_grade_the_written_diagnosis():
    # Para comparar el diagnóstico que escribe el estudiante, cada caso acepta varias formas de nombrarlo.
    for path in sorted((CASES_DIR / "curated").glob("*.json")):
        case = json.loads(path.read_text(encoding="utf-8"))
        synonyms = case["protected"]["diagnosis"]["synonyms"]
        assert len(set(synonyms)) >= 3, (case["case_id"], synonyms)
