# Intento 5: un dato revelado repetía su etiqueta en la hoja

**Qué pasó.** Tercera corrida en verde de la prueba en navegador: 20 de 20 comprobaciones pasaron y la foto de la
hoja completa salió entera (704 × 2594 px). Al revisarla, la sección «Datos que obtuviste en la consulta»
mostraba «Troponina I ultrasensible: Troponina I ultrasensible: 2850 ng/L…».

**Causa.** La hoja escribía cada dato como «etiqueta: texto», y en algunos casos el texto del dato ya empieza con
su etiqueta. Ninguna comprobación lo detectaba.

**Corrección.** Se agregó la comprobación «ningún dato revelado repite su etiqueta» a `probar_navegador.cjs` y la
hoja muestra solo el texto cuando ya empieza con la etiqueta. La corrida se repitió.

**Datos de prueba.** La consulta de invitado de esta corrida se borró del Supabase de producción al final de la
fase.
