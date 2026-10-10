from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from typing import Any

from server.ai.embeddings import EmbeddingProvider, get_embedding_provider

from .documents import IndexDocument, documents_fingerprint


LIGHTRAG_VERSION = "1.5.7"


async def _local_embedding(texts: list[str]) -> Any:
    """Compatibilidad con pruebas/implementaciones anteriores."""
    return await get_embedding_provider("local_hash").embed(texts)


async def _no_entity_extraction(*_args: Any, **_kwargs: Any) -> str:
    # El índice de Sprint 1 usa LightRAG en modo vectorial seguro. La extracción
    # de entidades/relaciones se habilitará solo cuando exista un LLM de RAG
    # explícitamente configurado y evaluado.
    return "<|COMPLETE|>"


def _safe_file_path(document: IndexDocument) -> str:
    digest = hashlib.sha256(document.document_id.encode("utf-8")).hexdigest()[:16]
    return f"evidence-{digest}.txt"


def _catalog_payload(
    documents: tuple[IndexDocument, ...],
    provider: EmbeddingProvider,
) -> dict[str, Any]:
    vectors = provider.embed_sync([document.text for document in documents])
    return {
        "format_version": 1,
        "embedding": provider.metadata.as_dict(),
        "documents": [
            {
                "document_id": document.document_id,
                "source_id": document.source_id,
                "case_id": document.case_id,
                "role": document.role,
                "category": document.category,
                "requires": list(document.requires),
                "specialty": document.specialty,
                "title": document.title,
                "text": document.text,
                "file_path": _safe_file_path(document),
                "vector": [float(value) for value in vectors[index].tolist()],
            }
            for index, document in enumerate(documents)
        ],
    }


async def index_documents(documents: tuple[IndexDocument, ...], output_dir: Path) -> Path:
    if not documents:
        raise ValueError("No hay documentos seguros y autorizados para indexar.")
    documents = tuple(sorted(documents, key=lambda item: item.document_id))
    if len({document.document_id for document in documents}) != len(documents):
        raise ValueError("Hay document_id duplicados en la entrada del índice.")

    try:
        from importlib.metadata import PackageNotFoundError, version

        installed_version = version("lightrag-hku")
        if installed_version != LIGHTRAG_VERSION:
            raise RuntimeError(
                f"Se requiere lightrag-hku=={LIGHTRAG_VERSION}; está instalado {installed_version}."
            )
        from lightrag import LightRAG
        from lightrag.utils import EmbeddingFunc
    except PackageNotFoundError as error:
        raise RuntimeError(
            "Instale la dependencia opcional del pipeline: pip install -e \".[indexing]\"."
        ) from error
    except ImportError as error:
        raise RuntimeError("No está disponible la dependencia opcional lightrag-hku.") from error

    provider = get_embedding_provider()
    document_fingerprint = documents_fingerprint(documents)
    fingerprint_payload = json.dumps(
        {
            "documents": document_fingerprint,
            "embedding": provider.metadata.as_dict(),
            "backend": "lightrag-hku",
            "backend_version": LIGHTRAG_VERSION,
            "format_version": 2,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    fingerprint = hashlib.sha256(fingerprint_payload.encode("utf-8")).hexdigest()
    destination = output_dir / fingerprint
    manifest_path = destination / "manifest.json"
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        if (
            existing.get("fingerprint") == fingerprint
            and existing.get("format_version") == 2
            and (destination / "retrieval_catalog.json").exists()
        ):
            return destination
        raise RuntimeError(
            f"Existe un índice incompatible en {destination}; elimínelo y regenere el índice."
        )

    store_dir = destination / "store"
    store_dir.mkdir(parents=True, exist_ok=True)

    # Un documento por partición. Esto permite que el runtime abra únicamente
    # particiones correspondientes a evidence_id ya autorizados; LightRAG nunca
    # necesita consultar una partición que contenga evidencia no permitida.
    partition_manifest: list[dict[str, Any]] = []
    for document in documents:
        partition_id = hashlib.sha256(document.document_id.encode("utf-8")).hexdigest()[:16]
        partition_dir = store_dir / f"partition-{partition_id}"
        partition_dir.mkdir(parents=True, exist_ok=True)
        rag = LightRAG(
            working_dir=str(partition_dir),
            embedding_func=EmbeddingFunc(
                embedding_dim=provider.dimension,
                max_token_size=2048,
                func=provider.embed,
            ),
            llm_model_func=_no_entity_extraction,
            chunk_token_size=512,
            chunk_overlap_token_size=64,
        )
        await rag.initialize_storages()
        try:
            light_rag_document_id = hashlib.sha256(
                document.document_id.encode("utf-8")
            ).hexdigest()
            await rag.ainsert(
                document.text,
                ids=[light_rag_document_id],
                file_paths=[_safe_file_path(document)],
            )
        finally:
            await rag.finalize_storages()

        partition_manifest.append(
            {
                "id": partition_id,
                "scope_id": document.case_id or f"knowledge:{document.source_id}",
                "case_id": document.case_id,
                "role": document.role,
                "category": document.category,
                "requires": list(document.requires),
                "document_ids": [document.document_id],
                "source_ids": [document.source_id],
                "file_path": _safe_file_path(document),
            }
        )

    catalog = _catalog_payload(documents, provider)
    (destination / "retrieval_catalog.json").write_text(
        json.dumps(catalog, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    manifest = {
        "format_version": 2,
        "fingerprint": fingerprint,
        "documents_fingerprint": document_fingerprint,
        "backend": "lightrag-hku",
        "backend_version": LIGHTRAG_VERSION,
        "retrieval_contract": "case_id+allowed_evidence_ids",
        "embedding": provider.metadata.as_dict(),
        "llm": "disabled-empty-entity-extraction",
        "runtime_mode": "secure-vector-catalog-with-lightrag-partitions",
        "documents": [
            {
                "id": document.document_id,
                "source_id": document.source_id,
                "case_id": document.case_id,
                "role": document.role,
                "category": document.category,
                "requires": list(document.requires),
                "specialty": document.specialty,
                "title": document.title,
                "file_path": _safe_file_path(document),
            }
            for document in documents
        ],
        "partitions": partition_manifest,
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return destination


def run_index(documents: tuple[IndexDocument, ...], output_dir: Path) -> Path:
    return asyncio.run(index_documents(documents, output_dir))
