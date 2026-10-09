from __future__ import annotations

from typing import Any, TypedDict

from app.architectures.base import BaseArchitecture
from app.models import SessionState, Usage, GeneratedAnswer
from app.routing import heuristic_route


class GraphState(TypedDict, total=False):
    case: dict[str, Any]
    question: str
    session: SessionState
    target: str
    tool: str | None
    tool_args: dict[str, Any]
    facts: list
    answer: GeneratedAnswer
    usage: Usage
    trace: list[str]


class StateGraphArchitecture(BaseArchitecture):
    name = "stategraph"

    def __init__(self, llm):
        super().__init__(llm)
        self._graph = self._build_graph()

    def _build_graph(self):
        try:
            from langgraph.graph import StateGraph, START, END
        except ImportError:
            return None

        builder = StateGraph(GraphState)
        builder.add_node("detect_intent", self._detect_intent)
        builder.add_node("execute_specialist", self._execute_specialist)
        builder.add_node("validate", self._validate_node)
        builder.add_edge(START, "detect_intent")
        builder.add_edge("detect_intent", "execute_specialist")
        builder.add_edge("execute_specialist", "validate")
        builder.add_edge("validate", END)
        return builder.compile()

    def _detect_intent(self, state: GraphState):
        target = heuristic_route(state["question"])
        return {"target": target, "trace": ["detect_intent", target]}

    def _execute_specialist(self, state: GraphState):
        target = state["target"]
        case = state["case"]
        session = state["session"]
        tool, args, facts = self.tools.execute(target, state["question"], case)
        context = self.policy.for_role(case, target, session.revealed_evidence_ids)
        answer, usage = self.llm.generate(target, state["question"], context, facts)
        return {"tool": tool, "tool_args": args, "facts": facts, "answer": answer, "usage": usage}

    def _validate_node(self, state: GraphState):
        trace = list(state.get("trace", [])) + ["validator"]
        return {"trace": trace}

    def _execute(self, case: dict[str, Any], question: str, session: SessionState):
        if self._graph is not None:
            out = self._graph.invoke({"case": case, "question": question, "session": session})
            return (
                out["target"], out["trace"], out.get("tool"), out.get("tool_args", {}),
                out["answer"], out.get("usage", Usage())
            )

        # Fallback sin LangGraph: mantiene exactamente las mismas etapas para poder
        # ejecutar tests locales incluso si la dependencia aún no está instalada.
        state: GraphState = {"case": case, "question": question, "session": session}
        state.update(self._detect_intent(state))
        state.update(self._execute_specialist(state))
        state.update(self._validate_node(state))
        return state["target"], state["trace"], state.get("tool"), state.get("tool_args", {}), state["answer"], state.get("usage", Usage())
