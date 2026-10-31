# Sprint 2 · Primeros cinco PBIs de Rodrigo

Fecha: 30 de octubre de 2026. Códigos actuales: `Backlog_Sprint2_Fases_y_Dependencias_Completado.docx`.
`alcance.json` conserva el encargo y la fuente históricos. La correspondencia actual,
responsables, criterios, fases y SHA-256 están en
[`correspondencia_backlog_sprint2.json`](../../docs/development/correspondencia_backlog_sprint2.json).
Las capturas, registros, nombres de pruebas y carpetas de evidencia conservan sus nombres originales.

| PBI | Resultado | Pruebas específicas | Documento independiente |
| --- | --- | ---: | --- |
| TA-011 | Autorización de sesiones y eventos verificada | 23 | `Entregables/Sprint2/TA-011_Autorizacion_sesiones_eventos.docx` |
| TA-012 | Guardrails, evidencia y auditoría reforzados | 12 | `Entregables/Sprint2/TA-012_Validacion_adversarial_guardrails.docx` |
| TA-014 | Informe y barrera de consistencia previa | 58 | `Entregables/Sprint2/TA-014_Validador_consistencia_casos.docx` |
| HU-005 | Exámenes/especialistas y tablilla progresiva | 10 | `Entregables/Sprint2/HU-005_Examenes_especialistas.docx` |
| EN-005 | Generación sintética controlada y validada | 21 | `Entregables/Sprint2/EN-005_Generacion_examenes_sinteticos.docx` |

**HU-006 y TA-023 excluidas del encargo inicial.** Los informes se renumeraron según el
backlog actualizado. El informe de calificación diagnóstica se identifica ahora como
**TA-021**; la carpeta `pruebas/TA-012` conserva sus registros originales. El TA-012
actual corresponde exclusivamente a validación adversarial y guardrails.
La aceptación del Product Owner y la revisión clínica humana siguen siendo independientes.

## Evidencia y límites

- `regresion.xml` y `regresion.txt`: 688 pruebas aprobadas, 3 pruebas `vivo` deseleccionadas.
- Cada carpeta de PBI contiene `pytest.xml`, `terminal.txt`, resultados JSON, recorrido
  de navegador y capturas de ejecución/resultado. El generador exige XML sin fallos.
- `servicios_reales.json`: cinco puntos comprobados de forma acotada con Supabase real;
  generación de un candidato con Groq real, persistencia y reutilización tras nueva instancia.
- El catálogo local tiene 43 casos; se revisaron 44 documentos remotos sin modificarlos.
- Se verificaron propietario A, usuario B y ausencia de credenciales con Supabase Auth real.
- La matriz remota de HU-005 cubre laboratorio. Radiología y especialista presente/ausente
  se comprueban con casos/fixture locales y proveedores controlados, sin afirmarlo como prueba remota.
- El bloqueo remoto de TA-012 es determinista; las salidas LLM hostiles se fuerzan localmente.
- Se eliminaron y verificaron dos cuentas temporales, dos sesiones y sus eventos.
  No se migró el esquema, no se modificaron casos curados, roles de usuarios existentes ni `.env`.
- La primera ejecución y la corrección del trazado automático se conservan en
  `intentos/01_trazado_automatico/`. La comprobación final no depende de LangSmith.

EN-005 incorpora **hemograma parcial y glucosa explícitamente en ayunas**, solo para adultos
con contrato aplicable. Los valores que no pasan el contrato no se muestran ni se guardan.
Los aceptados indican `synthetic=true` y revisión clínica humana pendiente; no se emplean
como evidencia canónica para conceder puntos. El repositorio entre casos/sesiones y la
validación clínica especializada de TA-016/TA-015 no se dan por terminados aquí.

## Ejecutar desde la terminal de VS Code

```powershell
npm run test:sprint2 -- --junitxml=../pruebas/Sprint2/regresion.xml
```

Una prueba específica, por ejemplo:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/sprint2/test_en013.py -q
cd ..
```

Para las capturas de navegador, una terminal mantiene el servidor de prueba:

```powershell
.\backend\.venv\Scripts\python.exe pruebas/Sprint2/servidor_evidencia.py
```

Y otra ejecuta el recorrido:

```powershell
node pruebas/Sprint2/probar_navegador.mjs
```

Se simulan micrófono, voz, Auth y proveedores del servidor de evidencia para reproducibilidad;
los endpoints, controles, validador y frontend se ejecutan realmente. Ese servidor escucha
solo en `127.0.0.1:3027` y no se importa en producción.

La comprobación remota requiere las claves del `.env` y consume una generación acotada en Groq:

```powershell
.\backend\.venv\Scripts\python.exe pruebas/Sprint2/verificar_servicios_reales.py
```

## Capturas y documentos

```powershell
.\backend\.venv\Scripts\python.exe pruebas/Sprint2/fotografiar_terminal.py
.\backend\.venv\Scripts\python.exe pruebas/Sprint2/documentar.py
```

Las imágenes de terminal son capturas nativas de ventanas propias de PowerShell que muestran
los **registros originales guardados al ejecutar las pruebas**, sin reconstruir resultados.
No se presentan como capturas de la terminal integrada de VS Code. El manifiesto
`capturas_terminal.json` conserva rutas y SHA-256; el generador rechaza registros modificados.
Pillow y python-docx son herramientas documentales, sin agregarse al runtime del simulador.
Los Word y las fotografías están excluidos de Git por las reglas actuales del repositorio.

## Activación en el simulador

Después de cargar el código, reiniciar el servidor con `npm start`.
`SYNTHETIC_EXAM_DATA=true` habilita EN-005; si la variable no está definida, hereda
`SYNTHETIC_CASE_DATA`. El `.env` proporcionado ya activa esa condición, sin haberlo modificado.
El resultado aceptado queda en `sma_sesiones.state.synthetic_exam_results` y la decisión
en `sma_eventos.payload.exam_validation`. No requiere crear columnas nuevas.

Fuentes oficiales de los intervalos educativos (consultadas el 30/10/2026):
[MedlinePlus: CBC](https://medlineplus.gov/ency/article/003642.htm) y
[MedlinePlus: glucosa](https://medlineplus.gov/ency/article/003482.htm).
