"""Batería de preguntas con el LLM real: busca síntomas inventados en las respuestas de los agentes.

Hace las mismas preguntas en los 10 casos curados (síntomas que la mayoría de los casos no tiene y una
pregunta abierta) y revisa cada respuesta con el detector de server/ai/agents/invencion.py contra todo
lo que el caso describe (ficha visible y datos a petición).

Requiere el servidor en http://localhost:3000 con claves de Groq en el .env.
Uso (desde backend/):  .venv\\Scripts\\python.exe ..\\pruebas\\10_mejoras_casos\\04_datos_inventados\\bateria_groq.py
"""

import json
import sys
import time
from pathlib import Path

import httpx

from server.ai.agents.invencion import invented_symptoms

sys.stdout.reconfigure(encoding="utf-8")
BASE = "http://localhost:3000"
CURATED = Path(__file__).resolve().parents[3] / "data" / "cases" / "curated"
PREGUNTAS = [
    "Pregúntale cómo se llama",
    "Pregúntale cómo se siente",
    "Pregúntale si tiene tos",
    "Pregúntale si le duele el pecho",
    "Pregúntale si se ha mareado",
    "Pregúntale si ha tenido náuseas o vómitos",
]

status = httpx.get(f"{BASE}/api/ai/status", timeout=30).json()
print(f"LLM: {status['llm_mode']} · recuperación: {status['retrieval_mode']}")
if status["llm_mode"] != "groq-pool":
    raise SystemExit("La batería necesita Groq: revisa GROQ_API_KEYS en el .env y reinicia el servidor.")

total = inventadas = 0
for path in sorted(CURATED.glob("*.json"), key=lambda p: int(p.stem[-3:])):
    case = json.loads(path.read_text(encoding="utf-8"))
    whole_case = {"public_evidence": [case["public"]["chief_complaint"], *case["public"]["items"]],
                  "retrieved_evidence": case["on_request"], "case_title": case["title"]}
    session = httpx.post(f"{BASE}/api/ai/sessions", json={"case_id": case["case_id"]}, timeout=30).json()["session_id"]
    print(f"\n{case['case_id']} · {case['public']['patient']['alias']}")
    for question in PREGUNTAS:
        reply = httpx.post(f"{BASE}/api/ai/sessions/{session}/message", json={"message": question}, timeout=120).json()
        found = invented_symptoms(reply["response"], whole_case)
        total += 1
        inventadas += bool(found)
        marca = f"INVENTA {found}" if found else "ok"
        print(f"  [{marca}] {question} → {reply.get('doctor_question')} → {reply['response']}")
        time.sleep(1)

print(f"\nRESULTADO: {inventadas} de {total} respuestas con síntomas que el caso no tiene.")
sys.exit(1 if inventadas else 0)
