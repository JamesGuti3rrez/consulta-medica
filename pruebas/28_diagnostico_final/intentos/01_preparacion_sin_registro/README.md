# Intento 1: la suite «antes» falló en la preparación, no en lo que comprueba

**Qué pasó.** Primera corrida de la suite HU-006 sobre el código anterior (`local_antes_intento1_pytest.txt`): los 25
casos terminaron en ERROR de preparación, sin llegar a comprobar nada.

**Causa.** La preparación local reemplaza `server.api.ai.get_diagnoses` por el registro sobre el Supabase simulado.
Antes del cambio esa función no existe, y `monkeypatch.setattr` falla si el atributo no existe.

**Cómo se corrigió.** `raising=False`, como hace la preparación de TA-011 con su verificador de identidad: antes del
cambio el reemplazo no se usa y cada caso falla por lo que comprueba. Se repitió la corrida.
