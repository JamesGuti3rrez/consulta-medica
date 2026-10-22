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

### Usar pgvector en Supabase

La opción `RAG_BACKEND=supabase_pgvector` hace que los turnos del SMA consulten la función
`public.buscar_evidencias_rag` de Supabase en lugar del índice embebido. La tabla
`public.rag_evidencias` y esa función deben estar creadas según el SQL acordado, con acceso exclusivo
para `service_role`.

El índice se carga a partir de los casos JSON curados versionados en `data/cases/curated/` (no se
descargan casos desde la base). Primero configura en `.env`:

```env
SUPABASE_URL=https://<proyecto>.supabase.co
SUPABASE_SECRET_KEY=<clave-secreta-del-servidor>
RAG_BACKEND=supabase_pgvector
RAG_EMBEDDING_BACKEND=sentence_transformers
RAG_EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
```

Instala el extra semántico y carga los documentos desde `backend/`:

```powershell
python -m pip install -e ".[semantic,dev]"
python -m case_preparation index-supabase
```

El indexador aplica las Quality Gates y prepara exclusivamente evidencia `public` y `on_request`;
`protected` no se inserta. La carga usa upsert por `(case_id, evidence_id)`, así que se puede repetir
para actualizar los textos y vectores. El mismo modelo de embeddings y las mismas dimensiones deben
usarse al indexar y al buscar. `local_hash` puede servir para una prueba de conectividad, pero no es
una configuración de recuperación semántica de calidad.

Al iniciar el backend, `/api/ai/status` debe informar `"retrieval_mode": "supabase-pgvector"`.
Si la RPC o la tabla no existen, el SMA devolverá el error de Supabase: no cambia silenciosamente al
fallback local en este modo.

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

0. Las rutas de búsqueda y `reload` exigen el token entre servicios `RAG_HTTP_TOKEN` en la cabecera
   `X-RAG-Token`; sin token configurado no se atienden. Un estudiante no puede llamarlas para pedir
   evidencia que `engine/disclosure` no le autorizó. `health` es pública.
1. `case_id` es obligatorio para recuperar evidencia clínica.
2. `allowed_evidence_ids` es obligatorio y nunca se amplía dentro del RAG.
3. Un `evidence_id` perteneciente a otro caso produce error 400.
4. `owner` y `category` solo reducen candidatos.
5. `protected` no se indexa ni aparece en respuestas.
6. Los documentos de conocimiento requieren registro explícito, aprobación, licencia y revisor.
7. Cada búsqueda queda registrada en `backend/logs/rag_retrieval.jsonl` con `evidence_id`, score,
   fingerprint del índice y filtros aplicados.
