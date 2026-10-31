"""Imitación mínima de la API de Supabase (PostgREST y Auth) para probar sesiones e intentos sin red."""

from __future__ import annotations

import json

import httpx


class FakeSupabase:
    def __init__(self):
        self.sessions: dict[str, dict] = {}
        self.events: list[dict] = []
        self.requests: list[httpx.Request] = []
        self.fail_with: int | None = None
        # Tokens de acceso válidos de Supabase Auth -> id del usuario.
        self.users: dict[str, str] = {}
        self.attempts: list[dict] = []
        # Tabla diagnosticos_finales (HU-006), con sus dos restricciones únicas.
        self.diagnoses: list[dict] = []
        # Se llama justo antes de cada insert en diagnosticos_finales: permite simular una carrera.
        self.before_diagnosis_insert = None
        # Fallos por tabla (HU-006): {"diagnosticos_finales": 500}, "sin_red" para simular una caída de conexión
        # o "sin_tabla" para la tabla que todavía no existe (migración pendiente: 404 con código PGRST205).
        self.fail_tables: dict[str, int | str] = {}

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._handle)

    def client(self) -> httpx.Client:
        return httpx.Client(transport=self.transport())

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.fail_with:
            return httpx.Response(self.fail_with, json={"message": "fallo simulado"})
        if request.url.path == "/auth/v1/user":
            token = request.headers.get("authorization", "").removeprefix("Bearer ")
            if token in self.users:
                return httpx.Response(200, json={"id": self.users[token], "aud": "authenticated"})
            return httpx.Response(401, json={"code": "bad_jwt", "message": "invalid JWT"})
        table = request.url.path.rsplit("/", 1)[-1]
        if table in self.fail_tables:
            if self.fail_tables[table] == "sin_red":
                raise httpx.ConnectError("conexión rechazada (simulada)", request=request)
            if self.fail_tables[table] == "sin_tabla":
                return httpx.Response(404, json={"code": "PGRST205", "details": None, "hint": None,
                                                 "message": f"Could not find the table 'public.{table}' in the schema cache"})
            return httpx.Response(int(self.fail_tables[table]), json={"message": "fallo simulado"})
        params = request.url.params
        body = json.loads(request.content) if request.content else None
        target = params.get("session_id", "").removeprefix("eq.")
        if table == "sma_sesiones":
            if request.method == "POST":
                if body["session_id"] in self.sessions:
                    return httpx.Response(409, json={"code": "23505"})
                self.sessions[body["session_id"]] = body
                return httpx.Response(201)
            if request.method == "GET":
                row = self.sessions.get(target)
                return httpx.Response(200, json=[{"state": row["state"]}] if row else [])
            if request.method == "PATCH":
                if target not in self.sessions:
                    return httpx.Response(200, json=[])
                self.sessions[target].update(body)
                return httpx.Response(200, json=[{"session_id": target}])
        if table == "sma_eventos":
            if request.method == "POST":
                if body["session_id"] not in self.sessions:
                    return httpx.Response(409, json={"code": "23503", "message": "violates foreign key constraint"})
                self.events.append(body)
                return httpx.Response(201)
            if request.method == "GET":
                return httpx.Response(200, json=[{"payload": e["payload"]} for e in self.events if e["session_id"] == target])
        if table == "diagnosticos_finales":
            return self._diagnoses(request, params, body)
        if table == "intentos" and request.method == "POST":
            row = {"id": f"intento-{len(self.attempts) + 1}", **body}
            self.attempts.append(row)
            return httpx.Response(201, json=[{"id": row["id"]}])
        return httpx.Response(404, json={"message": "ruta no simulada"})

    def _diagnoses(self, request: httpx.Request, params, body) -> httpx.Response:
        def matches(row: dict) -> bool:
            for column in ("session_id", "usuario_id", "case_id"):
                value = params.get(column)
                if value is not None and str(row[column]) != value.removeprefix("eq."):
                    return False
            return True

        if request.method == "GET":
            rows = sorted((r for r in self.diagnoses if matches(r)), key=lambda r: r["numero_intento"],
                          reverse=params.get("order") == "numero_intento.desc")
            if params.get("limit"):
                rows = rows[: int(params["limit"])]
            return httpx.Response(200, json=rows)
        if request.method == "POST":
            if self.before_diagnosis_insert:
                self.before_diagnosis_insert(body)
            if any(r["session_id"] == body["session_id"] for r in self.diagnoses):
                return httpx.Response(409, json={"code": "23505", "message": "diagnosticos_finales_session_id_key"})
            if any(r["usuario_id"] == body["usuario_id"] and r["case_id"] == body["case_id"]
                   and r["numero_intento"] == body["numero_intento"] for r in self.diagnoses):
                return httpx.Response(409, json={"code": "23505", "message": "diagnosticos_finales_intento_key"})
            row = {"id": f"diag-{len(self.diagnoses) + 1}", "creado_en": "2026-10-31T12:00:00+00:00", **body}
            self.diagnoses.append(row)
            return httpx.Response(201, json=[row])
        return httpx.Response(405, json={"message": "método no simulado"})
