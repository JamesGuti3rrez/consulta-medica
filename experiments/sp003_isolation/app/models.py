from dataclasses import dataclass, field
from typing import Any

@dataclass
class LLMAnswer:
    natural_response: str
    evidence_ids: list[str] = field(default_factory=list)
    refused: bool = False

@dataclass
class Usage:
    llm_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

@dataclass
class TurnResult:
    strategy: str
    provider: str
    model: str
    temperature: float
    case_id: str
    repeat: int
    question_id: str
    kind: str
    role: str
    question: str
    context_text: str
    context_evidence_ids: list[str]
    response_raw: str
    response_final: str
    evidence_ids: list[str]
    refused: bool
    protected_context_exposure: bool
    diagnostic_leak_raw: bool
    diagnostic_leak_final: bool
    cross_role_leak_final: bool
    authorized_correct: bool
    correct_refusal: bool
    guardrail_blocked: bool
    traceable: bool
    latency_ms: float
    llm_calls: int
    input_tokens: int
    output_tokens: int
