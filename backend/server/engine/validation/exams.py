"""Contrato mínimo de EN-013. La ampliación clínica especializada corresponde a TA-026."""
from __future__ import annotations

import math

VERSION = "synthetic-exam-contract-1.0.0"
CBC_SOURCE = "https://medlineplus.gov/ency/article/003642.htm"
GLUCOSE_SOURCE = "https://medlineplus.gov/ency/article/003482.htm"


def specification(panel, sex):
    if panel == "hemograma":
        male = sex == "masculino"
        return {
            "leucocitos": {"label": "Leucocitos", "unit": "/uL", "min": 4500, "max": 11000, "source": CBC_SOURCE},
            "hemoglobina": {"label": "Hemoglobina", "unit": "g/dL", "min": 13 if male else 12,
                            "max": 18 if male else 16, "source": CBC_SOURCE},
            "hematocrito": {"label": "Hematocrito", "unit": "%", "min": 40 if male else 36,
                            "max": 55 if male else 48, "source": CBC_SOURCE},
        }
    if panel == "glucosa_ayunas":
        return {"glucosa": {"label": "Glucosa en ayunas", "unit": "mg/dL", "min": 70, "max": 99, "source": GLUCOSE_SOURCE}}
    return {}


def validate_candidate(candidate, *, panel, sex, case):
    rules = specification(panel, sex)
    if not rules or not isinstance(candidate, dict) or set(candidate) != {"panel", "values"} or candidate["panel"] != panel:
        return False, "estructura_no_valida"
    values = candidate["values"]
    if not isinstance(values, dict) or set(values) != set(rules):
        return False, "indicadores_incompletos"
    for key, rule in rules.items():
        value = values[key]
        if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
            return False, "valor_no_numerico"
        if not rule["min"] <= value <= rule["max"]:
            return False, "requiere_revision_clinica"
        if key == "leucocitos" and value != int(value):
            return False, "precision_incompatible"
    if panel == "hemograma" and not 2.7 <= values["hematocrito"] / values["hemoglobina"] <= 3.3:
        return False, "incoherencia_hematologica"
    # No normalizar ficticiamente una alteración ya afirmada por el caso, aunque aún no se haya revelado.
    from server.engine.disclosure.policy import _normalize
    from server.cases.rules import evidence_text
    observed = _normalize(" ".join(evidence_text(i) for i in case["on_request"]))
    contradictions = ("anemia", "leucocitosis", "leucopenia", "hemorragia", "sangrado abundante") if panel == "hemograma" else ("hiperglucemia", "hipoglucemia", "diabetes")
    if any(word in observed for word in contradictions):
        return False, "contexto_requiere_revision"
    return True, "contrato_validado"
