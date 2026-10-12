"""Familia sintética «dolor torácico agudo»: EME-101, EME-102 y EME-103.

Tres pacientes llegan con el mismo motivo de consulta. Lo que separa un infarto con elevación del ST,
una tromboembolia pulmonar y una disección aórtica solo aparece si el estudiante pregunta, examina o
pide exámenes. Cada caso tiene como diferenciales los diagnósticos de los otros dos (y la pericarditis
aguda), con los datos que los descartan. Diseño y fuentes: data/cases/familias/README.md.

Uso (desde backend/):  .venv\\Scripts\\python.exe -m case_preparation.familias.dolor_toracico
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from server.cases.rules import check_batch_rules, check_case_rules, check_case_warnings
from server.cases.validator import validate_case_document

ROOT = Path(__file__).resolve().parents[3]
CURATED = ROOT / "data" / "cases" / "curated"
FAMILY = "dolor_toracico"
CREATED_AT = "2026-10-12"

MOTIVO = "Dolor en el pecho que empezó hace unas 2 horas y no se le pasa."

IAM = "Infarto agudo de miocardio con elevación del ST"
TEP = "Tromboembolia pulmonar aguda"
DISECCION = "Disección aórtica aguda tipo A"
PERICARDITIS = "Pericarditis aguda"

# Quién revela cada dato y ante qué pedido (contrato R14).
POLICY = {
    "caracteristicas": ("anamnesis", "Características del dolor", "paciente", "al_preguntar", ["caracteristicas_sintoma"]),
    "inicio": ("anamnesis", "Inicio y evolución", "paciente", "al_preguntar", ["inicio_y_evolucion"]),
    "asociados": ("sintoma", "Síntomas acompañantes", "paciente", "al_preguntar", ["sintomas_asociados"]),
    "antecedentes": ("antecedente", "Antecedentes personales", "paciente", "al_preguntar", ["antecedentes_personales"]),
    "familiares": ("antecedente", "Antecedentes familiares", "paciente", "al_preguntar", ["antecedentes_familiares"]),
    "medicacion": ("medicacion", "Medicación habitual", "paciente", "al_preguntar", ["medicacion"]),
    "alergias": ("antecedente", "Alergias", "paciente", "al_preguntar", ["alergias"]),
    "habitos": ("antecedente", "Hábitos y viajes", "paciente", "al_preguntar", ["habitos"]),
    "exploracion": ("examen_fisico", "Exploración física", "medico_asistente", "al_examinar", ["exploracion_fisica"]),
    "ecg": ("estudio", "Electrocardiograma de 12 derivaciones", "laboratorio", "al_solicitar_examen", ["electrocardiograma"]),
    "troponina": ("laboratorio", "Troponina I ultrasensible", "laboratorio", "al_solicitar_examen", ["troponina"]),
    "dimero": ("laboratorio", "Dímero D", "laboratorio", "al_solicitar_examen", ["dimero_d"]),
    "radiografia": ("imagen", "Radiografía de tórax", "radiologia", "al_solicitar_examen", ["radiografia_torax"]),
    "angiotac": ("imagen", "Angiotomografía de tórax", "radiologia", "al_solicitar_examen", ["angiotomografia_torax"]),
}
EVIDENCE_TYPE = {
    "anamnesis": "anamnesis", "sintoma": "sintoma", "antecedente": "antecedente", "medicacion": "medicacion",
    "examen_fisico": "examen", "estudio": "estudio", "laboratorio": "lab", "imagen": "imagen",
}
NAMES = {
    "caracteristicas": "caracteristicas_dolor", "inicio": "inicio_evolucion", "asociados": "sintomas_acompanantes",
    "antecedentes": "antecedentes", "familiares": "antecedentes_familiares", "medicacion": "tratamiento_habitual",
    "alergias": "alergias", "habitos": "habitos", "exploracion": "exploracion_fisica", "ecg": "electrocardiograma",
    "troponina": "troponina", "dimero": "dimero_d", "radiografia": "radiografia_torax", "angiotac": "angiotomografia_torax",
}
TROPONINA_RANGO = "< 26 ng/L"
INTERPRETATION = {"N": "dentro del rango normal", "H": "por encima del rango normal", "L": "por debajo del rango normal", "A": "anormal"}
DIMERO_RANGO = "< 500 ng/mL"

CASES = [
    {
        "case_id": "EME-101",
        "slug": "infarto_inferior",
        "patient": {"alias": "Carlos Mendoza", "age_years": 58, "sex": "masculino"},
        "vitals": "Presión arterial 148/92 mmHg, pulso 98/min, frecuencia respiratoria 20/min, temperatura 36,8 °C y saturación de oxígeno 95 % al aire ambiente.",
        "data": {
            "caracteristicas": "Es un dolor opresivo, como un peso en el centro del pecho, que se le va al brazo izquierdo y a la mandíbula. No cambia al respirar, al moverse ni al inclinarse hacia adelante. Lo califica con 8 de 10.",
            "inicio": "Empezó hace unas 2 horas mientras subía las escaleras de su casa cargando bolsas; no se le quitó al sentarse. La semana pasada tuvo molestias parecidas al caminar rápido, que se le pasaban en pocos minutos al descansar.",
            "asociados": "Sudor frío y náuseas desde que empezó el dolor, y un poco de falta de aire. No ha tenido tos, fiebre ni desmayos.",
            "antecedentes": "Diabetes tipo 2 desde hace 8 años e hipertensión arterial. Le dijeron que tenía el colesterol alto, pero no se trata. No lo han operado y no ha estado en cama en las últimas semanas.",
            "familiares": "Su padre murió de un ataque al corazón a los 60 años.",
            "medicacion": "Metformina 850 mg dos veces al día y enalapril 10 mg al día.",
            "alergias": "No tiene alergias conocidas a medicamentos.",
            "habitos": "Fuma una cajetilla al día desde hace 30 años. No ha hecho viajes largos recientemente.",
            "exploracion": "Paciente pálido y sudoroso. Ruidos cardiacos rítmicos, sin soplos ni roce. Pulmones con murmullo vesicular normal, sin crepitantes. Pulsos radiales simétricos; presión arterial 146/90 mmHg en el brazo derecho y 148/92 mmHg en el izquierdo. Piernas sin edema y pantorrillas no dolorosas.",
            "ecg": "Ritmo sinusal a 96/min. Elevación del segmento ST de 3 mm en II, III y aVF, con descenso del ST en I y aVL.",
            "troponina": (2850, "ng/L", TROPONINA_RANGO, "H"),
            "dimero": (420, "ng/mL", DIMERO_RANGO, "N"),
            "radiografia": "Silueta cardiaca y mediastino de tamaño normal. Campos pulmonares sin infiltrados ni derrame. Sin neumotórax.",
            "angiotac": "Arterias pulmonares sin defectos de llenado. Aorta de calibre normal, sin colgajo intimal.",
        },
        "diagnosis": (IAM, ["Infarto agudo de miocardio", "IAMCEST", "Síndrome coronario agudo con elevación del ST", "Infarto de cara inferior"]),
        "differentials": [
            (TEP, True, ["habitos", "exploracion", "dimero", "angiotac"]),
            (DISECCION, True, ["caracteristicas", "exploracion", "radiografia", "angiotac"]),
            (PERICARDITIS, False, ["caracteristicas", "exploracion", "ecg"]),
        ],
        "treatment": (
            "Reperfusión urgente: angioplastia primaria, idealmente en menos de 90 minutos desde el diagnóstico, o fibrinólisis si no se puede hacer en menos de 120 minutos. Doble antiagregación, anticoagulación y analgesia.",
            [
                "Electrocardiograma en los primeros 10 minutos de la llegada.",
                "Activar la sala de hemodinamia para angioplastia primaria.",
                "Aspirina y un segundo antiagregante, más anticoagulación, si no hay contraindicación.",
                "Oxígeno solo si la saturación es menor de 90 %.",
            ],
        ),
        "contraindications": [],
        "key_questions": [
            ("Características del dolor: opresivo, irradiado al brazo izquierdo y la mandíbula", ["caracteristicas"], 5, True, "razonamiento_clinico"),
            ("Inicio con el esfuerzo y molestias previas al caminar", ["inicio"], 4, True, "anamnesis_incompleta"),
            ("Factores de riesgo: diabetes, hipertensión, colesterol, tabaco y antecedente familiar", ["antecedentes", "habitos", "familiares"], 4, True, "anamnesis_incompleta"),
            ("Alergias antes de indicar antiagregantes", ["alergias"], 4, True, "negligencia"),
            ("Electrocardiograma: elevación del ST en cara inferior", ["ecg"], 5, True, "negligencia"),
            ("Troponina elevada", ["troponina"], 3, False, "razonamiento_clinico"),
        ],
        "tests": (["electrocardiograma", "troponina"], ["radiografia_torax"], ["dimero_d", "angiotomografia_torax"]),
    },
    {
        "case_id": "EME-102",
        "slug": "tromboembolia_pulmonar",
        "patient": {"alias": "Luis Ramírez", "age_years": 56, "sex": "masculino"},
        "vitals": "Presión arterial 126/78 mmHg, pulso 112/min, frecuencia respiratoria 26/min, temperatura 37,4 °C y saturación de oxígeno 90 % al aire ambiente.",
        "data": {
            "caracteristicas": "Es un dolor punzante en el lado derecho del pecho que empeora al respirar hondo y al toser. No se le va al brazo ni a la espalda y no cambia al inclinarse hacia adelante. Lo califica con 6 de 10.",
            "inicio": "Empezó de golpe hace unas 2 horas, junto con falta de aire, cuando se levantó de la cama para ir al baño. Desde entonces le cuesta respirar incluso sentado.",
            "asociados": "Falta de aire desde el inicio y tos seca; esta mañana escupió una flema con hilos de sangre. No ha tenido fiebre ni sudor frío.",
            "antecedentes": "Cáncer de próstata en tratamiento hormonal desde hace un año. Hipertensión arterial. No tiene diabetes.",
            "familiares": "No sabe de enfermedades del corazón en su familia.",
            "medicacion": "Leuprolida inyectable cada 3 meses y losartán 50 mg al día.",
            "alergias": "Es alérgico a la penicilina: le salieron ronchas en todo el cuerpo.",
            "habitos": "Hace 5 días volvió de un viaje en bus de 20 horas desde Cusco y casi no se levantó del asiento. No fuma ni toma alcohol.",
            "exploracion": "Paciente ansioso, respira rápido. Ruidos cardiacos rítmicos y rápidos, sin soplos ni roce; el segundo ruido pulmonar está aumentado. Pulmones con murmullo vesicular conservado, sin crepitantes. Pulsos simétricos y presión arterial igual en ambos brazos. Pantorrilla derecha hinchada, 3 cm más gruesa que la izquierda, caliente y dolorosa a la palpación.",
            "ecg": "Taquicardia sinusal a 112/min. Onda S profunda en I, onda Q y onda T negativa en III, y ondas T negativas de V1 a V3. Sin elevación del segmento ST.",
            "troponina": (38, "ng/L", TROPONINA_RANGO, "H"),
            "dimero": (3200, "ng/mL", DIMERO_RANGO, "H"),
            "radiografia": "Sin infiltrados ni derrame pleural importante. Silueta cardiaca y mediastino de tamaño normal.",
            "angiotac": "Defectos de llenado en la arteria pulmonar principal derecha que se extienden a las ramas lobares media e inferior. Relación entre ventrículo derecho e izquierdo de 1,1. Aorta de calibre normal, sin colgajo intimal.",
        },
        "diagnosis": (TEP, ["Tromboembolismo pulmonar", "Tromboembolia pulmonar", "Embolia pulmonar"]),
        "differentials": [
            (IAM, True, ["caracteristicas", "ecg"]),
            (DISECCION, True, ["caracteristicas", "exploracion", "angiotac"]),
            (PERICARDITIS, False, ["caracteristicas", "exploracion", "ecg"]),
        ],
        "treatment": (
            "Anticoagulación inmediata con heparina, ingreso con monitorización por el riesgo intermedio (ventrículo derecho dilatado y troponina elevada con presión normal) y fibrinólisis de rescate solo si se deteriora.",
            [
                "Calcular la probabilidad clínica (escala de Wells) antes de pedir exámenes.",
                "Con probabilidad alta, angiotomografía directa sin esperar el dímero D.",
                "Anticoagular con heparina de bajo peso molecular o heparina no fraccionada.",
                "Vigilar presión arterial y oxigenación por si necesita fibrinólisis.",
            ],
        ),
        "contraindications": [],
        "key_questions": [
            ("Características del dolor: pleurítico, empeora al respirar", ["caracteristicas"], 5, True, "razonamiento_clinico"),
            ("Inicio brusco con falta de aire", ["inicio", "asociados"], 4, True, "anamnesis_incompleta"),
            ("Factores de riesgo de trombosis: cáncer y viaje largo inmóvil", ["antecedentes", "habitos"], 5, True, "anamnesis_incompleta"),
            ("Alergias antes de indicar medicamentos", ["alergias"], 3, True, "negligencia"),
            ("Exploración: pantorrilla derecha hinchada y dolorosa", ["exploracion"], 4, True, "razonamiento_clinico"),
            ("Angiotomografía: defectos de llenado en las arterias pulmonares", ["angiotac"], 5, True, "negligencia"),
        ],
        "tests": (["angiotomografia_torax", "electrocardiograma", "troponina"], ["dimero_d", "radiografia_torax"], []),
    },
    {
        "case_id": "EME-103",
        "slug": "diseccion_aortica",
        "patient": {"alias": "Víctor Chávez", "age_years": 61, "sex": "masculino"},
        "vitals": "Presión arterial 172/98 mmHg, pulso 104/min, frecuencia respiratoria 20/min, temperatura 36,6 °C y saturación de oxígeno 97 % al aire ambiente.",
        "data": {
            "caracteristicas": "Es el peor dolor de su vida, como si algo se le desgarrara por dentro. Empezó en el centro del pecho y ahora lo siente entre los omóplatos. No cambia al respirar ni al inclinarse hacia adelante. Lo califica con 10 de 10.",
            "inicio": "Empezó de golpe hace unas 2 horas, con toda su fuerza desde el primer momento, mientras cargaba un costal en el mercado. Desde entonces el dolor se ha ido corriendo hacia la espalda.",
            "asociados": "Al comienzo sintió que se iba a desmayar y estuvo mareado unos minutos. Tiene sudor frío. No tiene tos ni fiebre.",
            "antecedentes": "Hipertensión arterial desde hace 15 años, mal controlada. No lo han operado.",
            "familiares": "No recuerda enfermedades del corazón en su familia.",
            "medicacion": "Le recetaron amlodipino 10 mg al día, pero dejó de tomarlo hace 4 meses.",
            "alergias": "No tiene alergias conocidas a medicamentos.",
            "habitos": "Fuma 10 cigarrillos al día y toma alcohol los fines de semana. No consume drogas. No ha hecho viajes recientes.",
            "exploracion": "Paciente sudoroso y muy angustiado por el dolor. Presión arterial 174/98 mmHg en el brazo derecho y 132/80 mmHg en el izquierdo; pulso radial izquierdo más débil que el derecho. Soplo diastólico suave en el borde esternal izquierdo. Pulmones sin crepitantes. Piernas sin edema y pantorrillas no dolorosas.",
            "ecg": "Ritmo sinusal a 104/min con signos de crecimiento del ventrículo izquierdo. Sin elevación ni descenso del segmento ST.",
            "troponina": (18, "ng/L", TROPONINA_RANGO, "N"),
            "dimero": (2400, "ng/mL", DIMERO_RANGO, "H"),
            "radiografia": "Mediastino ensanchado, de 8,5 cm a la altura del botón aórtico, con contorno aórtico irregular. Campos pulmonares sin infiltrados.",
            "angiotac": "Colgajo intimal que se origina en la aorta ascendente, 2 cm por encima de la válvula aórtica, y se extiende por el arco hasta la aorta descendente, con una luz verdadera y una luz falsa. Arterias pulmonares sin defectos de llenado.",
        },
        "diagnosis": (DISECCION, ["Disección aórtica aguda", "Disección de aorta", "Disección aórtica", "Síndrome aórtico agudo"]),
        "differentials": [
            (IAM, True, ["ecg", "troponina"]),
            (TEP, True, ["exploracion", "angiotac"]),
            (PERICARDITIS, False, ["caracteristicas", "ecg"]),
        ],
        "treatment": (
            "Emergencia quirúrgica: cirugía urgente de la aorta ascendente. Mientras tanto, analgesia con opioides y betabloqueador intravenoso para bajar la frecuencia a menos de 60/min y la presión sistólica a 100–120 mmHg.",
            [
                "Medir la presión en ambos brazos ante un dolor torácico desgarrante.",
                "Angiotomografía urgente para confirmar y ver la extensión.",
                "Betabloqueador intravenoso y analgesia; vasodilatador solo después del betabloqueador.",
                "Interconsulta urgente con cirugía cardiovascular.",
            ],
        ),
        "contraindications": [
            ("Antiagregantes, anticoagulantes y fibrinolíticos (aspirina, heparina, alteplasa)",
             "Aumentan el riesgo de sangrado y de rotura de la aorta; darlos como si fuera un infarto puede ser mortal.",
             "angiotac",
             "Analgesia, betabloqueador intravenoso y cirugía urgente."),
        ],
        "key_questions": [
            ("Características del dolor: desgarrante, migra a la espalda, máximo desde el inicio", ["caracteristicas", "inicio"], 5, True, "razonamiento_clinico"),
            ("Hipertensión mal controlada y abandono del tratamiento", ["antecedentes", "medicacion"], 4, True, "anamnesis_incompleta"),
            ("Presión arterial en ambos brazos y pulsos", ["exploracion"], 5, True, "negligencia"),
            ("Alergias antes de indicar medicamentos", ["alergias"], 3, True, "negligencia"),
            ("Angiotomografía: colgajo intimal en la aorta ascendente", ["angiotac"], 5, True, "negligencia"),
            ("Electrocardiograma sin isquemia: no tratar como infarto", ["ecg"], 4, True, "razonamiento_clinico"),
        ],
        "tests": (["angiotomografia_torax", "electrocardiograma", "radiografia_torax"], ["troponina"], ["dimero_d"]),
    },
]


def _evidence_id(case_id: str, key: str) -> str:
    return f"{case_id}.{EVIDENCE_TYPE[POLICY[key][0]]}.{NAMES[key]}"


def build_case(spec: dict) -> dict:
    case_id = spec["case_id"]
    on_request = []
    for key, content in spec["data"].items():
        category, label, owner, mode, requires = POLICY[key]
        item = {"evidence_id": _evidence_id(case_id, key), "category": category, "label": label}
        if isinstance(content, tuple):
            value, unit, reference_range, interpretation = content
            item.update(value=value, unit=unit, reference_range=reference_range, interpretation=interpretation)
            # El texto lleva el rango: sin él, el estudiante no sabe si el valor es normal.
            item["text"] = f"{label}: {value} {unit} (valor de referencia {reference_range}); {INTERPRETATION[interpretation]}."
        else:
            item["text"] = content
        item["reveal_policy"] = {"owner": owner, "mode": mode, "requires": requires}
        on_request.append(item)
    name, synonyms = spec["diagnosis"]
    summary, actions = spec["treatment"]
    recommended, optional, unnecessary = spec["tests"]
    return {
        "schema_version": "1.1.0",
        "case_id": case_id,
        "title": f"Paciente de {spec['patient']['age_years']} años con dolor en el pecho",
        "specialty": "emergencias",
        "language": "es",
        "status": "curado",
        "source": {"dataset": "sintetico", "item_id": f"{FAMILY}/{spec['slug']}", "license": "CC BY 4.0", "method": "generado_ia"},
        "public": {
            "patient": spec["patient"],
            "chief_complaint": {"evidence_id": f"{case_id}.motivo.queja_principal", "category": "motivo", "label": "Motivo de consulta", "text": MOTIVO},
            "items": [{"evidence_id": f"{case_id}.vital.signos_vitales", "category": "signo_vital", "label": "Signos vitales", "text": spec["vitals"]}],
            "allergies_recorded": False,
        },
        "on_request": on_request,
        "protected": {
            "diagnosis": {"name": name, "synonyms": synonyms},
            "differentials": [
                {"name": d_name, "must_not_miss": must, "discard_evidence_ids": [_evidence_id(case_id, key) for key in keys]}
                for d_name, must, keys in spec["differentials"]
            ],
            "treatment_reference": {"summary": summary, "key_actions": actions},
            "contraindications": [
                {"id": f"ci{i}", "drug_or_class": drug, "reason": reason, "evidence_id": _evidence_id(case_id, key), "alternative": alternative}
                for i, (drug, reason, key, alternative) in enumerate(spec["contraindications"], start=1)
            ],
            "evaluation": {
                "key_questions": [
                    {"id": f"kq{i}", "topic": topic, "evidence_ids": [_evidence_id(case_id, key) for key in keys],
                     "weight": weight, "critical": critical, "error_if_missing": error}
                    for i, (topic, keys, weight, critical, error) in enumerate(spec["key_questions"], start=1)
                ],
                "tests": {"recommended": recommended, "optional": optional, "unnecessary": unnecessary},
            },
        },
        "provenance": {
            "created_by": "case_preparation.familias.dolor_toracico",
            "created_at": CREATED_AT,
            "validator_version": "1.1.0",
            "validated_at": CREATED_AT,
            "curated_by": "James Bryam Gutiérrez Rubio",
            "curated_at": CREATED_AT,
            "rejection_reason": None,
        },
    }


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    cases = [build_case(spec) for spec in CASES]
    problems = check_batch_rules(cases)
    for case in cases:
        validate_case_document(case)
        problems += check_case_rules(case) + check_case_warnings(case)
    if problems:
        for problem in problems:
            print(f"  FALLA {problem}")
        return 1
    for case in cases:
        path = CURATED / f"{case['case_id']}.json"
        path.write_text(json.dumps(case, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"  {path.relative_to(ROOT)}: {case['protected']['diagnosis']['name']} · {len(case['on_request'])} datos a petición")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
