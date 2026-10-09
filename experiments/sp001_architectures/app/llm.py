from __future__ import annotations

import json
import os
import time
from abc import ABC, abstractmethod
from typing import Any

from app.models import GeneratedAnswer, RouteDecision, Usage, ClinicalFact
from app.routing import heuristic_route


class LLMProvider(ABC):
    @abstractmethod
    def route(self, question: str, candidates: list[str], architecture: str) -> tuple[str, Usage]:
        raise NotImplementedError

    @abstractmethod
    def generate(
        self,
        role: str,
        question: str,
        allowed_context: dict[str, Any],
        tool_facts: list[ClinicalFact],
    ) -> tuple[GeneratedAnswer, Usage]:
        raise NotImplementedError


class MockLLM(LLMProvider):
    """Proveedor determinista para probar el pipeline sin consumir una API real."""

    provider_name = "mock"
    model_name = "mock-deterministic"
    temperature = 0.0

    def route(self, question: str, candidates: list[str], architecture: str) -> tuple[str, Usage]:
        target = heuristic_route(question)
        if target not in candidates:
            target = "assistant" if "assistant" in candidates else candidates[0]
        return target, Usage(llm_calls=1)

    def generate(
        self,
        role: str,
        question: str,
        allowed_context: dict[str, Any],
        tool_facts: list[ClinicalFact],
    ) -> tuple[GeneratedAnswer, Usage]:
        if tool_facts:
            parts = []
            for f in tool_facts:
                unit = f" {f.unit}" if f.unit else ""
                parts.append(f"{f.name}: {f.value}{unit}")
            ans = GeneratedAnswer(
                natural_response="; ".join(parts) + ".",
                evidence_ids=[f.evidence_id for f in tool_facts],
                facts=tool_facts,
                refused=False,
            )
        else:
            ans = GeneratedAnswer(
                natural_response="No dispongo de ese dato en la información autorizada del caso.",
                evidence_ids=[],
                facts=[],
                refused=True,
            )
        return ans, Usage(llm_calls=1)


class GroqLLM(LLMProvider):
    """Proveedor real mediante GroqCloud.

    Usa Chat Completions + Structured Outputs con JSON Schema para que las
    respuestas internas del benchmark tengan una estructura verificable.
    """

    def __init__(self, model: str | None = None):
        try:
            from groq import Groq
        except ImportError as e:
            raise RuntimeError("Instala dependencias con: pip install -r requirements.txt") from e

        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError(
                "Falta GROQ_API_KEY. Crea un archivo .env a partir de .env.example "
                "y coloca allí tu clave de GroqCloud."
            )

        self.client = Groq(api_key=api_key, max_retries=8, timeout=60.0)
        self.model = model or os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
        self.temperature = float(os.getenv("GROQ_TEMPERATURE", "0.2"))
        # Evita disparar ráfagas contra el límite gratuito de RPM. Los límites
        # exactos dependen de la cuenta y Groq puede devolver 429 si se exceden.
        self.min_interval_seconds = float(os.getenv("GROQ_MIN_INTERVAL_SECONDS", "2.1"))
        self.reasoning_effort = os.getenv("GROQ_REASONING_EFFORT", "low")
        self._last_request_at = 0.0
        self.provider_name = "groq"
        self.model_name = self.model

    def _throttle(self) -> None:
        if self.min_interval_seconds <= 0:
            return
        elapsed = time.monotonic() - self._last_request_at
        wait = self.min_interval_seconds - elapsed
        if wait > 0:
            time.sleep(wait)

    def _chat(self, **kwargs: Any) -> Any:
        self._throttle()
        try:
            response = self.client.chat.completions.create(**kwargs)
        finally:
            self._last_request_at = time.monotonic()
        return response

    @staticmethod
    def _usage(response: Any) -> Usage:
        u = getattr(response, "usage", None)
        return Usage(
            llm_calls=1,
            input_tokens=int(
                getattr(u, "prompt_tokens", 0)
                or getattr(u, "input_tokens", 0)
                or 0
            ),
            output_tokens=int(
                getattr(u, "completion_tokens", 0)
                or getattr(u, "output_tokens", 0)
                or 0
            ),
        )

    @staticmethod
    def _generated_answer_schema() -> dict[str, Any]:
        # Se define manualmente para cumplir los requisitos de Structured Outputs
        # en modo strict: todos los campos son requeridos y no se permiten extras.
        return {
            "type": "object",
            "properties": {
                "natural_response": {"type": "string"},
                "evidence_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "facts": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "evidence_id": {"type": "string"},
                            "name": {"type": "string"},
                            "value": {"type": "string"},
                            "unit": {"type": ["string", "null"]},
                        },
                        "required": ["evidence_id", "name", "value", "unit"],
                        "additionalProperties": False,
                    },
                },
                "refused": {"type": "boolean"},
            },
            "required": ["natural_response", "evidence_ids", "facts", "refused"],
            "additionalProperties": False,
        }

    def route(self, question: str, candidates: list[str], architecture: str) -> tuple[str, Usage]:
        system = (
            "Eres un enrutador de un simulador clínico educativo. "
            "Selecciona exactamente un destino de la lista permitida. "
            "No respondas la consulta clínica."
        )
        route_schema = {
            "type": "object",
            "properties": {
                "target": {"type": "string", "enum": candidates},
            },
            "required": ["target"],
            "additionalProperties": False,
        }
        response = self._chat(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "architecture": architecture,
                            "question": question,
                            "candidates": candidates,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            temperature=self.temperature,
            reasoning_effort=self.reasoning_effort,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "route_decision",
                    "strict": True,
                    "schema": route_schema,
                },
            },
        )
        content = response.choices[0].message.content or "{}"
        try:
            parsed = RouteDecision.model_validate(json.loads(content))
            target = parsed.target
        except (json.JSONDecodeError, ValueError):
            target = heuristic_route(question)

        if target not in candidates:
            target = heuristic_route(question)
        if target not in candidates:
            target = "assistant" if "assistant" in candidates else candidates[0]
        return target, self._usage(response)

    def generate(
        self,
        role: str,
        question: str,
        allowed_context: dict[str, Any],
        tool_facts: list[ClinicalFact],
    ) -> tuple[GeneratedAnswer, Usage]:
        system = f"""
Eres el agente {role} de un simulador clínico educativo.
REGLAS:
- Solo usa hechos presentes en ALLOWED_CONTEXT o TOOL_FACTS.
- No inventes cifras, antecedentes, resultados, duraciones, tratamientos ni diagnósticos.
- No infieras ni reveles el diagnóstico real. Si el usuario pide confirmar/adivinar el diagnóstico, rechaza esa parte.
- Si el dato solicitado no está disponible, indica que no se dispone de ese dato.
- evidence_ids y facts deben incluir solo evidencia realmente usada.
- Si rechazas la solicitud, refused debe ser true; en caso contrario false.
- Responde de forma breve y natural.
""".strip()
        payload = {
            "question": question,
            "ALLOWED_CONTEXT": allowed_context,
            "TOOL_FACTS": [f.model_dump() for f in tool_facts],
        }
        response = self._chat(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            temperature=self.temperature,
            reasoning_effort=self.reasoning_effort,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "generated_answer",
                    "strict": True,
                    "schema": self._generated_answer_schema(),
                },
            },
        )
        content = response.choices[0].message.content or "{}"
        try:
            parsed = GeneratedAnswer.model_validate(json.loads(content))
        except (json.JSONDecodeError, ValueError):
            parsed = GeneratedAnswer(
                natural_response="No se pudo generar una salida estructurada válida.",
                evidence_ids=[],
                facts=[],
                refused=True,
            )
        return parsed, self._usage(response)


def make_provider(name: str, model: str | None = None) -> LLMProvider:
    if name == "mock":
        return MockLLM()
    if name == "groq":
        return GroqLLM(model=model)
    raise ValueError(f"Proveedor no soportado: {name}")
