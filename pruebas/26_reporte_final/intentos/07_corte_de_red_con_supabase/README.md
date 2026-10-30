# Intento 7: corte de red con Supabase durante la preparación en vivo

**Qué pasó.** Primera corrida en vivo «después» de la suite HU006 (servidor con el código de HU-006 en
`http://127.0.0.1:3100`, Supabase de producción): los 17 casos en ERROR de preparación. El cierre de la consulta de
A respondió 503 «No se pudo acceder a las sesiones» y el log del servidor registró
`[sesiones] No se pudo conectar con Supabase: ReadError`.

**Causa.** Un corte de red transitorio entre el equipo y Supabase en esa petición: el servidor respondió 503, que
es lo que debe hacer cuando el almacén no responde. Para descartar que lo causara el cierre nuevo (que además lee
los eventos de la consulta para armar el reporte), se repitió el flujo tres veces seguidas contra el mismo
servidor con consultas de invitado: los tres cierres respondieron 200 con el reporte (unos 4,3 s cada uno) y
`GET /report` respondió 200. Esas 3 consultas se borraron enseguida con la clave secreta.

**Datos de prueba.** La limpieza de la corrida funcionó: 2 consultas y 2 usuarios creados y borrados, 0 eventos
restantes (`resultados_vivo_despues/limpieza.json`).

**Corrección.** Ninguna en el código: la corrida se repitió.
