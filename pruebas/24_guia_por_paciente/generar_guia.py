r"""Arma el contenido de «Guiones de prueba por paciente» a partir de los datos del proyecto.

Fuentes:
- pruebas/13_guiones_por_paciente/guiones.py: qué preguntar (en orden), qué no preguntar, por qué y notas.
- descartes.py (esta carpeta): por qué cada dato descarta cada diagnóstico diferencial.
- data/cases/curated/: paciente, motivo de consulta, diagnóstico, diferenciales y sus datos de descarte.
- Un resultados_guiones.json de la batería con el modelo real: lo que respondió el simulador.

Sigue cada diferencial con los datos revelados (más los que el doctor presenta al inicio): «posible» mientras no
haya datos en su contra, «menos probable» con el primero y «descartada» cuando se revelan todos. Escribe
resultados/guia.json, que generar_docx.cjs convierte en el documento Word.

Uso, desde la raíz:
    backend\.venv\Scripts\python.exe pruebas\24_guia_por_paciente\generar_guia.py <resultados_guiones.json>
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "pruebas" / "13_guiones_por_paciente"))
sys.path.insert(0, str(HERE))
sys.stdout.reconfigure(encoding="utf-8")

from descartes import DESCARTES  # noqa: E402
from guiones import GUIONES, POR_QUE  # noqa: E402
from server.engine.disclosure.policy import DisclosurePolicy  # noqa: E402

CURATED = ROOT / "data" / "cases" / "curated"
SITIO = "https://consulta-medica-three.vercel.app"
ESPECIALIDAD = {
    "emergencias": "Emergencias", "medicina_interna": "Medicina interna", "pediatria": "Pediatría",
    "ginecologia_obstetricia": "Ginecología y obstetricia", "cirugia_general": "Cirugía general",
}
AGENTE = {
    "paciente": "Paciente", "medico_asistente": "Médico asistente", "laboratorio": "Laboratorio",
    "radiologia": "Radiología", "especialista": "Especialista",
}


def estado(diferencial: dict, revelados: set[str]) -> str:
    datos = set(diferencial["discard_evidence_ids"])
    vistos = datos & revelados
    if datos and vistos == datos:
        return "descartada"
    return "menos probable" if vistos else "posible"


def resumen(case: dict, estados: dict[str, str]) -> dict[str, list[str]]:
    grupos = {"posibles": [case["protected"]["diagnosis"]["name"]], "menos probables": [], "descartadas": []}
    clave = {"posible": "posibles", "menos probable": "menos probables", "descartada": "descartadas"}
    for nombre, valor in estados.items():
        grupos[clave[valor]].append(nombre)
    return {grupo: sorted(nombres) for grupo, nombres in grupos.items()}


def armar_caso(case: dict, resultado: dict) -> dict:
    case_id = case["case_id"]
    guion = GUIONES[case_id]
    por_que = POR_QUE.get(case_id, {})
    items = {i["evidence_id"]: i for i in [case["public"]["chief_complaint"], *case["public"]["items"], *case["on_request"]]}
    diferenciales = case["protected"]["differentials"]
    faltan = [d["name"] for d in diferenciales if d["name"] not in DESCARTES.get(case_id, {})]
    if faltan:
        raise SystemExit(f"{case_id}: faltan explicaciones de descarte para {faltan}")

    revelados = set(DisclosurePolicy.initial_evidence_ids(case))
    estados = {d["name"]: estado(d, revelados) for d in diferenciales}
    turnos = {t["pedido"]: t for t in resultado["turnos"]}
    pasos = []
    for numero, (pedido, agente, _) in enumerate(guion["preguntar"], start=1):
        turno = turnos[pedido]
        revelados.update(turno["evidencia"])
        cambios = []
        for d in diferenciales:
            nuevo = estado(d, revelados)
            if nuevo == estados[d["name"]]:
                continue
            if nuevo == "descartada":
                cambios.append({"enfermedad": d["name"], "pasa_a": "descartada", "por_que": DESCARTES[case_id][d["name"]]})
            else:
                en_contra = [items[e]["label"] for e in d["discard_evidence_ids"] if e in revelados]
                cambios.append({"enfermedad": d["name"], "pasa_a": "menos probable",
                                "por_que": f"Primer dato en contra: {', '.join(en_contra)}. Falta: "
                                           + ", ".join(items[e]["label"] for e in d["discard_evidence_ids"] if e not in revelados) + "."})
            estados[d["name"]] = nuevo
        pasos.append({
            "numero": numero, "pedido": pedido, "por_que": por_que.get(pedido, ""), "agente": AGENTE.get(agente, agente),
            "medico_tratante": turno.get("medico_tratante"), "respuesta": turno["respuesta"],
            "problemas": turno.get("problemas", []), "cambios": cambios, "queda": resumen(case, estados),
        })
    no_preguntar = [{"pedido": pedido, "motivo": motivo, "respuesta": turnos[pedido]["respuesta"]}
                    for pedido, motivo in guion["no_preguntar"]]
    patient = case["public"]["patient"]
    inicial = {d["name"]: estado(d, set(DisclosurePolicy.initial_evidence_ids(case))) for d in diferenciales}
    return {
        "case_id": case_id,
        "paciente": f"{patient['alias']}, {patient['age_years']} años",
        "especialidad": ESPECIALIDAD[case["specialty"]],
        "motivo": case["public"]["chief_complaint"]["text"],
        "enlace": f"{SITIO}/simulacion.html?caso={case_id}",
        "al_empezar": resumen(case, inicial),
        "pasos": pasos,
        "al_terminar": resumen(case, estados),
        "no_preguntar": no_preguntar,
        "nota": guion.get("nota", ""),
        "diagnostico": case["protected"]["diagnosis"]["name"],
        "descartes": [{"enfermedad": d["name"], "por_que": DESCARTES[case_id][d["name"]]} for d in diferenciales],
    }


def main(resultados_path: str) -> None:
    resultados = json.loads(Path(resultados_path).read_text(encoding="utf-8"))
    casos = [json.loads(p.read_text(encoding="utf-8")) for p in CURATED.glob("*.json")]
    casos.sort(key=lambda c: int(c["case_id"].rsplit("-", 1)[1]))  # 001 a 010 y luego los sintéticos 101 a 103
    guia = [armar_caso(case, resultados[case["case_id"]]) for case in casos]
    total = sum(len(r["turnos"]) for r in resultados.values())
    con_problemas = sum(bool(t.get("problemas")) for r in resultados.values() for t in r["turnos"])
    con_un_solo = sum(not c["al_terminar"]["menos probables"] and len(c["al_terminar"]["posibles"]) == 1 for c in guia)
    salida = HERE / "resultados" / "guia.json"
    salida.parent.mkdir(exist_ok=True)
    salida.write_text(json.dumps({
        "fecha": date.today().isoformat(), "pedidos": total, "pedidos_correctos": total - con_problemas,
        "casos": guia,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(guia)} casos; {total - con_problemas} de {total} pedidos correctos en la verificación con el modelo real")
    print(f"casos que terminan con un solo diagnóstico: {con_un_solo} de {len(guia)}")
    for c in guia:
        fin = c["al_terminar"]
        print(f"  {c['case_id']}: {len(c['pasos'])} pasos -> queda {fin['posibles']}"
              + (f" | menos probables: {fin['menos probables']}" if fin["menos probables"] else ""))
    print(f"Contenido guardado en {salida.relative_to(ROOT)}")


if __name__ == "__main__":
    main(sys.argv[1])
