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
    case = CanonicalCaseRepository().get_conversation_case("MED-007")
    decision = DisclosurePolicy().authorize(
        case=case,
        role=AgentRole.PACIENTE,
        intent=Intent.ASK_PATIENT,
        student_message="¿Es alérgica a algún medicamento?",
    )
    assert "MED-007.antecedente.alergias" in decision.allowed_evidence_ids


def test_curated_case_reveals_exam_only_when_examining():
    case = CanonicalCaseRepository().get_conversation_case("EME-001")
    policy = DisclosurePolicy()
    asked = policy.authorize(case=case, role=AgentRole.MEDICO_ASISTENTE, intent=Intent.ASK_ASSISTANT,
                             student_message="Voy a examinar al paciente")
    examined = policy.authorize(case=case, role=AgentRole.MEDICO_ASISTENTE, intent=Intent.EXAMINE,
                                student_message="Voy a examinar al paciente")
    assert asked.allowed_evidence_ids == []
    assert examined.allowed_evidence_ids == ["EME-001.examen.exploracion_fisica"]


def test_team_exam_topics_match_how_students_ask_for_them():
    from server.engine.disclosure.policy import DisclosurePolicy, _normalize

    matches = DisclosurePolicy._requirement_matches
    assert matches("factores_coagulacion", _normalize("Pido el dosaje del factor VIII y del factor IX"))
    assert matches("prolactina", _normalize("Solicito una prolactina sérica"))
    assert matches("electroencefalograma", _normalize("Pido un EEG"))


def test_mood_questions_reach_associated_symptoms():
    from server.engine.disclosure.policy import DisclosurePolicy, _normalize

    assert DisclosurePolicy._requirement_matches("sintomas_asociados", _normalize("¿Cómo está de ánimo? ¿Se ha sentido triste?"))


def test_tells_a_named_exam_from_a_generic_request():
    # Un pedido genérico no nombra ningún examen: el laboratorio debe preguntar cuál, no decir que no existe.
    from server.engine.disclosure.policy import DisclosurePolicy

    names = DisclosurePolicy.names_specific_exam
    for specific in ("Pido un hemograma", "Solicito pruebas de coagulación", "Pido una tomografía de cráneo",
                     "Solicito función tiroidea", "Pido una radiografía de tórax", "Pido el dosaje del factor VIII"):
        assert names(specific), specific
    for generic in ("¿Qué resultados tienen los análisis de sangre de antes de la operación?",
                    "Pido unos exámenes de laboratorio", "Quiero un estudio de imagen", "Mándele unos análisis"):
        assert not names(generic), generic


def test_natural_medication_question_retrieves_existing_hypertension_treatment():
    case = CanonicalCaseRepository().get_conversation_case("EME-103")
    decision = DisclosurePolicy().authorize(
        case=case, role=AgentRole.PACIENTE, intent=Intent.ASK_PATIENT,
        student_message="qué está tomando para controlar su hipertensión y en qué año le dio esta enfermedad",
    )
    assert "EME-103.medicacion.tratamiento_habitual" in decision.allowed_evidence_ids


def test_missing_medication_does_not_authorize_unrelated_lesion_history():
    case = CanonicalCaseRepository().get_conversation_case("MED-008")
    decision = DisclosurePolicy().authorize(
        case=case, role=AgentRole.PACIENTE, intent=Intent.ASK_PATIENT,
        student_message="qué está tomando para controlar su hipertensión y en qué año le dio esta enfermedad",
    )
    assert decision.allowed_evidence_ids == []
