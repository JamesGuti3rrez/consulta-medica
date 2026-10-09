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
