"""Sesiones del SMA guardadas en Supabase (tablas sma_sesiones y sma_eventos, por su API REST).

En Vercel cada petición puede atenderla una instancia distinta del servidor, así que la sesión no puede
vivir en memoria. Las tablas se crean con supabase/migrations/20261011_sesiones_sma.sql y solo se
acceden con la clave secreta del servidor: tienen RLS activado y ninguna política para el navegador.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import httpx

from .store import SessionNotFound

SESSIONS_TABLE = "sma_sesiones"
EVENTS_TABLE = "sma_eventos"


class SessionStoreError(RuntimeError):
    """Supabase no respondió o rechazó la operación."""


def _uuid(session_id: str) -> str:
    try:
        return str(UUID(str(session_id)))
    except ValueError as exc:
        raise SessionNotFound(session_id) from exc


class SupabaseSessionStore:
    """Misma interfaz que InMemorySessionStore: create, get, save, event y events."""

    def __init__(self, url: str, secret_key: str, client: httpx.Client | None = None, timeout: float = 10.0):
        if not url or not secret_key:
            raise ValueError("SESSION_STORE=supabase requiere SUPABASE_URL y SUPABASE_SECRET_KEY.")
        headers = {"apikey": secret_key, "Content-Type": "application/json"}
        # Las claves antiguas (service_role) son JWT y también van en Authorization; las nuevas sb_secret_ no.
        if not secret_key.startswith("sb_"):
            headers["Authorization"] = f"Bearer {secret_key}"
        self._client = client or httpx.Client(timeout=timeout)
        self._base = f"{url.rstrip('/')}/rest/v1"
        self._headers = headers

    def _request(self, method: str, table: str, **kwargs) -> httpx.Response:
        headers = {**self._headers, **kwargs.pop("headers", {})}
        try:
            response = self._client.request(method, f"{self._base}/{table}", headers=headers, **kwargs)
        except httpx.HTTPError as exc:
            raise SessionStoreError(f"No se pudo conectar con Supabase: {exc.__class__.__name__}") from exc
        if response.status_code >= 400:
            raise SessionStoreError(f"Supabase respondió HTTP {response.status_code} en {table}: {response.text[:200]}")
        return response

    def create(self, state: dict) -> dict:
        session_id = _uuid(state["session_id"])
        self._request("POST", SESSIONS_TABLE, headers={"Prefer": "return=minimal"}, json={
            "session_id": session_id,
            "case_id": state["case_id"],
            "phase": state["phase"],
            "state": state,
        })
        return dict(state)

    def get(self, session_id: str) -> dict:
        rows = self._request("GET", SESSIONS_TABLE, params={
            "session_id": f"eq.{_uuid(session_id)}", "select": "state",
        }).json()
        if not rows:
            raise SessionNotFound(session_id)
        return rows[0]["state"]

    def save(self, state: dict) -> None:
        rows = self._request("PATCH", SESSIONS_TABLE, headers={"Prefer": "return=representation"},
                             params={"session_id": f"eq.{_uuid(state['session_id'])}", "select": "session_id"},
                             json={"phase": state["phase"], "state": state,
                                   "updated_at": datetime.now(timezone.utc).isoformat()}).json()
        if not rows:
            raise SessionNotFound(state["session_id"])

    def event(self, session_id: str, payload: dict) -> None:
        try:
            self._request("POST", EVENTS_TABLE, headers={"Prefer": "return=minimal"},
                          json={"session_id": _uuid(session_id), "payload": payload})
        except SessionStoreError as exc:
            # 23503: la clave foránea no encuentra la sesión.
            if "23503" in str(exc):
                raise SessionNotFound(session_id) from exc
            raise

    def events(self, session_id: str) -> list[dict]:
        self.get(session_id)
        rows = self._request("GET", EVENTS_TABLE, params={
            "session_id": f"eq.{_uuid(session_id)}", "select": "payload", "order": "id.asc",
        }).json()
        return [row["payload"] for row in rows]
