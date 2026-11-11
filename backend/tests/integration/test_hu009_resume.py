from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import server.api.ai as ai_module
from server.ai.llm.gateway import LLMGateway
from server.ai.llm.providers import LocalDevelopmentProvider
from server.auth import SupabaseAuth
from server.main import app
from server.orchestration import InMemorySessionStore
from tests.fakes_supabase import FakeSupabase

CASES = Path(__file__).resolve().parents[1] / "fixtures" / "cases"
client = TestClient(app)
ALICE = "0b8f3c1e-5d4a-4f6b-9a1e-2c3d4e5f6a7b"
BOB = "9f9f9f9f-0000-4000-8000-000000000001"


@pytest.fixture(autouse=True)
def resume_environment(monkeypatch):
    fake = FakeSupabase()
    fake.users.update({"token-alice": ALICE, "token-bob": BOB})
    store = InMemorySessionStore()
    monkeypatch.setattr(ai_module, "CASES_DIR", CASES)
    monkeypatch.setattr(
        ai_module,
        "settings",
        replace(ai_module.settings, session_store="memoria", rag_embedded_enabled=False, rag_service_url=""),
    )
    monkeypatch.setattr(ai_module, "STORE", store)
    monkeypatch.setattr(ai_module, "build_gateway", lambda: LLMGateway([LocalDevelopmentProvider()]))
    monkeypatch.setattr(
        ai_module,
        "get_session_auth",
        lambda: SupabaseAuth("https://proyecto.supabase.co", "sb_publishable_prueba", client=fake.client()),
    )
    ai_module.get_service.cache_clear()
    yield store
    ai_module.get_service.cache_clear()


def _headers(user="alice"):
    return {"Authorization": f"Bearer token-{user}"}


def _start(user="alice"):
    response = client.post(
        "/api/ai/sessions",
        json={"case_id": "MED-900"},
        headers=_headers(user),
    )
    assert response.status_code == 200, response.text
    return response.json()["session_id"]


def test_list_and_restore_are_limited_to_the_owner_and_open_individual_sessions(resume_environment):
    store = resume_environment
    own_session = _start()
    group_session = _start()
    finished_session = _start()
    another_session = _start("bob")

    group_state = store.get(group_session)
    group_state["group_assignment_id"] = "actividad-1"
    store.save(group_state)
    finished_state = store.get(finished_session)
    finished_state["phase"] = "finalizada"
    store.save(finished_state)

    response = client.get("/api/ai/sessions", headers=_headers())
    assert response.status_code == 200, response.text
    assert [item["session_id"] for item in response.json()["sessions"]] == [own_session]
    assert "case_id" not in response.json()["sessions"][0]

    denied = client.get(
        f"/api/ai/sessions/{another_session}/restore",
        headers=_headers(),
    )
    assert denied.status_code == 404


def test_another_student_cannot_overwrite_the_saved_hypotheses(resume_environment):
    session_id = _start("alice")
    mine = [{"name": "Migraña", "discarded": False, "reason": ""}]
    assert client.patch(f"/api/ai/sessions/{session_id}/progress",
                        json={"hypotheses": mine}, headers=_headers("alice")).status_code == 200

    denied = client.patch(
        f"/api/ai/sessions/{session_id}/progress",
        json={"hypotheses": [{"name": "Hipótesis ajena", "discarded": False, "reason": ""}]},
        headers=_headers("bob"),
    )

    assert denied.status_code == 404
    assert resume_environment.get(session_id)["student_hypotheses"] == mine


def test_restore_includes_turns_revealed_evidence_and_saved_hypotheses():
    session_id = _start()
    message = client.post(
        f"/api/ai/sessions/{session_id}/message",
        json={"message": "¿Desde cuándo comenzó el dolor?"},
        headers=_headers(),
    )
    assert message.status_code == 200, message.text

    hypotheses = [{"name": "Migraña", "discarded": False, "reason": ""}]
    saved = client.patch(
        f"/api/ai/sessions/{session_id}/progress",
        json={"hypotheses": hypotheses},
        headers=_headers(),
    )
    assert saved.status_code == 200, saved.text

    restored = client.get(
        f"/api/ai/sessions/{session_id}/restore",
        headers=_headers(),
    )
    assert restored.status_code == 200, restored.text
    body = restored.json()
    assert body["session"]["session_id"] == session_id
    assert "protected" not in body["case"]
    assert body["hypotheses"] == hypotheses
    assert any(event.get("type") == "turn" for event in body["events"])
    assert "MED-900.anamnesis.inicio_dolor" in {
        evidence["evidence_id"] for evidence in body["evidences"]
    }


def test_finalized_session_cannot_be_restored_or_updated(resume_environment):
    store = resume_environment
    session_id = _start()
    state = store.get(session_id)
    state["phase"] = "finalizada"
    store.save(state)

    restored = client.get(
        f"/api/ai/sessions/{session_id}/restore",
        headers=_headers(),
    )
    progress = client.patch(
        f"/api/ai/sessions/{session_id}/progress",
        json={"hypotheses": []},
        headers=_headers(),
    )
    assert restored.status_code == 409
    assert progress.status_code == 409
