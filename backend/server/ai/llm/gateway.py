from __future__ import annotations

import threading
import time

from server.ai.llm.base import LLMProvider, LLMResult
from server.ai.llm.providers import ProviderError


class LLMGateway:
    """Pool con balanceo simple, cooldown y fallback entre credenciales/proveedores autorizados."""

    def __init__(self, providers: list[LLMProvider], *, cooldown_seconds: float = 60.0):
        if not providers:
            raise ValueError("Se requiere al menos un proveedor LLM.")
        self.providers = providers
        self.cooldown_seconds = cooldown_seconds
        self._cursor = 0
        self._cooldown_until: dict[str, float] = {}
        self._lock = threading.Lock()

    def generate(self, messages: list[dict[str, str]], *, temperature: float = 0.0) -> LLMResult:
        errors: list[str] = []
        ordered = self._ordered_available()
        if not ordered:
            ordered = list(self.providers)

        for index, provider in enumerate(ordered):
            try:
                result = provider.generate(messages, temperature=temperature)
                if index > 0:
                    result = LLMResult(**{**result.__dict__, "fallback_used": True})
                self._advance(provider.name)
                return result
            except ProviderError as exc:
                errors.append(str(exc))
                if exc.retryable:
                    self._cooldown_until[provider.name] = time.monotonic() + self.cooldown_seconds
                    continue
                raise
        raise RuntimeError("No hay proveedor LLM disponible. " + " | ".join(errors))

    def _ordered_available(self) -> list[LLMProvider]:
        now = time.monotonic()
        with self._lock:
            available = [p for p in self.providers if self._cooldown_until.get(p.name, 0) <= now]
            if not available:
                return []
            pivot = self._cursor % len(available)
            return available[pivot:] + available[:pivot]

    def _advance(self, provider_name: str) -> None:
        with self._lock:
            for idx, provider in enumerate(self.providers):
                if provider.name == provider_name:
                    self._cursor = idx + 1
                    break

    def status(self) -> list[dict[str, object]]:
        now = time.monotonic()
        return [
            {
                "name": p.name,
                "model": p.model,
                "available": self._cooldown_until.get(p.name, 0) <= now,
            }
            for p in self.providers
        ]
