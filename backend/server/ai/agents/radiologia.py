from server.ai.agents.base import BaseAgent
from server.domain import AgentRole


class RadiologiaAgent(BaseAgent):
    role = AgentRole.RADIOLOGIA
    prompt_filename = "radiologia.md"
    # Sin estudio para lo pedido: una frase natural, sin términos internos ni hallazgos inventados.
    missing_data_rule = (
        "El estudio de imagen pedido no tiene informe en este caso. Responde con una frase breve y natural, por "
        "ejemplo «Ese estudio no se realizó en este paciente». No inventes hallazgos, no sugieras otros "
        "estudios y no uses palabras como evidencia, autorizado o recuperado."
    )
