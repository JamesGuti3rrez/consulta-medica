from fastapi.testclient import TestClient

from server import api
from server.main import app


client = TestClient(app)


def test_status_reports_curated_catalog_without_claiming_full_simulation_ready():
    response = client.get("/api/status")

    assert response.status_code == 200
    assert response.json() == {
        "caseConfigured": True,
        "simulationReady": False,
        "availableCases": 10,
    }


def test_case_endpoint_returns_only_student_facing_fields():
    response = client.get("/api/caso")

    assert response.status_code == 200
    case = response.json()
    assert case["case_id"]
    expected_keys = {
        "case_id",
        "specialty",
        "patient",
        "chief_complaint",
        "items",
        "allergies_recorded",
    }
    if case["allergies_recorded"]:
        expected_keys.add("allergies")
        assert case["allergies"]
    assert set(case) == expected_keys
    assert set(case["patient"]) == {"alias", "age_years", "sex"}
    assert all(set(item) == {"label", "text"} for item in case["items"])
    assert "protected" not in case
    assert "on_request" not in case
    assert "diagnosis" not in str(case).lower()


def test_case_endpoint_reports_unavailable_when_catalog_is_empty(monkeypatch):
    monkeypatch.setattr(api.routes, "load_curated_cases", lambda: [])

    response = client.get("/api/caso")

    assert response.status_code == 503
    assert response.json()["detail"] == "No hay casos curados disponibles."
