# backend/server/

Paquete Python del servidor FastAPI (`server.main:app`). `main.py` arma la aplicación (cabeceras de seguridad, rutas y archivos del frontend) y `config.py` lee el `.env`. Rutas: `api/routes.py` (`/api/status`, `/api/config` y `/api/caso`, que sirve la ficha pública de un caso curado), `api/ai.py` (`/api/ai`, sesiones del sistema multiagente) y `rag/router.py` (`/api/v1/rag`). La arquitectura del SMA está en `docs/agents/ARQUITECTURA_SMA.md` y el contrato del RAG en `docs/rag/README.md`.

## Principio rector

**La IA redacta, el código decide.** Todo lo que está fuera de `ai/` es determinístico. Nada dentro de `ai/` puede decidir estado clínico, revelación, seguridad ni evaluación.

## Módulos

| Módulo | Componente de la arquitectura | Responsabilidad | ¿Usa IA? |
| --- | --- | --- | --- |
| `api/` | API REST | Rutas HTTP y contratos de entrada/salida. Sin lógica clínica. | No |
| `domain/` | Modelo del caso y la sesión | Tipos que reflejan `schemas/caso.schema.json` y el estado de la consulta. Sin dependencias internas. | No |
| `cases/` | Casos canónicos | Cargar casos, validar (esquema + reglas cruzadas), compuerta de `status`. | No |
| `engine/state_machine/` | Máquina de estados | Fases de la consulta y transiciones; estado del avatar que consume el frontend. | No |
| `engine/disclosure/` | Acceso por rol | Aplica `reveal_policy` y produce `allowed_evidence_ids` por turno. | No |
| `engine/safety/` | Motor de reglas | Compara propuestas de tratamiento con alergias registradas y contraindicaciones del caso; emite alertas sin exponer datos protegidos. | No |
| `engine/evaluation/` | Evaluación | Puntúa evidencia recabada y agrupa omisiones por tipo de error al finalizar la sesión. | No |
| `orchestration/` | Orquestador (StateGraph) | Decide qué agente atiende cada turno y encadena los pasos. | No (invoca IA) |
| `rag/` | Servicio RAG | Política de indexación, chunks, recuperación filtrada por `case_id` y evidencia autorizada. | No (usa embeddings) |
| `guardrails/` | Filtro de salida | Detecta términos protegidos en respuestas y en contenido a indexar. | No |
| `tracing/` | Trazas | Registro por turno: contexto, evidencia, respuesta, validación. | No |
| `persistence/` | Supabase | Acceso a cuentas e intentos. | No |
| `ai/agents/` | Agentes por rol | Paciente, médico asistente, laboratorio, radiología, especialista. Solo redactan. | Sí |
| `ai/llm/` | LLM | Cliente intercambiable de proveedor. | Sí |
| `ai/embeddings/` | Embeddings | Codificación de textos para el RAG. | Sí |

## Reglas de dependencia (no negociables)

- `domain/` no importa nada del proyecto.
- `ai/` **nunca** importa `cases/`, `engine/` ni accede a `protected`. Recibe solo el contexto que le entrega `orchestration/`.
- `protected` solo lo leen `engine/safety/` y `engine/evaluation/`.
- `rag/` nunca indexa `protected` y nunca decide autorización: recibe `allowed_evidence_ids` de `engine/disclosure/`.
- `api/` no contiene reglas clínicas; delega en `engine/` y `orchestration/`.

## Estado clínico de la sesión

La máquina conserva el avance de fase sin impedir que el estudiante vuelva a preguntar a otro agente. El estado del avatar expone los signos vitales definidos en `public`, una postura asociada a la fase y las alertas de seguridad. No modifica signos vitales ni inventa complicaciones: el esquema del caso aún no define una evolución por caso.

La verificación determinística de tratamiento detecta nombres de alergias registradas y términos de `protected.contraindications`. Un resultado sin alertas significa que no hubo coincidencias con esos datos del caso, no que cualquier tratamiento sea universalmente seguro. Al cerrar, el reporte puntúa las preguntas de `protected.evaluation.key_questions` según la evidencia recuperada durante la sesión y solo devuelve conteos de errores, sin temas ni datos protegidos. Las preguntas cuya evidencia ya entrega la presentación del caso (por ejemplo, el motivo de consulta) no se puntúan ni cuentan como omisión, porque el estudiante no puede pedirlas.
