"""El médico tratante reformula lo que pide el estudiante como pregunta directa al paciente.

Solo recibe la frase del estudiante: nunca el caso ni la evidencia. La autorización de qué se revela
sigue usando la frase original (engine/disclosure), así que la reformulación no puede desbloquear datos.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from server.ai.llm.gateway import LLMGateway

PROMPT = "reformulador.md"
MAX_LENGTH = 300
LOCAL_PROVIDER = "local-development"

# «Pregúntale si…», «pregúntele al paciente desde cuándo…», «dígale que me cuente…».
ORDER_PREFIX = re.compile(
    r"^\s*(?:por favor,?\s*)?(?:doctor(?:a)?,?\s*)?"
    r"(?:preg[uú]nt(?:ale|ele|ales|eles|e|a)|consult(?:ale|ele)|d[ií]gale(?:\s+que)?|p[ií]dale\s+que(?:\s+me)?)"
    r"\s+(?:al?\s+(?:paciente|se[nñ]ora?|ni[nñ]o|ni[nñ]a)\s+)?",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Reformulation:
    text: str
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    used_llm: bool = False


def reformulate_without_llm(student_message: str) -> str:
    """Regla simple: quita la orden («pregúntale si…») y devuelve la pregunta con sus signos."""
    text = " ".join(student_message.split()).strip(" ¿?.!¡")
    match = ORDER_PREFIX.match(text)
    if match:
        text = text[match.end():]
        text = re.sub(r"^(?:si|que)\s+", "", text, flags=re.IGNORECASE)
    if not text:
        return student_message.strip()
    return f"¿{text[0].upper()}{text[1:]}?"


class QuestionReformulator:
    def __init__(self, gateway: LLMGateway, prompts_dir):
        self.gateway = gateway
        self.system_prompt = (prompts_dir / PROMPT).read_text(encoding="utf-8").strip()

    def reformulate(self, student_message: str, *, temperature: float = 0.0) -> Reformulation:
        fallback = reformulate_without_llm(student_message)
        try:
            result = self.gateway.generate(
                [
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": student_message},
                ],
                temperature=temperature,
            )
        except Exception:  # noqa: BLE001 - sin LLM disponible, la regla simple basta
            return Reformulation(fallback, LOCAL_PROVIDER, "rules-only")
        text = " ".join(result.text.split()).strip("\"'«» ")
        if result.provider == LOCAL_PROVIDER or not text or len(text) > MAX_LENGTH:
            return Reformulation(fallback, result.provider, result.model)
        return Reformulation(
            text=text,
            provider=result.provider,
            model=result.model,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            used_llm=True,
        )
