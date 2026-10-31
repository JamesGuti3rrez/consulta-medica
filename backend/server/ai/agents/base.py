from __future__ import annotations

import json
import re
import unicodedata
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from server.ai.agents.invencion import invented_symptoms, omitted_figures, invented_figures
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
    "- No inventes síntomas, enfermedades, antecedentes, valores, hallazgos ni resultados que no estén "
    "en el CONTEXTO AUTORIZADO."
)

# Limpieza final por si el modelo no sigue las reglas: códigos de evidencia (MED-007.sintoma.x, también
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

    # Qué hacer cuando la pregunta no tiene dato en el caso; cada agente puede definir la suya.
    # Respuesta a un pedido genérico (sin nombrar examen); solo la usan laboratorio y radiología.
    generic_request_reply: str | None = None
    missing_data_rule = (
        "Si no hay evidencia recuperada suficiente para responder, indícalo de forma breve y no inventes datos."
    )
    missing_data_reply = "No hay evidencia adicional autorizada para esta solicitud."

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
                "\n\nREGLA DE AUSENCIA DE EVIDENCIA:\n" + self.missing_data_rule
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
        # Pedido genérico sin resultado (lo marca el orquestador): frase fija que pregunta qué examen, sin LLM.
        if context.get("pedido_generico") and self.generic_request_reply:
            return AgentReply(role=self.role, text=self.generic_request_reply, provider="reglas", model="reglas",
                              evidence_ids=[], input_tokens=0, output_tokens=0, fallback_used=False,
                              grounding_retry_used=False, grounding_fallback_used=False)
        if self.role in (AgentRole.LABORATORIO, AgentRole.RADIOLOGIA, AgentRole.ESPECIALISTA) and not self._has_retrieved_evidence(context):
            return AgentReply(role=self.role, text=self.missing_data_reply, provider="reglas", model="reglas")
        if self.role in (AgentRole.LABORATORIO, AgentRole.RADIOLOGIA, AgentRole.ESPECIALISTA):
            # Los informes existentes se entregan literalmente: un LLM no necesita reinterpretar sus cifras.
            return AgentReply(role=self.role, text=clean_reply(self._deterministic_evidence_fallback(context)),
                              provider="reglas", model="dato-canonico",
                              evidence_ids=[i["evidence_id"] for i in context["retrieved_evidence"]])
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
        elif not self._has_retrieved_evidence(context) and self._asks_student_to_supply_available_evidence(first.text):
            # Sin datos que entregar, pedir al estudiante que describa o invente hallazgos confunde: se dice que
            # el dato no está disponible.
            grounding_fallback_used = True
            result_text = self.missing_data_reply
        else:
            result_text = first.text

        # Síntomas sin respaldo: se pide una corrección; si el modelo insiste,
        # se usa evidencia autorizada o se reconoce que falta el dato.
        invented = invented_symptoms(result_text, context)
        if invented and not grounding_fallback_used:
            grounding_retry_used = True
            correction = {
                "role": "user",
                "content": (
                    f"CORRECCIÓN: tu respuesta menciona {', '.join(invented)}, que no está en el CONTEXTO "
                    "AUTORIZADO. Responde de nuevo sin mencionarlo y sin añadir otros síntomas."
                ),
            }
            retry = self.gateway.generate([*messages, {"role": "assistant", "content": result_text}, correction], temperature=temperature)
            total_input_tokens += retry.input_tokens
            total_output_tokens += retry.output_tokens
            provider_fallback_used = provider_fallback_used or retry.fallback_used
            result = retry
            if invented_symptoms(retry.text, context):
                grounding_fallback_used = True
                # Se quitan solo las frases con el síntoma inventado; si no queda nada, la respuesta base.
                kept = [sentence for sentence in re.split(r"(?<=[.!?])\s+", retry.text.strip())
                        if sentence and not invented_symptoms(sentence, context)]
                if kept:
                    result_text = " ".join(kept)
                else:
                    result_text = (self._deterministic_evidence_fallback(context)
                                   if self._has_retrieved_evidence(context) else self.missing_data_reply)
            else:
                result_text = retry.text

        # Cifras del dato que la respuesta omite (una dosis, una duración, un valor): se pide una corrección
        # una vez y se usa la nueva respuesta si ya no omite nada.
        omitted = omitted_figures(result_text, context) if self._has_retrieved_evidence(context) else []
        if omitted and not grounding_fallback_used:
            grounding_retry_used = True
            correction = {
                "role": "user",
                "content": (
                    f"CORRECCIÓN: tu respuesta omite datos de retrieved_evidence ({', '.join(omitted)}). Responde de "
                    "nuevo con tus palabras incluyendo esas cifras, sin añadir nada que no esté en el contexto."
                ),
            }
            retry = self.gateway.generate([*messages, {"role": "assistant", "content": result_text}, correction], temperature=temperature)
            total_input_tokens += retry.input_tokens
            total_output_tokens += retry.output_tokens
            provider_fallback_used = provider_fallback_used or retry.fallback_used
            if not omitted_figures(retry.text, context) and not invented_symptoms(retry.text, context):
                result = retry
                result_text = retry.text

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
        # Último control: ninguna cifra nueva del LLM puede convertirse en un resultado clínico.
        final_text = clean_reply(result_text)
        if invented_figures(final_text, context):
            final_text = clean_reply(self._deterministic_evidence_fallback(context))
            grounding_fallback_used = True
        return AgentReply(
            role=self.role,
            text=final_text,
            provider=result.provider,
            model=result.model,
            evidence_ids=evidence_ids,
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
            fallback_used=provider_fallback_used,
            grounding_retry_used=grounding_retry_used,
            grounding_fallback_used=grounding_fallback_used,
        )
