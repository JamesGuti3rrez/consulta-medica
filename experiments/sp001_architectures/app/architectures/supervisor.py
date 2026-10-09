from __future__ import annotations

from typing import Any
from app.architectures.base import BaseArchitecture
from app.models import SessionState, Usage


class SupervisorArchitecture(BaseArchitecture):
    name = "supervisor"

    def _execute(self, case: dict[str, Any], question: str, session: SessionState):
        candidates = ["assistant", "patient", "laboratory", "radiology", "specialist"]
        target, u1 = self.llm.route(question, candidates, self.name)
        tool, args, facts = self.tools.execute(target, question, case)
        context = self.policy.for_role(case, target, session.revealed_evidence_ids)
        answer, u2 = self.llm.generate(target, question, context, facts)
        trace = ["supervisor", target, "supervisor"]
        return target, trace, tool, args, answer, u1 + u2
