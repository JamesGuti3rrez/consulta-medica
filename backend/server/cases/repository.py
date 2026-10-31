"""Repositorio de casos canónicos para el sistema multiagente.

Adaptado de la rama Rodrigo (9493e8b): valida con el mismo esquema y las mismas reglas cruzadas
que el catálogo (validator.py y rules.py) en lugar de un validador propio.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

from .catalog import CURATED_CASES_DIR
from .rules import check_case_rules
from .validator import validate_case_document
from .consistency import ensure_presentable

# Mismo patrón que case_id en schemas/caso.schema.json. El ID llega del cliente y se usa como
# nombre de archivo: cualquier otra forma (por ejemplo, con «../») se trata como inexistente.
CASE_ID_PATTERN = re.compile(r"^[A-Z]{3,5}-\d{3}$")


class CaseNotFound(KeyError):
    pass


class CaseNotAvailable(ValueError):
    pass


class CaseValidationError(ValueError):
    pass


class CanonicalCaseRepository:
    """Lee casos válidos de una carpeta y entrega solo los estados habilitados explícitamente."""

    def __init__(
        self,
        cases_dir: Path | str = CURATED_CASES_DIR,
        schema_path: Path | str | None = None,
        *,
        accepted_statuses: tuple[str, ...] = ("curado",),
    ):
        invalid_statuses = set(accepted_statuses) - {"curado", "validado"}
        if invalid_statuses:
            raise ValueError(f"Estados de caso no permitidos: {sorted(invalid_statuses)}")
        self.cases_dir = Path(cases_dir)
        self.schema_path = schema_path
        self.accepted_statuses = frozenset(accepted_statuses)

    def list_curated(self) -> list[str]:
        result: list[str] = []
        for path in sorted(self.cases_dir.glob("*.json")):
            try:
                case = self._load(path)
            except (CaseValidationError, ValueError):
                continue
            if case.get("status") in self.accepted_statuses:
                result.append(str(case["case_id"]))
        return result

    def get_case(self, case_id: str) -> dict[str, Any]:
        if not isinstance(case_id, str) or not CASE_ID_PATTERN.fullmatch(case_id):
            raise CaseNotFound(case_id)
        path = self.cases_dir / f"{case_id}.json"
        if not path.exists():
            raise CaseNotFound(case_id)
        case = self._load(path)
        if case.get("status") not in self.accepted_statuses:
            raise CaseNotAvailable(case_id)
        return copy.deepcopy(case)

    def get_conversation_case(self, case_id: str) -> dict[str, Any]:
        """Devuelve solo los metadatos, public y on_request. Nunca protected."""
        case = self.get_case(case_id)
        return {
            "schema_version": case["schema_version"],
            "case_id": case["case_id"],
            "title": case["title"],
            "specialty": case["specialty"],
            "language": case["language"],
            "status": case["status"],
            "public": copy.deepcopy(case["public"]),
            "on_request": copy.deepcopy(case["on_request"]),
        }

    def get_protected(self, case_id: str) -> dict[str, Any]:
        """Acceso restringido: solo para engine/safety y engine/evaluation."""
        return copy.deepcopy(self.get_case(case_id)["protected"])

    def _load(self, path: Path) -> dict[str, Any]:
        case = json.loads(path.read_text(encoding="utf-8"))
        try:
            validate_case_document(case, self.schema_path)
        except Exception as exc:
            raise CaseValidationError(f"{path.name}: no cumple el esquema: {exc}") from exc
        errors = check_case_rules(case)
        if errors:
            raise CaseValidationError(f"{path.name}: incumple reglas cruzadas: {errors}")
        try:
            ensure_presentable(case)
        except ValueError as exc:
            raise CaseValidationError(str(exc)) from exc
        return case
