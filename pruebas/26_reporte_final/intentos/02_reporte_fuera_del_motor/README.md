# Intento 2: el reporte leía la parte protegida del caso fuera del motor de evaluación

**Qué pasó.** Con la ruta `/report` ya en verde (`t2_green`), la suite completa dio 2 fallos (474 pasan). Uno era
el esperado (`test_09` de TA-011: ahora hay 5 rutas con `session_id`). El otro no:
`tests/security/test_dependency_rules.py::test_only_safety_or_evaluation_consume_get_protected` →
`['server/report/builder.py']`.

**Causa.** La regla del proyecto solo deja leer la parte protegida de un caso (diagnóstico, diferenciales,
tratamiento de referencia, preguntas clave) a los motores de seguridad y de evaluación. La primera versión puso
`build_report` en un paquete propio, `server/report/`, que la leía por su cuenta, y el servicio de la consulta
cargaba el caso completo.

**Corrección.** El reporte es la evaluación completa después del cierre: `build_report` pasó a
`server/engine/evaluation/report.py` y el motor expone `ClinicalEvaluationEngine.report(session, events)`, que lee
la parte protegida con su propio repositorio. El servicio solo llama al motor. La suite se repitió
(`ejecucion/tdd/t2_suite_completa_tras_mover`): 475 pasan y solo falla el `test_09` de TA-011, que se actualiza en
la tarea 3.

Archivos conservados sin modificar: la salida y la foto de la terminal (solo en el equipo).
