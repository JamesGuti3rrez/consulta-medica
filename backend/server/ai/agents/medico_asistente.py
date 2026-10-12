from server.ai.agents.base import BaseAgent
from server.domain import AgentRole


class MedicoAsistenteAgent(BaseAgent):
    role = AgentRole.MEDICO_ASISTENTE
    prompt_filename = "medico_asistente.md"
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
