r"""Pide en el sitio publicado los datos que agregó el equipo (decisión 0002) y muestra lo que lee el estudiante.

Uso, desde la raíz:  backend\.venv\Scripts\python.exe pruebas\18_casos_con_un_solo_diagnostico\probar_vercel.py [URL]
"""

import sys
import time

import httpx

sys.stdout.reconfigure(encoding="utf-8")
BASE = (sys.argv[1] if len(sys.argv) > 1 else "https://consulta-medica-three.vercel.app").rstrip("/")
PEDIDOS = [
    ("CIR-005", "Pido el dosaje del factor VIII y del factor IX", "CIR-005.lab.factores_coagulacion"),
    ("CIR-006", "Pido una radiografía de tórax", "CIR-006.imagen.radiografia_torax"),
    ("EME-001", "Solicito función tiroidea", "EME-001.lab.funcion_tiroidea"),
    ("EME-001", "Pido un electroencefalograma", "EME-001.estudio.electroencefalograma"),
    ("EME-002", "Solicito una tomografía de cráneo sin contraste", "EME-002.imagen.tomografia_craneo"),
    ("GOB-003", "Solicito una prolactina sérica", "GOB-003.lab.prolactina"),
    ("MED-007", "Solicito un hemograma y perfil hepático", "MED-007.lab.hemograma_bioquimica"),
]

client = httpx.Client(timeout=60)
status = client.get(f"{BASE}/api/ai/status").json()
print(f"Sitio: {BASE} | modelo: {status['llm_mode']} | recuperación: {status['retrieval_mode']}\n")
ok = 0
for case_id, message, expected in PEDIDOS:
    sid = client.post(f"{BASE}/api/ai/sessions", json={"case_id": case_id}).json()["session_id"]
    reply = client.post(f"{BASE}/api/ai/sessions/{sid}/message", json={"message": message}).json()
    got = expected in reply.get("evidence_ids", [])
    ok += got
    print(f"{'OK ' if got else 'FALLA'} {case_id} «{message}» -> {reply.get('agent')}\n      {reply.get('response', '')[:160]}")
    client.post(f"{BASE}/api/ai/sessions/{sid}/finish")
    time.sleep(1.5)
print(f"\nRESUMEN: {ok} de {len(PEDIDOS)} datos nuevos llegan al estudiante en el sitio publicado")
