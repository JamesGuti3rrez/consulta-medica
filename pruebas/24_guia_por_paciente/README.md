# 24. Guía de preguntas por paciente, versión 3.0

## Objetivo

Actualizar el documento «Guiones de prueba por paciente» (`Entregables/05_Guia_de_pruebas/`) con lo que cambió
desde su versión 2.0 (12 de octubre):

- **Códigos nuevos** de los casos (fase 23).
- **Exámenes agregados** para que cada caso llegue a un solo diagnóstico (fase 18).
- **Listas de diferenciales corregidas** de CIR-006 y GOB-003.

Además, explicar en cada paso por qué se pregunta y por qué se va descartando cada enfermedad.

## Qué tiene el documento

Para cada uno de los 13 casos, en el orden de su número:

- Qué puede ser al empezar.
- Cada paso, con:
  - qué decir y por qué se pregunta;
  - quién responde y qué contestó el simulador con el modelo real;
  - **qué cambia y por qué**: qué enfermedad pasa a menos probable o descartada, y la razón clínica ligada al
    dato;
  - qué queda.
- Al terminar el guion: lo que queda, que en los 13 casos es solo el diagnóstico.
- **Por qué se descarta cada una:** resumen del razonamiento para todas las enfermedades alternativas.
- Qué no preguntar, con la respuesta del simulador.
- Anexo con el diagnóstico y las enfermedades que cada caso permite descartar.

Son 35 páginas. La versión 2.0 se guarda en `version_anterior/`, solo en el equipo.

## Cómo se genera

El documento ya no se arma a mano. Tres piezas versionadas:

| Archivo | Qué hace |
| --- | --- |
| [descartes.py](descartes.py) | Por qué cada dato descarta cada uno de los 48 diagnósticos diferenciales, en palabras sencillas y ligado al dato del caso |
| [generar_guia.py](generar_guia.py) | Une los guiones (`13_guiones_por_paciente/guiones.py`), los casos curados, las explicaciones y las respuestas reales; sigue el estado de cada enfermedad y escribe `resultados/guia.json`. Falla si a alguna enfermedad le falta su explicación |
| [generar_docx.cjs](generar_docx.cjs) | Convierte `guia.json` en el Word, con el formato de los entregables (A4, Arial, márgenes de 2 cm) |

Desde la raíz:

```powershell
backend\.venv\Scripts\python.exe pruebas\24_guia_por_paciente\generar_guia.py pruebas\24_guia_por_paciente\resultados\resultados_guiones_groq.json
node pruebas/24_guia_por_paciente/generar_docx.cjs "Entregables/05_Guia_de_pruebas/Guiones de prueba por paciente.docx"
```

`generar_docx.cjs` necesita el paquete `docx` (`npm install --no-save docx@9.5.1`). Las respuestas salen de la
batería de la fase 13 con el modelo real (`resultados/resultados_guiones_groq.json`).

## Resultados

| Ejecución | Resultado | Evidencia |
| --- | --- | --- |
| Batería de los 13 guiones con Groq | 124 de 124 pedidos correctos (tras corregir GOB-003; ver intento) | `resultados/resultados_guiones_groq.json`, `ejecucion/01_guion_gob003_groq.txt`, `_terminal.png` |
| Contenido de la guía | 13 de 13 casos terminan con un solo diagnóstico | `ejecucion/02_generar_guia.txt`, `resultados/guia.json` |
| Documento Word | 35 páginas, revisado página por página (convertido a PDF con Word) | `ejecucion/03_generar_docx.txt`, `ejecucion/02_generar_guia_terminal.png` |

Las fotos (`.png`) y el Word se guardan en el equipo y no se suben a GitHub.

## Intento fallido

### Los antecedentes menstruales de GOB-003 se revelaban al preguntar por el parto

En la primera corrida con Groq (`intentos/01_menstruales_revelados_en_el_paso_1/`) salió 123 de 124: en GOB-003, el
paso «¿Cómo eran sus reglas antes del embarazo?» no revelaba nada nuevo. El dato ya se había revelado en el
paso 1, «¿Cómo fue el parto?», porque los dos compartían el tema «antecedentes gineco-obstétricos». La paciente
no lo había dicho, pero el sistema lo daba por visto. En la guía, eso habría descartado el tumor hipofisario un
paso antes de que el estudiante leyera el dato.

Corrección:

- `bdef89e`: los antecedentes menstruales pasan al tema «antecedentes personales», que en GOB-003 no usa otro
  dato.
- `13da1f5`: el guion los pide con «¿Qué antecedentes tenía antes del embarazo? ¿Reglas irregulares, dolores de
  cabeza o problemas de la vista?».

Un primer intento de redacción («¿Tenía algún problema de salud...?») tampoco funcionó, porque el sistema
reconoce «problemas de salud» en plural. Con la pregunta final, GOB-003 queda en 8 de 8 y la batería de la fase
18 sigue en 13 de 13.
