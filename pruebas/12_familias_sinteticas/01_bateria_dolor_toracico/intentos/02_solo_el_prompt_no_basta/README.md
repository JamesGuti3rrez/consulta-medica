# Intento 2 · Ajustar las instrucciones del paciente no bastó

Segunda corrida (2026-10-11), ya con la comprobación de fidelidad en la batería y con una instrucción
nueva en `backend/server/ai/agents/prompts/paciente.md`: contar completo el dato que responde la
pregunta, aunque la respuesta corta sea «no».

Resultado ([bateria_familia_terminal.png](bateria_familia_terminal.png)): 42 de 42 turnos con el
agente y el dato correctos, 0 fugas, 0 síntomas inventados, pero **1 omisión**, la misma del intento 1:

```
EME-103 · ¿Toma algún medicamento?
respuesta: No, no estoy tomando ningún medicamento.
! omite las cifras ['10', '4'] del dato
```

La batería ahora sí lo detecta. El modelo trabaja con temperatura 0 y ante «¿Está tomando algún
medicamento?» responde lo literal. La instrucción se conserva (es correcta en general), pero la
corrección efectiva va en el dato: se redacta como lo diría el paciente, empezando por que ya no lo toma
y siguiendo con qué era y desde cuándo.
