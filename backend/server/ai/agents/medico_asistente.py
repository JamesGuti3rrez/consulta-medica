from server.ai.agents.base import BaseAgent
from server.domain import AgentRole


class MedicoAsistenteAgent(BaseAgent):
    role = AgentRole.MEDICO_ASISTENTE
    prompt_filename = "medico_asistente.md"
