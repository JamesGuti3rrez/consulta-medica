from __future__ import annotations

from typing import Any
from contextlib import nullcontext

from server.domain import AgentReply, AgentRole, Intent, SessionPhase, TurnGraphState
from server.orchestration.graph_compat import END, START, StateGraph
from server.engine.disclosure.synthetic_scope import outside_clinical_scope, OUT_OF_SCOPE_REPLY, rapport_reply
from server.cases.rules import evidence_text
from server.rag.port import RetrievedEvidence
from server.ai.agents.invencion import invented_figures

try:
    from langsmith import tracing_context
except ImportError:
    tracing_context = None


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
        temperature: float = 0.0,
        patient_completion=None,
        exam_completion=None,
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
        self.temperature = temperature
        self.patient_completion = patient_completion
        self.exam_completion = exam_completion
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
            forbidden_terms = self.protected_lexicon.for_case(state["case_id"])
            # El estudiante pregunta directamente al agente. No se crea un turno intermedio del doctor.
            social = rapport_reply(state["student_message"]) if role == AgentRole.PACIENTE else None
            disclosure = self.disclosure_policy.authorize(
                case=case,
                role=role,
                intent=intent,
                student_message=state["student_message"],
            )
            retrieved = self.retriever.retrieve(
                query=state["student_message"],
                case_id=state["case_id"],
                agent_role=role,
                allowed_evidence_ids=disclosure.allowed_evidence_ids,
                session_id=state.get("session_id"),
            )
            # La autorización sigue siendo local aunque un adaptador devuelva un ID ajeno o texto alterado.
            allowed = set(disclosure.allowed_evidence_ids)
            canonical = {item["evidence_id"]: item for item in case.get("on_request", [])}
            retrieved = [RetrievedEvidence(item.evidence_id, evidence_text(canonical[item.evidence_id]), item.score)
                         for item in retrieved if item.evidence_id in allowed and item.evidence_id in canonical
                         and item.evidence_id.startswith(case["case_id"] + ".")]
            # Un fallo de ranking/índice no convierte un resultado canónico existente en uno ausente.
            if allowed and not retrieved:
                retrieved = [RetrievedEvidence(eid, evidence_text(canonical[eid]))
                             for eid in disclosure.allowed_evidence_ids if eid in canonical]
            retrieved = list({item.evidence_id: item for item in retrieved}.values())
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
            # Exploración física sin hallazgos registrados: el doctor lo dice, sin pedir al estudiante que los describa.
            if role == AgentRole.MEDICO_ASISTENTE and intent == Intent.EXAMINE and not retrieved:
                context["exploracion_sin_hallazgos"] = True
            completion = None
            exam_result = None
            if role == AgentRole.LABORATORIO and not disclosure.allowed_evidence_ids and self.exam_completion is not None:
                exam_result = self.exam_completion.complete(
                    case=case, role=role, intent=intent, message=state["student_message"], context=context,
                    previous=state.get("synthetic_exam_results", {}), forbidden_terms=forbidden_terms,
                    guard=self.output_guard,
                )
                if exam_result:
                    context["retrieved_evidence"] = [{"evidence_id": i["evidence_id"], "text": i["text"], "score": 1.0}
                                                     for i in exam_result["evidence"]]
            if role == AgentRole.PACIENTE and self.patient_completion is not None:
                completion = self.patient_completion.complete(
                    question=state["student_message"], case=case, context=context,
                    forbidden_terms=forbidden_terms, session_id=state.get("session_id"),
                )
            reply = exam_result["reply"] if exam_result else completion.reply if completion is not None else None
            if reply is None and social:
                reply = AgentReply(role=role, text=social, provider="reglas", model="reglas")
            if reply is None:
                reply = self.agents[role].respond(
                    student_message=state["student_message"], context=context, temperature=self.temperature,
                )
                if completion is not None:
                    reply.input_tokens += completion.selector_usage[0]
                    reply.output_tokens += completion.selector_usage[1]
            # Los controles del agente se aplican si respondió el agente, también tras un rechazo del generador.
            from_generator = completion is not None and completion.reply is not None
            ok, reason = self.output_guard.validate(reply.text, forbidden_terms)
            if not from_generator and invented_figures(reply.text, context):
                ok, reason = False, "cifras_sin_respaldo"
            # Un agente tampoco puede adjuntar referencias fuera del conjunto que realmente recibió.
            visible_ids = {item["evidence_id"] for key in ("retrieved_evidence", "revealed_evidence")
                           for item in context.get(key, [])}
            if any(eid not in visible_ids for eid in reply.evidence_ids) and not from_generator:
                ok, reason = False, "evidencia_no_autorizada"
            scope_rejected = bool(completion and completion.scope_rejected)
            # Un rechazo del generador ya no bloquea: respondió el agente; el motivo queda en la auditoría.
            validation_rejected = bool(from_generator and completion.validation_rejected)
            return {
                "response_text": reply.text if ok else "Eso no lo puedo responder. Sigamos con la consulta.",
                "doctor_question": None,  # Compatibilidad del contrato; ya no hay preguntas intermediadas.
                "provider": reply.provider,
                "model": reply.model,
                "input_tokens": reply.input_tokens,
                "output_tokens": reply.output_tokens,
                "fallback_used": reply.fallback_used,
                "grounding_retry_used": reply.grounding_retry_used,
                "grounding_fallback_used": reply.grounding_fallback_used,
                "retrieved_evidence_ids": reply.evidence_ids if ok else [],
                "synthetic_generated_ids": ([i["evidence_id"] for i in exam_result["evidence"]] if not exam_result["reused"] else [])
                                           if exam_result else completion.generated_ids if completion else [],
                "synthetic_reused_ids": ([i["evidence_id"] for i in exam_result["evidence"]] if exam_result["reused"] else [])
                                        if exam_result else completion.reused_ids if completion else [],
                "synthetic_exam_results": {**state.get("synthetic_exam_results", {}),
                                           **(exam_result["snapshot"] if exam_result and ok else {})},
                "exam_evidence": exam_result["evidence"] if exam_result and ok else [],
                "exam_validation": exam_result["validation"] if exam_result else None,
                "data_source": ("sintetico_examen" if exam_result["evidence"] else "examen_no_validado") if exam_result
                               else completion.source if completion else "conversacional" if social else "curado",
                "synthetic_rejection_reason": completion.rejection_reason if completion else None,
                "blocked": not ok or scope_rejected or validation_rejected or reply.blocked,
                "block_reason": ("fuera_de_alcance" if scope_rejected else
                                 "validacion_sintetica" if validation_rejected else reason or
                                 ("examen_no_validado" if reply.blocked else None)),
            }

        return node

    @staticmethod
    def _central_finalize(state: TurnGraphState) -> dict[str, Any]:
        return {"active_agent": state["active_agent"]}

    def invoke(self, state: TurnGraphState) -> TurnGraphState:
        # LangGraph hereda variables globales de LangSmith. Nunca enviar su estado clínico completo:
        # la única auditoría externa permitida es la proyección saneada del servicio.
        with tracing_context(enabled=False) if tracing_context else nullcontext():
            return self.graph.invoke(state)
