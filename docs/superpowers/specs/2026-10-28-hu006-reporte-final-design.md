# HU-006: Completar reporte final (diseño)

Fecha: 2026-10-28. Responsable: James Bryam Gutiérrez Rubio. Ficha del PBI: prioridad baja, 1 SP. Diseño aprobado
por el usuario el 2026-10-28, con la indicación de que quede completo.

## Historia y criterios de aceptación

> HU-006 — Completar reporte final. Reporte solo poscierre y con propietario validado. Incluye diagnóstico de
> referencia, propuesta, tratamiento, puntajes y evidencia revelada; ninguna fuente ajena al `case_id`; E2E.

| Criterio | Qué significa en este diseño |
| --- | --- |
| CA1 Solo poscierre | El reporte solo existe cuando la consulta está en fase `finalizada`. Antes, el servidor lo niega. |
| CA2 Propietario validado | Solo el dueño de la consulta lo obtiene: el alumno con su token o el invitado con su credencial de capacidad (la misma regla de TA-011). Cualquier otro recibe 404 o 401 como en TA-011. |
| CA3 Contenido completo | Diagnóstico de referencia, la propuesta del alumno (diagnóstico e hipótesis), tratamiento (de referencia y el que propuso el alumno, con sus alertas), puntajes (total y por pregunta clave) y la evidencia revelada. |
| CA4 Ninguna fuente ajena al `case_id` | Todo lo que contiene el reporte sale del caso de esa consulta y de la propia sesión; ningún dato de otro caso, del RAG ni del modelo de lenguaje. |
| CA5 E2E | Se prueba de punta a punta: navegador real, servidor real y Supabase real. |

## Por qué

Hoy la hoja de evaluación solo muestra conteos («Obtuviste 3 de 5 datos clave», «Anamnesis incompleta: 2 datos
clave sin obtener»). El alumno no sabe **cuáles** obtuvo, **cuáles** le faltaron, **por qué** importaban, cuál
era el diagnóstico ni cuál era el tratamiento. Los casos ya tienen toda esa información en `protected`; el motor
la usa para puntuar pero no la entrega.

## Decisiones del usuario

- El reporte lo ve **solo el alumno que hizo la consulta**, al cerrarla y mientras la consulta exista.
- Estructura **por secciones** (boceto aprobado: `.superpowers/brainstorm/.../reporte-secciones-v2.html`), con
  el «por qué» de cada dato que faltó, bien estructurado y sin llenar de texto.
- **No cambiar el diseño actual** de la hoja de evaluación (portapapeles, sello del puntaje, casillas, firma):
  se agregan secciones con los mismos estilos.
- Debe quedar completo y justificado con evidencia, como TA-011.

## Diseño

### 1. Servidor: `GET /api/ai/sessions/{session_id}/report`

- Protegida con la dependencia `authorize_session` de TA-011 (401 sin credencial, 404 ajena o inexistente).
- Si la consulta no está finalizada: **409** `{"detail": "El reporte estará disponible al terminar la consulta."}`.
- Respuesta 200 con el reporte (estructura en la sección 3). Siempre el mismo reporte para la misma consulta.
- `POST /finish` sigue devolviendo lo mismo que hoy y además el reporte en `report`, para que la pantalla no haga
  una segunda llamada al cerrar.
- El inventario de rutas de TA-011 pasa de 4 a 5 rutas con `session_id`; el caso TA011-09 se actualiza en un
  commit propio.

### 2. Guardar la propuesta del alumno en la sesión

`finish` recibe hoy `diagnosis` e `hypotheses` (FinishRequest) pero solo los guarda en la tabla `intentos`, que
no existe en producción. Se guardan también en el estado de la sesión (`student_diagnosis`,
`student_hypotheses`) al cerrar. Cerrar otra vez no los cambia (el cierre ya es idempotente).

### 3. Contenido del reporte (todo derivado del caso y de la sesión)

| Sección | Fuente |
| --- | --- |
| Encabezado: paciente, motivo, fecha de cierre | `public.patient`, `public.chief_complaint`, `finished_at` |
| Diagnóstico: el del alumno y el de referencia (con sinónimos) | sesión; `protected.diagnosis` |
| Hipótesis del alumno (activas y descartadas con su motivo) | sesión |
| Diagnósticos diferenciales del caso | `protected.differentials[].name` |
| Puntaje: total, peso obtenido y total, preguntas obtenidas y totales | evaluación ya calculada |
| Preguntas clave obtenidas: nombre y peso | `protected.evaluation.key_questions` |
| Preguntas clave que faltaron: nombre, peso, tipo de omisión, si era crítica y el «por qué» | ídem + diferenciales |
| Exámenes: recomendados pedidos y no pedidos, opcionales pedidos, innecesarios pedidos | `protected.evaluation.tests` + evidencia pedida (un examen corresponde a la evidencia de `on_request` cuyo id termina en su nombre) |
| Otras indicaciones del caso: entradas de `tests` sin evidencia asociada (34 de 110, todas en los 10 casos del examen original, p. ej. «valoración de hematología urgente») | se listan sin casilla de pedido/no pedido, porque no se pueden pedir en la consulta |
| Tratamiento propuesto por el alumno y alertas de seguridad | eventos de la sesión con intención de proponer tratamiento |
| Tratamiento de referencia: resumen y acciones clave | `protected.treatment_reference` |
| Evidencia revelada: etiqueta y texto de cada dato | `public` y `on_request` filtrados por los ids revelados |
| Recomendaciones | las mismas reglas por tipo de omisión que ya usa la pantalla, movidas al servidor |

**El «por qué» de un dato que faltó** se arma solo con datos del caso, sin texto clínico nuevo:
- el tipo de omisión con una frase fija por tipo (negligencia: dato de seguridad antes de tratar; anamnesis
  incompleta: parte de la historia clínica; razonamiento clínico: dato que orienta el diagnóstico);
- «Crítico» si `critical` es verdadero;
- «Ayudaba a descartar: X, Y» con los diferenciales cuyo `discard_evidence_ids` incluye alguno de sus
  `evidence_ids`.

**No se califica el diagnóstico escrito** (anti-objetivo: marcar mal a quien escribió un sinónimo). Se muestra
junto al de referencia; la pantalla ya dice que el puntaje no lo califica.

### 4. Ninguna fuente ajena al `case_id`

- El reporte se arma con una función pura que recibe la sesión y el caso de esa sesión; no llama al RAG ni al LLM.
- Cada `evidence_id` del reporte debe empezar con `<case_id>.`; los de otros casos se descartan.
- Se verifica con pruebas que recorren el reporte entero de cada uno de los 43 casos curados y buscan ids, nombres
  de diagnóstico o textos de cualquier otro caso.

### 5. Pantalla

- `showEvaluation` pinta las secciones nuevas del boceto con los estilos de la hoja actual (`sheet-section`,
  `sheet-list-ok`, `sheet-list-miss`, `sheet-fields`, `stamp`) más unas pocas clases nuevas para las etiquetas y los
  pliegues.
- Toma los datos del reporte que devuelve `finish`; si se reabre la hoja, usa ese mismo reporte. Si el reporte no
  llega (servidor sin conexión), se muestra el mensaje de error que ya existe.
- Todo texto que viene del servidor se inserta como texto, nunca como HTML.

### 6. Datos

10 de las 253 preguntas clave tienen como `topic` el enunciado completo del examen original («Traducción al
español: …»). Las 10 son la `kq1` de los casos del examen original y apuntan al motivo de consulta, que es
evidencia inicial: el motor ya las excluye del puntaje y no aparecen en el reporte. No se modifican los datos; una
prueba recorre los reportes de los 43 casos y comprueba que ningún nombre de pregunta clave supera 120
caracteres.

## Evidencia (como TA-011)

Carpeta `pruebas/26_reporte_final/` con:
- Suite HTTP `backend/tests/integration/test_hu006_report.py` con casos `HU006-XX`, modo local y modo vivo,
  evidencia JSON por caso y tarjeta PNG; antes (código sin la ruta: 404 o 405) y después.
- Prueba de contenido sobre los 43 casos curados (CA3 y CA4).
- E2E en navegador real (Playwright): consulta completa, cierre, la hoja muestra cada sección; otro navegador no
  obtiene el reporte; pedirlo antes de cerrar responde 409. Contra el servidor local con el Supabase de
  producción y, si las claves de Groq del preview funcionan, contra el preview de Vercel.
- Regresión completa antes y después; fotos reales de terminal; intentos fallidos conservados; informe
  `INFORME_HU-006.md` y el Word y PDF en `Entregables/07_HU-006_Reporte_final/`.

## Fuera de alcance

- Ver el reporte desde «Mis simulaciones» o desde el panel docente (depende de las tablas `perfiles` e `intentos`,
  que no existen en producción, y de otra historia).
- Calificar automáticamente el diagnóstico escrito.
- Escribir explicaciones clínicas nuevas por diferencial (no hay revisión médica).
- Exportar el reporte a PDF.

## Restricciones

- Rama `hu-006-reporte-final` creada desde `ta-011-autorizacion-sesiones` (depende de su autorización; TA-011
  aún no está en `main`).
- Un commit por cambio; mensajes y documentos en español, sin emojis; sin coautoría de Claude.
- Las pruebas fijan su entorno (`SESSION_STORE`, `CASE_STORE`, `RAG_BACKEND`, `SYNTHETIC_CASE_DATA`,
  `LANGSMITH_TRACING`), porque el `.env` apunta a producción (hallazgo D-10 de TA-011).
- Las pruebas en vivo crean y borran sus propios usuarios y consultas en el Supabase de producción.

## Decisiones tomadas por Claude (para revisar)

1. 409 para pedir el reporte de una consulta abierta (el dueño ya está autorizado, así que no revela nada).
2. El reporte también va en la respuesta de `finish`.
3. El «por qué» con frase fija por tipo + crítico + diferenciales que ayudaba a descartar.
4. No calificar el diagnóstico escrito.
5. Rama desde `ta-011-autorizacion-sesiones`.
6. Las entradas de `tests` que no corresponden a un examen pedible se muestran como «otras indicaciones del
   caso», sin casilla.
7. Las 10 preguntas clave con enunciado largo no se corrigen: nunca llegan al reporte.
