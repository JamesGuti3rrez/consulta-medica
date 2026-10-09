# Observaciones sobre caso.schema.json (1.0.0)

Detectadas durante el análisis. **No se corrigió nada**: el esquema se conserva idéntico. Cada punto requiere decisión del equipo.

1. **Falta un campo de dificultad.** La descripción del proyecto indica que el caso se elige por especialidad **y dificultad** (fácil, intermedio, difícil), pero el esquema no tiene ese campo y `additionalProperties: false` impide agregarlo sin cambiar la versión.
2. **Especialidades.** El enum tiene cinco valores (medicina interna, pediatría, ginecología y obstetricia, cirugía general, emergencias). Documentos anteriores mencionan cardiología y neumología. Además, el prefijo de `case_id` no está ligado a `specialty` (un caso con prefijo CARD puede ser de emergencias); conviene definir si el prefijo debe significar algo.
3. **Reglas cruzadas fuera del esquema.** La descripción del esquema remite a `validar_caso.py`, que no está en el repositorio. **Resuelto (2026-10-09):** las reglas están en `backend/server/cases/rules.py` (R01–R13 y W01; ver `README.md`). La descripción del esquema sigue nombrando `validar_caso.py`; corregirla cambia el archivo del esquema y requiere una decisión.
4. **Grupo sanguíneo.** La descripción del proyecto lo incluye en la tablilla; el esquema no tiene un campo para él (podría ir como `dato` público si se decide).
5. **reveal_policy.** Restringe el modo para paciente, laboratorio y radiología, pero no para `medico_asistente` ni `especialista`. Confirmar si es intencional.
6. **Estado visual del avatar.** El esquema no modela complicaciones visibles ni cambios de signos vitales tras un error. Es coherente que lo decida el motor de reglas, pero hay que definir de dónde sale ese comportamiento por caso.
