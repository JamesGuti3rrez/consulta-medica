"""Caso clínico: lectura del archivo, versión pública (sin respuestas) y evaluación del razonamiento."""

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

CASE_PATH = Path(__file__).resolve().parent.parent / "data" / "caso-demo.json"

# Campos que revelan la respuesta: nunca se envían al navegador.
PRIVATE_FIELDS = {"diagnostico_correcto", "tratamiento_referencia", "errores_comunes", "diagnosticos_diferenciales"}


def read_case() -> dict[str, Any]:
    return json.loads(CASE_PATH.read_text(encoding="utf-8"))


def public_case(clinical_case: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in clinical_case.items() if key not in PRIVATE_FIELDS}


def normalize(text: Any) -> str:
    """Minúsculas, sin tildes y solo letras y números separados por un espacio."""
    decomposed = unicodedata.normalize("NFD", str(text or "").lower())
    without_accents = "".join(char for char in decomposed if not "̀" <= char <= "ͯ")
    return re.sub(r"[^a-z0-9]+", " ", without_accents).strip()


def match_differential(text: Any, differentials: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Devuelve el diferencial mencionado primero en el texto (a igual posición, el sinónimo más largo)."""
    source = f" {normalize(text)}"
    best = None
    best_index = float("inf")
    best_length = 0

    for differential in differentials:
        for synonym in differential.get("sinonimos", []):
            normalized_synonym = normalize(synonym)
            if not normalized_synonym:
                continue
            index = source.find(f" {normalized_synonym}")
            if index == -1:
                continue
            if index < best_index or (index == best_index and len(normalized_synonym) > best_length):
                best = differential
                best_index = index
                best_length = len(normalized_synonym)
    return best


def evaluate_reasoning(clinical_case: dict[str, Any], body: dict[str, Any]) -> list[dict[str, str]]:
    differentials = clinical_case.get("diagnosticos_diferenciales", [])
    hypotheses = body.get("hipotesis") if isinstance(body.get("hipotesis"), list) else []
    items: list[dict[str, str]] = []

    def ok(texto: str) -> None:
        items.append({"tipo": "ok", "texto": texto})

    def warning(texto: str) -> None:
        items.append({"tipo": "aviso", "texto": texto})

    def error(texto: str) -> None:
        items.append({"tipo": "error", "texto": texto})

    recognized: dict[str, dict[str, Any]] = {}
    unrecognized: list[dict[str, Any]] = []
    for hypothesis in hypotheses:
        if not isinstance(hypothesis, dict):
            continue
        match = match_differential(hypothesis.get("texto"), differentials)
        if match:
            recognized[match["id"]] = hypothesis
        else:
            unrecognized.append(hypothesis)

    if not hypotheses:
        warning("No registraste hipótesis durante la consulta.")

    for differential in differentials:
        name = differential["nombre"]
        hypothesis = recognized.get(differential["id"])

        if differential.get("correcta"):
            if not hypothesis:
                error(f"No planteaste {name} entre tus hipótesis.")
            elif hypothesis.get("descartada"):
                error(f"Descartaste {name}, que era la hipótesis correcta.")
            else:
                ok(f"Planteaste y mantuviste {name}, la hipótesis correcta.")
            continue

        if not hypothesis:
            if differential.get("peligrosa"):
                warning(f"No consideraste {name}. {differential.get('por_que_considerar', '')}")
            continue

        if not hypothesis.get("descartada"):
            warning(f"{name} quedó activa sin descartar. {differential.get('dato_que_descarta', '')}")
            continue

        discard_turn = hypothesis.get("descartadaEnTurno")
        if not isinstance(discard_turn, int) or isinstance(discard_turn, bool):
            discard_turn = 0
        needed_turns = differential.get("turnos_necesarios")
        if needed_turns is not None and discard_turn < needed_turns:
            error(f"Descarte prematuro de {name}: aún no tenías el dato. {differential.get('dato_que_descarta', '')}")
        else:
            reason = f" (tu motivo: {hypothesis['motivo']})" if hypothesis.get("motivo") else ""
            ok(f"Descartaste {name} con el dato disponible{reason}.")

    for hypothesis in unrecognized:
        warning(f'"{hypothesis.get("texto", "")}" no está entre los diferenciales previstos para este caso.')

    expected = clinical_case.get("diagnostico_correcto", "")
    final_match = match_differential(body.get("diagnostico"), differentials)
    if final_match and final_match.get("correcta"):
        ok(f"Tu diagnóstico final coincide con el esperado: {expected}.")
    elif final_match:
        error(f"Tu diagnóstico final apunta a {final_match['nombre']}; el esperado era: {expected}.")
    else:
        warning(f"No se reconoció tu diagnóstico final. El esperado era: {expected}.")

    return items
