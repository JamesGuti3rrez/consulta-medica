"""Plantillas descargables desde el panel; no se almacenan documentos subidos en disco."""
from __future__ import annotations

import copy
from io import BytesIO

from server.cases.uploads import COLUMNS

INSTRUCTIONS = [
    ("Formato", "Un caso por fila de Casos. El mismo case_id relaciona las cinco hojas."),
    ("Listas", "Separa sinónimos, acciones, temas y claves con |. No uses fórmulas."),
    ("Identificadores", "Usa MED, PED, GOB, CIR o EME seguido de guion y tres cifras. No sobrescribe IDs existentes."),
    ("Especialidades", "medicina_interna | pediatria | ginecologia_obstetricia | cirugia_general | emergencias"),
    ("Propietarios", "paciente | medico_asistente | laboratorio | radiologia"),
    ("Temas del paciente", "inicio_y_evolucion | caracteristicas_sintoma | sintomas_asociados | antecedentes_personales | antecedentes_familiares | medicacion | alergias | habitos | antecedentes_gineco_obstetricos"),
    ("Temas del médico", "signos_vitales | exploracion_fisica"),
    ("Temas de exámenes", "Nombre del examen en minúsculas con guiones bajos: hemograma, funcion_tiroidea, radiografia_torax, etc."),
    ("Categorías", "sintoma | antecedente | medicacion | signo_vital | anamnesis | examen_fisico | laboratorio | imagen | estudio"),
    ("Referencias", "Evaluacion.evidencias y Diferenciales.evidencias_descartan usan las claves de Evidencias.clave."),
    ("Errores", "negligencia | anamnesis_incompleta | razonamiento_clinico"),
    ("Revisión", "El ejemplo es ficticio. Sustituye su contenido y revisa la información clínica antes de publicar."),
]


def example_case(cases: list[dict]) -> dict:
    # La plantilla procede de un caso remoto actual, sin inventar datos al importar.
    selected = next((case for case in cases if case["case_id"] == "MED-101"), None)
    selected = selected or next((case for case in cases if not case["protected"]["contraindications"]), None)
    if selected is None:
        raise ValueError("Carga primero un caso sin contraindicaciones para usarlo como plantilla.")
    case = copy.deepcopy(selected)
    prefix = case["case_id"].split("-")[0]
    used = {item["case_id"] for item in cases}
    candidate = next((f"{prefix}-{number:03d}" for number in range(101, 1000) if f"{prefix}-{number:03d}" not in used), None)
    if candidate is None:
        raise ValueError("No quedan identificadores disponibles para esta especialidad.")
    old_id = case["case_id"]
    def replace_ids(value):
        if isinstance(value, dict):
            return {key: replace_ids(item) for key, item in value.items()}
        if isinstance(value, list):
            return [replace_ids(item) for item in value]
        if isinstance(value, str) and (value == old_id or value.startswith(old_id + ".")):
            return candidate + value[len(old_id):]
        return value
    case = replace_ids(case)
    case["status"] = "borrador"
    case["source"] = {"dataset": "manual", "item_id": f"docente/{candidate}", "license": "Aportado por el docente para uso educativo", "method": "manual"}
    case["provenance"].update(created_by="Plantilla docente", validated_at=None,
                              curated_by=None, curated_at=None, rejection_reason=None)
    return case


def excel_template(case: dict) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    workbook = Workbook()
    workbook.remove(workbook.active)
    sheets = {name: workbook.create_sheet(name) for name in COLUMNS}
    for name, columns in COLUMNS.items():
        sheets[name].append(columns)
    case_id, public, protected = case["case_id"], case["public"], case["protected"]
    patient = public["patient"]
    sheets["Casos"].append([
        case_id, case["title"], case["specialty"], patient["alias"], patient["age_years"],
        patient["sex"], public["chief_complaint"]["text"], protected["diagnosis"]["name"],
        " | ".join(protected["diagnosis"]["synonyms"]), protected["treatment_reference"]["summary"],
        " | ".join(protected["treatment_reference"]["key_actions"]),
    ])
    short = {item["evidence_id"]: item["evidence_id"].split(".")[-1] for item in case["on_request"]}
    for item in case["on_request"]:
        policy = item["reveal_policy"]
        text = item.get("text") or f"{item.get('value')} {item.get('unit')}"
        sheets["Evidencias"].append([case_id, short[item["evidence_id"]], item["category"],
                                    item["label"], text, policy["owner"], " | ".join(policy["requires"])])
    for item in protected["differentials"]:
        sheets["Diferenciales"].append([case_id, item["name"], item["must_not_miss"],
                                        " | ".join(short[eid] for eid in item["discard_evidence_ids"])])
    for item in protected["evaluation"]["key_questions"]:
        sheets["Evaluacion"].append([case_id, item["topic"], " | ".join(short[eid] for eid in item["evidence_ids"]),
                                     item["weight"], item.get("critical", False), item["error_if_missing"]])
    tests = protected["evaluation"]["tests"]
    sheets["Examenes"].append([case_id, " | ".join(tests["recommended"]),
                               " | ".join(tests["optional"]), " | ".join(tests["unnecessary"])])
    guide = workbook.create_sheet("Instrucciones", 0)
    guide.append(["Campo", "Cómo completarlo"])
    for row in INSTRUCTIONS:
        guide.append(row)
    for sheet in workbook:
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        for cell in sheet[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="087F8C")
        for column in sheet.columns:
            sheet.column_dimensions[column[0].column_letter].width = min(58, max(18, len(str(column[0].value)) + 4))
        # Los textos que empiezan con = se exportan como texto, nunca fórmulas.
        for row in sheet.iter_rows(min_row=2):
            for cell in row:
                if isinstance(cell.value, str):
                    cell.data_type = "s"
    result = BytesIO()
    workbook.save(result)
    return result.getvalue()

