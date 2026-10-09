from pathlib import Path

from server.cases import CanonicalCaseRepository
from server.domain import AgentRole, Intent
from server.engine.disclosure.policy import DisclosurePolicy

ROOT = Path(__file__).resolve().parents[2]


def _repo():
    return CanonicalCaseRepository(ROOT / "data/cases/curated", ROOT / "schemas/caso.schema.json")


def test_disclosure_uses_owner_mode_and_requires():
    case = _repo().get_conversation_case("CARD-001")
    policy = DisclosurePolicy()

    patient = policy.authorize(
        case=case,
        role=AgentRole.PACIENTE,
        intent=Intent.ASK_PATIENT,
        student_message="¿Desde cuándo comenzó el dolor y cómo lo describiría?",
    )
    assert patient.allowed_evidence_ids == ["CARD-001.anamnesis.inicio_dolor"]

    wrong_role = policy.authorize(
        case=case,
        role=AgentRole.PACIENTE,
        intent=Intent.ASK_PATIENT,
        student_message="Solicito un hemograma",
    )
    assert "CARD-001.laboratorio.hemograma" not in wrong_role.allowed_evidence_ids

    lab = policy.authorize(
        case=case,
        role=AgentRole.LABORATORIO,
        intent=Intent.REQUEST_LAB,
        student_message="Solicito un hemograma",
    )
    assert lab.allowed_evidence_ids == ["CARD-001.laboratorio.hemograma"]
