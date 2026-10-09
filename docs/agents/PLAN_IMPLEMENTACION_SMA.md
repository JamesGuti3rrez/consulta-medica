# Plan de implementación del SMA

Estado actual: baseline funcional alineado con la guía de arquitectura.

1. Contrato canónico y caso curado de desarrollo: implementado.
2. Topología estrella con StateGraph: implementada.
3. Decision Router determinístico: implementado.
4. `reveal_policy` + mínimo privilegio: implementado.
5. Cinco agentes especializados: implementados.
6. LLM Gateway con fallback: implementado.
7. Guardrail de salida sin acceso directo a `protected`: implementado.
8. Trazas locales y LangSmith opcional: implementados.
9. Integración con RAG real: pendiente de conectar al servicio del responsable RAG.
10. Persistencia de sesiones/casos en BD: pendiente de integrar con la implementación de Datos/Infraestructura.
11. Evals con LLM real y métricas del charter: siguiente bloque.
12. Integración E2E con frontend: siguiente bloque.
