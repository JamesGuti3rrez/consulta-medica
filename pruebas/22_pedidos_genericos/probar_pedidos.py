r"""Pedidos al laboratorio y a radiología: examen que existe, examen que no existe y pedido genérico.

Antes, un pedido genérico («análisis de sangre») recibía «Ese examen no se realizó», aunque el caso tuviera
el resultado con otro nombre. Ahora se pregunta qué examen se quiere.

Uso, desde la raíz:
    backend\.venv\Scripts\python.exe pruebas\22_pedidos_genericos\probar_pedidos.py [URL]
Sin URL, usa el sitio publicado.
"""

import sys
import time

import httpx

sys.stdout.reconfigure(encoding="utf-8")
BASE = (sys.argv[1] if len(sys.argv) > 1 else "https://consulta-medica-three.vercel.app").rstrip("/")
PEDIDOS = [
    ("CIR-005", "¿Qué resultados tienen los análisis de sangre de antes de la operación?",
     "genérico: el caso SÍ tiene pruebas de coagulación", "pregunta"),
    ("CIR-005", "Pido unos exámenes de laboratorio", "genérico", "pregunta"),
    ("EME-002", "Quiero un estudio de imagen", "genérico de imagen: el caso SÍ tiene tomografía", "pregunta"),
    ("CIR-005", "Solicito pruebas de coagulación", "examen concreto que existe", "resultado"),
    ("CIR-005", "Pido un hemograma", "examen concreto que el caso no tiene", "no se realizó"),
]

client = httpx.Client(timeout=60)
status = client.get(f"{BASE}/api/ai/status").json()
print(f"Sitio: {BASE} | modelo: {status['llm_mode']}\n")
ok = 0
for case_id, message, kind, expected in PEDIDOS:
    sid = client.post(f"{BASE}/api/ai/sessions", json={"case_id": case_id}).json()["session_id"]
    reply = client.post(f"{BASE}/api/ai/sessions/{sid}/message", json={"message": message}).json()
    text = reply.get("response", "")
    got = ("resultado" if reply.get("evidence_ids") else
           "pregunta" if text.startswith("¿Qué ") else
           "no se realizó" if "no se realiz" in text.lower() or "no tenemos" in text.lower() else "otra")
    ok += got == expected
    print(f"{'OK   ' if got == expected else 'FALLA'} [{case_id}] {kind}\n      «{message}» -> {reply.get('agent')}"
          f"\n      {text[:170]}\n      esperado: {expected} | obtenido: {got}\n")
    client.post(f"{BASE}/api/ai/sessions/{sid}/finish")
    time.sleep(1.5)
print(f"RESUMEN: {ok} de {len(PEDIDOS)} pedidos reciben la respuesta correcta")
