"""HU-006: GET /api/ai/sessions/{id}/report, solo para el dueño y solo después del cierre."""
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import server.api.ai as ai_module
from server.ai.llm.gateway import LLMGateway
from server.ai.llm.providers import LocalDevelopmentProvider
from server.api.ai import STORE, get_service
from server.main import app

client = TestClient(app)
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "cases"
NOT_FINISHED = {"detail": "El reporte estará disponible al terminar la consulta."}


@pytest.fixture(autouse=True)
def fixture_cases(monkeypatch):
    monkeypatch.setattr(ai_module, "CASES_DIR", FIXTURES)
    monkeypatch.setattr(ai_module, "settings", replace(ai_module.settings, rag_embedded_enabled=False, rag_service_url=""))
    monkeypatch.setattr(ai_module, "build_gateway", lambda: LLMGateway([LocalDevelopmentProvider()]))
    monkeypatch.setattr(ai_module, "get_session_auth", lambda: None)
    STORE.clear()
    get_service.cache_clear()
    yield
    get_service.cache_clear()


def _guest():
    start = client.post("/api/ai/sessions", json={"case_id": "MED-900"})
    assert start.status_code == 200, start.text
    return start.json()["session_id"], {"X-Session-Token": start.json()["session_token"]}


def _finish(sid, headers, diagnosis="Migraña", hypotheses=None):
    body = {"diagnosis": diagnosis, "hypotheses": hypotheses or [{"name": "Migraña", "discarded": False, "reason": ""}]}
    response = client.post(f"/api/ai/sessions/{sid}/finish", json=body, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_reporte_solo_tras_cerrar():
    sid, headers = _guest()
    before = client.get(f"/api/ai/sessions/{sid}/report", headers=headers)
    assert before.status_code == 409
    assert before.json() == NOT_FINISHED
    _finish(sid, headers)
    after = client.get(f"/api/ai/sessions/{sid}/report", headers=headers)
    assert after.status_code == 200
    assert after.json()["case_id"] == "MED-900"
    assert after.json()["diagnosis"]["reference"] == "Migraña sin signos de alarma"


def test_finish_devuelve_el_mismo_reporte():
    sid, headers = _guest()
    client.post(f"/api/ai/sessions/{sid}/message", json={"message": "¿Es alérgico a algún medicamento?"}, headers=headers)
    finished = _finish(sid, headers)
    assert finished["report"] == client.get(f"/api/ai/sessions/{sid}/report", headers=headers).json()
    assert "student_diagnosis" not in finished and "student_hypotheses" not in finished


def test_cerrar_dos_veces_no_cambia_la_propuesta():
    sid, headers = _guest()
    _finish(sid, headers, diagnosis="Primera")
    second = _finish(sid, headers, diagnosis="Segunda", hypotheses=[{"name": "Otra", "discarded": True, "reason": "x"}])
    assert second["report"]["diagnosis"]["student"] == "Primera"
    assert second["report"]["hypotheses"] == [{"name": "Migraña", "discarded": False, "reason": ""}]


def test_reporte_de_consulta_sin_propuesta_guardada():
    sid, headers = _guest()
    _finish(sid, headers)
    state = STORE.get(sid)
    state.pop("student_diagnosis")
    state.pop("student_hypotheses")
    STORE.save(state)
    response = client.get(f"/api/ai/sessions/{sid}/report", headers=headers)
    assert response.status_code == 200
    assert response.json()["diagnosis"]["student"] == ""
    assert response.json()["hypotheses"] == []


def test_reporte_ajeno_e_inexistente():
    sid, headers = _guest()
    _finish(sid, headers)
    other_sid, other_headers = _guest()
    ajeno = client.get(f"/api/ai/sessions/{sid}/report", headers=other_headers)
    inexistente = client.get("/api/ai/sessions/00000000-0000-4000-8000-000000000000/report", headers=other_headers)
    assert ajeno.status_code == 404
    assert (inexistente.status_code, inexistente.text) == (ajeno.status_code, ajeno.text)
    assert client.get(f"/api/ai/sessions/{sid}/report").status_code == 401
