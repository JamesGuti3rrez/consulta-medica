# Fase 10 · Mejoras de los casos (2026-10-10)

> Numeración: este README usa los códigos de casos anteriores a la fase 23. Equivalencias actuales: MED-008 → MED-007 (Patricia Vargas), MED-009 → MED-008 (Alberto Núñez) y PED-007 → PED-009 (Mateo Quispe).

## 1. Nombres de los pacientes

En lugar de «Paciente N», cada paciente tiene un nombre y apellido ficticios acordes a su sexo (y a
su edad en los casos pediátricos). Se guardan en el reparto de cada caso (`distribution.alias` en
`data/cases/reviews/medqa_lote_curacion.json`); el generador los usa y, si faltan, vuelve a
«Paciente N». Commit `e5acd71`.

| Caso | Nombre | Edad | Sexo |
| --- | --- | --- | --- |
| EME-001 | Jorge Salazar | 33 | masculino |
| EME-002 | Ricardo Medina | 57 | masculino |
| GOB-003 | Lucía Paredes | 24 | femenino |
| GOB-004 | Andrea Castillo | 24 | femenino |
| CIR-005 | Martín Rojas | 28 | masculino |
| CIR-006 | Rosa Villanueva | 68 | femenino |
| PED-007 | Mateo Quispe | 7 | masculino |
| MED-008 | Patricia Vargas | 48 | femenino |
| MED-009 | Alberto Núñez | 68 | masculino |
| PED-010 | Valeria Torres | 6 | femenino |

Evidencia: [01_nombres/nombres_terminal.png](01_nombres/nombres_terminal.png)
([mostrar_nombres.py](01_nombres/mostrar_nombres.py)).

## 2. GOB-003 y PED-010 con más datos a petición

Eran los casos con menos datos para revelar. Sin añadir nada que la fuente no diga, se repartió mejor
lo que el enunciado describe (commit `18a3244`):

- **GOB-003:** la evolución del parto deja la ficha visible y se reparte en tres datos a petición:
  el parto y la reposición de líquidos y sangre (paciente, `antecedentes_gineco_obstetricos`), los
  signos vitales tras el parto (médico asistente, `signos_vitales`) y la exploración física. De 1 a 3
  datos a petición y de 2 a 4 preguntas clave.
- **PED-010:** la exploración se separa en mamas y piel, y el estudio óseo en imagen (displasia
  fibrosa) y edad ósea. De 3 a 5 datos a petición y de 4 a 6 preguntas clave.

Evidencia: [02_reparto_gob003_ped010/reparto_terminal.png](02_reparto_gob003_ped010/reparto_terminal.png).

## 3. Datos que descartan cada diagnóstico diferencial

`discard_evidence_ids` estaba vacío en todos los casos. Ahora 29 de los 39 diferenciales citan los
datos del caso que los descartan o los hacen menos probables (por ejemplo, en EME-001 el tono muscular
mínimo frente al síndrome neuroléptico maligno, que cursa con rigidez; en GOB-004 el pH vaginal de 5,8
frente a la candidiasis). Los 10 restantes no tienen un dato claro en el caso y quedan sin vincular en
lugar de forzarlos (por ejemplo, hemofilia A frente a B solo se distinguen midiendo los factores).

- El reparto guarda la relación en `distribution.discard` (diferencial → datos).
- El generador falla si se cita un diferencial que el caso no tiene.
- La regla R03 comprueba ahora también que los datos citados por los diferenciales existan.

Commit `1226fc7`. Evidencia: [03_descartes/descartes_terminal.png](03_descartes/descartes_terminal.png)
([mostrar_descartes.py](03_descartes/mostrar_descartes.py)).

## 4. Síntomas inventados por los agentes (rama de integración)

En una prueba, el paciente añadió «mareado», que el caso no tiene. Se añadió una comprobación
automática en los agentes (commits `3482548` y `031b97f`):

- `backend/server/ai/agents/invencion.py`: busca síntomas comunes (mareo, tos, dolor de pecho, náuseas,
  fiebre…) en cada respuesta y comprueba si están en el contexto autorizado que recibió el agente. No
  cuentan los negados («no tengo tos») ni la fiebre si el caso tiene una temperatura de 38 °C o más.
- Si encuentra uno, el agente pide una corrección al LLM; si insiste, se quitan solo las frases con el
  síntoma inventado (y si no queda nada, el paciente responde «No»).
- El agente recibe además el nombre, la edad y el sexo del paciente (ya visibles en la ficha): dice
  cómo se llama y habla en su género (antes, Rosa Villanueva decía «confundido»). Ante preguntas
  abiertas («¿cómo se siente?») cuenta su motivo de consulta en lugar de responder «No».
- [bateria_groq.py](04_datos_inventados/bateria_groq.py) hace 6 preguntas en los 10 casos con el LLM
  real (nombre, cómo se siente y cuatro síntomas que casi ningún caso tiene) y revisa cada respuesta
  contra todo lo que el caso describe. Resultado: 0 de 60 respuestas con síntomas inventados
  ([bateria_groq_terminal.png](04_datos_inventados/bateria_groq_terminal.png)).
- Pendiente: en EME-001 (Glasgow 10) el paciente responde «No» a «¿Cómo se siente?»; en los casos
  en que el paciente no puede contestar debería hablar un acompañante.

## Pendiente

- La revisión de los casos por una persona con formación médica (los vínculos de la sección 3 son
  criterio clínico y deben revisarse).
