# 22. Pedidos genéricos al laboratorio y a radiología

## Objetivo

Cuando el estudiante pedía un examen con palabras genéricas («¿qué resultados tienen los análisis de sangre
de antes de la operación?»), el sistema no lo relacionaba con ningún examen del caso. El laboratorio no
recibía datos y, siguiendo sus instrucciones, contestaba «Ese examen no se realizó en este paciente», aunque
el caso sí tuviera el resultado (en CIR-005, las pruebas de coagulación). El estudiante creía que el examen no
existía y dejaba de buscarlo.

## Qué se hizo

| Commit | Cambio |
| --- | --- |
| `e3b5a70` | `DisclosurePolicy.names_specific_exam` (`engine/disclosure`) distingue si el mensaje nombra un examen concreto, usando la lista de exámenes que ya reconoce el sistema. «Análisis de sangre», «exámenes de laboratorio» o «estudio de imagen» cuentan como genéricos |
| `f112e66` | Si el laboratorio o radiología no reciben datos y el pedido es genérico, el orquestador lo marca y el agente responde con una frase fija, sin modelo de lenguaje: «¿Qué examen en concreto desea solicitar?» o «¿Qué estudio de imagen desea solicitar?». Si se nombró un examen que el caso no tiene, sigue respondiendo «Ese examen no se realizó» |

Se respeta la separación de la arquitectura: la detección vive en `engine/`, el orquestador pasa el
resultado en el contexto y el agente (`ai/`) no importa nada de `engine/`. Un pedido genérico no revela
ningún dato: el estudiante sigue teniendo que saber qué examen pedir.

| Pedido (CIR-005) | Antes | Después |
| --- | --- | --- |
| «Análisis de sangre de antes de la operación» | «Ese examen no se realizó» (falso) | «¿Qué examen en concreto desea solicitar?» |
| «Pruebas de coagulación» | Resultados | Resultados |
| «Un hemograma» (el caso no lo tiene) | «Ese examen no se realizó» | «Ese examen no se realizó» |

## Comandos

Desde la raíz, contra el sitio publicado o un servidor local:

```powershell
backend\.venv\Scripts\python.exe pruebas\22_pedidos_genericos\probar_pedidos.py [URL]
```

Pruebas automáticas, desde `backend/`:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## Resultados

| Ejecución | Resultado | Evidencia |
| --- | --- | --- |
| Antes, en el sitio publicado (Groq) | 2 de 5: los 3 pedidos genéricos recibían «no se realizó», dos de ellos en casos que sí tienen el examen | `intentos/01_antes/` |
| Después, servidor local con Groq | 5 de 5 | `ejecucion/01_pedidos_local.txt`, `_terminal.png` |
| Pruebas del backend | 175 aprobadas (4 nuevas) | `ejecucion/02_pruebas_backend.txt`, `_terminal.png` |
| Batería de los 13 casos (fase 18) | Sigue en 13 de 13 | se repitió sin cambios |

Las fotos (`.png`) se guardan en el equipo y no se suben a GitHub.

## Observaciones

- La lista de exámenes reconocidos es la de los casos actuales. Si un caso nuevo trae un examen con otro
  nombre, hay que agregarlo a `ALIASES` y a `EXAM_TOPICS` (en `engine/disclosure/policy.py`). Si no se agrega,
  ese examen se tomará como pedido genérico y se preguntará cuál.
- Al escribir la detección, la marca de «límite de palabra» de la expresión regular se convirtió en un
  carácter invisible y la prueba unitaria falló. Se reemplazó por una comparación de palabras completas,
  sin expresiones regulares.
