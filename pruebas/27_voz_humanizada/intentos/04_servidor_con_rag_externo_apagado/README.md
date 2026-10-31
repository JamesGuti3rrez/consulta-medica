# Intento 4: el servidor de prueba buscaba un RAG externo que no estaba encendido

**Qué pasó.** Primera corrida en rojo de la prueba de navegador que exige conservar los signos
(`18_signos_rojo_intento1.txt`). La parte de los signos dio lo esperado (6 textos sin signos), pero las dos
preguntas del estudiante recibieron «No pude procesar tu pregunta. Inténtalo de nuevo.»: el servidor respondió 500.

**Causa.** El `.env` tiene `RAG_SERVICE_URL=http://127.0.0.1:8001`, así que el servidor de prueba (puerto 3100)
consultaba un servicio RAG por HTTP y en ese puerto no había nada (`httpx.ConnectError`, WinError 10061).

**Cómo se corrigió.** El servidor de prueba se levanta con `RAG_SERVICE_URL` vacía, además de
`SESSION_STORE=memoria`, `CASE_STORE=local`, `RAG_BACKEND=local` y `TTS_PROVIDER=edge`. `/api/ai/status` pasa a
mostrar `retrieval_mode: embedded-lightrag` y la corrida se repite.
