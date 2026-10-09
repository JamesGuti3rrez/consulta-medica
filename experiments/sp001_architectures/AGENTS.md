# Reglas para Codex

Este repositorio es un experimento académico comparativo. Antes de modificarlo:

1. Mantén constantes los casos, preguntas, prompts de rol, herramientas y verificador entre arquitecturas.
2. La variable experimental principal es la orquestación: supervisor, StateGraph, handoffs y supervisor+handoffs.
3. `protected_evaluation` no debe entrar en ningún agente conversacional.
4. No fabriques resultados para favorecer a una arquitectura. Los CSV deben contener únicamente ejecuciones reales.
5. El modo `mock` solo valida infraestructura; no se usa como evidencia empírica del comportamiento de un LLM.
6. Toda nueva métrica debe tener definición computable y guardarse en `raw_results.csv` antes de agregarse a `summary.csv`.
7. Ejecuta `pytest -q` después de cambios funcionales.
8. Mantén compatibilidad con Python 3.11+ y Google Colab.
9. El benchmark real usa Groq (`--provider groq`) y debe mantener el mismo `GROQ_MODEL`, temperatura y reasoning effort para las cuatro arquitecturas.
10. Nunca imprimas, registres ni incluyas `GROQ_API_KEY` en resultados, logs o capturas.
