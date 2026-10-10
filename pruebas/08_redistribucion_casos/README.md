# Fase 8 · Redistribución de los 10 casos entre public y on_request (2026-10-09)

## Objetivo

Que cada caso funcione como una consulta: el estudiante ve al inicio solo el motivo de consulta, los
datos de llegada y los signos vitales (arquitectura §6.1, SP-002), y tiene que preguntar, examinar y
pedir exámenes para obtener el resto. Hasta ahora toda la historia estaba en `public` y `on_request`
solo tenía un marcador vacío, así que el sistema multiagente no tenía nada que revelar.

## Qué cambió

- **Reparto en los datos de curación.** `data/cases/reviews/medqa_lote_curacion.json` tiene una sección
  `distribution`: para cada dato, la zona, el dueño (`owner`), los temas (`requires`) y las preguntas
  clave que lo citan. El generador (`medqa_case_builder.py`) construye el caso a partir de ella; el
  modo sale del dueño (paciente `al_preguntar`, médico asistente `al_examinar`, laboratorio y
  radiología `al_solicitar_examen`).
- **Temas de `requires`.** Los del contrato de indexado de Julio: `inicio_y_evolucion`,
  `caracteristicas_sintoma`, `sintomas_asociados`, `antecedentes_personales`,
  `antecedentes_familiares`, `medicacion`, `alergias`, `habitos`, `antecedentes_gineco_obstetricos`
  (paciente) y `signos_vitales`, `exploracion_fisica` (médico asistente). Los exámenes usan su
  nombre (`ph_vaginal`, `coagulacion`, `radiografia`, `funcion_tiroidea`, `imagen_osea`).
- **Traducción completa** (decisión 0001 §6). Cada dato traducido del enunciado en inglés. Se
  recuperaron datos que la traducción anterior omitía, por ejemplo: el ibuprofeno, el ardor y el
  agotamiento (MED-008), los anticonceptivos, los antecedentes y los signos vitales normales
  (GOB-004), el cambio en el juego y el desarrollo (PED-007), las compras independientes (CIR-006).
  Solo se omite la pregunta de opción múltiple y, en MED-008, la frase en la que el médico decide
  iniciar el antimicrobiano, porque esa decisión le toca al estudiante.
- **Preguntas clave.** `kq1` conserva el enunciado original y su traducción; `kq2` en adelante citan
  los datos de `on_request` (de 2 a 5 por caso).
- **MED-008.** La alergia a tetraciclinas pasa a `on_request` (`allergies_recorded: false`): el
  estudiante debe preguntarla y no hacerlo se evalúa como negligencia. Se registra la
  contraindicación de las tetraciclinas.
- **Regla R14** (`backend/server/cases/rules.py`): cada dato bajo solicitud usa el modo de su dueño, y
  el paciente y el médico asistente solo usan los temas acordados. Habría detectado el error de la
  exploración física con `al_preguntar`.

| | Antes | Después |
| --- | --- | --- |
| Datos visibles al inicio | 20 | 22 |
| Datos a petición | 10 marcadores vacíos | 34 |
| Preguntas clave | 10 | 38 |
| Casos con aviso W01 (examen en `public`) | 4 | 0 |

## Evidencia

- [01_curation_terminal.png](01_curation_terminal.png): regeneración de los 10 casos con `curation`;
  todos pasan las Quality Gates (R01–R14).
- [02_reparto_terminal.png](02_reparto_terminal.png): reparto de cada caso, generado con
  [mostrar_reparto.py](mostrar_reparto.py).
- [03_verificacion_y_pytest_terminal.png](03_verificacion_y_pytest_terminal.png):
  `verificar_casos.py` (todas las comprobaciones pasan, 0 avisos) y `pytest` (50 pruebas).

## Limitaciones

- La fuente no siempre trae datos para cada rol: CIR-005 no describe exploración física y GOB-003 solo
  describe la evolución del parto. No se inventaron datos para completarlos (regla R13).
- En EME-001, EME-002 y CIR-006 el paciente no puede contestar (alteración de la conciencia o
  confusión) y en PED-007 y PED-010 es un menor: el rol `paciente` representa al acompañante o a la
  historia clínica. Está anotado en `notes` de cada caso.
- `discard_evidence_ids` de los diferenciales sigue vacío: vincular cada diferencial con los datos
  que lo descartan es una decisión clínica pendiente.
- La revisión por una persona con formación médica sigue pendiente.
- Los casos rechazados (`data/cases/rejected/`) conservan el formato anterior y ahora incumplen también
  R14; no se sirven.
