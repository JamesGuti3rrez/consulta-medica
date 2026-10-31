# Integración de la rama Rodrigo en James (31 de octubre de 2026)

La rama `Rodrigo` partía de una versión de `main` del 17 de octubre y traía copiados, sin fusionar, los archivos
de TA-011 y del reporte final. Al unirla con `James` se resolvieron 25 conflictos con este criterio:

| Tema | Se conserva | Motivo |
|---|---|---|
| Autorización de sesiones (TA-011) | James | Mismo contenido; la rama de Rodrigo era una copia anterior. Se añade su comprobación de grupo en `authorize_session`. |
| Diagnóstico final (HU-006) | James | Obligatorio, validado, con confirmación y registrado por alumno, caso, sesión e intento. |
| Reporte final (HU-007) | James | Renumerado de HU-006; se añaden los exámenes sintéticos de EN-013 a la evidencia revelada. |
| Calificación automática del diagnóstico (su TA-012, backlog TA-021) | Se retira | Permitía un diagnóstico vacío con 0 puntos, contrario a HU-006. TA-021 corresponde a James y se hará sobre HU-006. |
| Panel Doctor: grupos, asignaciones y seguimiento (su HU-014, backlog HU-011) | Rodrigo | Sin calificación, el panel muestra el diagnóstico sin puntaje y la entrega como finalizada. |
| Diálogo directo (su TA-017) | Rodrigo | El médico ya no repite la pregunta; en la voz solo habla quien responde. |
| Exámenes sintéticos (su EN-013, backlog EN-005) | Rodrigo | Sin cambios. |
| Validador de consistencia de casos (su TA-027, backlog TA-014) | Rodrigo | Sin cambios. |
| Guardrails y exámenes o especialistas (su TA-007 y HU-004) | Rodrigo | Sus pruebas cierran la consulta con el contrato de HU-006. |
| Voz humanizada (TA-019, edge-tts) | James | Sin cambios. |

Migraciones: las 0005 y 0006 de grupos ya están aplicadas en producción; la del diagnóstico final pasa de 0005 a
`0007_diagnosticos_finales.sql`. La base PostgreSQL de prueba de grupos (`pruebas/HU-014/`) carga también la 0007 y
atiende las peticiones de `diagnosticos_finales`, porque el cierre de una actividad de grupo registra el diagnóstico.

Comprobación tras unir: backend 825 pruebas pasan (incluidas las 16 de grupos con PostgreSQL de prueba).
