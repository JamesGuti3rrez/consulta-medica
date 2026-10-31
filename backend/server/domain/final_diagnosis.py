"""Diagnóstico final del alumno (HU-006): obligatorio, validado y normalizado antes de registrarlo.

El simulador aplica las mismas reglas antes de enviar; el servidor las vuelve a aplicar porque es quien registra.
"""

from __future__ import annotations

import re
import unicodedata

MAX_LENGTH = 2000
MIN_LETTERS = 3

MISSING = "Escribe tu diagnóstico final antes de cerrar la consulta."
FEW_LETTERS = f"El diagnóstico debe tener al menos {MIN_LETTERS} letras."
TOO_LONG = f"El diagnóstico no puede superar los {MAX_LENGTH} caracteres."
CONTROL = "El diagnóstico tiene caracteres no permitidos."
MARKUP = "El diagnóstico no puede contener los signos < ni >."

_SPACES = re.compile(r"[ \t ]+")
_BLANK_LINES = re.compile(r"\n{3,}")


class InvalidDiagnosis(ValueError):
    """El texto no sirve como diagnóstico final; message es lo que ve el alumno."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def normalize_final_diagnosis(text: object) -> str:
    """Texto listo para registrar, o InvalidDiagnosis con el motivo en español."""
    if not isinstance(text, str):
        raise InvalidDiagnosis(MISSING)
    text = unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n")
    # Saltos de línea y tabuladores son parte de una justificación; cualquier otro carácter de control no.
    if any(unicodedata.category(char) == "Cc" and char not in "\n\t" for char in text):
        raise InvalidDiagnosis(CONTROL)
    lines = [_SPACES.sub(" ", line).strip() for line in text.split("\n")]
    text = _BLANK_LINES.sub("\n\n", "\n".join(lines)).strip()
    if not text:
        raise InvalidDiagnosis(MISSING)
    if "<" in text or ">" in text:
        raise InvalidDiagnosis(MARKUP)
    if sum(char.isalpha() for char in text) < MIN_LETTERS:
        raise InvalidDiagnosis(FEW_LETTERS)
    if len(text) > MAX_LENGTH:
        raise InvalidDiagnosis(TOO_LONG)
    return text
