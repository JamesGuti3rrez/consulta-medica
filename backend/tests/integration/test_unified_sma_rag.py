from pathlib import Path

from fastapi.testclient import TestClient

from server.main import app
from server.rag.embedded import EmbeddedRAGRetriever


def test_rag_routes_are_exposed_by_same_fastapi_app():
    client = TestClient(app)
    response = client.get("/api/v1/rag/health")
    assert response.status_code == 200
    assert "ready" in response.json()


def test_embedded_retriever_reports_not_ready_without_index(tmp_path):
    retriever = EmbeddedRAGRetriever(tmp_path / "indexes", tmp_path / "rag.jsonl")
    assert retriever.ready is False
