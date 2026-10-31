# TA-017 · Separar diálogo estudiante–médico–paciente

El doctor presenta el caso. Después comunica hallazgos autorizados y aclara solicitudes,
sin repetir ni reformular las preguntas del estudiante para dirigírselas al paciente.
El estudiante conversa directamente con el agente destinatario.

Se eliminó el reformulador del flujo activo. La recuperación y el agente reciben la
pregunta original; el historial nuevo conserva estudiante y agente, sin un tercer
turno `medico_tratante`. `doctor_question` permanece en el contrato como `null`.
Los turnos intermediados antiguos se excluyen del contexto del modelo y de la
reconstrucción visual/por voz, conservando sus registros históricos.

La espera de respuesta es neutral: no se muestra al doctor pensando por cada pregunta.
Sus hallazgos y aclaraciones conservan su burbuja y su voz. Los informes de laboratorio,
radiología y especialista conservan su emisor. Se mantienen permisos, revelación y filtros.

## Verificación

- `regresion.xml`: 704 pruebas aprobadas, tres de servicios vivos deseleccionadas.
- `pytest.xml`: cuatro pruebas específicas aprobadas: diez turnos, pregunta original,
  compatibilidad con historial antiguo y bloqueo de respuesta protegida del paciente.
- `navegador.json`: presentación, diez turnos con dos mensajes y una lectura por voz,
  recuperación de una actividad antigua sin eco y ausencia de errores JavaScript.
- API real y PostgreSQL local PGlite. Identidad y dispositivos de voz controlados;
  el evento antiguo se inserta exclusivamente en el fixture local.
- No se requirieron escrituras de prueba en Supabase ni llamadas a Groq.

El flujo de recuperación comprobado es el existente de actividades de grupo. Este
cambio no implementa por sí solo la historia general de retomar sesiones interrumpidas.

## Repetir

```powershell
npm run test:sprint2
node backend/scripts/python.mjs test-cases tests/integration/test_direct_dialogue.py tests/sprint2/test_ta007.py -k 'direct_dialogue or patient_response_is_guarded' --junitxml=../pruebas/TA-017_Dialogo/pytest.xml
```

Navegador: iniciar los dos servidores en terminales separadas y después ejecutar la prueba:

```powershell
node pruebas/HU-014/sql_server.mjs
.\backend\.venv\Scripts\python.exe pruebas/HU-014/servidor_evidencia.py
node pruebas/TA-017_Dialogo/probar_navegador.mjs
```

Los servidores escuchan únicamente en loopback, puertos 3039 y 3037. La prueba prepara
y limpia las tablas de grupos/sesiones del fixture, nunca la base real.

Informe: `Entregables/Sprint2/TA-017_Dialogo_estudiante_medico_paciente.docx`.
Las capturas de terminal muestran registros originales en ventanas propias de PowerShell.
