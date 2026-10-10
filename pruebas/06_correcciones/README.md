# Fase 6 · Auditoría y correcciones (2026-10-09)

## Objetivo

Revisar la parte de datos (descarga, conversión, validación y casos) en busca de problemas,
vulnerabilidades y desajustes, contrastarla con los documentos del proyecto y corregir cada hallazgo
en su propio commit, con evidencia.

Documentos contrastados: Arquitectura del sistema (docx y PDF con la estructura del repositorio),
Respaldo del diseño del esquema (EN-001), Pipeline de conversión (TA-002), Conversión de datasets
(SP-002), Repositorio y API de casos (EN-002), Prototipo (TA-001), Orquestador (EN-003), RAG,
aislamiento y arquitecturas de agentes. Los datos de esos informes son de experimentos: **no se tomó
ningún dato de ellos**; solo sus especificaciones y criterios.

## Correcciones

| # | Hallazgo | Corrección | Commit | Evidencia |
| --- | --- | --- | --- | --- |
| 1 | El zip del repositorio apuntaba a la rama `master`, que puede cambiar; la descarga no tenía límite de tiempo; el manifiesto de procedencia solo existía en el equipo local | Zip fijado al commit `27b02f6`, límite de 60 s y `source_manifest.json` versionado | `de2b026` | [01_fuente_fijada/](01_fuente_fijada/) |
| 2 | El extractor descomprimía zips dentro de `data/raw/` en cada ejecución (modificaba los originales), usaba un zip sin registrar, leía bancos excluidos (Mainland) y repetía preguntas (53 151 candidatos para 16 137 preguntas distintas) | Lee el zip registrado sin descomprimirlo y tras verificar su huella; solo `US_qbank.jsonl` y Taiwan en inglés; filtro del SP-002 (≥ 250 caracteres, diagnóstico o tratamiento, sin imagen); sin duplicados; archivo y línea de origen en cada candidato | `3bc5fa8` | [02_extractor/](02_extractor/): `data/raw` intacto (0 archivos cambiados), 4 790 candidatos, 0 duplicados |
| 3 | Restos locales en `data/raw/` y `data/interim/` | Eliminados tras comprobar que eran copias o restos; `listar_raw.py` lee el zip | `8d4698c` | [03_limpieza/](03_limpieza/) (antes y después) |
| 4 | Traducciones, revisiones y ajustes de los 10 casos estaban dentro del código (1239 líneas); la arquitectura (§9.3) dice que `case_preparation/` no guarda datos de casos | Movidos a `data/cases/reviews/medqa_lote_curacion.json`; el módulo queda en 387 líneas | `c0676a6` | [04_datos_fuera_del_codigo/](04_datos_fuera_del_codigo/): casos regenerados idénticos |
| 5 | Los casos validados estaban en `validated_second_pass/` y `validated/` quedaba vacía; el comando `transform` (selección rechazada) seguía activo | Casos en `data/cases/validated/`; comando y selección automática retirados | `e69b3bf` | [05_carpetas_y_comando_retirado/](05_carpetas_y_comando_retirado/) |
| 6 | PED-010 tenía una nota propia en la ficha y MED-008 conservaba el texto de la pregunta de opción múltiple | Textos fieles a la fuente; la ambigüedad de PED-010 queda en su revisión | `a00a66a` | [06_textos_fieles_a_la_fuente/](06_textos_fieles_a_la_fuente/) |
| 7 | Los alias no seguían el orden de los casos (EME-001 era «Paciente 9») | Alias con el número del caso | `129edda` | [07_alias_en_orden/](07_alias_en_orden/) |
| 8 | Los casos registraban la curación como «asistida por IA» | Redacción neutral del proceso (`curated_by: case_preparation.curation`); el método `ia_validador` se mantiene (decisión 0001 §5) | `c72d6f0` | [08_curacion_redaccion_neutral/](08_curacion_redaccion_neutral/) |
| 9 | Los casos no decían de qué archivo de MedQA salían | El índice del lote registra archivo y línea de cada pregunta | `e88c1ee` | [09_trazabilidad_origen/](09_trazabilidad_origen/): 10 de 10 coinciden con su línea original |
| 10 | `quality_gates/` estaba vacío y faltaban verificaciones del validador del SP-002 | Módulo de Quality Gates que reutiliza `server/cases/`; reglas R11 (diferenciales visibles), R12 (texto de la pregunta), R13 (cifras inventadas) y aviso W01 (laboratorio o examen en `public`) | `61887e5` | [10_quality_gates_sp002/](10_quality_gates_sp002/) |
| 11 | La prueba del simulador dependía de Playwright en la caché de npx de un solo equipo | Playwright `1.63.0` como dependencia de desarrollo del proyecto | `61bdd24` | [11_playwright_del_proyecto/](11_playwright_del_proyecto/) |
| 12 | La API ignoraba la especialidad: «las cinco especialidades cargan el mismo caso» (arquitectura, pendientes) | `GET /api/caso?especialidad=…`, conteo por especialidad en `/api/status` y el simulador pasa el parámetro de su URL | `0dab41d` | [12_caso_por_especialidad/](12_caso_por_especialidad/) |
| 13 | La documentación decía que las reglas cruzadas no existían, describía carpetas sin uso y la decisión 0001 no reflejaba la fuente real | README de `data/`, del pipeline y del esquema, tabla de reglas en `docs/data_model/`, decisión 0001 y nota de traspaso actualizadas | `889b65f` | — |
| 14 | La comprobación 6 de `verificar_casos.py` (banco de origen de cada pregunta) buscaba la carpeta `data_clean/` descomprimida, que se eliminó en la corrección 3: se omitía sin fallar (la salida de `03_validacion/ejecucion/01_verificar_casos.txt` muestra «[OMITIDO]») | Lee las preguntas dentro de `data_clean.zip`, sin descomprimirlo; los 10 casos aparecen en el banco US o Taiwan | (rama `feature/integracion-sma-rag`) | [14_banco_de_origen/](14_banco_de_origen/) |

Comprobación final: el recorrido completo pasa 8 de 8 y `pytest` pasa 45 de 45
([../05_recorrido_completo/](../05_recorrido_completo/README.md)).

## Desajustes con los documentos del proyecto que no se corrigieron

Requieren una decisión del equipo o coordinación con otro integrante:

| Documento | Qué pide | Situación | Quién decide |
| --- | --- | --- | --- |
| Arquitectura §6.1, SP-002 | Zona inicial con motivo, datos de llegada y signos vitales; anamnesis, examen, laboratorio e imágenes en `on_request` | Toda la historia está en `public` (aviso W01 en 4 casos) y `on_request` solo tiene un marcador. Hay que redistribuir los 10 casos | James, con los nombres de temas (`requires`) acordados con Julio |
| Decisión 0001 §6 | Misma información que el enunciado en inglés | El texto público es un resumen adaptado; hacer la traducción completa junto con la redistribución | James |
| Esquema `evaluation` | Preguntas clave que citen la evidencia | Cada caso tiene una sola `key_question` y su `topic` guarda el enunciado original | James y Julio (evaluación) |
| Arquitectura §7 | «Ningún proceso automático marca un caso como curado: eso lo hace una persona con formación médica» | La curación la marca el pipeline; no hay revisor con formación médica | Equipo (y docente) |
| Arquitectura §13, EN-001 | Campo de dificultad; nombre y grupo sanguíneo en la tablilla | El esquema no tiene esos campos; agregarlos requiere nueva versión del esquema | Equipo |
| TA-001 | Portada «Elige tu caso» con especialidad | La portada actual enlaza directo al simulador; la API ya admite la especialidad | Quien lleve el frontend |
| EN-002 | Índice de `on_request` sin valores clínicos | No existe esa ruta; tiene sentido después de la redistribución | Julio (acceso por rol) |
| Esquema (descripción) | Remite a `validar_caso.py` | La función la cumple `rules.py`; corregir la descripción cambia el esquema | Equipo |

## Sin vulnerabilidades graves

Sin secretos en el repositorio (`.env.example` vacío); el simulador muestra los datos con
`textContent`; la descompresión ya no escribe en disco; las descargas verifican la huella y tienen
límite de tiempo.
