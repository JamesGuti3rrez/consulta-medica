from server.ai.agents.base import BaseAgent
from server.domain import AgentRole


class EspecialistaAgent(BaseAgent):
    role = AgentRole.ESPECIALISTA
    prompt_filename = "especialista.md"
