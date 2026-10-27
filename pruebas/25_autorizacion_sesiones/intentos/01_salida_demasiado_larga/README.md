# Intento 1: salida de la suite demasiado larga

**Qué pasó.** La primera corrida «local antes» (commit `5148509`) usó `--tb=line`. Cada caso que falla
imprimió todos sus pasos y comprobaciones en una sola línea, y la foto real de la terminal quedó de
5 páginas, difícil de leer. Además, la ventana terminó con «Código de salida: 0», porque `correr_suite.ps1`
no devolvía el código de pytest; el `.txt` sí registró `CODIGO_SALIDA: 1`.

**Resultado de ese intento** (válido, idéntico al de la corrida oficial): 23 fallan, 14 pasan, 3 no
seleccionadas (solo en vivo).

**Corrección.** `correr_suite.ps1` usa `--tb=no -rN`: la terminal muestra un PASSED/FAILED por caso y el
resumen; el detalle de cada fallo queda en `resultados/<fase>/logs/TA017-XX.json` y en su tarjeta PNG. El
script termina con `exit $codigo`.

Archivos conservados sin modificar: `02_local_antes_terminal.png`, `local_antes_pytest.txt` y
`correr_suite_v1.ps1`.
