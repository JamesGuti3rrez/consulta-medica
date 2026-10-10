from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from server.domain import AgentRole, SessionPhase
from server.orchestration.store import InMemorySessionStore


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MultiAgentSessionService:
    def __init__(
        self,
        *,
        graph,
        repository,
        disclosure_policy,
        store: InMemorySessionStore,
        local_tracer,
        langsmith_observer,
    ):
        self.graph = graph
        self.repository = repository
        self.disclosure_policy = disclosure_policy
        self.store = store
        self.local_tracer = local_tracer
        self.langsmith_observer = langsmith_observer

    def start(self, case_id: str) -> dict:
        case = self.repository.get_conversation_case(case_id)
        state = {
            "session_id": str(uuid4()),
            "case_id": case["case_id"],
            "phase": SessionPhase.PRESENTACION.value,
            "active_agent": AgentRole.MEDICO_ASISTENTE.value,
            "revealed_evidence_ids": self.disclosure_policy.initial_evidence_ids(case),
            "history": [],
            "started_at": _now(),
            "updated_at": _now(),
            "finished_at": None,
        }
        self.store.create(state)
        self.store.event(
            state["session_id"],
            {
                "type": "session_started",
                "case_id": state["case_id"],
                "phase": state["phase"],
                "evidence_ids": state["revealed_evidence_ids"],
            },
        )
        return self._public(state)

    def get(self, session_id: str) -> dict:
        return self._public(self.store.get(session_id))

    def message(self, session_id: str, student_message: str) -> dict:
        session = self.store.get(session_id)
        if session["phase"] == SessionPhase.FINALIZADA.value:
            raise ValueError("La sesión ya finalizó.")

        graph_state = {
            "session_id": session_id,
            "case_id": session["case_id"],
            "phase": session["phase"],
            "student_message": student_message,
            "revealed_evidence_ids": session["revealed_evidence_ids"],
            "conversation_tail": session["history"],
        }
        result = self.graph.invoke(graph_state)
        session["phase"] = result["phase"]
        session["active_agent"] = result["active_agent"]
        session["updated_at"] = _now()
        session["revealed_evidence_ids"] = list(
            dict.fromkeys([
                *session["revealed_evidence_ids"],
                *result.get("retrieved_evidence_ids", []),
            ])
        )
        session["history"].append({"role": "student", "text": student_message})
        session["history"].append({"role": result["active_agent"], "text": result["response_text"]})
        self.store.save(session)

        event = {
            "type": "turn",
            "case_id": session["case_id"],
            "phase": session["phase"],
            "intent": result.get("route_intent"),
            "agent": result["active_agent"],
            "route_reason": result.get("route_reason"),
            "route_confidence": result.get("route_confidence"),
            "provider": result.get("provider"),
            "model": result.get("model"),
            "input_tokens": result.get("input_tokens", 0),
            "output_tokens": result.get("output_tokens", 0),
            "fallback_used": result.get("fallback_used", False),
            "grounding_retry_used": result.get("grounding_retry_used", False),
            "grounding_fallback_used": result.get("grounding_fallback_used", False),
            "evidence_ids": result.get("retrieved_evidence_ids", []),
            "blocked": result.get("blocked", False),
            "block_reason": result.get("block_reason"),
        }
        self.store.event(session_id, event)
        self.local_tracer.record({"session_id": session_id, **event})
        self.langsmith_observer.record_turn(
            inputs={"message": student_message, "case_id": session["case_id"]},
            outputs={"response": result["response_text"], "agent": result["active_agent"]},
            metadata=event,
        )
        return {
            "session": self._public(session),
            "intent": result.get("route_intent"),
            "agent": result["active_agent"],
            "response": result["response_text"],
            "provider": result.get("provider"),
            "model": result.get("model"),
            "evidence_ids": result.get("retrieved_evidence_ids", []),
            "blocked": result.get("blocked", False),
        }

    def finish(self, session_id: str) -> dict:
        session = self.store.get(session_id)
        session["phase"] = SessionPhase.FINALIZADA.value
        session["active_agent"] = AgentRole.ORCHESTRATOR.value
        session["updated_at"] = _now()
        session["finished_at"] = _now()
        self.store.save(session)
        self.store.event(session_id, {"type": "session_finished", "case_id": session["case_id"]})
        return self._public(session)

    def events(self, session_id: str) -> list[dict]:
        return self.store.events(session_id)

    @staticmethod
    def _public(state: dict) -> dict:
        keys = {
            "session_id", "case_id", "phase", "active_agent", "revealed_evidence_ids",
            "started_at", "updated_at", "finished_at",
        }
        return {key: state[key] for key in keys}
