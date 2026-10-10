from __future__ import annotations

from server.domain import AgentRole
from server.rag.retriever import HttpRetriever


class _Response:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_http_retriever_propagates_session_and_agent(monkeypatch):
    captured = {}

    def fake_post(url, *, json, headers, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        captured["timeout"] = timeout
        return _Response(
            {
                "results": [
                    {
                        "evidence_id": "EME-001.solicitud.exploracion_fisica",
                        "text": "Exploración sin hallazgos adicionales.",
                        "score": 0.91,
                    }
                ]
            }
        )

    monkeypatch.setattr("server.rag.retriever.httpx.post", fake_post)
    retriever = HttpRetriever("http://127.0.0.1:8001", token="secreto")
    result = retriever.retrieve(
        query="Realizo exploración física",
        case_id="EME-001",
        agent_role=AgentRole.MEDICO_ASISTENTE,
        allowed_evidence_ids=["EME-001.solicitud.exploracion_fisica"],
        session_id="session-123",
    )

    assert captured["url"].endswith("/api/v1/rag/evidence/search")
    assert captured["json"]["session_id"] == "session-123"
    assert captured["json"]["agent"] == "medico_asistente"
    assert captured["json"]["owner"] == "medico_asistente"
    assert captured["headers"] == {"X-RAG-Token": "secreto"}
    assert [item.evidence_id for item in result] == ["EME-001.solicitud.exploracion_fisica"]
