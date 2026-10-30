# Intento 8: el preview de Vercel no tiene un modelo de lenguaje disponible

**Qué pasó.** Corrida contra el preview de la rama (`consulta-medica-1mjw4o7qz-...vercel.app`, commit `5f9435d`,
2026-10-28) con el token de bypass. El preview creó las 4 consultas de la preparación (A, B y los dos
invitados), pero el primer mensaje de A respondió **503** «El simulador no puede responder en este momento».
Sin esos mensajes la preparación no termina: 39 casos en ERROR y el 39 deseleccionado.

**Causa.** No es de autorización. `GET /api/ai/status` del preview muestra las tres claves de Groq
(`groq-1` a `groq-3`) con `available: false`, y cada mensaje falla en 0,6 s. En el mismo momento:

- las tres claves del `.env` local respondieron 200 en Groq, con cupo de sobra;
- producción (`consulta-medica-three.vercel.app/api/ai/status`) mostraba sus tres claves con `available: true`.

Las variables de entorno de Vercel para los previews no tienen claves de Groq válidas (o no son las de
producción). Desde el repositorio no se pueden ver ni cambiar.

**Datos de prueba.** Los 2 alumnos temporales se crearon y se borraron. Las 4 consultas viven en la memoria
del preview (`session_store: memoria`), no en Supabase; por eso la limpieza no encontró filas que borrar.

**Pendiente.** Configurar `GROQ_API_KEYS` para el entorno Preview en Vercel, volver a desplegar y repetir.
