# Evidencias del flujo de datos (Sprint 1)

Recorrido comprobado: **fuente MedQA → descarga verificada → candidatos → 10 casos JSON → validación → frontend**.
Todas las capturas están en **vista de escritorio/PC (1440 px de ancho)**; ninguna usa vista móvil.

| Fase | Carpeta | Qué demuestra | Resultado |
| --- | --- | --- | --- |
| 1. Descarga | [01_descarga_datasets/](01_descarga_datasets/README.md) | Fuente y archivos originales identificados, URL de obtención y huella SHA-256 verificada | OK |
| 2. Conversión a JSON | [02_transformacion/](02_transformacion/README.md) | Se vuelven a generar los 10 casos con IDs 001–010 y el resultado es idéntico al versionado | OK |
| 3. Validación | [03_validacion/](03_validacion/README.md) | Los JSON cumplen el esquema y la demo usa solo los casos curados | OK |
| 4. Frontend | [04_frontend/](04_frontend/README.md) | Cinco casos cargados en pantalla, solo con datos públicos | OK |
| 5. Recorrido completo | [05_recorrido_completo/](05_recorrido_completo/resumen_recorrido.txt) | Resumen de los códigos de salida de todas las fases | OK |

## Convención de cada fase

Cada carpeta `NN_<fase>/` tiene:

- `README.md`: objetivo, comandos, resultado, observaciones y tabla de intentos.
- `codigo/`: capturas del código que se ejecuta.
- `ejecucion/`: salida de cada comando (`.txt` completo y `.png`, con fecha y código de salida).
- `resultados/`: archivos generados y comprobaciones.
- `intentos/NN_<descripcion>/`: intentos fallidos o incompletos, **conservados sin modificar**, con un README sobre qué falló y cómo se corrigió.

La evidencia fallida nunca se borra: forma parte del proceso.

## Cómo repetir todo

Desde la raíz del repositorio, con `backend/.venv` instalado (`npm run setup`):

```powershell
backend\.venv\Scripts\python.exe pruebas\_herramientas\recorrido_completo.py
```

El script ejecuta las fases en orden, se detiene en la primera que falle y vuelve a generar cada `.txt`
y `.png` de esta carpeta. La fase 4 levanta el servidor en el puerto 3100 y usa Playwright, que no es
dependencia del proyecto: si no está disponible, ejecute `npx playwright@1.63.0 install chromium`.

## Herramientas

- [_herramientas/recorrido_completo.py](_herramientas/recorrido_completo.py): orquesta las cuatro fases.
- [_herramientas/evidencia.py](_herramientas/evidencia.py): ejecuta un comando y guarda su salida como `.txt` y `.png`; también captura código y archivos JSON.
- [_herramientas/capturar_frontend.cjs](_herramientas/capturar_frontend.cjs): abre `/simulacion.html`, carga casos y comprueba que no se vea información protegida.
- [03_validacion/verificar_casos.py](03_validacion/verificar_casos.py): validación de esquema, lote curado y vista pública.

## Alcance

Estas evidencias cubren el flujo de datos. No acreditan el diálogo clínico, la evaluación del
estudiante ni la persistencia en base de datos, que siguen pendientes.
