from __future__ import annotations

import re
import unicodedata



def normalize(text: str) -> str:
    raw = unicodedata.normalize("NFD", str(text or "").casefold())
    raw = "".join(ch for ch in raw if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", raw).strip()


class ProtectedLexiconService:
    """Único adaptador conversacional autorizado a leer protected para crear una denylist.

    El guardrail recibe solo términos normalizados; nunca el bloque protected ni el caso completo.
    """

    def __init__(self, repository):
        self.repository = repository

    def for_case(self, case_id: str) -> set[str]:
        protected = self.repository.get_protected(case_id)
        terms: set[str] = set()
        diagnosis = protected.get("diagnosis") or {}
        for value in [diagnosis.get("name"), *(diagnosis.get("synonyms") or [])]:
            if value:
                terms.add(normalize(str(value)))
        for item in protected.get("differentials", []) or []:
            if item.get("name"):
                terms.add(normalize(str(item["name"])))
        treatment = protected.get("treatment_reference") or {}
        if treatment.get("summary"):
            terms.add(normalize(str(treatment["summary"])))
        return {term for term in terms if len(term) >= 4}
