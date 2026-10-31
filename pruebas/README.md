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
| 16. Historial de simulaciones | [16_historial_simulaciones/](16_historial_simulaciones/README.md) | Cada consulta de un alumno con sesión iniciada se guarda en Supabase y aparece en «Mis simulaciones»; los invitados no guardan y nadie puede quedarse con la consulta de otro | OK (intento 2) |
| 17. Probar otro caso o cerrar | [17_otro_caso/](17_otro_caso/README.md) | La hoja de evaluación abre otro paciente de la misma especialidad sin repetir el anterior, o vuelve a la portada | OK |
| 18. Un solo diagnóstico por caso | [18_casos_con_un_solo_diagnostico/](18_casos_con_un_solo_diagnostico/README.md) | Con el guion de cada paciente queda en pie solo el diagnóstico en los 13 casos (antes, 7): datos que agregó el equipo con fuente clínica (decisión 0002) y regla R15 para todo caso curado | OK (intento 3) |
| 19. Aviso de privacidad | [19_aviso_privacidad/](19_aviso_privacidad/README.md) | Aviso según la Ley 29733 enlazado desde la portada y «Mis simulaciones»; crear cuenta exige aceptarlo y guarda versión y fecha | OK (intento 2) |
| 20. Sinónimos del diagnóstico | [20_sinonimos_diagnostico/](20_sinonimos_diagnostico/README.md) | Cada caso acepta al menos tres formas de nombrar su diagnóstico (52 en total, antes 21), base para calificar el diagnóstico escrito | OK |
| 21. Cierre del sprint 1 | [21_cierre_sprint1/](21_cierre_sprint1/README.md) | Qué pedía el sprint, qué se entregó y dónde está la prueba de cada componente; recorrido completo con un comando | ver README |
| 22. Pedidos genéricos | [22_pedidos_genericos/](22_pedidos_genericos/README.md) | Ante un pedido sin nombre de examen («análisis de sangre»), el laboratorio y radiología preguntan cuál en lugar de afirmar que no se realizó | OK (intento 2) |
| 23. Numeración de los casos | [23_numeracion_casos/](23_numeracion_casos/README.md) | Casos agrupados por especialidad (EME 001-002, GOB 003-004, CIR 005-006, MED 007-008, PED 009-010) con equivalencias para la evidencia anterior | OK (intento 2) |
| 24. Guía de preguntas por paciente | [24_guia_por_paciente/](24_guia_por_paciente/README.md) | Documento «Guiones de prueba por paciente» 3.0, generado desde los datos: por qué de cada pregunta y por qué se descarta cada enfermedad; 124 de 124 pedidos con el modelo real | OK (intento 2) |
| 25. Autorización de sesiones (TA-011) | [25_autorizacion_sesiones/](25_autorizacion_sesiones/README.md) | Cada consulta solo la abre quien la empezó: el alumno con su token o el invitado con una credencial de 256 bits; otro usuario recibe 404 sin datos. 23 casos fallaban antes; después pasan 37 de 37 en local y 40 de 40 en vivo contra el Supabase de producción; el preview de Vercel queda pendiente (sin claves de Groq) | OK local y en vivo; preview pendiente |
| 26. Reporte final (HU-007, entregada como HU-006) | [26_reporte_final/](26_reporte_final/README.md) | Al cerrar, el dueño recibe un reporte armado solo con datos de su caso: diagnóstico de referencia y propuesto, preguntas clave obtenidas y faltantes con su porqué, exámenes, tratamiento propuesto y de referencia, puntajes y evidencia revelada; antes del cierre, 409; otra persona, 404. Suite 14 FALLA antes y 17 de 17 después (local y en vivo), 43 casos sin fuentes ajenas, E2E 21 de 21; el preview de Vercel queda pendiente (sin claves de Groq) | OK local, en vivo y E2E; preview pendiente |
| 28. Diagnóstico final (HU-006) | [28_diagnostico_final/](28_diagnostico_final/README.md) | El diagnóstico es obligatorio y se valida en el navegador y en el servidor; el alumno confirma el cierre; el servidor lo registra por alumno, caso, sesión e intento antes de cerrar y, si falla, la consulta sigue abierta; un segundo envío no cambia lo registrado; el acceso ajeno se rechaza. Suite 20 FALLA antes y 25 de 25 después, E2E 33 de 33, regresión 662 | OK local y E2E; en vivo pendiente de la migración 0007 |
| 29. Escena de la consulta | [29_escena_consulta/](29_escena_consulta/README.md) | El doctor presenta el caso y en el interrogatorio se ve al paciente (hombre o mujer) con su globo de diálogo; si el doctor o un servicio entrega un hallazgo aparece el doctor y luego vuelve el paciente. Incluye la regresión tras unir la rama de Rodrigo (grupos, diálogo directo, panel docente, HU-006, HU-007, voz). Antes 0 de 7, después 18 de 18 en hombre, mujer y celular; backend 825 | OK local y E2E |
| 30. Preguntas sin dato | [30_preguntas_sin_dato/](30_preguntas_sin_dato/README.md) | Sin hallazgos registrados el doctor lo dice (no pide al estudiante describirlos); si el generador de datos sintéticos rechaza, responde el agente paciente con naturalidad (no «No entendí bien»); «¿Desde cuándo tiene la molestia?» no se responde con el año de un antecedente. Antes 5 + 5 fallan, después 16 de 16; conversaciones reales CIR-005 y MED-008 sin respuestas raras; backend 841 | OK local y con el modelo real |
| 31. Integración del PR #3 de Julio | [31_integracion_julio/](31_integracion_julio/README.md) | Benchmark RAGAS de Julio unido a James: se añade el conjunto de datos que faltaba (generado por su script), las suites en vivo conservan Supabase y se resuelve el choque con Rodrigo. PR tal cual: 3 fallan; unido: backend 868, RAGAS 33 de 33, escena 18 de 18, HU-006 33 de 33 | OK local |

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

El script ejecuta las fases del flujo de datos (1 a 4) y las comprobaciones del simulador que se pueden
repetir sin costo (14, 15, 17, 18, 19 y 20), se detiene en la primera que falle y deja un resumen en
`05_recorrido_completo/resumen_recorrido.txt`. Las fases 1 a 4 regeneran su `.txt` en su carpeta; las demás
escriben en `21_cierre_sprint1/recorrido/`. Corre sin Groq, sin trazas a LangSmith y sin crear cuentas: la
fase 16, que necesita un alumno temporal en Supabase, se repite aparte con su README. El servidor de prueba
usa el puerto 3100 y las pruebas del navegador usan Playwright: si no está disponible, ejecute
`npx playwright@1.63.0 install chromium`.

## Herramientas

- [_herramientas/recorrido_completo.py](_herramientas/recorrido_completo.py): repite el flujo de datos y las comprobaciones del simulador del sprint 1.
- [_herramientas/captura_terminal.ps1](_herramientas/captura_terminal.ps1): ejecuta un comando en una ventana real de PowerShell (1440 px de ancho, alto de pantalla completa) y la fotografía página por página, uniendo las páginas en una sola imagen con toda la salida (`-ConservarPaginas` guarda además cada página suelta). Su primer intento, que solo captaba el final, está en `_herramientas/intentos/`.
- [_herramientas/evidencia.py](_herramientas/evidencia.py): ejecuta un comando y guarda su salida como `.txt` y `.png`; también captura código y archivos JSON.
- [_herramientas/capturar_frontend.cjs](_herramientas/capturar_frontend.cjs): abre `/simulacion.html`, carga casos y comprueba que no se vea información protegida.
- [03_validacion/verificar_casos.py](03_validacion/verificar_casos.py): validación de esquema, lote curado y vista pública.

## Alcance

Las fases 1 a 5 cubren el flujo de datos; las siguientes, el diálogo clínico (7, 9, 12 y 13), la
persistencia de sesiones en Supabase (11) el motor clínico con la evaluación del estudiante (14 y 15) y el historial de simulaciones (16).
