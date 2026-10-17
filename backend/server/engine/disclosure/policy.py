from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from server.domain import AgentRole, Intent


def _normalize(text: str) -> str:
    raw = unicodedata.normalize("NFD", str(text or "").casefold())
    raw = "".join(ch for ch in raw if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", raw).strip()


ALIASES: dict[str, tuple[str, ...]] = {
    # Temas del contrato de indexado del RAG (regla R14): los que usan los casos curados.
    "inicio_y_evolucion": ("desde cuando", "cuando comenzo", "cuando empezo", "como empezo", "inicio", "evolucion",
                           "cuanto tiempo", "duracion", "hace cuanto"),
    "caracteristicas_sintoma": ("donde le duele", "donde duele", "como es el dolor", "describa", "describiria",
                                "localizacion", "que le duele"),
    "sintomas_asociados": ("otros sintomas", "algun otro sintoma", "algo mas", "nausea", "vomito", "luz",
                           "fiebre", "orinar", "relaciones sexuales", "debilidad", "rigidez", "desmayo",
                           "animo", "triste", "tristeza", "llanto"),
    "antecedentes_personales": ("antecedentes", "enfermedad", "problemas de salud",
                                "operacion", "cirugia previa", "desarrollo"),
    "antecedentes_familiares": ("familia", "familiar", "familiares", "padres", "madre", "padre", "hermanos"),
    "medicacion": ("medicacion", "medicamento", "medicamentos", "pastillas", "toma algo", "tomo algo", "tomado",
                   "paracetamol", "tratamiento", "recetaron", "receta",
                   "tratamiento habitual", "que toma", "que esta tomando", "que estas tomando"),
    "alergias": ("alergia", "alergias", "alergico", "alergica"),
    "habitos": ("habitos", "fuma", "tabaco", "alcohol", "drogas", "trabajo", "ocupacion", "viaje", "al sol", "protector solar",
                "parejas", "vida sexual", "preservativo", "bosque", "garrapata", "actividad", "compras"),
    "antecedentes_gineco_obstetricos": ("embarazo", "embarazos", "menstruacion", "regla", "parto", "anticonceptivo"),
    "signos_vitales": ("signos vitales", "presion", "pulso", "temperatura", "saturacion"),
    "exploracion_fisica": ("examen", "examino", "examinar", "exploracion", "exploro", "explorar", "ausculto",
                           "auscultar", "palpo", "palpar", "reviso al paciente", "evaluacion fisica",
                           "revision fisica", "revisar al paciente"),
    # Exámenes de los casos curados.
    "coagulacion": ("coagulacion", "coagulograma", "ttpa", "tiempo de protrombina", "tiempo de tromboplastina"),
    "ph_vaginal": ("ph vaginal", "ph de la vagina"),
    "funcion_tiroidea": ("funcion tiroidea", "tiroides", "tsh", "hormonas tiroideas"),
    "imagen_osea": ("imagen osea", "radiografia", "edad osea", "serie osea"),
    "radiografia": ("radiografia", "rayos x", "placa"),
    # Exámenes que agregó el equipo para decidir entre diagnósticos parecidos (decisión 0002).
    "factores_coagulacion": ("factor viii", "factor ix", "factores de coagulacion", "dosaje de factores"),
    "prolactina": ("prolactina", "hormonas hipofisarias"),
    "electroencefalograma": ("electroencefalograma", "eeg"),
    # Exámenes de la familia de casos sintéticos de dolor torácico (EME-101 a EME-103).
    "electrocardiograma": ("electrocardiograma", "ecg", "electro"),
    "troponina": ("troponina", "enzimas cardiacas", "marcadores cardiacos"),
    "dimero_d": ("dimero d", "dimero"),
    "radiografia_torax": ("radiografia", "rayos x", "placa de torax"),
    "angiotomografia_torax": ("angiotomografia", "angiotac", "tomografia"),
    # Estudios de las diez familias incorporadas en octubre de 2026.
    "flujo_espiratorio": ("flujo espiratorio", "flujometria", "peak flow"),
    "gasometria": ("gasometria arterial", "gases arteriales"),
    "ecocardiografia": ("ecocardiograma", "ecocardiografia"),
    "estudio_lcr": ("liquido cefalorraquideo", "lcr"),
    "angiografia_cerebral": ("angiotomografia cerebral", "angiografia cerebral", "angiotac cerebral"),
    "ecografia_abdominal": ("ecografia abdominal", "ecografia del abdomen"),
    "tomografia_abdominal": ("tomografia abdominal", "tac abdominal", "tomografia del abdomen"),
    "uroanalisis": ("analisis de orina", "examen de orina", "uroanalisis"),
    "funcion_renal": ("funcion renal", "creatinina"),
    "electrolitos": ("electrolitos", "ionograma"),
    "glucosa": ("glucosa", "glucemia", "glicemia"),
    "ferritina": ("ferritina", "perfil de hierro"),
    "hemoglobina_glicosilada": ("hemoglobina glicosilada", "hemoglobina glucosilada", "hemoglobina glicada", "hba1c"),
    "prueba_molecular_esputo": ("prueba molecular de esputo", "pcr de esputo"),
    "beta_hcg": ("beta hcg", "bhcg", "gonadotropina corionica"),
    "ecografia_pelvica": ("ecografia pelvica", "ecografia transvaginal", "ecografia obstetrica"),
    "microscopia_vaginal": ("microscopia vaginal", "exudado vaginal", "secrecion vaginal"),
    "prueba_molecular_vaginal": ("prueba molecular vaginal", "pcr vaginal"),
    # Temas propios del caso de prueba original (CARD-001).
    "inicio_dolor": ("desde cuando", "cuando comenzo", "inicio", "duracion", "como lo describiria", "dolor"),
    "fotofobia": ("fotofobia", "luz", "molesta la luz"),
    "nauseas": ("nausea", "nauseas", "vomito", "vomitos"),
    "antecedente_familiar": ("antecedente familiar", "familia", "madre", "padre", "migraña"),
    "signos_alarma": ("debilidad", "hablar", "desmayo", "rigidez", "signos de alarma"),
    "examen_neurologico": ("examen neurologico", "exploracion neurologica", "examinar neurologico"),
    "hemograma": ("hemograma", "analisis de sangre"),
    "tomografia": ("tomografia", "tac", "imagen cerebral"),
    "neurologia": ("neurologia", "neurologo", "interconsulta neurologica"),
}


MODE_BY_INTENT: dict[Intent, str] = {
    Intent.ASK_PATIENT: "al_preguntar",
    Intent.ASK_ASSISTANT: "al_preguntar",
    Intent.REQUEST_SPECIALIST: "al_preguntar",
    Intent.EXAMINE: "al_examinar",
    Intent.REQUEST_LAB: "al_solicitar_examen",
    Intent.REQUEST_RADIOLOGY: "al_solicitar_examen",
    Intent.PROPOSE_HYPOTHESIS: "al_preguntar",
    Intent.PROPOSE_DIAGNOSIS: "al_preguntar",
    Intent.PROPOSE_TREATMENT: "al_preguntar",
    Intent.FINISH: "al_preguntar",
}


@dataclass(frozen=True)
class DisclosureDecision:
    allowed_evidence_ids: list[str]
    matched_requirements: list[str]


# Temas de los exámenes que piden el laboratorio y radiología (ver ALIASES). Sirven para distinguir un
# examen concreto («Pido un hemograma») de un pedido genérico («unos análisis de sangre»).
EXAM_TOPICS = (
    "coagulacion", "ph_vaginal", "funcion_tiroidea", "imagen_osea", "radiografia", "factores_coagulacion",
    "prolactina", "electroencefalograma", "electrocardiograma", "troponina", "dimero_d", "radiografia_torax",
    "angiotomografia_torax", "hemograma", "tomografia",
    "flujo_espiratorio", "gasometria", "ecocardiografia", "estudio_lcr", "angiografia_cerebral",
    "ecografia_abdominal", "tomografia_abdominal", "uroanalisis", "funcion_renal", "electrolitos",
    "glucosa", "ferritina", "hemoglobina_glicosilada", "prueba_molecular_esputo", "beta_hcg",
    "ecografia_pelvica", "microscopia_vaginal", "prueba_molecular_vaginal",
)
# Alias que no nombran un examen concreto: no bastan para decir que «ese examen no se realizó».
GENERIC_EXAM_TERMS = frozenset({"analisis de sangre"})


class DisclosurePolicy:
    """Aplica reveal_policy sin LLM y calcula allowed_evidence_ids por turno."""

    def authorize(
        self,
        *,
        case: dict[str, Any],
        role: AgentRole,
        intent: Intent,
        student_message: str,
    ) -> DisclosureDecision:
        mode = MODE_BY_INTENT[intent]
        text = _normalize(student_message)
        allowed: list[str] = []
        matched: list[str] = []

        for item in case.get("on_request", []):
            policy = item.get("reveal_policy") or {}
            if policy.get("owner") != role.value or policy.get("mode") != mode:
                continue
            required = [str(value) for value in policy.get("requires", [])]
            if required and not all(self._requirement_matches(req, text) for req in required):
                continue
            allowed.append(str(item["evidence_id"]))
            matched.extend(required)

        return DisclosureDecision(
            allowed_evidence_ids=allowed,
            matched_requirements=list(dict.fromkeys(matched)),
        )

    @staticmethod
    def names_specific_exam(student_message: str) -> bool:
        """True si el mensaje nombra un examen concreto; False si el pedido es genérico."""
        message = _normalize(student_message)
        terms = {
            _normalize(term)
            for topic in EXAM_TOPICS
            for term in (topic.replace("_", " "), *ALIASES.get(topic, ()))
        } - {_normalize(term) for term in GENERIC_EXAM_TERMS}
        return any(f" {term} " in f" {message} " for term in terms if term)

    @staticmethod
    def initial_evidence_ids(case: dict[str, Any]) -> list[str]:
        public = case["public"]
        ids = [str(public["chief_complaint"]["evidence_id"])]
        ids.extend(str(item["evidence_id"]) for item in public.get("items", []))
        return ids

    @staticmethod
    def _requirement_matches(requirement: str, normalized_message: str) -> bool:
        direct = _normalize(requirement.replace("_", " "))
        candidates = (direct, *ALIASES.get(requirement, ()))
        return any(_normalize(candidate) in normalized_message for candidate in candidates if candidate)
