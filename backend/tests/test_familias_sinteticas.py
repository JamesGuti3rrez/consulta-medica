"""Familia sintética de dolor torácico (EME-101 a EME-103) y reglas R15 a R18."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from case_preparation.familias.dolor_toracico import CASES, build_case
from server.cases.rules import check_batch_rules, check_case_rules
from server.engine.disclosure.policy import DisclosurePolicy
from server.domain import AgentRole, Intent
from server.orchestration.router import DecisionRouter

CURATED = Path(__file__).resolve().parents[2] / "data" / "cases" / "curated"
FAMILY_IDS = ("EME-101", "EME-102", "EME-103")


def _family() -> list[dict]:
    return [json.loads((CURATED / f"{case_id}.json").read_text(encoding="utf-8")) for case_id in FAMILY_IDS]


def _codes(errors: list[str]) -> set[str]:
    return {error.split(" ", 1)[0] for error in errors}


def test_versioned_cases_match_the_family_design():
    """Los JSON de curated/ son exactamente los que genera el diseño de la familia."""
    assert [build_case(spec) for spec in CASES] == _family()


def test_family_passes_all_rules():
    family = _family()
    assert {case["case_id"]: check_case_rules(case) for case in family} == {case_id: [] for case_id in FAMILY_IDS}
    assert check_batch_rules(family) == []


def test_family_shares_the_presentation_and_differs_in_the_diagnosis():
    family = _family()
    assert len({case["public"]["chief_complaint"]["text"] for case in family}) == 1
    assert len({case["protected"]["diagnosis"]["name"] for case in family}) == 3
    for case in family:
        assert all(d["discard_evidence_ids"] for d in case["protected"]["differentials"]), case["case_id"]


def test_r15_differential_without_discarding_data():
    case = _family()[0]
    case["protected"]["differentials"][0]["discard_evidence_ids"] = []
    assert "R15" in _codes(check_case_rules(case))


def test_r16_discarding_data_must_be_on_request():
    case = _family()[0]
    case["protected"]["differentials"][0]["discard_evidence_ids"].append(case["public"]["items"][0]["evidence_id"])
    assert "R16" in _codes(check_case_rules(case))


def test_r17_family_in_item_id():
    case = _family()[0]
    case["source"]["item_id"] = "sin familia"
    assert "R17" in _codes(check_case_rules(case))


def test_r18_family_must_share_complaint_and_cross_differentials():
    family = _family()
    changed = deepcopy(family)
    changed[0]["public"]["chief_complaint"]["text"] = "Dolor abdominal desde ayer."
    assert "R18" in _codes(check_batch_rules(changed))
    changed = deepcopy(family)
    changed[1]["protected"]["differentials"] = changed[1]["protected"]["differentials"][1:]
    assert "R18" in _codes(check_batch_rules(changed))
    assert "R18" in _codes(check_batch_rules(family[:1]))


def test_medqa_cases_are_not_affected_by_synthetic_rules():
    medqa = json.loads((CURATED / "EME-001.json").read_text(encoding="utf-8"))
    assert medqa["source"]["dataset"] == "MedQA"
    assert not {"R15", "R16", "R17"} & _codes(check_case_rules(medqa))


@pytest.mark.parametrize(
    ("message", "role", "intent", "suffix"),
    [
        ("Quiero un electrocardiograma", AgentRole.LABORATORIO, Intent.REQUEST_LAB, "estudio.electrocardiograma"),
        ("Pido troponina", AgentRole.LABORATORIO, Intent.REQUEST_LAB, "lab.troponina"),
        ("Solicito dímero D", AgentRole.LABORATORIO, Intent.REQUEST_LAB, "lab.dimero_d"),
        ("Pido una radiografía de tórax", AgentRole.RADIOLOGIA, Intent.REQUEST_RADIOLOGY, "imagen.radiografia_torax"),
        ("Solicito angiotomografía de tórax", AgentRole.RADIOLOGIA, Intent.REQUEST_RADIOLOGY, "imagen.angiotomografia_torax"),
    ],
)
def test_family_exams_are_routed_and_revealed(message, role, intent, suffix):
    decision = DecisionRouter().route(message)
    assert (decision.target, decision.intent) == (role, intent)
    case = _family()[2]
    allowed = DisclosurePolicy().authorize(case=case, role=role, intent=intent, student_message=message).allowed_evidence_ids
    assert allowed == [f"EME-103.{suffix}"]
