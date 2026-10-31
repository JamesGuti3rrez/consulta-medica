"""Selección compartida por el simulador y el benchmark; no abre sesiones."""

from server.config import settings
from .embedded import EmbeddedRAGRetriever
from .retriever import CaseEvidenceRetriever, HttpRetriever
from .supabase import SupabasePgvectorRetriever


def build_retriever(repository, *, config=None, log_path=None):
    config = config or settings
    if config.rag_backend == "supabase_pgvector":
        return SupabasePgvectorRetriever(config.supabase_url, config.supabase_secret_key)
    if config.case_store == "supabase":
        return CaseEvidenceRetriever(repository)
    if config.rag_service_url:
        return HttpRetriever(config.rag_service_url, token=config.rag_http_token)
    if config.rag_backend != "local":
        raise ValueError(f"RAG_BACKEND no reconocido: {config.rag_backend!r} (use local o supabase_pgvector).")
    if config.rag_embedded_enabled and config.case_store == "local":
        embedded = EmbeddedRAGRetriever(
            config.rag_index_dir, log_path or config.rag_log_path, repository=repository,
        )
        if embedded.ready:
            return embedded
    return CaseEvidenceRetriever(repository)
