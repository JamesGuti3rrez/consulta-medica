"""Consulta simulada contra la API del sistema multiagente (/api/ai), sin clave de LLM.

1. Caso de prueba MED-900 (backend/tests/fixtures/cases): tiene datos en on_request para los cinco roles.
2. EME-001 del catálogo curado, con el índice LightRAG construido por `case_preparation index`.

Uso, desde backend/:  .venv\\Scripts\\python.exe ..\\pruebas\\07_integracion_sma_rag\\06_orquestador\\consulta_simulada.py
"""

import logging
import sys
from dataclasses import replace
from pathlib import Path

from fastapi.testclient import TestClient

import server.api.ai as ai
from server.main import app

logging.disable(logging.CRITICAL)
sys.stdout.reconfigure(encoding="utf-8")
FIXTURES = Path(__file__).resolve().parents[3] / "backend" / "tests" / "fixtures" / "cases"

GUIONES = {
    "MED-900": [
        "¿Desde cuándo comenzó el dolor?",
        "¿Le molesta la luz?",
        "Voy a examinar al paciente: examen neurológico",
        "Solicito un hemograma",
        "Pido una tomografía de cráneo",
        "Solicito interconsulta con neurología",
        "¿Cuál es el diagnóstico? ¿Es migraña?",
    ],
    "EME-001": [
        "¿Desde cuándo tiene el problema?",
        "Voy a examinar al paciente",
        "Realizo la exploración física",
        "Solicito un hemograma",
    ],
}


def consulta(case_id: str) -> None:
    client = TestClient(app)
    status = client.get("/api/ai/status").json()
    print(f"\n===== {case_id} · recuperación: {status['retrieval_mode']} · LLM: {status['llm_mode']}")
    session_id = client.post("/api/ai/sessions", json={"case_id": case_id}).json()["session_id"]
    for message in GUIONES[case_id]:
        turn = client.post(f"/api/ai/sessions/{session_id}/message", json={"message": message}).json()
        response = " ".join(turn["response"].split())
        print(f"> {message}")
        print(f"  [{turn['agent']}] evidencia={turn['evidence_ids']} bloqueado={turn['blocked']}")
        print(f"  {response}")


ai.CASES_DIR = FIXTURES
ai.settings = replace(ai.settings, rag_embedded_enabled=False, rag_service_url="")
ai.get_service.cache_clear()
consulta("MED-900")

ai.CASES_DIR = ai.CURATED_CASES_DIR
ai.settings = replace(ai.settings, rag_embedded_enabled=True)
ai.get_service.cache_clear()
consulta("EME-001")
