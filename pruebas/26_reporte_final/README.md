# 26. Reporte final de la consulta (HU-006)

## Objetivo

HU-006 pide un reporte **solo poscierre y con propietario validado**, que incluya diagnóstico de referencia,
propuesta, tratamiento, puntajes y evidencia revelada, **sin ninguna fuente ajena al `case_id`**, con prueba E2E.

Antes, la hoja de evaluación solo mostraba conteos («Obtuviste 3 de 5 datos clave»). Ahora el alumno ve
**cuáles** datos clave obtuvo, **cuáles** le faltaron y **por qué** importaban, el diagnóstico de referencia junto
al suyo, los exámenes que pidió, el tratamiento que propuso y el de referencia, y todo lo que reveló en la
consulta. El servidor arma el reporte y solo lo entrega al dueño de la consulta cerrada.

Informe completo con la matriz de trazabilidad, los defectos y la recomendación:
[INFORME_HU-006.md](INFORME_HU-006.md). Diseño y plan: `docs/superpowers/specs/2026-10-28-hu006-reporte-final-design.md`
y `docs/superpowers/plans/2026-10-28-hu006-reporte-final.md`. Índice visual de las capturas: `evidencia.html`.

## Documentos

| Archivo | Contenido |
| --- | --- |
| [01_contrato_reporte.md](01_contrato_reporte.md) (+ `.png`) | Rutas, campos del reporte con su fuente y reglas |
| [INFORME_HU-006.md](INFORME_HU-006.md) (+ `.png`) | Informe final para el Product Owner |

## Qué se hizo

| Commit | Cambio |
| --- | --- |
| `c835f86`, `8f1d254`, `0a1d735` | **Código:** `build_report` en el motor de evaluación (`backend/server/engine/evaluation/report.py`) y `ClinicalEvaluationEngine.report` |
| `169c005` | **Código:** `GET /api/ai/sessions/{id}/report` con `authorize_session`, 409 antes del cierre; el cierre guarda la propuesta y devuelve el reporte |
| `fc76495`, `c5fafb5` | **Código:** secciones nuevas de la hoja de evaluación, pintadas como texto |
| `753cbc6` | El inventario de rutas de TA-011 incluye `/report` |
| `36177d5`, `06032f7` | Suite HTTP HU006-01 a HU006-17 (local y en vivo) |
| `b8c1366` | Prueba sobre los 43 casos curados (CA4) |
| `375ff0e`, `a17cb62`, `9e24bf1` | Lanzadores de pruebas con entorno fijo, salida y foto |

Pruebas nuevas: `backend/tests/unit/test_report_builder.py` (11), `backend/tests/integration/test_api_report.py`
(5), `backend/tests/security/test_hu006_report.py` (17), `backend/tests/integration/test_report_all_cases.py` (88).

## Comandos

Desde la raíz del repositorio:

```powershell
# Una prueba con entorno fijo, salida y foto real (deja ejecucion\tdd\<nombre>.txt y _terminal.png)
.\pruebas\26_reporte_final\correr_prueba.ps1 -Nombre t1_green -Pytest "tests/unit/test_report_builder.py -v"

# Suite HU006 en local (evidencia en resultados\<fase>)
.\pruebas\26_reporte_final\correr_suite.ps1 -Fase local_despues

# En vivo: servidor real con las sesiones en Supabase, y la suite contra él
$env:PORT='3100'; $env:SESSION_STORE='supabase'; $env:LANGSMITH_TRACING='false'; npm start > <log>
.\pruebas\26_reporte_final\correr_suite.ps1 -Fase vivo_despues -Modo vivo -BaseUrl http://127.0.0.1:3100 -LogServidor <log>

# Navegador real (E2E) contra el servidor en marcha
node pruebas\26_reporte_final\probar_navegador.cjs pruebas\26_reporte_final\capturas

# Tarjetas por caso, capturas de las salidas, evidencia.html y verificación
backend\.venv\Scripts\python.exe pruebas\26_reporte_final\generar_capturas.py
```

El «antes» se ejecuta en un worktree con la suite de HU-006 y el código del servidor y de la pantalla de la rama
`ta-011-autorizacion-sesiones` (`git checkout ta-011-autorizacion-sesiones -- backend/server frontend/public`).

## Resultados

| Ejecución | Resultado | Evidencia |
| --- | --- | --- |
| Regresión antes (rama TA-011) | 461 pasan | `ejecucion/01_regresion_antes.txt`, `_terminal.png` |
| Suite HU006, local, antes | 3 PASA, **14 FALLA** | `ejecucion/local_antes_pytest.txt`, `02_local_antes_terminal.png`, `resultados/local_antes/` |
| Suite HU006, local, después | **17 de 17 PASA** | `ejecucion/local_despues_pytest.txt`, `04_local_despues_terminal.png`, `resultados/local_despues/` |
| Suite HU006, en vivo, antes (Supabase de producción) | 3 PASA, **14 FALLA** | `ejecucion/vivo_antes_pytest.txt`, `03_vivo_antes_terminal.png`, `resultados/vivo_antes/` |
| Suite HU006, en vivo, después (Supabase de producción) | **17 de 17 PASA**; usuarios y consultas temporales borrados | `ejecucion/vivo_despues_pytest.txt`, `05b_vivo_despues_terminal.png`, `resultados/vivo_despues/` |
| Regresión después | **582 pasan** (461 + 121 nuevas), 3 deseleccionadas | `ejecucion/05_regresion_despues.txt`, `_terminal.png` |
| 43 casos curados | 88 de 88 | `ejecucion/tdd/t6_43_casos.txt` |
| Navegador real (E2E), caso EME-101 | **21 de 21** comprobaciones | `capturas/navegador_*.png`, `capturas/navegador_registro.json`, `ejecucion/08_navegador_terminal.png` |
| Preview de Vercel | **No ejecutado**: sus claves de Groq no funcionan; `/report` sí exige credencial (401) | `ejecucion/09_preview_vercel.txt`, `intentos/08_...` |
| Limpieza de las consultas del navegador | 6 consultas y 36 eventos borrados; Auth con sus 2 usuarios | `ejecucion/10_limpieza_navegador.txt` |
| TDD de cada tarea (rojo y verde) | Salida y foto de cada corrida | `ejecucion/tdd/` |

Los 3 casos que pasan «antes» (04, 05 y 07) esperan 404 para personas ajenas: sin la ruta, todos reciben 404.
Pasan por la razón equivocada y por eso se cuentan junto con los demás en el informe.

Las fotos (`.png`) y los logs del servidor se guardan en el equipo y no se suben a GitHub; los JSON, las salidas
`.txt` y los scripts sí.

## Estructura

- `ejecucion/`: salidas `.txt` y fotos reales de terminal; `ejecucion/tdd/`, las corridas en rojo y en verde de
  cada tarea.
- `resultados/<fase>/logs/HU006-XX.json`: petición y respuesta reales de cada caso, tokens enmascarados;
  `resultados/<fase>/capturas/`: su tarjeta PNG; `resultados/<fase>/limpieza.json` en vivo.
- `capturas/`: prueba en navegador (la hoja completa y cada sección) y salidas renderizadas.
- `codigo/`: capturas del código que se cambió.
- `intentos/`: intentos fallidos, conservados sin modificar.

## Intentos

| Intento | Qué falló | Corrección |
| --- | --- | --- |
| [01_ventana_cerrada_por_exit](intentos/01_ventana_cerrada_por_exit/README.md) | El lanzador cerraba la ventana antes de la foto | `$global:LASTEXITCODE` en lugar de `exit` |
| [02_reporte_fuera_del_motor](intentos/02_reporte_fuera_del_motor/README.md) | El reporte leía la parte protegida del caso fuera del motor de evaluación (regla de dependencias) | `build_report` pasa a `server/engine/evaluation/` |
| [03_pliegues_cerrados_en_la_prueba](intentos/03_pliegues_cerrados_en_la_prueba/README.md) | La prueba en navegador leía como vacías las secciones plegadas | `textContent` en lugar de `innerText` |
| [04_foto_de_la_hoja_recortada](intentos/04_foto_de_la_hoja_recortada/README.md) | La foto de la hoja completa salía cortada | Se libera también la altura de la tarjeta |
| [05_dato_con_etiqueta_repetida](intentos/05_dato_con_etiqueta_repetida/README.md) | Un dato revelado repetía su etiqueta | La hoja no la repite; nueva comprobación |
| [06_vivo_sin_registro_de_limpieza](intentos/06_vivo_sin_registro_de_limpieza/README.md) | La corrida en vivo no dejó `limpieza.json` | `TA011_EVIDENCIA` a la carpeta de la fase |
| [07_corte_de_red_con_supabase](intentos/07_corte_de_red_con_supabase/README.md) | `ReadError` transitorio con Supabase (503) | Comprobado que el cierre funciona; corrida repetida |
| [08_preview_sin_modelo_de_lenguaje](intentos/08_preview_sin_modelo_de_lenguaje/README.md) | Las claves de Groq del preview no funcionan | Pendiente: `GROQ_API_KEYS` en el entorno Preview de Vercel |
