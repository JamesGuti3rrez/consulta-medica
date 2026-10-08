from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


def load_schema(schema_path: Path | str | None = None) -> dict[str, Any]:
    if schema_path is None:
        schema_path = Path(__file__).resolve().parents[3] / "schemas" / "caso.schema.json"
    with Path(schema_path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def validate_case_document(case: dict[str, Any], schema_path: Path | str | None = None) -> None:
    schema = load_schema(schema_path)
    Draft202012Validator(schema).validate(case)
