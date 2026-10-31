from server.ai.agents.base import BaseAgent
from server.domain import AgentRole


class EspecialistaAgent(BaseAgent):
    missing_data_reply = "No hay una interconsulta disponible en este caso. Puede continuar con la historia, la exploración y los exámenes disponibles."
    role = AgentRole.ESPECIALISTA
    prompt_filename = "especialista.md"
    # Ningún caso trae datos de interconsulta: se responde con naturalidad, sin términos internos.
    missing_data_rule = (
        "En este caso no hay una interconsulta disponible. Dilo con una frase breve y natural y anima al "
        "estudiante a seguir con la anamnesis, la exploración y los exámenes. No des opiniones clínicas y no "
        "uses palabras como evidencia, autorizado o recuperado."
    )
