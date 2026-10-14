from __future__ import annotations

from typing import Any

from server.domain import AgentRole, Intent, SessionPhase, TurnGraphState
from server.orchestration.graph_compat import END, START, StateGraph


class StarGraphOrchestrator:
    """Topología estrella: un nodo central decide, un agente hoja responde y el control vuelve al centro."""

    def __init__(
        self,
        *,
        router,
        agents,
        repository,
        retriever,
        disclosure_policy,
        context_assembler,
        state_machine,
        output_guard,
        protected_lexicon,
        reformulator=None,
        temperature: float = 0.0,
    ):
        self.router = router
        self.agents = agents
        self.repository = repository
        self.retriever = retriever
        self.disclosure_policy = disclosure_policy
        self.context_assembler = context_assembler
        self.state_machine = state_machine
        self.output_guard = output_guard
        self.protected_lexicon = protected_lexicon
        self.reformulator = reformulator
        self.temperature = temperature
        self.graph = self._build()

    def _build(self):
        builder = StateGraph(TurnGraphState)
        builder.add_node("orchestrator", self._orchestrator_node)
        for role in self.agents:
            builder.add_node(role.value, self._agent_node(role))
        builder.add_node("central_finalize", self._central_finalize)
        builder.add_edge(START, "orchestrator")
        builder.add_conditional_edges(
            "orchestrator",
            lambda state: state["active_agent"],
            {role.value: role.value for role in self.agents},
        )
        for role in self.agents:
            builder.add_edge(role.value, "central_finalize")
        builder.add_edge("central_finalize", END)
        return builder.compile()

    def _orchestrator_node(self, state: TurnGraphState) -> dict[str, Any]:
        decision = self.router.route(state["student_message"])
        phase = SessionPhase(state.get("phase", SessionPhase.PRESENTACION.value))
        next_phase = self.state_machine.advance(phase, decision.intent)
        return {
            "active_agent": decision.target.value,
            "route_intent": decision.intent.value,
            "route_reason": decision.reason,
            "route_confidence": decision.confidence,
            "phase": next_phase.value,
        }

    def _agent_node(self, role: AgentRole):
        def node(state: TurnGraphState) -> dict[str, Any]:
            case = self.repository.get_conversation_case(state["case_id"])
            intent = Intent(state["route_intent"])
            # Al paciente le habla el médico tratante: reformula lo que pidió el estudiante. La
            # autorización usa la frase original, así la reformulación no puede revelar datos.
            reformulation = None
            message_for_agent = state["student_message"]
            if role == AgentRole.PACIENTE and self.reformulator is not None:
                reformulation = self.reformulator.reformulate(state["student_message"], temperature=self.temperature)
                message_for_agent = reformulation.text
            disclosure = self.disclosure_policy.authorize(
                case=case,
                role=role,
                intent=intent,
                student_message=state["student_message"],
            )
            retrieved = self.retriever.retrieve(
                query=message_for_agent,
                case_id=state["case_id"],
                agent_role=role,
                allowed_evidence_ids=disclosure.allowed_evidence_ids,
                session_id=state.get("session_id"),
            )
            context = self.context_assembler.build(
                case=case,
                role=role,
                revealed_evidence_ids=state.get("revealed_evidence_ids", []),
                retrieved=retrieved,
                conversation_tail=state.get("conversation_tail", []),
            )
            # Laboratorio y radiología sin resultado: si el estudiante no nombró ningún examen, se le pregunta
            # cuál quiere en vez de afirmar que no se hizo (podría existir con otro nombre).
            if (role in (AgentRole.LABORATORIO, AgentRole.RADIOLOGIA) and not retrieved
                    and not self.disclosure_policy.names_specific_exam(state["student_message"])):
                context["pedido_generico"] = True
            reply = self.agents[role].respond(
                student_message=message_for_agent,
                context=context,
                temperature=self.temperature,
            )
            forbidden_terms = self.protected_lexicon.for_case(state["case_id"])
            ok, reason = self.output_guard.validate(reply.text, forbidden_terms)
            return {
                "response_text": reply.text if ok else "Eso no lo puedo responder. Sigamos con la consulta.",
                "doctor_question": reformulation.text if reformulation else None,
                "provider": reply.provider,
                "model": reply.model,
                "input_tokens": reply.input_tokens + (reformulation.input_tokens if reformulation else 0),
                "output_tokens": reply.output_tokens + (reformulation.output_tokens if reformulation else 0),
                "fallback_used": reply.fallback_used,
                "grounding_retry_used": reply.grounding_retry_used,
                "grounding_fallback_used": reply.grounding_fallback_used,
                "retrieved_evidence_ids": reply.evidence_ids,
                "blocked": not ok,
                "block_reason": reason,
            }

        return node

    @staticmethod
    def _central_finalize(state: TurnGraphState) -> dict[str, Any]:
        return {"active_agent": state["active_agent"]}

    def invoke(self, state: TurnGraphState) -> TurnGraphState:
        return self.graph.invoke(state)
