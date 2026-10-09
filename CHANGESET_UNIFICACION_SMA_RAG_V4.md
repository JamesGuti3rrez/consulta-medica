# Unificación SMA + RAG v4

- Se tomó el SMA v3 como raíz para conservar el frontend y el backend del repositorio principal.
- Se incorporó `case_preparation/` y el runtime LightRAG en `server/rag/`.
- Se incorporó el proveedor de embeddings en `server/ai/embeddings/`.
- Se fusionó el corpus curado de 11 casos, incluido CARD-001 con evidencias para los cinco roles.
- Se añadió `EmbeddedRAGRetriever`: SMA y RAG pueden ejecutarse en el mismo proceso FastAPI.
- Se mantienen los endpoints HTTP `/api/v1/rag/*` para pruebas, observabilidad o despliegue desacoplado.
- `RAG_SERVICE_URL` tiene prioridad si se desea separar el servicio; si está vacío y `RAG_EMBEDDED=true`, se usa LightRAG in-process.
- Se unificaron dependencias y extras en un solo `pyproject.toml`.
- Se incorporaron pruebas RAG al árbol principal y pruebas de integración del servicio unificado.
- No se incluyen `.env`, índices generados, logs, caches, `.venv` ni `node_modules`.
