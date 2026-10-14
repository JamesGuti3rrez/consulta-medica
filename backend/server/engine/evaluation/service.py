from __future__ import annotations

from typing import Any


ERROR_TYPES = ("negligencia", "anamnesis_incompleta", "razonamiento_clinico")


class ClinicalEvaluationEngine:
    """Puntúa evidencia recabada y clasifica omisiones según protected.evaluation."""

    def __init__(self, repository):
        self.repository = repository

    def evaluate(self, *, case_id: str, evidence_ids: list[str]) -> dict[str, Any]:
        protected = self.repository.get_protected(case_id)
        questions = protected["evaluation"]["key_questions"]
        observed = set(evidence_ids)
        total_weight = sum(question["weight"] for question in questions)
        earned_weight = 0
        errors = {error_type: 0 for error_type in ERROR_TYPES}

        for question in questions:
            required_evidence = set(question["evidence_ids"])
            if required_evidence.issubset(observed):
                earned_weight += question["weight"]
            else:
                errors[question["error_if_missing"]] += 1

        return {
            "score": round(earned_weight * 100 / total_weight, 2),
            "earned_weight": earned_weight,
            "total_weight": total_weight,
            "completed_questions": sum(
                set(question["evidence_ids"]).issubset(observed) for question in questions
            ),
            "total_questions": len(questions),
            "errors": errors,
        }
