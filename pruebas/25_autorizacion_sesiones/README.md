# 25. Autorización de sesiones y eventos (TA-017)

## Objetivo

TA-017 pide controles de propietario en todas las operaciones de sesión del simulador, también para los
invitados. La auditoría confirmó que en `main` (`0cebb31`) **cualquiera que conociera el UUID de una consulta
podía leerla, escribir en ella, ver sus eventos y cerrarla**. Ahora cada consulta solo la abre quien la empezó:
el alumno con su token de Supabase o el invitado con una credencial de capacidad de 256 bits.

Informe completo con la matriz de trazabilidad, los defectos y la recomendación:
[INFORME_TA-017.md](INFORME_TA-017.md). Índice visual de todas las capturas: `evidencia.html`.

## Documentos

| Archivo | Contenido |
| --- | --- |
| [01_inventario_rutas.md](01_inventario_rutas.md) (+ `.png`) | Las rutas con `session_id`: identidad y control antes y después; dueño; RLS de las tablas |
| [02_politica_acceso.md](02_politica_acceso.md) (+ `.png`) | La regla verificada, los códigos de respuesta y las decisiones (404 y no 403, credencial alterada, cierre) |
| [INFORME_TA-017.md](INFORME_TA-017.md) (+ `.png`) | Informe final para el Product Owner |

## Qué se hizo

| Commit | Cambio |
| --- | --- |
| `5148509`, `0ef9e0e` | Suite `backend/tests/security/test_ta017_session_authz.py`: casos TA017-01 a TA017-40, modo local y modo vivo, con evidencia JSON por caso |
| `b07ee1c` | **Código:** `authorize_session` en las 4 rutas, credencial de capacidad para invitados, 401/404 según la política, registro de denegaciones |
| `e158cbb` | Los casos en vivo se deseleccionan fuera del modo vivo |
| `5c31164` | Las 19 pruebas existentes que usaban las rutas sin credencial envían la suya (2 aserciones más estrictas, ver informe) |
| `9aa930f` | **Código:** el simulador envía la credencial en cada mensaje y al cerrar |
| `c752abe` | El caso 18 enmascara también la credencial alterada de SN2 (ver intento 3) |
| `6224b1d` | Los scripts del recorrido completo (fases 14 y 18) envían la credencial |

## Comandos

Desde la raíz del repositorio:

```powershell
# Suite TA-017 en modo local; deja la evidencia en resultados\<fase>\logs y ejecucion\<fase>_pytest.txt
.\pruebas\25_autorizacion_sesiones\correr_suite.ps1 -Fase local_despues

# Modo vivo: servidor real con SESSION_STORE=supabase y Supabase del .env (crea y borra 2 alumnos temporales)
.\pruebas\25_autorizacion_sesiones\correr_suite.ps1 -Fase vivo_despues -Modo vivo -BaseUrl http://127.0.0.1:3100 -LogServidor <log del servidor>

# Navegador real (servidor en marcha; para un preview protegido de Vercel, VERCEL_BYPASS=<token>)
node pruebas\25_autorizacion_sesiones\probar_navegador.cjs pruebas\25_autorizacion_sesiones\capturas

# Tarjetas PNG por caso, capturas de las salidas y evidencia.html
backend\.venv\Scripts\python.exe pruebas\25_autorizacion_sesiones\generar_capturas.py
```

Cada ejecución se hizo dentro de `pruebas\_herramientas\captura_terminal.ps1` para tener la foto real de la
terminal (`ejecucion\*_terminal.png`).

## Resultados

| Ejecución | Resultado | Evidencia |
| --- | --- | --- |
| Regresión antes (`main`) | 424 pasan | `ejecucion/01_regresion_antes.txt`, `_terminal.png` |
| Suite TA-017, local, antes | 14 PASA, **23 FALLA**, 3 solo en vivo | `ejecucion/local_antes_pytest.txt`, `02_local_antes_terminal.png`, `resultados/local_antes/` |
| Suite TA-017, local, después | **37 PASA**, 0 FALLA, 3 solo en vivo | `ejecucion/local_despues_pytest.txt`, `04_local_despues_terminal.png`, `resultados/local_despues/` |
| Regresión después | 461 pasan, 3 deseleccionadas (casos en vivo) | `ejecucion/05_regresion_despues.txt`, `_terminal.png` |
| Navegador real (localhost:3000, Groq) | El invitado conversa y cierra con su credencial; otro navegador recibe 401 sin credencial y 404 con una ajena | `capturas/navegador_0*.png`, `capturas/navegador_registro.json`, `ejecucion/08_navegador_terminal.png` |
| Fase 14 con la credencial | 43 de 43 casos, código 0 | `ejecucion/07_recorrido_scripts.txt`, `_terminal.png` |
| Fase 18 con la credencial | 13 de 13 casos con guion, código 0 | `ejecucion/07b_bateria_13_casos.txt`, `_terminal.png` |
| Suite en vivo (Supabase real) | **No ejecutada**: el proyecto de Supabase del `.env` no existe | `intentos/02_supabase_del_env_no_existe/` |
| Preview de Vercel | Desplegado, **no ejecutado**: protegido por Vercel Authentication | `ejecucion/09_preview_protegido.txt` |

Las fotos (`.png`) se guardan en el equipo y no se suben a GitHub; los JSON, las salidas `.txt` y los scripts sí.

## Estructura

- `ejecucion/`: salidas `.txt` y fotos reales de terminal.
- `resultados/<fase>/logs/TA017-XX.json`: petición y respuesta reales de cada caso, tokens enmascarados.
- `resultados/<fase>/capturas/TA017-XX_<nombre>.png`: tarjeta de cada caso (petición a la izquierda, respuesta a
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
| [03_credencial_alterada_sin_enmascarar](intentos/03_credencial_alterada_sin_enmascarar/README.md) | Una credencial alterada de TA017-18 quedó completa en el JSON | `c752abe`; la corrida se repitió |
| [04_recorrido_con_langsmith_activo](intentos/04_recorrido_con_langsmith_activo/README.md) | Los scripts de las fases 14 y 18 quedaron esperando a LangSmith (429, cupo agotado) | `LANGSMITH_TRACING=false`, como el recorrido oficial |

## Observaciones

- La batería de la fase 18 sin lista de casos se cae con los 30 casos sintéticos (`KeyError: 'CIR-101'`): no
  tienen guion en `pruebas/13_guiones_por_paciente/guiones.py`. Ya pasaba antes de TA-017 (commit `89fa6a3`).
- Los scripts de fases anteriores que llaman a la API sin credencial no se modificaron: son evidencia
  histórica. Si se vuelven a ejecutar, responderán 401.
