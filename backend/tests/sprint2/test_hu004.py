"""HU-004: roles, resultados existentes/ausentes y datos progresivos sin duplicados."""
from pathlib import Path

import pytest

from server.cases.repository import CanonicalCaseRepository
from server.rag.retriever import CaseEvidenceRetriever
from .conftest import start, ask

TASK = "HU-004"
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures/cases"


@pytest.mark.parametrize("question,role,ending", [
    ("Solicito un hemograma", "laboratorio", "laboratorio.hemograma"),
    ("Solicito una tomografía cerebral", "radiologia", "imagen.tomografia_craneo"),
    ("Solicito interconsulta con neurología", "especialista", "estudio.interconsulta_neurologia"),
])
def test_existing_exam_uses_correct_role_and_case_evidence(api, question, role, ending):
    client, service, _ = api
    service.repository = service.graph.repository = CanonicalCaseRepository(FIXTURES)
    service.graph.retriever = CaseEvidenceRetriever(service.repository)
    service.graph.protected_lexicon.repository = service.repository
    sid, headers = start(client, "MED-900")
    reply = ask(client, sid, headers, question)
    assert reply["agent"] == role and reply["evidence_ids"] == ["MED-900." + ending]
    assert reply["clinical_evidence"][0]["synthetic"] is False
    assert reply["clinical_evidence"][0]["text"] in reply["response"]
    assert not reply["blocked"]
    again = ask(client, sid, headers, question)
    revealed = again["session"]["revealed_evidence_ids"]
    assert len(revealed) == len(set(revealed))
    events = client.get(f"/api/ai/sessions/{sid}/events", headers=headers).json()
    assert events[-1]["evidence_ids"] == reply["evidence_ids"]


@pytest.mark.parametrize("question,role", [
    ("Solicito hemograma", "laboratorio"), ("Solicito una radiografía", "radiologia"),
    ("Solicito interconsulta con cardiología", "especialista"),
])
def test_unsupported_request_does_not_invent_or_reveal_another_result(api, question, role):
    client, _, _ = api
    sid, headers = start(client)
    reply = ask(client, sid, headers, question)
    assert reply["agent"] == role and not reply["evidence_ids"] and not reply["clinical_evidence"]
    assert "disponible" in reply["response"]


@pytest.mark.parametrize("question,role", [("Pido análisis de sangre", "laboratorio"), ("Quiero un estudio de imagen", "radiologia")])
def test_generic_request_asks_for_specific_exam(api, question, role):
    client, _, _ = api
    sid, headers = start(client)
    reply = ask(client, sid, headers, question)
    assert reply["agent"] == role and reply["response"].startswith("¿Qué")
    assert not reply["clinical_evidence"]


def test_physical_exam_uses_assistant_and_updates_progressive_evidence(api):
    client, _, _ = api
    sid, headers = start(client)
    reply = ask(client, sid, headers, "Realizo exploración física")
    assert reply["agent"] == "medico_asistente"
    assert "párpado" in reply["clinical_evidence"][0]["text"]
    assert reply["clinical_evidence"][0]["evidence_id"] in reply["session"]["revealed_evidence_ids"]


def test_patient_word_orinar_does_not_route_to_laboratory(api):
    client, _, _ = api
    sid, headers = start(client)
    reply = ask(client, sid, headers, "¿Tiene molestias al orinar?")
    assert reply["agent"] == "paciente"
