from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server.ai.embeddings import get_embedding_provider
from server.main import app
from server.rag.retriever import RAGContractError, SecureRAGRetriever
from server.rag.service import RAGService
import server.rag.router as rag_router_module


def _write_index(root: Path) -> Path:
    provider = get_embedding_provider("local_hash")
    docs = [
        {
            "document_id": "MED-001:public:MED-001.motivo.dolor",
            "source_id": "MED-001.motivo.dolor",
            "case_id": "MED-001",
            "role": "public",
            "category": "motivo",
            "requires": [],
            "specialty": "medicina_interna",
            "title": "Dolor abdominal en adulto",
            "text": "Edad 42. Dolor abdominal desde ayer.",
        },
        {
            "document_id": "MED-001:paciente:MED-001.anamnesis.inicio",
            "source_id": "MED-001.anamnesis.inicio",
            "case_id": "MED-001",
            "role": "paciente",
            "category": "anamnesis",
            "requires": ["inicio_y_evolucion"],
            "specialty": "medicina_interna",
            "title": "Dolor abdominal en adulto",
            "text": "El dolor comenzó hace un día.",
        },
        {
            "document_id": "MED-001:laboratorio:MED-001.lab.hemograma",
            "source_id": "MED-001.lab.hemograma",
            "case_id": "MED-001",
            "role": "laboratorio",
            "category": "laboratorio",
            "requires": ["hemograma"],
            "specialty": "medicina_interna",
            "title": "Dolor abdominal en adulto",
            "text": "Hemoglobina 13 g/dL.",
        },
        {
            "document_id": "knowledge-guia:knowledge:conversation:guia",
            "source_id": "guia",
            "case_id": None,
            "role": "knowledge:conversation",
            "category": "knowledge",
            "requires": [],
            "specialty": "",
            "title": "",
            "text": "Guía clínica aprobada para dolor abdominal.",
        },
    ]
    vectors = provider.embed_sync([doc["text"] for doc in docs])
    fingerprint = "a" * 64
    index_dir = root / fingerprint
    index_dir.mkdir(parents=True)
    embedding = provider.metadata.as_dict()
    manifest = {
        "format_version": 2,
        "fingerprint": fingerprint,
        "backend": "lightrag-hku",
        "backend_version": "1.5.7",
        "runtime_mode": "secure-vector-catalog-with-lightrag-partitions",
        "embedding": embedding,
        "documents": [],
        "partitions": [],
    }
    catalog = {
        "format_version": 1,
        "embedding": embedding,
        "documents": [
            {**doc, "file_path": f"doc-{idx}.txt", "vector": vectors[idx].tolist()}
            for idx, doc in enumerate(docs)
        ],
    }
    (index_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (index_dir / "retrieval_catalog.json").write_text(json.dumps(catalog), encoding="utf-8")
    return index_dir


def test_evidence_search_is_case_scoped_and_allowlist_scoped(tmp_path):
    _write_index(tmp_path)
    retriever = SecureRAGRetriever(tmp_path)

    results = retriever.search_evidence(
        query="¿cuándo comenzó el dolor?",
        case_id="MED-001",
        allowed_evidence_ids=["MED-001.anamnesis.inicio"],
        owner="paciente",
        top_k=3,
        min_score=-1.0,
    )

    assert [result.evidence_id for result in results] == ["MED-001.anamnesis.inicio"]
    assert all(result.evidence_id != "MED-001.lab.hemograma" for result in results)


def test_foreign_evidence_id_fails_closed(tmp_path):
    _write_index(tmp_path)
    retriever = SecureRAGRetriever(tmp_path)

    with pytest.raises(RAGContractError, match="otro caso"):
        retriever.search_evidence(
            query="hemograma",
            case_id="MED-001",
            allowed_evidence_ids=["PED-001.lab.hemograma"],
        )


def test_empty_allowlist_returns_no_evidence(tmp_path):
    _write_index(tmp_path)
    retriever = SecureRAGRetriever(tmp_path)

    assert retriever.search_evidence(
        query="dolor",
        case_id="MED-001",
        allowed_evidence_ids=[],
    ) == []


def test_case_and_knowledge_search_use_only_safe_partitions(tmp_path):
    _write_index(tmp_path)
    retriever = SecureRAGRetriever(tmp_path)

    cases = retriever.search_cases(
        query="dolor abdominal",
        specialty="medicina_interna",
        min_score=-1.0,
    )
    knowledge = retriever.search_knowledge(
        query="dolor abdominal",
        scope="conversation",
        min_score=-1.0,
    )

    assert [item.case_id for item in cases] == ["MED-001"]
    assert [item.evidence_id for item in knowledge] == ["guia"]


def test_http_contract_matches_multiagent_http_retriever(tmp_path, monkeypatch):
    _write_index(tmp_path)
    service = RAGService(tmp_path, tmp_path / "retrieval.jsonl")
    monkeypatch.setattr(rag_router_module, "service", service)
    client = TestClient(app)

    response = client.post(
        "/api/v1/rag/evidence/search",
        json={
            "query": "¿cuándo comenzó el dolor?",
            "case_id": "MED-001",
            "allowed_evidence_ids": ["MED-001.anamnesis.inicio"],
            "owner": "paciente",
            "top_k": 3,
            "min_score": -1.0,
            "session_id": "session-1",
            "agent": "paciente",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["results"][0]["evidence_id"] == "MED-001.anamnesis.inicio"
    assert "protected" not in json.dumps(payload).lower()
    log_path = tmp_path / "retrieval.jsonl"
    assert log_path.exists()
    log_record = json.loads(log_path.read_text(encoding="utf-8").strip())
    assert log_record["session_id"] == "session-1"
    assert log_record["agent"] == "paciente"
    assert log_record["results"][0]["evidence_id"] == "MED-001.anamnesis.inicio"
