# Revisión de trazado automático

La primera comprobación contra los servicios reales terminó con los cinco puntos aprobados
y confirmó la limpieza de sus dos cuentas y dos sesiones temporales. Sin embargo, LangGraph
heredó el trazado automático del entorno e intentó enviarlo a LangSmith; ese servicio respondió
429 por cuota agotada. El registro original se conserva en esta carpeta.

Se corrigió `StarGraphOrchestrator.invoke` para desactivar el trazado automático del estado
clínico y mantener únicamente la proyección explícita de auditoría saneada. Una prueba
comprueba esa condición incluso con `LANGSMITH_TRACING=true` en el entorno. La ejecución
remota posterior queda en `pruebas/Sprint2/servicios_reales.*`.
