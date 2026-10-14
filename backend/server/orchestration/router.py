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
        "factor viii", "factor ix", "factores de coagulacion", "prolactina", "eeg",
    }
    RADIOLOGY = {"radiografia", "ecografia", "tomografia", "resonancia", "imagen", "rayos x", "tac", "edad osea"}
    SPECIALIST = {"especialista", "interconsulta", "neurologia", "cardiologia", "cirugia", "ginecologia"}
    ASSISTANT = {"resumen", "que sabemos", "presentacion", "historia clinica", "estado del caso",
                 "el diagnostico", "que tiene el paciente", "cual es la enfermedad"}
    EXAMINE = {"examen fisico", "examinar", "examino", "exploracion", "exploro", "explorar", "neurologico",
               "ausculto", "auscultar", "palpo", "palpar", "examen ginecologico",
               "signos vitales", "tomo la presion", "tomar la presion", "mido la presion"}
    HYPOTHESIS = {"mi hipotesis", "hipotesis es", "considero que", "sospecho"}
    DIAGNOSIS = {"mi diagnostico", "diagnostico final", "diagnostico es"}
    # Propuestas del estudiante en primera persona. No basta «tratamiento» o «receta»: «¿Está en
    # tratamiento?» o «¿Qué le recetaron?» son preguntas al paciente.
    TREATMENT = {"mi tratamiento", "el tratamiento es", "el tratamiento seria", "el tratamiento que", "como tratamiento",
                 "prescribo", "indicaria", "le indico", "administro", "le administro", "le doy", "le daria",
                 "le pongo", "inicio tratamiento", "iniciaria"}
    FINISH = {"finalizar consulta", "terminar consulta", "cerrar consulta", "finalizar sesion"}

    def route(self, message: str) -> RouteDecision:
        text = _normalize(message)
        if any(term in text for term in self.FINISH):
            return RouteDecision(Intent.FINISH, AgentRole.MEDICO_ASISTENTE, 1.0, "solicitud explícita de cierre")
        if any(term in text for term in self.DIAGNOSIS):
            return RouteDecision(Intent.PROPOSE_DIAGNOSIS, AgentRole.MEDICO_ASISTENTE, 0.98, "propuesta de diagnóstico")
        # Una pregunta («¿Qué le indicó su médico?») no es una propuesta de tratamiento.
        if "?" not in message and any(term in text for term in self.TREATMENT):
            return RouteDecision(Intent.PROPOSE_TREATMENT, AgentRole.MEDICO_ASISTENTE, 0.98, "propuesta de tratamiento")
        if any(term in text for term in self.HYPOTHESIS):
            return RouteDecision(Intent.PROPOSE_HYPOTHESIS, AgentRole.MEDICO_ASISTENTE, 0.95, "registro de hipótesis")
        if any(term in text for term in self.LAB):
            return RouteDecision(Intent.REQUEST_LAB, AgentRole.LABORATORIO, 0.95, "términos de laboratorio")
        if any(term in text for term in self.RADIOLOGY):
            return RouteDecision(Intent.REQUEST_RADIOLOGY, AgentRole.RADIOLOGIA, 0.95, "términos de imagen")
        if any(term in text for term in self.SPECIALIST):
            return RouteDecision(Intent.REQUEST_SPECIALIST, AgentRole.ESPECIALISTA, 0.92, "solicitud de especialista")
        if any(term in text for term in self.EXAMINE):
            return RouteDecision(Intent.EXAMINE, AgentRole.MEDICO_ASISTENTE, 0.9, "solicitud de examen físico")
        if any(term in text for term in self.ASSISTANT):
            return RouteDecision(Intent.ASK_ASSISTANT, AgentRole.MEDICO_ASISTENTE, 0.9, "consulta al asistente")
        return RouteDecision(Intent.ASK_PATIENT, AgentRole.PACIENTE, 0.75, "pregunta clínica dirigida al paciente por defecto")
