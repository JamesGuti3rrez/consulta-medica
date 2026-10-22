"""Reconstruye el índice desde los casos actuales de Supabase, sin modificar sus documentos."""
from __future__ import annotations

import hashlib

from case_preparation.indexing.documents import build_case_documents
from server.ai.embeddings import get_embedding_provider
from server.cases.rules import check_batch_rules
from server.persistence.teaching import TeachingStoreError
from server.rag.supabase import _vector_literal


def prepare_evidence(cases):
    documents = build_case_documents(cases)
    provider = get_embedding_provider()
    vectors = provider.embed_sync([item.text for item in documents])
    return [
        {"case_id": document.case_id, "evidence_id": document.source_id, "owner": document.role,
         "category": document.category, "requires": list(document.requires), "content": document.text,
         "embedding": _vector_literal(vector), "embedding_model": provider.metadata.model,
         "source_hash": hashlib.sha256(document.text.encode("utf-8")).hexdigest()}
        for document, vector in zip(documents, vectors, strict=True)
    ]


def synchronize_catalog(store, *, user_id: str, batch_size: int = 100):
    if not 1 <= batch_size <= 100:
        raise ValueError("El tamaño de lote debe estar entre 1 y 100.")
    cases = store.cases.list_cases()
    if not cases:
        return {"casos_sincronizados": 0, "evidencias_indexadas": 0, "lotes": 0}
    if check_batch_rules(cases):
        raise TeachingStoreError("El catálogo tiene casos duplicados o familias incompletas. Revísalo antes de sincronizar.")
    # Preparar y validar todo antes de realizar la primera escritura.
    evidence = prepare_evidence(cases)
    groups = {}
    for row in evidence:
        groups.setdefault(row["case_id"], []).append(row)
    completed = indexed = batches = 0
    for start in range(0, len(cases), batch_size):
        batch = cases[start:start + batch_size]
        rows = [row for case in batch for row in groups.get(case["case_id"], [])]
        try:
            result = store.publish(batch, rows, user_id=user_id, filename="Sincronización general del catálogo")
        except TeachingStoreError as exc:
            raise TeachingStoreError(
                f"Se sincronizaron {completed} de {len(cases)} casos antes de detenerse. "
                f"Puedes volver a intentarlo. {exc}"
            ) from exc
        if result.get("evidencias_indexadas") != len(rows):
            raise TeachingStoreError("Supabase no confirmó todas las evidencias del lote. Vuelve a sincronizar.")
        completed += len(batch)
        indexed += len(rows)
        batches += 1
    return {"casos_sincronizados": completed, "evidencias_indexadas": indexed, "lotes": batches}

