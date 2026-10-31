from __future__ import annotations

import hashlib
import json
from pathlib import Path


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode()).hexdigest()


def validate_dataset(records, repository):
    if not isinstance(records, list) or not records:
        raise ValueError("El benchmark debe ser una lista no vacía")
    seen = set()
    for record in records:
        test_id = record["test_id"]
        if test_id in seen:
            raise ValueError("test_id duplicado")
        seen.add(test_id)
        if not isinstance(record["query"], str) or not record["query"].strip():
            raise ValueError("Consulta vacía")
        case = repository.get_conversation_case(record["case_id"])
        if case["specialty"] != record["specialty"]:
            raise ValueError(f"Especialidad incorrecta: {test_id}")
        ids = {item["evidence_id"] for item in case["on_request"]}
        expected = record["expected_evidence_ids"]
        if not isinstance(expected, list) or any(not isinstance(x, str) for x in expected):
            raise ValueError(f"Referencias inválidas: {test_id}")
        if len(expected) != len(set(expected)) or not set(expected) <= ids:
            raise ValueError(f"Referencia ausente, pública, duplicada o ajena: {test_id}")
        if record.get("case_sha256") != digest(case):
            raise ValueError(f"Caso modificado: regenere/revise las referencias de {test_id}")
        sources = record.get("reference_sources", [])
        if {source["evidence_id"] for source in sources} != set(expected):
            raise ValueError(f"Referencias sin trazabilidad: {test_id}")
        for source in sources:
            item = case["on_request"][source["on_request_index"]]
            if item["evidence_id"] != source["evidence_id"] or digest(item) != source["sha256"]:
                raise ValueError(f"Fuente modificada: {test_id}")
    return records


def load_dataset(path: Path, repository, *, limit=None):
    records = json.loads(path.read_text(encoding="utf-8"))
    if limit is not None:
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
            raise ValueError("limit debe ser un entero positivo")
        if not isinstance(records, list):
            raise ValueError("El benchmark debe ser una lista no vacía")
        records = records[:limit]
    return validate_dataset(records, repository)
