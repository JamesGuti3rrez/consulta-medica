from __future__ import annotations

from pathlib import Path

from server.domain import AgentRole
from server.rag.port import RetrievedEvidence
from server.rag.service import RAGService


class EmbeddedRAGRetriever:
    """Adaptador in-process al runtime RAG del mismo repositorio.

    Mantiene el mismo contrato que HttpRetriever, pero evita un segundo proceso
    cuando SMA y RAG se despliegan juntos. La autorización sigue llegando desde
    engine/disclosure mediante allowed_evidence_ids.
    """

    def __init__(self, index_root: Path, log_path: Path):
        self.service = RAGService(index_root, log_path)

    @property
    def ready(self) -> bool:
        return bool(self.service.health().get("ready"))

    def retrieve(
        self,
        *,
        query: str,
        case_id: str,
        agent_role: AgentRole,
        allowed_evidence_ids: list[str],
        top_k: int = 3,
        session_id: str | None = None,
    ) -> list[RetrievedEvidence]:
        results = self.service.evidence_search(
            query=query,
            case_id=case_id,
            allowed_evidence_ids=allowed_evidence_ids,
            owner=agent_role.value,
            top_k=top_k,
            min_score=0.0,
            session_id=session_id,
            agent=agent_role.value,
        )
        return [
            RetrievedEvidence(
                evidence_id=result.evidence_id,
                text=result.text,
                score=result.score,
            )
            for result in results
        ]
