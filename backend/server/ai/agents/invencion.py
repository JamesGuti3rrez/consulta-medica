"""Detección de síntomas inventados: los que el agente menciona como presentes y el caso no tiene.

Compara la respuesta con el CONTEXTO AUTORIZADO que recibió el agente (ficha visible, datos ya revelados
y evidencia recuperada). Un síntoma negado («no tengo tos», «sin fiebre», «nada de mareos») no cuenta.
"""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Any

# Raíces normalizadas (sin tildes): cubren las variantes («mareo», «mareado», «mareos»).
SYMPTOMS = {
    "mareo": ("mare",),
    "náuseas": ("nause",),
    "vómitos": ("vomit",),
    "diarrea": ("diarre",),
    "tos": ("tos", "toso"),
    "dolor de cabeza": ("dolor de cabeza", "duele la cabeza", "cefale"),
    "dolor de pecho": ("dolor de pecho", "dolor en el pecho", "duele el pecho", "dolor toracic"),
    "falta de aire": ("falta de aire", "ahog", "disne"),
    "fiebre": ("fiebre", "febril"),
    "escalofríos": ("escalofri",),
    "sangrado": ("sangr",),
    "picazón": ("picaz", "comezon"),
    "ardor": ("ardor",),
    "hormigueo": ("hormigue", "entumec"),
    "debilidad": ("debil",),
    "cansancio": ("cansad", "cansanci", "fatiga"),
    "palpitaciones": ("palpitacion",),
    "desmayo": ("desmay",),
    "convulsiones": ("convuls",),
    "visión borrosa": ("vision borrosa",),
    "dolor abdominal": ("dolor abdominal", "dolor de estomago", "dolor de barriga", "duele el estomago", "duele la barriga"),
    "dolor de garganta": ("dolor de garganta",),
    "pérdida de peso": ("perdida de peso", "baje de peso", "bajado de peso"),
}
FEVER_CELSIUS = 38.0
TEMPERATURE = re.compile(r"(\d{2}(?:[.,]\d)?)\s*(?:°|grados)\s*c", re.IGNORECASE)
NEGATION = re.compile(r"\b(?:no|ni|sin|niego|niega|nada|nunca|tampoco|ningun|ninguna)\b")


def _normalize(text: str) -> str:
    raw = unicodedata.normalize("NFD", str(text or "").casefold())
    raw = "".join(ch for ch in raw if unicodedata.category(ch) != "Mn")
    return " " + re.sub(r"[^a-z0-9]+", " ", raw).strip() + " "


def _context_text(context: dict[str, Any]) -> str:
    parts = [context.get("case_title", "")]
    for key in ("public_evidence", "revealed_evidence", "retrieved_evidence"):
        parts.append(json.dumps(context.get(key) or [], ensure_ascii=False))
    return _normalize(" ".join(parts))


def _has_fever(context: dict[str, Any]) -> bool:
    raw = " ".join(json.dumps(context.get(key) or [], ensure_ascii=False)
                   for key in ("public_evidence", "revealed_evidence", "retrieved_evidence"))
    return any(float(value.replace(",", ".")) >= FEVER_CELSIUS for value in TEMPERATURE.findall(raw))


def invented_symptoms(reply: str, context: dict[str, Any]) -> list[str]:
    """Síntomas que la respuesta afirma y que no aparecen en el contexto autorizado."""
    text = _normalize(reply)
    allowed = _context_text(context)
    fever = _has_fever(context)
    found = []
    for name, stems in SYMPTOMS.items():
        # Cada raíz coincide al inicio de una palabra («tos» no coincide dentro de «gastos»).
        if any(f" {stem}" in allowed for stem in stems) or (name == "fiebre" and fever):
            continue
        for stem in stems:
            start = text.find(f" {stem}")
            while start != -1:
                # Negado si en las cuatro palabras anteriores hay una negación.
                before = " ".join(text[:start].split()[-4:])
                if not NEGATION.search(before):
                    found.append(name)
                    break
                start = text.find(f" {stem}", start + 1)
            if name in found:
                break
    return found


# Cifras escritas con letras que cuentan como la cifra («hace cinco días» = 5).
NUMBER_WORDS = {
    "1": ("uno", "una", "un"), "2": ("dos",), "3": ("tres",), "4": ("cuatro",), "5": ("cinco",), "6": ("seis",),
    "7": ("siete",), "8": ("ocho",), "9": ("nueve",), "10": ("diez",), "12": ("doce",), "15": ("quince",),
    "20": ("veinte",), "30": ("treinta",), "60": ("sesenta",),
}
FIGURE = re.compile(r"\d+(?:[.,]\d+)?")


def invented_figures(reply: str, context: dict[str, Any]) -> list[str]:
    """Las cifras de una salida clínica deben existir en su contexto, no en la pregunta del alumno."""
    raw = json.dumps({key: context.get(key) for key in
                     ("patient", "public_evidence", "revealed_evidence", "retrieved_evidence")}, ensure_ascii=False)
    # Los números que aparecen solo en identificadores no autorizan valores clínicos.
    raw = re.sub(r'[A-Z]{3,5}-\d{3}(?:\.[\w]+)*', '', raw)
    allowed = {value.replace(',', '.') for value in FIGURE.findall(raw)}
    return [value for value in FIGURE.findall(reply) if value.replace(',', '.') not in allowed]


def omitted_figures(reply: str, context: dict[str, Any]) -> list[str]:
    """Cifras de la evidencia recuperada que la respuesta no menciona (ni con dígitos ni con letras).

    Una dosis, una duración o un valor de laboratorio que se omite cambia el caso: «dejó el amlodipino»
    no es lo mismo que «dejó el amlodipino 10 mg hace 4 meses».
    """
    evidence = " ".join(str(item.get("text", "")) for item in context.get("retrieved_evidence") or [])
    in_reply = {figure.replace(",", ".") for figure in FIGURE.findall(reply)}
    words = set(_normalize(reply).split())
    return [
        figure for figure in dict.fromkeys(FIGURE.findall(evidence))
        if figure.replace(",", ".") not in in_reply and not words & set(NUMBER_WORDS.get(figure, ()))
    ]
