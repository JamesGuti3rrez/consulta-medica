"""Quality Gates del pipeline: deciden si un caso se acepta o se rechaza antes de guardarlo.

Reutilizan la validación de server/cases/ (esquema y reglas cruzadas); no la copian
(arquitectura del repositorio, §9.3 y regla de dependencia 6).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from jsonschema import ValidationError

from server.cases.rules import check_batch_rules, check_case_rules, check_case_warnings
from server.cases.validator import validate_case_document


@dataclass(frozen=True)
class GateResult:
    case_id: str
    errors: list[str]
    warnings: list[str]

    @property
    def accepted(self) -> bool:
        return not self.errors


def evaluate_case(case: dict[str, Any]) -> GateResult:
    """Esquema primero; si lo cumple, reglas cruzadas (bloquean) y avisos (no bloquean)."""
    case_id = str(case.get("case_id", "?"))
    try:
        validate_case_document(case)
    except ValidationError as error:
        path = "/".join(str(part) for part in error.absolute_path) or "(raíz)"
        return GateResult(case_id, [f"ESQUEMA {path}: {error.message}"], [])
    return GateResult(case_id, check_case_rules(case), check_case_warnings(case))


def evaluate_batch(cases: list[dict[str, Any]]) -> list[str]:
    """Reglas entre los casos de un lote (preguntas fuente e IDs repetidos)."""
    return check_batch_rules(cases)
