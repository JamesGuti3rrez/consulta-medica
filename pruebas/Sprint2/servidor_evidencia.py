"""Servidor de prueba local: HTTP real y proveedores controlados. No se importa desde producción."""
from __future__ import annotations

import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
for key, value in {"CASE_STORE": "local", "SESSION_STORE": "memoria", "RAG_BACKEND": "local",
                   "RAG_EMBEDDED": "false", "RAG_SERVICE_URL": "", "SYNTHETIC_CASE_DATA": "false",
                   "SYNTHETIC_EXAM_DATA": "true", "LANGSMITH_TRACING": "false", "LANGCHAIN_TRACING_V2": "false"}.items():
    os.environ[key] = value

import json
import shutil
from tempfile import TemporaryDirectory

from fastapi import HTTPException
from fastapi.staticfiles import StaticFiles
import httpx
import uvicorn

from server.api import ai, routes, teaching
from server.auth import AuthUser, get_auth
from server.ai.llm.base import LLMResult
from server.ai.llm.gateway import LLMGateway
from server.ai.llm.providers import LocalDevelopmentProvider
from server.cases.catalog import CURATED_CASES_DIR
from server.cases.repository import CanonicalCaseRepository
from server.main import app


class ControlledProvider(LocalDevelopmentProvider):
    name, model = "sprint2-controlled", "local-test-double"
    def generate(self, messages, **kwargs):
        text = messages[-1]["content"]
        if "respuesta protegida de prueba" in text:
            return LLMResult(text="Es carcinoma basocelular.", provider=self.name, model=self.model)
        return super().generate(messages, **kwargs)
    def generate_json(self, messages, **kwargs):
        payload = json.loads(messages[-1]["content"])
        values = {"leucocitos": 7000, "hemoglobina": 14.5, "hematocrito": 43} if payload["panel"] == "hemograma" else {"glucosa": 90}
        return LLMResult(text=json.dumps({"panel": payload["panel"], "values": values}), provider=self.name, model=self.model)


class ControlledAuth:
    def verify(self, token):
        if token not in {"alumno-a", "alumno-b", "docente-evidencia"}:
            raise HTTPException(401, "Credencial inválida.")
        return AuthUser(id=token, email="evidencia@example.com",
                        role="profesor" if token == "docente-evidencia" else "alumno")


class TeachingFixture:
    def __init__(self, repository):
        self.cases = repository
        self.client = httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(200, json=[])))
    def evidence(self, case_id):
        return []


def main():
    with TemporaryDirectory(prefix="sprint2-evidencia-") as directory:
        directory = Path(directory)
        for path in CURATED_CASES_DIR.glob("*.json"):
            shutil.copyfile(path, directory / path.name)
        shutil.copyfile(ROOT / "backend/tests/fixtures/cases/MED-900.json", directory / "MED-900.json")
        repository = CanonicalCaseRepository(directory)
        repository.list_cases = lambda: [repository.get_case(cid) for cid in repository.list_curated()]
        ai.CASES_DIR = directory
        ai.build_gateway = lambda: LLMGateway([ControlledProvider()])
        ai.get_session_auth = lambda: ControlledAuth()
        ai.get_service.cache_clear()
        routes.load_curated_cases = repository.list_cases
        fixture = TeachingFixture(repository)
        app.dependency_overrides[get_auth] = lambda: ControlledAuth()
        app.dependency_overrides[teaching.get_teaching_store] = lambda: fixture
        app.mount("/evidencia-sprint2", StaticFiles(directory=ROOT / "pruebas/Sprint2", html=True), name="evidencia-sprint2")
        app.router.routes.insert(0, app.router.routes.pop())
        print("SPRINT2: servidor de evidencia local; proveedores y Auth controlados; no usa Supabase ni Groq.", flush=True)
        uvicorn.run(app, host="127.0.0.1", port=3027)


if __name__ == "__main__":
    main()
