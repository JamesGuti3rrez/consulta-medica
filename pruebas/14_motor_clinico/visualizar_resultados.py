"""Genera un informe HTML con tablas de resultados del motor clínico."""

from __future__ import annotations

import argparse
import html
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"

RESULT_SETS = (
    {
        "key": "curated",
        "title": "Casos curados",
        "filename": "resultados_casos_curados.json",
    },
    {
        "key": "validated",
        "title": "Casos validados",
        "filename": "resultados_casos_validados.json",
    },
    {
        "key": "clinical",
        "title": "Prueba clínica anterior",
        "filename": "resultados_motor_clinico.json",
    },
)

SPECIALTY_LABELS = {
    "cirugia_general": "Cirugía general",
    "emergencias": "Emergencias",
    "ginecologia_obstetricia": "Ginecología y obstetricia",
    "medicina_interna": "Medicina interna",
    "pediatria": "Pediatría",
}

ERROR_LABELS = (
    ("negligencia", "Negligencia"),
    ("anamnesis_incompleta", "Anamnesis incompleta"),
    ("razonamiento_clinico", "Razonamiento clínico"),
)


def _read_result_file(path: Path) -> list[dict[str, Any]] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"No se pudo leer el archivo de resultados {path}: {exc}") from exc
    if not isinstance(data, list) or any(not isinstance(row, dict) for row in data):
        raise RuntimeError(f"El archivo debe contener una lista de resultados JSON: {path}")
    return data


def _clinical_case_metadata() -> dict[str, dict[str, str]]:
    metadata: dict[str, dict[str, str]] = {}
    case_directories = (ROOT / "data" / "cases" / "curated", ROOT / "data" / "cases" / "validated")
    for directory in case_directories:
        for path in sorted(directory.glob("*.json")):
            try:
                case = json.loads(path.read_text(encoding="utf-8-sig"))
            except (OSError, json.JSONDecodeError) as exc:
                raise RuntimeError(f"No se pudieron leer los metadatos del caso {path}: {exc}") from exc
            metadata[case["case_id"]] = {
                "specialty": case.get("specialty", ""),
                "source_dataset": case.get("source", {}).get("dataset", ""),
            }
    return metadata


def _value(row: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in row:
            return row[key]
    return default


def _case_id(row: dict[str, Any]) -> str:
    return str(_value(row, "case_id", "caso", default="—"))


def _evaluation(row: dict[str, Any]) -> dict[str, Any]:
    value = _value(row, "evaluation", "evaluacion", default={})
    return value if isinstance(value, dict) else {}


def _errors(row: dict[str, Any]) -> dict[str, int]:
    raw = _evaluation(row).get("errors", {})
    return raw if isinstance(raw, dict) else {}


def _alerts(row: dict[str, Any]) -> list[str]:
    raw = _value(row, "treatment_safety_alerts", "alertas_por_tratamiento", default=[])
    if not isinstance(raw, list):
        return []
    labels = []
    for alert in raw:
        if isinstance(alert, dict):
            alert = alert.get("code", alert.get("message", ""))
        if alert:
            labels.append(str(alert))
    return labels


def _specialty(row: dict[str, Any], metadata: dict[str, dict[str, str]]) -> str:
    case_id = _case_id(row)
    specialty = _value(row, "specialty", "especialidad", default="")
    specialty = specialty or metadata.get(case_id, {}).get("specialty", "")
    return SPECIALTY_LABELS.get(str(specialty), str(specialty) if specialty else "No especificada")


def _source_dataset(row: dict[str, Any], metadata: dict[str, dict[str, str]]) -> str:
    case_id = _case_id(row)
    return str(
        _value(row, "source_dataset", "tipo_caso", default="")
        or metadata.get(case_id, {}).get("source_dataset", "")
        or "—"
    )


def _check_label(row: dict[str, Any], keys: tuple[str, ...]) -> str:
    value = _value(row, *keys, default=None)
    if value is None:
        return "—"
    return "Correcto" if bool(value) else "Revisar"


def _table_rows(
    results: list[dict[str, Any]],
    metadata: dict[str, dict[str, str]],
) -> str:
    rows: list[str] = []
    for row in results:
        evaluation = _evaluation(row)
        errors = _errors(row)
        score = evaluation.get("score")
        score_text = f"{score:.2f}%" if isinstance(score, (int, float)) else "—"
        completed = evaluation.get("completed_questions")
        total = evaluation.get("total_questions")
        questions = f"{completed}/{total}" if completed is not None and total is not None else "—"
        turns = _value(row, "verified_turns", "turnos_verificados", default="—")
        all_roles = _value(
            row,
            "all_roles_and_evidence_correct",
            "todos_los_turnos_correctos",
            default=None,
        )
        vitals = _value(row, "vitals_preserved", "signos_vitales_conservados", default=None)
        status = _value(row, "status", default="—")
        alert_text = ", ".join(_alerts(row)) or "—"
        error_text = " · ".join(
            f"{label}: {errors.get(key, 0)}"
            for key, label in ERROR_LABELS
        )
        values = (
            _case_id(row),
            _specialty(row, metadata),
            _source_dataset(row, metadata),
            str(status),
            str(turns),
            score_text,
            questions,
            error_text,
            alert_text,
            _check_label(
                row,
                ("all_roles_and_evidence_correct", "todos_los_turnos_correctos"),
            ) if all_roles is not None else "—",
            _check_label(row, ("vitals_preserved", "signos_vitales_conservados"))
            if vitals is not None else "—",
        )
        cells = "".join(f"<td>{html.escape(value)}</td>" for value in values)
        rows.append(f"<tr>{cells}</tr>")
    return "\n".join(rows)


def _specialty_summary(
    result_sets: list[tuple[dict[str, str], list[dict[str, Any]] | None]],
    metadata: dict[str, dict[str, str]],
) -> str:
    totals: dict[tuple[str, str], dict[str, Any]] = defaultdict(
        lambda: {"cases": 0, "scores": [], "turns": 0, "completed": 0, "questions": 0}
    )
    for result_set, results in result_sets:
        if results is None:
            continue
        for row in results:
            specialty = _specialty(row, metadata)
            aggregate = totals[(result_set["title"], specialty)]
            evaluation = _evaluation(row)
            aggregate["cases"] += 1
            if isinstance(evaluation.get("score"), (int, float)):
                aggregate["scores"].append(float(evaluation["score"]))
            turns = _value(row, "verified_turns", "turnos_verificados", default=0)
            if isinstance(turns, int):
                aggregate["turns"] += turns
            aggregate["completed"] += int(evaluation.get("completed_questions", 0) or 0)
            aggregate["questions"] += int(evaluation.get("total_questions", 0) or 0)

    rows = []
    for (source, specialty), aggregate in sorted(totals.items()):
        scores = aggregate["scores"]
        average = f"{sum(scores) / len(scores):.2f}%" if scores else "—"
        completion = (
            f"{aggregate['completed']}/{aggregate['questions']}"
            if aggregate["questions"] else "—"
        )
        cells = (
            source,
            specialty,
            str(aggregate["cases"]),
            str(aggregate["turns"]),
            average,
            completion,
        )
        rows.append("<tr>" + "".join(f"<td>{html.escape(cell)}</td>" for cell in cells) + "</tr>")
    return "\n".join(rows)


def generate_report(output_path: Path) -> Path:
    metadata = _clinical_case_metadata()
    loaded = [
        (result_set, _read_result_file(BACKEND / result_set["filename"]))
        for result_set in RESULT_SETS
    ]
    sections = []
    for result_set, results in loaded:
        if results is None:
            body = (
                f'<tr><td colspan="11" class="empty">No existe '
                f"<code>{html.escape(result_set['filename'])}</code>; ejecuta la prueba correspondiente.</td></tr>"
            )
            count = 0
        else:
            body = _table_rows(results, metadata) or (
                '<tr><td colspan="11" class="empty">El archivo no contiene resultados.</td></tr>'
            )
            count = len(results)
        sections.append(
            f"""
            <section class="panel" id="{html.escape(result_set['key'])}">
              <div class="section-heading">
                <div>
                  <h2>{html.escape(result_set['title'])}</h2>
                  <p>{html.escape(result_set['filename'])}</p>
                </div>
                <span class="badge">{count} casos</span>
              </div>
              <div class="table-wrap">
                <table>
                  <thead><tr>
                    <th>Caso</th><th>Especialidad</th><th>Fuente</th><th>Estado</th>
                    <th>Turnos</th><th>Puntaje</th><th>Preguntas</th><th>Errores</th>
                    <th>Alertas</th><th>Roles/evidencia</th><th>Signos vitales</th>
                  </tr></thead>
                  <tbody>{body}</tbody>
                </table>
              </div>
            </section>
            """
        )

    summary_rows = _specialty_summary(loaded, metadata)
    if not summary_rows:
        summary_rows = '<tr><td colspan="6" class="empty">No hay resultados para resumir.</td></tr>'

    document = f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Resultados del motor clínico</title>
  <style>
    :root {{ color-scheme: light; font-family: "Segoe UI", Arial, sans-serif; color: #172033; background: #f3f6fb; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; padding: 32px; }}
    main {{ max-width: 1600px; margin: 0 auto; }}
    header {{ margin-bottom: 24px; }}
    h1 {{ margin: 0 0 8px; font-size: clamp(1.7rem, 3vw, 2.5rem); }}
    h2 {{ margin: 0; font-size: 1.25rem; }}
    p {{ color: #65728a; }}
    .muted {{ margin: 0; font-size: .9rem; }}
    .panel {{ background: white; border: 1px solid #dfe6f0; border-radius: 14px; margin: 18px 0; padding: 20px; box-shadow: 0 5px 20px #1d35570a; }}
    .section-heading {{ display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 16px; }}
    .badge {{ background: #e8efff; color: #244f9c; border-radius: 99px; padding: 6px 12px; font-size: .85rem; white-space: nowrap; }}
    .table-wrap {{ overflow-x: auto; }}
    table {{ border-collapse: collapse; width: 100%; font-size: .9rem; }}
    th, td {{ text-align: left; padding: 10px 12px; border-bottom: 1px solid #e9edf4; vertical-align: top; }}
    th {{ background: #f7f9fc; color: #49566d; font-weight: 650; white-space: nowrap; }}
    tbody tr:hover {{ background: #f8faff; }}
    td:first-child {{ font-weight: 700; white-space: nowrap; }}
    .empty {{ color: #7b8799; text-align: center; padding: 24px; }}
    code {{ background: #f0f3f8; padding: 2px 5px; border-radius: 4px; }}
    @media (max-width: 700px) {{ body {{ padding: 14px; }} .panel {{ padding: 14px; }} }}
    @media print {{ body {{ background: white; padding: 0; }} .panel {{ box-shadow: none; break-inside: avoid; }} }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Resultados del motor clínico</h1>
      <p class="muted">Generado: {html.escape(datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z"))}</p>
      <p class="muted">Las tablas reflejan los JSON disponibles en <code>backend/</code>.</p>
    </header>
    <section class="panel">
      <div class="section-heading"><div><h2>Resumen por especialidad y corrida</h2></div></div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Conjunto</th><th>Especialidad</th><th>Casos</th><th>Turnos</th><th>Puntaje promedio</th><th>Preguntas completadas</th></tr></thead>
          <tbody>{summary_rows}</tbody>
        </table>
      </div>
    </section>
    {''.join(sections)}
  </main>
</body>
</html>
"""
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(document, encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"No se pudo escribir el informe HTML en {output_path}: {exc}") from exc
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Genera un informe HTML de las tablas de resultados curados, validados y clínicos."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=BACKEND / "visualizacion_resultados_clinicos.html",
        help="Ruta del HTML de salida (por defecto, backend/visualizacion_resultados_clinicos.html).",
    )
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    try:
        report_path = generate_report(output)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"Informe HTML generado: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
