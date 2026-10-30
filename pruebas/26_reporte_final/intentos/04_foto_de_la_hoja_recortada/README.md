# Intento 4: la foto de la hoja completa salió cortada

**Qué pasó.** Segunda corrida en verde de la prueba en navegador: las 20 comprobaciones pasaron, pero
`navegador_02_hoja_completa.png` mide 704 × 940 px y termina en «Lo que faltó preguntar»: no muestra el resto de
la hoja.

**Causa.** Para la foto, la prueba quitaba la altura máxima del papel (`.clipboard-paper`), pero la tarjeta que lo
contiene (`.clipboard.report-card`) también tiene una altura máxima ligada a la ventana.

**Corrección.** La prueba también quita la altura máxima de la tarjeta antes de la foto. La corrida se repitió.

**Datos de prueba.** La consulta de invitado (`57d38092-b4e4-4098-94c1-4629c239b626`) se borró del Supabase de
producción al final de la fase.
