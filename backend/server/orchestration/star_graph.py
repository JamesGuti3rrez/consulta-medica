from __future__ import annotations

from typing import Any

from server.domain import AgentReply, AgentRole, Intent, SessionPhase, TurnGraphState
from server.orchestration.graph_compat import END, START, StateGraph
from server.engine.disclosure.synthetic_scope import outside_clinical_scope, OUT_OF_SCOPE_REPLY, rapport_reply


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
        patient_completion=None,
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
        self.patient_completion = patient_completion
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
        if outside_clinical_scope(state["student_message"]):
            return {
                "active_agent": AgentRole.PACIENTE.value, "route_intent": Intent.ASK_PATIENT.value,
                "route_reason": "pregunta fuera del caso clínico", "route_confidence": 1.0,
                "phase": state.get("phase", SessionPhase.PRESENTACION.value), "scope_rejected": True,
            }
        decision = self.router.route(state["student_message"])
        phase = SessionPhase(state.get("phase", SessionPhase.PRESENTACION.value))
        next_phase = self.state_machine.advance(phase, decision.intent)
        return {
            "active_agent": decision.target.value,
            "route_intent": decision.intent.value,
            "route_reason": decision.reason,
            "route_confidence": decision.confidence,
            "phase": next_phase.value,
            "scope_rejected": False,
        }

    def _agent_node(self, role: AgentRole):
        def node(state: TurnGraphState) -> dict[str, Any]:
            if state.get("scope_rejected"):
                return {
                    "response_text": OUT_OF_SCOPE_REPLY, "doctor_question": None,
                    "provider": "reglas", "model": "reglas", "input_tokens": 0, "output_tokens": 0,
                    "retrieved_evidence_ids": [], "synthetic_generated_ids": [], "synthetic_reused_ids": [],
                    "data_source": "fuera_de_alcance", "blocked": True, "block_reason": "fuera_de_alcance",
                }
            case = self.repository.get_conversation_case(state["case_id"])
            intent = Intent(state["route_intent"])
            # Al paciente le habla el médico tratante: reformula lo que pidió el estudiante. La
            # autorización usa la frase original, así la reformulación no puede revelar datos.
            reformulation = None
            message_for_agent = state["student_message"]
            social = rapport_reply(state["student_message"]) if role == AgentRole.PACIENTE else None
            if role == AgentRole.PACIENTE and self.reformulator is not None and not social:
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
            if (role == AgentRole.MEDICO_ASISTENTE and intent == Intent.ASK_ASSISTANT
                    and self.router.generic_exam_request(state["student_message"])):
                context["pedido_generico"] = True
            forbidden_terms = self.protected_lexicon.for_case(state["case_id"])
            completion = None
            if role == AgentRole.PACIENTE and self.patient_completion is not None:
                completion = self.patient_completion.complete(
                    question=state["student_message"], case=case, context=context,
                    forbidden_terms=forbidden_terms, session_id=state.get("session_id"),
                )
            reply = completion.reply if completion is not None else None
            if reply is None and social:
                reply = AgentReply(role=role, text=social, provider="reglas", model="reglas")
            if reply is None:
                reply = self.agents[role].respond(
                    student_message=message_for_agent, context=context, temperature=self.temperature,
                )
                if completion is not None:
                    reply.input_tokens += completion.selector_usage[0]
                    reply.output_tokens += completion.selector_usage[1]
            ok, reason = self.output_guard.validate(reply.text, forbidden_terms)
            scope_rejected = bool(completion and completion.scope_rejected)
            validation_rejected = bool(completion and completion.validation_rejected)
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
                "synthetic_generated_ids": completion.generated_ids if completion else [],
                "synthetic_reused_ids": completion.reused_ids if completion else [],
                "data_source": completion.source if completion else "conversacional" if social else "curado",
                "synthetic_rejection_reason": completion.rejection_reason if completion else None,
                "blocked": not ok or scope_rejected or validation_rejected,
                "block_reason": ("fuera_de_alcance" if scope_rejected else
                                 "validacion_sintetica" if validation_rejected else reason),
            }

        return node

    @staticmethod
    def _central_finalize(state: TurnGraphState) -> dict[str, Any]:
        return {"active_agent": state["active_agent"]}

    def invoke(self, state: TurnGraphState) -> TurnGraphState:
        return self.graph.invoke(state)
