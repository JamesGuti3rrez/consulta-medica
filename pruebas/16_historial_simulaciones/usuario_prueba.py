"""Crea o borra un alumno de prueba en Supabase Auth para probar «Mis simulaciones» sin usar cuentas reales.

Uso, desde la raíz del repositorio:
    backend\\.venv\\Scripts\\python.exe pruebas\\16_historial_simulaciones\\usuario_prueba.py crear <archivo_credenciales>
    backend\\.venv\\Scripts\\python.exe pruebas\\16_historial_simulaciones\\usuario_prueba.py intentos <archivo_credenciales>
    backend\\.venv\\Scripts\\python.exe pruebas\\16_historial_simulaciones\\usuario_prueba.py borrar <archivo_credenciales>

«crear» guarda el correo, la contraseña y el id en el archivo indicado (fuera del repositorio); nunca los
imprime. «intentos» muestra los intentos guardados de ese alumno. «borrar» lo elimina; sus perfiles e
intentos se borran en cascada.
"""

from __future__ import annotations

import json
import secrets
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from server.config import settings  # noqa: E402


def _admin_headers() -> dict[str, str]:
    key = settings.supabase_secret_key
    headers = {"apikey": key, "Content-Type": "application/json"}
    if not key.startswith("sb_"):
        headers["Authorization"] = f"Bearer {key}"
    return headers


def crear(path: Path) -> None:
    email = f"alumno.prueba.{secrets.token_hex(4)}@example.com"
    password = secrets.token_urlsafe(18)
    response = httpx.post(
        f"{settings.supabase_url}/auth/v1/admin/users",
        headers=_admin_headers(),
        json={"email": email, "password": password, "email_confirm": True,
              "user_metadata": {"nombres": "Alumno", "apellidos": "De Prueba"}},
        timeout=20,
    )
    response.raise_for_status()
    user_id = response.json()["id"]
    path.write_text(json.dumps({"email": email, "password": password, "id": user_id}), encoding="utf-8")
    print(f"Alumno de prueba creado (id {user_id[:8]}...). Credenciales guardadas fuera del repositorio.")


def intentos(path: Path) -> None:
    user_id = json.loads(path.read_text(encoding="utf-8"))["id"]
    response = httpx.get(
        f"{settings.supabase_url}/rest/v1/intentos",
        headers=_admin_headers(),
        params={"usuario_id": f"eq.{user_id}",
                "select": "creado_en,especialidad,puntaje,diagnostico,hipotesis,duracion_segundos,reporte",
                "order": "creado_en.asc"},
        timeout=20,
    )
    response.raise_for_status()
    rows = response.json()
    print(f"Intentos guardados del alumno de prueba: {len(rows)}")
    for row in rows:
        report = row["reporte"]
        print(f"- {row['especialidad']}: {row['puntaje']} % | {report['completed_questions']} de "
              f"{report['total_questions']} datos clave | diagnóstico: {row['diagnostico']!r} | "
              f"hipótesis: {[h['name'] for h in row['hipotesis']]} | {row['duracion_segundos']} s | "
              f"alertas: {report['safety_alerts']}")


def borrar(path: Path) -> None:
    user_id = json.loads(path.read_text(encoding="utf-8"))["id"]
    response = httpx.delete(f"{settings.supabase_url}/auth/v1/admin/users/{user_id}",
                            headers=_admin_headers(), timeout=20)
    response.raise_for_status()
    remaining = httpx.get(f"{settings.supabase_url}/rest/v1/intentos", headers=_admin_headers(),
                          params={"usuario_id": f"eq.{user_id}", "select": "id"}, timeout=20).json()
    path.unlink()
    print(f"Alumno de prueba borrado. Intentos que quedan de ese alumno: {len(remaining)}")


if __name__ == "__main__":
    action, credentials = sys.argv[1], Path(sys.argv[2])
    {"crear": crear, "intentos": intentos, "borrar": borrar}[action](credentials)
