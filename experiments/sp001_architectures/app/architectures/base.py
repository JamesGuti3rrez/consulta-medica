from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any

from app.context_policy import ContextPolicy
from app.llm import LLMProvider
from app.models import SessionState, TurnResult, Usage
from app.tools import ToolRegistry
from app.verifier import Verifier


class BaseArchitecture(ABC):
    name = "base"

    def __init__(self, llm: LLMProvider):
        self.llm = llm
        self.tools = ToolRegistry()
        self.verifier = Verifier()
        self.policy = ContextPolicy()

    @abstractmethod
    def _execute(self, case: dict[str, Any], question: str, session: SessionState):
        raise NotImplementedError

    def run_turn(self, case: dict[str, Any], question_id: str, question: str, session: SessionState) -> TurnResult:
        t0 = time.perf_counter()
        agent, trace, tool, tool_args, answer, usage = self._execute(case, question, session)
        validation = self.verifier.verify(case, answer)
        session.revealed_evidence_ids.update(answer.evidence_ids)
        session.history.append({"role": "user", "content": question})
        session.history.append({"role": "assistant", "content": answer.natural_response})
        latency = (time.perf_counter() - t0) * 1000
        return TurnResult(
            architecture=self.name,
            case_id=case["case_id"],
            session_id=session.session_id,
            question_id=question_id,
            question=question,
            agent=agent,
            route_trace=trace,
            tool=tool,
            tool_arguments=tool_args,
            answer=answer,
            validation=validation,
            latency_ms=latency,
            usage=usage,
        )
