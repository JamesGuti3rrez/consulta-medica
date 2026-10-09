# Servicio RAG - contrato de integración

`orchestration/` entrega `case_id`, `owner` y `allowed_evidence_ids`. El RAG recupera/rankea,
pero **no autoriza**. `protected` nunca se indexa.

La implementación final puede usar LightRAG, pgvector u otro backend decidido por el responsable
RAG sin cambiar el contrato `RetrieverPort`.
