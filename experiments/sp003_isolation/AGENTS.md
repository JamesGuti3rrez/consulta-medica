# Reglas del experimento

- No modificar preguntas, caso, modelo o temperatura entre estrategias.
- No introducir el diagnóstico protegido en `minimal_context`,
  `selective_retrieval` o `hybrid_guardrails`.
- `shared_context` debe recibir el caso completo deliberadamente, pues es el
  control inseguro del experimento.
- El evaluador externo debe ser idéntico para todas las estrategias.
- Solo `hybrid_guardrails` puede bloquear/regenerar una salida como parte de su
  diseño.
- No presentar resultados de `mock` como resultados del LLM real.
- No fabricar métricas ni alterar CSV manualmente.
- Ejecutar `pytest -q` después de cambios.
- No guardar claves API en archivos rastreados por Git.
