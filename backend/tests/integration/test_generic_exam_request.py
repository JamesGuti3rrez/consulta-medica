"""Pedido genérico al laboratorio o a radiología: se pregunta qué examen, no se afirma que no existe."""

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

import server.api.ai as ai_module
from server.ai.agents.laboratorio import LaboratorioAgent
from server.ai.agents.radiologia import RadiologiaAgent
from server.ai.agents.medico_asistente import MedicoAsistenteAgent
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
    start = client.post("/api/ai/sessions", json={"case_id": case_id}).json()
    # Consulta de invitado: se continúa con su credencial de capacidad (TA-011).
    response = client.post(f"/api/ai/sessions/{start['session_id']}/message", json={"message": message},
                           headers={"X-Session-Token": start["session_token"]})
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


def test_physical_exam_from_screenshot_reads_existing_case_findings(monkeypatch):
    class NoSynthesis:
        def complete(self, **kwargs):
            pytest.fail("Los resultados existentes no deben pasar por la generación del paciente")
    service = get_service()
    service.graph.patient_completion = NoSynthesis()
    reply = _ask("MED-008", "bueno pasemos con los exámenes físicos que tiene que tomar el paciente para empezar a ver cómo está actualmente")
    assert reply["agent"] == "medico_asistente"
    assert reply["intent"] == "examine"
    assert "MED-008.examen.exploracion_fisica" in reply["evidence_ids"]
    assert "párpado" in reply["response"] and "0,5" in reply["response"]
    assert reply["data_source"] == "curado" and not reply["blocked"]
    assert reply["synthetic_generated_ids"] == []
    assert reply["doctor_question"] is None
    assert "losartán" not in reply["response"].lower()


def test_generic_medical_exams_do_not_return_synthetic_medication():
    reply = _ask("MED-008", "pasamos por los exámenes médicos")
    assert reply["agent"] == "medico_asistente"
    assert reply["response"] == MedicoAsistenteAgent.generic_request_reply
    assert reply["provider"] == "reglas"
    assert reply["evidence_ids"] == [] and reply["synthetic_generated_ids"] == []
    assert reply["doctor_question"] is None


def test_physical_evaluation_synonym_reveals_curated_exam():
    reply = _ask("MED-008", "Realizo una evaluación física")
    assert reply["agent"] == "medico_asistente"
    assert reply["evidence_ids"] == ["MED-008.examen.exploracion_fisica"]
