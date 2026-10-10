"""Generación de embeddings para el RAG: `local_hash` (reproducible, para pruebas) o `sentence_transformers` (semántico)."""

from .provider import EmbeddingMetadata, EmbeddingProvider, get_embedding_provider

__all__ = ["EmbeddingMetadata", "EmbeddingProvider", "get_embedding_provider"]
