from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from server.cases.catalog import load_curated_cases
from server.cases.rules import check_batch_rules, check_case_rules

CASES_DIR = Path(__file__).resolve().parents[2] / "data" / "cases"


def _load(folder: str, case_id: str) -> dict:
    return json.loads((CASES_DIR / folder / f"{case_id}.json").read_text(encoding="utf-8"))


def _codes(case: dict) -> set[str]:
    return {error.split(" ", 1)[0] for error in check_case_rules(case)}


@pytest.fixture
def case() -> dict:
    return _load("curated", "MED-008")


def test_all_curated_cases_pass_rules():
    cases = [json.loads(path.read_text(encoding="utf-8")) for path in sorted((CASES_DIR / "curated").glob("*.json"))]
    assert len(cases) == 10
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
    case["protected"]["evaluation"]["key_questions"][0]["evidence_ids"] = ["MED-008.historia.no_existe"]
    assert "R03" in _codes(case)


def test_r04_diagnosis_not_visible(case):
    case["title"] = f"Caso de {case['protected']['diagnosis']['name']}"
    assert "R04" in _codes(case)


def test_r05_allergies_consistent(case):
    case["public"]["allergies"] = []
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
    (tmp_path / "MED-008.json").write_text(json.dumps(case, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="R01"):
        load_curated_cases(tmp_path)
