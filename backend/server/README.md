# backend/server/

Paquete Python del servidor FastAPI (`server.main:app`). `main.py` arma la aplicación (cabeceras de seguridad, rutas y archivos del frontend) y `config.py` lee el `.env`. Las rutas viven en `api/routes.py`: hoy son `/api/status`, `/api/config` y `/api/caso`, que responde 503 hasta conectar casos.

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
| `engine/safety/` | Motor de reglas | Alergias, contraindicaciones, verificación de la receta, complicaciones. | No |
| `engine/evaluation/` | Evaluación | Puntaje y clasificación de errores (negligencia, anamnesis incompleta, razonamiento clínico). | No |
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
