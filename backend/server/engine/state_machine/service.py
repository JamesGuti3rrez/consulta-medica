from __future__ import annotations

import copy
from typing import Any

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

_GESTURE_BY_PHASE = {
    SessionPhase.PRESENTACION: "idle",
    SessionPhase.ANAMNESIS: "attentive",
    SessionPhase.EXAMENES: "attentive",
    SessionPhase.HIPOTESIS: "thinking",
    SessionPhase.DIAGNOSTICO: "thinking",
    SessionPhase.CIERRE: "idle",
    SessionPhase.FINALIZADA: "idle",
}


class ClinicalStateMachine:
    """Fases clínicas y estado visual determinísticos; no infiere deterioro del paciente."""

    def advance(self, current: SessionPhase, intent: Intent) -> SessionPhase:
        if current == SessionPhase.FINALIZADA:
            return current
        target = _TARGET_BY_INTENT[intent]
        if target == SessionPhase.CIERRE:
            return target
        # La fase representa progreso alcanzado, no restringe volver a preguntar a otro agente.
        return target if _PHASE_ORDER[target] > _PHASE_ORDER[current] else current

    def initial_avatar_state(self, case: dict[str, Any]) -> dict[str, Any]:
        public = case["public"]
        vitals = [
            {
                key: item[key]
                for key in ("evidence_id", "label", "value", "unit", "text")
                if key in item
            }
            for item in public["items"]
            if item["category"] == "signo_vital"
        ]
        return {
            "gesture": _GESTURE_BY_PHASE[SessionPhase.PRESENTACION],
            "vitals": vitals,
            "alerts": [],
            "complications": [],
        }

    def update_avatar_state(
        self,
        current: dict[str, Any],
        phase: SessionPhase,
        alerts: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        updated = copy.deepcopy(current)
        updated["gesture"] = _GESTURE_BY_PHASE[phase]
        updated["alerts"].extend(copy.deepcopy(alerts or []))
        return updated
