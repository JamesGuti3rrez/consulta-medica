from __future__ import annotations

from typing import Any
from app.models import ClinicalFact
from app.routing import normalize


class ToolRegistry:
    def execute(self, role: str, question: str, case: dict[str, Any]) -> tuple[str | None, dict[str, Any], list[ClinicalFact]]:
        if role == "laboratory":
            return self._lookup("get_lab_result", case.get("laboratory_data", {}), question)
        if role == "radiology":
            return self._lookup("get_imaging_result", case.get("radiology_data", {}), question)
        if role == "patient":
            return self._lookup("get_patient_fact", case.get("patient_knowledge", {}), question)
        if role == "specialist":
            return self._lookup("get_specialist_fact", case.get("specialist_data", {}), question)
        return None, {}, []

    def _lookup(self, tool_name: str, section: dict[str, Any], question: str):
        q = normalize(question)
        flat = list(_walk(section))
        scored: list[tuple[int, dict[str, Any]]] = []
        for key, item in flat:
            score = 0
            tokens = set(normalize(key.replace("_", " ")).split()) | set(normalize(str(item.get("name", ""))).split())
            for token in tokens:
                if len(token) >= 4 and token in q:
                    score += 1
            aliases = item.get("aliases", [])
            score += sum(2 for alias in aliases if normalize(alias) in q)
            scored.append((score, item))
        scored.sort(key=lambda x: x[0], reverse=True)
        if not scored or scored[0][0] <= 0:
            return tool_name, {"query": question}, []
        item = scored[0][1]
        fact = ClinicalFact(
            evidence_id=item["evidence_id"],
            name=item.get("name", "dato"),
            value=str(item.get("value", "")),
            unit=item.get("unit"),
        )
        return tool_name, {"query": question}, [fact]


def _walk(obj: Any, prefix: str = ""):
    if isinstance(obj, dict):
        if "evidence_id" in obj and "value" in obj:
            yield prefix, obj
        for k, v in obj.items():
            if isinstance(v, (dict, list)):
                yield from _walk(v, f"{prefix} {k}".strip())
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk(v, f"{prefix} {i}".strip())
