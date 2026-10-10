from server.ai.agents.base import BaseAgent
from server.domain import AgentRole


class PacienteAgent(BaseAgent):
    role = AgentRole.PACIENTE
    prompt_filename = "paciente.md"
