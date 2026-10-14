from server.ai.agents.base import BaseAgent
from server.domain import AgentRole


class RadiologiaAgent(BaseAgent):
    role = AgentRole.RADIOLOGIA
    prompt_filename = "radiologia.md"
    # Pedido genérico (sin nombrar examen): se pregunta cuál, sin afirmar que no existe.
    generic_request_reply = "¿Qué estudio de imagen desea solicitar? Indíqueme cuál, por ejemplo una radiografía o una tomografía y de qué zona."
    # Sin estudio para lo pedido: una frase natural, sin términos internos ni hallazgos inventados.
    missing_data_rule = (
        "Se pidió un estudio de imagen concreto que no tiene informe en este caso. Responde con una frase breve y natural, por "
        "ejemplo «Ese estudio no se realizó en este paciente». No inventes hallazgos, no sugieras otros "
        "estudios y no uses palabras como evidencia, autorizado o recuperado."
    )
