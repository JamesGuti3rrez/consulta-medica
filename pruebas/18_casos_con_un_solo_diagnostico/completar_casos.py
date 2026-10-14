"""Complementos del equipo para que cada caso llegue a un solo diagnóstico (decisión 0002).

Edita el archivo de revisión data/cases/reviews/medqa_lote_curacion.json, del que el comando `curation`
genera los casos. Se aplica de a un caso, para dejar un commit por caso:

    backend\\.venv\\Scripts\\python.exe pruebas\\18_casos_con_un_solo_diagnostico\\completar_casos.py CIR-005

Cada dato agregado lleva "complemento" (fuente clínica registrada y motivo). Los textos son cualitativos,
sin cifras nuevas (regla R13). Volver a aplicar un caso ya completado no cambia nada.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REVIEW = ROOT / "data" / "cases" / "reviews" / "medqa_lote_curacion.json"

NEW_SOURCES = {
    "medlineplus_atelectasis": {
        "title": "MedlinePlus Medical Encyclopedia: Atelectasis",
        "url": "https://medlineplus.gov/ency/article/000065.htm",
    },
    "medlineplus_thyroid_storm": {
        "title": "MedlinePlus Medical Encyclopedia: Thyroid storm",
        "url": "https://medlineplus.gov/ency/article/000400.htm",
    },
    "medlineplus_eeg": {
        "title": "MedlinePlus Medical Encyclopedia: EEG",
        "url": "https://medlineplus.gov/ency/article/003931.htm",
    },
    "medlineplus_postpartum_depression": {
        "title": "MedlinePlus Medical Encyclopedia: Postpartum depression",
        "url": "https://medlineplus.gov/ency/article/007215.htm",
    },
    "cdc_ehrlichiosis": {
        "title": "CDC: Clinical signs and symptoms of ehrlichiosis",
        "url": "https://www.cdc.gov/ehrlichiosis/hcp/clinical-signs/index.html",
    },
}


def lab(key, label, text, requires, fuente, motivo, category="laboratorio", owner="laboratorio"):
    return {
        "key": key, "category": category, "label": label, "text": text,
        "owner": owner, "requires": requires,
        "complemento": {"fuente": fuente, "motivo": motivo},
    }


def key_question(topic, evidence, weight=3, critical=False, error="razonamiento_clinico"):
    return {"topic": topic, "evidence": evidence, "weight": weight, "critical": critical, "error_if_missing": error}


# Por caso: datos nuevos a petición, descartes, preguntas clave nuevas, fuentes usadas y, si hace falta,
# la lista corregida de diferenciales (en clinical_overrides).
CHANGES = {
    "CIR-005": {
        "on_request": [
            lab("factores_coagulacion", "Dosaje de factores de coagulación",
                "Actividad del factor VIII disminuida; actividad del factor IX normal.",
                ["factores_coagulacion"], "cdc_hemophilia",
                "El TTPa prolongado no distingue hemofilia A de B; solo el dosaje de factores lo hace."),
        ],
        "discard": {"Hemofilia B": ["factores_coagulacion"]},
        "key_questions": [key_question("Dosaje de factores: factor VIII disminuido y factor IX normal",
                                       ["factores_coagulacion"], weight=4, critical=True)],
    },
    "CIR-006": {
        "differentials": [
            {"name": "Síndrome de respuesta inflamatoria sistémica no infeccioso", "must_not_miss": False},
            {"name": "Embolia pulmonar posoperatoria", "must_not_miss": True},
            {"name": "Atelectasia u otra causa de hipoxemia", "must_not_miss": False},
            {"name": "Delirio posoperatorio por causa metabólica o farmacológica", "must_not_miss": False},
        ],
        "on_request": [
            lab("radiografia_torax", "Radiografía de tórax",
                "Consolidación en la base pulmonar derecha con broncograma aéreo, compatible con neumonía; "
                "sin colapso lobar ni desplazamiento de cisuras.",
                ["radiografia_torax"], "medlineplus_atelectasis",
                "Muestra el foco infeccioso (neumonía) y distingue la consolidación de una atelectasia.",
                category="imagen", owner="radiologia"),
            lab("hemograma", "Hemograma", "Leucocitosis con neutrofilia.", ["hemograma"], "cdc_sepsis",
                "Apoya un origen infeccioso frente a una respuesta inflamatoria no infecciosa."),
        ],
        "discard": {
            "Síndrome de respuesta inflamatoria sistémica no infeccioso": ["radiografia_torax", "hemograma"],
            "Atelectasia u otra causa de hipoxemia": ["radiografia_torax"],
        },
        "key_questions": [key_question("Radiografía de tórax: consolidación en la base derecha (foco de la sepsis)",
                                       ["radiografia_torax"], weight=4, critical=True)],
    },
    "EME-001": {
        "on_request": [
            lab("funcion_tiroidea", "Función tiroidea", "TSH y tiroxina libre dentro del rango normal.",
                ["funcion_tiroidea"], "medlineplus_thyroid_storm",
                "Toma propranolol por hipertiroidismo: la tormenta tiroidea solo se descarta con la función tiroidea."),
            lab("electroencefalograma", "Electroencefalograma",
                "Sin actividad epileptiforme; enlentecimiento difuso propio de una encefalopatía.",
                ["electroencefalograma"], "medlineplus_eeg",
                "Tiene epilepsia y está obnubilado: el estado epiléptico no convulsivo se descarta con el EEG.",
                category="estudio"),
        ],
        "discard": {
            "Tormenta tiroidea": ["funcion_tiroidea"],
            "Estado epiléptico": ["electroencefalograma"],
        },
        "key_questions": [key_question("Función tiroidea normal pese al antecedente de hipertiroidismo",
                                       ["funcion_tiroidea"])],
    },
    "EME-002": {
        "on_request": [
            lab("tomografia_craneo", "Tomografía de cráneo sin contraste",
                "Sangre en el espacio subaracnoideo de las cisternas basales y los surcos, sin hematoma intraparenquimatoso.",
                ["tomografia"], "nice_sah",
                "La tomografía distingue la hemorragia subaracnoidea de la intracerebral.",
                category="imagen", owner="radiologia"),
        ],
        "discard": {"Hemorragia intracerebral": ["tomografia_craneo"]},
        "key_questions": [key_question("Tomografía de cráneo: sangre subaracnoidea sin hematoma intraparenquimatoso",
                                       ["tomografia_craneo"], weight=5, critical=True)],
    },
    "GOB-003": {
        # El enunciado pregunta por la falla de lactancia: la atonía explica la hemorragia (no compite) y el
        # síndrome de Sheehan es el propio diagnóstico. Se usan las opciones del enunciado original.
        "differentials": [
            {"name": "Retención de restos placentarios", "must_not_miss": True},
            {"name": "Tristeza puerperal", "must_not_miss": False},
            {"name": "Tumor hipofisario", "must_not_miss": False},
            {"name": "Hipofisitis posparto", "must_not_miss": False},
        ],
        "on_request": [
            lab("prolactina", "Prolactina sérica", "Prolactina baja para el puerperio.", ["prolactina"],
                "sheehan_statpearls",
                "La prolactina baja apunta a un daño hipofisario y no a restos placentarios ni a un tumor que la eleve."),
            {
                "key": "estado_de_animo", "category": "sintoma", "label": "Estado de ánimo",
                "text": "Se siente con ánimo para cuidar al bebé y quiere amamantar; niega tristeza, llanto o ansiedad.",
                "owner": "paciente", "requires": ["sintomas_asociados"],
                "complemento": {"fuente": "medlineplus_postpartum_depression",
                                "motivo": "Sin síntomas afectivos, la tristeza puerperal no explica el cuadro."},
            },
            {
                "key": "antecedentes_menstruales", "category": "antecedente", "label": "Antecedentes menstruales",
                "text": "Antes del embarazo tenía reglas regulares; nunca tuvo cefalea persistente ni problemas de la vista.",
                "owner": "paciente", "requires": ["antecedentes_gineco_obstetricos"],
                "complemento": {"fuente": "sheehan_statpearls",
                                "motivo": "Una función hipofisaria normal antes del parto va en contra de un tumor previo."},
            },
        ],
        "discard": {
            "Retención de restos placentarios": ["prolactina"],
            "Tristeza puerperal": ["estado_de_animo"],
            "Tumor hipofisario": ["antecedentes_menstruales", "prolactina"],
        },
        "key_questions": [key_question("Prolactina baja para el puerperio", ["prolactina"], weight=4, critical=True)],
    },
    "MED-008": {
        "on_request": [
            lab("hemograma_bioquimica", "Hemograma y perfil hepático",
                "Leucocitos y plaquetas normales; transaminasas normales.", ["hemograma"], "cdc_ehrlichiosis",
                "Ehrlichiosis y anaplasmosis suelen bajar leucocitos y plaquetas y elevar las transaminasas."),
        ],
        "discard": {"Otras infecciones transmitidas por garrapatas": ["hemograma_bioquimica", "exploracion_fisica"]},
        "key_questions": [key_question("Hemograma y perfil hepático normales", ["hemograma_bioquimica"])],
    },
}


def apply(case_id: str) -> None:
    data = json.loads(REVIEW.read_text(encoding="utf-8"))
    change = CHANGES[case_id]
    distribution = data["distribution"][case_id]
    used = {entry["complemento"]["fuente"] for entry in change["on_request"]}
    for source in sorted(used & NEW_SOURCES.keys()):
        data["clinical_sources"].setdefault(source, NEW_SOURCES[source])
    if "differentials" in change:
        override = data["clinical_overrides"][case_id]
        override["clinical_differentials"] = change["differentials"]
        names = {item["name"] for item in change["differentials"]}
        distribution["discard"] = {name: keys for name, keys in distribution.get("discard", {}).items() if name in names}
    existing = {entry["key"] for entry in distribution["on_request"]}
    distribution["on_request"].extend(entry for entry in change["on_request"] if entry["key"] not in existing)
    distribution.setdefault("discard", {}).update(change["discard"])
    topics = {question["topic"] for question in distribution["key_questions"]}
    distribution["key_questions"].extend(q for q in change["key_questions"] if q["topic"] not in topics)
    REVIEW.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{case_id}: {len(change['on_request'])} datos del equipo, {len(change['discard'])} descartes, "
          f"{len(change['key_questions'])} preguntas clave nuevas"
          + (", diferenciales corregidos" if "differentials" in change else ""))


if __name__ == "__main__":
    for case_id in sys.argv[1:]:
        apply(case_id)
