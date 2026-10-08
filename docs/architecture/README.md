# Análisis de arquitectura (base para la estructura del repositorio)

Fuente de diseño: Arquitectura_Paciente_Virtual (v1.0), diagrama de contenedores (06/10), `caso.schema.json`, descripción del proyecto, informe del prototipo y reunión con el docente (07/10). Los informes de pruebas se leyeron solo para entender cómo funcionaba cada parte; nada de ellos se incorpora al proyecto.

## A. Componentes

Navegador (portada, simulación, reporte, voz) · API REST · orquestador StateGraph · acceso por rol · filtro de salida · servicio RAG · motor de reglas · evaluación · trazas · agentes por rol · LLM · embeddings · casos canónicos · Supabase · índice vectorial · pipeline de preparación (adaptador, transformación, Quality Gates, curación, indexación).

## B. Responsabilidades

- Lo que **decide** (sin IA): estado de la consulta, qué se revela y a quién, seguridad de la receta, evaluación, trazas.
- Lo que **redacta** (IA): respuestas de cada rol con el contexto autorizado.
- Lo que **prepara** (fuera de línea): convertir, validar, curar e indexar casos.

## C. Dependencias

```
navegador → API → orquestador → acceso por rol → RAG → embeddings
                              → agentes → LLM
                              → filtro de salida → trazas
            API → motor de reglas, evaluación (leen protected)
pipeline (sources → adapters → transform) → validación de casos (compartida) → casos → indexación → índice
```

## D. Flujo de un turno

1. El navegador envía la pregunta (voz transcrita o texto).
2. El orquestador detecta intención y rol.
3. El acceso por rol calcula `allowed_evidence_ids` según `reveal_policy`.
4. El RAG recupera solo evidencia del caso activo y autorizada.
5. El agente redacta con esa evidencia (una llamada al LLM).
6. El filtro de salida revisa la respuesta; si falla, regenera una vez o usa una respuesta fija.
7. Se registra la traza; la tablilla se actualiza por `evidence_id`; el motor de estado actualiza el estado visual del avatar.

`protected` solo lo leen el motor de reglas y la evaluación.

## E. Separaciones obligatorias

Frontend / backend · código determinístico / capa de IA · servidor en ejecución / pipeline fuera de línea · esquema / datos · datos definitivos / fixtures de prueba · pruebas / evals.

## F. Partes que crecerán

Casos curados (de 1 a 20–50), motor de reglas, agentes y prompts, RAG (cambio de almacén), evaluación, frontend (avatar, voz, texto). Cada una tiene su propia carpeta desde el inicio.

## Decisiones abiertas (se dejaron modulares)

| Decisión | Opciones en los documentos | Dónde impacta |
| --- | --- | --- |
| Almacén vectorial | índice JSON local, ChromaDB, pgvector en Supabase, Milvus, GraphRAG | `server/rag/`, `backend/supabase/` |
| Proveedor de LLM | Groq, OpenRouter, Claude, Gemini | `server/ai/llm/` |
| Orquestación final | StateGraph (Arquitectura v1.0) vs. una arquitectura orientada a decisiones (pedida por el docente) | `server/orchestration/` |
| Framework de interfaz | HTML+JS actual vs. React | `frontend/src/` |
| Voz | Web Speech API vs. Whisper + TTS externo | `frontend/src/voice/` |
| Conocimiento general en RAG | protocolos y guías (sugerencia del docente) | `data/knowledge/` |
| Temperatura | 0 según el principio del proyecto; confirmar | `server/ai/llm/`, `.env` |
