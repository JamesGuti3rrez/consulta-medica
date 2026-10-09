"""Compatibilidad temporal con el caso plano usado por el frontend existente.

El SMA nuevo no consume este formato. Se conserva hasta que el frontend migre al caso canónico.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CASE_PATH = Path(__file__).resolve().parents[2] / "data" / "caso-demo.json"
PRIVATE_FIELDS = {
    "diagnostico_correcto", "tratamiento_referencia", "errores_comunes", "diagnosticos_diferenciales"
}


def read_case() -> dict[str, Any]:
    return json.loads(CASE_PATH.read_text(encoding="utf-8"))


def public_case(clinical_case: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in clinical_case.items() if key not in PRIVATE_FIELDS}
