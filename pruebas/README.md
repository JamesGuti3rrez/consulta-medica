# Evidencias del flujo de datos (Sprint 1)

Recorrido comprobado: **fuente MedQA → descarga verificada → candidatos → 10 casos JSON → validación → frontend**.
Todas las capturas están en **vista de escritorio/PC (1440 px de ancho)**; ninguna usa vista móvil.

> **Fotos:** desde el 12 de octubre de 2026 las fotos (`.png`, `.jpg`) de esta carpeta no se suben a GitHub; se
> guardan en el equipo del responsable y se entregan aparte. Los enlaces a imágenes de estos README solo funcionan
> en esa copia local. El código, las salidas en texto y los resultados en JSON sí están en el repositorio.

| Fase | Carpeta | Qué demuestra | Resultado |
| --- | --- | --- | --- |
| 1. Descarga | [01_descarga_datasets/](01_descarga_datasets/README.md) | Fuente y archivos originales identificados, URL de obtención y huella SHA-256 verificada | OK |
| 2. Conversión a JSON | [02_transformacion/](02_transformacion/README.md) | Se vuelven a generar los 10 casos con IDs 001–010 y el resultado es idéntico al versionado | OK |
| 3. Validación | [03_validacion/](03_validacion/README.md) | Los JSON cumplen el esquema, las reglas cruzadas R01–R13 y la decisión 0001; la demo usa solo los casos curados | OK (intento 2) |
| 4. Frontend | [04_frontend/](04_frontend/README.md) | Un caso por especialidad cargado en pantalla, solo con datos públicos | OK (intento 3) |
| 5. Recorrido completo | [05_recorrido_completo/](05_recorrido_completo/README.md) | Todas las fases seguidas, con foto de la terminal | OK (intento 2) |
| 6. Auditoría y correcciones | [06_correcciones/](06_correcciones/README.md) | Hallazgos de la revisión, contraste con los documentos del proyecto y una corrección por commit | OK |
| 7. Integración del SMA y del RAG | [07_integracion_sma_rag/](07_integracion_sma_rag/README.md) | El trabajo de la rama `Rodrigo` adaptado a la estructura y a los datos actuales, con una consulta simulada | OK |
| 8. Redistribución de los casos | [08_redistribucion_casos/](08_redistribucion_casos/README.md) | Cada dato en su zona (`public` u `on_request`), con dueño, tema y preguntas clave; traducción completa | OK |
| 9. Presentación narrada | [09_narracion_simulador/](09_narracion_simulador/README.md) | El doctor presenta un caso al azar de la especialidad elegida, con burbuja, voz y chat | OK |
| 10. Mejoras de los casos | [10_mejoras_casos/](10_mejoras_casos/README.md) | Nombres de los pacientes, más datos en GOB-003 y PED-010 y datos que descartan cada diferencial | OK |
| 11. Sesiones en Supabase | [11_sesiones_supabase/](11_sesiones_supabase/README.md) | Las consultas se guardan en Supabase: en Vercel cualquier instancia del servidor encuentra la sesión (antes, HTTP 404) | OK |
| 12. Familias sintéticas | [12_familias_sinteticas/](12_familias_sinteticas/README.md) | Tres casos con la misma presentación y distinto diagnóstico; con el modelo real, cada pedido revela el dato correcto y las hipótesis se descartan hasta dejar solo el diagnóstico | OK (intento 3) |
| 13. Guiones por paciente | [13_guiones_por_paciente/](13_guiones_por_paciente/README.md) | Los 13 casos recorridos con su guion (qué preguntar y qué no) con el modelo real: 114 de 114 pedidos correctos | OK (intento 2) |
| 14. Motor clínico | [14_motor_clinico/](14_motor_clinico/README.md) | Trabajo de la rama `julio`: con los 13 casos curados, acceso por rol, alertas de contraindicación, signos vitales conservados y evaluación final | OK |
| 15. Integración del motor clínico | [15_integracion_motor_clinico/](15_integracion_motor_clinico/README.md) | El motor en `main`, conectado a la API, a las sesiones y a la hoja de evaluación del simulador | OK (intento 3) |

## Convención de cada fase

Cada carpeta `NN_<fase>/` tiene:

- `README.md`: objetivo, comandos, resultado, observaciones y tabla de intentos.
- `codigo/`: capturas del código que se ejecuta.
- `ejecucion/`: salida de cada comando: `_terminal.png`, foto real de la ventana de PowerShell donde se ejecutó, que muestra el equipo, la ruta y el comando; y `.txt` con el texto completo, la fecha y el código de salida. Los `.png` sin `_terminal` son imágenes generadas desde el texto en las primeras ejecuciones; ya no se generan.
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
- [_herramientas/captura_terminal.ps1](_herramientas/captura_terminal.ps1): ejecuta un comando en una ventana real de PowerShell (1440 px de ancho, alto de pantalla completa) y la fotografía página por página, uniendo las páginas en una sola imagen con toda la salida (`-ConservarPaginas` guarda además cada página suelta). Su primer intento, que solo captaba el final, está en `_herramientas/intentos/`.
- [_herramientas/evidencia.py](_herramientas/evidencia.py): ejecuta un comando y guarda su salida como `.txt` y `.png`; también captura código y archivos JSON.
- [_herramientas/capturar_frontend.cjs](_herramientas/capturar_frontend.cjs): abre `/simulacion.html`, carga casos y comprueba que no se vea información protegida.
- [03_validacion/verificar_casos.py](03_validacion/verificar_casos.py): validación de esquema, lote curado y vista pública.

## Alcance

Las fases 1 a 5 cubren el flujo de datos; las siguientes, el diálogo clínico (7, 9, 12 y 13), la
persistencia de sesiones en Supabase (11) y el motor clínico con la evaluación del estudiante (14 y 15).
