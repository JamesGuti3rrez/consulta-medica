# backend/evals/

Arnés de medición continua de la capa de IA sobre el sistema real.

Medirá las métricas de la carta del proyecto: fugas del diagnóstico, fuga entre roles, cobertura de evidencia, datos inventados, variación entre ejecuciones y latencia por turno. Opcionalmente se integrará con LangSmith (sugerencia del docente).

Diferencia con otras carpetas:

- `backend/tests/` → pruebas determinísticas que deben pasar siempre (sin LLM real).
- `backend/evals/` → corridas con LLM real, con resultados que se comparan entre versiones.

Vacío en esta etapa. Los conjuntos de preguntas se crearán después, desde cero, sobre casos curados.
