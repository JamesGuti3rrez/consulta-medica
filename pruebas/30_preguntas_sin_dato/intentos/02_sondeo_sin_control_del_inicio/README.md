# Intento 2: la conversación real no detectaba el inicio de la molestia mal respondido

Con MED-008, a «¿Desde cuándo tiene la molestia?» el paciente respondió «Me diagnosticaron en 2003, cuando tenía
aproximadamente 45 años» (año de su hipertensión) y el script marcó PASA porque solo buscaba «No entendí bien» y
«describe los hallazgos». Se añadió el control (pregunta por el inicio de la molestia respondida con un diagnóstico)
y se corrigió la causa en `synthetic_scope.py`; la corrida válida es `ejecucion/07_conversacion_real_med008`.
