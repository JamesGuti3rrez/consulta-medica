# Herramienta de captura de terminal · Intento 1 (incompleto) — 2026-10-08

Primeras capturas reales de terminal tomadas con `captura_terminal.ps1`.

## Qué falló

La ventana tenía un alto fijo (900 px) y solo se fotografiaba lo visible al terminar el comando. En
salidas largas, como `verificar_casos.py`, la captura mostraba únicamente el final y las secciones
1 a 4 quedaban fuera de la imagen.

## Cómo se corrigió (intento 2, vigente)

- La ventana se abre con 1440 px de ancho y todo el alto de la pantalla.
- Al terminar el comando, la consola vuelve al inicio de la salida y se fotografía página por página.
- Las páginas se guardan por separado (`_p1.png`, `_p2.png`…) y unidas en una sola imagen con toda la salida.
- En la unión se descartan las líneas que ya aparecían en la página anterior. Se comprobó con una salida de 80 líneas numeradas: no falta ni se repite ninguna.
