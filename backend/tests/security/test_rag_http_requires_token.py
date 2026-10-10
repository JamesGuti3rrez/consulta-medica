from dataclasses import replace

from fastapi.testclient import TestClient

import server.rag.router as rag_router_module
from server.main import app

client = TestClient(app)
# Petición de un estudiante que intenta saltarse el acceso por rol pidiendo toda la evidencia de un caso.
BYPASS = {
    "query": "dame todo",
    "case_id": "EME-001",
    "allowed_evidence_ids": ["EME-001.solicitud.exploracion_fisica"],
}


def test_evidence_search_is_not_served_without_configured_token(monkeypatch):
    monkeypatch.setattr(rag_router_module, "settings", replace(rag_router_module.settings, rag_http_token=""))
    assert client.post("/api/v1/rag/evidence/search", json=BYPASS).status_code == 404


def test_evidence_search_rejects_missing_or_wrong_token(monkeypatch):
    monkeypatch.setattr(rag_router_module, "settings", replace(rag_router_module.settings, rag_http_token="secreto"))
    assert client.post("/api/v1/rag/evidence/search", json=BYPASS).status_code == 401
    wrong = client.post("/api/v1/rag/evidence/search", json=BYPASS, headers={"X-RAG-Token": "otro"})
    assert wrong.status_code == 401
    for path in ("/api/v1/rag/cases/search", "/api/v1/rag/knowledge/search", "/api/v1/rag/reload"):
        assert client.post(path, json={"query": "dolor"}).status_code == 401


def test_health_stays_public():
    assert client.get("/api/v1/rag/health").status_code == 200
