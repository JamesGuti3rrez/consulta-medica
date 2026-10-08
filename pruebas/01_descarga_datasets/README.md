# Fase 1 · Descarga del dataset

## Objetivo

Identificar la fuente y los archivos originales de MedQA, dejar claro cómo se obtienen y comprobar
que lo guardado en `data/raw/medqa/` es exactamente lo publicado (huella SHA-256).

## Fuente

| Dato | Valor |
| --- | --- |
| Dataset | MedQA (Jin et al., 2020, *What Disease does this Patient Have?*, arXiv:2009.13081) |
| Repositorio oficial | https://github.com/jind11/MedQA (rama `master`) |
| Licencia | MIT, según el `LICENSE` del repositorio (© 2022 Di Jin) |
| Responsable registrado | James Gutiérrez (`obtained_by` en el manifiesto) |

Se usan **dos archivos originales**, registrados en
[`backend/case_preparation/sources/registry.py`](../../backend/case_preparation/sources/registry.py):

| Archivo | Origen | SHA-256 | Contenido |
| --- | --- | --- | --- |
| `MedQA-master.zip` (37 558 B) | `https://github.com/jind11/MedQA/archive/refs/heads/master.zip` | `1b7af07b…d8c4b60c` | Código, README y LICENSE. No trae preguntas. |
| `data_clean.zip` (131 741 885 B) | Enlace de Google Drive de la sección *Data* del README oficial (id `1ImYUSLk9JbgHXOemfvyiDiirluZHPeQw`) | `1c2ca813…6960f629` | Preguntas (`questions/US`, `Mainland`, `Taiwan`, 30 `.jsonl`) y libros de texto. |

El 2026-10-08 se descargó de nuevo `data_clean.zip` desde esa URL, en una carpeta aparte, y la huella
coincidió con la registrada: la fuente se puede volver a obtener tal cual.

## Comandos

```powershell
cd backend
.\.venv\Scripts\python.exe -m case_preparation sources fetch --dataset medqa
cd ..
backend\.venv\Scripts\python.exe pruebas\01_descarga_datasets\listar_raw.py
```

`sources fetch` descarga los archivos que falten, **rechaza cualquier archivo cuya huella no coincida**
y escribe `data/raw/medqa/source_manifest.json` con URL, huella, fecha de obtención y fecha de
verificación de cada archivo. Al volver a ejecutarlo conserva la fecha original de obtención.

## Evidencias

- [codigo/00_registro_fuente_medqa.png](codigo/00_registro_fuente_medqa.png): registro de la fuente, con URL y huella esperada de cada archivo.
- [codigo/01_codigo_fetch_medqa.png](codigo/01_codigo_fetch_medqa.png): módulo de descarga y verificación.
- [ejecucion/02_ejecucion_fetch_medqa.png](ejecucion/02_ejecucion_fetch_medqa.png) ([.txt](ejecucion/02_ejecucion_fetch_medqa.txt)): ejecución con código de salida 0 y ambas huellas verificadas.
- [resultados/03_manifest_medqa.png](resultados/03_manifest_medqa.png): manifiesto de procedencia generado.
- [resultados/04_listado_medqa.png](resultados/04_listado_medqa.png) ([.txt](resultados/04_listado_medqa.txt)): contenido de `data/raw/medqa/` y comparación de huellas esperadas con las obtenidas.

## Observaciones

- `data/raw/` no se versiona; cualquiera puede reconstruirlo con el comando anterior.
- `data_clean_retry.zip` es una copia idéntica de `data_clean.zip` (misma huella); `extracted_test/` y `__MACOSX/` son restos locales. El pipeline no los usa.
- La licencia MIT figura en el repositorio; el archivo de Google Drive no declara una licencia propia.
## Intentos

| Intento | Resultado | Evidencia |
| --- | --- | --- |
| 1 | Fallido: ejecuciones con código 1 y 255; `data_clean.zip` sin registrar | [intentos/01_intento_fallido/](intentos/01_intento_fallido/README.md) |
| 2 | Correcto: código 0, dos archivos con huella verificada | esta carpeta (`codigo/`, `ejecucion/`, `resultados/`) |
