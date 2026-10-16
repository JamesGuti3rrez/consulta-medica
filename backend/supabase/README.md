# backend/supabase/

Base de datos transaccional del sistema (Supabase / PostgreSQL).

- `migrations/`: migraciones SQL numeradas y en orden (`NNNN_descripcion.sql`). `0001_perfiles_e_intentos.sql` se conserva sin cambios; `0002_sesiones_sma.sql` crea las sesiones y los eventos del simulador (`SESSION_STORE=supabase`).
- Uso actual: cuentas de usuario (`perfiles`), sesiones del simulador (`sma_sesiones`, `sma_eventos`) e intentos.
  `intentos` guarda cada consulta que termina un alumno con la sesión iniciada; solo el servidor la escribe
  (`server/persistence/attempts.py`) y el navegador solo lee los del propio alumno («Mis simulaciones»).
  Evidencia: `pruebas/16_historial_simulaciones/`.
- Pendiente de decisión: si el índice vectorial del RAG vivirá aquí (pgvector, sugerido por el docente) o en otro almacén. Si se adopta, entrará como una migración nueva, no editando la 0001.
- Datos personales de estudiantes: requieren aviso de privacidad y consentimiento (Ley 29733). El aviso está en
  `frontend/public/privacidad.html` y se acepta al crear la cuenta (`privacidad_version` y
  `privacidad_aceptada_en` en los datos del usuario). Evidencia: `pruebas/19_aviso_privacidad/`.
- Los casos se incorporan mediante la migracion 0003; los datos de prueba no se cargan en produccion.

## Casos en el nuevo proyecto de Supabase

La migracion `migrations/0003_casos_curados.sql` prepara el almacenamiento de casos.
Es independiente de las migraciones 0001 y 0002: se puede ejecutar sola en el
SQL Editor del nuevo proyecto, una vez y completa.

- `casos_curados`: `case_id` y `documento` JSONB con el caso canonico completo.
  Titulo, especialidad y version se calculan a partir del documento.
- `caso_datos_adicionales`: contenido sintetico JSONB asociado al caso, con
  pregunta de origen, tema normalizado, modelo y estado de revision. Una clave
  por caso evita que dos solicitudes creen el mismo tema simultaneamente.

Ambas tablas tienen RLS activado y acceso reservado a `service_role`.
El frontend debe seguir recibiendo unicamente la informacion autorizada por
el backend; no puede consultar directamente el documento que contiene `protected`.

### Aplicacion y comprobacion

1. Abrir el SQL Editor del **nuevo** proyecto de Supabase.
2. Pegar el archivo 0003 completo y ejecutarlo.
3. Comprobar en Table Editor que existen ambas tablas.

Las claves `SUPABASE_URL` y `SUPABASE_SECRET_KEY` permiten acceder a las tablas
por la API de datos; no permiten ejecutar una migracion SQL arbitraria. Para
automatizar la creacion hace falta una conexion PostgreSQL o un token de
administracion de Supabase con los permisos correspondientes.

### Cargar los casos y activar Supabase

Desde la raiz del proyecto, en la terminal integrada de VS Code:

```powershell
npm install
npm run setup -- --extras dev
npm run test:cases
npm run import:cases -- --dry-run
npm run import:cases
npm start
```

`import:cases` valida todos los JSON curados con el esquema y las reglas cruzadas,
inserta los casos ausentes en un lote y lee de nuevo los documentos para verificar
que coinciden. Repetirlo no sobrescribe documentos ni toca los datos adicionales.
Si ya existe un caso distinto con el mismo ID, se detiene y no activa la fuente remota.
La importacion usa exclusivamente el proyecto indicado por `SUPABASE_URL` en `.env`.

Solo tras verificar la carga guarda `CASE_STORE=supabase` en `.env`. Hay que
reiniciar el servidor; no es necesario activar manualmente el entorno Python,
porque los comandos npm usan `backend/.venv` directamente. `--dry-run` no conecta,
no escribe y no activa nada. Para trabajar expresamente con archivos en pruebas,
se puede configurar `CASE_STORE=local`.

`GET /api/status` debe informar `caseStore: "supabase"` y el numero de casos
disponibles. `GET /api/caso` sigue entregando solo la vista publica permitida.
El SMA usa el mismo repositorio para conversar, evaluar y verificar seguridad.
Una caida de Supabase devuelve HTTP 503: no usa archivos como respaldo silencioso.

En modo Supabase la evidencia autorizada se obtiene del documento remoto actual
(`retrieval_mode: "supabase-case-evidence"`). No se usa el indice local ni un
servicio RAG externo que pudiera contener una version anterior del caso. Esto
conecta los casos; no implementa aun busqueda vectorial en Supabase.

Las sesiones se configuran por separado con `SESSION_STORE`; este cambio no
modifica ese valor. Guardarlas en Supabase requiere las tablas de la migracion 0002.
Los perfiles e intentos del nuevo proyecto necesitan la migracion 0001.

### Completar datos ausentes de la historia

Con `CASE_STORE=supabase`, credenciales de Groq y `SYNTHETIC_CASE_DATA=true`, el
Paciente puede completar medicacion habitual, cronologia de antecedentes conocidos
y habitos (agua, alimentacion, actividad fisica, tabaco, alcohol, sueno y ocupacion).
Tambien puede completar la reaccion emocional cotidiana ante un antecedente ya
conocido (`reaccion_diagnostico`), sin inventar trastornos o enfermedades nuevas.
`impacto_vida_diaria` permite completar la repercusion cotidiana de un sintoma o
hallazgo ya visible. Por ejemplo, preguntar por las actividades diarias despues de
mostrar una papula no debe perder la referencia a esa exploracion. El contexto del
Paciente incluye solo los hallazgos previamente revelados en su sesion, nunca
exploraciones pendientes ni `protected`. Si el caso ya describe su autonomia, se
respeta ese dato. Los complementos no incorporan datos recuperados que no
respondan a los temas preguntados.
La importacion inicial no modifica `caso_datos_adicionales`; las preguntas al paciente
generan los datos durante la consulta, si son pertinentes y falta ese campo.

El selector, generador y revisor usan temperatura 0. El codigo limita los campos,
evita reemplazar datos canonicos, comprueba cronologia, impide dosis nuevas y
filtra sintomas nuevos y terminos protegidos antes de guardar. El modelo revisa
ademas pertinencia y coherencia con la informacion autorizada. No recibe el
diagnostico protegido ni el bloque `on_request` completo.

Los datos se guardan ANTES de responder. Otras sesiones reutilizan la misma clave
por caso aunque la pregunta sea una parafrasis. Una insercion concurrente conserva
el primer registro y ambas solicitudes leen el dato persistido. No se altera el
JSON curado, el estado clinico ni el puntaje de la evaluacion por agregar estos datos.

Cada fila conserva pregunta de origen, modelo, huella del caso, sesion de origen y
marca `contenido.origen = "sintetico"`. `estado_revision = "pendiente"` significa
que supero una revision automatica, no que un docente lo aprobo. Esos datos ya
pueden reutilizarse. Los rechazados no se usan; si cambia la version del caso o un
dato queda rechazado, se detiene su reutilizacion para que se revise, sin borrarlo
ni regenerarlo silenciosamente.

Para cambiar un estado, edita `estado_revision` en el Table Editor o ejecuta un
UPDATE limitado por `case_id` y `clave` (o por el `id` de la fila). Los valores son:
`pendiente` (revision automatica, reutilizable), `aprobado` (revisado por docente,
reutilizable) y `rechazado` (bloqueado, no se regenera ni sustituye automaticamente).
Ejemplo para aprobar solo un dato:

```sql
update public.caso_datos_adicionales
set estado_revision = 'aprobado'
where case_id = 'MED-008'
  and clave = 'medicacion_habitual'
returning case_id, clave, estado_revision;
```

`GET /api/ai/status` informa `synthetic_case_data: true` cuando esta activo. Los
eventos `turn` y la respuesta HTTP contienen `data_source` (`curado`, `sintetico`,
`mixto`, `conversacional` o `fuera_de_alcance`) y los identificadores `synthetic_generated_ids` y
`synthetic_reused_ids`. El texto sintetico persistido se conserva en las respuestas
para mantener nombres y cifras consistentes. No es un indice vectorial nuevo.

El compositor pide JSON al proveedor y usa instrucciones separadas para seleccionar,
generar y validar. Si el borrador incumple el contrato, intenta corregirlo una vez
antes de descartarlo. Los eventos guardan `synthetic_rejection_reason` con la fase
y el motivo del rechazo para distinguir un fallo de formato de un dato incoherente.
Una respuesta vacia del proveedor se trata como fallo reintentable.

Las expresiones habituales de voz como "que podrias tomar para el control" se
consideran preguntas por la medicacion habitual de un antecedente conocido. Los
comentarios breves de cortesia, bromas y frases sociales poco claras tienen una
respuesta conversacional; quedan en el historial de la sesion pero no crean datos
clinicos adicionales ni se repiten como pregunta del medico al paciente. El rechazo
de preguntas ajenas conserva la voz del paciente en lugar de describir reglas internas.

Para comprobar el flujo, reinicia el servidor e inicia MED-008. Pregunta por la
medicacion para la hipertension y el ano del diagnostico; despues inicia otra
sesion con ese caso y pregunta lo mismo con otras palabras. Comprueba:

```sql
select case_id, clave, contenido ->> 'respuesta' as respuesta,
       estado_revision, modelo, created_at
from public.caso_datos_adicionales
where case_id = 'MED-008'
order by clave;

select session_id, payload ->> 'data_source' as origen,
       payload -> 'synthetic_generated_ids' as generados,
       payload -> 'synthetic_reused_ids' as reutilizados
from public.sma_eventos
where payload ->> 'type' = 'turn'
order by id desc
limit 10;
```

Una pregunta como `Cuanto es 2+2` se rechaza sin llamar al modelo ni crear datos
adicionales. Se conserva el evento de la consulta para poder comprobar el rechazo.
No se sintetizan nuevos diagnosticos, complicaciones, pruebas, signos vitales ni
prescripciones. Si un candidato no supera las comprobaciones, no se guarda.

Las solicitudes de exploracion fisica (incluido "examenes fisicos" en plural)
van al Medico Asistente y recuperan los hallazgos del caso canonico. Laboratorio y
Radiologia conservan sus resultados registrados. Pedir solo "examenes medicos"
sin indicar el tipo produce una aclaracion del Medico Asistente, no una respuesta
del Paciente ni una consulta a los datos sinteticos. Un resultado ausente se informa
como no disponible; este flujo no fabrica valores de pruebas que puedan cambiar
el diagnostico o la evaluacion.
