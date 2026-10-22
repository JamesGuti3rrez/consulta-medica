"""Contrato de los 30 casos nuevos y acceso a sus evidencias durante una consulta."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from case_preparation.familias.ampliacion import build_cases, load_design
from server.cases.catalog import to_student_case
from server.cases.rules import check_batch_rules, check_case_rules, check_case_warnings
from server.cases.validator import validate_case_document
from server.domain import AgentRole, Intent
from server.engine.disclosure.policy import DisclosurePolicy
from server.orchestration.router import DecisionRouter

CURATED = Path(__file__).resolve().parents[2] / "data/cases/curated"
DESIGN = load_design()
CASES = build_cases()
STUDIES = [
    (case, study)
    for family in DESIGN for spec in family["cases"]
    for case in CASES if case["case_id"] == spec["id"]
    for study in spec["studies"]
]


def test_thirty_new_cases_preserve_numbering_and_versioned_content():
    expected = {f"{prefix}-{number:03d}" for prefix in ("CIR", "GOB", "MED", "PED") for number in range(101, 107)}
    expected |= {f"EME-{number:03d}" for number in range(104, 110)}
    assert {case["case_id"] for case in CASES} == expected
    for case in CASES:
        saved = json.loads((CURATED / f"{case['case_id']}.json").read_text(encoding="utf-8"))
        assert saved == case
        validate_case_document(saved)
        assert check_case_rules(saved) == []
        assert check_case_warnings(saved) == []
    assert check_batch_rules(CASES) == []


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["case_id"])
def test_new_cases_keep_initial_presentation_free_of_private_findings(case):
    public = to_student_case(case)
    assert "protected" not in public and "on_request" not in public
    assert not ({"signo_vital", "examen_fisico", "laboratorio", "imagen"} &
                {item["category"] for item in case["public"]["items"]})
    initial = set(DisclosurePolicy.initial_evidence_ids(case))
    assert not initial & {item["evidence_id"] for item in case["on_request"]}
    assert "pendiente" in case["provenance"]["curated_by"]


@pytest.mark.parametrize(("case", "study"), STUDIES,
                         ids=[f"{case['case_id']}-{study['key']}" for case, study in STUDIES])
def test_each_study_can_be_requested_and_stays_hidden_from_patient(case, study):
    route = DecisionRouter().route(study["ask"])
    owner = AgentRole(study["owner"])
    intent = Intent.REQUEST_RADIOLOGY if owner == AgentRole.RADIOLOGIA else Intent.REQUEST_LAB
    assert (route.target, route.intent) == (owner, intent)
    allowed = DisclosurePolicy().authorize(case=case, role=owner, intent=intent, student_message=study["ask"])
    expected = next(item["evidence_id"] for item in case["on_request"]
                    if item["reveal_policy"]["requires"] == [study["key"]])
    assert expected in allowed.allowed_evidence_ids
    assert DisclosurePolicy.names_specific_exam(study["ask"])
    patient = DisclosurePolicy().authorize(case=case, role=AgentRole.PACIENTE,
                                           intent=Intent.ASK_PATIENT, student_message=study["ask"])
    assert expected not in patient.allowed_evidence_ids


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["case_id"])
def test_physician_examination_reveals_only_requested_clinical_evidence(case):
    policy = DisclosurePolicy()
    for message, key in (("Solicito signos vitales", "signos_vitales"),
                         ("Realizo exploración física", "exploracion_fisica")):
        route = DecisionRouter().route(message)
        assert (route.target, route.intent) == (AgentRole.MEDICO_ASISTENTE, Intent.EXAMINE)
        allowed = policy.authorize(case=case, role=route.target, intent=route.intent, student_message=message)
        assert len(allowed.allowed_evidence_ids) == 1
        assert allowed.allowed_evidence_ids[0].endswith("." + key)

