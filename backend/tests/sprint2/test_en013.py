"""EN-013: candidato condicionado, validación, procedencia, prioridad canónica y aislamiento."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from server.ai.llm.base import LLMResult
from server.cases.repository import CanonicalCaseRepository
from server.rag.retriever import CaseEvidenceRetriever
from server.orchestration.exam_completion import SyntheticExamCompletion
from .conftest import start, ask

TASK = "EN-013"
GOOD = {"panel": "hemograma", "values": {"leucocitos": 7000, "hemoglobina": 14.5, "hematocrito": 43}}


class Composer:
    def __init__(self, candidate=None):
        self.candidate = deepcopy(GOOD if candidate is None else candidate)
        self.calls = []
    def compose(self, **kwargs):
        self.calls.append(kwargs)
        assert "protected" not in kwargs["context"]
        return LLMResult(text=json.dumps(self.candidate), provider="prueba-estructurada", model="controlled")


def enable(service, candidate=None):
    composer = Composer(candidate)
    service.graph.exam_completion = SyntheticExamCompletion(composer)
    return composer


def test_generated_exam_has_units_references_provenance_and_session_reuse(api):
    client, service, _ = api
    composer = enable(service)
    sid, headers = start(client)
    first = ask(client, sid, headers, "Solicito hemograma")
    assert not first["blocked"] and first["data_source"] == "sintetico_examen"
    item = first["clinical_evidence"][0]
    assert item["synthetic"] and len(item["indicators"]) == 3
    assert all(i["unit"] and i["reference"]["min"] <= i["value"] <= i["reference"]["max"] for i in item["indicators"])
    assert item["provenance"]["clinical_review"] == "pendiente"
    assert "no observado" in first["response"]
    second = ask(client, sid, headers, "Quiero los resultados del hemograma")
    assert second["response"] == first["response"] and len(composer.calls) == 1
    assert second["synthetic_reused_ids"] == first["synthetic_generated_ids"]
    snapshot = service.store.get(sid)["synthetic_exam_results"]
    assert snapshot["hemograma"]["candidate"] == GOOD
    event = client.get(f"/api/ai/sessions/{sid}/events", headers=headers).json()[-1]
    assert event["exam_validation"]["decision"] == "contrato_validado"


@pytest.mark.parametrize("case_id,question", [("MED-900", "Solicito hemograma"), ("CIR-005", "Solicito pruebas de coagulación")])
def test_canonical_results_prevent_generation(api, case_id, question):
    client, service, _ = api
    if case_id == "MED-900":
        service.repository = service.graph.repository = CanonicalCaseRepository(Path(__file__).resolve().parents[1] / "fixtures/cases")
        service.graph.retriever = CaseEvidenceRetriever(service.repository)
        service.graph.protected_lexicon.repository = service.repository
    composer = enable(service)
    sid, headers = start(client, case_id)
    reply = ask(client, sid, headers, question)
    assert reply["evidence_ids"] and not composer.calls
    assert reply["data_source"] == "curado" and not reply["synthetic_generated_ids"]


@pytest.mark.parametrize("candidate", [
    {"panel": "hemograma", "values": {"leucocitos": 999999, "hemoglobina": 14.5, "hematocrito": 43}},
    {"panel": "hemograma", "values": {"leucocitos": "7000", "hemoglobina": 14.5, "hematocrito": 43}},
    {"panel": "hemograma", "values": {"leucocitos": 7000, "hemoglobina": 18, "hematocrito": 40}},
    {"panel": "hemograma", "values": {"leucocitos": 7000}},
    {**GOOD, "diagnostico": "Carcinoma basocelular"},
    {"panel": "troponina", "values": {"troponina": 1}},
    {"abstain": True},
    {"panel": "hemograma", "values": {"leucocitos": True, "hemoglobina": 14.5, "hematocrito": 43}},
    {"panel": "hemograma", "values": {"leucocitos": float("nan"), "hemoglobina": 14.5, "hematocrito": 43}},
])
def test_unvalidated_candidate_is_never_revealed_or_saved(api, candidate):
    client, service, _ = api
    enable(service, candidate)
    sid, headers = start(client)
    result = ask(client, sid, headers, "Solicito hemograma")
    assert result["blocked"] and result["evidence_ids"] == [] and result["clinical_evidence"] == []
    assert "999999" not in result["response"] and "carcinoma" not in result["response"].lower()
    assert not service.store.get(sid).get("synthetic_exam_results")


@pytest.mark.parametrize("question", ["Solicito una tomografía", "Solicito troponina", "Pido análisis de sangre", "¿Tiene alergias?"])
def test_only_supported_explicit_lab_requests_can_generate(api, question):
    client, service, _ = api
    composer = enable(service)
    sid, headers = start(client)
    reply = ask(client, sid, headers, question)
    assert not composer.calls and not reply["synthetic_generated_ids"]


def test_fasting_glucose_requires_explicit_sample_condition(api):
    client, service, _ = api
    composer = enable(service, {"panel": "glucosa_ayunas", "values": {"glucosa": 90}})
    sid, headers = start(client)
    assert not ask(client, sid, headers, "Solicito glucosa")["synthetic_generated_ids"]
    generated = ask(client, sid, headers, "Solicito glucosa en ayunas")
    assert generated["clinical_evidence"][0]["indicators"][0]["unit"] == "mg/dL"
    assert len(composer.calls) == 1


def test_generated_exam_is_not_shared_between_sessions_and_not_graded_as_canonical(api):
    client, service, _ = api
    composer = enable(service)
    sid, headers = start(client)
    ask(client, sid, headers, "Solicito hemograma")
    other, other_headers = start(client)
    assert not service.store.get(other).get("synthetic_exam_results")
    ask(client, other, other_headers, "Solicito hemograma")
    assert len(composer.calls) == 2
    finish = client.post(f"/api/ai/sessions/{sid}/finish", headers=headers, json={}).json()
    assert len(finish["report"]["synthetic_exams"]) == 1
    assert all("sintetico" not in str(q) for q in finish["report"]["key_questions"]["obtained"])


def test_composer_prompt_contains_no_alias_diagnosis_or_raw_student_instructions():
    from server.ai.agents.exam_composer import ExamComposer
    from server.engine.validation.exams import specification
    class Gateway:
        def generate_json(self, messages, **kwargs):
            text = json.dumps(messages)
            assert "Alberto" not in text and "carcinoma" not in text.lower() and "ignore" not in text.lower()
            return LLMResult(text=json.dumps(GOOD), provider="fake", model="json")
    ExamComposer(Gateway()).compose(panel="hemograma", context={"patient": {"alias": "Alberto", "age_years": 68, "sex": "masculino"}},
        specification=__import__('server.engine.validation.exams', fromlist=['specification']).specification("hemograma", "masculino"))


@pytest.mark.parametrize("case_id", ["PED-101", "GOB-101"])
def test_population_without_reference_contract_never_generates(api, case_id):
    client, service, _ = api
    composer = enable(service)
    sid, headers = start(client, case_id)
    reply = ask(client, sid, headers, "Solicito hemograma")
    assert not composer.calls and not reply["synthetic_generated_ids"]
