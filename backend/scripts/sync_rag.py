"""Sincroniza los casos remotos y activa pgvector únicamente tras verificar el índice y la RPC."""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
from dotenv import set_key

from case_preparation.indexing.documents import build_case_documents
from server.ai.embeddings import get_embedding_provider
from server.config import ROOT_DIR, settings
from server.domain import AgentRole
from server.persistence.teaching import TeachingStore, TeachingStoreError
from server.rag.catalog_sync import synchronize_catalog
from server.rag.supabase import SupabasePgvectorRetriever


def find_staff_id(email, url, headers):
    page = 1
    with httpx.Client(timeout=20) as client:
        while True:
            response = client.get(url.rstrip("/") + "/auth/v1/admin/users",
                                  headers=headers, params={"page": page, "per_page": 100})
            if response.is_error:
                raise ValueError("No se pudo comprobar la cuenta docente.")
            users = response.json().get("users", [])
            for user in users:
                if (user.get("email") or "").casefold() == email.strip().casefold():
                    if (user.get("app_metadata") or {}).get("rol") not in {"profesor", "administrativo"}:
                        raise ValueError("La cuenta no tiene rol docente.")
                    return user["id"]
            if len(users) < 100:
                raise ValueError("No se encontró la cuenta docente.")
            page += 1


def verify_index(store):
    cases = store.cases.list_cases()
    documents = build_case_documents(cases)
    expected = {(item.case_id, item.source_id): item for item in documents}
    rows = []
    while True:
        page = store.request("GET", "/rag_evidencias", params={
            "select": "case_id,evidence_id,source_hash,embedding_model", "order": "case_id.asc,evidence_id.asc",
            "limit": 100, "offset": len(rows),
        })
        if not page:
            break
        rows.extend(page)
    indexed = {(item["case_id"], item["evidence_id"]): item for item in rows}
    model = get_embedding_provider().metadata.model
    for key, document in expected.items():
        row = indexed.get(key)
        if row is None or row["source_hash"] != hashlib.sha256(document.text.encode("utf-8")).hexdigest() or row["embedding_model"] != model:
            raise ValueError("El índice no coincide con todos los casos actuales. No se activó pgvector.")
    # Comprobar la RPC real, además de la existencia de filas en la tabla.
    sample = next((item for item in documents if item.role == "laboratorio"), None)
    if sample is None:
        raise ValueError("No se encontró una evidencia de laboratorio para comprobar la recuperación.")
    retriever = SupabasePgvectorRetriever(settings.supabase_url, settings.supabase_secret_key)
    results = retriever.retrieve(query=sample.text, case_id=sample.case_id, agent_role=AgentRole.LABORATORIO,
                                 allowed_evidence_ids=[sample.source_id], top_k=1)
    if not results or results[0].evidence_id != sample.source_id:
        raise ValueError("La RPC no recuperó la evidencia de control. No se activó pgvector.")
    return len(cases), len(expected)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--activate", action="store_true")
    args = parser.parse_args()
    try:
        store = TeachingStore(settings.supabase_url, settings.supabase_secret_key)
        user_id = find_staff_id(args.email, settings.supabase_url, store.headers)
        result = synchronize_catalog(store, user_id=user_id)
        count, evidence_count = verify_index(store)
        print(f"Sincronización verificada: {count} casos, {evidence_count} evidencias y RPC pgvector operativa.")
        print(f"Lotes procesados: {result['lotes']}. Los documentos curados y los datos adicionales se conservaron.")
        if args.activate:
            set_key(str(ROOT_DIR / ".env"), "RAG_BACKEND", "supabase_pgvector")
            print("RAG_BACKEND=supabase_pgvector guardado en .env. Reinicia el servidor con npm start.")
        return 0
    except (TeachingStoreError, ValueError, httpx.HTTPError) as exc:
        print(f"Sincronización detenida: {exc}. No se cambió RAG_BACKEND.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

