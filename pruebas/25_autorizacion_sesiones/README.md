# 25. Autorización de sesiones y eventos (TA-011)

## Objetivo

TA-011 pide controles de propietario en todas las operaciones de sesión del simulador, también para los
invitados. La auditoría confirmó que en `main` (`0cebb31`) **cualquiera que conociera el UUID de una consulta
podía leerla, escribir en ella, ver sus eventos y cerrarla**. Ahora cada consulta solo la abre quien la empezó:
el alumno con su token de Supabase o el invitado con una credencial de capacidad de 256 bits.

Informe completo con la matriz de trazabilidad, los defectos y la recomendación:
[INFORME_TA-011.md](INFORME_TA-011.md). Índice visual de todas las capturas: `evidencia.html`.

## Documentos

| Archivo | Contenido |
| --- | --- |
| [01_inventario_rutas.md](01_inventario_rutas.md) (+ `.png`) | Las rutas con `session_id`: identidad y control antes y después; dueño; RLS de las tablas |
| [02_politica_acceso.md](02_politica_acceso.md) (+ `.png`) | La regla verificada, los códigos de respuesta y las decisiones (404 y no 403, credencial alterada, cierre) |
| [INFORME_TA-011.md](INFORME_TA-011.md) (+ `.png`) | Informe final para el Product Owner |

## Qué se hizo

| Commit | Cambio |
| --- | --- |
| `c8f5c26`, `a4e169e` | Suite `backend/tests/security/test_ta011_session_authz.py`: casos TA011-01 a TA011-40, modo local y modo vivo, con evidencia JSON por caso |
| `cd54a74` | **Código:** `authorize_session` en las 4 rutas, credencial de capacidad para invitados, 401/404 según la política, registro de denegaciones |
| `8864490` | Los casos en vivo se deseleccionan fuera del modo vivo |
| `7442a79` | Las 19 pruebas existentes que usaban las rutas sin credencial envían la suya (2 aserciones más estrictas, ver informe) |
| `ac7c0e1` | **Código:** el simulador envía la credencial en cada mensaje y al cerrar |
| `1aaec15` | El caso 18 enmascara también la credencial alterada de SN2 (ver intento 3) |
| `e4ffe0f` | Los scripts del recorrido completo (fases 14 y 18) envían la credencial |
| `4cacae9`, `d0308cd`, `901edb6` | Cambio de nombre de TA-017 a TA-011 en la suite, las variables, los comentarios y los scripts |
| `0666f9e`, `104e52a`, `66de2a4` | La ejecución anterior pasa a intentos; resultados de las ejecuciones repetidas y del preview |
| `9e2caae` | El caso 40 admite el 403 con que un servidor real rechaza el websocket (ver intento 6) |
| `5f9435d` | `correr_suite.ps1` fija el modo local en memoria y apaga LangSmith |
| `64218b9`, `cf0c846` | Suite en vivo contra el Supabase de producción; suites locales y regresión repetidas |

## Comandos

Desde la raíz del repositorio:

```powershell
# Suite TA-011 en modo local; deja la evidencia en resultados\<fase>\logs y ejecucion\<fase>_pytest.txt
.\pruebas\25_autorizacion_sesiones\correr_suite.ps1 -Fase local_despues

# Modo vivo: primero el servidor real con las sesiones en Supabase, escribiendo su log
$env:PORT='3100'; $env:SESSION_STORE='supabase'; $env:LANGSMITH_TRACING='false'; npm start > <log del servidor>
# luego la suite (crea y borra 2 alumnos temporales en el Supabase del .env)
.\pruebas\25_autorizacion_sesiones\correr_suite.ps1 -Fase vivo_despues -Modo vivo -BaseUrl http://127.0.0.1:3100 -LogServidor <log del servidor>

# Preview de Vercel: el token de bypass debe estar exportado antes de lanzar la suite (intento 7); sin log, sin el 39
$env:TA011_VERCEL_BYPASS = <token>
.\pruebas\25_autorizacion_sesiones\correr_suite.ps1 -Fase vercel_preview -Modo vivo -BaseUrl <url del preview> -Filtro 'not logs_servidor'

# Navegador real (servidor en marcha; para un preview protegido de Vercel, VERCEL_BYPASS=<token>)
node pruebas\25_autorizacion_sesiones\probar_navegador.cjs pruebas\25_autorizacion_sesiones\capturas

# Tarjetas PNG por caso, capturas de las salidas y evidencia.html
backend\.venv\Scripts\python.exe pruebas\25_autorizacion_sesiones\generar_capturas.py
```

El «antes» de la suite se ejecuta en un worktree con el código de producción de `main`:

```powershell
git worktree add --detach .wt_antes ta-011-autorizacion-sesiones
git -C .wt_antes checkout 0cebb31 -- backend/server frontend/public/js
# en .wt_antes: backend\.venv enlazado al del repositorio (mklink /J) y el mismo .env
.\.wt_antes\pruebas\25_autorizacion_sesiones\correr_suite.ps1 -Fase local_antes
```

Cada ejecución se hizo dentro de `pruebas\_herramientas\captura_terminal.ps1` para tener la foto real de la
terminal (`ejecucion\*_terminal.png`).

## Resultados

| Ejecución | Resultado | Evidencia |
| --- | --- | --- |
| Regresión antes (`main`, `0cebb31`) | 424 pasan | `ejecucion/01_regresion_antes.txt`, `_terminal.png` |
| Suite TA-011, local, antes | 14 PASA, **23 FALLA**, 3 solo en vivo | `ejecucion/local_antes_pytest.txt`, `02_local_antes_terminal.png`, `resultados/local_antes/` |
| Suite TA-011, local, después | **37 PASA**, 0 FALLA, 3 solo en vivo | `ejecucion/local_despues_pytest.txt`, `04_local_despues_terminal.png`, `resultados/local_despues/` |
| Regresión después | 461 pasan, 3 deseleccionadas (casos en vivo) | `ejecucion/05_regresion_despues.txt`, `_terminal.png` |
| Navegador real (localhost:3000, Groq) | El invitado conversa y cierra con su credencial; otro navegador recibe 401 sin credencial y 404 con una ajena | `capturas/navegador_0*.png`, `capturas/navegador_registro.json`, `ejecucion/08_navegador_terminal.png` |
| Fase 14 con la credencial | 43 de 43 casos, código 0 | `ejecucion/07_recorrido_scripts.txt`, `_terminal.png` |
| Fase 18 con la credencial | 13 de 13 casos con guion, código 0 | `ejecucion/07b_bateria_13_casos.txt`, `_terminal.png` |
| Suite en vivo, antes (código de `main` + Supabase de producción) | 17 PASA, **23 FALLA**; RLS (34 a 36) PASA | `ejecucion/vivo_antes_pytest.txt`, `03_vivo_antes_terminal.png`, `resultados/vivo_antes/` |
| Suite en vivo, después (Supabase de producción) | **40 de 40 PASA**; usuarios y consultas temporales borrados | `ejecucion/vivo_despues_pytest.txt`, `05b_vivo_despues_terminal.png`, `resultados/vivo_despues/` |
| Preview de Vercel | Con el token de bypass responde la API (401 sin credencial), pero **no ejecutado**: sus claves de Groq no funcionan | `ejecucion/09_preview_protegido.txt`, `intentos/08_preview_sin_modelo_de_lenguaje/` |

Las fotos (`.png`) se guardan en el equipo y no se suben a GitHub; los JSON, las salidas `.txt` y los scripts sí.

## Estructura

- `ejecucion/`: salidas `.txt` y fotos reales de terminal.
- `resultados/<fase>/logs/TA011-XX.json`: petición y respuesta reales de cada caso, tokens enmascarados.
- `resultados/<fase>/capturas/TA011-XX_<nombre>.png`: tarjeta de cada caso (petición a la izquierda, respuesta a
  la derecha, resultado en verde o rojo).
- `resultados/verificacion_capturas.txt`: un PNG por caso ejecutado, casos sin ejecutar y búsqueda de secretos.
- `capturas/`: regresión, salidas de la suite, git diff y pruebas en navegador.
- `codigo/`: capturas del código que se cambió.
- `intentos/`: intentos fallidos, conservados sin modificar.

## Intentos

| Intento | Qué falló | Corrección |
| --- | --- | --- |
| [01_salida_demasiado_larga](intentos/01_salida_demasiado_larga/README.md) | Con `--tb=line` la foto ocupó 5 páginas y la ventana mostraba código de salida 0 | `--tb=no -rN` y `exit $codigo` |
| [02_supabase_del_env_no_existe](intentos/02_supabase_del_env_no_existe/README.md) | El modo vivo no pudo crear usuarios: el dominio de Supabase del `.env` no existe | Pendiente: clave del proyecto vigente o un proyecto de pruebas |
| [03_credencial_alterada_sin_enmascarar](intentos/03_credencial_alterada_sin_enmascarar/README.md) | Una credencial alterada del caso 18 quedó completa en el JSON | `1aaec15`; la corrida se repitió |
| [04_recorrido_con_langsmith_activo](intentos/04_recorrido_con_langsmith_activo/README.md) | Los scripts de las fases 14 y 18 quedaron esperando a LangSmith (429, cupo agotado) | `LANGSMITH_TRACING=false`, como el recorrido oficial |
| [05_ejecucion_con_el_nombre_ta017](intentos/05_ejecucion_con_el_nombre_ta017/README.md) | La tarea se llamaba TA-017 cuando se ejecutó todo; luego pasó a TA-011 | Suite, casos y variables renombrados; todas las ejecuciones repetidas |
| [06_websocket_403_en_servidor_real](intentos/06_websocket_403_en_servidor_real/README.md) | En vivo, el caso 40 no admitía el 403 con que uvicorn rechaza el websocket | `9e2caae`; corrida en vivo repetida |
| [07_preview_sin_token_de_bypass](intentos/07_preview_sin_token_de_bypass/README.md) | El token de bypass no llegó a la suite (se lee al importarla) | Exportar `TA011_VERCEL_BYPASS` antes de lanzarla |
| [08_preview_sin_modelo_de_lenguaje](intentos/08_preview_sin_modelo_de_lenguaje/README.md) | El preview responde 503 a cada mensaje: sus claves de Groq no funcionan | Pendiente: `GROQ_API_KEYS` para el entorno Preview en Vercel |
| [09_regresion_con_el_env_de_produccion](intentos/09_regresion_con_el_env_de_produccion/README.md) | Con `RAG_BACKEND` de Supabase en el `.env`, 2 pruebas de `test_api_sma.py` fallan | Regresión con los valores por defecto (461 pasan) |

Los intentos 01 a 04 citan el nombre y los commits anteriores (TA-017, `0ef9e0e`, `c752abe`...); la
equivalencia con los commits actuales está en la sección 0 del informe.

## Observaciones

- La batería de la fase 18 sin lista de casos se cae con los 30 casos sintéticos (`KeyError: 'CIR-101'`): no
  tienen guion en `pruebas/13_guiones_por_paciente/guiones.py`. Ya pasaba antes de TA-011 (commit `89fa6a3`).
- Los scripts de fases anteriores que llaman a la API sin credencial no se modificaron: son evidencia
  histórica. Si se vuelven a ejecutar, responderán 401.
