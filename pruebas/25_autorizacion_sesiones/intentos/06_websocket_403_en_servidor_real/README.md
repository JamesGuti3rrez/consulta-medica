# Intento 6: el caso 40 no admitía el 403 de un servidor real al rechazar un websocket

**Qué pasó.** Primera corrida en vivo («vivo antes», 2026-10-28 05:50 UTC): servidor real con el código de
producción de `main` (`0cebb31`) en `http://127.0.0.1:3100`, sesiones y casos en el Supabase de producción
(`rynkx…`). Resultado: 24 fallan y 16 pasan. Los 23 fallos de autorización son los mismos del modo local; el
caso **TA011-40** falló además, aunque en modo local pasaba.

**Causa.** El caso 40 intenta abrir un websocket en `/api/ai/sessions/<SA>/ws`. Esa ruta no existe, y uvicorn
rechaza el handshake con **403** (es lo que hace un servidor ASGI cuando cierra un websocket antes de aceptarlo).
La prueba solo admitía 400, 401, 404 o 405; con `TestClient` la respuesta era otra y el problema no apareció.
Las comprobaciones de seguridad del caso sí pasaron: el servidor no aceptó el websocket (no hubo 101) y
ninguna respuesta contenía datos de SA. No es un fallo de autorización.

**Corrección.** El handshake de websocket admite también 403; el resto del caso no cambia. La corrida en vivo
se repitió con la prueba corregida.

**Datos de prueba.** La suite creó 2 alumnos temporales y 10 consultas, y los borró al terminar
(`resultados_vivo_antes/limpieza.json`: 0 consultas y 0 eventos quedan, 2 usuarios borrados). La tabla
`intentos` no existe en ese proyecto (HTTP 404).

Archivos conservados sin modificar: la foto de la terminal, la salida de pytest, los JSON de cada caso, la
limpieza y el log del servidor (el log y la foto, solo en el equipo).
