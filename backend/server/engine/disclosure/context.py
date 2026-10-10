from __future__ import annotations

from typing import Any

from server.domain import AgentRole
from server.rag.port import RetrievedEvidence


class ContextAssembler:
    """Construye el único objeto clínico que puede entrar a un agente/LLM.

    No recibe ni conoce `protected`. El médico asistente puede resumir evidencia ya
    revelada al estudiante, pero no obtiene evidencia nueva por esa vía.
    """

    def build(
        self,
        *,
        case: dict[str, Any],
        role: AgentRole,
        revealed_evidence_ids: list[str],
        retrieved: list[RetrievedEvidence],
        conversation_tail: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        visible = set(revealed_evidence_ids)
        public_items: list[dict[str, Any]] = []
        complaint = case["public"]["chief_complaint"]
        if complaint["evidence_id"] in visible:
            public_items.append(self._compact(complaint))
        for item in case["public"].get("items", []):
            if item["evidence_id"] in visible:
                public_items.append(self._compact(item))

        previously_revealed: list[dict[str, Any]] = []
        if role == AgentRole.MEDICO_ASISTENTE:
            for item in case.get("on_request", []):
                if item["evidence_id"] in visible:
                    previously_revealed.append(self._compact(item))

        return {
            "role": role.value,
            "case_id": case["case_id"],
            "case_title": case["title"],
            "public_evidence": public_items,
            "revealed_evidence": previously_revealed,
            "retrieved_evidence": [
                {
                    "evidence_id": item.evidence_id,
                    "text": item.text,
                    "score": item.score,
                }
                for item in retrieved
            ],
            "conversation_tail": list((conversation_tail or [])[-4:]),
        }

    @staticmethod
    def _compact(item: dict[str, Any]) -> dict[str, Any]:
        result = {
            "evidence_id": item["evidence_id"],
            "label": item["label"],
            "category": item["category"],
        }
        for key in ("text", "value", "unit", "interpretation"):
            if key in item:
                result[key] = item[key]
        return result
