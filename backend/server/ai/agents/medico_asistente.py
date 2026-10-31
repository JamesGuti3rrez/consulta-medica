from server.ai.agents.base import BaseAgent
from server.domain import AgentReply, AgentRole


class MedicoAsistenteAgent(BaseAgent):
    role = AgentRole.MEDICO_ASISTENTE
    prompt_filename = "medico_asistente.md"
    generic_request_reply = (
        "¿Desea realizar la exploración física o solicitar un examen de laboratorio o de imagen? Indique cuál."
    )
    # Hipótesis, diagnósticos y tratamientos del estudiante: se registran sin confirmarlos ni corregirlos
    # (la evaluación es del motor de evaluación, no del agente), y sin pistas que adelanten datos.
    missing_data_rule = (
        "Si el estudiante propone una hipótesis, un diagnóstico o un tratamiento, no lo confirmes, no lo "
        "corrijas y no digas cuál es el correcto: responde en una o dos frases que lo anotas y que se revisará "
        "al cerrar la consulta, y anímalo a seguir reuniendo datos con preguntas, exploración o exámenes, sin "
        "sugerir exámenes ni hallazgos concretos. Si te pide el diagnóstico, dile con amabilidad que debe "
        "llegar a él con los datos de la consulta. Si pide un dato que no está en el contexto, di con "
        "naturalidad que no está disponible. No uses palabras como evidencia, autorizado o recuperado."
    )
    missing_data_reply = "Ese dato no está disponible en la ficha de este paciente."
    no_exam_findings_reply = "No hay hallazgos de exploración física registrados para este paciente."

    def respond(self, *, student_message, context, temperature=0.0):
        # Sin hallazgos registrados no se llama al modelo: no puede pedir al estudiante que los describa.
        if context.get("exploracion_sin_hallazgos"):
            return AgentReply(role=self.role, text=self.no_exam_findings_reply, provider="reglas", model="reglas",
                              evidence_ids=[], input_tokens=0, output_tokens=0)
        return super().respond(student_message=student_message, context=context, temperature=temperature)
