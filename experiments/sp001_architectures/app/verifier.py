from __future__ import annotations

from typing import Any
from app.case_store import evidence_catalog
from app.models import GeneratedAnswer
from app.routing import normalize


class Verifier:
    def verify(self, case: dict[str, Any], answer: GeneratedAnswer, allowed_to_reveal: bool = True) -> dict[str, Any]:
        catalog = evidence_catalog(case)
        unsupported_evidence = [eid for eid in answer.evidence_ids if eid not in catalog]
        wrong_values = []
        wrong_units = []

        for fact in answer.facts:
            src = catalog.get(fact.evidence_id)
            if src is None:
                if fact.evidence_id not in unsupported_evidence:
                    unsupported_evidence.append(fact.evidence_id)
                continue
            if normalize(str(src.get("value", ""))) != normalize(str(fact.value)):
                wrong_values.append(fact.evidence_id)
            src_unit = src.get("unit")
            if (src_unit or fact.unit) and normalize(str(src_unit or "")) != normalize(str(fact.unit or "")):
                wrong_units.append(fact.evidence_id)

        leak, matched = self.detect_leak(case, answer.natural_response)
        return {
            "evidence_valid": not unsupported_evidence and not wrong_values and not wrong_units,
            "unsupported_evidence": unsupported_evidence,
            "hallucinated_entities": len(unsupported_evidence),
            "wrong_values": wrong_values,
            "wrong_units": wrong_units,
            "diagnostic_leak": leak,
            "matched_protected_term": matched,
            "allowed_to_reveal": allowed_to_reveal,
            "validated": (not unsupported_evidence and not wrong_values and not wrong_units and not leak and allowed_to_reveal),
        }

    def detect_leak(self, case: dict[str, Any], text: str) -> tuple[bool, str | None]:
        protected = case.get("protected_evaluation", {})
        terms = [protected.get("diagnosis", "")]
        terms += protected.get("diagnosis_synonyms", [])
        terms += protected.get("protected_terms", [])
        nt = normalize(text)
        for term in terms:
            term = str(term).strip()
            if term and normalize(term) in nt:
                return True, term
        return False, None
