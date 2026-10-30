"""TA-012: comparación determinística del diagnóstico final, sin LLM ni búsqueda aproximada."""
from __future__ import annotations

import re
import unicodedata
from typing import Any

VERSION = "1.0.0"
PREFIX = re.compile(r"^(?:(?:mi|el)\s+)?(?:diagnostico(?:\s+final)?|dx)(?:\s+es\s*[:=-]?|\s*[:=-])\s*")
UNCERTAIN = re.compile(r"\b(?:posible|probable|quizas|tal vez|podria|puede ser|sospecha|descartar|versus|vs)\b")
ALTERNATIVES = re.compile(r"[,;/|\n]+|\s+(?:o|u|y|e|versus|vs\.?)\s+", re.IGNORECASE)


def normalize_diagnosis(value: str | None) -> str:
    text = unicodedata.normalize("NFKD", value or "").casefold()
    text = "".join(char for char in text if not unicodedata.combining(char) and unicodedata.category(char) != "Cf")
    text = PREFIX.sub("", text.strip())
    return " ".join(re.findall(r"[a-z0-9]+", text))


def grade_diagnosis(value: str | None, diagnosis: dict[str, Any],
                    differentials: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Compara solo etiquetas completas del caso. La frontera de cierre está en el motor."""
    normalized = normalize_diagnosis(value)
    reference = diagnosis["name"]
    accepted = [reference, *diagnosis.get("synonyms", [])]
    matches = [label for label in accepted if normalized and normalize_diagnosis(label) == normalized]

    def result(status, code, reason, matched=None):
        return {"status": status, "score": 100 if status == "correct" else 0, "max_score": 100,
                "reason_code": code, "reason": reason, "normalized_input": normalized,
                "matched_term": matched, "requires_review": status == "ambiguous", "version": VERSION}

    if not normalized:
        return result("empty", "empty_input", "No se registró un diagnóstico final.")
    if "?" in (value or ""):
        return result("ambiguous", "uncertain_answer",
                      "La respuesta expresa duda o una hipótesis; requiere revisión docente y no recibe acierto automático.")
    shared = any(normalize_diagnosis(item["name"]) == normalized for item in differentials or [])
    if matches and shared:
        return result("ambiguous", "shared_label",
                      "La etiqueta coincide con la referencia y con un diferencial del caso; requiere revisión docente.")
    if matches:
        canonical = normalized == normalize_diagnosis(reference)
        return result("correct", "reference_match" if canonical else "synonym_match",
                      "Coincide con el diagnóstico de referencia normalizado." if canonical
                      else "Coincide con un sinónimo admitido por este caso.", matches[0])
    if UNCERTAIN.search(normalized):
        return result("ambiguous", "uncertain_answer",
                      "La respuesta expresa duda o una hipótesis; requiere revisión docente y no recibe acierto automático.")
    parts = [part.strip() for part in ALTERNATIVES.split(value or "") if normalize_diagnosis(part)]
    if len(parts) > 1:
        return result("ambiguous", "multiple_answers",
                      "Se registraron varias alternativas en lugar de un único diagnóstico final; requiere revisión docente.")
    return result("incorrect", "no_match",
                  "No coincide exactamente con el diagnóstico de referencia ni con los sinónimos admitidos por este caso.")

