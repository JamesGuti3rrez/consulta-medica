from server.ai.agents.especialista import EspecialistaAgent
from server.ai.agents.laboratorio import LaboratorioAgent
from server.ai.agents.medico_asistente import MedicoAsistenteAgent
from server.ai.agents.paciente import PacienteAgent
from server.ai.agents.radiologia import RadiologiaAgent
from server.ai.llm.gateway import LLMGateway
from server.domain import AgentRole


def build_agents(gateway: LLMGateway):
    return {
        AgentRole.MEDICO_ASISTENTE: MedicoAsistenteAgent(gateway),
        AgentRole.PACIENTE: PacienteAgent(gateway),
        AgentRole.LABORATORIO: LaboratorioAgent(gateway),
        AgentRole.RADIOLOGIA: RadiologiaAgent(gateway),
        AgentRole.ESPECIALISTA: EspecialistaAgent(gateway),
    }
