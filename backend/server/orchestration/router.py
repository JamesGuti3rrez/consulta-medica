from __future__ import annotations

import re
import unicodedata

from server.domain import AgentRole, Intent, RouteDecision


def _normalize(text: str) -> str:
    raw = unicodedata.normalize("NFD", str(text or "").casefold())
    raw = "".join(ch for ch in raw if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", raw)


class DecisionRouter:
    """Router determinístico del nodo central de la topología estrella."""

    LAB = {
        "laboratorio", "analisis", "hemograma", "troponina", "glucosa", "sangre", "orina",
        "coagulacion", "coagulograma", "ttpa", "tiempo de protrombina", "ph vaginal", "tiroides", "tiroidea", "tsh",
        "electrocardiograma", "ecg", "electro", "dimero", "enzimas cardiacas",
        # Exámenes que agregó el equipo para decidir entre diagnósticos parecidos (decisión 0002).
        "factor viii", "factor ix", "factores de coagulacion", "prolactina", "eeg", "electroencefalograma",
        # Estudios de la ampliación de casos sintéticos (octubre de 2026).
        "flujo espiratorio", "flujometria", "peak flow", "gasometria", "liquido cefalorraquideo", "lcr",
        "funcion renal", "creatinina", "uroanalisis", "electrolitos", "ionograma", "ferritina",
        "hemoglobina glicosilada", "hemoglobina glucosilada", "hemoglobina glicada", "hba1c",
        "beta hcg", "bhcg", "microscopia vaginal", "exudado vaginal", "secrecion vaginal",
        "prueba molecular vaginal", "prueba molecular de esputo", "baciloscopia",
    }
    RADIOLOGY = {"radiografia", "ecografia", "tomografia", "resonancia", "imagen", "rayos x", "tac", "edad osea",
                 "ecocardiografia", "ecocardiograma", "angiografia cerebral", "angiotomografia", "angiotac"}
    SPECIALIST = {"especialista", "interconsulta", "neurologia", "cardiologia", "cirugia", "ginecologia"}
    ASSISTANT = {"resumen", "que sabemos", "presentacion", "historia clinica", "estado del caso",
                 "el diagnostico", "que tiene el paciente", "cual es la enfermedad"}
    EXAMINE = {"examen fisico", "examinar", "examino", "exploracion", "exploro", "explorar", "neurologico",
               "ausculto", "auscultar", "palpo", "palpar", "examen ginecologico",
               "signos vitales", "tomo la presion", "tomar la presion", "mido la presion",
               "examenes fisicos", "examenes fisico", "examen fisicos", "evaluacion fisica",
               "revision fisica", "revisar al paciente"}
    HYPOTHESIS = {"mi hipotesis", "hipotesis es", "considero que", "sospecho"}
    DIAGNOSIS = {"mi diagnostico", "diagnostico final", "diagnostico es"}
    # Propuestas del estudiante en primera persona. No basta «tratamiento» o «receta»: «¿Está en
    # tratamiento?» o «¿Qué le recetaron?» son preguntas al paciente.
    TREATMENT = {"mi tratamiento", "el tratamiento es", "el tratamiento seria", "el tratamiento que", "como tratamiento",
                 "prescribo", "indicaria", "le indico", "administro", "le administro", "le doy", "le daria",
                 "le pongo", "inicio tratamiento", "iniciaria"}
    FINISH = {"finalizar consulta", "terminar consulta", "cerrar consulta", "finalizar sesion"}

    @staticmethod
    def generic_exam_request(message: str) -> bool:
        """Un pedido de pruebas sin tipo se aclara con el médico, no con el paciente."""
        return bool(re.search(r"\b(?:examen(?:es)?|pruebas|estudios medicos)\b", _normalize(message)))

    @classmethod
    def requested_specific_agents(cls, message: str) -> set[AgentRole]:
        text = f" {_normalize(message).strip()} "

        def mentions(terms):
            return any(f" {term} " in text for term in terms)

        requested = set()
        if mentions(cls.LAB):
            requested.add(AgentRole.LABORATORIO)
        if mentions(cls.RADIOLOGY):
            requested.add(AgentRole.RADIOLOGIA)
        if mentions(cls.SPECIALIST):
            requested.add(AgentRole.ESPECIALISTA)
        return requested

    @classmethod
    def requests_multiple_specific_agents(cls, message: str) -> bool:
        return len(cls.requested_specific_agents(message)) > 1

    def route(self, message: str) -> RouteDecision:
        text = _normalize(message)
        def mentions(terms):
            return any(f" {term} " in f" {text.strip()} " for term in terms)
        if mentions(self.FINISH):
            return RouteDecision(Intent.FINISH, AgentRole.MEDICO_ASISTENTE, 1.0, "solicitud explícita de cierre")
        if mentions(self.DIAGNOSIS):
            return RouteDecision(Intent.PROPOSE_DIAGNOSIS, AgentRole.MEDICO_ASISTENTE, 0.98, "propuesta de diagnóstico")
        # Una pregunta («¿Qué le indicó su médico?») no es una propuesta de tratamiento.
        if "?" not in message and mentions(self.TREATMENT):
            return RouteDecision(Intent.PROPOSE_TREATMENT, AgentRole.MEDICO_ASISTENTE, 0.98, "propuesta de tratamiento")
        if mentions(self.HYPOTHESIS):
            return RouteDecision(Intent.PROPOSE_HYPOTHESIS, AgentRole.MEDICO_ASISTENTE, 0.95, "registro de hipótesis")
        requested_agents = self.requested_specific_agents(message)
        if len(requested_agents) > 1:
            return RouteDecision(Intent.ASK_ASSISTANT, AgentRole.MEDICO_ASISTENTE, 0.9,
                                 "solicitud simultánea para varios agentes; se requiere aclaración")
        if requested_agents:
            target = next(iter(requested_agents))
            if target == AgentRole.LABORATORIO:
                return RouteDecision(Intent.REQUEST_LAB, target, 0.95, "términos de laboratorio")
            if target == AgentRole.RADIOLOGIA:
                return RouteDecision(Intent.REQUEST_RADIOLOGY, target, 0.95, "términos de imagen")
            return RouteDecision(Intent.REQUEST_SPECIALIST, target, 0.92, "solicitud de especialista")
        if mentions(self.EXAMINE):
            return RouteDecision(Intent.EXAMINE, AgentRole.MEDICO_ASISTENTE, 0.9, "solicitud de examen físico")
        if self.generic_exam_request(message):
            return RouteDecision(Intent.ASK_ASSISTANT, AgentRole.MEDICO_ASISTENTE, 0.9,
                                 "solicitud de exámenes sin especificar el tipo")
        if mentions(self.ASSISTANT):
            return RouteDecision(Intent.ASK_ASSISTANT, AgentRole.MEDICO_ASISTENTE, 0.9, "consulta al asistente")
        return RouteDecision(Intent.ASK_PATIENT, AgentRole.PACIENTE, 0.75, "pregunta clínica dirigida al paciente por defecto")
