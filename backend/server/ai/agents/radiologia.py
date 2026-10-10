from server.ai.agents.base import BaseAgent
from server.domain import AgentRole


class RadiologiaAgent(BaseAgent):
    role = AgentRole.RADIOLOGIA
    prompt_filename = "radiologia.md"
