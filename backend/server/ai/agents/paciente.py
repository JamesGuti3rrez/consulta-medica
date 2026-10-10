from server.ai.agents.base import BaseAgent
from server.domain import AgentRole


class PacienteAgent(BaseAgent):
    role = AgentRole.PACIENTE
    prompt_filename = "paciente.md"
    # El caso solo trae lo que la fuente describe: lo que no aparece se toma como ausente.
    missing_data_rule = (
        "Si te preguntan por algo que no aparece en el contexto (un síntoma, una alergia, un antecedente, un "
        "hábito), respóndelo con naturalidad y en negativo, por ejemplo «No» o «No, nada de eso», como lo diría "
        "el paciente. No digas que no lo sabes y no añadas síntomas, enfermedades ni datos nuevos."
    )
