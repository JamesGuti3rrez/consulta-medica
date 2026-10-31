# Intento 1: la prueba del rechazo no provocaba un rechazo

`test_rechazo_del_generador_deja_responder_al_agente_paciente` usaba la selección `{"alcance": "caso", "claves":
["sintoma_inventado"]}`. Una clave fuera de las permitidas se descarta y la pregunta se trata como curada, sin rechazo,
así que la prueba fallaba por otro motivo. Se cambió a una selección mal formada (`"claves": "sintoma_inventado"`) y la
corrida «antes» se repitió con el código anterior (`ejecucion/01_antes`).
