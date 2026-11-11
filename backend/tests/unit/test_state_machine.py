import pytest

from server.domain import Intent, SessionPhase
from server.engine.state_machine.service import ClinicalStateMachine


def test_state_machine_tracks_progress_without_forcing_agent_pipeline():
    machine = ClinicalStateMachine()
    phase = machine.advance(SessionPhase.PRESENTACION, Intent.ASK_PATIENT)
    assert phase == SessionPhase.ANAMNESIS
    phase = machine.advance(phase, Intent.REQUEST_LAB)
    assert phase == SessionPhase.EXAMENES
    # Volver al paciente no hace retroceder la fase ni impide el routing.
    assert machine.advance(phase, Intent.ASK_PATIENT) == SessionPhase.EXAMENES
    assert machine.advance(phase, Intent.PROPOSE_HYPOTHESIS) == SessionPhase.HIPOTESIS


def test_closing_phase_allows_consultation_intents_without_reopening_or_regressing():
    machine = ClinicalStateMachine()

    assert machine.advance(SessionPhase.CIERRE, Intent.ASK_PATIENT) == SessionPhase.CIERRE
    assert machine.advance(SessionPhase.CIERRE, Intent.REQUEST_LAB) == SessionPhase.CIERRE
    assert machine.advance(SessionPhase.CIERRE, Intent.FINISH) == SessionPhase.CIERRE
    assert machine.advance(SessionPhase.FINALIZADA, Intent.ASK_PATIENT) == SessionPhase.FINALIZADA


def test_unknown_phase_or_intent_is_rejected_with_a_clear_error():
    machine = ClinicalStateMachine()

    with pytest.raises(ValueError, match="Fase clínica no válida"):
        machine.advance("fase_desconocida", Intent.ASK_PATIENT)
    with pytest.raises(ValueError, match="Intención clínica no válida"):
        machine.advance(SessionPhase.ANAMNESIS, "intencion_desconocida")


def test_avatar_keeps_case_vitals_and_records_alerts_without_simulating_complications():
    machine = ClinicalStateMachine()
    case = {
        "public": {
            "items": [
                {"evidence_id": "CSE-001.vital.fc", "category": "signo_vital", "label": "FC", "value": 74, "unit": "/min"},
                {"evidence_id": "CSE-001.sintoma.dolor", "category": "sintoma", "label": "Dolor", "text": "Leve"},
            ]
        }
    }
    initial = machine.initial_avatar_state(case)
    alert = {"code": "case_contraindication", "message": "Revisar la propuesta."}

    updated = machine.update_avatar_state(initial, SessionPhase.DIAGNOSTICO, [alert])

    assert initial["vitals"] == [
        {"evidence_id": "CSE-001.vital.fc", "label": "FC", "value": 74, "unit": "/min"}
    ]
    assert updated["vitals"] == initial["vitals"]
    assert updated["gesture"] == "thinking"
    assert updated["alerts"] == [alert]
    assert updated["complications"] == []
