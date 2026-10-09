# Servicio RAG de casos clínicos

## Objetivo

El módulo `backend/server/rag/` implementa recuperación en tiempo de ejecución sobre el índice
preparado offline por `backend/case_preparation/indexing/`. La autorización **no pertenece al RAG**:
`engine/disclosure/` debe calcular `allowed_evidence_ids` y el orquestador entrega esa lista al
servicio RAG.

## Flujo

```text
casos curados / fuentes aprobadas
        ↓
case_preparation index
        ↓
LightRAG 1.5.7 + retrieval_catalog.json
        ↓
/api/v1/rag/evidence/search
        ↑
case_id + allowed_evidence_ids + owner
        ↑
orquestador / disclosure
```

La preparación aplica `public / on_request / protected`, comprueba fugas contra `protected` y crea
una partición por documento autorizado. `protected` nunca se convierte en documento recuperable.

## Endpoints

- `GET /api/v1/rag/health`: estado del índice activo.
- `POST /api/v1/rag/reload`: recarga el índice más reciente.
- `POST /api/v1/rag/evidence/search`: recuperación dentro del caso activo y del allowlist recibido.
- `POST /api/v1/rag/cases/search`: búsqueda segura de casos usando únicamente el documento público.
- `POST /api/v1/rag/knowledge/search`: fuentes generales explícitamente aprobadas y separadas por
  `scope=conversation|evaluation`.

### Contrato usado por el Sistema Multiagente

```json
{
  "query": "¿desde cuándo comenzó el dolor?",
  "case_id": "MED-001",
  "allowed_evidence_ids": ["MED-001.anamnesis.inicio"],
  "owner": "paciente",
  "top_k": 3,
  "session_id": "opcional",
  "agent": "paciente"
}
```

El servicio responde:

```json
{
  "case_id": "MED-001",
  "results": [
    {
      "evidence_id": "MED-001.anamnesis.inicio",
      "text": "...",
      "score": 0.82,
      "case_id": "MED-001",
      "role": "paciente",
      "category": "anamnesis",
      "requires": ["inicio_y_evolucion"]
    }
  ]
}
```

Este contrato coincide con `HttpRetriever` del repositorio del Sistema Multiagente, cuyo
`RAG_SERVICE_URL` debe apuntar a la raíz de este servidor, por ejemplo
`http://127.0.0.1:8001`.

## Preparar el RAG

Desde `backend/`:

```powershell
python -m pip install -e ".[pipeline,indexing,dev]"
python -m pytest -q
python -m case_preparation index
```

Para activar embeddings semánticos locales:

```powershell
python -m pip install -e ".[pipeline,indexing,semantic,dev]"
$env:RAG_EMBEDDING_BACKEND="sentence_transformers"
python -m case_preparation index
```

El modelo debe estar disponible en la máquina. El modo `local_hash` permanece como baseline
reproducible para pruebas; no se presenta como calidad semántica final.

## Levantar como servicio separado

Desde `backend/`:

```powershell
python -m uvicorn server.main:app --host 127.0.0.1 --port 8001
```

Swagger: `http://127.0.0.1:8001/api/docs`.

En el SMA:

```env
RAG_SERVICE_URL=http://127.0.0.1:8001
```

## Seguridad

1. `case_id` es obligatorio para recuperar evidencia clínica.
2. `allowed_evidence_ids` es obligatorio y nunca se amplía dentro del RAG.
3. Un `evidence_id` perteneciente a otro caso produce error 400.
4. `owner` y `category` solo reducen candidatos.
5. `protected` no se indexa ni aparece en respuestas.
6. Los documentos de conocimiento requieren registro explícito, aprobación, licencia y revisor.
7. Cada búsqueda queda registrada en `backend/logs/rag_retrieval.jsonl` con `evidence_id`, score,
   fingerprint del índice y filtros aplicados.
