from __future__ import annotations

import json
import httpx

from server.ai.llm.base import LLMResult


class ProviderError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


class GroqProvider:
    def __init__(self, *, name: str, api_key: str, model: str, base_url: str, timeout: float):
        self.name = name
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def generate(self, messages: list[dict[str, str]], *, temperature: float = 0.0) -> LLMResult:
        try:
            response = httpx.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json={"model": self.model, "messages": messages, "temperature": temperature},
                timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            raise ProviderError(str(exc), retryable=True) from exc

        if response.status_code >= 400:
            retryable = response.status_code in {408, 409, 429} or response.status_code >= 500
            detail = response.text[:400]
            raise ProviderError(f"{self.name}: HTTP {response.status_code}: {detail}", retryable=retryable)

        data = response.json()
        usage = data.get("usage") or {}
        return LLMResult(
            text=data["choices"][0]["message"]["content"],
            provider=self.name,
            model=self.model,
            input_tokens=int(usage.get("prompt_tokens") or 0),
            output_tokens=int(usage.get("completion_tokens") or 0),
        )


class LocalDevelopmentProvider:
    """Respuesta local para probar routing/aislamiento sin consumir un LLM real."""
    name = "local-development"
    model = "rules-only"

    def generate(self, messages: list[dict[str, str]], *, temperature: float = 0.0) -> LLMResult:
        last = messages[-1]["content"] if messages else ""
        context = {}
        marker = "CONTEXTO AUTORIZADO:\n"
        end_marker = "\n\nMENSAJE DEL ESTUDIANTE:\n"
        if marker in last and end_marker in last:
            raw = last.split(marker, 1)[1].split(end_marker, 1)[0]
            try:
                context = json.loads(raw)
            except json.JSONDecodeError:
                context = {}
        evidence = context.get("retrieved_evidence") or []
        if not evidence:
            evidence = context.get("revealed_evidence") or []
        if evidence:
            text = " ".join(str(item.get("text", "")) for item in evidence if item.get("text"))
        else:
            text = "No hay evidencia adicional autorizada para esta solicitud."
        return LLMResult(text=text, provider=self.name, model=self.model)
