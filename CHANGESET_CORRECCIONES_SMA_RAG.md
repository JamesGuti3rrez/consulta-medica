# Correcciones SMA ↔ RAG posteriores a la primera prueba E2E

## 1. Trazabilidad completa SMA → RAG

`HttpRetriever` ahora propaga `session_id` y `agent` al endpoint `/api/v1/rag/evidence/search`.
Esto permite correlacionar una misma ejecución entre `.runtime/ai_traces.jsonl` y
`backend/logs/rag_retrieval.jsonl` usando sesión, agente, caso y `evidence_id`.

## 2. Grounding del agente con evidencia ya recuperada

Cuando `retrieved_evidence` no está vacío, el agente recibe una regla explícita: debe comunicar
los hallazgos ya disponibles y no pedir al estudiante que los invente o describa.

Si el LLM incumple esta regla:
1. se realiza una única regeneración correctiva;
2. si vuelve a incumplir, el código responde de forma determinística usando solamente la evidencia autorizada.

Las trazas incluyen `grounding_retry_used` y `grounding_fallback_used`.

## 3. Caso E2E reproducible

Se incorpora `EME-001` corregido con `reveal_policy.mode = al_examinar` para la evidencia de
exploración física, de modo que el flujo `Intent.EXAMINE → disclosure → RAG` sea consistente.

## 4. Pruebas

Se agregan pruebas del contrato de trazabilidad HTTP y del mecanismo de grounding correctivo.
La suite SMA queda en 14 pruebas superadas.
