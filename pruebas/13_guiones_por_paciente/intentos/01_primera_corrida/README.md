# Intento 1 · Primera corrida de los 13 guiones: 102 de 114

> Numeración: este README usa los códigos de casos anteriores a la fase 23. Equivalencias actuales: MED-008 → MED-007 (Patricia Vargas), MED-009 → MED-008 (Alberto Núñez) y PED-007 → PED-009 (Mateo Quispe).

Salida completa en [salida_terminal.txt](salida_terminal.txt) y detalle en
[resultados_guiones.json](resultados_guiones.json) (2026-10-12). Los 12 pedidos con problema:

| Problema | Pedidos | Causa | Corrección |
| --- | --- | --- | --- |
| «Reveló» datos al pedir el diagnóstico o proponer un tratamiento | 8 (EME-101 a EME-103, EME-001, MED-008) | No era un fallo del sistema: el médico asistente devuelve todo lo revelado hasta ese turno y la batería lo contaba como nuevo. | La batería cuenta solo los datos nuevos. |
| «¿Tiene alguna enfermedad?» no reveló los antecedentes | 1 (EME-002) | Se reconocía «enfermedades» en plural, no «enfermedad». | Alias en singular (`policy.py`, commit `415d229`). |
| Omitió cifras del dato | 2 (EME-103: dosis de 10 mg; CIR-006: años de cada enfermedad) | El modelo resume a veces. | Si la respuesta omite cifras del dato, el agente pide una corrección una vez (commit `ae0891c`). |
| «¿Tiene fiebre?» reveló los síntomas acompañantes | 1 (GOB-004) | Por diseño: la fiebre es parte del tema «otros síntomas». | No es un error: el ejemplo del guion se cambió por «¿Ha tenido tos?». |
