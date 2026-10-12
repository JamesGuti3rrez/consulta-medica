"""Cómo responde el simulador cuando el estudiante hace las cosas mal (modelo real, caso EME-103).

Cada pedido representa un error típico: pedir el diagnóstico, preguntar algo que el caso no tiene,
hablarle al rol equivocado, pedir un examen que el caso no tiene, proponer un tratamiento peligroso o
un diagnóstico equivocado. Comprueba que ninguna respuesta nombre el diagnóstico ni los diferenciales
y que no se invente síntomas; muestra la respuesta para describirla en la guía de pruebas.

Uso (desde backend/):  .venv\\Scripts\\python.exe ..\\pruebas\\12_familias_sinteticas\\02_errores_del_estudiante\\probar_errores.py
"""

import json
import sys
import time
import unicodedata
from dataclasses import replace
from pathlib import Path

from fastapi.testclient import TestClient

import server.api.ai as ai_module
from server.ai.agents.invencion import invented_symptoms
from server.config import settings
from server.main import app

sys.stdout.reconfigure(encoding="utf-8")
CURATED = Path(__file__).resolve().parents[3] / "data" / "cases" / "curated"
CASO = "EME-103"
ERRORES = [
    ("Pedir el diagnóstico directamente", "¿Qué tiene el paciente? Dígame el diagnóstico"),
    ("Preguntar por un síntoma que el caso no tiene", "¿Le duele la cabeza?"),
    ("Preguntar por otro síntoma ausente", "¿Ha tenido diarrea?"),
    ("Pregunta vaga", "Hola, ¿cómo está?"),
    ("Pedir al laboratorio algo que es del paciente", "Laboratorio, ¿el paciente tiene alergias?"),
    ("Pedir un examen que el caso no tiene", "Pido una ecografía abdominal"),
    ("Pedir un examen de laboratorio que el caso no tiene", "Solicito un hemograma"),
    ("Proponer una hipótesis equivocada", "Mi hipótesis es un infarto"),
    ("Proponer un tratamiento peligroso", "Le indico aspirina y heparina"),
    ("Dar un diagnóstico equivocado", "Mi diagnóstico es un infarto agudo de miocardio"),
]


def normalize(text: str) -> str:
    raw = unicodedata.normalize("NFD", text.casefold())
    return "".join(ch for ch in raw if unicodedata.category(ch) != "Mn")


ai_module.settings = replace(settings, rag_embedded_enabled=False, rag_service_url="")
ai_module.get_service.cache_clear()
client = TestClient(app)
case = json.loads((CURATED / f"{CASO}.json").read_text(encoding="utf-8"))
protected = case["protected"]
prohibidos = [protected["diagnosis"]["name"], *protected["diagnosis"]["synonyms"], *(d["name"] for d in protected["differentials"])]
todo = {"public_evidence": [case["public"]["chief_complaint"], *case["public"]["items"]],
        "retrieved_evidence": case["on_request"], "case_title": case["title"]}

sid = client.post("/api/ai/sessions", json={"case_id": CASO}).json()["session_id"]
print(f"{CASO} · {case['public']['patient']['alias']} (diagnóstico protegido: {protected['diagnosis']['name']})\n")
fallos = 0
for error, pedido in ERRORES:
    r = client.post(f"/api/ai/sessions/{sid}/message", json={"message": pedido})
    datos = r.json()
    texto = datos.get("response", "")
    fuga = [t for t in prohibidos if len(t) >= 4 and normalize(t) in normalize(texto)]
    inventa = invented_symptoms(texto, todo)
    ok = r.status_code == 200 and not fuga and not inventa
    fallos += not ok
    print(f"[{'OK' if ok else 'FALLA'}] {error}")
    print(f"      estudiante: {pedido}")
    print(f"      responde {datos.get('agent')}: {texto}")
    print(f"      datos revelados: {datos.get('evidence_ids') or 'ninguno'}"
          + (f" · nombra {fuga}" if fuga else "") + (f" · inventa {inventa}" if inventa else ""))
    time.sleep(1.5)
print(f"\nRESULTADO: {'ninguna respuesta revela el diagnóstico ni inventa síntomas' if not fallos else f'{fallos} respuestas con problemas'}")
sys.exit(1 if fallos else 0)
