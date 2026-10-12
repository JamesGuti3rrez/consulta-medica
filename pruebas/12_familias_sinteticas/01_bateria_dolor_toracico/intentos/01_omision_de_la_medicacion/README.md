# Intento 1 · La batería pasó, pero el paciente omitió un dato clave

Primera corrida de la batería (`bateria_familia_v1.py`, 2026-10-11 22:50). El resumen decía que todo
pasaba: 42 de 42 turnos con el agente y el dato correctos, 0 fugas, 0 síntomas inventados y los 3 casos
resueltos ([bateria_familia_terminal.png](bateria_familia_terminal.png)).

Al revisar las respuestas una por una apareció un fallo que la batería no medía. En EME-103 (Víctor
Chávez, disección aórtica), turno 5:

```
¿Toma algún medicamento? -> paciente
médico tratante: ¿Está tomando algún medicamento?
respuesta: No, no estoy tomando ningún medicamento.
```

El dato del caso dice: «Le recetaron amlodipino 10 mg al día, pero dejó de tomarlo hace 4 meses.» El
dato se reveló (su `evidence_id` llegó en la respuesta), pero el paciente contestó solo «no» y omitió el
abandono del tratamiento, que es una pregunta clave del caso (hipertensión mal controlada).

**Por qué no se detectó:** la batería comprobaba qué datos se autorizaban, no si la respuesta los
contaba completos.

**Corrección:**

1. La batería mide la fidelidad: las cifras del dato (por ejemplo «10 mg», «4 meses») deben aparecer en
   la respuesta, en número o en palabras.
2. Las instrucciones del paciente (`backend/server/ai/agents/prompts/paciente.md`) le piden contar todo
   el dato que responde la pregunta, aunque la respuesta corta sea «no».
