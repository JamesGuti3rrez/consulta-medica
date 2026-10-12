from __future__ import annotations

import copy
from threading import RLock


class SessionNotFound(KeyError):
    pass


class InMemorySessionStore:
    """Sesiones en memoria del proceso: para desarrollo y pruebas. En Vercel se usa SupabaseSessionStore."""

    def __init__(self):
        self._sessions: dict[str, dict] = {}
        self._events: dict[str, list[dict]] = {}
        self._lock = RLock()

    def create(self, state: dict) -> dict:
        with self._lock:
            self._sessions[state["session_id"]] = copy.deepcopy(state)
            self._events[state["session_id"]] = []
            return copy.deepcopy(state)

    def get(self, session_id: str) -> dict:
        with self._lock:
            if session_id not in self._sessions:
                raise SessionNotFound(session_id)
            return copy.deepcopy(self._sessions[session_id])

    def save(self, state: dict) -> None:
        with self._lock:
            if state["session_id"] not in self._sessions:
                raise SessionNotFound(state["session_id"])
            self._sessions[state["session_id"]] = copy.deepcopy(state)

    def event(self, session_id: str, payload: dict) -> None:
        with self._lock:
            if session_id not in self._sessions:
                raise SessionNotFound(session_id)
            self._events[session_id].append(copy.deepcopy(payload))

    def events(self, session_id: str) -> list[dict]:
        with self._lock:
            if session_id not in self._events:
                raise SessionNotFound(session_id)
            return copy.deepcopy(self._events[session_id])

    def clear(self) -> None:
        with self._lock:
            self._sessions.clear()
            self._events.clear()
