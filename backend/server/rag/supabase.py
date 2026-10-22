from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Iterable, Sequence

import httpx

from server.ai.embeddings import get_embedding_provider
from server.domain import AgentRole
from server.rag.port import RetrievedEvidence

if TYPE_CHECKING:
    from case_preparation.indexing.documents import IndexDocument


RPC_NAME = "buscar_evidencias_rag"


class SupabaseRAGError(RuntimeError):
    """Supabase rejected a RAG indexing or retrieval request."""


def _headers(secret_key: str, *, prefer: str | None = None) -> dict[str, str]:
    headers = {
        "apikey": secret_key,
        "Content-Type": "application/json",
    }
    if not secret_key.startswith("sb_"):
        headers["Authorization"] = f"Bearer {secret_key}"
    if prefer:
        headers["Prefer"] = prefer
    return headers


def _vector_literal(vector: Iterable[float]) -> str:
    return "[" + ",".join(format(float(value), ".9g") for value in vector) + "]"


class SupabasePgvectorRetriever:
    """Retrieves only evidence pre-authorized by engine/disclosure."""

    def __init__(
        self,
        url: str,
        secret_key: str,
        *,
        client: httpx.Client | None = None,
        timeout: float = 10.0,
    ):
        if not url or not secret_key:
            raise ValueError("RAG_BACKEND=supabase_pgvector requiere SUPABASE_URL y SUPABASE_SECRET_KEY.")
        self._base = f"{url.rstrip('/')}/rest/v1"
        self._headers = _headers(secret_key)
        self._timeout = timeout
        self._client = client or httpx.Client(timeout=timeout)
        self._provider = get_embedding_provider()

    @property
    def ready(self) -> bool:
        return True

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
        del session_id
        if not allowed_evidence_ids:
            return []
        query_vector = self._provider.embed_sync([query])[0]
        try:
            response = self._client.post(
                f"{self._base}/rpc/{RPC_NAME}",
                headers=self._headers,
                json={
                    "p_query_embedding": _vector_literal(query_vector),
                    "p_case_id": case_id,
                    "p_allowed_evidence_ids": allowed_evidence_ids,
                    "p_owner": agent_role.value,
                    "p_embedding_model": self._provider.metadata.model,
                    "p_top_k": top_k,
                },
                timeout=self._timeout,
            )
        except httpx.HTTPError as error:
            raise SupabaseRAGError(
                f"No se pudo conectar con Supabase RAG ({error.__class__.__name__})."
            ) from error
        if response.status_code >= 400:
            raise SupabaseRAGError(
                f"Supabase RAG respondió HTTP {response.status_code}: {response.text[:300]}"
            )
        try:
            rows = response.json()
        except ValueError as error:
            raise SupabaseRAGError("Supabase RAG devolvió una respuesta JSON inválida.") from error
        if not isinstance(rows, list):
            raise SupabaseRAGError("Supabase RAG devolvió un formato de respuesta inesperado.")

        allowlist = set(allowed_evidence_ids)
        results = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            evidence_id = row.get("evidence_id")
            if not isinstance(evidence_id, str) or evidence_id not in allowlist:
                continue
            try:
                results.append(
                    RetrievedEvidence(
                        evidence_id=evidence_id,
                        text=str(row.get("content", "")),
                        score=float(row.get("score", 0.0)),
                    )
                )
            except (TypeError, ValueError) as error:
                raise SupabaseRAGError("Supabase RAG devolvió un resultado inválido.") from error
        return results


def index_documents_in_supabase(
    url: str,
    secret_key: str,
    documents: Sequence[IndexDocument],
    *,
    client: httpx.Client | None = None,
    batch_size: int = 100,
) -> int:
    """Upserts safe documents from the validated offline case catalog."""
    if not url or not secret_key:
        raise ValueError("Indexar en Supabase requiere SUPABASE_URL y SUPABASE_SECRET_KEY.")
    if batch_size < 1 or batch_size > 500:
        raise ValueError("batch_size debe estar entre 1 y 500.")
    provider = get_embedding_provider()
    http = client or httpx.Client(timeout=30.0)
    base = f"{url.rstrip('/')}/rest/v1/rag_evidencias"
    headers = _headers(secret_key, prefer="resolution=merge-duplicates,return=minimal")
    count = 0

    for start in range(0, len(documents), batch_size):
        batch = documents[start:start + batch_size]
        vectors = provider.embed_sync([document.text for document in batch])
        rows = []
        for document, vector in zip(batch, vectors):
            if document.case_id is None or not document.source_id:
                continue
            rows.append(
                {
                    "case_id": document.case_id,
                    "evidence_id": document.source_id,
                    "owner": document.role,
                    "category": document.category,
                    "requires": list(document.requires),
                    "content": document.text,
                    "embedding": _vector_literal(vector),
                    "embedding_model": provider.metadata.model,
                    "source_hash": hashlib.sha256(document.text.encode("utf-8")).hexdigest(),
                }
            )
        if not rows:
            continue
        try:
            response = http.post(
                base,
                params={"on_conflict": "case_id,evidence_id"},
                headers=headers,
                json=rows,
                timeout=30.0,
            )
        except httpx.HTTPError as error:
            raise SupabaseRAGError(
                f"No se pudo conectar con Supabase al cargar evidencia ({error.__class__.__name__})."
            ) from error
        if response.status_code >= 400:
            raise SupabaseRAGError(
                f"Supabase rechazó la carga RAG (HTTP {response.status_code}): {response.text[:300]}"
            )
        count += len(rows)
    return count
