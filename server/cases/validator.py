from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


class CaseValidationError(ValueError):
    pass


class CaseValidator:
    """Valida el contrato JSON y reglas cruzadas que el esquema no puede expresar."""

    def __init__(self, schema_path: Path):
        self.schema_path = schema_path
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        self._validator = Draft202012Validator(schema, format_checker=FormatChecker())

    def validate(self, case: dict[str, Any]) -> None:
        errors = sorted(self._validator.iter_errors(case), key=lambda e: list(e.path))
        if errors:
            first = errors[0]
            path = ".".join(str(p) for p in first.path) or "<root>"
            raise CaseValidationError(f"JSON Schema inválido en {path}: {first.message}")

        case_id = str(case["case_id"])
        evidence_ids = self._all_evidence_ids(case)
        if len(evidence_ids) != len(set(evidence_ids)):
            raise CaseValidationError("Hay evidence_id duplicados.")
        bad_prefix = [eid for eid in evidence_ids if not eid.startswith(case_id + ".")]
        if bad_prefix:
            raise CaseValidationError(f"evidence_id ajeno al caso: {bad_prefix[0]}")

        known = set(evidence_ids)
        for differential in case["protected"]["differentials"]:
            for eid in differential["discard_evidence_ids"]:
                if eid not in known:
                    raise CaseValidationError(f"discard_evidence_id inexistente: {eid}")
        for item in case["protected"]["evaluation"]["key_questions"]:
            for eid in item["evidence_ids"]:
                if eid not in known:
                    raise CaseValidationError(f"evaluation.evidence_id inexistente: {eid}")

    @staticmethod
    def _all_evidence_ids(case: dict[str, Any]) -> list[str]:
        public = case["public"]
        ids = [public["chief_complaint"]["evidence_id"]]
        ids.extend(item["evidence_id"] for item in public["items"])
        ids.extend(item["evidence_id"] for item in case["on_request"])
        return ids
