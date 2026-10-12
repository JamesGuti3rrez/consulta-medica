from fastapi.testclient import TestClient

from server import api
from server.main import app


client = TestClient(app)


def test_status_reports_curated_catalog_without_claiming_full_simulation_ready():
    response = client.get("/api/status")

    assert response.status_code == 200
    body = response.json()
    assert {key: body[key] for key in ("caseConfigured", "simulationReady", "availableCases")} == {
        "caseConfigured": True,
        "simulationReady": False,
        "availableCases": 13,  # 10 de MedQA y 3 de la familia sintética de dolor torácico
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


def test_case_endpoint_filters_by_specialty():
    for _ in range(10):
        response = client.get("/api/caso", params={"especialidad": "pediatria"})
        assert response.status_code == 200
        assert response.json()["specialty"] == "pediatria"


def test_case_endpoint_rejects_unknown_specialty():
    response = client.get("/api/caso", params={"especialidad": "cardiologia"})
    assert response.status_code == 422


def test_status_reports_cases_by_specialty():
    counts = client.get("/api/status").json()["casesBySpecialty"]
    assert counts == {
        "medicina_interna": 2,
        "pediatria": 2,
        "ginecologia_obstetricia": 2,
        "cirugia_general": 2,
        "emergencias": 5,  # EME-001, EME-002 y la familia EME-101 a EME-103
    }
