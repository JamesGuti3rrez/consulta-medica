from server.ai.agents.base import BaseAgent, _normalize
from server.domain import AgentRole


class PacienteAgent(BaseAgent):
    role = AgentRole.PACIENTE
    prompt_filename = "paciente.md"
    missing_data_reply = "No recuerdo con precisión ese dato."
    # Un dato no registrado es desconocido, no un antecedente o síntoma negado.
    missing_data_rule = (
        "Si te preguntan algo abierto (cómo se siente, qué le pasa, por qué viene), cuenta con tus palabras tu "
        "motivo de consulta y lo que ya está en public_evidence. Si falta un dato concreto, di con naturalidad "
        "que no lo recuerdas con precisión. La ausencia de un dato no significa que el paciente lo niegue. "
        "No respondas «No» ni «No tomo nada» por el solo hecho de que no se registró un medicamento. "
        "Conserva los antecedentes conocidos: si consta hipertensión controlada pero no el fármaco o el año "
        "del diagnóstico, puedes reconocer la hipertensión y aclarar que no recuerdas esos detalles. "
        "En preguntas con varias partes, responde lo conocido y aclara qué parte no recuerdas. "
        "No inventes nombres, dosis, fechas ni otros datos."
    )

    def respond(self, *, student_message, context, temperature=0.0):
        reply = super().respond(student_message=student_message, context=context, temperature=temperature)
        # Una negación aislada no contesta una pregunta abierta de detalle. Se aplica
        # después de la limpieza y conserva los tokens/proveedor para las trazas.
        question = _normalize(student_message)
        asks_details = any(term in f" {question} " for term in (
            " que ", " cual ", " cuales ", " cuando ", " cuanto ", " cuanta ",
            " cuantos ", " cuantas ", " como ", " donde ",
        ))
        if (not context.get("retrieved_evidence") and asks_details
                and _normalize(reply.text) in {"no", "no nada de eso", "nada", "ninguno", "ninguna"}):
            reply.text = self.missing_data_reply
            reply.grounding_fallback_used = True
        return reply
