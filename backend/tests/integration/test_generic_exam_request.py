"""Pedido genérico al laboratorio o a radiología: se pregunta qué examen, no se afirma que no existe."""

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

import server.api.ai as ai_module
from server.ai.agents.laboratorio import LaboratorioAgent
from server.ai.agents.radiologia import RadiologiaAgent
from server.ai.llm.gateway import LLMGateway
from server.ai.llm.providers import LocalDevelopmentProvider
from server.api.ai import STORE, get_service
from server.cases.catalog import CURATED_CASES_DIR
from server.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def curated_cases(monkeypatch):
    monkeypatch.setattr(ai_module, "CASES_DIR", CURATED_CASES_DIR)
    monkeypatch.setattr(ai_module, "settings", replace(ai_module.settings, rag_embedded_enabled=False, rag_service_url=""))
    monkeypatch.setattr(ai_module, "build_gateway", lambda: LLMGateway([LocalDevelopmentProvider()]))
    STORE.clear()
    get_service.cache_clear()
    yield
    get_service.cache_clear()


def _ask(case_id: str, message: str) -> dict:
    sid = client.post("/api/ai/sessions", json={"case_id": case_id}).json()["session_id"]
    response = client.post(f"/api/ai/sessions/{sid}/message", json={"message": message})
    assert response.status_code == 200, response.text
    return response.json()


def test_generic_lab_request_asks_which_exam_instead_of_denying_it():
    reply = _ask("CIR-005", "¿Qué resultados tienen los análisis de sangre de antes de la operación?")
    assert reply["agent"] == "laboratorio"
    assert reply["evidence_ids"] == []
    assert reply["response"] == LaboratorioAgent.generic_request_reply


def test_generic_imaging_request_asks_which_study():
    reply = _ask("EME-002", "Quiero un estudio de imagen")
    assert reply["agent"] == "radiologia"
    assert reply["response"] == RadiologiaAgent.generic_request_reply


def test_named_exam_still_returns_its_result_or_says_it_was_not_done():
    found = _ask("CIR-005", "Solicito pruebas de coagulación")
    assert "CIR-005.lab.coagulacion_preoperatoria" in found["evidence_ids"]
    missing = _ask("CIR-005", "Pido un hemograma")
    assert missing["evidence_ids"] == []
    assert missing["response"] != LaboratorioAgent.generic_request_reply
