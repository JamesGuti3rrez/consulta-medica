from server.ai.agents.base import BaseAgent
from server.domain import AgentRole


class PacienteAgent(BaseAgent):
    role = AgentRole.PACIENTE
    prompt_filename = "paciente.md"
    # El caso solo trae lo que la fuente describe: lo que no aparece se toma como ausente.
    missing_data_rule = (
        "Si te preguntan algo abierto (cómo se siente, qué le pasa, por qué viene), cuenta con tus palabras tu "
        "motivo de consulta y lo que ya está en public_evidence. Si te preguntan por algo concreto que no aparece "
        "en el contexto (un síntoma, una alergia, un antecedente, un hábito), respóndelo con naturalidad y en "
        "negativo, por ejemplo «No» o «No, nada de eso». No digas que no lo sabes y no añadas síntomas, "
        "enfermedades ni datos nuevos."
    )
