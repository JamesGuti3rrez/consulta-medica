# Intento 2: la corrida en vivo no pudo preparar los usuarios

**Qué pasó.** La corrida «vivo antes» (commit `0ef9e0e`, servidor real en `http://127.0.0.1:3100` con
`SESSION_STORE=supabase`) terminó con los 40 casos en ERROR de preparación:
`httpx.ConnectError: [Errno 11001] getaddrinfo failed` al crear el alumno A en Supabase Auth.

**Causa.** El `SUPABASE_URL` del `.env` local apunta al proyecto `uxmux…`, cuyo dominio ya no existe
(`nslookup_supabase_env.txt`: *Non-existent domain* en 8.8.8.8). El despliegue de Vercel usa otro proyecto,
`rynkx…` (`config_produccion.json`, leído de `/api/config` de producción, con la clave publicable omitida).
El equipo no tiene la clave secreta de ese proyecto en el `.env`, y sin ella no se pueden crear ni borrar
los alumnos temporales.

**Qué no ocurrió.** No se creó ningún usuario ni ninguna sesión: la primera llamada a Supabase falló. Tampoco
se escribió `limpieza.json`, porque no había nada que limpiar.

Archivos conservados sin modificar: la foto de la terminal, la salida de pytest, los JSON de error de cada
caso (`resultados_vivo_antes/logs`) y el log del servidor.
