#!/usr/bin/env python3
"""Comprobación final del recorrido completo de datos y regeneración de las evidencias.

Ejecuta, en orden, las cuatro fases (descarga → transformación → validación → frontend) y guarda
cada salida como .txt y como PNG en vista de escritorio/PC dentro de pruebas/. Se detiene en la
primera fase que falle.

Uso (desde la raíz del repositorio):
  backend/.venv/Scripts/python.exe pruebas/_herramientas/recorrido_completo.py

La fase 4 necesita Node y el paquete `playwright` (no es dependencia del proyecto). Si no está en
NODE_PATH, se busca en la caché de npx; se instala con `npx playwright@1.63.0 install chromium`.
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
    code = evidencia("ejecutar", comando, "--cwd", str(cwd), "--salida", str(PRUEBAS / salida))
    results.append((etapa, descripcion, code))
    print(f"   código de salida: {code} → {salida}")
    if code != 0:
        finish()


def captura(tipo: str, archivo: str, salida: str, lineas: str | None = None) -> None:
    args = [tipo, archivo, "--salida", str(PRUEBAS / salida)]
    if lineas:
        args += ["--lineas", lineas]
    evidencia(*args)
    print(f"   captura de {archivo} → {salida}")


def playwright_node_path() -> str | None:
    if os.environ.get("NODE_PATH"):
        return os.environ["NODE_PATH"]
    cache = Path.home() / "AppData" / "Local" / "npm-cache" / "_npx"
    for candidate in sorted(cache.glob("*/node_modules/playwright")):
        return str(candidate.parent)
    return None


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
        "Recorrido completo del flujo de datos MedQA → casos curados → frontend",
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
    evidencia("archivo", str(out), "--salida", str(out.with_suffix(".png")))
    print("\n" + text)
    sys.exit(0 if ok else 1)


def main() -> None:
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

    # Fase 4: conexión con el frontend.
    node_path = playwright_node_path()
    if not node_path:
        print("No se encontró el paquete playwright. Ejecute: npx playwright@1.63.0 install chromium")
        results.append(("Fase 4", "playwright no disponible", 1))
        finish()
    server = subprocess.Popen(
        [PY, "-m", "uvicorn", "server.main:app", "--port", PORT],
        cwd=BACKEND,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        if not wait_for_server(f"http://localhost:{PORT}/api/status"):
            results.append(("Fase 4", "el servidor no respondió", 1))
            finish()
        os.environ["NODE_PATH"] = node_path
        os.environ["BASE_URL"] = f"http://localhost:{PORT}"
        ejecutar("Fase 4", "carga de un caso por especialidad en /simulacion.html (1440 px)",
                 "node pruebas/_herramientas/capturar_frontend.cjs pruebas/04_frontend/capturas 5",
                 "04_frontend/ejecucion/01_capturar_frontend.png")
    finally:
        server.terminate()
        server.wait(timeout=10)

    finish()


if __name__ == "__main__":
    main()
