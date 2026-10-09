from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from server.cases.validator import CaseValidator


class CaseNotFound(KeyError):
    pass


class CaseNotAvailable(ValueError):
    pass


class CanonicalCaseRepository:
    """Repositorio local de casos canónicos.

    Es un adaptador temporal. James puede sustituirlo por Supabase/PostgreSQL sin
    cambiar los contratos consumidos por orchestration/, engine/ o rag/.
    """

    def __init__(self, cases_dir: Path, schema_path: Path):
        self.cases_dir = cases_dir
        self.validator = CaseValidator(schema_path)

    def list_curated(self) -> list[str]:
        result: list[str] = []
        for path in sorted(self.cases_dir.glob("*.json")):
            try:
                case = self._load(path)
            except Exception:
                continue
            if case.get("status") == "curado":
                result.append(str(case["case_id"]))
        return result

    def get_case(self, case_id: str) -> dict[str, Any]:
        resolved = self._resolve_alias(case_id)
        path = self.cases_dir / f"{resolved}.json"
        if not path.exists():
            raise CaseNotFound(case_id)
        case = self._load(path)
        if case.get("status") != "curado":
            raise CaseNotAvailable(case_id)
        return copy.deepcopy(case)

    def get_conversation_case(self, case_id: str) -> dict[str, Any]:
        """Devuelve solo metadata + public + on_request. Nunca protected."""
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
        """Acceso restringido para engine/safety y engine/evaluation."""
        return copy.deepcopy(self.get_case(case_id)["protected"])

    def _load(self, path: Path) -> dict[str, Any]:
        case = json.loads(path.read_text(encoding="utf-8"))
        self.validator.validate(case)
        return case

    def _resolve_alias(self, case_id: str) -> str:
        if case_id != "demo":
            return case_id
        curated = self.list_curated()
        if not curated:
            raise CaseNotFound(case_id)
        return curated[0]
