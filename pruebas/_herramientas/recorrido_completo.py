#!/usr/bin/env python3
"""Comprobación final del recorrido completo del sprint 1 y regeneración de las evidencias.

Ejecuta, en orden, las cuatro fases del flujo de datos (descarga → transformación → validación →
frontend) y luego las comprobaciones del simulador que se pueden repetir sin costo: motor clínico (14),
hoja de evaluación (15), otro caso (17), un solo diagnóstico (18), aviso de privacidad (19) y sinónimos
(20). Las fases 1 a 4 regeneran su evidencia en su carpeta; las demás guardan su salida en
pruebas/21_cierre_sprint1/recorrido/. Se detiene en la primera que falle.

Todo corre sin Groq (proveedor local determinístico) y sin crear cuentas: la fase 16 (historial con un
alumno temporal en Supabase) se repite aparte con su propio README.

Uso (desde la raíz del repositorio):
  backend/.venv/Scripts/python.exe pruebas/_herramientas/recorrido_completo.py

La fase 4 necesita Node y `playwright`, dependencia de desarrollo del proyecto: `npm install` y, una
sola vez, `npx playwright install chromium` para descargar el navegador.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND = REPO_ROOT / "backend"
PRUEBAS = REPO_ROOT / "pruebas"
EVIDENCIA = PRUEBAS / "_herramientas" / "evidencia.py"
PY = sys.executable
PORT = os.environ.get("PORT_PRUEBAS", "3100")

results: list[tuple[str, str, int]] = []


def evidencia(*args: str) -> int:
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    return subprocess.run([PY, str(EVIDENCIA), *args], cwd=REPO_ROOT, env=env).returncode


def ejecutar(etapa: str, descripcion: str, comando: str, salida: str, cwd: Path = REPO_ROOT) -> None:
    print(f"\n== {etapa}: {descripcion}\n   {comando}")
    # Solo el .txt: la evidencia visual es la foto real de la terminal donde corre este script.
    code = evidencia("ejecutar", comando, "--cwd", str(cwd), "--salida", str(PRUEBAS / salida), "--sin-png")
    salida = salida.rsplit(".", 1)[0] + ".txt"
    results.append((etapa, descripcion, code))
    print(f"   código de salida: {code} → {salida}")
    if code != 0:
        finish()


def captura(tipo: str, archivo: str, salida: str, lineas: str | None = None) -> None:
    args = [tipo, archivo, "--salida", str(PRUEBAS / salida)]
    if lineas:
        args += ["--lineas", lineas]
    code = evidencia(*args)
    print(f"   captura de {archivo} → {salida} (código {code})")
    if code != 0:
        results.append(("Evidencia", f"no se pudo generar {salida}", code))
        finish()


def playwright_available() -> bool:
    return (REPO_ROOT / "node_modules" / "playwright").exists()


def wait_for_server(url: str, timeout: float = 30) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2):
                return True
        except OSError:
            time.sleep(0.5)
    return False


def finish() -> None:
    lines = [
        "Recorrido completo del sprint 1: flujo de datos MedQA → casos curados → frontend → simulador",
        f"Fecha: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "",
    ]
    lines += [f"[{'OK' if code == 0 else 'FALLA'}] {etapa}: {desc} (código {code})" for etapa, desc, code in results]
    ok = results and all(code == 0 for _, _, code in results)
    lines += ["", "RESULTADO: recorrido completo sin errores." if ok else "RESULTADO: el recorrido se detuvo por un error."]
    text = "\n".join(lines) + "\n"
    out = PRUEBAS / "05_recorrido_completo" / "resumen_recorrido.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    image_code = evidencia("archivo", str(out), "--salida", str(out.with_suffix(".png")))
    print("\n" + text)
    if image_code != 0:
        print(f"No se pudo generar la imagen del resumen (código {image_code}).")
    sys.exit(0 if ok and image_code == 0 else 1)


def main() -> None:
    # Sin trazas a LangSmith: no hacen falta para comprobar nada y, sin cuota, llenan la salida de avisos.
    os.environ["LANGSMITH_TRACING"] = "false"
    venv_py = ".\\.venv\\Scripts\\python.exe" if os.name == "nt" else "./.venv/bin/python"
    root_py = f"backend\\{venv_py[2:]}" if os.name == "nt" else "backend/.venv/bin/python"

    # Fase 1: descarga e identificación de la fuente.
    captura("codigo", "backend/case_preparation/sources/registry.py", "01_descarga_datasets/codigo/00_registro_fuente_medqa.png")
    captura("codigo", "backend/case_preparation/sources/fetch.py", "01_descarga_datasets/codigo/01_codigo_fetch_medqa.png")
    ejecutar("Fase 1", "descarga y verificación SHA-256 de MedQA",
             f"{venv_py} -m case_preparation sources fetch --dataset medqa",
             "01_descarga_datasets/ejecucion/02_ejecucion_fetch_medqa.png", BACKEND)
    captura("archivo", "data/raw/medqa/source_manifest.json", "01_descarga_datasets/resultados/03_manifest_medqa.png")
    ejecutar("Fase 1", "listado de data/raw/medqa y huellas esperadas",
             f"{root_py} pruebas/01_descarga_datasets/listar_raw.py",
             "01_descarga_datasets/resultados/04_listado_medqa.png")

    # Fase 2: extracción de candidatos y conversión a JSON de los 10 casos.
    ejecutar("Fase 2", "extracción de candidatos MedQA",
             f"{venv_py} -m case_preparation adapters extract --dataset medqa",
             "02_transformacion/ejecucion/02_extract_medqa.png", BACKEND)
    ejecutar("Fase 2", "conversión a JSON y curación de los 10 casos",
             f"{venv_py} -m case_preparation curation",
             "02_transformacion/ejecucion/03_curation_medqa.png", BACKEND)
    ejecutar("Fase 2", "reproducibilidad: data/cases/ idéntico a lo versionado",
             "git -c core.safecrlf=false diff --ignore-cr-at-eol --exit-code --stat -- data/cases && echo Sin diferencias: la regeneracion reproduce exactamente los casos versionados.",
             "02_transformacion/resultados/04_reproducibilidad_casos.png")
    captura("archivo", "data/cases/final_selection/medqa_final_10.json", "02_transformacion/resultados/05_seleccion_final_10.png")

    # Fase 3: validación de esquema, lote curado y vista pública.
    ejecutar("Fase 3", "esquema, lote curado y vista pública",
             f"{root_py} pruebas/03_validacion/verificar_casos.py",
             "03_validacion/ejecucion/01_verificar_casos.png")
    ejecutar("Fase 3", "pruebas automatizadas del backend",
             f"{venv_py} -m pytest -v -p no:cacheprovider",
             "03_validacion/ejecucion/02_pytest_backend.png", BACKEND)

    fases_del_simulador(venv_py, root_py)

    # Fase 4: conexión con el frontend; con el mismo servidor, las pruebas del simulador en el navegador.
    if not playwright_available():
        print("Falta playwright. Ejecute: npm install && npx playwright install chromium")
        results.append(("Fase 4", "playwright no disponible", 1))
        finish()
    server = subprocess.Popen(
        [PY, "-m", "uvicorn", "server.main:app", "--port", PORT],
        cwd=BACKEND,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        # Sin Groq: respuestas determinísticas, sin costo ni cuota.
        env={**os.environ, "GROQ_API_KEYS": ""},
    )
    try:
        if not wait_for_server(f"http://localhost:{PORT}/api/status"):
            results.append(("Fase 4", "el servidor no respondió", 1))
            finish()
        os.environ["BASE_URL"] = f"http://localhost:{PORT}"
        ejecutar("Fase 4", "carga de un caso por especialidad en /simulacion.html (1440 px)",
                 "node pruebas/_herramientas/capturar_frontend.cjs pruebas/04_frontend/capturas",
                 "04_frontend/ejecucion/01_capturar_frontend.png")
        ejecutar("Fase 15", "hoja de evaluación y alerta de seguridad en el navegador",
                 f"node pruebas/15_integracion_motor_clinico/probar_evaluacion.cjs parcial pruebas/{CIERRE}/capturas",
                 f"{CIERRE}/04_fase15_hoja_evaluacion.png")
        ejecutar("Fase 17", "probar otro caso y cerrar el simulador",
                 f"node pruebas/17_otro_caso/probar_otro_caso.cjs pruebas/{CIERRE}/capturas",
                 f"{CIERRE}/05_fase17_otro_caso.png")
        ejecutar("Fase 19", "aviso de privacidad y aceptación al crear cuenta",
                 f"node pruebas/19_aviso_privacidad/probar_aviso.cjs pruebas/{CIERRE}/capturas",
                 f"{CIERRE}/06_fase19_aviso_privacidad.png")
    finally:
        server.terminate()
        server.wait(timeout=10)

    finish()


# Salidas de las fases posteriores al flujo de datos (no pisan la evidencia original de cada fase).
CIERRE = "21_cierre_sprint1/recorrido"


def fases_del_simulador(venv_py: str, root_py: str) -> None:
    """Comprobaciones sin servidor: motor clínico, un solo diagnóstico y sinónimos."""
    (PRUEBAS / CIERRE / "capturas").mkdir(parents=True, exist_ok=True)
    ejecutar("Fase 14", "motor clínico con los 13 casos curados (API, roles, alertas y evaluación)",
             f"{venv_py} ../pruebas/14_motor_clinico/probar_casos_curated.py",
             f"{CIERRE}/01_fase14_motor_clinico.png", BACKEND)
    ejecutar("Fase 18", "cada caso llega a un solo diagnóstico (modo local)",
             f"{venv_py} ../pruebas/18_casos_con_un_solo_diagnostico/bateria_un_solo_diagnostico.py --local",
             f"{CIERRE}/02_fase18_un_solo_diagnostico.png", BACKEND)
    ejecutar("Fase 20", "sinónimos del diagnóstico por caso",
             f"{root_py} pruebas/20_sinonimos_diagnostico/mostrar_sinonimos.py",
             f"{CIERRE}/03_fase20_sinonimos.png")


if __name__ == "__main__":
    main()
