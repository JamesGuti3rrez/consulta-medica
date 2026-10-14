r"""Verificación del sitio publicado tras la renumeración: corre, contra Vercel, las pruebas de las fases 15 a 22.

Usa el modelo real (Groq) y el Supabase real. Para «Mis simulaciones» crea un alumno de prueba temporal y lo
borra al terminar, con sus intentos.

Uso, desde la raíz:
    backend\.venv\Scripts\python.exe pruebas\23_numeracion_casos\verificar_produccion.py [URL]
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
PY = sys.executable
BASE = (sys.argv[1] if len(sys.argv) > 1 else "https://consulta-medica-three.vercel.app").rstrip("/")
OUT = "pruebas/23_numeracion_casos/vercel"
sys.stdout.reconfigure(encoding="utf-8")


def codigos() -> int:
    """Los códigos nuevos abren a su paciente; los viejos que ya no existen responden 404."""
    client = httpx.Client(timeout=30)
    esperados = {"MED-007": "Patricia Vargas", "MED-008": "Alberto Núñez", "PED-009": "Mateo Quispe"}
    fallas = 0
    for case_id, alias in esperados.items():
        body = client.get(f"{BASE}/api/caso", params={"caso": case_id}).json()
        ok = body.get("patient", {}).get("alias") == alias
        fallas += not ok
        print(f"  {case_id} -> {body.get('patient', {}).get('alias')} ({'OK' if ok else 'FALLA'})")
    for viejo in ("MED-009", "PED-007"):
        status = client.get(f"{BASE}/api/caso", params={"caso": viejo}).status_code
        fallas += status != 404
        print(f"  {viejo} (ya no existe) -> HTTP {status} ({'OK' if status == 404 else 'FALLA'})")
    return fallas


def correr(nombre: str, comando: list[str], env: dict | None = None) -> int:
    print(f"\n== {nombre}")
    result = subprocess.run(comando, cwd=ROOT, env={**os.environ, "BASE_URL": BASE, **(env or {})},
                            capture_output=True, text=True, encoding="utf-8")
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    for line in lines[-6:]:
        print(f"  {line[:150]}")
    if result.returncode != 0:
        print(f"  ERROR (código {result.returncode}): {result.stderr.strip()[-300:]}")
        return result.returncode
    # Algunas pruebas solo imprimen el resultado: «RESUMEN: X de Y» debe ser completo y sin errores de consola.
    for line in lines:
        match = re.search(r"RESUMEN: (\d+) de (\d+)", line)
        if match and match.group(1) != match.group(2):
            print("  FALLA: resumen incompleto")
            return 1
        if line.startswith("errores:") and line.strip() != "errores: []":
            print("  FALLA: errores en la consola del navegador")
            return 1
    return 0


def main() -> int:
    print(f"Sitio: {BASE}")
    print("\n== Códigos de los casos")
    resultados = {"Códigos de los casos": codigos()}
    resultados["Fase 22: pedidos genéricos"] = correr(
        "Fase 22: pedidos genéricos", [PY, "pruebas/22_pedidos_genericos/probar_pedidos.py", BASE])
    resultados["Fase 18: datos agregados"] = correr(
        "Fase 18: datos agregados por el equipo", [PY, "pruebas/18_casos_con_un_solo_diagnostico/probar_vercel.py", BASE])
    resultados["Fase 15: hoja de evaluación"] = correr(
        "Fase 15: hoja de evaluación", ["node", "pruebas/15_integracion_motor_clinico/probar_evaluacion.cjs", "parcial", OUT])
    resultados["Fase 17: otro caso"] = correr(
        "Fase 17: probar otro caso", ["node", "pruebas/17_otro_caso/probar_otro_caso.cjs", OUT])
    resultados["Fase 19: aviso de privacidad"] = correr(
        "Fase 19: aviso de privacidad", ["node", "pruebas/19_aviso_privacidad/probar_aviso.cjs", OUT])

    with tempfile.TemporaryDirectory() as tmp:
        credenciales = str(Path(tmp) / "alumno.json")
        usuario = "pruebas/16_historial_simulaciones/usuario_prueba.py"
        subprocess.run([PY, usuario, "crear", credenciales], cwd=ROOT, check=True)
        try:
            resultados["Fase 16: Mis simulaciones"] = correr(
                "Fase 16: Mis simulaciones (alumno temporal)",
                ["node", "pruebas/16_historial_simulaciones/probar_historial.cjs", OUT], {"CREDENCIALES": credenciales})
        finally:
            subprocess.run([PY, usuario, "borrar", credenciales], cwd=ROOT, check=True)

    print("\nRESUMEN")
    for nombre, code in resultados.items():
        print(f"  [{'OK' if code == 0 else 'FALLA'}] {nombre}")
    ok = all(code == 0 for code in resultados.values())
    print("\nRESULTADO:", "todo funciona en el sitio publicado." if ok else "hay fallas.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
