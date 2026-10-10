# Fase 5 · Recorrido completo

## Objetivo

Comprobar de una sola vez todo el flujo de datos: descarga, conversión a JSON, validación y frontend.

## Comando

```powershell
backend\.venv\Scripts\python.exe pruebas\_herramientas\recorrido_completo.py
```

Ejecuta las fases en orden, se detiene en la primera que falle, regenera las evidencias de cada fase
y escribe el resumen.

## Resultado

Las 8 comprobaciones terminan con código 0: «recorrido completo sin errores».

## Evidencias

- [recorrido_completo_terminal.png](recorrido_completo_terminal.png): foto de la terminal con toda la salida.
- [resumen_recorrido.txt](resumen_recorrido.txt) y [resumen_recorrido.png](resumen_recorrido.png): resumen de las 8 comprobaciones.

## Intentos

| Intento | Resultado | Evidencia |
| --- | --- | --- |
| 1 | Las 8 comprobaciones pasaron, pero la imagen del resumen fallaba sin avisar (`JSONDecodeError`) | [intentos/01_resumen_sin_imagen/](intentos/01_resumen_sin_imagen/README.md) |
| 2 | Correcto: sin errores y con la imagen del resumen | esta carpeta |
