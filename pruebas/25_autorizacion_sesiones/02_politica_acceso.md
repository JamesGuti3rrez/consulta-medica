# TA-017 - Política de acceso a las sesiones del simulador

Esta es la regla que verifican los casos TA017-01 a TA017-40 y la que aplica el código desde el commit
`b07ee1c` (`authorize_session`, `backend/server/api/ai.py:224`).

## Quién puede operar sobre una sesión

| Tipo de sesión | Credencial que la abre | Dónde se envía |
| --- | --- | --- |
| De un alumno registrado (creada con su token) | Solo el token de Supabase **del mismo alumno** (su `user_id` debe ser el `owner_id` de la sesión) | `Authorization: Bearer <access_token>` |
| De un invitado (creada sin token) | Solo la **credencial de capacidad** que recibió al crearla | `X-Session-Token: <session_token>` |

- **Credencial de capacidad:** `secrets.token_urlsafe(32)`: 256 bits aleatorios, 43 caracteres base64url
  (el mínimo pedido era 128 bits). Se entrega una sola vez, en la respuesta de `POST /api/ai/sessions`
  (`session_token`). El servidor guarda solo su hash SHA-256 en el estado de la sesión y la compara en tiempo
  constante (`hmac.compare_digest`). El simulador la mantiene solo en memoria: no va a `localStorage`, ni a
  la URL, ni a los registros.
- **Una credencial por sesión:** la de SN1 no abre SN2 ni ninguna sesión creada después (TA017-20).
- **Un alumno no hereda las sesiones de invitado** aunque esté conectado (TA017-17).
- **La credencial solo se acepta en la cabecera.** En la URL (`?token=`) se ignora y la petición responde 401
  (TA017-19): así no queda en el historial del navegador ni en los registros de acceso.

## Códigos de respuesta

| Situación | Código | Cuerpo | Caso |
| --- | --- | --- | --- |
| Sin `Authorization` ni `X-Session-Token` | 401 | `{"detail": "Inicia sesión o vuelve a empezar la consulta para continuar."}` | TA017-21 |
| `Authorization` con otro esquema (`Basic`, `Token`, sin esquema) o vacío | 401 | igual | TA017-25 |
| Token que Supabase rechaza (malformado, firma alterada, vencido, sesión cerrada, clave publicable) | 401 | igual | TA017-22 a 24, 26 |
| `X-Session-Token` malformado (largo o alfabeto incorrecto) | 401 | igual | TA017-18 |
| Credencial válida, pero la sesión es de otro (alumno o invitado) | **404** | `{"detail": "Sesión no encontrada."}` | TA017-10, 15 a 17, 20 |
| Credencial bien formada que no corresponde a la sesión (por ejemplo, alterada en un carácter) | **404** | igual | TA017-18 |
| UUID que no existe | 404 | igual, byte por byte | TA017-14 |
| Mensaje a una sesión cerrada (por su dueño) | 409 | `{"detail": "La sesión ya finalizó."}` | TA017-30 |
| Cerrar una sesión ya cerrada | 200 | la misma evaluación, sin recalcular ni duplicar el intento | TA017-32 |
| Supabase Auth no responde al verificar un token | 503 | `{"detail": "No se pudo verificar la sesión con Supabase."}` | (no se provoca en las pruebas) |

## Decisiones tomadas (regla 6: ante la duda, lo más seguro)

1. **404 y no 403 para lo ajeno.** Un 403 confirmaría que la sesión existe. Con 404 y el mismo cuerpo que una
   sesión inexistente no se puede saber si un UUID corresponde a una consulta real (TA017-14 compara los dos
   cuerpos byte por byte).
2. **401 antes de buscar la sesión.** La falta de credencial, las malformadas y los tokens que Supabase rechaza
   se resuelven antes de consultar el almacén. Así, el 401 tampoco revela si la sesión existe.
3. **Credencial alterada: 404, no 401.** El prompt pedía 401. No se puede distinguir «credencial inventada»
   de «credencial válida de otra sesión» sin buscar la credencial en todas las sesiones, y ese 401 serviría
   para saber si una credencial existe en otro lado. Las credenciales malformadas sí responden 401.
4. **Cierre:** después de cerrar no se aceptan mensajes (409, que ya existía). No hay ruta para escribir
   eventos, así que no se pueden agregar a una sesión cerrada (TA017-31: 405). Cerrar dos veces es idempotente
   (200, misma evaluación), nunca 500.
5. **Al iniciar, si Supabase Auth no responde**, la consulta empieza como de invitado, con su credencial, en vez
   de fallar (es lo que ya hacía el código). Si Supabase responde que el token no vale, la respuesta es 401.
6. **Sesiones creadas antes del cambio:** no tienen `access_token_hash`. Si eran de invitado, quedan
   inaccesibles (404); si eran de un alumno, solo él las abre. Son consultas de minutos, sin datos que se
   pierdan: el historial está en `intentos`.
7. **Registro de denegaciones:** cada 401 y 404 de autorización escribe en el log del servidor una línea
   `[autorizacion] <código> <método> <ruta> <quién> motivo=<motivo>`. «Quién» es el id del alumno o la
   credencial enmascarada (6 primeros caracteres, «…» y 4 últimos), nunca el token completo (TA017-39).

## Capa de datos

`sma_sesiones` y `sma_eventos` no tienen políticas RLS y tienen los permisos revocados para `anon` y
`authenticated`. Solo el servidor las lee y escribe, con la clave secreta. La autorización se aplica entonces
en la API; la base de datos impide además cualquier acceso directo desde el navegador (TA017-34 a 36).
