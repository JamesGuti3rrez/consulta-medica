"""Autorización docente: sesión verificada por Supabase, rol asignado por administración."""
from __future__ import annotations

from dataclasses import dataclass

import httpx
from fastapi import Depends, Header, HTTPException

from server.config import settings

STAFF_ROLES = frozenset({"profesor", "administrativo"})


@dataclass(frozen=True)
class AuthUser:
    id: str
    email: str
    role: str


class SupabaseAuth:
    def __init__(self, url: str, key: str, *, client=None):
        self.url, self.key, self.client = url.rstrip("/"), key, client

    def verify(self, token: str) -> AuthUser:
        headers = {"apikey": self.key, "Authorization": f"Bearer {token}"}
        try:
            if self.client is not None:
                response = self.client.get(self.url + "/auth/v1/user", headers=headers)
            else:
                with httpx.Client(timeout=12) as client:
                    response = client.get(self.url + "/auth/v1/user", headers=headers)
            if response.status_code in (401, 403):
                raise HTTPException(401, "La sesión venció o no es válida. Inicia sesión de nuevo.")
            if response.is_error:
                raise HTTPException(503, "No se pudo verificar la sesión con Supabase.")
            user = response.json()
            if not isinstance(user, dict) or not user.get("id"):
                raise ValueError("Usuario inválido")
        except (httpx.HTTPError, ValueError) as exc:
            raise HTTPException(503, "No se pudo verificar la sesión con Supabase.") from exc
        # user_metadata y campos enviados por el navegador NO conceden permisos.
        metadata = user.get("app_metadata") or {}
        role = metadata.get("rol", "alumno") if isinstance(metadata, dict) else "alumno"
        if not isinstance(role, str) or role not in STAFF_ROLES:
            role = "alumno"
        return AuthUser(str(user["id"]), str(user.get("email") or ""), role)


def get_auth() -> SupabaseAuth:
    if not settings.auth_enabled:
        raise HTTPException(503, "Configura Supabase Auth antes de usar el panel docente.")
    return SupabaseAuth(settings.supabase_url, settings.supabase_publishable_key)


def current_user(authorization: str | None = Header(default=None),
                 auth: SupabaseAuth = Depends(get_auth)) -> AuthUser:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.casefold() != "bearer" or not token.strip() or len(token) > 8192:
        raise HTTPException(401, "Inicia sesión para continuar.")
    return auth.verify(token.strip())


def require_staff(user: AuthUser = Depends(current_user)) -> AuthUser:
    if user.role not in STAFF_ROLES:
        raise HTTPException(403, "Este apartado requiere rol de profesor o administrativo.")
    return user

