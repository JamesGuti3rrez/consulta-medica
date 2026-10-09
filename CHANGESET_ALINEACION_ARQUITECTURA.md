# Changeset — Alineación SMA con Arquitectura del Paciente Virtual Adaptativo v1.0

## Cambios estructurales

- Separación de capa IA y núcleo determinístico.
- Nuevo `server/orchestration/` para StateGraph y routing.
- Nuevo `server/engine/disclosure/` para `reveal_policy`.
- Nuevo `server/engine/state_machine/` para fases clínicas.
- Nuevo `server/engine/safety/` para reglas derivadas de información protegida.
- Nuevo `server/rag/` para el contrato de recuperación.
- Nuevo `server/guardrails/` y `server/tracing/`.
- `server/ai/` queda limitado a agentes, prompts, LLM y punto de integración de embeddings.

## Contrato de datos

- Se incorpora `schemas/caso.schema.json` oficial v1.0.0.
- Se incorpora `data/cases/curated/CARD-001.json` como caso canónico de desarrollo.
- El SMA deja de depender del JSON legado plano.
- El campo de dificultad se elimina también del caso legado.

## Seguridad

- Autorización por `owner + mode + requires`.
- `protected` no se entrega a agentes ni al RAG.
- El guardrail recibe una denylist preparada por `engine/safety`, no el caso completo.
- Pruebas automáticas verifican dependencias prohibidas.

## Pruebas

La suite alineada incluye pruebas unitarias, integración y seguridad, incluido un flujo con los cinco agentes.
