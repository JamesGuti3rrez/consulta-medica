# Intento 4: los scripts del recorrido se quedaron esperando a LangSmith

**Qué pasó.** Para comprobar que los scripts del recorrido completo (fases 14 y 18) siguen funcionando con la
credencial de la consulta, se ejecutaron directamente desde `backend/`. Ninguno terminó: después de más de
20 minutos se detuvieron a mano.

**Causa.** El `.env` tiene `LANGSMITH_TRACING=true`. LangSmith respondía `429 Too Many Requests` («Monthly
unique traces usage limit exceeded») y cada turno quedaba esperando los reintentos. El recorrido oficial
(`pruebas/_herramientas/recorrido_completo.py`) pone `LANGSMITH_TRACING=false` antes de correr estos scripts;
al ejecutarlos sueltos no se hizo lo mismo. No es un problema de TA-017: ningún error de la salida es de
autorización.

**Corrección.** Se repitieron con `$env:LANGSMITH_TRACING='false'`, igual que el recorrido oficial.

Archivos conservados sin modificar: la foto de la terminal y la salida completa.
