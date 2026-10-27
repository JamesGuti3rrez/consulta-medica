"""Registro de evidencia de TA-017: cada caso guarda sus peticiones y respuestas reales en un JSON.

Solo escribe si la variable TA017_EVIDENCIA apunta a una carpeta; en la suite normal no deja archivos.
Los secretos (tokens de usuario, credenciales de capacidad, claves) se enmascaran como
«primeros 6 caracteres + … + últimos 4» antes de escribir nada.
"""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

MAX_BODY = 4000


def mask(secret: str) -> str:
    secret = str(secret)
    if len(secret) <= 12:
        return "…" * 3
    return f"{secret[:6]}…{secret[-4:]}"


class Secrets:
    """Todos los secretos vistos durante la corrida, para borrarlos de cualquier texto guardado."""

    def __init__(self):
        self.values: set[str] = set()

    def add(self, *values: str | None) -> None:
        for value in values:
            if value and len(value) > 12:
                self.values.add(value)

    def scrub(self, text: str) -> str:
        # Los más largos primero: un token puede contener a otro más corto (por ejemplo, alterado).
        for value in sorted(self.values, key=len, reverse=True):
            text = text.replace(value, mask(value))
        return text


SECRETS = Secrets()


def _commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                              cwd=Path(__file__).resolve().parents[3]).stdout.strip()
    except OSError:
        return "desconocido"


def _short(text: str) -> str:
    return text if len(text) <= MAX_BODY else text[:MAX_BODY] + f"… ({len(text) - MAX_BODY} caracteres más)"


class Caso:
    """Pasos (petición + respuesta) y comprobaciones de un caso TA017-XX."""

    def __init__(self, id: str, criterio: str, titulo: str, nombre: str, esperado: str):  # noqa: A002
        case_id = id
        self.case_id, self.criterio, self.titulo, self.nombre, self.esperado = case_id, criterio, titulo, nombre, esperado
        self.pasos: list[dict] = []
        self.comprobaciones: list[dict] = []
        self.notas: list[str] = []

    def paso(self, identidad: str, response, esperado: set[int] | tuple[int, ...], descripcion: str = "",
             cuerpo_enviado=None) -> bool:
        request = response.request
        headers = {k: v for k, v in request.headers.items()
                   if k.lower() in {"authorization", "x-session-token", "apikey", "origin", "content-type",
                                    "access-control-request-method"}}
        ok = response.status_code in set(esperado)
        self.pasos.append({
            "descripcion": descripcion,
            "identidad": identidad,
            "metodo": request.method,
            "url": str(request.url),
            "cabeceras": headers,
            "cuerpo_enviado": cuerpo_enviado,
            "codigo_recibido": response.status_code,
            "cabeceras_respuesta": {k: v for k, v in response.headers.items()
                                    if k.lower().startswith("access-control") or k.lower() == "content-type"},
            "cuerpo_recibido": _short(response.text),
            "codigo_esperado": sorted(set(esperado)),
            "resultado": "PASA" if ok else "FALLA",
        })
        return ok

    def comprobar(self, descripcion: str, ok: bool, detalle: str = "") -> bool:
        self.comprobaciones.append({"descripcion": descripcion, "resultado": "PASA" if ok else "FALLA",
                                    "detalle": detalle})
        return ok

    def nota(self, texto: str) -> None:
        self.notas.append(texto)

    def fallos(self) -> list[str]:
        malos = [f"paso {i + 1} ({p['metodo']} {p['url']}): {p['codigo_recibido']} no está en {p['codigo_esperado']}"
                 for i, p in enumerate(self.pasos) if p["resultado"] != "PASA"]
        malos += [f"comprobación: {c['descripcion']} {c['detalle']}".strip()
                  for c in self.comprobaciones if c["resultado"] != "PASA"]
        return malos

    def exigir(self) -> None:
        malos = self.fallos()
        assert not malos, f"{self.case_id}: " + " | ".join(malos)

    def escribir(self, resultado: str, error: str = "") -> None:
        folder = os.getenv("TA017_EVIDENCIA")
        if not folder:
            return
        logs = Path(folder) / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        data = {
            "id": self.case_id,
            "nombre": self.nombre,
            "titulo": self.titulo,
            "criterio": self.criterio,
            "resultado_esperado": self.esperado,
            "resultado": resultado,
            "modo": os.getenv("TA017_MODO", "local"),
            "servidor": os.getenv("TA017_BASE_URL", "TestClient (en proceso)"),
            "fase": os.getenv("TA017_FASE", ""),
            "commit": _commit(),
            "fecha": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "pasos": self.pasos,
            "comprobaciones": self.comprobaciones,
            "notas": self.notas,
            "error": error,
        }
        text = SECRETS.scrub(json.dumps(data, ensure_ascii=False, indent=2))
        (logs / f"{self.case_id}.json").write_text(text, encoding="utf-8")
