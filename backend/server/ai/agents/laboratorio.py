from server.ai.agents.base import BaseAgent
from server.domain import AgentRole


class LaboratorioAgent(BaseAgent):
    role = AgentRole.LABORATORIO
    prompt_filename = "laboratorio.md"
