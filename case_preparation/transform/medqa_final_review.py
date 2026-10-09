from __future__ import annotations

import json
from collections import Counter
from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any

from server.cases.validator import validate_case_document
from .medqa_selection import _build_case

REPO_ROOT = Path(__file__).resolve().parents[2]
CANDIDATES_PATH = REPO_ROOT / "data" / "interim" / "medqa_candidatos.jsonl"
OUTPUT_DIR = REPO_ROOT / "data" / "cases" / "validated_second_pass"
CURATED_OUTPUT_DIR = REPO_ROOT / "data" / "cases" / "curated"
REJECTED_OUTPUT_DIR = REPO_ROOT / "data" / "cases" / "rejected"
VALIDATED_OUTPUT_DIR = REPO_ROOT / "data" / "cases" / "validated"
FINAL_SELECTION_PATH = REPO_ROOT / "data" / "cases" / "final_selection" / "medqa_final_10.json"
SELECTION_REVIEW_PATH = REPO_ROOT / "data" / "cases" / "reviews" / "second_pass_selection.json"
CLINICAL_REVIEW_PATH = REPO_ROOT / "data" / "cases" / "reviews" / "clinical_coherence_review.json"
LEGACY_CURATION_SUMMARY_PATH = REPO_ROOT / "data" / "cases" / "reviews" / "curation_summary.json"
LEGACY_SELECTION_INDEX_PATH = (
    REPO_ROOT / "data" / "cases" / "validated" / "medqa_selected_cases_index.json"
)
LEGACY_SELECTION_AUDIT_PATH = (
    REPO_ROOT / "data" / "cases" / "reviews" / "legacy_selection_audit.json"
)
CURATION_SUMMARY_PATH = (
    REPO_ROOT / "data" / "cases" / "reviews" / "medqa_second_pass_curation_summary.json"
)
LEGACY_CASES_TO_REJECT = {
    "MED-001": (
        "No es un caso de paciente; corresponde a un diseño de estudio o ensayo clínico agrupado."
    ),
    "MED-002": (
        "No es un caso de paciente; corresponde a un diseño de estudio o ensayo clínico agrupado."
    ),
    "PED-003": (
        "No es un caso de paciente; corresponde a un diseño de estudio o ensayo clínico agrupado."
    ),
    "PED-004": (
        "No es un caso de paciente; corresponde a un diseño de estudio o ensayo clínico agrupado."
    ),
    "CIR-007": (
        "Fuente incompleta para un caso clínico: el resumen original no está disponible, la ficha contiene "
        "diagnóstico genérico y el sexo de la copia curada contradice el dato fuente."
    ),
    "CIR-008": (
        "Fuente incompleta para un caso clínico: el resumen original no está disponible, la ficha contiene "
        "diagnóstico genérico y el sexo de la copia curada contradice el dato fuente."
    ),
    "EME-009": (
        "El texto fuente es el resumen de un ensayo comparativo sobre imágenes para nefrolitiasis, no un caso "
        "clínico individual; la ficha tampoco tiene diagnóstico específico."
    ),
    "EME-010": (
        "El texto fuente es un duplicado del resumen de un ensayo comparativo sobre imágenes para nefrolitiasis, "
        "no un caso clínico individual; la ficha tampoco tiene diagnóstico específico."
    ),
    "GOB-005": (
        "La fuente describe a una recién nacida de un día con un problema de extremidad superior, no un caso "
        "de ginecología-obstetricia; la copia curada contiene sexo y edad incompatibles con la fuente."
    ),
    "GOB-006": (
        "La fuente describe a una recién nacida de un día con un problema de extremidad superior, no un caso "
        "de ginecología-obstetricia; la copia curada contiene sexo y edad incompatibles con la fuente."
    ),
}
INVALIDATED_LEGACY_CURATIONS = {
    "CIR-007",
    "CIR-008",
    "EME-009",
    "EME-010",
    "GOB-005",
    "GOB-006",
}

SELECTED_CASES: list[dict[str, Any]] = [
    {
        "case_id": "MED-008",
        "candidate_id": "medqa-bd8bb86bdc2e57fe",
        "specialty": "medicina_interna",
        "clinical_diagnosis": "Enfermedad de Lyme con eritema migrans",
        "clinical_summary_es": (
            "Mujer de 48 años con cefalea, fiebre de hasta 40,1 °C, escalofríos, artralgias, sed intensa y "
            "erupción progresiva en la espalda. Una lesión pequeña evolucionó en tres días a una placa "
            "circular eritematosa en diana de 17 × 19 cm; había caminado por el bosque tres semanas antes y "
            "no identificó garrapata. Refiere anafilaxia previa a tetraciclinas. La pregunta fuente pide "
            "elegir un antimicrobiano."
        ),
        "clinical_differentials": [
            "Celulitis bacteriana",
            "Eritema multiforme",
            "Rickettsiosis",
        ],
        "allergies": ["Tetraciclinas (antecedente de anafilaxia)"],
        "treatment_reference": {
            "summary": (
                "La respuesta correcta registrada por MedQA es amoxicilina (opción B); el ítem no especifica "
                "dosis ni duración y no constituye por sí solo una prescripción."
            ),
            "key_actions": [
                "Conservar la respuesta textual de la fuente: amoxicilina.",
                "Verificar pauta, alergias y guías clínicas vigentes antes de cualquier uso.",
            ],
        },
        "rationale": (
            "Medicina interna: cuadro de eritema migrans y síntomas sistémicos; alergia a tetraciclinas y "
            "respuesta fuente recuperada como opción B (amoxicilina)."
        ),
    },
    {
        "case_id": "MED-009",
        "candidate_id": "medqa-7fe0528c54197057",
        "specialty": "medicina_interna",
        "clinical_diagnosis": "Carcinoma basocelular",
        "clinical_summary_es": (
            "Hombre de 68 años acude a control anual; su hipertensión está controlada y no tiene otros síntomas. "
            "Presenta en el párpado una pápula perlada rosada de 0,5 cm, con borde sobreelevado y telangiectasias. "
            "Tiene piel clara, cabello rubio y exposición laboral prolongada al sol sin protector; notó la lesión "
            "hace seis meses y ha crecido ligeramente."
        ),
        "clinical_differentials": [
            "Carcinoma escamocelular",
            "Queratoacantoma",
            "Carcinoma verrugoso",
            "Queratosis actínica",
        ],
        "rationale": (
            "Medicina interna: adulto con lesión cutánea descrita clínicamente; este registro no depende de una "
            "imagen ausente."
        ),
    },
    {
        "case_id": "PED-007",
        "candidate_id": "medqa-dadd721b55c88d20",
        "specialty": "pediatria",
        "clinical_diagnosis": "Enfermedad de Legg-Calvé-Perthes",
        "clinical_summary_es": (
            "Niño de 7 años presenta cojera y dolor referido en la rodilla izquierda. Está afebril, con signos "
            "vitales estables y desarrollo adecuado. La rodilla conserva todo su rango de movimiento, pero la "
            "movilización pasiva de la cadera provoca dolor; la radiografía muestra aplanamiento de la cabeza "
            "femoral izquierda."
        ),
        "clinical_differentials": [
            "Artritis séptica",
            "Raquitismo",
            "Osteopetrosis",
            "Enfermedad de Osgood-Schlatter",
            "Epifisiólisis de la cabeza femoral",
            "Artritis idiopática juvenil",
        ],
        "rationale": "Pediatría: paciente de 7 años y hallazgos osteoarticulares pediátricos explícitos.",
    },
    {
        "case_id": "PED-010",
        "candidate_id": "medqa-5fc375051c4a68f2",
        "specialty": "pediatria",
        "clinical_diagnosis": "Síndrome de McCune-Albright",
        "clinical_summary_es": (
            "Niña de 6 años evaluada después de una fractura del brazo. Se describen desarrollo mamario "
            "precoz, manchas café con leche, displasia fibrosa ósea y edad ósea de 9 años. El enunciado "
            "fuente menciona alteraciones tiroideas con términos contradictorios, por lo que no se especifica "
            "si tiene hipo o hipertiroidismo."
        ),
        "clinical_differentials": [
            "Neurofibromatosis tipo 1",
            "Síndrome de Peutz-Jeghers",
            "Displasia fibrosa ósea no sindrómica",
            "Otras causas de pubertad precoz periférica",
        ],
        "rationale": (
            "Pediatría: fractura, manchas café con leche, displasia fibrosa y desarrollo mamario precoz "
            "apoyan síndrome de McCune-Albright."
        ),
    },
    {
        "case_id": "GOB-003",
        "candidate_id": "medqa-b437ab65d13f9352",
        "specialty": "ginecologia_obstetricia",
        "clinical_diagnosis": "Infarto hipofisario posparto (síndrome de Sheehan)",
        "clinical_summary_es": (
            "Mujer de 24 años tuvo un parto a término con Apgar 9 y 10. A los 30 minutos presentó hipotensión "
            "(80/60 mmHg), taquicardia (124/min), extremidades frías y útero atónico; recibió reanimación con "
            "cuatro unidades de líquidos intravenosos y cuatro unidades de sangre total, con estabilización "
            "posterior. A la mañana siguiente informó "
            "que no podía lactar."
        ),
        "clinical_differentials": [
            "Tumor hipofisario",
            "Retención de restos placentarios",
            "Hemorragia hipofisaria",
        ],
        "rationale": (
            "Gineco-obstetricia: complicación inmediatamente posparto con hemorragia/hipotensión y falla de lactancia."
        ),
    },
    {
        "case_id": "GOB-004",
        "candidate_id": "medqa-a04db516708da5ae",
        "specialty": "ginecologia_obstetricia",
        "clinical_diagnosis": "Tricomoniasis vulvovaginal",
        "clinical_summary_es": (
            "Mujer de 24 años consulta por dos semanas de molestia pélvica leve, flujo vaginal espumoso "
            "amarillento, dispareunia y disuria ocasional. Refiere dos parejas sexuales y uso inconsistente de "
            "preservativo. En la exploración hay eritema vulvovaginal, cérvix en fresa doloroso a la movilización "
            "y flujo maloliente verde-amarillo; pH vaginal 5,8."
        ),
        "clinical_differentials": [
            "Candidiasis vulvovaginal",
            "Vaginitis atrófica",
            "Vaginosis bacteriana",
            "Infección por clamidia",
        ],
        "rationale": (
            "Gineco-obstetricia: síntomas genitales y hallazgos de examen pélvico explícitos."
        ),
    },
    {
        "case_id": "CIR-005",
        "candidate_id": "medqa-4135d59786b5b7ac",
        "specialty": "cirugia_general",
        "clinical_diagnosis": "Hemofilia A",
        "clinical_summary_es": (
            "Hombre de 28 años con dolor abdominal intenso y apendicitis fue sometido a apendicectomía urgente. "
            "Durante la intervención presentó hemorragia persistente que requirió transfusión. Antes de la "
            "cirugía tenía tiempo de sangrado, tiempo de protrombina/INR y recuento plaquetario normales; "
            "después se encontró TTPa prolongado y refirió antecedente familiar de trastorno hemorrágico."
        ),
        "clinical_differentials": [
            "Síndrome de Bernard-Soulier",
            "Trombastenia de Glanzmann",
            "Púrpura trombótica trombocitopénica",
            "Enfermedad de von Willebrand",
        ],
        "rationale": (
            "Cirugía general: episodio hemorrágico intraoperatorio durante apendicectomía, con estudio de "
            "coagulación posoperatorio."
        ),
    },
    {
        "case_id": "CIR-006",
        "candidate_id": "medqa-e9b7102d702a0a7f",
        "specialty": "cirugia_general",
        "clinical_diagnosis": "Sepsis posoperatoria",
        "clinical_summary_es": (
            "Mujer de 68 años, quinto día después de hemicolectomía derecha electiva sin complicaciones "
            "intraoperatorias. Tiene diabetes tipo 2 de 20 años, hipertensión de 15 años, angina de esfuerzo "
            "de 6 años y antecedente de tabaquismo de 30 paquetes-año; antes era independiente. Presenta "
            "confusión, temperatura 38,5 °C, frecuencia respiratoria 28/min, "
            "saturación 92 % con oxígeno a 2 L/min y pulso 118/min. Tiene crepitantes en la base pulmonar "
            "derecha; la herida quirúrgica evoluciona bien y el abdomen está blando e indoloro."
        ),
        "clinical_differentials": [
            "Síndrome de respuesta inflamatoria sistémica no infeccioso",
            "Síndrome de disfunción multiorgánica",
            "Fiebre inducida por fármacos",
        ],
        "rationale": (
            "Cirugía general: deterioro infeccioso probable en el posoperatorio, con fiebre, taquipnea, "
            "hipoxemia y confusión."
        ),
    },
    {
        "case_id": "EME-001",
        "candidate_id": "medqa-a83444b6eabc9a5b",
        "specialty": "emergencias",
        "clinical_diagnosis": "Golpe de calor por esfuerzo",
        "clinical_summary_es": (
            "Hombre de 33 años es encontrado en el suelo en una obra y llega con alteración del estado mental "
            "(Glasgow 10), temperatura de 41,1 °C, presión arterial de 109/62 mmHg, pulso de 170/min, "
            "frecuencia respiratoria de 23/min y saturación de oxígeno de 95 % al aire ambiente. Fue sometido "
            "a anestesia meses antes; tiene esquizofrenia tratada con haloperidol, epilepsia tratada con "
            "fenitoína e hipertiroidismo tratado con propranolol. Presenta tono muscular bajo y diaforesis."
        ),
        "clinical_differentials": [
            "Hipertermia maligna",
            "Síndrome neuroléptico maligno",
            "Estado epiléptico",
            "Tormenta tiroidea",
        ],
        "rationale": "Emergencias: hipertermia grave y alteración aguda de conciencia en el lugar de trabajo.",
    },
    {
        "case_id": "EME-002",
        "candidate_id": "medqa-83b0322c93dff066",
        "specialty": "emergencias",
        "clinical_diagnosis": "Hemorragia subaracnoidea",
        "clinical_summary_es": (
            "Hombre de 57 años con hipertensión presenta cefalea intensa de inicio súbito mientras se baña, "
            "seguida de vómitos y deterioro del estado de conciencia. En urgencias responde de forma limitada "
            "a estímulos dolorosos y tiene rigidez de nuca; presión arterial 180/110 mmHg, temperatura 37,9 °C, "
            "pulso regular de 80/min y frecuencia respiratoria de 20/min."
        ),
        "clinical_differentials": [
            "Meningoencefalitis aguda",
            "Hemorragia intracerebral",
            "Crisis epiléptica",
        ],
        "rationale": (
            "Emergencias: cefalea súbita intensa, vómitos, alteración de conciencia y rigidez de nuca; "
            "la respuesta fuente es hemorragia subaracnoidea."
        ),
    },
]

SPANISH_SOURCE_TEXT: dict[str, dict[str, Any]] = {
    "medqa-bd8bb86bdc2e57fe": {
        "question": (
            "Mujer de 48 años consulta por cefalea, fiebre intermitente y escalofríos, artralgias, sed intensa "
            "y una erupción progresiva en la espalda. La lesión comenzó como una pequeña elevación y se "
            "convirtió en una erupción circular. Dos días antes tuvo fiebre de 39,4 °C; al acudir presenta "
            "40,1 °C y una placa eritematosa en diana de 17 × 19 cm. Caminó por el bosque tres semanas antes, "
            "aunque no vio ninguna garrapata. Tiene antecedente de anafilaxia a tetraciclinas. Según la fuente, "
            "¿qué antimicrobiano se eligió?"
        ),
        "options": ["Cefalexina", "Amoxicilina", "Azitromicina", "Eritromicina", "Doxiciclina"],
    },
    "medqa-7fe0528c54197057": {
        "question": (
            "Hombre de 68 años acude a su control anual sin síntomas y con hipertensión controlada. Se observa "
            "en el párpado una pápula de 0,5 cm, rosada y perlada, con borde sobreelevado y telangiectasias. "
            "Tiene piel clara, cabello rubio y exposición laboral prolongada al sol sin protector. La lesión "
            "apareció hace unos seis meses y ha crecido ligeramente. ¿Cuál es el diagnóstico más probable?"
        ),
        "options": [
            "Carcinoma escamocelular",
            "Queratoacantoma",
            "Carcinoma verrugoso",
            "Carcinoma basocelular",
            "Queratosis actínica",
        ],
    },
    "medqa-dadd721b55c88d20": {
        "question": (
            "Niño de 7 años presenta cojera y favorece la pierna izquierda; refiere dolor en la rodilla. Está "
            "afebril y con signos vitales estables. La rodilla tiene rango de movimiento completo, pero la "
            "movilización pasiva provoca dolor en la cadera izquierda. La radiografía muestra aplanamiento de "
            "la cabeza femoral izquierda. ¿Cuál es el diagnóstico más probable?"
        ),
        "options": [
            "Artritis séptica",
            "Raquitismo",
            "Osteopetrosis",
            "Enfermedad de Legg-Calvé-Perthes",
            "Enfermedad de Osgood-Schlatter",
            "Epifisiólisis de la cabeza femoral",
            "Artritis idiopática juvenil",
        ],
    },
    "medqa-5fc375051c4a68f2": {
        "question": (
            "Niña de 6 años hospitalizada por fractura del brazo presenta desarrollo mamario, manchas café "
            "con leche y displasia fibrosa en estudios óseos; su edad ósea se estima en 9 años. El texto fuente "
            "menciona alteraciones tiroideas de forma contradictoria, sin aclarar cuál presenta. ¿Cuál es el "
            "diagnóstico más probable?"
        ),
        "options": [
            "Síndrome de Fanconi",
            "Síndrome de McCune-Albright",
            "Neurofibromatosis",
            "Síndrome de Peutz-Jeghers",
        ],
    },
    "medqa-b437ab65d13f9352": {
        "question": (
            "Mujer de 24 años tiene un parto a término; el recién nacido obtiene Apgar de 9 y 10 al minuto y "
            "a los 5 minutos, respectivamente. Treinta minutos después, la madre presenta presión arterial de "
            "80/60 mmHg y pulso de 124/min; tiene extremidades frías y húmedas y útero atónico. Se administran "
            "cuatro unidades de líquidos intravenosos y cuatro unidades de sangre total, tras lo cual se "
            "estabiliza. A la mañana siguiente refiere que no puede lactar. Según la fuente, ¿cuál es la causa "
            "más probable de la falla de lactancia?"
        ),
        "options": [
            "Tumor hipofisario",
            "Tristeza puerperal",
            "Restos placentarios retenidos",
            "Infarto hipofisario",
            "Hemorragia hipofisaria",
        ],
    },
    "medqa-a04db516708da5ae": {
        "question": (
            "Mujer de 24 años consulta por dos semanas de molestia pélvica leve y flujo vaginal espumoso "
            "amarillento; también presenta dispareunia y disuria ocasional. Tiene dos parejas sexuales previas "
            "y uso inconsistente de preservativo. En la exploración se observa eritema vulvovaginal, cérvix "
            "en fresa doloroso a la movilización y flujo maloliente verdoso-amarillo. El pH vaginal es 5,8. "
            "¿Cuál es el diagnóstico más probable?"
        ),
        "options": [
            "Candidiasis vulvovaginal",
            "Vaginitis atrófica",
            "Vaginosis bacteriana",
            "Infección por clamidia",
            "Tricomoniasis",
        ],
    },
    "medqa-4135d59786b5b7ac": {
        "question": (
            "Hombre de 28 años con apendicitis se somete a apendicectomía urgente y presenta sangrado "
            "persistente que requiere transfusión. Antes de la cirugía tenía tiempo de sangrado, tiempo de "
            "protrombina/INR y recuento plaquetario normales; después se detecta TTPa prolongado y refiere "
            "antecedentes familiares de un trastorno hemorrágico. ¿Cuál es el diagnóstico más probable?"
        ),
        "options": [
            "Hemofilia A",
            "Síndrome de Bernard-Soulier",
            "Trombastenia de Glanzmann",
            "Púrpura trombótica trombocitopénica",
            "Enfermedad de von Willebrand",
        ],
    },
    "medqa-e9b7102d702a0a7f": {
        "question": (
            "Mujer de 68 años, en el quinto día tras una hemicolectomía derecha electiva sin complicaciones, "
            "presenta confusión. Antecedentes: diabetes tipo 2 de 20 años, hipertensión de 15 años, angina "
            "de esfuerzo de 6 años y tabaquismo de 30 paquetes-año; era independiente. Tiene fiebre de 38,5 °C, "
            "presión arterial de 110/65 mmHg, respiración de 28/min, saturación de oxígeno de 92 % pese a "
            "2 L/min y pulso de 118/min. Presenta crepitantes en la base pulmonar derecha; la herida evoluciona "
            "bien y el abdomen está blando e indoloro. ¿Cuál es el diagnóstico más probable?"
        ),
        "options": [
            "Síndrome de respuesta inflamatoria sistémica no infeccioso",
            "Síndrome de disfunción multiorgánica",
            "Sepsis",
            "Hipertermia maligna",
            "Fiebre inducida por fármacos",
        ],
    },
    "medqa-a83444b6eabc9a5b": {
        "question": (
            "Hombre de 33 años, trabajador de construcción, es encontrado en el suelo en el trabajo con "
            "alteración del estado mental. Se sometió a anestesia meses antes para una apendicectomía. Tiene "
            "esquizofrenia controlada con haloperidol, epilepsia tratada con fenitoína e hipertiroidismo y "
            "ansiedad tratados con propranolol. Temperatura de 41,1 °C, presión arterial de 109/62 mmHg, "
            "pulso de 170/min, frecuencia respiratoria de 23/min y saturación de oxígeno de 95 % al aire "
            "ambiente. Glasgow 10, tono muscular bajo, respuestas incoherentes, sudor y suciedad. ¿Cuál es "
            "el diagnóstico más probable?"
        ),
        "options": [
            "Golpe de calor por esfuerzo",
            "Hipertermia maligna",
            "Síndrome neuroléptico maligno",
            "Estado epiléptico",
            "Tormenta tiroidea",
        ],
    },
    "medqa-83b0322c93dff066": {
        "question": (
            "Hombre de 57 años con hipertensión presenta cefalea intensa de inicio súbito mientras se baña, "
            "seguida de vómitos. Unos 30 minutos después, en urgencias, tiene respuesta disminuida: abre los "
            "ojos y gime ante estímulos dolorosos, y presenta rigidez de nuca. Presión arterial de 180/110 mmHg, "
            "temperatura de 37,9 °C, pulso regular de 80/min y frecuencia respiratoria de 20/min. El enunciado "
            "fuente está redactado de forma deficiente; esta adaptación interpreta que la cefalea comenzó "
            "repentinamente mientras se bañaba. ¿Cuál es el diagnóstico más probable?"
        ),
        "options": [
            "Intoxicación por monóxido de carbono",
            "Hemorragia subaracnoidea",
            "Meningoencefalitis aguda",
            "Crisis epiléptica",
        ],
    },
}

CLINICAL_SOURCES: dict[str, dict[str, str]] = {
    "cdc_lyme": {
        "title": "CDC: Clinical treatment of erythema migrans",
        "url": "https://www.cdc.gov/lyme/hcp/clinical-care/erythema-migrans-rash.html",
    },
    "aad_bcc": {
        "title": "American Academy of Dermatology: Basal cell carcinoma",
        "url": "https://www.aad.org/public/diseases/skin-cancer/basal-cell-carcinoma",
    },
    "aaos_perthes": {
        "title": "AAOS OrthoInfo: Legg-Calve-Perthes disease",
        "url": "https://orthoinfo.aaos.org/en/diseases--conditions/legg-calve-perthes-disease/",
    },
    "medlineplus_mccune_albright": {
        "title": "MedlinePlus Genetics: McCune-Albright syndrome",
        "url": "https://medlineplus.gov/genetics/condition/mccune-albright-syndrome/",
    },
    "sheehan_statpearls": {
        "title": "NCBI Bookshelf: Sheehan syndrome",
        "url": "https://www.ncbi.nlm.nih.gov/books/NBK459166/",
    },
    "cdc_trich": {
        "title": "CDC STI Treatment Guidelines: Trichomoniasis",
        "url": "https://www.cdc.gov/std/treatment-guidelines/trichomoniasis.htm",
    },
    "cdc_pid": {
        "title": "CDC STI Treatment Guidelines: Pelvic inflammatory disease",
        "url": "https://www.cdc.gov/std/treatment-guidelines/pid.htm",
    },
    "cdc_hemophilia": {
        "title": "CDC: Hemophilia treatment overview",
        "url": "https://www.cdc.gov/hemophilia/treatment/index.html",
    },
    "cdc_sepsis": {
        "title": "CDC: About sepsis",
        "url": "https://www.cdc.gov/sepsis/about/index.html",
    },
    "heatstroke_position": {
        "title": "National Athletic Trainers' Association position statement: exertional heat illnesses",
        "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC164365/",
    },
    "nice_sah": {
        "title": "NICE NG228: Subarachnoid haemorrhage caused by a ruptured aneurysm",
        "url": "https://www.nice.org.uk/guidance/ng228/chapter/Recommendations",
    },
}

CLINICAL_REVIEW: dict[str, dict[str, Any]] = {
    "MED-008": {
        "disposition": "coherente_con_precauciones",
        "confidence": "moderada_alta",
        "assessment": (
            "La placa anular expansiva mayor de 5 cm tras exposición posible a garrapata es compatible con "
            "eritema migrans; la ausencia de garrapata observada no lo excluye. Amoxicilina es una opción "
            "recomendada por CDC para enfermedad de Lyme temprana localizada. La fiebre de 40,1 °C es "
            "marcadamente alta y exige valoración urgente de gravedad y diagnósticos alternativos; no asumir "
            "que todo el cuadro queda explicado por Lyme."
        ),
        "actions": [
            "Mantener el diagnóstico fuente como probable, no como confirmación etiológica absoluta.",
            "Conservar la anafilaxia a tetraciclinas; verificar alergias a beta-lactámicos antes de cualquier uso de amoxicilina.",
            "En eritema migrans típico el diagnóstico es clínico y la serología inicial puede ser negativa; reconsiderar pruebas si la presentación es atípica.",
            "No añadir dosis al caso como prescripción individual; la referencia CDC describe pautas generales.",
        ],
        "source_ids": ["cdc_lyme"],
    },
    "MED-009": {
        "disposition": "compatible_requiere_confirmacion",
        "confidence": "moderada",
        "assessment": (
            "La pápula perlada rosada con borde sobreelevado y telangiectasias es muy sugestiva de carcinoma "
            "basocelular. La ficha no incluye histopatología; por tanto, no es diagnóstico confirmado. El "
            "párpado es una localización funcionalmente crítica y requiere valoración dermatológica y "
            "oftalmológica/oculoplástica, con confirmación histológica y planificación terapéutica."
        ),
        "actions": [
            "Mantener carcinoma basocelular como diagnóstico presuntivo, pendiente de biopsia.",
            "Añadir carcinoma sebáceo palpebral y chalazión persistente como alternativas clínicas pertinentes, sin presentarlas como más probables.",
            "No recomendar observación rutinaria ni destruir/tratar la lesión sin diagnóstico histológico y valoración especializada.",
        ],
        "source_ids": ["aad_bcc"],
    },
    "PED-007": {
        "disposition": "coherente_con_precauciones",
        "confidence": "moderada_alta",
        "assessment": (
            "La edad, cojera, dolor de cadera referido a rodilla y aplanamiento radiográfico de la cabeza "
            "femoral son compatibles con enfermedad de Legg-Calve-Perthes. La ficha ya contiene radiografía; "
            "la caracterización y el manejo dependen de extensión, edad y evolución."
        ),
        "actions": [
            "Mantener Legg-Calve-Perthes como diagnóstico más probable y añadir valoración por ortopedia pediátrica.",
            "Conservar artritis séptica como diagnóstico que no se debe pasar por alto: estar afebril no la excluye si aparecen dolor intenso, incapacidad para apoyar o mal estado general.",
            "No inventar estadificación radiológica ni tratamiento sin descripción de proyecciones/etapa.",
        ],
        "source_ids": ["aaos_perthes"],
    },
    "PED-010": {
        "disposition": "coherente_con_precauciones",
        "confidence": "moderada_alta",
        "assessment": (
            "La combinación de displasia fibrosa, manchas café con leche y desarrollo mamario precoz es "
            "altamente compatible con síndrome de McCune-Albright. El enunciado fuente contiene una "
            "descripción contradictoria de la función tiroidea; no permite definir un fenotipo tiroideo "
            "concreto ni justificar un tratamiento."
        ),
        "actions": [
            "Mantener síndrome de McCune-Albright como diagnóstico probable según los hallazgos descritos.",
            "Solicitar evaluación por endocrinología pediátrica y revisar el informe radiológico de la displasia fibrosa.",
            "Aclarar la alteración tiroidea con historia, examen y pruebas de función tiroidea; no asumir hipo ni hipertiroidismo.",
            "Documentar pubertad precoz y planificar seguimiento endocrino y esquelético; el caso no aporta resultados suficientes para indicar tratamiento individual.",
        ],
        "source_ids": ["medlineplus_mccune_albright"],
    },
    "GOB-003": {
        "disposition": "compatible_requiere_confirmacion",
        "confidence": "moderada",
        "assessment": (
            "El shock hemorrágico posparto y la incapacidad de lactar hacen plausible el infarto hipofisario "
            "posparto (síndrome de Sheehan), que coincide con la respuesta fuente. La imposibilidad de lactar "
            "a la mañana siguiente por sí sola no confirma hipopituitarismo; el evento de atonía/hemorragia "
            "requiere manejo obstétrico urgente independientemente de esa hipótesis."
        ),
        "actions": [
            "Mantener Sheehan como explicación probable de examen, no como diagnóstico endocrinológico confirmado.",
            "Priorizar documentación y manejo de hemorragia posparto; si persisten síntomas o se sospecha déficit hipofisario, solicitar evaluación endocrina urgente.",
            "Valorar ejes hipofisarios, incluido cortisol, con interpretación especializada; no iniciar sustitución hormonal a partir de esta ficha aislada.",
        ],
        "source_ids": ["sheehan_statpearls"],
    },
    "GOB-004": {
        "disposition": "coherente_con_alerta_de_pid",
        "confidence": "moderada_alta",
        "assessment": (
            "Flujo espumoso amarillo-verdoso, pH elevado y cérvix en fresa apoyan tricomoniasis. Sin embargo, "
            "dolor pélvico y dolor a la movilización cervical obligan a evaluar enfermedad pélvica "
            "inflamatoria (EPI); no debe cerrarse como vaginitis aislada."
        ),
        "actions": [
            "Mantener tricomoniasis como diagnóstico fuente y confirmar con NAAT cuando esté disponible.",
            "Evaluar EPI con umbral bajo por dolor pélvico y dolor a la movilización cervical; valorar embarazo y diagnósticos alternativos.",
            "La guía CDC para mujeres recomienda metronidazol oral 500 mg dos veces al día durante 7 días; además, manejo de parejas sexuales, abstinencia hasta completar tratamiento y resolución de síntomas, pruebas de otras ITS y repetición de prueba aproximadamente a los 3 meses. Es información educativa, no receta individual.",
        ],
        "source_ids": ["cdc_trich", "cdc_pid"],
    },
    "CIR-005": {
        "disposition": "compatible_requiere_confirmacion",
        "confidence": "moderada",
        "assessment": (
            "Sangrado con plaquetas, tiempo de protrombina e INR normales y TTPa prolongado es compatible "
            "con deficiencia de factor de la vía intrínseca; la historia familiar favorece hemofilia "
            "hereditaria. El TTPa prolongado aislado no distingue hemofilia A de hemofilia B, enfermedad "
            "de von Willebrand u otras causas."
        ),
        "actions": [
            "Mantener hemofilia A como respuesta fuente probable, no confirmada sin actividad de factor VIII.",
            "Añadir valoración hematológica urgente, repetición/confirmación de coagulación, estudio de mezcla y actividad de factores VIII y IX; considerar estudio de von Willebrand.",
            "La hemorragia quirúrgica activa requiere control hemostático especializado; no inferir dosis de factor ni transfusiones adicionales en este JSON.",
        ],
        "source_ids": ["cdc_hemophilia"],
    },
    "CIR-006": {
        "disposition": "compatible_urgente_requiere_confirmacion",
        "confidence": "moderada",
        "assessment": (
            "Fiebre, taquicardia, taquipnea, hipoxemia, confusión y crepitantes basales en el quinto día "
            "posoperatorio son preocupantes por infección respiratoria con posible sepsis y disfunción "
            "orgánica. El foco pulmonar es probable, pero no está confirmado por imagen o microbiología; "
            "también hay que valorar embolia pulmonar y otras causas de hipoxemia/delirio."
        ),
        "actions": [
            "Mantener sospecha de sepsis posoperatoria como diagnóstico de trabajo y dejar explícito que no está confirmada microbiológicamente.",
            "Indicar evaluación y tratamiento hospitalarios inmediatos; investigar foco con imagen torácica, cultivos y lactato según protocolo local sin retrasar antimicrobianos si la sospecha de sepsis es alta.",
            "Añadir embolia pulmonar como diferencial grave posoperatorio; elegir pruebas según probabilidad clínica.",
        ],
        "source_ids": ["cdc_sepsis"],
    },
    "EME-001": {
        "disposition": "coherente_urgencia_critica",
        "confidence": "moderada_alta",
        "assessment": (
            "Temperatura central de 41,1 °C y alteración neurológica después de trabajo físico al aire libre "
            "son altamente compatibles con golpe de calor por esfuerzo. La diaforesis no lo descarta. "
            "Haloperidol hace importante considerar síndrome neuroléptico maligno; anestesia meses antes "
            "no apoya hipertermia maligna perioperatoria actual."
        ),
        "actions": [
            "Tratarlo como emergencia vital: iniciar enfriamiento activo inmediato y traslado/atención de emergencia; no retrasar el enfriamiento por estudios.",
            "Evaluar daño renal, muscular, hepático, electrolítico y de coagulación; explorar síndrome neuroléptico maligno por la medicación.",
            "No usar antipiréticos como sustituto del enfriamiento en hipertermia por golpe de calor.",
        ],
        "source_ids": ["heatstroke_position"],
    },
    "EME-002": {
        "disposition": "compatible_urgencia_critica_requiere_confirmacion",
        "confidence": "moderada_alta",
        "assessment": (
            "Cefalea explosiva, vómitos, deterioro de conciencia y rigidez de nuca son altamente "
            "preocupantes por hemorragia subaracnoidea, pero la fuente no aporta neuroimagen ni LCR: "
            "la respuesta de MedQA no equivale a confirmación."
        ),
        "actions": [
            "Tratar como emergencia neurológica: evaluación hospitalaria inmediata y TC craneal sin contraste urgente.",
            "Si la TC no confirma hemorragia y persiste la sospecha, completar investigación (por ejemplo, punción lumbar o angio-TC) según tiempo de inicio, hallazgos y protocolo/localidad; consultar neurología/neurocirugía.",
            "Mantener meningitis/meningoencefalitis y otras causas de cefalea en trueno en el diagnóstico diferencial.",
        ],
        "source_ids": ["nice_sah"],
    },
}

CLINICAL_OVERRIDES: dict[str, dict[str, Any]] = {
    "MED-008": {
        "clinical_differentials": [
            {"name": "Celulitis bacteriana", "must_not_miss": False},
            {"name": "Reacción local a picadura", "must_not_miss": False},
            {"name": "Otras infecciones transmitidas por garrapatas", "must_not_miss": True},
        ],
        "recommended_tests": ["valoracion_clinica_urgente_por_fiebre_alta"],
        "optional_tests": ["ninguna_serologia_si_eritema_migrans_tipico", "serologia_si_presentacion_atipica"],
        "treatment_reference": {
            "summary": (
                "CDC incluye amoxicilina como opción general para eritema migrans; la fuente MedQA marca "
                "amoxicilina (B). No es una prescripción individual: valorar fiebre muy alta, alergias a "
                "beta-lactámicos, embarazo, diseminación y diagnósticos alternativos."
            ),
            "key_actions": [
                "No retrasar valoración urgente de fiebre de 40,1 °C.",
                "Confirmar antecedentes alérgicos antes de cualquier antibiótico.",
                "Usar guías locales actualizadas para pauta y duración.",
            ],
        },
    },
    "MED-009": {
        "clinical_differentials": [
            {"name": "Carcinoma escamocelular", "must_not_miss": True},
            {"name": "Carcinoma sebáceo palpebral", "must_not_miss": True},
            {"name": "Queratoacantoma", "must_not_miss": False},
            {"name": "Chalazión persistente", "must_not_miss": False},
        ],
        "recommended_tests": ["biopsia_o_confirmacion_histopatologica"],
        "optional_tests": ["valoracion_dermatologia_y_oftalmologia_oculoplastica"],
        "treatment_reference": {
            "summary": (
                "No hay confirmación histológica ni tratamiento individual en la fuente. Por la localización "
                "palpebral, requiere diagnóstico tisular y planificación por especialistas antes de tratar."
            ),
            "key_actions": [
                "No retrasar la valoración especializada de una lesión palpebral que crece.",
                "Evitar tratamiento destructivo sin confirmación diagnóstica.",
            ],
        },
    },
    "PED-007": {
        "clinical_differentials": [
            {"name": "Artritis séptica", "must_not_miss": True},
            {"name": "Epifisiólisis de la cabeza femoral", "must_not_miss": True},
            {"name": "Osteomielitis", "must_not_miss": True},
            {"name": "Artritis idiopática juvenil", "must_not_miss": False},
        ],
        "recommended_tests": ["valoracion_ortopedia_pediatrica", "revisar_radiografias_de_cadera"],
        "optional_tests": ["resonancia_si_diagnostico_temprano_incierto"],
        "treatment_reference": {
            "summary": (
                "La radiografía y la edad apoyan Legg-Calve-Perthes. El manejo depende de extensión y "
                "evolución, por lo que debe decidirlo ortopedia pediátrica; la ficha no prescribe tratamiento."
            ),
            "key_actions": [
                "Valorar por ortopedia pediátrica.",
                "Reevaluar con urgencia si aparece fiebre, dolor intenso o incapacidad para apoyar.",
            ],
        },
    },
    "PED-010": {
        "clinical_differentials": [
            {"name": "Neurofibromatosis tipo 1", "must_not_miss": False},
            {"name": "Síndrome de Peutz-Jeghers", "must_not_miss": False},
            {"name": "Displasia fibrosa ósea no sindrómica", "must_not_miss": False},
            {"name": "Otras causas de pubertad precoz periférica", "must_not_miss": True},
        ],
        "recommended_tests": [
            "valoracion_endocrinologia_pediatrica",
            "funcion_tiroidea_para_aclarar_enunciado_fuente",
            "revisar_imagenes_y_extension_de_displasia_fibrosa",
        ],
        "optional_tests": [
            "evaluacion_endocrina_de_pubertad_precoz",
            "seguimiento_esqueletico_segun_especialista",
        ],
        "treatment_reference": {
            "summary": (
                "Los hallazgos descritos apoyan síndrome de McCune-Albright, pero el texto fuente es ambiguo "
                "sobre la función tiroidea y no aporta resultados hormonales completos. No se establece "
                "tratamiento individual; requiere evaluación endocrina y esquelética pediátrica."
            ),
            "key_actions": [
                "Aclarar y confirmar la función tiroidea; no asumir que la paciente tiene simultáneamente hipotiroidismo e hipertiroidismo.",
                "Coordinar seguimiento por endocrinología pediátrica y ortopedia según extensión ósea y manifestaciones.",
            ],
        },
    },
    "GOB-003": {
        "clinical_differentials": [
            {"name": "Hemorragia posparto por atonía uterina", "must_not_miss": True},
            {"name": "Hipopituitarismo posparto (síndrome de Sheehan)", "must_not_miss": True},
            {"name": "Retención de restos placentarios", "must_not_miss": True},
            {"name": "Hipofisitis posparto", "must_not_miss": False},
        ],
        "recommended_tests": ["evaluar_y_documentar_hemorragia_posparto"],
        "optional_tests": ["eje_hipofisario_si_persisten_sintomas"],
        "treatment_reference": {
            "summary": (
                "La fuente plantea infarto hipofisario tras shock hemorrágico, pero no proporciona un plan "
                "terapéutico. La hemorragia posparto es la prioridad; sospecha de déficit hipofisario requiere "
                "evaluación endocrina urgente y tratamiento especializado."
            ),
            "key_actions": [
                "Priorizar estabilización y control obstétrico de la hemorragia.",
                "No inferir ni iniciar reemplazo hormonal sin evaluación urgente del eje, incluido cortisol.",
            ],
        },
    },
    "GOB-004": {
        "clinical_differentials": [
            {"name": "Enfermedad pélvica inflamatoria", "must_not_miss": True},
            {"name": "Cervicitis por gonorrea o clamidia", "must_not_miss": True},
            {"name": "Vaginosis bacteriana", "must_not_miss": False},
            {"name": "Candidiasis vulvovaginal", "must_not_miss": False},
        ],
        "recommended_tests": [
            "naat_trichomonas",
            "naat_gonorrea_y_clamidia",
            "evaluar_criterios_de_enfermedad_pelvica_inflamatoria",
        ],
        "optional_tests": ["prueba_de_embarazo", "pruebas_de_otras_its"],
        "treatment_reference": {
            "summary": (
                "CDC recomienda para tricomoniasis en mujeres metronidazol oral 500 mg dos veces al día "
                "durante 7 días y manejo de parejas; si se sospecha EPI, necesita evaluación y tratamiento "
                "presuntivo por un profesional, ya que el esquema para vaginitis no cubre por sí solo toda EPI."
            ),
            "key_actions": [
                "No omitir evaluación de EPI ante dolor pélvico y dolor a la movilización cervical.",
                "Tratar simultáneamente a las parejas sexuales y evitar relaciones hasta completar tratamiento y resolver síntomas.",
                "Ofrecer pruebas para otras ITS y repetir prueba de tricomoniasis aproximadamente a los 3 meses.",
            ],
        },
    },
    "CIR-005": {
        "clinical_differentials": [
            {"name": "Hemofilia B", "must_not_miss": False},
            {"name": "Enfermedad de von Willebrand", "must_not_miss": False},
            {"name": "Inhibidor adquirido de factor VIII", "must_not_miss": True},
            {"name": "Coagulopatía perioperatoria adquirida", "must_not_miss": True},
        ],
        "recommended_tests": [
            "actividad_de_factor_viii_y_factor_ix",
            "estudio_de_mezcla_del_ttp",
            "valoracion_hematologia_urgente",
        ],
        "optional_tests": ["antigeno_y_actividad_del_factor_de_von_willebrand"],
        "treatment_reference": {
            "summary": (
                "El sangrado activo con posible hemofilia requiere control hemostático urgente con hematología. "
                "El producto depende de factor deficiente, inhibidores y situación clínica; la fuente no "
                "permite elegir producto ni dosis."
            ),
            "key_actions": [
                "No retrasar consulta de hematología ante sangrado quirúrgico persistente.",
                "Confirmar actividad de factor VIII/IX y descartar inhibidor antes de etiquetar hemofilia A.",
            ],
        },
    },
    "CIR-006": {
        "clinical_differentials": [
            {"name": "Neumonía posoperatoria", "must_not_miss": True},
            {"name": "Embolia pulmonar posoperatoria", "must_not_miss": True},
            {"name": "Atelectasia u otra causa de hipoxemia", "must_not_miss": False},
            {"name": "Delirio posoperatorio por causa metabólica o farmacológica", "must_not_miss": False},
        ],
        "recommended_tests": [
            "evaluacion_hospitalaria_inmediata",
            "radiografia_o_imagen_de_torax",
            "cultivos_y_lactato_segun_protocolo_sin_retrasar_tratamiento",
        ],
        "optional_tests": ["evaluacion_de_embolia_pulmonar_segun_probabilidad"],
        "treatment_reference": {
            "summary": (
                "Posible sepsis posoperatoria: requiere evaluación y tratamiento hospitalarios inmediatos, "
                "búsqueda del foco y soporte de órganos. La fuente no demuestra germen ni prescribe un "
                "antibiótico específico."
            ),
            "key_actions": [
                "No retrasar tratamiento de sepsis probable para completar pruebas no esenciales.",
                "Investigar foco pulmonar y valorar diagnósticos alternativos graves, especialmente embolia pulmonar.",
            ],
        },
    },
    "EME-001": {
        "clinical_differentials": [
            {"name": "Síndrome neuroléptico maligno", "must_not_miss": True},
            {"name": "Tormenta tiroidea", "must_not_miss": True},
            {"name": "Estado epiléptico", "must_not_miss": True},
            {"name": "Hipertermia maligna perioperatoria", "must_not_miss": False},
        ],
        "recommended_tests": [
            "enfriamiento_activo_inmediato",
            "creatina_quinasa_funcion_renal_electrolitos",
            "funcion_hepatica_y_coagulacion",
        ],
        "optional_tests": ["ecg_glucosa_y_evaluacion_de_sindrome_neuroleptico_maligno"],
        "treatment_reference": {
            "summary": (
                "Golpe de calor por esfuerzo con alteración neurológica es una emergencia vital. El enfriamiento "
                "activo debe comenzar de inmediato; la fuente no autoriza una pauta farmacológica individual."
            ),
            "key_actions": [
                "Iniciar enfriamiento activo rápido y activar atención de emergencia.",
                "No usar antipiréticos como sustituto del enfriamiento.",
                "Vigilar rabdomiólisis, lesión renal/hepática, alteraciones electrolíticas y coagulopatía.",
            ],
        },
    },
    "EME-002": {
        "clinical_differentials": [
            {"name": "Meningitis o meningoencefalitis", "must_not_miss": True},
            {"name": "Hemorragia intracerebral", "must_not_miss": True},
            {"name": "Trombosis venosa cerebral", "must_not_miss": True},
            {"name": "Crisis epiléptica", "must_not_miss": False},
        ],
        "recommended_tests": ["tc_craneal_sin_contraste_urgente"],
        "optional_tests": ["puncion_lumbar_o_angio_tc_si_persiste_sospecha_tras_tc"],
        "treatment_reference": {
            "summary": (
                "Sospecha de hemorragia subaracnoidea: evaluación hospitalaria inmediata y neuroimagen urgente. "
                "Si TC inicial no confirma y persiste sospecha, completar estudio según tiempo de inicio y "
                "protocolo especializado; la fuente no contiene imagen confirmatoria."
            ),
            "key_actions": [
                "No demorar TC craneal y valoración neurológica/neuroquirúrgica urgente.",
                "No declarar hemorragia confirmada solo por la clave de respuesta MedQA.",
            ],
        },
    },
}


def _load_selected_sources(path: Path) -> dict[str, dict[str, Any]]:
    wanted_ids = {case["candidate_id"] for case in SELECTED_CASES}
    selected: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            candidate_id = record.get("candidate_id")
            if candidate_id not in wanted_ids:
                continue

            existing = selected.get(candidate_id)
            if existing is None or len(record.get("options", [])) > len(existing.get("options", [])):
                selected[candidate_id] = record
            elif len(record.get("options", [])) == len(existing.get("options", [])):
                for key in ("question", "options", "answer", "answer_text"):
                    if record.get(key) != existing.get(key):
                        raise ValueError(f"Variantes incompatibles para el registro fuente {candidate_id}.")

    missing = wanted_ids - selected.keys()
    if missing:
        raise FileNotFoundError(f"No se encontraron candidatos fuente seleccionados: {sorted(missing)}")
    return selected


def curate_ai_reviewed_case(case: dict[str, Any], clinical_review: dict[str, Any]) -> dict[str, Any]:
    if not clinical_review.get("assessment") or not clinical_review.get("disposition"):
        raise ValueError(f"Falta una evaluación clínica asistida para {case.get('case_id')}.")

    curated_case = deepcopy(case)
    curated_case["status"] = "curado"
    curated_case["provenance"]["curated_by"] = "curacion_asistida_por_ia"
    curated_case["provenance"]["curated_at"] = date.today().isoformat()
    validate_case_document(curated_case)
    return curated_case


def _write_ai_curated_cases(case_index: list[dict[str, Any]]) -> None:
    CURATED_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CURATION_SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    index_by_id = {item["case_id"]: item for item in case_index}
    expected_ids = {item["case_id"] for item in SELECTED_CASES}
    if set(index_by_id) != expected_ids:
        raise ValueError("El lote de revisión no coincide con los diez casos seleccionados.")

    curated_records: list[dict[str, Any]] = []
    for case_id in sorted(expected_ids, key=lambda value: int(value.rsplit("-", 1)[1])):
        source_path = OUTPUT_DIR / f"{case_id}.json"
        case = json.loads(source_path.read_text(encoding="utf-8"))
        review = CLINICAL_REVIEW[case_id]
        curated_case = curate_ai_reviewed_case(case, review)
        destination = CURATED_OUTPUT_DIR / source_path.name
        destination.write_text(
            json.dumps(curated_case, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        curated_records.append(
            {
                "case_id": case_id,
                "status": "curado",
                "curated_by": curated_case["provenance"]["curated_by"],
                "disposition": review["disposition"],
                "confidence": review["confidence"],
                "review": review["assessment"],
                "source_review": "clinical_coherence_review.json",
            }
        )

    summary = {
        "dataset": "MedQA",
        "status": "curado_con_revision_asistida_por_ia",
        "method": "curacion_asistida_por_ia",
        "curated_count": len(curated_records),
        "curated_at": date.today().isoformat(),
        "source_dir": "data/cases/validated_second_pass",
        "curated_dir": "data/cases/curated",
        "cases": curated_records,
    }
    CURATION_SUMMARY_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _invalidate_legacy_curations() -> None:
    REJECTED_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    review_records: list[dict[str, Any]] = []
    for case_id, reason in LEGACY_CASES_TO_REJECT.items():
        filename = f"{case_id}.json"
        source_path = next(
            (
                directory / filename
                for directory in (VALIDATED_OUTPUT_DIR, CURATED_OUTPUT_DIR, REJECTED_OUTPUT_DIR)
                if (directory / filename).exists()
            ),
            None,
        )
        if source_path is None:
            raise FileNotFoundError(f"No se encontró el caso legado {case_id} para auditarlo.")

        case = json.loads(source_path.read_text(encoding="utf-8"))
        rejected_case = deepcopy(case)
        rejected_case["status"] = "rechazado"
        rejected_case["provenance"]["curated_by"] = None
        rejected_case["provenance"]["curated_at"] = None
        rejected_case["provenance"]["rejection_reason"] = reason
        validate_case_document(rejected_case)
        (REJECTED_OUTPUT_DIR / filename).write_text(
            json.dumps(rejected_case, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        for directory in (VALIDATED_OUTPUT_DIR, CURATED_OUTPUT_DIR):
            stale_path = directory / filename
            if stale_path.exists():
                stale_path.unlink()

        review_path = SELECTION_REVIEW_PATH.parent / filename
        if case_id not in INVALIDATED_LEGACY_CURATIONS and review_path.exists():
            previous_review = json.loads(review_path.read_text(encoding="utf-8"))
            previous_review["accepted"] = False
            previous_review["decision"] = "rechazado_por_reglas_automatizadas"
            previous_review["reason"] = reason
            previous_review["reviewer"] = "auditoria_automatica_de_datos"
            review_path.write_text(
                json.dumps(previous_review, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            review_records.append(previous_review)
            continue

        review_record = {
            "case_id": case_id,
            "reviewed_at": date.today().isoformat(),
            "accepted": False,
            "decision": (
                "curacion_anterior_invalidada"
                if case_id in INVALIDATED_LEGACY_CURATIONS
                else "rechazado_por_reglas_automatizadas"
            ),
            "reason": reason,
            "reviewer": "auditoria_automatica_de_datos",
        }
        review_path.write_text(
            json.dumps(review_record, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        review_records.append(review_record)

    invalidated_ids = sorted(INVALIDATED_LEGACY_CURATIONS)
    rejected_ids = sorted(set(LEGACY_CASES_TO_REJECT) - INVALIDATED_LEGACY_CURATIONS)
    LEGACY_CURATION_SUMMARY_PATH.write_text(
        json.dumps(
            {
                "dataset": "MedQA",
                "status": "lote_anterior_rechazado_o_curacion_invalidada",
                "reviewed_count": len(LEGACY_CASES_TO_REJECT),
                "accepted_count": 0,
                "rejected_count": len(LEGACY_CASES_TO_REJECT),
                "invalidated_count": len(invalidated_ids),
                "accepted_case_ids": [],
                "rejected_case_ids": sorted(LEGACY_CASES_TO_REJECT),
                "invalidated_case_ids": invalidated_ids,
                "reason": (
                    "Se retiraron seis curaciones heurísticas por datos demográficos o especialidades sin "
                    "respaldo. Cuatro entradas adicionales son resúmenes de estudios, no casos de pacientes. "
                    "Las diez se conservan en rechazados y no se mezclan con el lote curado actual."
                ),
                "generated_at": date.today().isoformat(),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    index_path = next(
        (
            path
            for path in (LEGACY_SELECTION_INDEX_PATH, LEGACY_SELECTION_AUDIT_PATH)
            if path.exists()
        ),
        None,
    )
    if index_path is not None:
        legacy_index = json.loads(index_path.read_text(encoding="utf-8"))
        legacy_index["status"] = "rechazado"
        legacy_index["decision"] = "seleccion_anterior_retirada_por_auditoria"
        legacy_index["rejected_case_ids"] = sorted(LEGACY_CASES_TO_REJECT)
        legacy_index["invalidated_case_ids"] = invalidated_ids
        legacy_index["accepted_count"] = 0
        legacy_index["rejected_count"] = len(LEGACY_CASES_TO_REJECT)
        LEGACY_SELECTION_AUDIT_PATH.write_text(
            json.dumps(legacy_index, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        if index_path != LEGACY_SELECTION_AUDIT_PATH:
            index_path.unlink()


def build_reviewed_cases() -> dict[str, Any]:
    sources = _load_selected_sources(CANDIDATES_PATH)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    FINAL_SELECTION_PATH.parent.mkdir(parents=True, exist_ok=True)
    SELECTION_REVIEW_PATH.parent.mkdir(parents=True, exist_ok=True)

    case_index: list[dict[str, Any]] = []
    for position, selection in enumerate(SELECTED_CASES, start=1):
        candidate = dict(sources[selection["candidate_id"]])
        candidate.update({key: value for key, value in selection.items() if key != "rationale"})
        candidate.update(CLINICAL_OVERRIDES[selection["case_id"]])
        translation = SPANISH_SOURCE_TEXT[selection["candidate_id"]]
        if len(translation["options"]) != len(candidate["options"]):
            raise ValueError(f"La traducción de opciones no coincide con la fuente para {selection['case_id']}.")
        candidate["question_translation_es"] = translation["question"]
        candidate["options_translation_es"] = translation["options"]
        case = _build_case(candidate, position)
        validate_case_document(case)
        output_path = OUTPUT_DIR / f"{case['case_id']}.json"
        output_path.write_text(json.dumps(case, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        case_index.append(
            {
                "case_id": case["case_id"],
                "candidate_id": selection["candidate_id"],
                "specialty": case["specialty"],
                "source_answer": candidate["answer"],
                "source_answer_text": candidate["answer_text"],
                "clinical_diagnosis": case["protected"]["diagnosis"]["name"],
                "rationale": selection["rationale"],
                "clinical_review": CLINICAL_REVIEW[selection["case_id"]],
                "schema_valid": True,
            }
        )

    selected_ids = [case["case_id"] for case in case_index]
    suffixes = [int(case_id.rsplit("-", 1)[1]) for case_id in selected_ids]
    if len(set(selected_ids)) != len(selected_ids) or sorted(suffixes) != list(range(1, len(case_index) + 1)):
        raise ValueError("Los IDs del lote deben ser únicos y numerados consecutivamente del 001 al total.")

    case_index.sort(key=lambda case: int(case["case_id"].rsplit("-", 1)[1]))
    _write_ai_curated_cases(case_index)
    _invalidate_legacy_curations()
    specialty_counts = dict(Counter(case["specialty"] for case in case_index))
    review_counts = dict(Counter(case["clinical_review"]["disposition"] for case in case_index))
    manifest = {
        "dataset": "MedQA",
        "status": "curado_con_revision_asistida_por_ia",
        "selection_criteria": [
            "10 preguntas fuente únicas; selección entre variantes con opciones y clave completas",
            "edad y sexo derivados del texto original, sin valores por defecto",
            "especialidad asignada según el escenario clínico, no palabras incidentales",
            "pregunta, opciones y respuesta originales preservadas en evaluación protegida",
            "hallazgos y respuestas cotejados con la fuente reparada; pruebas y tratamiento contrastados con guías identificadas",
            "tratamiento educativo sujeto a evaluación clínica individual; sin convertirlo en prescripción",
            "figuras y datos no disponibles señalados como limitación, no reconstruidos",
        ],
        "selected_case_ids": [case["case_id"] for case in case_index],
        "specialty_counts": specialty_counts,
        "validation": {
            "schema_ok": True,
            "unique_source_items": len({case["candidate_id"] for case in case_index}),
            "total_validated": len(case_index),
            "source_dir": "data/cases/validated_second_pass",
        },
        "clinical_review": (
            "Lote curado mediante revisión asistida por IA y fuentes identificadas. Cada caso conserva "
            "sus incertidumbres, alertas y necesidades de confirmación. PED-010 se sustituyó por una fuente "
            "pediátrica completa sin imagen faltante."
        ),
        "clinical_review_counts": review_counts,
    }
    FINAL_SELECTION_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    SELECTION_REVIEW_PATH.write_text(
        json.dumps(
            {
                "dataset": "MedQA",
                "status": "ai_assisted_curation_completed",
                "selected_count": len(case_index),
                "specialty_counts": specialty_counts,
                "clinical_review_counts": review_counts,
                "clinical_sources": CLINICAL_SOURCES,
                "cases": case_index,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    CLINICAL_REVIEW_PATH.write_text(
        json.dumps(
            {
                "review_type": "AI-assisted curation and content/source-fidelity review",
                "review_status": "ai_assisted_curation_completed",
                "audit_round": 2,
                "reviewed_at": date.today().isoformat(),
                "method": (
                    "Second-pass audit: compare each generated case with the repaired MedQA source, "
                    "answer, and options; verify clinical-summary fidelity, Spanish adaptation, differential "
                    "risk links, diagnostic fit, missing evidence, red flags, tests, and general treatment "
                    "recommendations against the linked references. Original English source text is retained."
                ),
                "educational_use": "curated_for_educational_simulation",
                "case_status_counts": review_counts,
                "clinical_sources": CLINICAL_SOURCES,
                "cases": case_index,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "written": len(case_index),
        "curated": len(case_index),
        "case_ids": [case["case_id"] for case in case_index],
        "specialty_counts": specialty_counts,
        "schema_valid": True,
        "curation_method": "curacion_asistida_por_ia",
    }


if __name__ == "__main__":
    print(json.dumps(build_reviewed_cases(), ensure_ascii=False, indent=2))
