# prompts/

Plantillas de prompt de cada agente, versionadas junto al código.

- Un archivo por rol (y por versión cuando cambie de forma relevante).
- Los prompts **no contienen datos clínicos**: los datos llegan en tiempo de ejecución desde la evidencia autorizada.
- Nunca incluyen diagnóstico, sinónimos, diferenciales ni tratamiento.

Prompts actuales (rama Rodrigo, 9493e8b): `paciente.md`, `medico_asistente.md`, `laboratorio.md`,
`radiologia.md` y `especialista.md`. `agents/base.py` les añade la regla de entrega de evidencia o la
de ausencia de evidencia en cada turno.
