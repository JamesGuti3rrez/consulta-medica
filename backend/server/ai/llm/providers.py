from __future__ import annotations

import json
import httpx

from server.ai.llm.base import LLMResult


class ProviderError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool = False, invalid_credential: bool = False):
        super().__init__(message)
        self.retryable = retryable
        # La clave fue rechazada (401/403): no sirve reintentar con ella, pero sí con otra del pool.
        self.invalid_credential = invalid_credential


class GroqProvider:
    def __init__(self, *, name: str, api_key: str, model: str, base_url: str, timeout: float):
        self.name = name
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def generate(self, messages: list[dict[str, str]], *, temperature: float = 0.0) -> LLMResult:
        return self._generate(messages, temperature=temperature)

    def generate_json(self, messages: list[dict[str, str]], *, temperature: float = 0.0) -> LLMResult:
        return self._generate(messages, temperature=temperature, json_mode=True)

    def _generate(self, messages, *, temperature=0.0, json_mode=False):
        payload = {"model": self.model, "messages": messages, "temperature": temperature}
        if json_mode:
            payload.update(response_format={"type": "json_object"}, max_completion_tokens=4096)
            if self.model.startswith("openai/gpt-oss-"):
                payload["reasoning_effort"] = "low"
        try:
            response = httpx.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json=payload,
                timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            raise ProviderError(str(exc), retryable=True) from exc

        if response.status_code >= 400:
            retryable = response.status_code in {408, 409, 429} or response.status_code >= 500
            detail = response.text[:400]
            raise ProviderError(
                f"{self.name}: HTTP {response.status_code}: {detail}",
                retryable=retryable,
                invalid_credential=response.status_code in {401, 403},
            )

        data = response.json()
        text = data["choices"][0]["message"].get("content")
        if not isinstance(text, str) or not text.strip():
            raise ProviderError(f"{self.name}: respuesta vacía del modelo.", retryable=True)
        usage = data.get("usage") or {}
        return LLMResult(
            text=text,
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
