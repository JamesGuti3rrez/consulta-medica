# Panel docente

El acceso está en `/docente.html`. Tras iniciar sesión con un rol docente se abre el panel;
el menú de perfil también ofrece «Panel docente». El registro público continúa creando alumnos.

## Activación

1. Aplicar [0004_panel_docente.sql](../../backend/supabase/migrations/0004_panel_docente.sql)
   en el SQL Editor del proyecto configurado en `.env`. Requiere `casos_curados`,
   `caso_datos_adicionales` y la tabla `rag_evidencias` de la integración pgvector.
2. Instalar dependencias y reiniciar desde la raíz en la terminal integrada de VS Code:

   ```powershell
   npm run setup -- --extras dev
   npm start
   ```

3. Asignar roles a cuentas **ya registradas** mediante el comando del servidor:

   ```powershell
   npm run role:user -- --email docente@universidad.edu.pe --rol profesor
   ```

   Admite `profesor`, `administrativo` y `alumno` (para revocar). `--dry-run` comprueba
   la cuenta sin cambiarla. Conserva los demás metadatos. Cerrar sesión e iniciar de nuevo.

No se necesitan claves nuevas. El backend usa las credenciales existentes de Supabase;
la clave secreta nunca se envía al navegador. Los permisos proceden de `app_metadata.rol`
y se comprueban consultando Supabase Auth en cada petición. `user_metadata` es editable
por el usuario y no concede privilegios, como indica la
[documentación de usuarios de Supabase](https://supabase.com/docs/guides/auth/users).
La migración también comprueba el rol actual en `auth.users` antes de escribir.

## Importación

El flujo es **seleccionar → leer y validar → revisar → publicar**.
No extrae ni inventa diagnósticos con un modelo de lenguaje: importa los datos estructurados
que aporta el docente. El docente confirma su revisión clínica al publicar.

- **JSON UTF-8:** un caso canónico, una lista de casos o `{"casos": [...]}`.
  El formato es [caso.schema.json](../../schemas/caso.schema.json).
- **Excel .xlsx:** descargar la plantilla en el panel. Las hojas se vinculan por `case_id`:
  `Casos`, `Evidencias`, `Diferenciales`, `Evaluacion` y `Examenes`.
  Una hoja adicional `Instrucciones` explica los campos y valores permitidos.
  Las columnas no se renombran. Las listas se separan por `|`.
- No se admiten PDF, Word, imágenes, `.xls`, macros ni fórmulas. Convertirlos al formato
  estructurado conserva la correspondencia entre hallazgos, preguntas y evaluación.
- Límite de 4 MB, 100 casos por archivo y 5000 filas por hoja. Se limita también el
  tamaño descomprimido del Excel. Se usa openpyxl junto a defusedxml
  ([seguridad del lector](https://openpyxl.readthedocs.io/en/stable/#security)).

Se comprueban esquema, edades y especialidades, identificadores, referencias a evidencias,
reglas de revelación, familias sintéticas y fugas del diagnóstico. La validación preliminar
no escribe. La publicación vuelve a validar con el catálogo remoto actual.

El ID debe tener prefijo de especialidad y tres cifras; la plantilla propone uno libre
desde 101. Un ID existente con contenido clínico diferente impide el lote completo.
Un caso idéntico se conserva; volver a publicarlo sincroniza su evidencia.
La procedencia nueva registra el ID del docente y la fecha real.

Excel genera una presentación inicial neutra y pone los hallazgos en `on_request`.
Para atributos avanzados del esquema (por ejemplo, contraindicaciones farmacológicas,
códigos clínicos o archivos adjuntos) usar JSON canónico.
La plantilla XLSX usa un caso sin contraindicaciones, sin perderlas al convertirlo.

## Persistencia y RAG

`importar_casos_docente` escribe `casos_curados`, reemplaza únicamente las evidencias
de los casos del lote en `rag_evidencias` y registra `importaciones_casos`, todo en
una transacción. Un fallo revierte la operación completa. Los datos adicionales
no se modifican. El bloqueo sobre casos evita comprobar un ID mientras otra importación
lo cambia; una colisión con otro contenido no sobrescribe datos.

Los embeddings se calculan con el proveedor actual de `server.ai.embeddings`, igual que
en la integración existente. Solo se indexan documentos construidos desde `public`
y `on_request`; `protected` se usa para validar fugas y no se indexa.

En el detalle de cada caso se muestran:

- Ficha, diagnóstico de referencia e historia completa, solo para docentes.
- Filas reales de `rag_evidencias`: ID, texto, agente, categoría, requisitos, modelo y fecha.
- Evidencias faltantes o cuyo `source_hash` no coincide con el caso actual.
- Datos adicionales con pregunta de origen, respuesta, modelo y estado de revisión.
- Una pregunta de prueba: el router y `DisclosurePolicy` calculan las evidencias autorizadas
  y luego consultan la RPC `buscar_evidencias_rag`. Se muestran IDs, textos y similitud.
  Esta prueba no crea una sesión ni genera datos adicionales.

«Sincronizar evidencias» vuelve a publicar el mismo documento y reconstruye su índice.
No cambia el contenido curado ni las respuestas sintéticas compartidas.

«Actualizar todas las evidencias», encima del catálogo, sincroniza **todas las especialidades**,
incluso si hay un filtro activo. El servidor lee los documentos actuales de Supabase, prepara
todo el índice y lo publica en lotes de hasta 100 casos usando la misma transacción de la
importación. No necesita otra migración. Informa cuántos casos y evidencias se actualizaron.
Si falla un lote, los anteriores permanecen sincronizados y el mensaje indica el avance;
se puede repetir sin modificar los casos curados. El botón se bloquea mientras trabaja.

Para sincronizar y activar el backend desde la terminal integrada de VS Code:

```powershell
npm run rag:sync -- --email docente@universidad.edu.pe --activate
```

Solo cambia `RAG_BACKEND` en `.env` después de comprobar las evidencias de todos los casos,
sus huellas, el modelo de embeddings y una recuperación real por la RPC. Luego reiniciar
con `npm start`. Sin `--activate` sincroniza y comprueba, conservando la configuración.

El panel siempre consulta Supabase. Para que el simulador use ese catálogo,
`CASE_STORE=supabase`. Para recuperación vectorial real,
`RAG_BACKEND=supabase_pgvector`, con la RPC existente y el mismo modelo/dimensión de
embeddings de la tabla. El panel muestra el backend activo; no lo cambia silenciosamente.
Si el backend es `local`, con casos en Supabase el simulador recupera directamente
las evidencias del caso remoto. No se presenta ese modo como búsqueda vectorial.

## Validación

`npm run test:cases` incluye pruebas del panel. Cubren sesión y roles, denegación de
alumnos e invitados, plantillas JSON/XLSX, referencias, fórmulas, tamaño máximo,
duplicados, revalidación y construcción del índice conversacional. Las pruebas HTTP
usan Supabase simulado y no publican casos en la base real.

La migración SQL se aplica por separado. El panel devuelve un mensaje con su nombre
si la RPC de publicación aún no existe.

Pruebas de navegador (con un servidor temporal en el puerto 3017):

```powershell
$env:TEST_BROWSER_CHANNEL = 'msedge'
node frontend/tests/docente.mjs
```

El guion simula sesiones y respuestas de la API; comprueba también la redirección al iniciar
sesión y el enlace del menú. Admite `TEST_BASE_URL` para usar otro puerto. Sin canal explícito
requiere el Chromium de Playwright. Las capturas quedan en `pruebas/27_panel_docente/`.

