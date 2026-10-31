# Sprint 2 · Integración de los primeros cinco puntos de Rodrigo

Se implementaron/verificaron TA-017, TA-007, TA-027, HU-004 y EN-013 en el orden del
backlog unificado v5.5. Las exclusiones solicitadas son HU-005 y TA-019.

La evidencia reproducible, resultados y ubicación de cada Word están en
[`pruebas/Sprint2/README.md`](../../pruebas/Sprint2/README.md).

El flujo conserva la arquitectura existente:

1. `authorize_session` comprueba propietario o capacidad antes de acceder al estado.
2. Los repositorios aplican `ensure_presentable` antes de entregar casos.
3. El router y la política de revelación determinan rol e identificadores autorizados.
4. Se entregan resultados canónicos; la tablilla añade cada evidencia una sola vez.
5. Si falta un examen soportado y EN-013 está habilitado, se propone un candidato JSON,
   se valida, se etiqueta como sintético y se guarda únicamente en la sesión activa.
6. Solo se muestran salidas y preguntas reformuladas que superan el filtro. Las trazas
   contienen metadatos permitidos; el trazado automático del estado de LangGraph está desactivado.

`POST /api/docente/consistencia` y el detalle docente muestran informes versionados de
consistencia. Profesor y administrativo pueden revisarlos; alumno e invitado no acceden.
Los errores y discrepancias pendientes bloquean presentación y publicación; los avisos
informativos quedan registrados. Apto automático no significa certificación clínica humana.

La generación inicial soporta hemograma parcial y glucosa en ayunas en adultos con
contrato aplicable. Un rechazo no genera evidencia ni snapshot. La revisión humana sigue
pendiente incluso para un candidato que pasó el contrato automático. TA-026 y TA-028
conservan su alcance propio para ampliaciones clínicas y reutilización entre casos/sesiones.
