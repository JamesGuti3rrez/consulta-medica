# Informe TA-017 - Autorización de sesiones y eventos

| Campo | Valor |
| --- | --- |
| PBI | TA-017 - Autorización de sesiones y eventos (Seguridad / Backend, prioridad crítica, 4 SP) |
| Responsables | James + Rodrigo |
| Rama | `ta-017-autorizacion-sesiones` (desde `main` en `0cebb31`) |
| Fecha de ejecución | 27 de octubre de 2026 (UTC) |
| Evidencia | `pruebas/25_autorizacion_sesiones/` (índice: `evidencia.html`) |

Este informe es la evidencia para la validación del Product Owner, no la aprobación del PBI.

## 1. Resumen

La auditoría confirmó la falla que motivó el PBI: **en el código de `main`, cualquiera que conociera el UUID de
una consulta podía leerla, escribir en ella, ver sus eventos y cerrarla**, fuera alumno o invitado. Se implementó
la política de acceso (sección 4) y se verificó con 40 casos de prueba.

| Ejecución | Casos ejecutados | PASA | FALLA | NO EJECUTADA | Evidencia |
| --- | --- | --- | --- | --- | --- |
| Local, **antes** del cambio (código de `main`) | 37 | 14 | **23** | 3 (34 a 36, solo en vivo) | `ejecucion/local_antes_pytest.txt`, `02_local_antes_terminal.png`, `resultados/local_antes/` |
| Local, **después** del cambio | 37 | **37** | 0 | 3 (34 a 36, solo en vivo) | `ejecucion/local_despues_pytest.txt`, `04_local_despues_terminal.png`, `resultados/local_despues/` |
| En vivo (servidor real + Supabase real) | 0 | - | - | **40** | Bloqueado: `intentos/02_supabase_del_env_no_existe/` |
| Preview de Vercel | 0 | - | - | **40** | Bloqueado: `ejecucion/09_preview_protegido.txt` |
| Navegador real contra `localhost:3000` (después) | 4 escenarios | 4 | 0 | - | `capturas/navegador_0*.png`, `capturas/navegador_registro.json`, `ejecucion/08_navegador_terminal.png` |
| Regresión completa (`backend/tests`) | antes 424 / después 461 | antes 424 / después 461 | 0 / 0 | después 3 deseleccionadas (34 a 36) | `ejecucion/01_regresion_antes*`, `ejecucion/05_regresion_despues*` |

Los 14 casos que pasaban antes del cambio son los positivos (el dueño usa su consulta), los de rutas que no
existen (registrar eventos, stream), los de formatos raros de id, CORS y el cierre. Ninguno de los negativos de
autorización pasaba.

**El modo local** usa `TestClient`, que atraviesa toda la pila HTTP de FastAPI (rutas, cabeceras, dependencias,
códigos), con Supabase Auth simulado (`tests/fakes_supabase.py`) y el proveedor de LLM local. **Las pruebas en
navegador** sí usan el servidor real (`npm start`, uvicorn en el puerto 3000), el simulador real y el modelo de
Groq.

## 2. Matriz de trazabilidad

Resultado «después» (local). Cada caso tiene su JSON en `resultados/<fase>/logs/TA017-XX.json` y su tarjeta en
`resultados/<fase>/capturas/TA017-XX_<nombre>.png`, en las fases `local_antes` y `local_despues`.

| Criterio | Casos | Resultado antes | Resultado después |
| --- | --- | --- | --- |
| **CA1** GET /sessions/{id}, mensaje, eventos y cierre comprueban propietario/token | 01, 02, 03, 04, 05, 06, 09, 10, 13, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 39, 40 | 12 PASA (positivos, rutas inexistentes, ids raros, cierre), 11 FALLA | 23 PASA |
| **CA2** Usuario B recibe 403/404 sin datos de A | 10, 11, 12, 13, 14, 15, 16, 17, 26, 27, 28, 33, 37, 38, 39 (+ 34, 35, 36 en vivo) | 1 PASA (38, CORS), 14 FALLA | 15 PASA; 34 a 36 NO EJECUTADOS |
| **CA3** Sesiones anónimas con credencial de capacidad | 07, 08, 15, 16, 17, 18, 19, 20 | 1 PASA (08: el invitado usaba su sesión porque nadie pedía nada), 7 FALLA | 8 PASA |
| **CA4** Test HTTP positivo/negativo | 01, 02, 03, 04, 05, 06, 08, 18, 21, 22, 23, 24, 25, 29, 37 | 8 PASA (positivos), 7 FALLA (negativos) | 15 PASA |

Detalle por caso:

| Caso | Qué comprueba | Antes | Después |
| --- | --- | --- | --- |
| TA017-01 | A crea SA: 200, UUID v4, sin `owner_id` en la respuesta | PASA | PASA |
| TA017-02 | A lee SA | PASA | PASA |
| TA017-03 | A envía 3 mensajes a SA | PASA | PASA |
| TA017-04 | A lista los eventos de SA | PASA | PASA |
| TA017-05 | Registrar evento: la ruta no existe (405) y la lista no cambia | PASA | PASA |
| TA017-06 | A cierra SA: 200, finalizada, con evaluación | PASA | PASA |
| TA017-07 | El invitado recibe una credencial de 256 bits, única por sesión | **FALLA** (no había credencial) | PASA |
| TA017-08 | El invitado lee, conversa, lista y cierra SN1 con su credencial | PASA | PASA |
| TA017-09 | OpenAPI: solo existen las 4 rutas con `{session_id}` | PASA | PASA |
| TA017-10 | B sobre SA en las 4 operaciones: 404 | **FALLA** (200 con los datos de SA; B cerró la consulta de A) | PASA |
| TA017-11 | Ningún dato de SA en las respuestas a B | **FALLA** (id, mensajes y evidencias de SA) | PASA |
| TA017-12 | SA no cambia tras los intentos de B | **FALLA** (eventos 4 -> 6: B agregó un turno y la cerró) | PASA |
| TA017-13 | B no puede cerrar SA | **FALLA** | PASA |
| TA017-14 | SA ajena y UUID inexistente: mismo código y mismo cuerpo | **FALLA** | PASA |
| TA017-15 | Invitado 2 con su credencial sobre SN1: 404 | **FALLA** | PASA |
| TA017-16 | Invitado 1 con su credencial sobre SA: 404 | **FALLA** | PASA |
| TA017-17 | A (registrado) sobre SN1: 404 | **FALLA** | PASA |
| TA017-18 | Credencial alterada: 404; malformada: 401 | **FALLA** | PASA |
| TA017-19 | Credencial en `?token=`: 401 | **FALLA** | PASA |
| TA017-20 | La credencial de SN1 no abre SN2 ni sesiones nuevas | **FALLA** | PASA |
| TA017-21 | Sin credencial: 401 en las 4 operaciones (SA, SN2 e inexistente) | **FALLA** | PASA |
| TA017-22 | `Bearer abc`: 401 | **FALLA** | PASA |
| TA017-23 | JWT con la firma alterada: 401 | **FALLA** | PASA (simulado; ver sección 8) |
| TA017-24 | JWT con `exp` vencido: 401 | **FALLA** | PASA (simulado; ver sección 8) |
| TA017-25 | Esquemas `Basic`, `Token` o sin esquema: 401 | **FALLA** | PASA |
| TA017-26 | Solo la clave publicable: 401 | **FALLA** | PASA |
| TA017-27 | `session_id = SB` en el cuerpo: se ignora y SB no recibe nada | **FALLA** (SA ya estaba cerrada por B) | PASA |
| TA017-28 | `owner_id`/`user_id = A` en el cuerpo: se ignora | **FALLA** (A leía la sesión de B) | PASA |
| TA017-29 | Ids raros (no UUID, 5000 caracteres, `../`, SQL, nulo): 4xx, nunca 500 | PASA | PASA |
| TA017-30 | Mensaje a SA cerrada: 409 | PASA | PASA |
| TA017-31 | Evento a SA cerrada: 405 y la lista no cambia | PASA | PASA |
| TA017-32 | Cerrar dos veces: 200, misma evaluación | PASA | PASA |
| TA017-33 | B sobre SA cerrada: 404 | **FALLA** | PASA |
| TA017-34 | RLS: B lee `sma_sesiones`, `sma_eventos` e `intentos` por REST | NO EJECUTADA | NO EJECUTADA |
| TA017-35 | RLS: B modifica o borra SA por REST | NO EJECUTADA | NO EJECUTADA |
| TA017-36 | RLS: solo la clave publicable | NO EJECUTADA | NO EJECUTADA |
| TA017-37 | Errores sin stack trace, SQL, rutas internas ni ids ajenos | **FALLA** (por los códigos 200; los cuerpos sí eran limpios) | PASA |
| TA017-38 | CORS: un origen ajeno no recibe `Access-Control-Allow-Origin` | PASA | PASA |
| TA017-39 | Denegaciones en el log del servidor, sin tokens completos | **FALLA** (no había registro) | PASA |
| TA017-40 | No hay stream SSE ni websocket: 404 al conectar | PASA | PASA |
| TA017-41 | Regresión completa antes y después | 424 pasan | 461 pasan (0 fallan) |

## 3. Inventario de rutas y estado final

Detalle completo en `01_inventario_rutas.md` (+ `.png`).

| Ruta | Antes | Después |
| --- | --- | --- |
| `POST /api/ai/sessions` | Dueño solo si el historial estaba activo; el invitado no recibía nada | Alumno verificado (401 si Supabase rechaza el token) o invitado con `session_token` |
| `GET /api/ai/sessions/{id}` | Sin control | `authorize_session` |
| `POST /api/ai/sessions/{id}/message` | Sin control | `authorize_session` |
| `GET /api/ai/sessions/{id}/events` | Sin control | `authorize_session` |
| `POST /api/ai/sessions/{id}/finish` | Cualquiera la cerraba y veía la evaluación | `authorize_session` + el guardado del intento sigue exigiendo al dueño |

No existen rutas de registrar eventos, hipótesis, reporte, reanudación ni stream (TA017-05, 09, 31 y 40).

## 4. Política aplicada y decisiones

Detalle completo en `02_politica_acceso.md` (+ `.png`). En resumen:

- **Alumno:** solo su token de Supabase (`Authorization: Bearer`) abre sus consultas.
- **Invitado:** credencial de capacidad `session_token` de 256 bits, enviada en `X-Session-Token`. El servidor
  guarda solo su hash SHA-256 y la compara en tiempo constante. El simulador la guarda solo en memoria.
- **Sin credencial, malformada o rechazada por Supabase:** 401, antes de buscar la sesión.
- **Ajena o inexistente: 404 con el mismo cuerpo** (`{"detail": "Sesión no encontrada."}`). Se eligió 404 y no
  403 para no revelar qué consultas existen; TA017-14 lo verifica byte por byte.
- **Credencial alterada en un carácter: 404** (el prompt pedía 401). Distinguirla de una credencial válida de
  otra consulta permitiría saber si una credencial existe. Las malformadas sí dan 401.
- **Cierre:** mensajes a una consulta cerrada, 409; cerrar otra vez, 200 con la misma evaluación.
- **Si Supabase Auth no responde al iniciar**, la consulta empieza como de invitado en lugar de fallar.

## 5. Cambios de código

Cambios de producción, en commits separados de las pruebas:

| Commit | Archivo | Cambio |
| --- | --- | --- |
| `b07ee1c` | `backend/server/api/ai.py` | `authorize_session` como dependencia de las 4 rutas; `session_token` al crear la consulta de un invitado; 401/404 según la política; registro `[autorizacion]` de cada denegación con la credencial enmascarada; `get_session_auth` (verificación con Supabase Auth, independiente del historial) |
| `b07ee1c` | `backend/server/orchestration/service.py` | `start(..., access_token_hash)` guarda el hash en el estado; `access_of()` devuelve dueño y hash. Ninguno sale en la respuesta pública |
| `9aa930f` | `frontend/public/js/simulacion.js` | El simulador guarda en memoria el `session_token` y envía, en cada mensaje y al cerrar, la credencial del invitado o el token del alumno |

Pruebas y herramientas:

| Commit | Cambio |
| --- | --- |
| `5148509`, `0ef9e0e`, `c752abe` | Suite `backend/tests/security/test_ta017_session_authz.py` (40 casos) y su registro de evidencia con tokens enmascarados |
| `e158cbb` | Los casos «vivo» se deseleccionan fuera de `TA017_MODO=vivo` (aparecen como «deselected») |
| `5c31164` | Las 19 pruebas existentes que usaban las rutas sin credencial ahora envían la suya. **Dos aserciones cambian porque el contrato es más estricto, no más débil:** token rechazado al cerrar, 401 (antes 200 con `sesion_invalida`); consulta de otro alumno, 404 (antes 200 con `otro_usuario`). En los dos casos se sigue comprobando que no se guarda ningún intento |
| `6224b1d` | `pruebas/14_motor_clinico/probar_casos_curated.py` y `pruebas/18_.../bateria_un_solo_diagnostico.py` envían la credencial. Fase 14: 43 de 43 casos (código 0); fase 18: 13 de 13 casos con guion (código 0) |

Diff completo: `ejecucion/06_git_diff_cambios.txt` y `capturas/git_diff_cambios.png`. No se tocaron los motores
de EN-009 ni de EN-010 (`backend/server/engine/` sin cambios).

## 6. Defectos encontrados

| ID | Severidad | Defecto | Cómo reproducirlo | Evidencia | Estado |
| --- | --- | --- | --- | --- | --- |
| D-01 | **Crítica** | Lectura, escritura, eventos y cierre de cualquier consulta sin comprobar al dueño (IDOR) | Con el código de `0cebb31`, `GET /api/ai/sessions/<id ajeno>` sin credencial: 200 con todo el estado | `resultados/local_antes/capturas/TA017-10_B_sobre_SA.png`, `TA017-21_sin_credencial.png` | Corregido en `b07ee1c` |
| D-02 | **Crítica** | Las consultas de invitado no tenían ninguna credencial: el UUID era el único secreto y viaja en cada URL | Crear una consulta sin token: la respuesta no trae credencial | `resultados/local_antes/capturas/TA017-07_anonimo1_crea_sesion.png` | Corregido en `b07ee1c` y `9aa930f` |
| D-03 | Alta | Cualquiera podía cerrar una consulta ajena y ver su evaluación (el guardado del intento sí estaba protegido) | `POST /finish` de un id ajeno: 200, `phase: finalizada` | `resultados/local_antes/capturas/TA017-13_B_cierra_SA.png` | Corregido |
| D-04 | Media | Las denegaciones no quedaban registradas | - | `resultados/local_antes/capturas/TA017-39_log_de_denegados.png` | Corregido |
| D-05 | Media (entorno) | El `SUPABASE_URL` del `.env` apunta a un proyecto que ya no existe; producción usa otro | `nslookup` del host del `.env`: *Non-existent domain* | `intentos/02_supabase_del_env_no_existe/` | Abierto: bloquea las pruebas en vivo |
| D-06 | Baja (fuera de TA-017) | La batería de la fase 18 se cae con los 30 casos sintéticos: no tienen guion (`KeyError: 'CIR-101'`) | `bateria_un_solo_diagnostico.py --local` sin lista de casos | `ejecucion/07_recorrido_scripts.txt` | Abierto (ya existía en `89fa6a3`) |
| D-07 | Baja (entorno) | Con `LANGSMITH_TRACING=true` y el cupo mensual de LangSmith agotado (429), los scripts quedan esperando | Correr la fase 14 sin `LANGSMITH_TRACING=false` | `intentos/04_recorrido_con_langsmith_activo/` | Abierto |

## 7. Bloqueos y dependencias

- **TA-004 y EN-011:** no aparecen en ningún archivo del repositorio (código, `docs/`, `pruebas/`). El backlog
  no está versionado, así que su estado no se puede verificar desde aquí. Hay que confirmarlo con el Product
  Owner.
- **Pruebas en vivo (34 a 36 y la repetición de los 40 casos contra Supabase real): bloqueadas.** El `.env`
  local apunta a un proyecto de Supabase que no existe (D-05) y no se tiene la clave secreta del proyecto que
  usa producción. Esa clave hace falta solo para crear y borrar los alumnos temporales A y B. El intento quedó
  documentado: no se creó ningún usuario ni ninguna sesión.
- **Preview de Vercel: desplegado pero bloqueado.** La rama generó el preview
  `consulta-medica-coubjba2a-...vercel.app` (estado `success`), pero está protegido por Vercel Authentication
  (302 al inicio de sesión de Vercel). Hace falta un token de *Protection Bypass for Automation*.
  `correr_suite.ps1` (`TA017_VERCEL_BYPASS`) y `probar_navegador.cjs` (`VERCEL_BYPASS`) ya lo admiten.

## 8. Riesgos residuales

1. **RLS sin verificar en vivo.** Según la migración `0002`, `sma_sesiones` y `sma_eventos` tienen RLS activado,
   ninguna política y permisos revocados, lo que debería impedir todo acceso desde el navegador. Falta
   confirmarlo contra la base real (TA017-34 a 36).
2. **JWT vencido y firma alterada: probados contra Supabase simulado.** En modo local, el falso Supabase rechaza
   cualquier token que no conoce. La verificación real de firma y vencimiento la hace Supabase
   (`/auth/v1/user`) y se prueba en vivo. Además, sin la clave de firma del proyecto no se puede emitir un JWT
   vencido con firma válida: TA017-24 usa el JWT con `exp` en el pasado y, en vivo, un token de una sesión
   cerrada con `logout`.
3. **Dependencia de Supabase Auth en cada petición de un alumno.** Cada operación verifica el token con
   `/auth/v1/user`: suma una llamada por mensaje y, si Supabase cae, el alumno recibe 503 (falla cerrada).
   Mejora posible: verificar el JWT localmente con las claves públicas (JWKS) del proyecto.
4. **Sin límite de peticiones.** Adivinar una credencial de 256 bits no es factible, pero no hay rate limiting en
   `/api/ai/sessions`. Crear consultas o enviar mensajes en masa consume la cuota del LLM.
5. **Registro de acceso de uvicorn.** Registra la URL completa. La API nunca acepta la credencial en la URL y el
   simulador no la pone ahí, pero si un cliente la enviara en `?token=`, quedaría en ese registro (TA017-39 lo
   revisa en vivo).
6. **Consultas creadas antes del despliegue.** Las de invitado quedan inaccesibles (404). Son consultas de
   minutos; el historial de los alumnos está en `intentos` y no se afecta.
7. **Recargar la página pierde la consulta del invitado.** La credencial vive solo en memoria. Antes del cambio
   el simulador tampoco retomaba una consulta al recargar.
8. **Scripts antiguos de `pruebas/`.** Los scripts de fases anteriores (07, 10 a 13, 16, 22) llaman a la API
   sin credencial: son evidencia histórica y no se modificaron. Si se vuelven a ejecutar, responderán 401.

## 9. Recomendación

**SÍ: TA-017 cumple sus cuatro criterios de aceptación con el código de la rama `ta-017-autorizacion-sesiones`.**
La reserva sobre la validación en vivo se detalla más abajo.

- **CA1:** las cuatro operaciones con `session_id` pasan por `authorize_session` y comprueban dueño o
  credencial (23 casos, todos PASA; antes 11 FALLA).
- **CA2:** B recibe 404 sin ningún dato de A en las cuatro operaciones, también con la consulta cerrada, y la
  respuesta es idéntica a la de una consulta inexistente (15 casos PASA).
- **CA3:** las consultas de invitado usan una credencial de capacidad de 256 bits, una por consulta, solo por
  cabecera (8 casos PASA). El simulador real la usa (capturas de navegador).
- **CA4:** hay pruebas HTTP positivas y negativas automatizadas, con la misma suite antes (23 FALLA) y después
  (37 PASA), y regresión completa sin pruebas rotas (461 pasan).

**Reserva:** no se pudo ejecutar la capa en vivo (Supabase real, RLS y revocación de tokens) ni la repetición
en el preview de Vercel (sección 7). Antes de dar por terminado el PBI, se recomienda ejecutarlas con
`correr_suite.ps1 -Modo vivo` cuando estén disponibles la clave del proyecto de Supabase (o un proyecto de
pruebas) y el token de bypass del preview. La decisión final es del Product Owner.

## Verificación final

- [x] Todas las rutas del inventario tienen casos positivos (02 a 06, 08) y negativos (10, 13 a 17, 20 a 26, 33).
- [x] Cada caso ejecutado tiene su JSON y su PNG (`resultados/verificacion_capturas.txt`: ninguno falta).
- [x] Ningún token completo en capturas ni logs: el verificador no encontró ninguno en los JSON ni en las salidas
      de texto de las fases oficiales. La única excepción conocida se conserva fuera de GitHub en
      `intentos/03_credencial_alterada_sin_enmascarar/` (una credencial alterada e inválida) y motivó la
      corrección `c752abe`.
- [x] Regresión antes (424) y después (461).
- [x] Datos de prueba limpios. En local todo vive en memoria y se borra al terminar. La consulta de invitado
      creada por la prueba de navegador quedó en la memoria del servidor de `localhost:3000`. En Supabase no se
      creó nada (sección 7).
- [x] Cada afirmación de este informe remite a un JSON, una salida `.txt` o una captura de esta carpeta.
