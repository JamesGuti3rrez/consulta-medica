# Intento 2: la prueba tomaba `"evaluation": null` como una fuga

**Qué pasó.** Segunda corrida «antes» (`local_antes_intento2_pytest.txt`): 21 fallan y 4 pasan. HU006-24 falló en
«sin la clave evaluation» al leer una consulta abierta.

**Causa.** La consulta abierta responde `"evaluation": null` (`resultados_intento2/logs/HU006-24.json`): la clave
existe pero vacía, igual que en TA-011. La comprobación exigía que la clave no apareciera, y eso no es una fuga.

**Cómo se corrigió.** La comprobación falla solo si `protected`, `evaluation`, `report` o `reference` traen un valor
distinto de `null`. Se repitió la corrida.
