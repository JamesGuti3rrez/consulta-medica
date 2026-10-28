# Intento 7: la suite contra el preview de Vercel no envió el token de bypass

**Qué pasó.** Primera corrida contra el preview de la rama (`consulta-medica-1mjw4o7qz-...vercel.app`, commit
`5f9435d`, 2026-10-28): 39 casos en ERROR de preparación y el 39 deseleccionado (no hay log del servidor en
Vercel). Al crear la consulta de A, el preview respondió con la página «Protected by Vercel Authentication».

**Causa.** La suite lee `TA011_VERCEL_BYPASS` del entorno al importarse, y el `.env` (donde está el token) se
carga después, al preparar el modo vivo. La corrida se lanzó sin exportar la variable, así que ninguna
petición llevó la cabecera `x-vercel-protection-bypass`. No es un problema del código de TA-011.

**Corrección.** Se repitió exportando `TA011_VERCEL_BYPASS` desde el `.env` en la misma terminal, sin imprimir
su valor.

**Datos de prueba.** Se crearon y borraron los 2 alumnos temporales; no llegó a crearse ninguna consulta
(`resultados_vercel_preview/limpieza.json`).

Archivos conservados sin modificar: la foto de la terminal (solo en el equipo), la salida de pytest, los JSON
de error de cada caso y la limpieza.

## Repetición con el comando mal citado

La primera repetición tampoco envió el token: el comando de PowerShell que lo carga del `.env` se pasó desde
bash entre comillas dobles, y bash interpretó las comillas invertidas (`` ` ``) como sustitución de comandos.
PowerShell recibió la línea cortada y la suite corrió otra vez sin la variable (mismo resultado: 39 ERROR, los
2 usuarios temporales creados y borrados). Se conserva en `repeticion_comando_mal_citado/`. La corrida válida
se lanzó desde un archivo `.ps1`, sin pasar por bash.
