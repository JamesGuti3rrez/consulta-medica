# Intento 6: la corrida en vivo no dejó el registro de limpieza

**Qué pasó.** Primera corrida en vivo «antes» de la suite HU006 (servidor con el código de TA-011 en
`http://127.0.0.1:3100`, sesiones y casos en el Supabase de producción): 14 fallan y 3 pasan, como en local. Pero
no se escribió `limpieza.json`.

**Causa.** La preparación del modo vivo es la de TA-011 y escribe `limpieza.json` en la carpeta de
`TA011_EVIDENCIA`; `correr_suite.ps1` de la fase 26 dejaba esa variable vacía para que los casos HU006 solo
escribieran en `HU006_EVIDENCIA`.

**Comprobación de que sí se limpió.** Después de la corrida, con la clave secreta: Auth tiene 2 usuarios y ninguno
de prueba; las 4 consultas que aparecen en los JSON de los casos ya no están en `sma_sesiones`.

**Corrección.** `correr_suite.ps1` pone en `TA011_EVIDENCIA` la misma carpeta de la fase. La corrida se repitió.

Archivos conservados sin modificar: la salida de pytest, los JSON de cada caso, el log del servidor y la foto de la
terminal (el log y la foto, solo en el equipo).
