from __future__ import annotations

import unicodedata


def normalize(text: str) -> str:
    text = text.lower().strip()
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def heuristic_route(question: str) -> str:
    q = normalize(question)
    if any(k in q for k in ["tropon", "hemoglob", "glucosa", "laboratorio", "analisis de sangre", "creatin", "potasio"]):
        return "laboratory"
    if any(k in q for k in ["ecg", "electrocard", "radiografia", "rayos x", "tomografia", "imagen"]):
        return "radiology"
    if any(k in q for k in ["cardiolog", "especialista", "interconsulta"]):
        return "specialist"
    if any(k in q for k in ["dolor", "duele", "sintoma", "siente", "antecedente", "alerg", "fuma", "familia"]):
        return "patient"
    return "assistant"
