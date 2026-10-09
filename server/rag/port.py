from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from server.domain import AgentRole


@dataclass(frozen=True)
class RetrievedEvidence:
    evidence_id: str
    text: str
    score: float = 1.0


class RetrieverPort(Protocol):
    def retrieve(
        self,
        *,
        query: str,
        case_id: str,
        agent_role: AgentRole,
        allowed_evidence_ids: list[str],
        top_k: int = 3,
        session_id: str | None = None,
    ) -> list[RetrievedEvidence]: ...
