from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import server.api.ai as ai_module
from server.api.ai import STORE, get_service
from server.main import app

client = TestClient(app)


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "cases"


@pytest.fixture(autouse=True)
def fixture_cases(monkeypatch):
    monkeypatch.setattr(ai_module, "CASES_DIR", FIXTURES)
    # El caso de prueba no está en el índice de LightRAG: la evidencia se lee del caso, sin depender
    # de si en el equipo hay un índice construido.
    monkeypatch.setattr(ai_module, "settings", replace(ai_module.settings, rag_embedded_enabled=False, rag_service_url=""))
    STORE.clear()
    get_service.cache_clear()
    yield
    get_service.cache_clear()


def _send(sid: str, message: str):
    response = client.post(f"/api/ai/sessions/{sid}/message", json={"message": message})
    assert response.status_code == 200, response.text
    return response.json()


def test_five_agents_in_one_star_session_with_traceable_evidence():
    status = client.get("/api/ai/status")
    assert status.status_code == 200
    assert status.json()["topology"] == "star"
    assert status.json()["disclosure_policy"] == "reveal-policy-minimum-privilege"

    start = client.post("/api/ai/sessions", json={"case_id": "MED-900"})
    assert start.status_code == 200
    sid = start.json()["session_id"]

    patient = _send(sid, "¿Desde cuándo comenzó el dolor y cómo lo describiría?")
    assert patient["agent"] == "paciente"
    assert patient["evidence_ids"] == ["MED-900.anamnesis.inicio_dolor"]

    lab = _send(sid, "Solicito un hemograma y análisis de sangre")
    assert lab["agent"] == "laboratorio"
    assert lab["evidence_ids"] == ["MED-900.laboratorio.hemograma"]

    radiology = _send(sid, "Solicito una tomografía cerebral")
    assert radiology["agent"] == "radiologia"
    assert radiology["evidence_ids"] == ["MED-900.imagen.tomografia_craneo"]

    specialist = _send(sid, "Solicito interconsulta con neurología")
    assert specialist["agent"] == "especialista"
    assert specialist["evidence_ids"] == ["MED-900.estudio.interconsulta_neurologia"]

    assistant = _send(sid, "Dame un resumen de lo que sabemos del caso")
    assert assistant["agent"] == "medico_asistente"

    events = client.get(f"/api/ai/sessions/{sid}/events")
    assert events.status_code == 200
    turns = [event for event in events.json() if event.get("type") == "turn"]
    assert [turn["agent"] for turn in turns] == [
        "paciente", "laboratorio", "radiologia", "especialista", "medico_asistente"
    ]
    assert all("evidence_ids" in turn for turn in turns)

    state = client.get(f"/api/ai/sessions/{sid}").json()
    assert "MED-900.laboratorio.hemograma" in state["revealed_evidence_ids"]
    assert "MED-900.imagen.tomografia_craneo" in state["revealed_evidence_ids"]

    finish = client.post(f"/api/ai/sessions/{sid}/finish")
    assert finish.status_code == 200
    assert finish.json()["phase"] == "finalizada"
