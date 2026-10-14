# 20. Sinónimos del diagnóstico

## Objetivo

El estudiante escribe su diagnóstico con sus palabras: «síndrome de Sheehan», «necrosis hipofisaria posparto»
o «infarto hipofisario» nombran lo mismo. Para que algún día se pueda comparar ese diagnóstico con el del
caso, cada caso debe aceptar varias formas de nombrarlo. Los 10 casos de MedQA solo tenían su nombre; los 3
sintéticos (EME-101 a EME-103) ya tenían sinónimos.

Esta fase prepara el dato, que es parte de los casos. Calificar el diagnóstico escrito es trabajo del motor de
evaluación (Julio) y queda para después.

## Qué se hizo

| Commit | Cambio |
| --- | --- |
| `47ef69d` | El generador toma `diagnosis_synonyms` del archivo de revisión (`clinical_overrides`), con el nombre primero y sin repetidos |
| `2eddadc` | Sinónimos de los 10 casos de MedQA y una prueba que exige al menos tres formas de nombrar el diagnóstico en todo caso curado |

Los sinónimos son nombres clínicos equivalentes: nombres alternativos, epónimos y siglas como «HSA». No se
agregaron diagnósticos distintos. La regla R04, que impide que el diagnóstico aparezca en lo que ve el
estudiante, revisa también los sinónimos, y los 13 casos la pasan.

## Comandos

Desde la raíz:

```powershell
backend\.venv\Scripts\python.exe pruebas\20_sinonimos_diagnostico\mostrar_sinonimos.py
```

Desde `backend/`:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## Resultados

| Ejecución | Resultado | Evidencia |
| --- | --- | --- |
| Sinónimos por caso | 52 formas de nombrar el diagnóstico en 13 casos (antes, 21) | `ejecucion/01_sinonimos.txt`, `_terminal.png` |
| Pruebas del backend | 171 aprobadas (2 nuevas) | `ejecucion/02_pruebas_backend.txt`, `_terminal.png` |

Las fotos (`.png`) se guardan en el equipo y no se suben a GitHub.

## Observaciones

- Comparar el diagnóstico escrito con estos sinónimos requiere normalizar el texto (mayúsculas, tildes y
  palabras sobrantes) en el motor de evaluación. Se deja como siguiente paso para Julio.
