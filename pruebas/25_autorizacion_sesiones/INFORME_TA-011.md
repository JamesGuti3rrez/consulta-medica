# Informe TA-011 - Autorización de sesiones y eventos

| Campo | Valor |
| --- | --- |
| PBI | TA-011 - Autorización de sesiones y eventos (Seguridad / Backend, prioridad crítica, 4 SP) |
| Responsable | James Bryam Gutiérrez Rubio |
| Rama | `ta-011-autorizacion-sesiones` (desde `main` en `0cebb31`) |
| Fecha de ejecución | 28 de octubre de 2026 (UTC). La primera ejecución, con el nombre TA-017, fue el 27 (intento 5) |
| Evidencia | `pruebas/25_autorizacion_sesiones/` (índice: `evidencia.html`) |

Este informe es la evidencia para la validación del Product Owner, no la aprobación del PBI.

## 0. Cambio de nombre: TA-017 pasa a TA-011

El PBI se llamaba TA-017 cuando se hizo el trabajo. Al renombrarlo:

- La rama `ta-017-autorizacion-sesiones` se reemplazó por `ta-011-autorizacion-sesiones`. Los 11 commits se
  reescribieron solo en el mensaje (`TA-017:` pasa a `TA-011:`); su contenido es idéntico, pero el hash cambió.
- La suite, los casos (`TA011-XX`), el marcador y las variables (`TA011_*`) se renombraron en commits nuevos, sin
  cambios de lógica.
- La ejecución anterior se conserva en `intentos/05_ejecucion_con_el_nombre_ta017/` y **todas las ejecuciones de
  este informe se repitieron** con el nombre nuevo.

| Commit anterior | Commit actual | Cambio |
| --- | --- | --- |
| `5148509` | `c8f5c26` | Pruebas HTTP de autorización de sesiones y eventos |
| `0ef9e0e` | `a4e169e` | El caso 39 revisa las líneas de autorización |
| `b07ee1c` | `cd54a74` | Autorización de propietario en todas las operaciones de sesión |
| `e158cbb` | `8864490` | Los casos en vivo se deseleccionan fuera del modo vivo |
| `5c31164` | `7442a79` | Las pruebas existentes continúan la consulta con su credencial |
| `9aa930f` | `ac7c0e1` | El simulador envía la credencial en cada petición |
| `c752abe` | `1aaec15` | El caso 18 enmascara también la credencial alterada de SN2 |
| `6224b1d` | `e4ffe0f` | Los scripts del recorrido continúan la consulta con su credencial |
| `96b5957` | `db59474` | Herramientas de ejecución y capturas |
| `4459a9d` | `0195b28` | Resultados de las ejecuciones antes y después |
| `d843e8b` | `ecf31c3` | Inventario de rutas, política de acceso e informe final |

## 1. Resumen

La auditoría confirmó la falla que motivó el PBI: **en el código de `main`, cualquiera que conociera el UUID de
una consulta podía leerla, escribir en ella, ver sus eventos y cerrarla**, fuera alumno o invitado. Se implementó
la política de acceso (sección 4) y se verificó con 40 casos de prueba.

| Ejecución | Casos ejecutados | PASA | FALLA | NO EJECUTADA | Evidencia |
| --- | --- | --- | --- | --- | --- |
| Local, **antes** del cambio (código de producción de `main`, `0cebb31`) | 37 | 14 | **23** | 3 (34 a 36, solo en vivo) | `ejecucion/local_antes_pytest.txt`, `02_local_antes_terminal.png`, `resultados/local_antes/` |
| Local, **después** del cambio | 37 | **37** | 0 | 3 (34 a 36, solo en vivo) | `ejecucion/local_despues_pytest.txt`, `04_local_despues_terminal.png`, `resultados/local_despues/` |
| En vivo, **antes** (servidor real con el código de `main` + Supabase de producción) | 40 | 17 | **23** | - | `ejecucion/vivo_antes_pytest.txt`, `03_vivo_antes_terminal.png`, `resultados/vivo_antes/` |
| En vivo, **después** (servidor real + Supabase de producción) | 40 | **40** | 0 | - | `ejecucion/vivo_despues_pytest.txt`, `05b_vivo_despues_terminal.png`, `resultados/vivo_despues/` |
| Preview de Vercel (con token de bypass) | 0 | - | - | **40** | Bloqueado: el preview no tiene modelo de lenguaje (`intentos/08_preview_sin_modelo_de_lenguaje/`) |
| Navegador real contra `localhost:3000` (después) | 4 escenarios | 4 | 0 | - | `capturas/navegador_0*.png`, `capturas/navegador_registro.json`, `ejecucion/08_navegador_terminal.png` |
| Regresión completa (`backend/tests`) | antes 424 / después 461 | antes 424 / después 461 | 0 / 0 | después 3 deseleccionadas (34 a 36) | `ejecucion/01_regresion_antes*`, `ejecucion/05_regresion_despues*` |

**Cómo se obtiene el «antes».** En un worktree de la rama se restauró el código de producción de `main`
(`git checkout 0cebb31 -- backend/server frontend/public/js`) y se ejecutó la misma suite TA-011. La foto de la
terminal muestra `git status` con esos tres archivos antes de la corrida, por eso la cabecera de
`local_antes_pytest.txt` cita el commit de la rama. La regresión «antes» se ejecutó con `main` (`0cebb31`) sin
cambios.

Los 14 casos que pasaban antes del cambio son los positivos (el dueño usa su consulta), los de rutas que no
existen (registrar eventos, stream), los de formatos raros de id, CORS y el cierre. Ninguno de los negativos de
autorización pasaba.

**El modo vivo** usa un servidor real (`npm start`, uvicorn en `127.0.0.1:3100`) con `SESSION_STORE=supabase` y
`CASE_STORE=supabase` contra el proyecto de Supabase que usa producción (`rynkx…`), el modelo de Groq y dos alumnos
temporales (`alumno.prueba.ta011.…@example.com`) que la suite crea y borra. El «antes» en vivo usa el mismo
worktree con el código de `main`. En las dos corridas `limpieza.json` registra 10 consultas creadas y borradas, 0
eventos restantes y los 2 usuarios borrados; Auth tenía 2 usuarios antes y después.

**El modo local** usa `TestClient`, que atraviesa toda la pila HTTP de FastAPI (rutas, cabeceras, dependencias,
códigos), con Supabase Auth simulado (`tests/fakes_supabase.py`) y el proveedor de LLM local. **Las pruebas en
navegador** sí usan el servidor real (`npm start`, uvicorn en el puerto 3000), el simulador real y el modelo de
Groq.

## 2. Matriz de trazabilidad

Resultado «después» (local y en vivo). Cada caso tiene su JSON en `resultados/<fase>/logs/TA011-XX.json` y su
tarjeta en `resultados/<fase>/capturas/TA011-XX_<nombre>.png`, en las fases `local_antes`, `local_despues`,
`vivo_antes` y `vivo_despues`.

| Criterio | Casos | Resultado antes | Resultado después |
| --- | --- | --- | --- |
| **CA1** GET /sessions/{id}, mensaje, eventos y cierre comprueban propietario/token | 01, 02, 03, 04, 05, 06, 09, 10, 13, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 39, 40 | 12 PASA (positivos, rutas inexistentes, ids raros, cierre), 11 FALLA | 23 PASA |
| **CA2** Usuario B recibe 403/404 sin datos de A | 10, 11, 12, 13, 14, 15, 16, 17, 26, 27, 28, 33, 37, 38, 39 (+ 34, 35, 36 en vivo) | 1 PASA (38, CORS), 14 FALLA; en vivo 34 a 36 PASA | 15 PASA; en vivo 18 PASA (34 a 36 incluidos) |
| **CA3** Sesiones anónimas con credencial de capacidad | 07, 08, 15, 16, 17, 18, 19, 20 | 1 PASA (08: el invitado usaba su sesión porque nadie pedía nada), 7 FALLA | 8 PASA |
| **CA4** Test HTTP positivo/negativo | 01, 02, 03, 04, 05, 06, 08, 18, 21, 22, 23, 24, 25, 29, 37 | 8 PASA (positivos), 7 FALLA (negativos) | 15 PASA |

Detalle por caso:

| Caso | Qué comprueba | Antes | Después |
| --- | --- | --- | --- |
| TA011-01 | A crea SA: 200, UUID v4, sin `owner_id` en la respuesta | PASA | PASA |
| TA011-02 | A lee SA | PASA | PASA |
| TA011-03 | A envía 3 mensajes a SA | PASA | PASA |
| TA011-04 | A lista los eventos de SA | PASA | PASA |
| TA011-05 | Registrar evento: la ruta no existe (405) y la lista no cambia | PASA | PASA |
| TA011-06 | A cierra SA: 200, finalizada, con evaluación | PASA | PASA |
| TA011-07 | El invitado recibe una credencial de 256 bits, única por sesión | **FALLA** (no había credencial) | PASA |
| TA011-08 | El invitado lee, conversa, lista y cierra SN1 con su credencial | PASA | PASA |
| TA011-09 | OpenAPI: solo existen las 4 rutas con `{session_id}` | PASA | PASA |
| TA011-10 | B sobre SA en las 4 operaciones: 404 | **FALLA** (200 con los datos de SA; B cerró la consulta de A) | PASA |
| TA011-11 | Ningún dato de SA en las respuestas a B | **FALLA** (id, mensajes y evidencias de SA) | PASA |
| TA011-12 | SA no cambia tras los intentos de B | **FALLA** (eventos 4 -> 6: B agregó un turno y la cerró) | PASA |
| TA011-13 | B no puede cerrar SA | **FALLA** | PASA |
| TA011-14 | SA ajena y UUID inexistente: mismo código y mismo cuerpo | **FALLA** | PASA |
| TA011-15 | Invitado 2 con su credencial sobre SN1: 404 | **FALLA** | PASA |
| TA011-16 | Invitado 1 con su credencial sobre SA: 404 | **FALLA** | PASA |
| TA011-17 | A (registrado) sobre SN1: 404 | **FALLA** | PASA |
| TA011-18 | Credencial alterada: 404; malformada: 401 | **FALLA** | PASA |
| TA011-19 | Credencial en `?token=`: 401 | **FALLA** | PASA |
| TA011-20 | La credencial de SN1 no abre SN2 ni sesiones nuevas | **FALLA** | PASA |
| TA011-21 | Sin credencial: 401 en las 4 operaciones (SA, SN2 e inexistente) | **FALLA** | PASA |
| TA011-22 | `Bearer abc`: 401 | **FALLA** | PASA |
| TA011-23 | JWT con la firma alterada: 401 | **FALLA** | PASA (en vivo, Supabase real lo rechaza: 401) |
| TA011-24 | JWT con `exp` vencido: 401; en vivo, token cerrado con `logout` | **FALLA** | PASA (en vivo: `logout` 204 y luego 401) |
| TA011-25 | Esquemas `Basic`, `Token` o sin esquema: 401 | **FALLA** | PASA |
| TA011-26 | Solo la clave publicable: 401 | **FALLA** | PASA |
| TA011-27 | `session_id = SB` en el cuerpo: se ignora y SB no recibe nada | **FALLA** (SA ya estaba cerrada por B) | PASA |
| TA011-28 | `owner_id`/`user_id = A` en el cuerpo: se ignora | **FALLA** (A leía la sesión de B) | PASA |
| TA011-29 | Ids raros (no UUID, 5000 caracteres, `../`, SQL, nulo): 4xx, nunca 500 | PASA | PASA |
| TA011-30 | Mensaje a SA cerrada: 409 | PASA | PASA |
| TA011-31 | Evento a SA cerrada: 405 y la lista no cambia | PASA | PASA |
| TA011-32 | Cerrar dos veces: 200, misma evaluación | PASA | PASA |
| TA011-33 | B sobre SA cerrada: 404 | **FALLA** | PASA |
| TA011-34 | RLS: B lee `sma_sesiones`, `sma_eventos` e `intentos` por REST | PASA (en vivo: 403; `intentos`, 404) | PASA (igual) |
| TA011-35 | RLS: B modifica o borra SA por REST | PASA (en vivo: 403 y SA intacta) | PASA (igual) |
| TA011-36 | RLS: solo la clave publicable | PASA (en vivo: 401; `intentos` y `perfiles`, 404) | PASA (igual) |
| TA011-37 | Errores sin stack trace, SQL, rutas internas ni ids ajenos | **FALLA** (por los códigos 200; los cuerpos sí eran limpios) | PASA |
| TA011-38 | CORS: un origen ajeno no recibe `Access-Control-Allow-Origin` | PASA | PASA |
| TA011-39 | Denegaciones en el log del servidor, sin tokens completos | **FALLA** (no había registro; en vivo, 200) | PASA (en vivo: 3 líneas `[autorizacion]`, sin tokens) |
| TA011-40 | No hay stream SSE ni websocket: 404 al conectar | PASA | PASA |
| TA011-41 | Regresión completa antes y después | 424 pasan | 461 pasan (0 fallan) |

## 3. Inventario de rutas y estado final

Detalle completo en `01_inventario_rutas.md` (+ `.png`).

| Ruta | Antes | Después |
| --- | --- | --- |
| `POST /api/ai/sessions` | Dueño solo si el historial estaba activo; el invitado no recibía nada | Alumno verificado (401 si Supabase rechaza el token) o invitado con `session_token` |
| `GET /api/ai/sessions/{id}` | Sin control | `authorize_session` |
| `POST /api/ai/sessions/{id}/message` | Sin control | `authorize_session` |
| `GET /api/ai/sessions/{id}/events` | Sin control | `authorize_session` |
| `POST /api/ai/sessions/{id}/finish` | Cualquiera la cerraba y veía la evaluación | `authorize_session` + el guardado del intento sigue exigiendo al dueño |

No existen rutas de registrar eventos, hipótesis, reporte, reanudación ni stream (TA011-05, 09, 31 y 40).

## 4. Política aplicada y decisiones

Detalle completo en `02_politica_acceso.md` (+ `.png`). En resumen:

- **Alumno:** solo su token de Supabase (`Authorization: Bearer`) abre sus consultas.
- **Invitado:** credencial de capacidad `session_token` de 256 bits, enviada en `X-Session-Token`. El servidor
  guarda solo su hash SHA-256 y la compara en tiempo constante. El simulador la guarda solo en memoria.
- **Sin credencial, malformada o rechazada por Supabase:** 401, antes de buscar la sesión.
- **Ajena o inexistente: 404 con el mismo cuerpo** (`{"detail": "Sesión no encontrada."}`). Se eligió 404 y no
  403 para no revelar qué consultas existen; TA011-14 lo verifica byte por byte.
- **Credencial alterada en un carácter: 404** (el prompt pedía 401). Distinguirla de una credencial válida de
  otra consulta permitiría saber si una credencial existe. Las malformadas sí dan 401.
- **Cierre:** mensajes a una consulta cerrada, 409; cerrar otra vez, 200 con la misma evaluación.
- **Si Supabase Auth no responde al iniciar**, la consulta empieza como de invitado en lugar de fallar.

## 5. Cambios de código

Cambios de producción, en commits separados de las pruebas:

| Commit | Archivo | Cambio |
| --- | --- | --- |
| `cd54a74` | `backend/server/api/ai.py` | `authorize_session` como dependencia de las 4 rutas; `session_token` al crear la consulta de un invitado; 401/404 según la política; registro `[autorizacion]` de cada denegación con la credencial enmascarada; `get_session_auth` (verificación con Supabase Auth, independiente del historial) |
| `cd54a74` | `backend/server/orchestration/service.py` | `start(..., access_token_hash)` guarda el hash en el estado; `access_of()` devuelve dueño y hash. Ninguno sale en la respuesta pública |
| `ac7c0e1` | `frontend/public/js/simulacion.js` | El simulador guarda en memoria el `session_token` y envía, en cada mensaje y al cerrar, la credencial del invitado o el token del alumno |

Pruebas y herramientas:

| Commit | Cambio |
| --- | --- |
| `c8f5c26`, `a4e169e`, `1aaec15` | Suite `backend/tests/security/test_ta011_session_authz.py` (40 casos) y su registro de evidencia con tokens enmascarados |
| `8864490` | Los casos «vivo» se deseleccionan fuera de `TA011_MODO=vivo` (aparecen como «deselected») |
| `7442a79` | Las 19 pruebas existentes que usaban las rutas sin credencial ahora envían la suya. **Dos aserciones cambian porque el contrato es más estricto, no más débil:** token rechazado al cerrar, 401 (antes 200 con `sesion_invalida`); consulta de otro alumno, 404 (antes 200 con `otro_usuario`). En los dos casos se sigue comprobando que no se guarda ningún intento |
| `e4ffe0f` | `pruebas/14_motor_clinico/probar_casos_curated.py` y `pruebas/18_.../bateria_un_solo_diagnostico.py` envían la credencial. Fase 14: 43 de 43 casos (código 0); fase 18: 13 de 13 casos con guion (código 0) |

Cambio de nombre a TA-011 (sin cambios de lógica):

| Commit | Cambio |
| --- | --- |
| `4cacae9` | La suite pasa a `test_ta011_session_authz.py` y `ta011_evidencia.py`; casos `TA011-XX`, marcador `ta011`, variables `TA011_*` |
| `d0308cd` | Los comentarios del servidor y de las pruebas citan TA-011 |
| `901edb6` | Los scripts de la evidencia usan la suite y las variables TA-011 |
| `0666f9e` | La ejecución con el nombre TA-017 pasa a `intentos/05_ejecucion_con_el_nombre_ta017/` |
| `104e52a`, `66de2a4` | Resultados de las ejecuciones repetidas y comprobación del preview |

Diff completo: `ejecucion/06_git_diff_cambios.txt` y `capturas/git_diff_cambios.png`. No se tocaron los motores
de EN-009 ni de EN-010 (`backend/server/engine/` sin cambios).

## 6. Defectos encontrados

| ID | Severidad | Defecto | Cómo reproducirlo | Evidencia | Estado |
| --- | --- | --- | --- | --- | --- |
| D-01 | **Crítica** | Lectura, escritura, eventos y cierre de cualquier consulta sin comprobar al dueño (IDOR) | Con el código de `0cebb31`, `GET /api/ai/sessions/<id ajeno>` sin credencial: 200 con todo el estado | `resultados/local_antes/capturas/TA011-10_B_sobre_SA.png`, `TA011-21_sin_credencial.png` | Corregido en `cd54a74` |
| D-02 | **Crítica** | Las consultas de invitado no tenían ninguna credencial: el UUID era el único secreto y viaja en cada URL | Crear una consulta sin token: la respuesta no trae credencial | `resultados/local_antes/capturas/TA011-07_anonimo1_crea_sesion.png` | Corregido en `cd54a74` y `ac7c0e1` |
| D-03 | Alta | Cualquiera podía cerrar una consulta ajena y ver su evaluación (el guardado del intento sí estaba protegido) | `POST /finish` de un id ajeno: 200, `phase: finalizada` | `resultados/local_antes/capturas/TA011-13_B_cierra_SA.png` | Corregido |
| D-04 | Media | Las denegaciones no quedaban registradas | - | `resultados/local_antes/capturas/TA011-39_log_de_denegados.png` | Corregido |
| D-05 | Media (entorno) | El `SUPABASE_URL` del `.env` apuntaba a un proyecto que ya no existe; producción usa otro | `nslookup` del host del `.env`: *Non-existent domain* | `intentos/02_supabase_del_env_no_existe/` | Corregido: el `.env` apunta al proyecto de producción desde el 28 de octubre |
| D-06 | Baja (fuera de TA-011) | La batería de la fase 18 se cae con los 30 casos sintéticos: no tienen guion (`KeyError: 'CIR-101'`) | `bateria_un_solo_diagnostico.py --local` sin lista de casos | `ejecucion/07_recorrido_scripts.txt` | Abierto (ya existía en `89fa6a3`) |
| D-07 | Baja (entorno) | Con `LANGSMITH_TRACING=true` y el cupo mensual de LangSmith agotado (429), los scripts quedan esperando | Correr la fase 14 sin `LANGSMITH_TRACING=false` | `intentos/04_recorrido_con_langsmith_activo/` | Abierto (`correr_suite.ps1` ya lo apaga) |
| D-08 | Media (fuera de TA-011) | El proyecto de Supabase de producción no tiene las tablas `perfiles` ni `intentos` (migración `0001`): el historial «Mis simulaciones» no puede guardar intentos allí | `GET /rest/v1/intentos` con la clave secreta: 404 `PGRST205` | `resultados/vivo_despues/limpieza.json` (`intentos_que_quedan: HTTP 404`), casos 34 y 36 | Abierto: aplicar `0001_perfiles_e_intentos.sql` o confirmar que el historial está desactivado en producción |
| D-09 | Media (entorno) | Las claves de Groq del entorno Preview de Vercel no funcionan: cada mensaje del preview responde 503 | `GET /api/ai/status` del preview: `groq-1` a `groq-3` con `available: false` (en producción, `true`) | `intentos/08_preview_sin_modelo_de_lenguaje/` | Abierto: bloquea la suite en el preview |
| D-10 | Baja (entorno) | Las pruebas dependen del `.env` de quien las corre: con el `.env` de producción (`SESSION_STORE`, `CASE_STORE` y `RAG_BACKEND` en Supabase), la suite local daba error en los 37 casos y la regresión fallaba en 2 pruebas de `test_api_sma.py` | Correr la suite o la regresión con ese `.env` sin fijar las variables | commit `5f9435d`, `intentos/09_regresion_con_el_env_de_produccion/` | Corregido en `correr_suite.ps1`; la regresión se ejecutó con los valores por defecto. Abierto para el resto del equipo: conviene que las pruebas fijen su entorno |

## 7. Bloqueos y dependencias

- **TA-004 y EN-011:** no aparecen en ningún archivo del repositorio (código, `docs/`, `pruebas/`). El backlog
  no está versionado, así que su estado no se puede verificar desde aquí. Hay que confirmarlo con el Product
  Owner.
- **Pruebas en vivo: ejecutadas.** Con el `.env` actualizado al proyecto de producción, la suite corrió contra
  Supabase real antes (23 FALLA, 17 PASA) y después (40 de 40) del cambio. La primera corrida en vivo reveló
  que el caso 40 no admitía el 403 con que uvicorn rechaza un websocket; se corrigió la prueba y se repitió
  (`intentos/06_websocket_403_en_servidor_real/`).
- **Preview de Vercel: bloqueado por el modelo de lenguaje.** Con el token de bypass, el preview
  `consulta-medica-1mjw4o7qz-...vercel.app` (commit `5f9435d`) ya responde la API: crea consultas y aplica la
  autorización (401 sin credencial). Pero sus tres claves de Groq no funcionan (D-09) y la preparación de la
  suite necesita conversar. Falta configurar `GROQ_API_KEYS` para el entorno Preview en Vercel y repetir
  (`intentos/07_preview_sin_token_de_bypass/`, `intentos/08_preview_sin_modelo_de_lenguaje/`).

## 8. Riesgos residuales

1. **RLS verificado en vivo.** Contra la base de producción, B no puede leer, modificar ni borrar
   `sma_sesiones` ni `sma_eventos` por REST con su JWT (403), y la clave publicable sola recibe 401 (TA011-34 a
   36, antes y después). Ese control no dependía de TA-011: ya protegía las tablas antes del cambio.
2. **Firma alterada y token revocado: verificados en vivo.** Supabase real rechaza el JWT con la firma alterada
   y el token de una sesión cerrada con `logout` (204), y la API responde 401 (TA011-23 y 24). Sin la clave de
   firma del proyecto no se puede emitir un JWT vencido con firma válida, así que el vencimiento por `exp` se
   sigue probando con el token alterado.
3. **Dependencia de Supabase Auth en cada petición de un alumno.** Cada operación verifica el token con
   `/auth/v1/user`: suma una llamada por mensaje y, si Supabase cae, el alumno recibe 503 (falla cerrada).
   Mejora posible: verificar el JWT localmente con las claves públicas (JWKS) del proyecto.
4. **Sin límite de peticiones.** Adivinar una credencial de 256 bits no es factible, pero no hay rate limiting en
   `/api/ai/sessions`. Crear consultas o enviar mensajes en masa consume la cuota del LLM.
5. **Registro de acceso de uvicorn.** Registra la URL completa. La API nunca acepta la credencial en la URL y el
   simulador no la pone ahí, pero si un cliente la enviara en `?token=`, quedaría en ese registro. En vivo,
   TA011-39 confirmó que las líneas `[autorizacion]` no contienen tokens completos.
6. **Consultas creadas antes del despliegue.** Las de invitado quedan inaccesibles (404). Son consultas de
   minutos; el historial de los alumnos no se afecta.
7. **Historial sin tablas en producción (D-08).** Si se activa `HISTORIAL_ALUMNOS` en producción sin aplicar la
   migración `0001`, guardar el intento fallará. No afecta a la autorización de TA-011.
8. **Recargar la página pierde la consulta del invitado.** La credencial vive solo en memoria. Antes del cambio
   el simulador tampoco retomaba una consulta al recargar.
9. **Scripts antiguos de `pruebas/`.** Los scripts de fases anteriores (07, 10 a 13, 16, 22) llaman a la API
   sin credencial: son evidencia histórica y no se modificaron. Si se vuelven a ejecutar, responderán 401.

## 9. Recomendación

**SÍ: TA-011 cumple sus cuatro criterios de aceptación con el código de la rama `ta-011-autorizacion-sesiones`.**
Verificado en local, en navegador y en vivo contra el Supabase de producción; la reserva sobre el preview se
detalla más abajo.

- **CA1:** las cuatro operaciones con `session_id` pasan por `authorize_session` y comprueban dueño o
  credencial (23 casos, todos PASA; antes 11 FALLA).
- **CA2:** B recibe 404 sin ningún dato de A en las cuatro operaciones, también con la consulta cerrada, y la
  respuesta es idéntica a la de una consulta inexistente (15 casos PASA). En vivo, B tampoco accede a las tablas
  por REST (34 a 36 PASA).
- **CA3:** las consultas de invitado usan una credencial de capacidad de 256 bits, una por consulta, solo por
  cabecera (8 casos PASA). El simulador real la usa (capturas de navegador).
- **CA4:** hay pruebas HTTP positivas y negativas automatizadas, con la misma suite antes (23 FALLA) y después
  (37 PASA en local, 40 de 40 en vivo), y regresión completa sin pruebas rotas (461 pasan).

**Reserva:** falta repetir la suite en el preview de Vercel, bloqueada porque el entorno Preview no tiene
claves de Groq que funcionen (D-09). El código del preview es el mismo que pasó 40 de 40 en vivo, y el preview
ya aplica la autorización (401 sin credencial, `ejecucion/09_preview_protegido.txt`). Cuando Vercel tenga
`GROQ_API_KEYS` en Preview, basta con `correr_suite.ps1 -Fase vercel_preview -Modo vivo` (sección 7). La
decisión final es del Product Owner.

## Verificación final

- [x] Todas las rutas del inventario tienen casos positivos (02 a 06, 08) y negativos (10, 13 a 17, 20 a 26, 33).
- [x] Cada caso ejecutado tiene su JSON y su PNG (`resultados/verificacion_capturas.txt`: ninguno falta).
- [x] Ningún token completo en capturas ni logs: el verificador no encontró ninguno en los JSON ni en las salidas
      de texto de las fases oficiales. La única excepción conocida se conserva fuera de GitHub en
      `intentos/03_credencial_alterada_sin_enmascarar/` (una credencial alterada e inválida) y motivó la
      corrección `1aaec15`.
- [x] Regresión antes (424) y después (461), con los valores por defecto de `SESSION_STORE`, `CASE_STORE`,
      `RAG_BACKEND` y `SYNTHETIC_CASE_DATA` (memoria y local), como en las regresiones anteriores.
- [x] Los intentos 6 a 9 (caso 40 demasiado estricto, preview sin token, preview sin modelo, regresión con el
      `.env` de producción) se conservan sin modificar en `intentos/`.
- [x] Datos de prueba limpios. En local todo vive en memoria y se borra al terminar. La consulta de invitado
      creada por la prueba de navegador quedó en la memoria del servidor de `localhost:3000`. En Supabase, cada
      corrida en vivo borró sus 2 alumnos temporales, sus 10 consultas y sus eventos (`limpieza.json`); Auth
      quedó con los mismos 2 usuarios que tenía.
- [x] Cada afirmación de este informe remite a un JSON, una salida `.txt` o una captura de esta carpeta.
