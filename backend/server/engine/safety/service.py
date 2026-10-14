from __future__ import annotations

import re

from server.domain import Intent
from server.engine.safety.protected_lexicon import normalize


class ClinicalSafetyEngine:
    """Comprueba propuestas contra alergias y contraindicaciones documentadas del caso."""

    def __init__(self, repository):
        self.repository = repository

    def evaluate_treatment(self, *, case_id: str, message: str, intent: Intent) -> list[dict[str, str]]:
        if intent != Intent.PROPOSE_TREATMENT:
            return []

        normalized_message = normalize(message)
        public = self.repository.get_conversation_case(case_id)["public"]
        protected = self.repository.get_protected(case_id)
        alerts: list[dict[str, str]] = []

        allergies = public.get("allergies", []) if public.get("allergies_recorded") else []
        if any(_contains_proposed_term(normalized_message, allergy) for allergy in allergies):
            alerts.append({
                "code": "known_allergy",
                "message": "La propuesta coincide con una alergia registrada. Verifícala antes de continuar.",
            })

        contraindications = protected["contraindications"]
        if any(
            _contains_proposed_term(normalized_message, term)
            for item in contraindications
            for term in _medication_terms(item["drug_or_class"])
        ):
            alerts.append({
                "code": "case_contraindication",
                "message": "La propuesta coincide con una contraindicación del caso. Verifícala antes de continuar.",
            })
        return alerts


def _medication_terms(value: str) -> set[str]:
    terms: set[str] = set()
    groups = re.findall(r"\(([^)]*)\)", value)
    outside_parentheses = re.sub(r"\([^)]*\)", " ", value)
    for group in [outside_parentheses, *groups]:
        for term in re.split(r",|\by\b|\be\b", group, flags=re.IGNORECASE):
            normalized = normalize(re.sub(r"\b(incluida?|incluidos?|como|por ejemplo)\b", " ", term))
            normalized = re.sub(r"\b(la|el|los|las|de|del)\b", " ", normalized)
            normalized = " ".join(normalized.split())
            if len(normalized) >= 3:
                terms.add(normalized)
    return terms


def _contains_proposed_term(normalized_message: str, value: str) -> bool:
    term = normalize(value)
    if not term:
        return False
    padded_message = f" {normalized_message} "
    padded_term = f" {term} "
    start = 0
    while (index := padded_message.find(padded_term, start)) >= 0:
        end = index + len(padded_term)
        before = padded_message[max(0, index - 90):index]
        if not re.search(
            r"\bno\s+(?:le\s+)?(?:prescrib\w*|indic\w*|administr\w*|d\w+|recomend\w*|inici\w*|us\w*|utiliz\w*)\b[^.!?]{0,60}$",
            before,
        ):
            return True
        start = end
    return False
