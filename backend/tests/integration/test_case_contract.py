from pathlib import Path

import pytest

from server.cases import CanonicalCaseRepository, CaseValidationError
from server.cases import CaseNotAvailable

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "cases"


def test_canonical_case_is_curated_and_schema_valid():
    repo = CanonicalCaseRepository(FIXTURES)
    case = repo.get_case("MED-900")
    assert case["status"] == "curado"
    assert set(["public", "on_request", "protected"]).issubset(case)
    conversation = repo.get_conversation_case("MED-900")
    assert "protected" not in conversation


def test_repository_serves_the_curated_catalog_without_protected():
    repo = CanonicalCaseRepository()
    case_ids = repo.list_curated()
    assert len(case_ids) == 13
    for case_id in case_ids:
        assert "protected" not in repo.get_conversation_case(case_id)


def test_repository_refuses_case_that_breaks_cross_rules(tmp_path):
    source = (FIXTURES / "MED-900.json").read_text(encoding="utf-8")
    (tmp_path / "MED-900.json").write_text(source.replace('"medicina_interna"', '"pediatria"'), encoding="utf-8")
    with pytest.raises(CaseValidationError):
        CanonicalCaseRepository(tmp_path).get_case("MED-900")


def test_validated_cases_require_explicit_repository_opt_in():
    validated = Path(__file__).resolve().parents[3] / "data" / "cases" / "validated"
    with pytest.raises(CaseNotAvailable):
        CanonicalCaseRepository(validated).get_case("CIR-005")

    repository = CanonicalCaseRepository(validated, accepted_statuses=("validado",))
    assert repository.get_case("CIR-005")["status"] == "validado"
    assert len(repository.list_curated()) == 10


def test_repository_rejects_unapproved_statuses():
    with pytest.raises(ValueError, match="Estados de caso no permitidos"):
        CanonicalCaseRepository(accepted_statuses=("borrador",))
