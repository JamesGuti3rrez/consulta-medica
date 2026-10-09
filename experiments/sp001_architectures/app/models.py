from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any
from pydantic import BaseModel, Field


class ClinicalFact(BaseModel):
    evidence_id: str
    name: str
    value: str
    unit: str | None = None


class GeneratedAnswer(BaseModel):
    natural_response: str
    evidence_ids: list[str] = Field(default_factory=list)
    facts: list[ClinicalFact] = Field(default_factory=list)
    refused: bool = False


class RouteDecision(BaseModel):
    target: str


@dataclass
class Usage:
    llm_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    def __add__(self, other: "Usage") -> "Usage":
        return Usage(
            self.llm_calls + other.llm_calls,
            self.input_tokens + other.input_tokens,
            self.output_tokens + other.output_tokens,
        )


@dataclass
class SessionState:
    session_id: str
    case_id: str
    revealed_evidence_ids: set[str] = field(default_factory=set)
    history: list[dict[str, str]] = field(default_factory=list)


@dataclass
class TurnResult:
    architecture: str
    case_id: str
    session_id: str
    question_id: str
    question: str
    agent: str
    route_trace: list[str]
    tool: str | None
    tool_arguments: dict[str, Any]
    answer: GeneratedAnswer
    validation: dict[str, Any]
    latency_ms: float
    usage: Usage

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["answer"] = self.answer.model_dump()
        d["usage"] = asdict(self.usage)
        return d
