# Alineación del repositorio con la guía de arquitectura v1.0

Fecha: 2026-10-08

## Resultado

La implementación SMA fue refactorizada para respetar los principios funcionales de la guía:
la IA redacta y el código decide; mínimo privilegio; defensa en profundidad; caso canónico
`public/on_request/protected`; trazabilidad por `evidence_id`; RAG sin capacidad de autorización;
y topología SMA en estrella controlada con LangGraph StateGraph.

## Cambios aplicados

| Regla de la guía | Situación anterior | Alineación aplicada |
|---|---|---|
| Solo la redacción usa IA | routing, contexto, guardrails y trazas vivían dentro de `server/ai/` | se movieron a `orchestration/`, `engine/`, `guardrails/` y `tracing/` |
| `ai/` no accede a `cases/`, `engine/` ni `protected` | la capa IA recibía un caso filtrado por campos | `server/ai/` contiene solo `agents/`, `llm/` y `embeddings/`; existe una prueba de dependencias |
| Contrato `public/on_request/protected` | el SMA usaba el JSON legado plano | se añadió `schemas/caso.schema.json` y un caso curado canónico `CARD-001` |
| `reveal_policy` calcula `allowed_evidence_ids` | se autorizaban todos los datos asociados a un rol | `engine/disclosure/` evalúa `owner`, `mode` y `requires` por turno |
| El RAG recupera pero no autoriza | el contrato ya aceptaba allowed IDs, pero el fallback no devolvía evidencia | `rag/` solo recupera dentro de `allowed_evidence_ids`; fallback local determinístico para desarrollo |
| `protected` nunca entra al flujo conversacional | el guardrail recibía el caso completo y permitía protected en `cierre` | solo `engine/safety/` lee `protected` para generar una denylist; el guardrail nunca recibe el bloque protegido |
| Prompts versionados | prompts incrustados en las clases Python | `server/ai/agents/prompts/*.md` |
| Fases clínicas determinísticas | fases reducidas a presentación/consulta/cierre | `state_machine/` usa presentación, anamnesis, exámenes, hipótesis, diagnóstico, cierre y finalizada |
| Trazabilidad | se registraba agente, proveedor y evidencia RAG | se añadieron fase, modelo, tokens, fallback y `evidence_ids` |
| Tests separados de evals | pruebas concentradas en `tests/ai/` | `tests/unit/`, `tests/integration/`, `tests/security/` y `evals/` reservado para LLM real |

## Decisión de compatibilidad con el repositorio principal

La guía propone físicamente `backend/` y `frontend/`. El repositorio principal existente usa
`server/`, `public/`, `src/` y `supabase/`, y sus scripts de npm/Vercel dependen de esa estructura.
No se movieron esas raíces en la rama IA porque afectaría simultáneamente al frontend y a la
infraestructura de otros responsables. La alineación aplicada es funcional y modular dentro del
backend actual. Si el equipo decide adoptar literalmente `backend/` y `frontend/`, debe hacerse
como una refactorización transversal del repositorio, no como un cambio aislado de IA.

## Puntos del PDF que ya están desactualizados

- El estado ya no es "sin implementación funcional": el SMA tiene implementación y pruebas.
- La orquestación ya no es una decisión abierta: se adoptó topología estrella con StateGraph.
- El proveedor dejó de ser una decisión totalmente abierta para la rama IA: existe un `LLMGateway`
  con pool/fallback de credenciales Groq; el proveedor sigue siendo intercambiable.
- LangSmith ya está integrado de forma opcional.
- El campo de dificultad no se incorporó al esquema ni al SMA; se mantiene fuera del diseño.
- La decisión del backend RAG sigue perteneciendo al responsable RAG; LightRAG puede conectarse
  detrás de `RetrieverPort` sin cambiar el SMA.

## Verificación

La suite del repositorio alineado ejecuta pruebas de contrato, routing, estado clínico, política de
revelación, aislamiento, guardrail, límite de autorización del RAG, fallback del LLM Gateway y un
flujo integrado con los cinco agentes.
