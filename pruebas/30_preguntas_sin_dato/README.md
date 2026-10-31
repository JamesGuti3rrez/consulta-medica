# 30. Preguntas sin dato en el caso: respuestas naturales del doctor y del paciente

Al probar la escena (fase 29) aparecieron respuestas raras que ya existían antes de unir la rama de Rodrigo y también
en producción. En los tres casos el caso no tiene el dato pedido, o el dato pertenece a otro tema.

| Pregunta | Antes | Causa | Ahora |
|---|---|---|---|
| «Realizo exploración física» (CIR-005, sin hallazgos registrados) | Doctor: «Por favor, describe los hallazgos que encuentres» | Sin hallazgos que entregar, el modelo pedía al estudiante que los aportara; la corrección existente solo actuaba cuando había hallazgos | «No hay hallazgos de exploración física registrados para este paciente.» (regla fija, sin modelo) |
| «¿Desde cuándo tiene el dolor?» (CIR-005) | Paciente: «No entendí bien, doctor. ¿Me puede hacer la pregunta de otra manera?» | Si el generador de datos sintéticos rechazaba la pregunta, respondía siempre esa frase | Responde el agente paciente con naturalidad: «El dolor empezó antes de la cirugía, pero no recuerdo la fecha exacta.» |
| «¿Desde cuándo tiene la molestia?» (MED-008) | Paciente: «Me diagnosticaron en 2003…» (año de la hipertensión) | «desde cuándo» y «hace cuánto» se tomaban siempre como inicio de un antecedente | «…noté la lesión hace unos 6 meses y desde entonces ha crecido ligeramente.» (dato del caso) |

## Cambios

| Qué | Dónde |
|---|---|
| Exploración sin hallazgos: respuesta fija del doctor | `backend/server/orchestration/star_graph.py` (marca `exploracion_sin_hallazgos`), `backend/server/ai/agents/medico_asistente.py` |
| Red de seguridad: sin datos, si el modelo pide al estudiante describir hallazgos, se dice que el dato no está disponible | `backend/server/ai/agents/base.py` |
| Rechazo del generador: responde el agente paciente; el motivo queda en `synthetic_rejection_reason` y ya no se marca como bloqueado | `backend/server/orchestration/patient_completion.py`, `star_graph.py` |
| Los controles de cifras inventadas y de evidencia no autorizada se aplican siempre que responde el agente (antes se saltaban si existía un resultado del generador, aunque respondiera el agente) | `star_graph.py` |
| «¿Desde cuándo…?» sobre la molestia actual (dolor, molestia, lesión, fiebre…) ya no se toma como inicio de un antecedente | `backend/server/engine/disclosure/synthetic_scope.py` |
| Pruebas nuevas (16) | `backend/tests/integration/test_preguntas_sin_dato.py` |
| Conversación real con el modelo y los datos sintéticos del `.env` | `pruebas/30_preguntas_sin_dato/codigo/conversacion_real.py` |

## Resultados

| Corrida | Archivo | Resultado |
|---|---|---|
| Pruebas del doctor y del paciente con el código anterior | `ejecucion/01_antes` | 5 fallan, 2 pasan (las de control) |
| Mismas pruebas con la corrección | `ejecucion/02_despues` | 7 de 7 |
| Conversación real CIR-005 tras las dos primeras correcciones | `ejecucion/03_conversacion_real_cir005` | 5 de 5 sin respuestas raras |
| Inicio de la molestia actual con el código anterior | `ejecucion/05_antes_inicio_de_la_molestia` | 5 fallan, 4 pasan (antecedentes) |
| Todas las pruebas nuevas | `ejecucion/06_despues_inicio_de_la_molestia` | 16 de 16 |
| Conversación real MED-008 (con hallazgos, datos sintéticos y examen sintético) | `ejecucion/07_conversacion_real_med008` | 5 de 5 |
| Conversación real CIR-005 final | `ejecucion/08_conversacion_real_cir005` | 5 de 5 |
| Regresión completa del backend | `ejecucion/09_regresion_backend` | 841 pasan |
| Regresión de la escena en el navegador | `ejecucion/10_regresion_escena` | 18 de 18 |

Cada corrida tiene su salida (`.txt`) y la foto real de la terminal (`_terminal.png`). Las conversaciones reales usan el
modelo de Groq: sus respuestas pueden variar en la redacción; lo que se comprueba es que no aparezcan las respuestas
raras de la tabla.

## Intentos fallidos (se conservan)

| Intento | Qué pasó |
|---|---|
| `intentos/01_prueba_de_rechazo_mal_planteada` | La primera prueba del rechazo usaba una clave no permitida, que el generador descarta sin rechazar. Se cambió por una selección mal formada (rechazo real) y la corrida «antes» se repitió con el código anterior. |
| `intentos/02_sondeo_sin_control_del_inicio` | La conversación real con MED-008 mostró «Me diagnosticaron en 2003» ante «¿Desde cuándo tiene la molestia?», pero el script no lo marcaba. Se añadió ese control y se corrigió la causa. |
