"""Entorno HTTP aislado; los proveedores adversariales se inyectan solo en pruebas."""
from __future__ import annotations

from dataclasses import replace
import json
import hashlib
import os
from pathlib import Path

from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest

from server.api import ai
from server.auth import AuthUser
from server.ai.llm.gateway import LLMGateway
from server.ai.llm.providers import LocalDevelopmentProvider
from server.cases.catalog import CURATED_CASES_DIR
from server.main import app
from server.orchestration.store import InMemorySessionStore

ROOT = Path(__file__).resolve().parents[3]


class TestAuth:
    def verify(self, token):
        if token not in {"alumno-a", "alumno-b"}:
            raise HTTPException(401, "Credencial inválida.")
        return AuthUser(id=token, email=token + "@example.com", role="alumno")


@pytest.fixture
def api(monkeypatch, tmp_path):
    monkeypatch.setattr(ai, "settings", replace(ai.settings, case_store="local", session_store="memoria",
        rag_backend="local", rag_embedded_enabled=False, rag_service_url="", history_enabled=False,
        synthetic_case_data=False, synthetic_exam_data=False, langsmith_tracing=False, trace_path=tmp_path / "traces.jsonl"))
    monkeypatch.setattr(ai, "CASES_DIR", CURATED_CASES_DIR)
    monkeypatch.setattr(ai, "STORE", InMemorySessionStore())
    monkeypatch.setattr(ai, "build_gateway", lambda: LLMGateway([LocalDevelopmentProvider()]))
    monkeypatch.setattr(ai, "get_session_auth", lambda: TestAuth())
    ai.get_service.cache_clear()
    ai.get_attempts.cache_clear()
    ai.get_diagnoses.cache_clear()
    with TestClient(app) as client:
        yield client, ai.get_service(), tmp_path
    ai.get_service.cache_clear()
    ai.get_attempts.cache_clear()
    ai.get_diagnoses.cache_clear()


def start(client, case_id="MED-008", token=None):
    response = client.post("/api/ai/sessions", json={"case_id": case_id},
                           headers={"Authorization": "Bearer " + token} if token else {})
    assert response.status_code == 200, response.text
    body = response.json()
    headers = {"Authorization": "Bearer " + token} if token else {"X-Session-Token": body["session_token"]}
    return body["session_id"], headers


def ask(client, sid, headers, message):
    response = client.post(f"/api/ai/sessions/{sid}/message", headers=headers, json={"message": message})
    assert response.status_code == 200, response.text
    return response.json()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when == "call" and os.getenv("SPRINT2_EVIDENCIA"):
        task = item.module.TASK
        folder = Path(os.environ["SPRINT2_EVIDENCIA"]) / task / "resultados"
        folder.mkdir(parents=True, exist_ok=True)
        result = {"id": task, "prueba": item.name, "resultado": "PASA" if report.passed else "FALLA",
                  "duracion_s": round(report.duration, 4), "entorno": "HTTP local y proveedores controlados"}
        name = item.originalname[:60] + "_" + hashlib.sha256(item.nodeid.encode()).hexdigest()[:10]
        (folder / (name + ".json")).write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
