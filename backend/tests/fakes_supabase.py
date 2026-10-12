"""Imitación mínima de la API REST de Supabase (PostgREST) para probar SupabaseSessionStore sin red."""

from __future__ import annotations

import json

import httpx


class FakeSupabase:
    def __init__(self):
        self.sessions: dict[str, dict] = {}
        self.events: list[dict] = []
        self.requests: list[httpx.Request] = []
        self.fail_with: int | None = None

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._handle)

    def client(self) -> httpx.Client:
        return httpx.Client(transport=self.transport())

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.fail_with:
            return httpx.Response(self.fail_with, json={"message": "fallo simulado"})
        table = request.url.path.rsplit("/", 1)[-1]
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
        return httpx.Response(404, json={"message": "ruta no simulada"})
