from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from server.ai.llm.gateway import LLMGateway
from server.domain import AgentReply, AgentRole

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


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

    def respond(self, *, student_message: str, context: dict[str, Any], temperature: float = 0.0) -> AgentReply:
        messages = [
            {"role": "system", "content": self.system_prompt},
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
        result = self.gateway.generate(messages, temperature=temperature)
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
            text=result.text,
            provider=result.provider,
            model=result.model,
            evidence_ids=evidence_ids,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            fallback_used=result.fallback_used,
        )
