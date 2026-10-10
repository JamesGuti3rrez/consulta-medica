from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server.cases import CanonicalCaseRepository, CaseNotFound
from server.main import app

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "cases"
OUTSIDE = ["../../backend/tests/fixtures/cases/MED-900", "../validated/EME-001", "EME-001/../EME-002", "eme-001", ""]


@pytest.mark.parametrize("case_id", OUTSIDE)
def test_repository_rejects_case_ids_that_are_not_plain_ids(case_id):
    with pytest.raises(CaseNotFound):
        CanonicalCaseRepository().get_case(case_id)


def test_sessions_cannot_load_a_case_outside_the_catalog():
    response = TestClient(app).post("/api/ai/sessions", json={"case_id": "../../backend/tests/fixtures/cases/MED-900"})
    assert response.status_code == 404


def test_plain_ids_still_load():
    assert CanonicalCaseRepository(FIXTURES).get_case("MED-900")["case_id"] == "MED-900"
