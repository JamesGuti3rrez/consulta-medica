"""Permisos limitados para completar exámenes: el dato canónico siempre tiene prioridad."""
from __future__ import annotations

from .policy import _normalize


def requested_panel(message):
    text = f" {_normalize(message)} "
    if " hemograma " in text:
        return "hemograma"
    if any(f" {name} " in text for name in ("glucosa", "glucemia", "glicemia")) and " ayunas " in text:
        return "glucosa_ayunas"
    return None


def generation_permission(*, case, role, intent, message):
    panel = requested_panel(message)
    if role.value != "laboratorio" or intent.value != "request_lab" or panel is None:
        return None, "examen_no_soportado"
    if case["public"]["patient"]["age_years"] < 18 or case["specialty"] == "ginecologia_obstetricia":
        return None, "poblacion_requiere_revision"
    # Un panel existente se reconoce incluso cuando su tema de revelación está mal configurado.
    terms = ("hemograma", "leucocit", "hemoglobina", "hematocrito") if panel == "hemograma" else ("glucos", "glucem", "glicem")
    for item in case["on_request"]:
        if item["reveal_policy"]["owner"] != "laboratorio":
            continue
        identity = _normalize(item["evidence_id"] + " " + item["label"] + " " + " ".join(item["reveal_policy"]["requires"]))
        if any(term in identity for term in terms):
            return None, "dato_canonico_existente"
    # Una solicitud es clínicamente pertinente si hay al menos un motivo clínico en la ficha.
    if not case["public"]["chief_complaint"].get("text", "").strip():
        return None, "sin_contexto_clinico"
    return panel, "autorizado"
