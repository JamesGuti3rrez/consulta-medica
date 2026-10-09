# sources/

Primer paso del pipeline: **obtener el dataset fuente** y dejarlo, sin modificar, en `data/raw/`.

## Qué hace

- Descarga el dataset (por ejemplo, MedQA) o lo genera (Synthea produce pacientes sintéticos con su propio programa).
- Verifica que el archivo obtenido sea el esperado, comparando su huella SHA-256.
- Registra la procedencia: de dónde vino, qué versión, con qué licencia y cuándo se obtuvo.

## Registro de cada fuente

Cada dataset que use el proyecto debe tener un registro con estos campos. Se completarán cuando el equipo elija las fuentes; aquí no se deja ningún valor de ejemplo.

| Campo | Para qué sirve |
| --- | --- |
| `name` | Nombre del dataset. Debe coincidir con `source.dataset` del esquema (`MedQA` o `Synthea`). |
| `url` | Dirección oficial de descarga o del generador. |
| `version` | Versión, etiqueta o fecha de publicación usada. |
| `license` | Licencia del dataset. Se copia luego a `source.license` de cada caso. |
| `files` | Archivos esperados y su huella SHA-256. |
| `obtained_at` | Fecha en que se descargó o generó. |
| `obtained_by` | Integrante responsable. |

## Reglas

- Los archivos descargados van a `data/raw/<nombre_del_dataset>/` y **no se suben a Git**. Cualquiera puede volver a obtenerlos con este módulo.
- Este módulo **no transforma ni filtra** datos: eso lo hacen `adapters/` y `transform/`.
- Solo fuentes públicas o sintéticas, nunca datos de pacientes reales.
- Las fuentes admitidas son las que permite `caso.schema.json`. Agregar otra fuente requiere cambiar el esquema y registrar la decisión en `docs/decisions/`.

Fuente registrada: **MedQA** (`registry.py`), con dos archivos originales: `MedQA-master.zip` (repositorio y licencia) y `data_clean.zip` (preguntas, enlazado desde el README oficial). Cada uno tiene su URL y huella SHA-256 esperada; `fetch.py` rechaza un archivo cuya huella no coincida.
