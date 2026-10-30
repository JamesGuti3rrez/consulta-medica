# Intento 8: el preview de Vercel sigue sin un modelo de lenguaje que funcione

**Qué pasó.** Corrida de la suite HU006 contra el preview de la rama (`consulta-medica-2huhqybm3-...vercel.app`)
con el token de bypass: 16 casos en ERROR de preparación (el 17 se deselecciona: en Vercel no hay log del
servidor). El primer mensaje de la consulta de A respondió 503 «El simulador no puede responder en este momento».

**Causa.** La misma de TA-011 (hallazgo D-09). Antes de la corrida, `/api/ai/status` del preview mostraba las tres
claves de Groq con `available: true`: es el estado de una instancia recién creada, que todavía no las ha usado.
Al primer mensaje Groq las rechaza y quedan en `available: false`. Producción, en el mismo momento, tiene sus
tres claves disponibles (`ejecucion/09_preview_vercel.txt`). Las variables `GROQ_API_KEYS` del entorno Preview
de Vercel no son válidas.

**Lo que sí se comprobó en el preview.** Con el token de bypass, `GET /report` sin credencial responde 401: la
ruta existe y aplica la autorización de TA-011.

**Datos de prueba.** Se crearon y borraron los 2 alumnos temporales; la única consulta creada vivió en la memoria
del preview (`session_store: memoria`), no en Supabase.

**Pendiente.** Configurar `GROQ_API_KEYS` para el entorno Preview en Vercel y repetir.
