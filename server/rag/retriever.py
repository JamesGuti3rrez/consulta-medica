from __future__ import annotations

import httpx

from server.domain import AgentRole
from server.rag.port import RetrievedEvidence


class CaseEvidenceRetriever:
    """Fallback determinístico local cuando el servicio RAG aún no está conectado.

    Respeta exactamente `allowed_evidence_ids`; no hace autorización ni ve `protected`.
    """

    def __init__(self, repository):
        self.repository = repository

    def retrieve(
        self,
        *,
        query: str,
        case_id: str,
        agent_role: AgentRole,
        allowed_evidence_ids: list[str],
        top_k: int = 3,
    ) -> list[RetrievedEvidence]:
        if not allowed_evidence_ids:
            return []
        case = self.repository.get_conversation_case(case_id)
        allow = set(allowed_evidence_ids)
        result: list[RetrievedEvidence] = []
        for item in case.get("on_request", []):
            if item.get("evidence_id") not in allow:
                continue
            text = item.get("text")
            if text is None and "value" in item:
                text = f"{item['label']}: {item['value']} {item.get('unit', '')}".strip()
            result.append(
                RetrievedEvidence(
                    evidence_id=str(item["evidence_id"]),
                    text=str(text or item.get("label", "")),
                    score=1.0,
                )
            )
        return result[:top_k]


class HttpRetriever:
    """Contrato HTTP para LightRAG/pgvector u otro servicio del equipo RAG."""

    def __init__(self, base_url: str, timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def retrieve(
        self,
        *,
        query: str,
        case_id: str,
        agent_role: AgentRole,
        allowed_evidence_ids: list[str],
        top_k: int = 3,
    ) -> list[RetrievedEvidence]:
        response = httpx.post(
            f"{self.base_url}/api/v1/rag/evidence/search",
            json={
                "query": query,
                "case_id": case_id,
                "allowed_evidence_ids": allowed_evidence_ids,
                "owner": agent_role.value,
                "top_k": top_k,
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        items = payload.get("results", payload) if isinstance(payload, dict) else payload
        return [
            RetrievedEvidence(
                evidence_id=str(item.get("evidence_id") or item.get("chunk_id") or "unknown"),
                text=str(item.get("text", "")),
                score=float(item.get("score", 0.0)),
            )
            for item in items
            if str(item.get("evidence_id") or item.get("chunk_id") or "") in set(allowed_evidence_ids)
        ]
