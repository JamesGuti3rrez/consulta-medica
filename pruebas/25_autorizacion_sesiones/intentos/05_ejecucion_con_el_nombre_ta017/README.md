# Intento 5: ejecución con el nombre anterior (TA-017)

## Qué pasó

La tarea se llamaba TA-017 cuando se hicieron las ejecuciones del 2026-10-27 (02:39 a 03:44 UTC). Después el
equipo la renombró a **TA-011**. Las salidas, los JSON y las capturas de esta carpeta dicen `TA-017` y `TA017-XX`
porque así se llamaban la suite, los casos y las variables en ese momento.

No es un fallo de las pruebas: los resultados fueron los mismos que en la ejecución nueva (23 fallan antes,
37 de 37 pasan después). Se conservan sin modificar como registro de esa ejecución.

## Contenido

| Carpeta o archivo | Qué es |
| --- | --- |
| `ejecucion/` | Salidas `.txt` y fotos de terminal de la regresión, la suite antes y después, los scripts del recorrido, el navegador y el preview |
| `resultados/` | JSON y tarjetas PNG de cada caso `TA017-XX` en las fases `local_antes` y `local_despues` |
| `capturas/` | Capturas de las salidas, git diff y pruebas en navegador |
| `codigo/` | Capturas del código cambiado (comentarios con «TA-017») |
| `evidencia.html`, `*.png` | Índice visual y fotos de los documentos de esa versión |

Los commits que citan estas salidas tenían otros identificadores antes de reescribir los mensajes
(por ejemplo, `0ef9e0e` pasó a `a4e169e` y `c752abe` a `1aaec15`; la tabla completa está en el informe).

## Corrección

Se renombraron la suite, los casos (`TA011-XX`), el marcador y las variables (`TA011_*`), y se repitieron todas
las ejecuciones con el nombre nuevo. La evidencia vigente está en `ejecucion/`, `resultados/`, `capturas/` y
`codigo/` de la carpeta principal.
