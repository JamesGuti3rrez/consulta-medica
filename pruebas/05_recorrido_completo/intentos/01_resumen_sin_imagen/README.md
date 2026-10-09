# Fase 5 · Intento 1 (con error oculto) — 2026-10-09

Primera ejecución del recorrido completo fotografiada en una terminal real
(`recorrido_completo_terminal.png`).

## Qué falló

Las ocho comprobaciones del flujo pasaron (código 0), pero al final apareció un `JSONDecodeError`:
`evidencia.py archivo` intentaba leer `resumen_recorrido.txt` como JSON. Por eso la imagen
`resumen_recorrido.png` nunca se había generado, tampoco en las ejecuciones anteriores.

El error no se veía porque:

- el script no revisaba el código de salida al generar capturas de archivos;
- en las ejecuciones anteriores solo se miraba el final de la salida, donde aparece el resumen.

La foto de la terminal completa lo hizo visible.

## Cómo se corrigió (intento 2, vigente)

- `evidencia.py archivo` admite archivos de texto, además de JSON y CSV.
- `recorrido_completo.py` comprueba el código de salida de cada captura y termina con error si alguna imagen no se genera.
