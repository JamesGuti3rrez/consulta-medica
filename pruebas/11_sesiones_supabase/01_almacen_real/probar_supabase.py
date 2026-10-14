"""Prueba del almacén de sesiones contra las tablas reales de Supabase (sma_sesiones y sma_eventos).

Reproduce lo que fallaba en Vercel: la consulta la crea una instancia del servidor y las preguntas las
atienden otras. Cada paso usa un SupabaseSessionStore nuevo, sin memoria compartida. Al final borra la
sesión de prueba. No muestra ninguna clave.

Uso (desde backend/):  .venv\\Scripts\\python.exe ..\\pruebas\\11_sesiones_supabase\\01_almacen_real\\probar_supabase.py
"""

import sys
from dataclasses import replace

import httpx
from fastapi.testclient import TestClient

import server.api.ai as ai_module
from server.ai.llm.gateway import LLMGateway
from server.ai.llm.providers import LocalDevelopmentProvider
from server.config import settings
from server.main import app
from server.orchestration import SessionNotFound, SupabaseSessionStore

sys.stdout.reconfigure(encoding="utf-8")
REST = f"{settings.supabase_url}/rest/v1"
SECRET = {"apikey": settings.supabase_secret_key}
fallos = 0


def check(nombre: str, ok: bool, detalle: str = "") -> None:
    global fallos
    fallos += 0 if ok else 1
    print(f"  [{'OK' if ok else 'FALLA'}] {nombre}{(' · ' + detalle) if detalle else ''}")


def nueva_instancia() -> None:
    """Como una instancia nueva de Vercel: otro almacén, otro servicio, nada en memoria."""
    ai_module.STORE = SupabaseSessionStore(settings.supabase_url, settings.supabase_secret_key)
    ai_module.get_service.cache_clear()


print(f"Proyecto: {settings.supabase_url}")
print(f"Clave secreta: formato {'sb_secret_' if settings.supabase_secret_key.startswith('sb_secret_') else 'otro'} (no se muestra)\n")

print("1. Tablas y permisos")
r = httpx.get(f"{REST}/sma_sesiones", params={"select": "session_id", "limit": "1"}, headers=SECRET, timeout=20)
check("el servidor (clave secreta) accede a sma_sesiones", r.status_code == 200, f"HTTP {r.status_code}")
r = httpx.get(f"{REST}/sma_eventos", params={"select": "id", "limit": "1"}, headers=SECRET, timeout=20)
check("el servidor (clave secreta) accede a sma_eventos", r.status_code == 200, f"HTTP {r.status_code}")
r = httpx.get(f"{REST}/sma_sesiones", params={"select": "*"}, headers={"apikey": settings.supabase_publishable_key}, timeout=20)
check("el navegador (clave publicable) no puede leer las sesiones", r.status_code in (401, 403) or r.json() == [], f"HTTP {r.status_code}, {r.text[:60]}")

print("\n2. Consulta completa con una instancia nueva en cada petición (caso MED-007, sin LLM)")
ai_module.settings = replace(settings, rag_embedded_enabled=False, rag_service_url="")
ai_module.build_gateway = lambda: LLMGateway([LocalDevelopmentProvider()])
client = TestClient(app)

nueva_instancia()
inicio = client.post("/api/ai/sessions", json={"case_id": "MED-007"})
sid = inicio.json().get("session_id", "")
check("instancia A crea la consulta", inicio.status_code == 200, f"session_id {sid}")

nueva_instancia()
resp = client.post(f"/api/ai/sessions/{sid}/message", json={"message": "Pregúntele si tiene alergias a algún medicamento"})
datos = resp.json()
check("instancia B responde la pregunta (antes: 404)", resp.status_code == 200, f"agente {datos.get('agent')}, evidencia {datos.get('evidence_ids')}")

nueva_instancia()
resp = client.post(f"/api/ai/sessions/{sid}/message", json={"message": "Quiero examinar la piel de la espalda"})
datos = resp.json()
check("instancia C responde otra pregunta", resp.status_code == 200, f"agente {datos.get('agent')}, evidencia {datos.get('evidence_ids')}")

nueva_instancia()
estado = client.get(f"/api/ai/sessions/{sid}").json()
check("instancia D ve los datos revelados por B y C",
      "MED-007.antecedente.alergias" in estado.get("revealed_evidence_ids", []),
      f"{len(estado.get('revealed_evidence_ids', []))} datos revelados")
fin = client.post(f"/api/ai/sessions/{sid}/finish")
check("instancia D cierra la consulta", fin.status_code == 200 and fin.json().get("phase") == "finalizada")

nueva_instancia()
eventos = client.get(f"/api/ai/sessions/{sid}/events").json()
tipos = [e["type"] for e in eventos]
check("instancia E lee los eventos en orden", tipos == ["session_started", "turn", "turn", "session_finished"], " > ".join(tipos))

print("\n3. Lo guardado en Supabase")
fila = httpx.get(f"{REST}/sma_sesiones", params={"session_id": f"eq.{sid}", "select": "case_id,phase,state,created_at,updated_at"}, headers=SECRET, timeout=20).json()[0]
print(f"  sma_sesiones: case_id={fila['case_id']} phase={fila['phase']} creada={fila['created_at'][:19]} actualizada={fila['updated_at'][:19]}")
for turno in fila["state"]["history"]:
    print(f"    {turno['role']:>17}: {turno['text'][:90]}")
check("la fila no guarda la solución del caso", "protected" not in str(fila) and "diagnosis" not in str(fila))

print("\n4. Sesión inexistente")
nueva_instancia()
resp = client.post("/api/ai/sessions/00000000-0000-0000-0000-000000000000/message", json={"message": "Hola, ¿cómo está?"})
check("una sesión que no existe responde 404", resp.status_code == 404)

print("\n5. Limpieza")
borrado = httpx.delete(f"{REST}/sma_sesiones", params={"session_id": f"eq.{sid}"}, headers=SECRET, timeout=20)
try:
    SupabaseSessionStore(settings.supabase_url, settings.supabase_secret_key).get(sid)
    quedo = True
except SessionNotFound:
    quedo = False
check("la sesión de prueba y sus eventos se borran", borrado.status_code == 204 and not quedo)

print(f"\nResultado: {'todas las comprobaciones pasan' if fallos == 0 else f'{fallos} comprobaciones fallan'}")
sys.exit(1 if fallos else 0)
