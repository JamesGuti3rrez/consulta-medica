# Intento 1: la ventana de la foto se cerraba antes de capturarla

**Qué pasó.** La primera corrida en rojo de la tarea 1 (`t1_red`) guardó su salida (`t1_red.txt`: `ImportError`,
el módulo `server.report` aún no existe, código 2), pero no hubo foto: la herramienta esperó 5 minutos y se
detuvo a mano.

**Causa.** El lanzador `correr_prueba.ps1` terminaba el comando con `exit $codigo`. Dentro de la ventana de
`captura_terminal.ps1` ese `exit` cierra la consola antes de que la herramienta imprima el código de salida y
tome la foto.

**Corrección.** El lanzador deja el código en `$global:LASTEXITCODE`, que es lo que la herramienta muestra en la
ventana, sin cerrarla. La corrida en rojo se repitió con foto.
