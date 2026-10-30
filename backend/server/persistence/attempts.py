"""Intentos del alumno en Supabase: verifica su sesión y guarda cada consulta terminada (tabla intentos)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

ATTEMPTS_TABLE = "intentos"


class AttemptStoreError(RuntimeError):
    """Supabase no respondió o rechazó la operación."""


class SupabaseAttempts:
    """Comprueba el token del alumno con Supabase Auth y guarda sus intentos con la clave secreta.

    La tabla no tiene política de insert: desde el navegador no se pueden crear intentos, así que el
    puntaje siempre es el que calculó el motor clínico en el servidor.
    """

    def __init__(self, url: str, publishable_key: str, secret_key: str,
                 client: httpx.Client | None = None, timeout: float = 10.0):
        if not url or not publishable_key or not secret_key:
            raise ValueError("Guardar intentos requiere SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY y SUPABASE_SECRET_KEY.")
        self._base = url.rstrip("/")
        self._publishable_key = publishable_key
        self._secret_headers = {"apikey": secret_key, "Content-Type": "application/json"}
        # Las claves antiguas (service_role) son JWT y también van en Authorization; las nuevas sb_secret_ no.
        if not secret_key.startswith("sb_"):
            self._secret_headers["Authorization"] = f"Bearer {secret_key}"
        self._client = client or httpx.Client(timeout=timeout)

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        try:
            return self._client.request(method, f"{self._base}{path}", **kwargs)
        except httpx.HTTPError as exc:
            raise AttemptStoreError(f"No se pudo conectar con Supabase: {exc.__class__.__name__}") from exc

    def user_id(self, access_token: str) -> str | None:
        """Id del alumno si el token de su sesión es válido; None si no lo es o ya venció."""
        response = self._request("GET", "/auth/v1/user", headers={
            "apikey": self._publishable_key, "Authorization": f"Bearer {access_token}",
        })
        if response.status_code in (401, 403):
            return None
        if response.status_code >= 400:
            raise AttemptStoreError(f"Supabase Auth respondió HTTP {response.status_code}: {response.text[:200]}")
        return response.json().get("id")

    def save(self, row: dict[str, Any]) -> str:
        response = self._request(
            "POST", f"/rest/v1/{ATTEMPTS_TABLE}",
            headers={**self._secret_headers, "Prefer": "return=representation"},
            params={"select": "id"}, json=row,
        )
        if response.status_code >= 400:
            raise AttemptStoreError(f"Supabase respondió HTTP {response.status_code} en {ATTEMPTS_TABLE}: {response.text[:200]}")
        return str(response.json()[0]["id"])


def build_attempt(*, user_id: str, session: dict[str, Any], specialty: str,
                  diagnosis: str | None, hypotheses: list[dict[str, Any]]) -> dict[str, Any]:
    """Fila de intentos a partir de la sesión finalizada. Solo puntaje y conteos: nada de protected."""
    evaluation = session["evaluation"]
    started = datetime.fromisoformat(session["started_at"])
    finished = datetime.fromisoformat(session["finished_at"])
    return {
        "usuario_id": user_id,
        "caso_id": session["case_id"],
        "especialidad": specialty,
        "puntaje": max(0, min(100, round(evaluation["score"]))),
        "diagnostico": diagnosis or None,
        "hipotesis": hypotheses,
        "reporte": {
            "session_id": session["session_id"],
            "score": evaluation["score"],
            "completed_questions": evaluation["completed_questions"],
            "total_questions": evaluation["total_questions"],
            "errors": evaluation["errors"],
            "safety_alerts": [alert["code"] for alert in session.get("avatar_state", {}).get("alerts", [])],
            **({"diagnosis_evaluation": session["diagnosis_evaluation"]} if session.get("diagnosis_evaluation") else {}),
        },
        "duracion_segundos": max(0, int((finished - started).total_seconds())),
    }
