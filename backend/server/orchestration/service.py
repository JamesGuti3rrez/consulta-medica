from __future__ import annotations

from datetime import datetime, timezone
from copy import deepcopy
from uuid import uuid4

from server.domain import AgentRole, Intent, SessionPhase
from server.orchestration.store import InMemorySessionStore
from server.tracing.sanitize import audit_metadata


class SessionNotFinished(Exception):
    """El reporte solo existe cuando la consulta terminó (HU-006)."""


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
        state_machine,
        safety_engine,
        evaluation_engine,
    ):
        self.graph = graph
        self.repository = repository
        self.disclosure_policy = disclosure_policy
        self.store = store
        self.local_tracer = local_tracer
        self.langsmith_observer = langsmith_observer
        self.state_machine = state_machine
        self.safety_engine = safety_engine
        self.evaluation_engine = evaluation_engine

    def start(self, case_id: str, owner_id: str | None = None, access_token_hash: str | None = None) -> dict:
        state = self.prepare_start(case_id, owner_id=owner_id, access_token_hash=access_token_hash)
        self.store.create(state)
        self.store.event(state['session_id'], {'type': 'session_started', 'case_id': state['case_id'],
                                             'phase': state['phase'], 'evidence_ids': state['revealed_evidence_ids']})
        return self._public(state)

    def prepare_start(self, case_id: str, owner_id: str | None = None, access_token_hash: str | None = None) -> dict:
        """Construye el estado sin escribir; el inicio de grupo se confirma atómicamente por RPC."""
        case = self.repository.get_conversation_case(case_id)
        state = {
            "session_id": str(uuid4()),
            "case_id": case["case_id"],
            "phase": SessionPhase.PRESENTACION.value,
            "active_agent": AgentRole.MEDICO_ASISTENTE.value,
            "revealed_evidence_ids": self.disclosure_policy.initial_evidence_ids(case),
            "requested_evidence_ids": [],
            "avatar_state": self.state_machine.initial_avatar_state(case),
            "evaluation": None,
            # Alumno con sesión iniciada que empezó la consulta: solo él puede guardarla. No es público.
            "owner_id": owner_id,
            # Consulta de invitado: hash SHA-256 de su credencial de capacidad (TA-011). Tampoco es público.
            "access_token_hash": access_token_hash,
            "history": [],
            "started_at": _now(),
            "updated_at": _now(),
            "finished_at": None,
        }
        return state

    def revealed(self, session_id):
        state = self.store.get(session_id)
        synthetic = [v['evidence'] for v in state.get('synthetic_exam_results', {}).values()]
        return self._turn_evidence(state['case_id'], state['revealed_evidence_ids'], synthetic)

    def access_details(self, session_id):
        state = self.store.get(session_id)
        return {key: state.get(key) for key in ('owner_id', 'access_token_hash', 'group_assignment_id')}

    def get(self, session_id: str) -> dict:
        return self._public(self.store.get(session_id))

    def message(self, session_id: str, student_message: str) -> dict:
        session = self.store.get(session_id)
        if session["phase"] == SessionPhase.FINALIZADA.value:
            raise ValueError("La sesión ya finalizó.")
        self._ensure_clinical_state(session)

        graph_state = {
            "session_id": session_id,
            "case_id": session["case_id"],
            "phase": session["phase"],
            "student_message": student_message,
            "revealed_evidence_ids": session["revealed_evidence_ids"],
            "conversation_tail": session["history"],
            "synthetic_exam_results": deepcopy(session.get("synthetic_exam_results", {})),
        }
        result = self.graph.invoke(graph_state)
        session["phase"] = result["phase"]
        session["active_agent"] = result["active_agent"]
        session["updated_at"] = _now()
        if result.get("synthetic_exam_results"):
            session["synthetic_exam_results"] = deepcopy(result["synthetic_exam_results"])
        intent = Intent(result["route_intent"])
        safety_alerts = self.safety_engine.evaluate_treatment(
            case_id=session["case_id"],
            message=student_message,
            intent=intent,
        )
        session["revealed_evidence_ids"] = list(
            dict.fromkeys([
                *session["revealed_evidence_ids"],
                *result.get("retrieved_evidence_ids", []),
            ])
        )
        session["requested_evidence_ids"] = list(
            dict.fromkeys([
                *session["requested_evidence_ids"],
                *result.get("retrieved_evidence_ids", []),
            ])
        )
        session["avatar_state"] = self.state_machine.update_avatar_state(
            session["avatar_state"],
            SessionPhase(session["phase"]),
            safety_alerts,
        )
        session["history"].append({"role": "student", "text": student_message})
        if result.get("doctor_question"):
            session["history"].append({"role": "medico_tratante", "text": result["doctor_question"]})
        session["history"].append({"role": result["active_agent"], "text": result["response_text"]})
        self.store.save(session)

        event = {
            "type": "turn",
            "student_message": student_message,
            "response_text": result["response_text"],
            "case_id": session["case_id"],
            "phase": session["phase"],
            "intent": result.get("route_intent"),
            "agent": result["active_agent"],
            "route_reason": result.get("route_reason"),
            "route_confidence": result.get("route_confidence"),
            "doctor_question": result.get("doctor_question"),
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
            "synthetic_generated_ids": result.get("synthetic_generated_ids", []),
            "synthetic_reused_ids": result.get("synthetic_reused_ids", []),
            "data_source": result.get("data_source", "curado"),
            "synthetic_rejection_reason": result.get("synthetic_rejection_reason"),
            "safety_alerts": [alert["code"] for alert in safety_alerts],
            "exam_validation": result.get("exam_validation"),
        }
        self.store.event(session_id, event)
        safe_event = audit_metadata({"session_id": session_id, **event})
        self.local_tracer.record(safe_event)
        self.langsmith_observer.record_turn(
            inputs={"case_id": session["case_id"]},
            outputs={"agent": result["active_agent"], "blocked": result.get("blocked", False)},
            metadata=safe_event,
        )
        return {
            "session": self._public(session),
            "intent": result.get("route_intent"),
            "agent": result["active_agent"],
            "response": result["response_text"],
            "synthetic_generated_ids": result.get("synthetic_generated_ids", []),
            "synthetic_reused_ids": result.get("synthetic_reused_ids", []),
            "data_source": result.get("data_source", "curado"),
            "doctor_question": result.get("doctor_question"),
            "provider": result.get("provider"),
            "model": result.get("model"),
            "evidence_ids": result.get("retrieved_evidence_ids", []),
            "blocked": result.get("blocked", False),
            "safety_alerts": safety_alerts,
            "clinical_evidence": self._turn_evidence(session["case_id"], result.get("retrieved_evidence_ids", []),
                                                     result.get("exam_evidence", [])),
            "exam_validation": result.get("exam_validation"),
        }

    def _turn_evidence(self, case_id, evidence_ids, synthetic):
        from server.cases.rules import evidence_text
        case = self.repository.get_conversation_case(case_id)
        items = {i["evidence_id"]: i for i in [*case["on_request"], *synthetic]}
        return [{"evidence_id": eid, "label": items[eid]["label"], "text": evidence_text(items[eid]),
                 "synthetic": bool(items[eid].get("synthetic")),
                 **({"indicators": deepcopy(items[eid]["indicators"]), "provenance": deepcopy(items[eid]["provenance"])}
                    if items[eid].get("synthetic") else {})}
                for eid in dict.fromkeys(evidence_ids) if eid in items and eid.startswith(case_id + ".")]

    def finish(self, session_id: str, diagnosis: str | None = None, hypotheses: list[dict] | None = None) -> dict:
        session = self.store.get(session_id)
        # Cerrar otra vez devuelve el mismo resultado: no se recalcula ni se duplica el intento guardado.
        if session["phase"] == SessionPhase.FINALIZADA.value and session.get("evaluation"):
            return self._public(session)
        # Lo que registró el estudiante queda en la consulta para el reporte final (HU-006). No es público.
        session["student_diagnosis"] = diagnosis if diagnosis is not None else ""
        session["student_hypotheses"] = list(hypotheses or [])
        self._ensure_clinical_state(session)
        case = self.repository.get_conversation_case(session["case_id"])
        session["evaluation"] = self.evaluation_engine.evaluate(
            case_id=session["case_id"],
            evidence_ids=session.get("requested_evidence_ids", []),
            initial_evidence_ids=self.disclosure_policy.initial_evidence_ids(case),
        )
        session["phase"] = SessionPhase.FINALIZADA.value
        session["active_agent"] = AgentRole.ORCHESTRATOR.value
        session["avatar_state"] = self.state_machine.update_avatar_state(
            session["avatar_state"],
            SessionPhase.FINALIZADA,
        )
        session["updated_at"] = _now()
        session["finished_at"] = _now()
        session["diagnosis_evaluation"] = self.evaluation_engine.evaluate_diagnosis(session)
        if session.get('group_assignment_id') and hasattr(self.store, 'finalize_group'):
            if not self.store.finalize_group(session):
                return self._public(self.store.get(session_id))
        else:
            self.store.save(session)
        self.store.event(session_id, {"type": "session_finished", "case_id": session["case_id"],
                                      "diagnosis_evaluation": deepcopy(session["diagnosis_evaluation"])})
        return self._public(session)

    def report(self, session_id: str) -> dict:
        """Reporte final de una consulta cerrada, armado solo con su caso y su propia sesión (HU-006)."""
        session = self.store.get(session_id)
        if session["phase"] != SessionPhase.FINALIZADA.value:
            raise SessionNotFinished(session_id)
        return self.evaluation_engine.report(session, self.store.events(session_id))

    def owner_of(self, session_id: str) -> str | None:
        return self.store.get(session_id).get("owner_id")

    def final_submission(self, session_id: str) -> dict:
        """El historial usa la entrega cerrada original, también al reintentar /finish."""
        session = self.store.get(session_id)
        if session["phase"] != SessionPhase.FINALIZADA.value:
            raise SessionNotFinished(session_id)
        return {"diagnosis": session.get("student_diagnosis") or "",
                "hypotheses": deepcopy(session.get("student_hypotheses") or [])}

    def access_of(self, session_id: str) -> tuple[str | None, str | None]:
        """Dueño registrado y hash de la credencial de invitado, para autorizar cada operación."""
        state = self.store.get(session_id)
        return state.get("owner_id"), state.get("access_token_hash")

    def attach_attempt(self, session_id: str, attempt_id: str) -> None:
        """Recuerda el intento guardado del alumno para no guardarlo dos veces."""
        session = self.store.get(session_id)
        session["attempt_id"] = attempt_id
        self.store.save(session)

    def events(self, session_id: str) -> list[dict]:
        return self.store.events(session_id)

    def _ensure_clinical_state(self, session: dict) -> None:
        if "avatar_state" in session and "requested_evidence_ids" in session:
            return
        case = self.repository.get_conversation_case(session["case_id"])
        if "avatar_state" not in session:
            session["avatar_state"] = self.state_machine.initial_avatar_state(case)
        if "requested_evidence_ids" not in session:
            initial_evidence = set(self.disclosure_policy.initial_evidence_ids(case))
            session["requested_evidence_ids"] = [
                evidence_id
                for evidence_id in session["revealed_evidence_ids"]
                if evidence_id not in initial_evidence
            ]

    @staticmethod
    def _public(state: dict) -> dict:
        keys = {
            "session_id", "case_id", "phase", "active_agent", "revealed_evidence_ids",
            "started_at", "updated_at", "finished_at",
        }
        public = {key: state[key] for key in keys}
        for key in ("avatar_state", "evaluation", "attempt_id"):
            if key in state:
                public[key] = state[key]
        if state["phase"] == SessionPhase.FINALIZADA.value and state.get("diagnosis_evaluation"):
            public["diagnosis_evaluation"] = deepcopy(state["diagnosis_evaluation"])
        return public
