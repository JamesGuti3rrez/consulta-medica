# HU-006 - Contrato del reporte final

## Rutas

| Ruta | Quién | Respuesta |
| --- | --- | --- |
| `GET /api/ai/sessions/{session_id}/report` | El dueño: el alumno con `Authorization: Bearer <token>` o el invitado con `X-Session-Token` (regla de TA-011, `authorize_session`) | **200** con el reporte si la consulta está finalizada; **409** `{"detail": "El reporte estará disponible al terminar la consulta."}` si sigue abierta |
| | Sin credencial o con una malformada | **401**, antes de buscar la consulta |
| | Otra persona, o una consulta que no existe | **404** `{"detail": "Sesión no encontrada."}`, el mismo cuerpo en los dos casos |
| `POST /api/ai/sessions/{session_id}/finish` | El dueño | Lo de siempre (estado, evaluación, intento guardado) y además `report`, idéntico al de `GET /report` |

El cierre guarda el diagnóstico y las hipótesis que envía el alumno en el estado de la consulta
(`student_diagnosis`, `student_hypotheses`) **solo la primera vez**; cerrar otra vez no los cambia. Esos campos
no salen en la respuesta pública de la sesión, solo dentro del reporte.

## Campos del reporte y su fuente

Todo sale del caso de la consulta (`public`, `on_request`, `protected`) y de la propia sesión. El reporte no llama
al RAG ni al modelo de lenguaje, y lo arma el motor de evaluación
(`ClinicalEvaluationEngine.report`, `backend/server/engine/evaluation/report.py`), el único que, junto al de
seguridad, puede leer la parte protegida del caso.

| Campo | Contenido | Fuente |
| --- | --- | --- |
| `case_id`, `finished_at` | Caso y hora de cierre | sesión |
| `patient`, `chief_complaint` | Alias, edad, sexo; motivo de consulta | `public.patient`, `public.chief_complaint.text` |
| `diagnosis.student` | Lo que escribió el alumno (vacío si la consulta se cerró antes de HU-006) | sesión |
| `diagnosis.reference`, `diagnosis.synonyms` | Diagnóstico de referencia | `protected.diagnosis` |
| `hypotheses` | Hipótesis del alumno, activas y descartadas con su motivo | sesión |
| `differentials` | Diagnósticos diferenciales del caso | `protected.differentials[].name` |
| `score` | `score`, `earned_weight`, `total_weight`, `completed_questions`, `total_questions` | evaluación guardada al cerrar |
| `key_questions.obtained` / `.missing` | Cada pregunta clave puntuable: `id`, `topic`, `weight`, `critical`, `error_type`, `error_name`, `why`, `helps_discard` | `protected.evaluation.key_questions` + diferenciales |
| `tests` | `recommended_requested`, `recommended_missing`, `optional_requested`, `unnecessary_requested` (cada uno `{name, label}`) y `other_indications` | `protected.evaluation.tests` + evidencia pedida |
| `treatment.proposed` | Cada mensaje del alumno reconocido como propuesta de tratamiento, con sus alertas de seguridad | eventos de la sesión (`intent = propose_treatment`) |
| `treatment.reference_summary`, `.key_actions` | Tratamiento de referencia | `protected.treatment_reference` |
| `revealed_evidence` | Cada dato revelado en la consulta: `evidence_id`, `label`, `text` | `public` y `on_request`, en el orden en que se revelaron |
| `recommendations` | Una por tipo de omisión, más la de seguridad si hubo alertas; si no falta nada, la de mantener el orden | reglas fijas |

## Reglas

- **Preguntas puntuables.** Las mismas que puntúa el motor: no cuentan las que solo piden evidencia que el
  doctor entrega al presentar el caso (motivo de consulta y signos iniciales).
- **Por qué de lo que faltó.** Frase fija por tipo de omisión, sin texto clínico nuevo:
  - negligencia: «Dato de seguridad: se pregunta antes de indicar un tratamiento.»
  - anamnesis incompleta: «Forma parte de una historia clínica completa.»
  - razonamiento clínico: «Orienta o confirma el diagnóstico del caso.»
  Más «Crítico» si la pregunta lo es y «Ayudaba a descartar: …» con los diferenciales cuyo
  `discard_evidence_ids` comparte evidencia con la pregunta.
- **Exámenes.** Un examen de `tests` corresponde a la evidencia de `on_request` cuyo último segmento del id es su
  nombre o empieza por `nombre_` (`tomografia` → `MED-900.imagen.tomografia_craneo`). Si no corresponde a ninguna
  evidencia (34 de 110 entradas, todas en los 10 casos del examen original, como «valoración de hematología
  urgente»), va a `other_indications`, con guiones bajos cambiados por espacios.
- **Ninguna fuente ajena.** Se descarta cualquier `evidence_id` que no empiece por `<case_id>.`.
- **Datos con valor y unidad.** Si un dato no tiene `text` (signos vitales del caso de prueba), se muestra como
  «74 /min».
- **Diagnóstico escrito.** No se califica automáticamente: se muestra junto al de referencia.

## En la pantalla

La hoja de evaluación (`frontend/public/simulacion.html`, `js/simulacion.js`) pinta el reporte que llega en la
respuesta de `finish`, con los estilos de la hoja actual. Todo texto se inserta como texto (`textContent`), nunca
como HTML. Si el reporte no llega, se muestra «No se pudo obtener el reporte de esta consulta».
