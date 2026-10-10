from __future__ import annotations

import json
import re
import unicodedata
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from server.ai.llm.gateway import LLMGateway
from server.domain import AgentReply, AgentRole

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def _normalize(text: str) -> str:
    raw = unicodedata.normalize("NFD", str(text or "").casefold())
    raw = "".join(ch for ch in raw if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", raw).strip()


EVIDENCE_SOLICITATION_PATTERNS = (
    "describe los hallazgos",
    "indicame los hallazgos",
    "dime los hallazgos",
    "proporciona los hallazgos",
    "que observas",
    "que has observado",
    "puedes describir",
    "cuentame que encontraste",
)


# Reglas comunes a todos los agentes: lo que ve el estudiante es texto plano y solo con datos del caso.
COMMON_RULES = (
    "\n\nREGLAS DE RESPUESTA:\n"
    "- Responde en texto plano: sin Markdown, sin asteriscos, sin viñetas ni títulos.\n"
    "- No menciones identificadores, códigos, referencias ni nombres de campos internos "
    "(por ejemplo retrieved_evidence o evidence_id).\n"
    "- Si el dato que te piden no está en el CONTEXTO AUTORIZADO, di que no lo sabes. "
    "Nunca lo niegues ni lo afirmes por tu cuenta."
)

# Limpieza final por si el modelo no sigue las reglas: códigos de evidencia (MED-008.sintoma.x, también
# con guiones tipográficos), «(Referencia: …)», marcas de Markdown y nombres de campos internos.
EVIDENCE_CODE = re.compile(r"\b[A-Z]{3,5}[-‐‑‒–]\d{3}(?:\.[A-Za-z0-9_]+)*\b")
REFERENCE_NOTE = re.compile(r"\(?\s*(?:Referencias?|Fuente|Evidencia)\s*:[^)\n]*\)?", re.IGNORECASE)
INTERNAL_TERMS = re.compile(
    r"\(?\s*(?:retrieved[_ ]evidence|evidence[_ ]ids?|public[_ ]evidence)\s*\)?", re.IGNORECASE
)


def clean_reply(text: str) -> str:
    text = REFERENCE_NOTE.sub("", text)
    text = EVIDENCE_CODE.sub("", text)
    text = INTERNAL_TERMS.sub("", text)
    text = re.sub(r"[*_]{2,}|^#+\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*[-•]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\(\s*\)", "", text)
    text = re.sub(r"\s*\n\s*", " ", text)
    text = re.sub(r"\s+([.,;:])", r"\1", text)
    return re.sub(r"\s{2,}", " ", text).strip()


class BaseAgent(ABC):
    role: AgentRole

    def __init__(self, gateway: LLMGateway):
        self.gateway = gateway

    @property
    @abstractmethod
    def prompt_filename(self) -> str: ...

    @property
    def system_prompt(self) -> str:
        return (PROMPTS_DIR / self.prompt_filename).read_text(encoding="utf-8").strip()

    @staticmethod
    def _has_retrieved_evidence(context: dict[str, Any]) -> bool:
        return bool(context.get("retrieved_evidence"))

    @staticmethod
    def _asks_student_to_supply_available_evidence(text: str) -> bool:
        normalized = _normalize(text)
        return any(pattern in normalized for pattern in EVIDENCE_SOLICITATION_PATTERNS)

    @staticmethod
    def _deterministic_evidence_fallback(context: dict[str, Any]) -> str:
        evidence = context.get("retrieved_evidence") or []
        texts = [str(item.get("text", "")).strip() for item in evidence if item.get("text")]
        if texts:
            return " ".join(texts)
        return "No hay evidencia adicional autorizada para esta solicitud."

    def _messages(self, *, student_message: str, context: dict[str, Any]) -> list[dict[str, str]]:
        grounding_rule = ""
        if self._has_retrieved_evidence(context):
            grounding_rule = (
                "\n\nREGLA OBLIGATORIA DE ENTREGA DE EVIDENCIA:\n"
                "La evidencia solicitada YA ESTÁ DISPONIBLE en retrieved_evidence. "
                "Debes comunicar al estudiante esos hallazgos o resultados usando únicamente esa evidencia. "
                "No le pidas al estudiante que describa, invente, proporcione o complete los hallazgos. "
                "No añadas datos clínicos externos y no menciones identificadores internos."
            )
        else:
            grounding_rule = (
                "\n\nREGLA DE AUSENCIA DE EVIDENCIA:\n"
                "Si no hay evidencia recuperada suficiente para responder, indícalo de forma breve y no inventes datos."
            )

        return [
            {"role": "system", "content": self.system_prompt + grounding_rule + COMMON_RULES},
            {
                "role": "user",
                "content": (
                    "CONTEXTO AUTORIZADO:\n"
                    + json.dumps(context, ensure_ascii=False, indent=2)
                    + "\n\nMENSAJE DEL ESTUDIANTE:\n"
                    + student_message
                ),
            },
        ]

    def respond(self, *, student_message: str, context: dict[str, Any], temperature: float = 0.0) -> AgentReply:
        messages = self._messages(student_message=student_message, context=context)
        first = self.gateway.generate(messages, temperature=temperature)

        result = first
        grounding_retry_used = False
        grounding_fallback_used = False
        total_input_tokens = first.input_tokens
        total_output_tokens = first.output_tokens
        provider_fallback_used = first.fallback_used

        # Si el modelo ignora una evidencia ya recuperada y pide al estudiante que
        # aporte el resultado, se corrige una vez. Si persiste, el código falla
        # cerrado con una respuesta determinística basada solo en la evidencia.
        if self._has_retrieved_evidence(context) and self._asks_student_to_supply_available_evidence(first.text):
            grounding_retry_used = True
            correction = {
                "role": "user",
                "content": (
                    "CORRECCIÓN DE GROUNDING: la evidencia ya fue recuperada y está disponible. "
                    "Responde ahora comunicando directamente los hallazgos presentes en retrieved_evidence. "
                    "No pidas al estudiante que los describa y no agregues información externa."
                ),
            }
            retry = self.gateway.generate([*messages, {"role": "assistant", "content": first.text}, correction], temperature=temperature)
            total_input_tokens += retry.input_tokens
            total_output_tokens += retry.output_tokens
            provider_fallback_used = provider_fallback_used or retry.fallback_used
            result = retry

            if self._asks_student_to_supply_available_evidence(retry.text):
                grounding_fallback_used = True
                # Conservamos provider/model para trazabilidad, pero el texto se
                # sustituye por evidencia autorizada sin una tercera llamada LLM.
                result_text = self._deterministic_evidence_fallback(context)
            else:
                result_text = retry.text
        else:
            result_text = first.text

        evidence_ids = [
            str(item.get("evidence_id"))
            for item in context.get("retrieved_evidence", [])
            if item.get("evidence_id")
        ]
        if self.role == AgentRole.MEDICO_ASISTENTE and not evidence_ids:
            evidence_ids = [
                str(item.get("evidence_id"))
                for item in context.get("revealed_evidence", [])
                if item.get("evidence_id")
            ]
        return AgentReply(
            role=self.role,
            text=clean_reply(result_text),
            provider=result.provider,
            model=result.model,
            evidence_ids=evidence_ids,
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
            fallback_used=provider_fallback_used,
            grounding_retry_used=grounding_retry_used,
            grounding_fallback_used=grounding_fallback_used,
        )
