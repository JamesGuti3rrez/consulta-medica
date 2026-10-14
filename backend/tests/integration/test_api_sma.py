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


@pytest.fixture(autouse=True)
def fixture_cases(monkeypatch):
    monkeypatch.setattr(ai_module, "CASES_DIR", FIXTURES)
    # El caso de prueba no está en el índice de LightRAG: la evidencia se lee del caso, sin depender
    # de si en el equipo hay un índice construido.
    monkeypatch.setattr(ai_module, "settings", replace(ai_module.settings, rag_embedded_enabled=False, rag_service_url=""))
    # Sin LLM real aunque el .env tenga claves: la prueba no gasta cuota y su resultado no varía.
    monkeypatch.setattr(ai_module, "build_gateway", lambda: LLMGateway([LocalDevelopmentProvider()]))
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
    assert start.json()["avatar_state"]["vitals"]
    assert start.json()["avatar_state"]["complications"] == []

    patient = _send(sid, "¿Desde cuándo comenzó el dolor y cómo lo describiría?")
    assert patient["agent"] == "paciente"
    assert patient["evidence_ids"] == ["MED-900.anamnesis.inicio_dolor"]
    # Al paciente le habla el médico tratante con la pregunta reformulada.
    assert patient["doctor_question"]

    ordered = _send(sid, "Pregúntale si tiene alergias")
    assert ordered["agent"] == "paciente"
    assert ordered["doctor_question"] == "¿Tiene alergias?"
    assert ordered["evidence_ids"] == ["MED-900.anamnesis.alergias"]

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
        "paciente", "paciente", "laboratorio", "radiologia", "especialista", "medico_asistente"
    ]
    assert all("evidence_ids" in turn for turn in turns)

    state = client.get(f"/api/ai/sessions/{sid}").json()
    assert "MED-900.laboratorio.hemograma" in state["revealed_evidence_ids"]
    assert "MED-900.imagen.tomografia_craneo" in state["revealed_evidence_ids"]

    finish = client.post(f"/api/ai/sessions/{sid}/finish")
    assert finish.status_code == 200
    assert finish.json()["phase"] == "finalizada"
    assert finish.json()["evaluation"]["total_questions"] > 0
    assert finish.json()["avatar_state"]["complications"] == []


def test_session_survives_across_instances_with_supabase_store(monkeypatch):
    """En Vercel cada petición puede llegar a otra instancia: con SESSION_STORE=supabase la sesión sigue."""
    from server.orchestration import SupabaseSessionStore
    from tests.fakes_supabase import FakeSupabase

    fake = FakeSupabase()

    def new_instance():
        monkeypatch.setattr(ai_module, "STORE", SupabaseSessionStore("https://proyecto.supabase.co", "sb_secret_prueba", client=fake.client()))
        get_service.cache_clear()

    new_instance()
    start = client.post("/api/ai/sessions", json={"case_id": "MED-900"})
    assert start.status_code == 200, start.text
    sid = start.json()["session_id"]

    new_instance()
    reply = _send(sid, "Pregúntele cuándo empezó el dolor")
    assert reply["evidence_ids"] == ["MED-900.anamnesis.inicio_dolor"]

    new_instance()
    assert client.post(f"/api/ai/sessions/{sid}/finish").status_code == 200
    types = [event["type"] for event in client.get(f"/api/ai/sessions/{sid}/events").json()]
    assert types == ["session_started", "turn", "session_finished"]
    assert fake.sessions[sid]["phase"] == "finalizada"


def test_store_failure_returns_503(monkeypatch):
    from server.orchestration import SupabaseSessionStore
    from tests.fakes_supabase import FakeSupabase

    fake = FakeSupabase()
    fake.fail_with = 500
    monkeypatch.setattr(ai_module, "STORE", SupabaseSessionStore("https://proyecto.supabase.co", "sb_secret_prueba", client=fake.client()))
    get_service.cache_clear()
    response = client.post("/api/ai/sessions", json={"case_id": "MED-900"})
    assert response.status_code == 503
    assert "supabase" not in response.text.lower()


def test_llm_unavailable_returns_503_with_clear_message(monkeypatch):
    from server.ai.llm.providers import ProviderError

    class Rejected:
        name = "groq-1"
        model = "m"

        def generate(self, messages, *, temperature=0.0):
            raise ProviderError("groq-1: HTTP 401: Invalid API Key", invalid_credential=True)

    monkeypatch.setattr(ai_module, "build_gateway", lambda: LLMGateway([Rejected()]))
    get_service.cache_clear()
    sid = client.post("/api/ai/sessions", json={"case_id": "MED-900"}).json()["session_id"]
    response = client.post(f"/api/ai/sessions/{sid}/message", json={"message": "¿Desde cuándo comenzó el dolor?"})
    assert response.status_code == 503
    assert "no puede responder" in response.json()["detail"]
    assert "Invalid API Key" not in response.text
