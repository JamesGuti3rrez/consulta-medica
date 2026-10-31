# 33. Publicación en main y Vercel: James, Rodrigo y Julio juntos

El 31 de octubre de 2026 `main` avanzó de `cb283d5` a `8ba0758`, la rama `James`, que ya contenía todo:

- **De James:** HU-006 (diagnóstico final), HU-007 (reporte final), TA-011, la voz con edge-tts (TA-019), la escena
  con avatares, las preguntas sin dato y el cierre sin la migración 0007.
- **De Rodrigo:** grupos y Panel Doctor, diálogo directo, exámenes sintéticos y validador de casos.
- **De Julio:** el benchmark RAGAS del PR #3, que GitHub marcó como fusionado.

Fue un avance directo, sin fusión, porque `main` ya estaba incluido en `James`. Antes de publicar, la suite completa del
backend pasaba en ese mismo commit (875, `pruebas/32_cierre_sin_migracion/ejecucion/05_regresion_backend`).

Vercel publicó la versión nueva con `TTS_PROVIDER=edge`. Los exámenes sintéticos quedan activos porque heredan
`SYNTHETIC_CASE_DATA`. La tabla `diagnosticos_finales` (migración 0007) todavía no existe: el cierre del alumno funciona
igual y el registro por intentos queda pendiente hasta aplicarla.

## Comprobación en producción (https://consulta-medica-three.vercel.app)

| Corrida | Archivo | Resultado |
|---|---|---|
| Voz neuronal para los 7 personajes, personaje no permitido y `simulacion.js` nuevo | `ejecucion/01_voz_produccion` | TODO PASA |
| Escena: doctor en la presentación, paciente mujer (CIR-006) en el interrogatorio, hallazgos del doctor y del laboratorio | `ejecucion/02_escena_produccion` | 18 de 18 |
| Alumno con sesión (temporal, borrado al final) cierra la consulta sin la migración 0007 | `ejecucion/03_cierre_alumno_produccion` | 10 de 10 |
| Conversación real con las preguntas que antes salían raras (CIR-005) | `ejecucion/04_conversacion_produccion` | TODO PASA |
| Páginas, API e imágenes de la escena | `ejecucion/05_paginas_produccion` | TODO PASA |

La primera captura de la voz falló porque la herramienta no encontró la ventana de la terminal; se repitió y quedó la
corrida válida.
