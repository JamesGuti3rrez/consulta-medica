from __future__ import annotations

from typing import Any


ERROR_TYPES = ("negligencia", "anamnesis_incompleta", "razonamiento_clinico")


class ClinicalEvaluationEngine:
    """Puntúa evidencia recabada y clasifica omisiones según protected.evaluation."""

    def __init__(self, repository):
        self.repository = repository

    def evaluate(
        self,
        *,
        case_id: str,
        evidence_ids: list[str],
        initial_evidence_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        protected = self.repository.get_protected(case_id)
        all_questions = protected["evaluation"]["key_questions"]
        # Lo que el doctor entrega al presentar el caso no depende del estudiante:
        # esas preguntas no se puntúan ni cuentan como omisión.
        initial = set(initial_evidence_ids or [])
        questions = [
            question for question in all_questions
            if not set(question["evidence_ids"]).issubset(initial)
        ] or all_questions
        observed = set(evidence_ids) | initial
        total_weight = sum(question["weight"] for question in questions)
        earned_weight = 0
        completed_questions = 0
        errors = {error_type: 0 for error_type in ERROR_TYPES}

        for question in questions:
            if set(question["evidence_ids"]).issubset(observed):
                earned_weight += question["weight"]
                completed_questions += 1
            else:
                errors[question["error_if_missing"]] += 1

        return {
            "score": round(earned_weight * 100 / total_weight, 2),
            "earned_weight": earned_weight,
            "total_weight": total_weight,
            "completed_questions": completed_questions,
            "total_questions": len(questions),
            "errors": errors,
        }
