from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class LLMResult:
    text: str
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    fallback_used: bool = False


class LLMProvider(Protocol):
    name: str
    model: str
    def generate(self, messages: list[dict[str, str]], *, temperature: float = 0.0) -> LLMResult: ...
