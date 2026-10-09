from __future__ import annotations

from typing import Any


class ContextPolicy:
    """Construye el contexto mínimo permitido por rol.

    protected_evaluation nunca entra en un contexto conversacional.
    """

    @staticmethod
    def for_role(case: dict[str, Any], role: str, revealed: set[str]) -> dict[str, Any]:
        if role == "patient":
            return {"patient_knowledge": case.get("patient_knowledge", {})}
        if role == "specialist":
            return {"specialist_data": case.get("specialist_data", {})}
        if role in {"laboratory", "radiology"}:
            return {}
        if role in {"assistant", "supervisor"}:
            return {
                "initial_presentation": case.get("initial_presentation", {}),
                "revealed_evidence_ids": sorted(revealed),
            }
        if role == "evaluator":
            return {
                "protected_evaluation": case.get("protected_evaluation", {}),
                "revealed_evidence_ids": sorted(revealed),
            }
        return {}
