from pathlib import Path

from server.cases import CanonicalCaseRepository
from server.domain import AgentRole, Intent
from server.engine.disclosure.policy import DisclosurePolicy

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "cases"


def _repo():
    return CanonicalCaseRepository(FIXTURES)


def test_disclosure_uses_owner_mode_and_requires():
    case = _repo().get_conversation_case("MED-900")
    policy = DisclosurePolicy()

    patient = policy.authorize(
        case=case,
        role=AgentRole.PACIENTE,
        intent=Intent.ASK_PATIENT,
        student_message="¿Desde cuándo comenzó el dolor y cómo lo describiría?",
    )
    assert patient.allowed_evidence_ids == ["MED-900.anamnesis.inicio_dolor"]

    wrong_role = policy.authorize(
        case=case,
        role=AgentRole.PACIENTE,
        intent=Intent.ASK_PATIENT,
        student_message="Solicito un hemograma",
    )
    assert "MED-900.laboratorio.hemograma" not in wrong_role.allowed_evidence_ids

    lab = policy.authorize(
        case=case,
        role=AgentRole.LABORATORIO,
        intent=Intent.REQUEST_LAB,
        student_message="Solicito un hemograma",
    )
    assert lab.allowed_evidence_ids == ["MED-900.laboratorio.hemograma"]


def test_curated_case_reveals_allergy_when_asked():
    case = CanonicalCaseRepository().get_conversation_case("MED-008")
    decision = DisclosurePolicy().authorize(
        case=case,
        role=AgentRole.PACIENTE,
        intent=Intent.ASK_PATIENT,
        student_message="¿Es alérgica a algún medicamento?",
    )
    assert "MED-008.antecedente.alergias" in decision.allowed_evidence_ids


def test_curated_case_reveals_exam_only_when_examining():
    case = CanonicalCaseRepository().get_conversation_case("EME-001")
    policy = DisclosurePolicy()
    asked = policy.authorize(case=case, role=AgentRole.MEDICO_ASISTENTE, intent=Intent.ASK_ASSISTANT,
                             student_message="Voy a examinar al paciente")
    examined = policy.authorize(case=case, role=AgentRole.MEDICO_ASISTENTE, intent=Intent.EXAMINE,
                                student_message="Voy a examinar al paciente")
    assert asked.allowed_evidence_ids == []
    assert examined.allowed_evidence_ids == ["EME-001.examen.exploracion_fisica"]
