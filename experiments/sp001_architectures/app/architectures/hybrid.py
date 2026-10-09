from __future__ import annotations

from typing import Any
from app.architectures.base import BaseArchitecture
from app.models import SessionState


class HybridArchitecture(BaseArchitecture):
    name = "supervisor_handoffs"

    def _execute(self, case: dict[str, Any], question: str, session: SessionState):
        candidates = ["assistant", "patient", "laboratory", "radiology", "specialist"]
        # 1) supervisor aplica política global
        coarse_target, u1 = self.llm.route(question, candidates, self.name)
        # 2) médico asistente confirma/realiza el handoff con otra decisión LLM
        target, u2 = self.llm.route(question, candidates, self.name + ":assistant")
        if coarse_target != "assistant" and target == "assistant":
            target = coarse_target
        tool, args, facts = self.tools.execute(target, question, case)
        context = self.policy.for_role(case, target, session.revealed_evidence_ids)
        answer, u3 = self.llm.generate(target, question, context, facts)
        trace = ["supervisor", "assistant", target, "assistant", "supervisor"]
        return target, trace, tool, args, answer, u1 + u2 + u3
