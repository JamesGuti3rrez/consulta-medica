# ADR-003 — Contexto por mínimo privilegio

**Decisión:** cada agente recibe únicamente evidencia pública ya visible y evidencia `on_request`
autorizada en el turno actual por `reveal_policy`.

`protected` nunca entra al flujo conversacional ni siquiera durante `cierre`. El motor de seguridad
puede leerlo para preparar reglas determinísticas, pero el agente/LLM no lo recibe.
