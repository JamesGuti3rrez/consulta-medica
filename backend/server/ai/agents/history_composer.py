"""Componente de redacción estructurada; no accede a casos, permisos ni persistencia."""

import json
import re
from dataclasses import replace

from .base import PROMPTS_DIR


class HistoryComposer:
    def __init__(self, gateway):
        self.gateway = gateway
        self.prompt = (PROMPTS_DIR / "completar_historia.md").read_text(encoding="utf-8")
        sections = re.split(r"FASE (seleccionar|generar|validar):", self.prompt)
        self.phase_prompts = {sections[index]: sections[0] + sections[index + 1]
                              for index in range(1, len(sections), 2)}

    def call(self, phase: str, payload: dict):
        messages = [
            {"role": "system", "content": self.phase_prompts[phase]},
            {"role": "user", "content": json.dumps({"fase": phase, **payload}, ensure_ascii=False)},
        ]
        generate = getattr(self.gateway, "generate_json", self.gateway.generate)
        input_tokens = output_tokens = 0
        fallback_used = False
        for attempt in range(2):
            result = generate(messages, temperature=0.0)
            input_tokens += result.input_tokens
            output_tokens += result.output_tokens
            fallback_used |= result.fallback_used
            text = (result.text or "").strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            try:
                data = json.loads(text)
                if not isinstance(data, dict) or not data:
                    raise ValueError("Se esperaba un objeto JSON no vacío.")
            except ValueError:
                if attempt:
                    raise
                messages.append({"role": "user", "content":
                                 "La respuesta anterior no fue un objeto JSON válido. Devuelve solo el objeto de esta fase."})
                continue
            return data, replace(result, input_tokens=input_tokens, output_tokens=output_tokens,
                                 fallback_used=fallback_used)
