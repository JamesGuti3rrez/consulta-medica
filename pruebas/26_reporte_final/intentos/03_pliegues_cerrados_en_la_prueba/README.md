# Intento 3: la prueba en navegador leía como vacías las secciones plegadas

**Qué pasó.** Primera corrida en verde de la prueba en navegador (`probar_navegador.cjs`, caso EME-101, servidor
local con el código de HU-006): 3 de 22 comprobaciones fallaron, «Diagnósticos diferenciales», «Acciones clave» y
«Datos obtenidos» sin contenido. Las capturas de la hoja muestran esas secciones con su contenido al abrirlas.

**Causa.** Las tres listas están dentro de un pliegue (`<details>`) cerrado, como en el boceto aprobado. La prueba
las leía con `innerText`, que devuelve vacío para lo que no se está mostrando. No es un fallo de la hoja.

**Corrección.** La prueba comprueba el contenido con `textContent`, que no depende de que el pliegue esté abierto,
y además abre los pliegues antes de las fotos. La corrida se repitió.

**Datos de prueba.** La consulta de invitado creada en el Supabase de producción
(`71a1a018-7ee6-4e50-99b0-1d1b06aaff28`) se borró al final de la fase, con las demás consultas de las pruebas en
navegador.
