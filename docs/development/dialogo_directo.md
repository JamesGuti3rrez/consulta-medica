# TA-017 · Separar diálogo estudiante–médico–paciente

Solicitud acordada: el doctor presenta el caso y puede entregar hallazgos o aclarar
solicitudes. Las preguntas del estudiante llegan directamente al paciente o al agente
destinatario, sin otro mensaje ni otra lectura por voz del doctor.

Cambios: retirar el reformulador del grafo activo; conservar la pregunta original en
recuperación y agentes; no añadir `medico_tratante` al historial; devolver
`doctor_question=null`; omitir ese campo al reconstruir conversaciones antiguas.
El contexto del agente excluye los ecos antiguos sin borrar los eventos almacenados.

El routing, los permisos y las restricciones de evidencia continúan aplicándose a cada
turno. La exploración física y las solicitudes genéricas siguen usando el médico
asistente; cada servicio de exámenes conserva su rol.

La documentación y pruebas están en [pruebas/TA-017_Dialogo](../../pruebas/TA-017_Dialogo/README.md).
Este TA-017 corresponde al diálogo según el backlog por fases y dependencias. Los
registros históricos de autorización que usaban TA-017 corresponden ahora a TA-011.
