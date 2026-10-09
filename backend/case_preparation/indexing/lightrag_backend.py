from __future__ import annotations

import asyncio
import json
import hashlib
from collections import defaultdict
from pathlib import Path

from .documents import IndexDocument, documents_fingerprint
from server.rag.light_rag import (
    EMBEDDING_DIMENSION,
    LIGHTRAG_VERSION,
    local_embedding as _local_embedding,
    no_entity_extraction as _no_entity_extraction,
)


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

    fingerprint = documents_fingerprint(documents)
    destination = output_dir / fingerprint
    manifest_path = destination / "manifest.json"
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        if existing.get("fingerprint") == fingerprint:
            return destination
        raise RuntimeError(f"El manifiesto existente en {manifest_path} no coincide.")

    store_dir = destination / "store"
    groups: dict[tuple[str, str, tuple[str, ...]], list[IndexDocument]] = defaultdict(list)
    for document in documents:
        scope_id = document.case_id or f"knowledge:{document.source_id}"
        groups[(scope_id, document.role, document.requires)].append(document)

    partition_manifest = []
    for (scope_id, role, requires), group_documents in sorted(groups.items()):
        partition_key = json.dumps(
            [scope_id, role, requires], ensure_ascii=False, separators=(",", ":")
        )
        partition_id = hashlib.sha256(partition_key.encode("utf-8")).hexdigest()[:16]
        partition_dir = store_dir / f"partition-{partition_id}"
        partition_dir.mkdir(parents=True, exist_ok=True)
        rag = LightRAG(
            working_dir=str(partition_dir),
            embedding_func=EmbeddingFunc(
                embedding_dim=EMBEDDING_DIMENSION,
                max_token_size=2048,
                func=_local_embedding,
            ),
            llm_model_func=_no_entity_extraction,
            chunk_token_size=512,
            chunk_overlap_token_size=64,
        )
        await rag.initialize_storages()
        try:
            for document in sorted(group_documents, key=lambda item: item.document_id):
                light_rag_document_id = hashlib.sha256(
                    document.document_id.encode("utf-8")
                ).hexdigest()
                await rag.ainsert(
                    document.text,
                    ids=[light_rag_document_id],
                    file_paths=[light_rag_document_id],
                )
        finally:
            await rag.finalize_storages()
        partition_manifest.append(
            {
                "id": partition_id,
                "scope_id": scope_id,
                "case_id": group_documents[0].case_id,
                "role": role,
                "requires": list(requires),
                "document_ids": [
                    document.document_id
                    for document in sorted(group_documents, key=lambda item: item.document_id)
                ],
            }
        )

    manifest = {
        "format_version": 1,
        "fingerprint": fingerprint,
        "backend": "lightrag-hku",
        "backend_version": LIGHTRAG_VERSION,
        "embedding": "local-deterministic-token-hash",
        "llm": "disabled-empty-entity-extraction",
        "documents": [
            {
                "id": document.document_id,
                "role": document.role,
                "requires": list(document.requires),
                "source_id": document.source_id,
                "text_sha256": hashlib.sha256(document.text.encode("utf-8")).hexdigest(),
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
