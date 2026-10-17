from __future__ import annotations

import json

import httpx

from server.ai.embeddings import get_embedding_provider
from server.domain import AgentRole
from case_preparation.indexing.documents import IndexDocument
from server.rag.supabase import (
    RPC_NAME,
    SupabasePgvectorRetriever,
    index_documents_in_supabase,
)


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_supabase_retriever_sends_case_role_and_authorized_ids(monkeypatch):
    provider = get_embedding_provider("local_hash")
    monkeypatch.setattr("server.rag.supabase.get_embedding_provider", lambda: provider)
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(
            200,
            json=[
                {
                    "evidence_id": "MED-001.anamnesis.inicio",
                    "content": "Empezó ayer.",
                    "score": 0.9,
                },
                {
                    "evidence_id": "MED-001.protected.diagnosis",
                    "content": "No debe pasar el allowlist.",
                    "score": 1.0,
                },
            ],
        )

    retriever = SupabasePgvectorRetriever(
        "https://project.supabase.co",
        "sb_secret_test",
        client=_client(handler),
    )
    results = retriever.retrieve(
        query="¿Cuándo empezó?",
        case_id="MED-001",
        agent_role=AgentRole.PACIENTE,
        allowed_evidence_ids=["MED-001.anamnesis.inicio"],
    )

    assert [result.evidence_id for result in results] == ["MED-001.anamnesis.inicio"]
    assert requests[0].url.path == f"/rest/v1/rpc/{RPC_NAME}"
    body = json.loads(requests[0].content)
    assert body["p_case_id"] == "MED-001"
    assert body["p_allowed_evidence_ids"] == ["MED-001.anamnesis.inicio"]
    assert body["p_owner"] == "paciente"
    assert body["p_embedding_model"] == provider.metadata.model
    assert body["p_query_embedding"].startswith("[")


def test_supabase_retriever_does_not_call_rpc_for_empty_allowlist(monkeypatch):
    provider = get_embedding_provider("local_hash")
    monkeypatch.setattr("server.rag.supabase.get_embedding_provider", lambda: provider)

    def unexpected_request(_request):
        raise AssertionError("RPC no debe llamarse con lista autorizada vacía")

    retriever = SupabasePgvectorRetriever(
        "https://project.supabase.co",
        "sb_secret_test",
        client=_client(unexpected_request),
    )
    assert retriever.retrieve(
        query="consulta",
        case_id="MED-001",
        agent_role=AgentRole.PACIENTE,
        allowed_evidence_ids=[],
    ) == []


def test_supabase_indexer_upserts_only_case_documents(monkeypatch):
    provider = get_embedding_provider("local_hash")
    monkeypatch.setattr("server.rag.supabase.get_embedding_provider", lambda: provider)
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(201)

    documents = (
        IndexDocument(
            document_id="MED-001:paciente:MED-001.anamnesis.inicio",
            source_id="MED-001.anamnesis.inicio",
            case_id="MED-001",
            role="paciente",
            category="anamnesis",
            requires=("inicio_y_evolucion",),
            text="Empezó ayer.",
        ),
        IndexDocument(
            document_id="knowledge:conversation:guide",
            source_id="guide",
            case_id=None,
            role="knowledge:conversation",
            category="knowledge",
            text="Guía aprobada.",
        ),
    )

    count = index_documents_in_supabase(
        "https://project.supabase.co",
        "sb_secret_test",
        documents,
        client=_client(handler),
    )

    assert count == 1
    assert len(requests) == 1
    assert requests[0].url.path == "/rest/v1/rag_evidencias"
    assert requests[0].url.params["on_conflict"] == "case_id,evidence_id"
    row = json.loads(requests[0].content)[0]
    assert row["case_id"] == "MED-001"
    assert row["evidence_id"] == "MED-001.anamnesis.inicio"
    assert row["owner"] == "paciente"
    assert row["embedding_model"] == provider.metadata.model
    assert row["embedding"].startswith("[")
