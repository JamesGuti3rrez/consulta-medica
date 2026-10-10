from __future__ import annotations

import httpx
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from server.ai.embeddings import get_embedding_provider

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
        session_id: str | None = None,
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

    def __init__(self, base_url: str, timeout: float = 10.0, token: str = ""):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.token = token

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
        response = httpx.post(
            f"{self.base_url}/api/v1/rag/evidence/search",
            json={
                "query": query,
                "case_id": case_id,
                "allowed_evidence_ids": allowed_evidence_ids,
                "owner": agent_role.value,
                "top_k": top_k,
                "session_id": session_id,
                "agent": agent_role.value,
            },
            headers={"X-RAG-Token": self.token},
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


class RAGNotReadyError(RuntimeError):
    pass


class RAGContractError(ValueError):
    pass


@dataclass(frozen=True)
class RetrievalResult:
    evidence_id: str
    text: str
    score: float
    case_id: str | None
    role: str
    category: str
    requires: tuple[str, ...]
    specialty: str = ""
    title: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "text": self.text,
            "score": self.score,
            "case_id": self.case_id,
            "role": self.role,
            "category": self.category,
            "requires": list(self.requires),
            "specialty": self.specialty,
            "title": self.title,
        }


@dataclass(frozen=True)
class IndexSnapshot:
    index_dir: Path
    fingerprint: str
    backend: str
    backend_version: str
    runtime_mode: str
    embedding: dict[str, Any]
    documents: tuple[dict[str, Any], ...]


def _latest_index(index_root: Path) -> Path:
    candidates = [
        item
        for item in index_root.iterdir()
        if item.is_dir()
        and (item / "manifest.json").exists()
        and (item / "retrieval_catalog.json").exists()
    ] if index_root.exists() else []
    if not candidates:
        raise RAGNotReadyError(
            f"No hay índice RAG listo en {index_root}. Ejecute: python -m case_preparation index"
        )
    return max(candidates, key=lambda item: (item.stat().st_mtime_ns, item.name))


def load_snapshot(index_root: Path) -> IndexSnapshot:
    index_dir = _latest_index(index_root)
    manifest = json.loads((index_dir / "manifest.json").read_text(encoding="utf-8"))
    catalog = json.loads((index_dir / "retrieval_catalog.json").read_text(encoding="utf-8"))
    if manifest.get("fingerprint") != index_dir.name:
        raise RAGNotReadyError("El fingerprint del manifiesto no coincide con el directorio del índice.")
    if manifest.get("format_version") != 2:
        raise RAGNotReadyError(
            "El índice existente usa un formato anterior. Regenérelo con: python -m case_preparation index"
        )
    if catalog.get("embedding") != manifest.get("embedding"):
        raise RAGNotReadyError("Metadatos de embeddings inconsistentes entre manifiesto y catálogo.")
    documents = catalog.get("documents")
    if not isinstance(documents, list) or not documents:
        raise RAGNotReadyError("El catálogo de recuperación está vacío o es inválido.")
    dimension = manifest.get("embedding", {}).get("dimension")
    if not isinstance(dimension, int) or dimension <= 0:
        raise RAGNotReadyError("Dimensión de embeddings inválida en el manifiesto.")
    for document in documents:
        vector = document.get("vector") if isinstance(document, dict) else None
        if not isinstance(vector, list) or len(vector) != dimension:
            raise RAGNotReadyError("Vector inválido en retrieval_catalog.json.")
    return IndexSnapshot(
        index_dir=index_dir,
        fingerprint=str(manifest["fingerprint"]),
        backend=str(manifest.get("backend", "unknown")),
        backend_version=str(manifest.get("backend_version", "unknown")),
        runtime_mode=str(manifest.get("runtime_mode", "unknown")),
        embedding=dict(manifest["embedding"]),
        documents=tuple(documents),
    )


def _cosine_score(query_vector: np.ndarray, document_vector: list[float]) -> float:
    vector = np.asarray(document_vector, dtype=np.float32)
    if vector.ndim != 1 or query_vector.ndim != 1 or len(vector) != len(query_vector):
        return -1.0
    # Los proveedores actuales normalizan. Se mantiene la fórmula completa para
    # tolerar índices futuros que no lo hagan.
    denominator = float(np.linalg.norm(query_vector) * np.linalg.norm(vector))
    if denominator == 0.0:
        return 0.0
    return float(np.dot(query_vector, vector) / denominator)


class SecureRAGRetriever:
    """Recuperación semántica con prefiltrado de autorización.

    El RAG NO decide autorización. `allowed_evidence_ids` llega calculado por
    engine/disclosure del orquestador. El retriever solo busca dentro de esa lista.
    """

    def __init__(self, index_root: Path):
        self.index_root = index_root
        self._snapshot: IndexSnapshot | None = None

    def reload(self) -> IndexSnapshot:
        self._snapshot = load_snapshot(self.index_root)
        return self._snapshot

    @property
    def snapshot(self) -> IndexSnapshot:
        if self._snapshot is None:
            self._snapshot = load_snapshot(self.index_root)
        return self._snapshot

    def status(self) -> dict[str, Any]:
        try:
            snapshot = self.snapshot
        except RAGNotReadyError as error:
            return {"ready": False, "detail": str(error)}
        case_ids = sorted({doc["case_id"] for doc in snapshot.documents if doc.get("case_id")})
        knowledge = [doc for doc in snapshot.documents if doc.get("case_id") is None]
        return {
            "ready": True,
            "backend": snapshot.backend,
            "backend_version": snapshot.backend_version,
            "runtime_mode": snapshot.runtime_mode,
            "fingerprint": snapshot.fingerprint,
            "index_dir": str(snapshot.index_dir),
            "embedding": snapshot.embedding,
            "documents": len(snapshot.documents),
            "cases": len(case_ids),
            "knowledge_documents": len(knowledge),
        }

    def _query_vector(self, query: str) -> np.ndarray:
        snapshot = self.snapshot
        clean = query.strip()
        if not clean:
            raise RAGContractError("query no puede estar vacío.")
        metadata = snapshot.embedding
        provider = get_embedding_provider(
            backend=str(metadata.get("backend")),
            model=str(metadata.get("model")),
            dimension=int(metadata.get("dimension")),
        )
        vectors = provider.embed_sync([clean])
        return np.asarray(vectors[0], dtype=np.float32)

    def _rank(
        self,
        query: str,
        documents: Iterable[dict[str, Any]],
        *,
        top_k: int,
        min_score: float,
    ) -> list[RetrievalResult]:
        if top_k < 1 or top_k > 20:
            raise RAGContractError("top_k debe estar entre 1 y 20.")
        if not -1.0 <= min_score <= 1.0:
            raise RAGContractError("min_score debe estar entre -1 y 1.")
        query_vector = self._query_vector(query)
        ranked: list[RetrievalResult] = []
        for document in documents:
            score = _cosine_score(query_vector, document["vector"])
            if score < min_score:
                continue
            ranked.append(
                RetrievalResult(
                    evidence_id=str(document["source_id"]),
                    text=str(document["text"]),
                    score=round(score, 6),
                    case_id=document.get("case_id"),
                    role=str(document.get("role", "")),
                    category=str(document.get("category", "")),
                    requires=tuple(document.get("requires") or ()),
                    specialty=str(document.get("specialty", "")),
                    title=str(document.get("title", "")),
                )
            )
        ranked.sort(key=lambda item: (-item.score, item.evidence_id))
        return ranked[:top_k]

    def search_evidence(
        self,
        *,
        query: str,
        case_id: str,
        allowed_evidence_ids: list[str],
        owner: str | None = None,
        category: str | None = None,
        top_k: int = 3,
        min_score: float = 0.0,
    ) -> list[RetrievalResult]:
        case_id = case_id.strip()
        if not case_id:
            raise RAGContractError("case_id es obligatorio.")
        if allowed_evidence_ids is None:
            raise RAGContractError("allowed_evidence_ids es obligatorio.")
        if len(set(allowed_evidence_ids)) != len(allowed_evidence_ids):
            raise RAGContractError("allowed_evidence_ids no debe contener duplicados.")
        foreign = [item for item in allowed_evidence_ids if not item.startswith(f"{case_id}.")]
        if foreign:
            raise RAGContractError(
                "allowed_evidence_ids contiene evidencia de otro caso: " + ", ".join(foreign[:3])
            )
        if not allowed_evidence_ids:
            return []

        allow = set(allowed_evidence_ids)
        candidates = [
            document
            for document in self.snapshot.documents
            if document.get("case_id") == case_id
            and document.get("source_id") in allow
            and (owner is None or document.get("role") == owner)
            and (category is None or document.get("category") == category)
        ]
        # IDs autorizados que aún no están indexados no se convierten en permiso implícito.
        # Se ignoran; jamás se amplía el conjunto de candidatos.
        return self._rank(query, candidates, top_k=top_k, min_score=min_score)

    def search_cases(
        self,
        *,
        query: str,
        specialty: str | None = None,
        top_k: int = 5,
        min_score: float = 0.0,
    ) -> list[RetrievalResult]:
        candidates = [
            document
            for document in self.snapshot.documents
            if document.get("case_id") is not None
            and document.get("role") == "public"
            and (specialty is None or document.get("specialty") == specialty)
        ]
        return self._rank(query, candidates, top_k=top_k, min_score=min_score)

    def search_knowledge(
        self,
        *,
        query: str,
        scope: str = "conversation",
        top_k: int = 3,
        min_score: float = 0.0,
    ) -> list[RetrievalResult]:
        if scope not in {"conversation", "evaluation"}:
            raise RAGContractError("scope debe ser conversation o evaluation.")
        role = f"knowledge:{scope}"
        candidates = [
            document
            for document in self.snapshot.documents
            if document.get("case_id") is None and document.get("role") == role
        ]
        return self._rank(query, candidates, top_k=top_k, min_score=min_score)
