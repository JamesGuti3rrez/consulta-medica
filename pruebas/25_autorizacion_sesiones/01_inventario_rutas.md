# TA-017 - Inventario de rutas de sesión

Fase 0 (reconocimiento). Se revisaron `backend/server/api/ai.py` completo, el servicio de sesiones
(`backend/server/orchestration/service.py`), los dos almacenes (`store.py` en memoria y `supabase_store.py`),
la autenticación (`backend/server/auth.py`), las demás rutas de la API (`api/routes.py`, `api/teaching.py`,
`rag/router.py`) y las migraciones de Supabase (`backend/supabase/migrations/0001` a `0004`).

Para confirmar que no hay más rutas con `session_id`, TA017-09 lee `/api/openapi.json` y compara la lista con
este inventario. Resultado: coincide en todas las fases.

## Rutas que reciben un `session_id` (todas en `/api/ai`)

| Operación | Método y ruta | Antes: archivo:línea (commit `0cebb31`) | Identidad que aceptaba antes | Comprobación de dueño antes | Después: archivo:línea | Protección después |
| --- | --- | --- | --- | --- | --- | --- |
| Crear sesión | `POST /api/ai/sessions` | `ai.py:189` | Opcional: `Authorization: Bearer <token Supabase>`, solo para anotar el dueño si el historial estaba activo | No aplica (crea) | `ai.py:206` | Alumno: se verifica su token (401 si Supabase lo rechaza) y la sesión queda a su nombre. Invitado: recibe `session_token` (256 bits) y el servidor guarda solo su hash |
| Leer sesión | `GET /api/ai/sessions/{session_id}` | `ai.py:199` | Ninguna | **Ninguna**: cualquiera con el UUID la leía | `ai.py:260` | `authorize_session` (`ai.py:224`) |
| Enviar mensaje | `POST /api/ai/sessions/{session_id}/message` | `ai.py:209` | Ninguna | **Ninguna**: cualquiera con el UUID escribía en la consulta | `ai.py:270` | `authorize_session` |
| Listar eventos | `GET /api/ai/sessions/{session_id}/events` | `ai.py:231` | Ninguna | **Ninguna**: cualquiera con el UUID leía los mensajes y las evidencias | `ai.py:292` | `authorize_session` |
| Cerrar sesión | `POST /api/ai/sessions/{session_id}/finish` | `ai.py:241` | Opcional: `Authorization`, solo para guardar el intento | **Parcial**: cualquiera la cerraba y veía la evaluación; solo el guardado del intento exigía al dueño | `ai.py:302` | `authorize_session` y, además, el guardado del intento exige al dueño |

## Rutas que no existen (pedidas en el prompt)

| Operación pedida | Estado en el código | Caso que lo comprueba |
| --- | --- | --- |
| Registrar eventos desde el cliente | No existe. Los eventos los escribe solo el servidor al iniciar, en cada mensaje y al cerrar | TA017-05, TA017-31 (`POST .../events` responde 405) |
| Hipótesis, exámenes, evaluación o reporte en rutas propias | No existen. Las hipótesis y el diagnóstico van en el cuerpo de `finish`; los exámenes se piden con `message` | TA017-09 |
| Reanudación | No existe ruta propia: reanudar es leer con `GET /sessions/{id}` | TA017-09 |
| Stream SSE o websocket | No existe | TA017-40 (404 al conectar, con o sin credencial) |

## Rutas que no son sesiones del simulador

- `GET /api/docente/sesion` (`api/teaching.py:61`): devuelve el usuario del panel docente a partir de su token
  (`current_user`). No recibe `session_id` y ya exige `Authorization`. Queda fuera del alcance.
- `/api/ai/status`, `/api/caso`, `/api/status`, `/api/config`, `/api/v1/rag/*`: no reciben `session_id`.

## Cómo se representa el dueño

- **Alumno registrado:** `owner_id` = id de Supabase Auth (`auth.users.id`), dentro del JSON `state` de la
  sesión (`service.py:51`). No hay columna propia: `sma_sesiones` guarda `session_id`, `case_id`, `phase` y
  `state` (jsonb). `owner_id` nunca se devuelve al navegador (`_public` usa una lista blanca).
- **Invitado:** antes no tenía ninguna identidad; la sesión quedaba con `owner_id = null` y abierta para
  cualquiera. Después tiene `access_token_hash` = SHA-256 de su credencial de capacidad, también en `state`
  (`service.py:52`) y también fuera de la respuesta pública.
- El id de sesión es un UUID versión 4 (`uuid4()`), no secuencial (TA017-01).

## Capa de datos (Supabase)

| Tabla | RLS | Políticas | Acceso desde el navegador (clave publicable o JWT de alumno) |
| --- | --- | --- | --- |
| `sma_sesiones` | Activado (`0002`) | Ninguna; además `revoke all ... from anon, authenticated` | Ninguno. Solo el servidor, con la clave secreta |
| `sma_eventos` | Activado (`0002`) | Ninguna; `revoke all` | Ninguno |
| `intentos` | Activado (`0001`) | `select` solo de las filas propias (`auth.uid() = usuario_id`); sin insert | El alumno lee solo los suyos |
| `perfiles` | Activado (`0001`) | `select` y `update` solo del propio | El alumno ve y edita solo el suyo |

El frontend no consulta `sma_sesiones` ni `sma_eventos` directamente: todo pasa por `/api/ai`. Los casos
TA017-34 a 36 lo comprueban contra Supabase real en el modo vivo.

## Dependencias TA-004 y EN-011

No aparecen en ningún archivo del repositorio (código, `docs/`, `pruebas/`, README). El backlog no está
versionado en el repositorio, así que su estado no se puede verificar desde aquí; se registra como bloqueo
de verificación en el informe.
