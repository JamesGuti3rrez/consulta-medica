from __future__ import annotations

from server.domain import Intent, SessionPhase


_PHASE_ORDER = {
    SessionPhase.PRESENTACION: 0,
    SessionPhase.ANAMNESIS: 1,
    SessionPhase.EXAMENES: 2,
    SessionPhase.HIPOTESIS: 3,
    SessionPhase.DIAGNOSTICO: 4,
    SessionPhase.CIERRE: 5,
    SessionPhase.FINALIZADA: 6,
}

_TARGET_BY_INTENT = {
    Intent.ASK_PATIENT: SessionPhase.ANAMNESIS,
    Intent.ASK_ASSISTANT: SessionPhase.ANAMNESIS,
    Intent.EXAMINE: SessionPhase.ANAMNESIS,
    Intent.REQUEST_LAB: SessionPhase.EXAMENES,
    Intent.REQUEST_RADIOLOGY: SessionPhase.EXAMENES,
    Intent.REQUEST_SPECIALIST: SessionPhase.EXAMENES,
    Intent.PROPOSE_HYPOTHESIS: SessionPhase.HIPOTESIS,
    Intent.PROPOSE_DIAGNOSIS: SessionPhase.DIAGNOSTICO,
    Intent.PROPOSE_TREATMENT: SessionPhase.DIAGNOSTICO,
    Intent.FINISH: SessionPhase.CIERRE,
}


class ClinicalStateMachine:
    """Fase clínica determinística; no obliga un pipeline rígido de agentes."""

    def advance(self, current: SessionPhase, intent: Intent) -> SessionPhase:
        if current == SessionPhase.FINALIZADA:
            return current
        target = _TARGET_BY_INTENT[intent]
        if target == SessionPhase.CIERRE:
            return target
        # La fase representa progreso alcanzado, no restringe volver a preguntar a otro agente.
        return target if _PHASE_ORDER[target] > _PHASE_ORDER[current] else current
