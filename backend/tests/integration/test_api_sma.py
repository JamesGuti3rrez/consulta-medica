from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import server.api.ai as ai_module
from server.ai.llm.gateway import LLMGateway
from server.ai.llm.providers import LocalDevelopmentProvider
from server.api.ai import STORE, get_service
from server.auth import SupabaseAuth
from server.main import app

client = TestClient(app)
# Contrato de cierre de HU-006: diagnóstico obligatorio y confirmación del alumno.
FINISH_BODY = {"diagnosis": "Migraña sin signos de alarma", "confirmado": True}


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "cases"


@pytest.fixture(autouse=True)
def fixture_cases(monkeypatch):
    monkeypatch.setattr(ai_module, "CASES_DIR", FIXTURES)
    # El caso de prueba no está en el índice de LightRAG: la evidencia se lee del caso, sin depender
    # de si en el equipo hay un índice construido.
    monkeypatch.setattr(ai_module, "settings", replace(ai_module.settings, rag_embedded_enabled=False, rag_service_url=""))
    # Sin LLM real aunque el .env tenga claves: la prueba no gasta cuota y su resultado no varía.
    monkeypatch.setattr(ai_module, "build_gateway", lambda: LLMGateway([LocalDevelopmentProvider()]))
    # Sin Supabase Auth salvo en las pruebas que lo simulan: ninguna prueba sale a la red.
    monkeypatch.setattr(ai_module, "get_session_auth", lambda: None)
    STORE.clear()
    get_service.cache_clear()
    yield
    get_service.cache_clear()


def _creds(start, **headers) -> dict:
    """Credencial para continuar la consulta (TA-011): la de capacidad del invitado y el token del alumno."""
    token = start.json().get("session_token")
    return {**headers, **({"X-Session-Token": token} if token else {})}


def _auth(monkeypatch, fake) -> None:
    monkeypatch.setattr(ai_module, "get_session_auth",
                        lambda: SupabaseAuth("https://proyecto.supabase.co", "sb_publishable_prueba", client=fake.client()))


def _send(sid: str, message: str, headers: dict):
    response = client.post(f"/api/ai/sessions/{sid}/message", json={"message": message}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_five_agents_in_one_star_session_with_traceable_evidence():
    status = client.get("/api/ai/status")
    assert status.status_code == 200
    assert status.json()["topology"] == "star"
    assert status.json()["disclosure_policy"] == "reveal-policy-minimum-privilege"

    start = client.post("/api/ai/sessions", json={"case_id": "MED-900"})
    assert start.status_code == 200
    sid, creds = start.json()["session_id"], _creds(start)
    assert start.json()["avatar_state"]["vitals"]
    assert start.json()["avatar_state"]["complications"] == []

    patient = _send(sid, "¿Desde cuándo comenzó el dolor y cómo lo describiría?", creds)
    assert patient["agent"] == "paciente"
    assert patient["evidence_ids"] == ["MED-900.anamnesis.inicio_dolor"]
    # Al paciente le habla el médico tratante con la pregunta reformulada.
    assert patient["doctor_question"]

    ordered = _send(sid, "Pregúntale si tiene alergias", creds)
    assert ordered["agent"] == "paciente"
    assert ordered["doctor_question"] == "¿Tiene alergias?"
    assert ordered["evidence_ids"] == ["MED-900.anamnesis.alergias"]

    lab = _send(sid, "Solicito un hemograma y análisis de sangre", creds)
    assert lab["agent"] == "laboratorio"
    assert lab["evidence_ids"] == ["MED-900.laboratorio.hemograma"]

    radiology = _send(sid, "Solicito una tomografía cerebral", creds)
    assert radiology["agent"] == "radiologia"
    assert radiology["evidence_ids"] == ["MED-900.imagen.tomografia_craneo"]

    specialist = _send(sid, "Solicito interconsulta con neurología", creds)
    assert specialist["agent"] == "especialista"
    assert specialist["evidence_ids"] == ["MED-900.estudio.interconsulta_neurologia"]

    assistant = _send(sid, "Dame un resumen de lo que sabemos del caso", creds)
    assert assistant["agent"] == "medico_asistente"

    events = client.get(f"/api/ai/sessions/{sid}/events", headers=creds)
    assert events.status_code == 200
    turns = [event for event in events.json() if event.get("type") == "turn"]
    assert [turn["agent"] for turn in turns] == [
        "paciente", "paciente", "laboratorio", "radiologia", "especialista", "medico_asistente"
    ]
    assert all("evidence_ids" in turn for turn in turns)

    state = client.get(f"/api/ai/sessions/{sid}", headers=creds).json()
    assert "MED-900.laboratorio.hemograma" in state["revealed_evidence_ids"]
    assert "MED-900.imagen.tomografia_craneo" in state["revealed_evidence_ids"]

    finish = client.post(f"/api/ai/sessions/{sid}/finish", json=FINISH_BODY, headers=creds)
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
    sid, creds = start.json()["session_id"], _creds(start)

    new_instance()
    reply = _send(sid, "Pregúntele cuándo empezó el dolor", creds)
    assert reply["evidence_ids"] == ["MED-900.anamnesis.inicio_dolor"]

    new_instance()
    assert client.post(f"/api/ai/sessions/{sid}/finish", json=FINISH_BODY, headers=creds).status_code == 200
    types = [event["type"] for event in client.get(f"/api/ai/sessions/{sid}/events", headers=creds).json()]
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
    start = client.post("/api/ai/sessions", json={"case_id": "MED-900"})
    response = client.post(f"/api/ai/sessions/{start.json()['session_id']}/message",
                           json={"message": "¿Desde cuándo comenzó el dolor?"}, headers=_creds(start))
    assert response.status_code == 503
    assert "no puede responder" in response.json()["detail"]
    assert "Invalid API Key" not in response.text


def _finished_session(monkeypatch, fake, start_token=None, **kwargs):
    from server.persistence import SupabaseAttempts

    attempts = SupabaseAttempts("https://proyecto.supabase.co", "sb_publishable_prueba", "sb_secret_prueba",
                                client=fake.client())
    monkeypatch.setattr(ai_module, "get_attempts", lambda: attempts)
    _auth(monkeypatch, fake)
    headers = {"Authorization": f"Bearer {start_token}"} if start_token else {}
    start = client.post("/api/ai/sessions", json={"case_id": "MED-900"}, headers=headers)
    sid = start.json()["session_id"]
    _send(sid, "¿Tiene alergias a algún medicamento?", _creds(start, **headers))
    finish_headers = {**_creds(start), **kwargs.pop("headers", {})}
    kwargs.setdefault("json", FINISH_BODY)
    return sid, client.post(f"/api/ai/sessions/{sid}/finish", headers=finish_headers, **kwargs)


def test_finish_saves_the_attempt_only_for_a_signed_in_student(monkeypatch):
    from tests.fakes_supabase import FakeSupabase

    fake = FakeSupabase()
    fake.users["token-alumno"] = "0b8f3c1e-5d4a-4f6b-9a1e-2c3d4e5f6a7b"
    body = {"diagnosis": "Diagnóstico del alumno", "hypotheses": [{"name": "Hipótesis A", "discarded": False}],
            "confirmado": True}
    sid, finish = _finished_session(monkeypatch, fake, start_token="token-alumno", json=body,
                                    headers={"Authorization": "Bearer token-alumno"})

    assert finish.status_code == 200
    assert finish.json()["attempt"] == {"saved": True, "id": "intento-1"}
    row = fake.attempts[0]
    assert row["usuario_id"] == "0b8f3c1e-5d4a-4f6b-9a1e-2c3d4e5f6a7b"
    assert row["caso_id"] == "MED-900"
    assert row["especialidad"] == "medicina_interna"
    assert row["puntaje"] == round(finish.json()["evaluation"]["score"])
    assert row["diagnostico"] == "Diagnóstico del alumno"
    assert row["hipotesis"] == [{"name": "Hipótesis A", "discarded": False, "reason": ""}]

    # Cerrar otra vez no duplica el intento.
    again = client.post(f"/api/ai/sessions/{sid}/finish", json=body, headers={"Authorization": "Bearer token-alumno"})
    assert again.json()["attempt"] == {"saved": True, "id": "intento-1"}
    assert len(fake.attempts) == 1


def test_finish_without_session_or_with_a_forged_token_saves_nothing(monkeypatch):
    from tests.fakes_supabase import FakeSupabase

    fake = FakeSupabase()
    _, guest = _finished_session(monkeypatch, fake)
    assert guest.status_code == 200
    assert guest.json()["evaluation"]["total_questions"] > 0
    assert guest.json()["attempt"] == {"saved": False, "reason": "sin_sesion"}

    fake.users["token-alumno"] = "0b8f3c1e-5d4a-4f6b-9a1e-2c3d4e5f6a7b"
    _, forged = _finished_session(monkeypatch, fake, start_token="token-alumno",
                                  headers={"Authorization": "Bearer token-inventado"})
    # TA-011: un token que Supabase rechaza no puede operar sobre la consulta (antes: 200 sin guardar).
    assert forged.status_code == 401
    assert "evaluation" not in forged.json()
    assert fake.attempts == []


def test_finish_still_returns_the_evaluation_if_supabase_fails(monkeypatch):
    from tests.fakes_supabase import FakeSupabase

    fake = FakeSupabase()
    fake.users["token-alumno"] = "0b8f3c1e-5d4a-4f6b-9a1e-2c3d4e5f6a7b"

    # Supabase cae después de iniciar la consulta: al cerrarla no se puede guardar.
    from server.persistence import SupabaseAttempts

    attempts = SupabaseAttempts("https://proyecto.supabase.co", "sb_publishable_prueba", "sb_secret_prueba",
                                client=fake.client())
    monkeypatch.setattr(ai_module, "get_attempts", lambda: attempts)
    auth_fake = FakeSupabase()
    auth_fake.users["token-alumno"] = "0b8f3c1e-5d4a-4f6b-9a1e-2c3d4e5f6a7b"
    _auth(monkeypatch, auth_fake)
    sid = client.post("/api/ai/sessions", json={"case_id": "MED-900"},
                      headers={"Authorization": "Bearer token-alumno"}).json()["session_id"]
    fake.fail_with = 500
    finish = client.post(f"/api/ai/sessions/{sid}/finish", json=FINISH_BODY, headers={"Authorization": "Bearer token-alumno"})
    assert finish.status_code == 200
    assert finish.json()["evaluation"]["total_questions"] > 0
    assert finish.json()["attempt"] == {"saved": False, "reason": "error"}


def test_only_the_student_who_started_the_consultation_can_save_it(monkeypatch):
    from tests.fakes_supabase import FakeSupabase

    fake = FakeSupabase()
    fake.users["token-alumno"] = "0b8f3c1e-5d4a-4f6b-9a1e-2c3d4e5f6a7b"
    fake.users["token-otro"] = "9f9f9f9f-0000-4000-8000-000000000001"

    # Otro alumno con el id de la consulta no puede quedarse con el resultado.
    _, stolen = _finished_session(monkeypatch, fake, start_token="token-alumno",
                                  headers={"Authorization": "Bearer token-otro"})
    # TA-011: la consulta ajena responde 404, como si no existiera (antes: 200 sin guardar).
    assert stolen.status_code == 404
    assert "evaluation" not in stolen.json()

    # Una consulta empezada sin sesión no se guarda aunque se cierre con sesión.
    _, guest_started = _finished_session(monkeypatch, fake, headers={"Authorization": "Bearer token-alumno"})
    assert guest_started.json()["attempt"] == {"saved": False, "reason": "iniciada_sin_sesion"}
    assert fake.attempts == []
    # El dueño no sale en la respuesta pública de la sesión.
    assert "owner_id" not in stolen.json()


def test_without_history_a_signed_in_student_finishes_without_saving_or_warnings(monkeypatch):
    # HISTORIAL_ALUMNOS=false: no se escribe en Supabase y la hoja no muestra aviso. El token del alumno sí
    # se verifica: es lo que le da acceso a su consulta (TA-011).
    from tests.fakes_supabase import FakeSupabase

    monkeypatch.setattr(ai_module, "settings", replace(ai_module.settings, history_enabled=False))
    ai_module.get_attempts.cache_clear()
    fake = FakeSupabase()
    fake.users["token-alumno"] = "0b8f3c1e-5d4a-4f6b-9a1e-2c3d4e5f6a7b"
    _auth(monkeypatch, fake)
    headers = {"Authorization": "Bearer token-alumno"}
    sid = client.post("/api/ai/sessions", json={"case_id": "MED-900"}, headers=headers).json()["session_id"]
    _send(sid, "¿Tiene alergias a algún medicamento?", headers)
    finish = client.post(f"/api/ai/sessions/{sid}/finish", json=FINISH_BODY, headers=headers)
    ai_module.get_attempts.cache_clear()

    assert finish.status_code == 200
    assert finish.json()["attempt"] == {"saved": False, "reason": "desactivado"}
    assert finish.json()["evaluation"]
