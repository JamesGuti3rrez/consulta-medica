from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TypedDict


class AgentRole(str, Enum):
    ORCHESTRATOR = "orchestrator"
    MEDICO_ASISTENTE = "medico_asistente"
    PACIENTE = "paciente"
    LABORATORIO = "laboratorio"
    RADIOLOGIA = "radiologia"
    ESPECIALISTA = "especialista"


class SessionPhase(str, Enum):
    PRESENTACION = "presentacion"
    ANAMNESIS = "anamnesis"
    EXAMENES = "examenes"
    HIPOTESIS = "hipotesis"
    DIAGNOSTICO = "diagnostico"
    CIERRE = "cierre"
    FINALIZADA = "finalizada"


class Intent(str, Enum):
    ASK_PATIENT = "ask_patient"
    REQUEST_LAB = "request_lab"
    REQUEST_RADIOLOGY = "request_radiology"
    REQUEST_SPECIALIST = "request_specialist"
    ASK_ASSISTANT = "ask_assistant"
    EXAMINE = "examine"
    PROPOSE_HYPOTHESIS = "propose_hypothesis"
    PROPOSE_DIAGNOSIS = "propose_diagnosis"
    PROPOSE_TREATMENT = "propose_treatment"
    FINISH = "finish"


@dataclass(frozen=True)
class RouteDecision:
    intent: Intent
    target: AgentRole
    confidence: float
    reason: str


@dataclass
class AgentReply:
    role: AgentRole
    text: str
    provider: str
    model: str
    evidence_ids: list[str] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    fallback_used: bool = False
    blocked: bool = False
    block_reason: str | None = None


class TurnGraphState(TypedDict, total=False):
    session_id: str
    case_id: str
    phase: str
    student_message: str
    revealed_evidence_ids: list[str]
    conversation_tail: list[dict[str, str]]
    active_agent: str
    route_intent: str
    route_reason: str
    route_confidence: float
    response_text: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    fallback_used: bool
    retrieved_evidence_ids: list[str]
    blocked: bool
    block_reason: str | None
