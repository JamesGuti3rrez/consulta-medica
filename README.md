# Paciente Virtual Adaptativo — Repositorio unificado SMA + RAG

Este repositorio integra el frontend existente, el Sistema Multiagente (topología estrella con LangGraph StateGraph), la política determinística de disclosure, el gateway LLM con Groq, LangSmith, guardrails, el runtime RAG seguro con LightRAG y el pipeline de preparación/indexación de casos.

## Ejecución local recomendada

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[pipeline,indexing,dev]"
npm install
python -m pytest -q
python -m case_preparation index
npm start
```

Con `RAG_EMBEDDED=true` no se necesita un segundo servidor RAG: el mismo FastAPI expone `/api/ai/*` y `/api/v1/rag/*`, y el SMA consulta el índice in-process. `RAG_SERVICE_URL` se conserva únicamente para un despliegue desacoplado.

## Flujo

`Frontend → StateGraph → Decision Router → DisclosurePolicy → allowed_evidence_ids → RAG → agente → LLM Gateway → Guardrail → trazas`

La sección `protected` nunca se entrega al RAG conversacional ni a los agentes.

---

# Consulta Médica Virtual — Paciente Virtual Adaptativo

Repositorio unificado del simulador de consulta médica. Conserva el frontend/prototipo existente y
añade el Sistema Multiagente (SMA) alineado con la guía de arquitectura v1.0.

## Requisitos

- Node.js 18 o superior.
- Python 3.12 o superior.

## Ejecución local

```powershell
npm install
npm run setup
.venv\Scripts\python.exe -m pip install -e ".[dev]"
.venv\Scripts\python.exe -m pytest -q
npm start
```

Aplicación: `http://localhost:3000`  
Swagger: `http://localhost:3000/api/docs`

## Principios implementados

1. **La IA redacta; el código decide.** Routing, fases, autorización y guardrails son determinísticos.
2. **Mínimo privilegio.** Cada agente recibe solo evidencia autorizada para su rol y turno.
3. **Defensa en profundidad.** `protected` no entra al contexto del LLM y existe filtro de salida.
4. **Casos canónicos.** El SMA consume `public / on_request / protected` según `schemas/caso.schema.json`.
5. **Trazabilidad.** Cada turno registra `evidence_id`, agente, fase, proveedor/modelo y fallback.

## Arquitectura SMA

- Topología: **estrella**.
- Orquestación: **LangGraph StateGraph**.
- Routing: `server/orchestration/router.py`.
- Estado clínico: `server/engine/state_machine/`.
- Autorización: `server/engine/disclosure/` mediante `reveal_policy`.
- Agentes: `server/ai/agents/`.
- LLM Gateway: `server/ai/llm/`.
- RAG: `server/rag/` (recupera; no autoriza).
- Guardrails: `server/guardrails/`.
- Trazas/LangSmith: `server/tracing/`.

### Flujo de un turno

```text
Estudiante
   ↓
DecisionRouter
   ↓
ClinicalStateMachine
   ↓
DisclosurePolicy → allowed_evidence_ids
   ↓
Retriever / RAG
   ↓
ContextAssembler
   ↓
Agente seleccionado → LLM Gateway
   ↓
OutputGuard
   ↓
Traza + respuesta
```

## Agentes

- `medico_asistente`
- `paciente`
- `laboratorio`
- `radiologia`
- `especialista`

Los prompts están versionados en `server/ai/agents/prompts/`.

## Datos clínicos

El contrato oficial está en:

```text
schemas/caso.schema.json
```

El caso de desarrollo canónico está en:

```text
data/cases/curated/CARD-001.json
```

El archivo `data/caso-demo.json` se conserva únicamente para compatibilidad con el frontend legado.
El SMA nuevo no depende de ese formato.

## RAG

La rama SMA no decide la tecnología interna del RAG. El contrato exige:

```text
query
case_id
owner
allowed_evidence_ids
top_k
```

Con `RAG_SERVICE_URL=` vacío se usa un fallback determinístico sobre el caso canónico para poder
probar routing y aislamiento sin el servicio externo. Cuando el servicio RAG esté disponible, se
conecta por HTTP. LightRAG, pgvector u otra implementación pueden quedar detrás del mismo contrato.

## LLM Gateway

`.env` admite una o varias claves Groq autorizadas:

```env
GROQ_API_KEYS=gsk_clave_1,gsk_clave_2,gsk_clave_3
GROQ_MODEL=openai/gpt-oss-20b
AI_LLM_TEMPERATURE=0
```

El gateway aplica rotación simple, cooldown y fallback ante errores recuperables. Sin claves, el
sistema usa `local-development` y no consume un LLM real.

## LangSmith

```env
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=...
LANGSMITH_PROJECT=paciente-virtual-sma
```

Las trazas locales se escriben en `.runtime/ai_traces.jsonl` y no se suben a Git.

## API SMA

| Método | Ruta | Uso |
|---|---|---|
| GET | `/api/ai/status` | Arquitectura y proveedores activos |
| POST | `/api/ai/sessions` | Iniciar sesión |
| GET | `/api/ai/sessions/{session_id}` | Estado mínimo de sesión |
| POST | `/api/ai/sessions/{session_id}/message` | Turno multiagente |
| GET | `/api/ai/sessions/{session_id}/events` | Trazabilidad |
| POST | `/api/ai/sessions/{session_id}/finish` | Finalizar sesión |

## Pruebas

```powershell
python -m pytest -q
```

La suite está separada en:

```text
tests/unit/
tests/integration/
tests/security/
tests/fixtures/
```

`tests/` no usa un LLM real. `evals/` queda reservado para mediciones con el proveedor real y
LangSmith.

## Estructura relevante

```text
consulta-medica/
├── schemas/
├── server/
│   ├── api/
│   ├── domain/
│   ├── cases/
│   ├── engine/
│   │   ├── state_machine/
│   │   ├── disclosure/
│   │   ├── safety/
│   │   └── evaluation/
│   ├── orchestration/
│   ├── rag/
│   ├── guardrails/
│   ├── tracing/
│   ├── persistence/
│   └── ai/
│       ├── agents/prompts/
│       ├── llm/
│       └── embeddings/
├── data/
│   └── cases/curated/
├── tests/
├── evals/
├── docs/
├── public/
├── src/
└── supabase/
```

La guía propone `backend/` y `frontend/` como raíces. Esta rama conserva las raíces físicas del
repositorio principal (`server/`, `public/`, `src/`) para no romper los scripts ni el trabajo de los
otros responsables. La separación interna sí sigue las responsabilidades de la guía.

## Documentación técnica

- `docs/architecture/ALINEACION_GUIA_ARQUITECTURA.md`
- `docs/agents/ARQUITECTURA_SMA.md`
- `docs/agents/PLAN_IMPLEMENTACION_SMA.md`
- `docs/decisions/`
- `docs/reports/`
- `CHANGESET_ALINEACION_ARQUITECTURA.md`
