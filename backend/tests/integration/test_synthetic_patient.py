import json
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

import server.api.ai as ai
from server.cases import CanonicalCaseRepository
from server.ai.agents.history_composer import HistoryComposer
from server.ai.llm.base import LLMResult
from server.ai.llm.providers import LocalDevelopmentProvider
from server.guardrails import OutputGuard
from server.main import app
from server.orchestration.patient_completion import PatientHistoryCompletion


class Store:
    def __init__(self):
        self.rows = {}

    def list_for_case(self, case_id):
        return list(self.rows.values())

    def insert_missing(self, rows):
        for row in rows:
            self.rows.setdefault(row["clave"], {"id": row["clave"], **row})


class Gateway:
    def __init__(self):
        self.calls = []

    def generate(self, messages, *, temperature):
        self.calls.append(messages)
        try:
            payload = json.loads(messages[-1]["content"])
        except ValueError:
            payload = {}
        phase = payload.get("fase")
        if phase == "seleccionar":
            keys = (["impacto_vida_diaria"] if "impacto_vida_diaria" in payload.get("claves_permitidas", [])
                    else ["medicacion_habitual", "inicio_antecedentes"])
            data = {"alcance": "caso", "claves": keys}
        elif phase == "generar":
            if payload.get("claves_solicitadas") == ["impacto_vida_diaria"]:
                assert any("pápula" in item.get("text", "")
                           for item in payload["contexto"]["revealed_evidence"])
                data = {"datos": [{"clave": "impacto_vida_diaria",
                                    "respuesta": "Sigo haciendo mis actividades habituales sin dificultad."}]}
            else:
                data = {"datos": [
                {"clave": "medicacion_habitual", "respuesta": "Tomo losartán para la hipertensión."},
                {"clave": "inicio_antecedentes", "respuesta": "Me diagnosticaron la hipertensión en 2016."},
                ]}
        elif phase == "validar":
            data = {"coherente": True, "dentro_alcance": True,
                    "sin_cambios_clinicos": True, "responde_pregunta": True}
        else:
            if "CONTEXTO AUTORIZADO:\n" in messages[-1]["content"]:
                return LocalDevelopmentProvider().generate(messages, temperature=temperature)
            return LLMResult("¿Qué toma para la hipertensión y en qué año se la diagnosticaron?", "fake", "fake")
        return LLMResult(json.dumps(data, ensure_ascii=False), "fake", "fake", 10, 5)


@pytest.fixture
def scenario(monkeypatch):
    gateway, facts = Gateway(), Store()
    monkeypatch.setattr(ai, "settings", replace(ai.settings, case_store="local", synthetic_case_data=False,
                                               rag_embedded_enabled=False, rag_service_url=""))
    monkeypatch.setattr(ai, "build_gateway", lambda: gateway)
    monkeypatch.setattr(ai, "build_case_repository", lambda *a, **kw: CanonicalCaseRepository())
    ai.STORE.clear()
    ai.get_service.cache_clear()
    service = ai.get_service()
    service.graph.patient_completion = PatientHistoryCompletion(HistoryComposer(gateway), facts, OutputGuard())
    yield TestClient(app), service, facts, gateway
    ai.STORE.clear()
    ai.get_service.cache_clear()


def test_two_sessions_get_identical_saved_history_and_trace_its_origin(scenario):
    client, service, facts, gateway = scenario
    replies = []
    for question in [
        "¿Qué está tomando para controlar su hipertensión y en qué año le dio esta enfermedad?",
        "¿Qué medicamentos toma y en qué año le diagnosticaron la hipertensión?",
    ]:
        start = client.post("/api/ai/sessions", json={"case_id": "MED-008"})
        assert start.status_code == 200
        sid = start.json()["session_id"]
        response = client.post(f"/api/ai/sessions/{sid}/message", json={"message": question},
                               headers={"X-Session-Token": start.json()["session_token"]})
        assert response.status_code == 200, response.text
        reply = response.json()
        assert reply["data_source"] == "sintetico"
        assert reply["evidence_ids"] == []
        assert "losartán" in reply["response"] and "2016" in reply["response"]
        event = service.store.events(sid)[-1]
        assert event["student_message"] == question
        assert event["response_text"] == reply["response"]
        assert event["data_source"] == "sintetico"
        replies.append(reply)
    assert replies[0]["response"] == replies[1]["response"]
    assert len(replies[0]["synthetic_generated_ids"]) == 2
    assert replies[1]["synthetic_reused_ids"] == replies[0]["synthetic_generated_ids"]
    assert not replies[1]["synthetic_generated_ids"]
    assert len(facts.rows) == 2


def test_math_is_rejected_before_reformulation_without_changing_phase(scenario):
    client, service, facts, gateway = scenario
    start = client.post("/api/ai/sessions", json={"case_id": "MED-008"}).json()
    response = client.post(f"/api/ai/sessions/{start['session_id']}/message", json={"message": "¿Cuánto es 2+2?"},
                           headers={"X-Session-Token": start["session_token"]})
    assert response.status_code == 200
    body = response.json()
    assert body["blocked"] is True
    assert body["data_source"] == "fuera_de_alcance"
    assert body["session"]["phase"] == start["phase"]
    assert "mi salud" in body["response"]
    assert not facts.rows and not gateway.calls


def test_casual_comment_is_not_echoed_as_a_medical_question(scenario):
    client, service, facts, gateway = scenario
    start = client.post("/api/ai/sessions", json={"case_id": "MED-008"}).json()
    response = client.post(f"/api/ai/sessions/{start['session_id']}/message",
                           json={"message": "pero general López chistoso"},
                           headers={"X-Session-Token": start["session_token"]})
    assert response.status_code == 200
    body = response.json()
    assert body["data_source"] == "conversacional" and not body["blocked"]
    assert "repetir" in body["response"] and body["doctor_question"] is None
    assert not facts.rows and not gateway.calls


def test_exam_then_functional_impact_keeps_the_revealed_finding(scenario):
    client, service, facts, gateway = scenario
    start = client.post("/api/ai/sessions", json={"case_id": "MED-008"}).json()
    sid, headers = start["session_id"], {"X-Session-Token": start["session_token"]}
    exam = client.post(f"/api/ai/sessions/{sid}/message", json={"message": "un examen de exploración física"},
                       headers=headers)
    assert exam.status_code == 200
    assert "párpado" in exam.json()["response"]
    question = "es esa pápula la ha dado inconvenientes al momento de realizar las actividades diarias"
    response = client.post(f"/api/ai/sessions/{sid}/message", json={"message": question}, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["agent"] == "paciente" and not body["blocked"]
    assert body["response"] == "Sigo haciendo mis actividades habituales sin dificultad."
    assert body["data_source"] == "sintetico" and len(body["synthetic_generated_ids"]) == 1
    assert "impacto_vida_diaria" in facts.rows
    assert "MED-008.anamnesis.exposicion_solar" not in body["session"]["revealed_evidence_ids"]
