"""TA-012: calificación HTTP, persistencia JSONB simulada y aislamiento de sesiones."""
import copy
import json
import os
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import server.api.ai as ai
from server.ai.llm.gateway import LLMGateway
from server.ai.llm.providers import LocalDevelopmentProvider
from server.auth import SupabaseAuth
from server.main import app
from server.orchestration import InMemorySessionStore, SupabaseSessionStore
from server.persistence import SupabaseAttempts
from tests.fakes_supabase import FakeSupabase

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures/cases"
REFERENCE = "Migraña sin signos de alarma"
USER = "0b8f3c1e-5d4a-4f6b-9a1e-2c3d4e5f6a7b"
HEADERS = {"Authorization": "Bearer token-alumno"}


@pytest.fixture
def context(monkeypatch):
    data, auth = FakeSupabase(), FakeSupabase()
    data.users["token-alumno"] = auth.users["token-alumno"] = USER
    auth.users["token-otro"] = "0b8f3c1e-5d4a-4f6b-9a1e-2c3d4e5f6a7c"
    monkeypatch.setattr(ai, "CASES_DIR", FIXTURES)
    monkeypatch.setattr(ai, "settings", replace(ai.settings, case_store="local", rag_backend="local",
        rag_embedded_enabled=False, rag_service_url="", history_enabled=True))
    monkeypatch.setattr(ai, "STORE", InMemorySessionStore())
    monkeypatch.setattr(ai, "build_gateway", lambda: LLMGateway([LocalDevelopmentProvider()]))
    monkeypatch.setattr(ai, "get_session_auth", lambda: SupabaseAuth("https://test.supabase.co", "public", client=auth.client()))
    monkeypatch.setattr(ai, "get_attempts", lambda: SupabaseAttempts("https://test.supabase.co", "public", "secret", client=data.client()))
    ai.get_service.cache_clear()
    yield TestClient(app), data
    ai.get_service.cache_clear()


def start(client, signed=False):
    response = client.post("/api/ai/sessions", json={"case_id": "MED-900"}, headers=HEADERS if signed else {})
    assert response.status_code == 200, response.text
    body = response.json()
    return body["session_id"], HEADERS if signed else {"X-Session-Token": body["session_token"]}


MATRIX = [
    ("correcto", REFERENCE, "correct", 100, "reference_match"),
    ("incorrecto", "Meningitis", "incorrect", 0, "no_match"),
    ("sinonimo", "  CEFALEA MIGRAÑOSA. ", "correct", 100, "synonym_match"),
    ("vacio", "", "empty", 0, "empty_input"),
    ("ambiguo", "Migraña o meningitis", "ambiguous", 0, "multiple_answers"),
]


@pytest.mark.parametrize(("name", "value", "status", "score", "code"), MATRIX, ids=[r[0] for r in MATRIX])
def test_finish_grades_and_persists_each_acceptance_case(context, name, value, status, score, code):
    client, data = context
    sid, headers = start(client, signed=True)
    response = client.post(f"/api/ai/sessions/{sid}/finish", json={"diagnosis": value}, headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    grade = body["diagnosis_evaluation"]
    assert (grade["status"], grade["score"], grade["reason_code"]) == (status, score, code)
    assert body["report"]["diagnosis"]["grading"] == grade
    assert body["phase"] == "finalizada"
    assert ai.STORE.get(sid)["diagnosis_evaluation"] == grade
    assert data.attempts[0]["reporte"]["diagnosis_evaluation"] == grade
    assert data.attempts[0]["diagnostico"] == (value or None)
    assert data.attempts[0]["puntaje"] == round(body["evaluation"]["score"])
    assert client.get(f"/api/ai/sessions/{sid}/report", headers=headers).json() == body["report"]
    if folder := os.getenv("TA012_EVIDENCIA"):
        path = Path(folder); path.mkdir(parents=True, exist_ok=True)
        (path / f"{name}.json").write_text(json.dumps({
            "criterio": name, "entrada": value, "http_status": response.status_code,
            "phase": body["phase"], "resultado": grade, "persistido_en_sesion": True,
            "persistido_en_intentos": True, "reporte_coincidente": True,
        }, ensure_ascii=False, indent=2), encoding="utf-8")


@pytest.mark.parametrize("payload", [None, {}, {"diagnosis": None}, {"diagnosis": "  \t"}])
def test_finish_accepts_missing_null_or_blank_diagnosis(context, payload):
    client, _ = context
    sid, headers = start(client)
    kwargs = {"json": payload} if payload is not None else {}
    response = client.post(f"/api/ai/sessions/{sid}/finish", headers=headers, **kwargs)
    assert response.status_code == 200
    assert response.json()["diagnosis_evaluation"]["status"] == "empty"
    assert response.json()["diagnosis_evaluation"]["score"] == 0


def test_no_grading_or_reference_leaks_before_finish(context, monkeypatch):
    client, _ = context
    sid, headers = start(client)
    service = ai.get_service()
    calls = []
    original = service.evaluation_engine.evaluate_diagnosis
    def grade(session):
        calls.append(session["phase"])
        return original(session)
    monkeypatch.setattr(service.evaluation_engine, "evaluate_diagnosis", grade)
    turn = client.post(f"/api/ai/sessions/{sid}/message", headers=headers,
                       json={"message": "Mi diagnóstico es cefalea migrañosa"})
    assert turn.status_code == 200
    responses = [client.get(f"/api/ai/sessions/{sid}", headers=headers),
                 client.get(f"/api/ai/sessions/{sid}/events", headers=headers), turn]
    assert client.get(f"/api/ai/sessions/{sid}/report", headers=headers).status_code == 409
    for response in responses:
        for forbidden in ("diagnosis_evaluation", "normalized_input", "matched_term", '"synonyms"', REFERENCE):
            assert forbidden not in response.text
    assert calls == []
    finished = client.post(f"/api/ai/sessions/{sid}/finish", headers=headers, json={"diagnosis": "Migraña"})
    assert finished.status_code == 200
    assert calls == ["finalizada"]
    client.get(f"/api/ai/sessions/{sid}/report", headers=headers)
    assert calls == ["finalizada"]


def test_repeated_finish_cannot_change_grade_or_create_another_attempt(context):
    client, data = context
    sid, headers = start(client, signed=True)
    first = client.post(f"/api/ai/sessions/{sid}/finish", headers=headers, json={"diagnosis": "Migraña"}).json()
    second = client.post(f"/api/ai/sessions/{sid}/finish", headers=headers, json={"diagnosis": "Meningitis"}).json()
    assert second["diagnosis_evaluation"] == first["diagnosis_evaluation"]
    assert second["report"] == first["report"]
    assert len(data.attempts) == 1
    assert len([event for event in ai.STORE.events(sid) if event["type"] == "session_finished"]) == 1


def test_retry_after_failed_attempt_save_uses_original_submission(context):
    client, data = context
    sid, headers = start(client, signed=True)
    data.fail_with = 500
    first = client.post(f"/api/ai/sessions/{sid}/finish", headers=headers, json={
        "diagnosis": "Migraña", "hypotheses": [{"name": "Original", "discarded": False}]}).json()
    assert first["attempt"] == {"saved": False, "reason": "error"}
    data.fail_with = None
    second = client.post(f"/api/ai/sessions/{sid}/finish", headers=headers, json={
        "diagnosis": "Meningitis", "hypotheses": [{"name": "Modificada", "discarded": False}]}).json()
    assert second["attempt"]["saved"] is True
    assert data.attempts[0]["diagnostico"] == "Migraña"
    assert data.attempts[0]["hipotesis"][0]["name"] == "Original"
    assert data.attempts[0]["reporte"]["diagnosis_evaluation"]["score"] == 100


def test_grade_is_persisted_through_supabase_store_and_read_by_new_service(context, monkeypatch):
    client, data = context
    monkeypatch.setattr(ai, "STORE", SupabaseSessionStore("https://test.supabase.co", "secret", client=data.client()))
    ai.get_service.cache_clear()
    sid, headers = start(client)
    response = client.post(f"/api/ai/sessions/{sid}/finish", headers=headers, json={"diagnosis": "Migraña"})
    assert response.status_code == 200
    grade = response.json()["diagnosis_evaluation"]
    assert data.sessions[sid]["state"]["diagnosis_evaluation"] == grade
    assert data.events[-1]["payload"]["diagnosis_evaluation"] == grade
    ai.get_service.cache_clear()  # Otro proceso lee la misma sesión persistida.
    assert client.get(f"/api/ai/sessions/{sid}", headers=headers).json()["diagnosis_evaluation"] == grade
    assert client.get(f"/api/ai/sessions/{sid}/report", headers=headers).json()["diagnosis"]["grading"] == grade


def test_other_user_and_guest_cannot_get_finished_grade(context):
    client, _ = context
    sid, headers = start(client, signed=True)
    client.post(f"/api/ai/sessions/{sid}/finish", headers=headers, json={"diagnosis": "Migraña"})
    _, guest_headers = start(client)
    for wrong_headers in ({}, {"Authorization": "Bearer token-otro"}, guest_headers):
        for endpoint in ("", "/report", "/events"):
            response = client.get(f"/api/ai/sessions/{sid}{endpoint}", headers=wrong_headers)
            assert response.status_code in (401, 404)
            assert "diagnosis_evaluation" not in response.text and REFERENCE not in response.text


def test_public_session_filter_hides_accidental_grade_before_close(context):
    client, _ = context
    sid, headers = start(client)
    state = ai.STORE.get(sid)
    state["diagnosis_evaluation"] = {"score": 100, "matched_term": REFERENCE}
    ai.STORE.save(state)
    assert "diagnosis_evaluation" not in client.get(f"/api/ai/sessions/{sid}", headers=headers).json()


def test_client_cannot_supply_its_own_score_or_reference(context):
    client, _ = context
    sid, headers = start(client)
    response = client.post(f"/api/ai/sessions/{sid}/finish", headers=headers, json={
        "diagnosis": "Meningitis", "diagnosis_evaluation": {"score": 100},
        "reference": "Meningitis", "synonyms": ["Meningitis"]})
    assert response.status_code == 200
    assert response.json()["diagnosis_evaluation"]["score"] == 0
    assert response.json()["report"]["diagnosis"]["reference"] == REFERENCE

