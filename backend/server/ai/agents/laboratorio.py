from server.ai.agents.base import BaseAgent
from server.domain import AgentRole


class LaboratorioAgent(BaseAgent):
    role = AgentRole.LABORATORIO
    prompt_filename = "laboratorio.md"
    # Pedido genérico (sin nombrar examen): se pregunta cuál, sin afirmar que no existe.
    generic_request_reply = "¿Qué examen en concreto desea solicitar? Indíqueme su nombre, por ejemplo hemograma o pruebas de coagulación."
    # Sin resultado para lo pedido: una frase natural, sin términos internos ni resultados inventados.
    missing_data_rule = (
        "Se pidió un examen concreto que no tiene resultado en este caso. Responde con una frase breve y natural, por ejemplo "
        "«Ese examen no se realizó en este paciente» o «No tenemos ese resultado». No inventes valores, no "
        "sugieras otros exámenes y no uses palabras como evidencia, autorizado o recuperado."
    )
