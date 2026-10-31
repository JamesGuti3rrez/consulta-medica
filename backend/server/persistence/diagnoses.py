"""Registro del diagnóstico final (HU-006): uno por sesión, numerado por alumno y caso.

En producción vive en la tabla diagnosticos_finales de Supabase (migración 0007), que solo usa el servidor con
la clave secreta. Con SESSION_STORE=memoria se usa la versión en memoria, con la misma interfaz.
No guarda nada de la parte protegida del caso: solo lo que propuso el alumno.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx

DIAGNOSES_TABLE = "diagnosticos_finales"


class DiagnosisStoreError(RuntimeError):
    """No se pudo leer o escribir el registro (Supabase no respondió o rechazó la operación)."""


@dataclass(frozen=True)
class FinalDiagnosisRecord:
    id: str
    session_id: str
    usuario_id: str
    case_id: str
    numero_intento: int
    diagnostico: str
    hipotesis: list[dict[str, Any]] = field(default_factory=list)
    creado_en: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> FinalDiagnosisRecord:
        return cls(id=str(row["id"]), session_id=str(row["session_id"]), usuario_id=str(row["usuario_id"]),
                   case_id=row["case_id"], numero_intento=int(row["numero_intento"]),
                   diagnostico=row["diagnostico"], hipotesis=list(row.get("hipotesis") or []),
                   creado_en=str(row.get("creado_en") or ""))


class InMemoryDiagnoses:
    """Para SESSION_STORE=memoria y las pruebas. Un candado hace atómico «ver si existe, numerar y guardar»."""

    def __init__(self):
        self._lock = threading.Lock()
        self._records: dict[str, FinalDiagnosisRecord] = {}

    def by_session(self, session_id: str) -> FinalDiagnosisRecord | None:
        return self._records.get(session_id)

    def register(self, *, session_id: str, user_id: str, case_id: str, diagnosis: str,
                 hypotheses: list[dict[str, Any]]) -> tuple[FinalDiagnosisRecord, bool]:
        with self._lock:
            if session_id in self._records:
                return self._records[session_id], False
            previous = [r.numero_intento for r in self._records.values()
                        if r.usuario_id == user_id and r.case_id == case_id]
            record = FinalDiagnosisRecord(
                id=str(uuid.uuid4()), session_id=session_id, usuario_id=user_id, case_id=case_id,
                numero_intento=max(previous, default=0) + 1, diagnostico=diagnosis, hipotesis=list(hypotheses),
                creado_en=datetime.now(timezone.utc).isoformat(),
            )
            self._records[session_id] = record
            return record, True

    def clear(self) -> None:
        with self._lock:
            self._records.clear()


def _uuid(value: str) -> str | None:
    try:
        return str(uuid.UUID(str(value)))
    except ValueError:
        return None


class SupabaseDiagnoses:
    """Tabla diagnosticos_finales por la API REST. Las restricciones únicas de la tabla resuelven las carreras:
    session_id (un registro por consulta) y (usuario_id, case_id, numero_intento)."""

    def __init__(self, url: str, secret_key: str, client: httpx.Client | None = None, timeout: float = 10.0):
        if not url or not secret_key:
            raise ValueError("El registro de diagnósticos requiere SUPABASE_URL y SUPABASE_SECRET_KEY.")
        headers = {"apikey": secret_key, "Content-Type": "application/json"}
        # Las claves antiguas (service_role) son JWT y también van en Authorization; las nuevas sb_secret_ no.
        if not secret_key.startswith("sb_"):
            headers["Authorization"] = f"Bearer {secret_key}"
        self._client = client or httpx.Client(timeout=timeout)
        self._url = f"{url.rstrip('/')}/rest/v1/{DIAGNOSES_TABLE}"
        self._headers = headers

    def _request(self, method: str, *, conflict_ok: bool = False, **kwargs) -> httpx.Response:
        headers = {**self._headers, **kwargs.pop("headers", {})}
        try:
            response = self._client.request(method, self._url, headers=headers, **kwargs)
        except httpx.HTTPError as exc:
            raise DiagnosisStoreError(f"No se pudo conectar con Supabase: {exc.__class__.__name__}") from exc
        if response.status_code == 409 and conflict_ok:
            return response
        if response.status_code >= 400:
            raise DiagnosisStoreError(
                f"Supabase respondió HTTP {response.status_code} en {DIAGNOSES_TABLE}: {response.text[:200]}")
        return response

    def by_session(self, session_id: str) -> FinalDiagnosisRecord | None:
        session_uuid = _uuid(session_id)
        if session_uuid is None:
            return None
        rows = self._request("GET", params={"session_id": f"eq.{session_uuid}", "select": "*"}).json()
        return FinalDiagnosisRecord.from_row(rows[0]) if rows else None

    def _next_attempt(self, user_id: str, case_id: str) -> int:
        rows = self._request("GET", params={
            "usuario_id": f"eq.{user_id}", "case_id": f"eq.{case_id}", "select": "numero_intento",
            "order": "numero_intento.desc", "limit": "1",
        }).json()
        return (int(rows[0]["numero_intento"]) if rows else 0) + 1

    def register(self, *, session_id: str, user_id: str, case_id: str, diagnosis: str,
                 hypotheses: list[dict[str, Any]]) -> tuple[FinalDiagnosisRecord, bool]:
        existing = self.by_session(session_id)
        if existing:
            return existing, False
        # Dos intentos: si otra consulta del mismo alumno y caso tomó el número, se vuelve a numerar una vez.
        for _ in range(2):
            response = self._request(
                "POST", conflict_ok=True, headers={"Prefer": "return=representation"}, params={"select": "*"},
                json={"session_id": session_id, "usuario_id": user_id, "case_id": case_id,
                      "numero_intento": self._next_attempt(user_id, case_id),
                      "diagnostico": diagnosis, "hipotesis": hypotheses},
            )
            if response.status_code != 409:
                return FinalDiagnosisRecord.from_row(response.json()[0]), True
            # Si el choque fue por la sesión, otro envío de esta misma consulta ganó: vale el suyo.
            winner = self.by_session(session_id)
            if winner:
                return winner, False
        raise DiagnosisStoreError("No se pudo asignar un número de intento: demasiados registros simultáneos.")
