# 18. Casos que llegan a un solo diagnóstico

## Objetivo

En algunos casos el estudiante se quedaba con dos o más diagnósticos posibles aunque pidiera todos los
datos: 10 de los 48 diagnósticos diferenciales no tenían ningún dato que los descartara, en 6 casos. Las
preguntas de MedQA piden el diagnóstico «más probable»: traen lo que apoya la respuesta, pero no siempre
lo que excluye las otras opciones.

Objetivo: que en los 13 casos curados, siguiendo el guion del paciente, quede en pie solo el diagnóstico.

## Decisión

[Decisión 0002](../../docs/decisions/0002-complementos-del-equipo.md): el equipo puede completar un caso de
MedQA con el dato que decide, bajo estas condiciones:

- solo lo necesario para descartar un diferencial;
- coherente con la fuente;
- con una fuente clínica registrada;
- marcado como complemento;
- sin cifras nuevas.

Los diferenciales mal planteados se corrigen, no se completan.

## Qué se cambió en cada caso

| Caso | Diferencial que quedaba en pie | Qué se hizo | Fuente |
| --- | --- | --- | --- |
| CIR-005 | Hemofilia B | Dosaje de factores: VIII disminuido, IX normal | CDC hemofilia |
| CIR-006 | Neumonía posoperatoria; atelectasia | La neumonía es el foco de la sepsis, no una alternativa: se reemplazó por «SIRS no infeccioso» (opción del enunciado). Radiografía de tórax con consolidación y sin colapso; hemograma con leucocitosis | MedlinePlus atelectasia; CDC sepsis |
| EME-001 | Tormenta tiroidea; estado epiléptico | Función tiroidea normal (toma propranolol por hipertiroidismo); electroencefalograma sin actividad epileptiforme | MedlinePlus tormenta tiroidea; MedlinePlus EEG |
| EME-002 | Hemorragia intracerebral | Tomografía de cráneo: sangre subaracnoidea sin hematoma intraparenquimatoso | NICE hemorragia subaracnoidea |
| GOB-003 | Atonía uterina; síndrome de Sheehan; restos placentarios | Uno de los diferenciales era el propio diagnóstico y la atonía explica la hemorragia, no la falta de lactancia. Se usan las opciones del enunciado (restos placentarios, tristeza puerperal, tumor hipofisario) más la hipofisitis. Datos nuevos: prolactina baja, ánimo conservado, reglas normales y sin cefalea ni problemas de la vista antes del parto | NCBI síndrome de Sheehan; MedlinePlus depresión posparto |
| MED-008 | Otras infecciones por garrapatas | Hemograma y perfil hepático normales (sin leucopenia, trombocitopenia ni transaminasas altas) | CDC ehrlichiosis |

Cada caso suma también una pregunta clave con el examen decisivo, así que el puntaje máximo exige pedirlo.
Las fuentes nuevas (MedlinePlus y CDC) se verificaron en línea antes de citarlas. Las páginas de NCBI
piden captcha y no se pudieron verificar, así que solo se usa la que ya estaba registrada.

**Revisión clínica pendiente:** los complementos los propuso el equipo con su fuente, pero deben pasar por la
revisión de un médico o del docente antes de usarse con estudiantes.

## Cambios en el código

| Commit | Cambio |
| --- | --- |
| `ae5e3b5` | Decisión 0002 |
| `b4cd7bc` | La curación exige fuente clínica registrada y motivo a cada complemento (`check_complements`) |
| `11ce1bd` | El simulador entiende los exámenes nuevos: dosaje de factores, prolactina y electroencefalograma (router y temas de revelación) |
| `5da9631` | [completar_casos.py](completar_casos.py): aplica los complementos al archivo de revisión, de a un caso |
| `fec2cbd` … `d9c5726` | Un commit por caso: CIR-005, CIR-006, EME-001, EME-002, GOB-003 y MED-008 |
| `98b4a9f` | Regla R15 en todo caso curado: un caso con un diferencial sin descarte no se acepta |
| `ae7fedf` | Guiones de la fase 13 con los exámenes nuevos. En CIR-006 y EME-002, la radiografía y la tomografía estaban en «no preguntar» porque el caso no traía el resultado; ahora sí lo trae |
| `01d0d64` | [bateria_un_solo_diagnostico.py](bateria_un_solo_diagnostico.py): recorre los 13 guiones y sigue cada diferencial |
| `82ee84a`, `02e54f9`, `edd84f7` | Corrección del intento 2 (ver abajo) |

Los casos se siguen generando de forma determinista con `python -m case_preparation curation` a partir de
`data/cases/reviews/medqa_lote_curacion.json`. Cada dato agregado lleva allí la marca
`"complemento": {"fuente": ..., "motivo": ...}`. El JSON del caso no cambia de formato, porque el esquema no
admite campos extra.

## Comandos

Desde `backend/`:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe ..\pruebas\18_casos_con_un_solo_diagnostico\bateria_un_solo_diagnostico.py --local
.\.venv\Scripts\python.exe ..\pruebas\18_casos_con_un_solo_diagnostico\bateria_un_solo_diagnostico.py
```

La primera corrida de la batería usa el proveedor determinístico (sin costo); la segunda, el modelo real
(Groq), como en el sitio publicado. En cada pedido del guion, la batería comprueba tres cosas: que responda
el agente esperado, que revele los datos esperados y que la respuesta no nombre el diagnóstico ni los
diferenciales. También muestra lo que el estudiante lee de cada dato agregado por el equipo. Un
diferencial queda descartado cuando se revelaron todos sus datos de descarte.

## Resultados

| Ejecución | Resultado | Evidencia |
| --- | --- | --- |
| Antes (versión publicada `ad2380a`) | 7 de 13 casos: CIR-005, CIR-006, EME-001, EME-002, GOB-003 y MED-008 terminaban con 1 a 3 diferenciales en pie | `intentos/01_antes_de_completar/` |
| Pruebas del backend | 166 aprobadas | `ejecucion/01_pruebas_backend.txt`, `_terminal.png` |
| Batería local | 13 de 13 casos llegan a un solo diagnóstico | `ejecucion/02_bateria_local.txt`, `_terminal.png` |
| Batería con Groq | 13 de 13 casos llegan a un solo diagnóstico; ninguna respuesta nombra el diagnóstico ni los diferenciales; en cada complemento el estudiante lee el dato completo (por ejemplo, «El factor VIII está disminuido; el factor IX es normal.») | `ejecucion/03_bateria_groq.txt`, `_terminal.png` |
| Diferenciales sin dato que los descarte | De 10 de 48 a 0 de 48 | regla R15 |

Las fotos (`.png`) se guardan en el equipo y no se suben a GitHub.

## Intentos fallidos

### Intento 1: antes de completar los casos

`intentos/01_antes_de_completar/` es la batería corrida sobre la versión publicada, en una copia temporal
del repositorio. Reproduce el problema: 6 casos con diferenciales en pie.

### Intento 2: el dato se revelaba, pero la paciente lo resumía de más

En la primera corrida con Groq (`intentos/02_respuestas_incompletas/bateria_groq_v1.txt`), los 13 casos
pasaban, pero en GOB-003 la paciente respondió «No.» a «¿Tiene algún otro síntoma?», sin hablar de su ánimo.
A la pregunta por las reglas respondió «Tenía reglas regulares.», sin mencionar la cefalea ni la vista. La
batería solo miraba qué datos se revelaban, no lo que lee el estudiante.

Corrección:

- `82ee84a`: las preguntas sobre el ánimo («ánimo», «triste», «llanto») entran en síntomas asociados.
- `02e54f9`: preguntas directas en el guion de GOB-003.
- `edd84f7`: la batería imprime la respuesta de cada complemento, para revisarla.

Con eso, la paciente responde completo: «Me siento con ánimo para cuidar al bebé y quiero amamantar. No me
siento triste...» y «Tenía reglas regulares antes del embarazo. Nunca tuve cefalea persistente ni problemas
de la vista».

## Observaciones

- Si el estudiante pregunta de forma muy general («¿algún otro síntoma?»), el modelo puede resumir de más.
  Es un comportamiento del modelo (parte de Rodrigo): conviene que el prompt del paciente pida dar el dato
  completo cuando se pregunta por él.
- El electroencefalograma lo responde el agente de laboratorio, porque el router agrupa ahí los estudios
  («electro»). Funciona, pero conceptualmente sería un estudio de neurología.
