# TA-007 — Validación adversarial y guardrails

## Guía de insumos para redactar el informe final

Este documento consolida la arquitectura existente, los cambios y las pruebas efectivamente ejecutadas para TA-007. Sirve como base para redactar el informe técnico y completar con las capturas del usuario. No reemplaza los registros de pytest ni afirma validación en producción.

## Alcance y objetivo

El backlog vigente define TA-007 como **Validación adversarial y guardrails**. Su objetivo es comprobar el aislamiento entre casos, la fidelidad a la evidencia autorizada y la protección del diagnóstico frente a solicitudes adversariales.

Criterios registrados en `pruebas/Sprint2/alcance.json`:

- Probar sinónimos, solicitudes entre roles, mezcla de `case_id` y datos inexistentes.
- Evitar que contenido prohibido llegue al frontend.
- Mantener logs saneados y enlazables con `evidence_id`.
- Comprobar tanto la ruta positiva como los bloqueos.

**Límite importante:** TA-007 no crea desde cero el motor de evaluación clínica ni introduce reglas de prescripción. El repositorio ya contenía el motor de evidencia y las barreras de divulgación. En esta tarea se reforzó el routing para aclarar solicitudes de varios agentes, se validaron transiciones de estado y se agregaron pruebas de integración y adversariales para verificar los componentes existentes.

## Arquitectura existente

1. **Enrutamiento determinista:** `backend/server/orchestration/router.py` selecciona la intención y el agente. Las solicitudes que mezclan categorías de agentes se dirigen al médico asistente para aclaración; una solicitud específica conserva la ruta de su agente.
2. **Control de estado:** `backend/server/engine/state_machine/service.py` hace avanzar fases clínicas de manera monotónica, mantiene `CIERRE` hasta que se ejecuta la finalización explícita y no reabre `FINALIZADA`. Rechaza fases e intenciones inválidas.
3. **Política de divulgación:** `backend/server/engine/disclosure/policy.py` autoriza IDs de evidencia por agente, intención, requisitos y caso activo.
4. **Contexto mínimo:** `backend/server/engine/disclosure/context.py` construye el contexto que reciben los agentes sin incluir el bloque `protected`; evidencia previamente revelada solo se agrega según rol y estado de divulgación.
5. **Aislamiento y canonización:** `backend/server/orchestration/star_graph.py` limita la recuperación a los IDs autorizados, descarta IDs de otros casos y sustituye texto recuperado por el texto canónico del caso antes de formar el contexto.
6. **Guardrail de salida:** `backend/server/guardrails/output_guard.py` compara la respuesta con términos protegidos normalizados. Si detecta una fuga, el flujo sustituye la salida por un mensaje seguro, elimina sus IDs citados y registra el motivo sin repetir el término bloqueado.
7. **Evaluación:** `backend/server/engine/evaluation/service.py` calcula el puntaje ponderado a partir de evidencias recabadas y preguntas clave del caso. Las evidencias iniciales entregadas al presentar el caso se excluyen del puntaje como omisiones del alumno.
8. **Reporte final:** `backend/server/engine/evaluation/report.py` y `backend/server/orchestration/service.py` generan el reporte una vez finalizada la consulta. La evidencia se filtra al `case_id` de la sesión; el puntaje se deriva de evidencia, mientras el diagnóstico escrito por el alumno queda registrado por separado.
9. **Auditoría saneada:** `backend/server/tracing/sanitize.py` permite una proyección de campos explícitamente seguros —incluidos `case_id`, `evidence_ids`, estado de bloqueo y proveedor—, sin texto del mensaje, respuesta clínica ni credenciales.

La lógica de seguridad clínica existente en `backend/server/engine/safety/service.py` comprueba propuestas contra alergias y contraindicaciones documentadas. **TA-007 no añade, recomienda ni modifica prescripciones:** esa lógica se menciona como componente preexistente, no como nuevo comportamiento de esta tarea.

## Cambios realizados para TA-007

- `backend/server/orchestration/router.py`: identifica solicitudes simultáneas dirigidas a distintos agentes y las envía al médico asistente para aclaración. Las solicitudes específicas conservan la prioridad correcta.
- `backend/server/engine/state_machine/service.py`: valida fase e intención; la fase de cierre no retrocede ante nuevos turnos y la fase finalizada sigue siendo terminal.
- `backend/tests/unit/test_router.py`: pruebas de ambigüedad, fallback determinista, prioridad de diagnóstico/cierre y prioridad de exámenes específicos.
- `backend/tests/unit/test_state_machine.py`: pruebas de continuidad en cierre y rechazo explícito de entradas inválidas.
- `backend/tests/integration/test_direct_dialogue.py`: pruebas de aclaración de solicitudes ambiguas y continuidad del diálogo hasta la finalización explícita.
- `backend/tests/integration/test_ta007_security_evaluation.py`: nuevas pruebas de bloqueo de salida protegida, traza saneada, aislamiento de IDs de otros casos, solicitudes con IDs inexistentes y coherencia de evidencia, puntaje y diagnóstico final.

No se modificaron las reglas de tratamiento/prescripción, el frontend, Supabase ni la política de RAG.

## Pruebas ejecutadas y resultados

Los siguientes resultados fueron aportados desde la ejecución local de pytest. Ambos XML muestran `errors="0"`, `failures="0"` y `skipped="0"`.

| Bloque | Resultado | Evidencia |
|---|---:|---|
| Routing, máquina de estados, diálogo directo, reanudación HU-009 y seguridad/evaluación | 26 pasaron en 3.86 s | `pruebas/TA-007/security-evaluation.xml` y `.txt` |
| Suite adversarial TA-007, guardrails, aislamiento de contexto/RAG y seguridad/evaluación | 19 pasaron en 1.34 s | `pruebas/TA-007/adversarial.xml` y `.txt` |
| Validación de routing/estados después del Undo | 23 pasaron en 2.24 s | `pruebas/TA-007/recovery-2.xml` y `.txt` |

Los bloques de 26 y 19 pruebas se solapan en las tres pruebas de `test_ta007_security_evaluation.py`; **no se deben sumar como 45 pruebas únicas**. La suite de 23 también es un resultado anterior que está contenido, con distinta selección, en la validación posterior de 26.

Cobertura adversarial observada:

- Diagnóstico protegido y sinónimos, incluyendo diferencias de mayúsculas.
- Bloqueo de respuestas de agentes y del paciente que contienen términos protegidos.
- Recuperación contaminada con IDs de otro caso y texto manipulado; solo se conserva evidencia canónica permitida.
- Rechazo de citas de evidencia pertenecientes a otro caso.
- Rechazo de cifras clínicas inventadas sin respaldo.
- Inyección de instrucciones y solicitudes fuera del alcance clínico.
- Ruta positiva de examen autorizado y verificación de metadatos de auditoría saneados.
- Aislamiento de `protected` del contexto del agente.
- Coherencia entre evidencia de eventos, evidencia acumulada, evaluación ponderada y reporte final.
- Registro del diagnóstico del alumno separado del puntaje calculado por evidencia.

Las ejecuciones usaron pruebas locales con `TestClient`, fixtures y proveedores controlados. No son pruebas en Vercel, ni usan un LLM real o Supabase real para verificar el comportamiento descrito. No certifican validez clínica ni reemplazan revisión humana.

## Comandos reproducibles

Ejecutar desde `D:\julio\consulta-medica\backend`:

```powershell
.\.venv\Scripts\python.exe -m pytest -vv tests\unit\test_router.py tests\unit\test_state_machine.py tests\integration\test_direct_dialogue.py tests\integration\test_hu009_resume.py tests\integration\test_ta007_security_evaluation.py --junitxml=..\pruebas\TA-007\security-evaluation.xml
```

```powershell
.\.venv\Scripts\python.exe -m pytest -vv tests\sprint2\test_ta007.py tests\security\test_guardrails.py tests\security\test_context_isolation.py tests\security\test_rag_authorization_boundary.py tests\integration\test_ta007_security_evaluation.py --junitxml=..\pruebas\TA-007\adversarial.xml
```

En Windows, puede agregarse `--basetemp=..\pruebas\TA-007\<directorio-temporal-nuevo>` si pytest vuelve a presentar problemas de permisos en su directorio temporal. Usar un directorio diferente en cada ejecución y no apuntar a una carpeta con archivos que se deban conservar.

## Capturas que debe agregar el usuario

Adjuntar capturas originales de la terminal con las ejecuciones y, si dispone de ellas, del flujo relevante de la aplicación. Mantenerlas sin editar y conservar sus archivos originales junto con el informe.

- **Figura 1 — Suite integración/seguridad:** ejecución que termina con `26 passed` y sin fallos.
- **Figura 2 — Suite adversarial:** ejecución que termina con `19 passed` y sin fallos.
- **Figura 3 — Bloqueo de divulgación:** respuesta segura ante intento de revelar el diagnóstico protegido, si se tomó captura de la app o prueba.
- **Figura 4 — Aislamiento/evidencia:** evidencia autorizada asociada al caso activo y rechazo de referencias ajenas, si existe captura.
- **Figura 5 — Puntaje/reporte final:** pantalla del resultado donde se observe el puntaje y el diagnóstico final registrado por separado, si existe captura.

Si una captura no existe, eliminar su figura del informe final; no recrear ni simular resultados. Los XML/TXT de pytest son la evidencia textual primaria; las capturas solo complementan esa evidencia.

## Instrucción para redactar el informe final

Al generar el informe con esta guía y las capturas adjuntas:

1. Describir TA-007 como integración y validación de guardrails y evaluación ya existentes, no como creación completa de un motor nuevo.
2. Distinguir claramente cambios de código, protecciones preexistentes y pruebas añadidas.
3. Informar los dos bloques principales de manera separada (26 y 19), explicando que se solapan en tres pruebas y no representan 45 casos únicos.
4. Indicar que la validación fue local y automatizada; no afirmar producción, Vercel, Supabase real, proveedor LLM real ni certificación clínica.
5. Confirmar que no se introdujeron prescripciones ni se cambiaron sus reglas.
6. Incluir las capturas adjuntas sin alterarlas, sus nombres/rótulos, los límites de la validación y las ubicaciones de los XML/TXT.
7. No inventar hallazgos, pasos manuales, tiempos, aprobaciones ni criterios que no estén en este documento o en la evidencia adjunta.
