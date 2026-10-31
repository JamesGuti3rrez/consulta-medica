# HU-006: Proponer y registrar diagnóstico final (diseño)

Fecha: 2026-10-31. Responsable: James Bryam Gutiérrez Rubio. Rama: `hu-006-diagnostico-final`, desde `main`.

## Renumeración

La historia que se entregó el 2026-10-28 como «HU-006: Completar reporte final» (PR #2, `pruebas/26_reporte_final/`)
pasa a ser **HU-007**. Esta HU-006 es nueva. Los commits y la rama ya fusionados no se reescriben; la documentación y
los comentarios del código que hablan del reporte final pasan a decir HU-007, con una nota de equivalencia.

## Criterios de aceptación (ficha)

| Id | Criterio |
| --- | --- |
| CA1 | Campo obligatorio de diagnóstico. |
| CA2 | Validación de texto. |
| CA3 | Confirmación de cierre. |
| CA4 | Almacenamiento por estudiante, case_id, sesión e intento. |
| CA5 | No exposición de protected. |
| CA6 | Evitar doble envío. |
| CA7 | Pruebas de fallo y de acceso ajeno. |

## Qué hay hoy (main, 1fa1c3c)

- `POST /api/ai/sessions/{id}/finish` acepta `diagnosis` nulo o vacío (`FinishRequest`, solo `max_length=2000`).
  Solo el navegador exige texto.
- «Guardar y finalizar consulta» cierra de inmediato, sin confirmación.
- Si el cierre falla (red, 5xx), el simulador igual muestra la hoja de evaluación y da la consulta por cerrada.
- El diagnóstico queda en el estado de la sesión (`sma_sesiones.state.student_diagnosis`) y, solo con
  `HISTORIAL_ALUMNOS=true`, en la tabla `intentos`, que no existe en producción. No hay número de intento.
- Cerrar dos veces devuelve el mismo resultado, pero dos cierres simultáneos pueden evaluar y guardar dos veces.
- El acceso ajeno ya lo bloquea `authorize_session` (TA-011): 401 sin credencial, 404 si es ajena.

## Decisiones

Decisión del usuario: **solo se registran los alumnos con sesión iniciada**. El invitado puede cerrar su consulta
con las mismas validaciones, pero su diagnóstico no queda en la tabla nueva (la respuesta lo dice).

Las demás son decisiones del desarrollador (el usuario pidió implementarlo sin más preguntas):

1. **Tabla nueva `diagnosticos_finales`** (migración `0005_diagnosticos_finales.sql`), en lugar de `intentos`:
   `intentos` depende de `HISTORIAL_ALUMNOS` y no existe en producción; mezclarla cambiaría «Mis simulaciones».
   Columnas: `id` uuid, `session_id` uuid **único**, `usuario_id` uuid (dueño de la sesión), `case_id` text,
   `numero_intento` integer >= 1, `diagnostico` text (2..2000), `hipotesis` jsonb, `creado_en` timestamptz.
   Único `(usuario_id, case_id, numero_intento)`. RLS activado y sin políticas: solo el servidor la usa con la
   clave secreta, como `sma_sesiones`. No guarda nada de protected.
2. **Número de intento**: cantidad de diagnósticos previos del mismo alumno en el mismo caso, más uno. Si dos
   cierres de consultas distintas chocan en el número, el índice único lo rechaza y se recalcula una vez.
3. **Almacén con dos implementaciones** (`server/persistence/diagnoses.py`): en memoria para `SESSION_STORE=memoria`
   y Supabase (REST) para `SESSION_STORE=supabase`. Misma interfaz: `register(...)`, `by_session(session_id)`.
4. **Validación en el servidor** (`server/domain/final_diagnosis.py`, función pura). El texto se normaliza (NFC,
   espacios repetidos a uno, sin espacios al inicio ni al final) y se rechaza con 422 y un mensaje en español si:
   falta o es vacío; tiene menos de 3 letras; supera 2000 caracteres; tiene caracteres de control; contiene `<` o
   `>` (marcado). El navegador aplica las mismas reglas antes de enviar.
5. **Confirmación en los dos lados**: el cuerpo debe traer `confirmado: true`; sin eso, 422 y la consulta sigue
   abierta. En el simulador, «Guardar y finalizar» muestra un paso de confirmación con el diagnóstico escrito y dos
   botones: «Confirmar y cerrar» y «Seguir en la consulta».
6. **Orden del cierre** (para que un fallo no deje un cierre a medias): validar → si la sesión ya está cerrada,
   devolver lo mismo que la primera vez → registrar el diagnóstico (alumno con sesión) → cerrar la sesión. Si el
   registro falla, 503 «No se pudo registrar tu diagnóstico; la consulta sigue abierta» y la sesión no se cierra.
   Si el registro ya existía (otro envío ganó la carrera), se usa el diagnóstico registrado, no el del segundo envío.
7. **Doble envío**: en el servidor, `session_id` único y cierre idempotente; en el navegador, una bandera de envío en
   curso y los botones deshabilitados hasta la respuesta. Un segundo envío nunca cambia el diagnóstico registrado.
8. **Respuesta del cierre**: agrega `registro`: `{"guardado": true, "id", "numero_intento"}` o
   `{"guardado": false, "motivo": "invitado"}`. El simulador muestra «Diagnóstico registrado (intento N)».
9. **El simulador ya no da la consulta por cerrada si el cierre falla**: 422 muestra el motivo, 503 o red muestran
   que sigue abierta, 401/404 muestran que no tiene acceso; en todos los casos los botones vuelven a habilitarse.
10. Las suites de TA-011 y HU-007 (antes HU-006) envían ahora `confirmado: true` y un diagnóstico válido al cerrar.
    Es el contrato nuevo, no un cambio de lo que comprueban.

## No objetivos

- No se califica el texto del diagnóstico (lo compara el reporte de HU-007 con la referencia).
- No se cambia `intentos` ni «Mis simulaciones».
- No se registra a los invitados.

## Pruebas (antes y después, con foto real de cada corrida)

- Unitarias: validación (casos válidos e inválidos), almacén en memoria (numeración, único por sesión, hilos
  concurrentes), almacén Supabase con transporte simulado (insert, conflicto 409, fallos de red y 5xx).
- Suite HU006 (`tests/security/test_hu006_final_diagnosis.py`), con la preparación de TA-011, en local y en vivo:
  obligatorio, validación, confirmación, registro por alumno/caso/sesión/intento, invitado sin registro, doble envío
  secuencial y simultáneo, fallo de Supabase sin cierre y reintento, acceso ajeno (otro alumno, otro invitado, sin
  credencial), sin protected en ninguna respuesta de error ni en la fila guardada.
- Navegador real (Playwright): validación en pantalla, confirmación y «Seguir en la consulta», doble clic con una sola
  petición, fallo 503 simulado sin cierre y reintento, intento N registrado.
- Regresión completa del backend antes y después.
- En vivo contra Supabase: requiere ejecutar la migración 0005 en el SQL Editor (lo hace el usuario); los datos de
  prueba se borran al terminar.

## Despliegue

La migración 0005 debe ejecutarse en Supabase **antes** de publicar: sin la tabla, el cierre de un alumno con sesión
responde 503 (la consulta sigue abierta y nada se pierde, pero no se puede cerrar).
