r"""Pide los datos nuevos con un índice RAG armado antes de completar los casos.

Copia el índice viejo (data/indexes/lightrag/<huella>) a una carpeta temporal y apunta el servidor a ella.
Con la corrección del adaptador del RAG, los datos autorizados que el índice no tiene salen del caso.

Uso (desde backend/):
    .venv\Scripts\python.exe ..\pruebas\18_casos_con_un_solo_diagnostico\probar_indice_viejo.py <huella_del_indice_viejo>
"""

import shutil
import sys
import tempfile
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.stdout.reconfigure(encoding="utf-8")

from fastapi.testclient import TestClient  # noqa: E402

import server.api.ai as ai  # noqa: E402
from server.ai.llm.gateway import LLMGateway  # noqa: E402
from server.ai.llm.providers import LocalDevelopmentProvider  # noqa: E402
from server.main import app  # noqa: E402
from server.orchestration import InMemorySessionStore  # noqa: E402

PEDIDOS = [
    ("CIR-005", "Pido el dosaje del factor VIII y del factor IX"),
    ("EME-002", "Solicito una tomografía de cráneo sin contraste"),
    ("GOB-003", "Solicito una prolactina sérica"),
    ("MED-007", "Solicito un hemograma y perfil hepático"),
]

old = ROOT / "data" / "indexes" / "lightrag" / sys.argv[1]
with tempfile.TemporaryDirectory() as tmp:
    shutil.copytree(old, Path(tmp) / old.name)
    ai.settings = replace(ai.settings, rag_embedded_enabled=True, rag_service_url="", rag_index_dir=Path(tmp),
                          session_store="memoria")
    ai.STORE = InMemorySessionStore()
    ai.build_gateway = lambda: LLMGateway([LocalDevelopmentProvider()])
    ai.get_service.cache_clear()
    with TestClient(app) as client:
        status = client.get("/api/ai/status").json()
        print(f"Índice usado: {old.name[:12]}... (armado antes de completar los casos) | modo: {status['retrieval_mode']}\n")
        ok = 0
        for case_id, message in PEDIDOS:
            sid = client.post("/api/ai/sessions", json={"case_id": case_id}).json()["session_id"]
            reply = client.post(f"/api/ai/sessions/{sid}/message", json={"message": message}).json()
            ok += bool(reply["evidence_ids"])
            print(f"{case_id} «{message}»\n   datos: {reply['evidence_ids']}\n   respuesta: {reply['response'][:150]}\n")
    ai.get_service.cache_clear()
print(f"RESUMEN: {ok} de {len(PEDIDOS)} datos nuevos llegan al estudiante con el índice viejo")
