# Fase 1 · Intento 1 (fallido) — 2026-10-08

Evidencia original de la primera documentación de la descarga, conservada tal como se generó.

## Qué falló

| Evidencia | Resultado | Causa |
| --- | --- | --- |
| `02_ejecucion_fetch_medqa.*` | Código de salida **1**: «El sistema no puede encontrar la ruta especificada» | La herramienta ejecutaba los comandos con `cmd.exe`, pero el comando estaba escrito en sintaxis de PowerShell (`cd backend; …`). |
| `04_listado_medqa.*` | Código de salida **255**: «"Get-ChildItem" no se reconoce…» | Misma causa: `Get-ChildItem` es un comando de PowerShell, no de `cmd`. |
| `05_resumen_huellas.json`, `06_…png` | Solo listaba `MedQA-master.zip` | El registro de la fuente no incluía `data_clean.zip`, el archivo que contiene las preguntas. |
| Todas las `.png` | Texto diminuto y acentos ilegibles («Ejecuci�n») | Se usaba la fuente de mapa de bits por defecto de Pillow. |

Además, `fetch` no comparaba la huella SHA-256 con un valor esperado (solo la calculaba) y, en cada
ejecución, sobrescribía la fecha de obtención.

## Cómo se corrigió (intento 2, vigente)

- `evidencia.py ejecutar` admite `--cwd` (sin depender de `cd`), fuerza UTF-8 y usa una fuente TrueType a 1440 px.
- `registry.py` registra los dos archivos originales con su URL y su huella esperada; `fetch.py` rechaza un archivo con huella distinta y conserva la fecha original de obtención.
- `listar_raw.py` reemplaza a `Get-ChildItem` y compara las huellas esperadas con las obtenidas.

Resultado del intento 2: código de salida 0 y ambas huellas verificadas. Ver [../../README.md](../../README.md).
