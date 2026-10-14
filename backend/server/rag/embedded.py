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

    def __init__(self, index_root: Path, log_path: Path, repository=None):
        self.service = RAGService(index_root, log_path)
        # Con el repositorio de casos, un índice desactualizado no esconde datos autorizados (ver retrieve).
        self.repository = repository

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
            # engine/disclosure ya decidió qué datos se pueden revelar: el RAG solo los ordena. Con un
            # umbral, un dato autorizado con poca similitud (p. ej. con embeddings local_hash) se perdía.
            min_score=-1.0,
            session_id=session_id,
            agent=agent_role.value,
        )
        evidence = [
            RetrievedEvidence(
                evidence_id=result.evidence_id,
                text=result.text,
                score=result.score,
            )
            for result in results
        ]
        return self._with_current_case(evidence, case_id, allowed_evidence_ids)

    def _with_current_case(
        self, evidence: list[RetrievedEvidence], case_id: str, allowed_evidence_ids: list[str]
    ) -> list[RetrievedEvidence]:
        """Corrige un índice armado antes del último cambio de los casos.

        engine/disclosure ya autorizó allowed_evidence_ids; el índice solo ordena. Si el índice no tiene un
        dato autorizado (se agregó después) o guarda un texto que ya cambió, se usa el del caso. Nunca se
        agrega un dato fuera de allowed_evidence_ids.
        """
        if self.repository is None:
            return evidence
        items = {
            item["evidence_id"]: item
            for item in self.repository.get_conversation_case(case_id).get("on_request", [])
            if item.get("evidence_id") in allowed_evidence_ids
        }
        indexed = {
            document.get("source_id")
            for document in self.service.retriever.snapshot.documents
            if document.get("case_id") == case_id
        }
        stale = False
        fresh: list[RetrievedEvidence] = []
        for result in evidence:
            current = items.get(result.evidence_id, {}).get("text")
            if current and current not in result.text:
                stale = True
                fresh.append(RetrievedEvidence(evidence_id=result.evidence_id, text=current, score=result.score))
            else:
                fresh.append(result)
        missing = [evidence_id for evidence_id in allowed_evidence_ids
                   if evidence_id in items and evidence_id not in indexed]
        if missing:
            stale = True
            fresh.extend(
                RetrievedEvidence(evidence_id=evidence_id, text=str(items[evidence_id].get("text") or items[evidence_id]["label"]), score=1.0)
                for evidence_id in missing
            )
        if stale:
            print(f"[rag] índice desactualizado para {case_id}: se usan los datos del caso. "
                  "Reconstrúyalo con: python -m case_preparation index")
        return fresh
