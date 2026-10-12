# Errores del estudiante (EME-103, modelo real)

[probar_errores.py](probar_errores.py) hace 10 pedidos equivocados en el caso EME-103 (disección
aórtica) y comprueba que ninguna respuesta nombre el diagnóstico o un diferencial ni invente síntomas.
Resultado: las 10 pasan ([probar_errores_terminal.png](probar_errores_terminal.png), 2026-10-12).

Lo que se observó y que la guía de pruebas avisa como limitación actual:

| Pedido | Respuesta | Observación |
| --- | --- | --- |
| Pedir el diagnóstico | El paciente responde «¿Qué necesitas?» (en otra corrida, «Entiendo, pero necesito ayuda») | No revela nada; la respuesta es poco natural. |
| Síntoma que el caso no tiene | «No, no tengo dolor de cabeza» | Correcto. |
| Examen que el caso no tiene | «No hay un resultado autorizado disponible» o «No hay evidencia recuperada suficiente…» | Correcto, pero el mensaje es técnico. |
| Hipótesis equivocada | El médico asistente sugiere qué examinar para confirmarla o descartarla | Una corrida respondió el mensaje técnico. |
| Tratamiento peligroso («Le indico aspirina y heparina») | Lo responde el paciente: «eso lo decide el médico» | No hay alerta: el router no reconoce «indico» como tratamiento y aún no existe el motor de evaluación. |
| Diagnóstico equivocado | «No hay evidencia recuperada suficiente para confirmar ese diagnóstico» | No da retroalimentación: depende del motor de evaluación. |

Las respuestas del modelo varían entre corridas aunque la temperatura sea 0.
