# Fase 2 · Intento 1 (rechazado) — 2026-10-08

Primera selección automática de 10 casos, conservada tal como se generó.

## Qué se hizo

`python -m case_preparation transform --dataset medqa --count 10` eligió 2 candidatos por especialidad
con reglas heurísticas y generó MED-001, MED-002, PED-003, PED-004, GOB-005, GOB-006, CIR-007, CIR-008,
EME-009 y EME-010. La ejecución terminó con código 0 y los JSON pasaban el esquema.

## Por qué se rechazó

En la revisión clínica de los 10 casos:

- seis tenían una curación heurística defectuosa (edad, sexo o especialidad inferidos de palabras sueltas, o respuesta incoherente con el cuadro);
- cuatro eran resúmenes de estudios clínicos, no casos de pacientes.

Pasar el esquema no basta: un caso puede ser válido en formato y aun así ser incorrecto clínicamente.
Los 10 casos y el motivo de cada rechazo se conservan en `data/cases/rejected/` y `data/cases/reviews/`.

## Cómo se corrigió (intento 2, vigente)

Segunda pasada: 10 preguntas fuente elegidas una por una, con revisión asistida por IA, adaptación
al español y verificación contra la fuente (`curation`). Ver [../../README.md](../../README.md).

## Evidencias

- `01_codigo_transform_medqa.png`: código de la selección automática.
- `02_ejecucion_transform_medqa.png` / `.txt`: ejecución y los 10 IDs seleccionados.
- `03_seleccion_10.png`: índice de la selección.
