# HU-014 · Panel Doctor, grupos y desempeño

Fecha: 30 de octubre de 2026.

Estado: refinamiento aprobado e implementado. La migración fue aplicada por el usuario
y se verificaron grupos, sesiones y permisos en Supabase real. Este archivo conserva la
especificación que dio origen a la implementación; no modifica el backlog Word original.

Implementación, uso, decisiones finales y evidencia: [pruebas/HU-014/README.md](../../pruebas/HU-014/README.md).
Decisiones finales: una sesión/entrega por alumno y actividad, con recuperación al recargar;
las notas se leen de la sesión cerrada. Los reintentos como ejercicios nuevos se asignan
mediante otra actividad. Las ambigüedades se identifican, sin adjudicación manual automática.

## Correspondencia con el backlog

El documento `Product_Backlog_Paciente_Virtual_Adaptativo_v5.5_Sprint2_Unificado.docx`
incluye HU-013, «Rondas gamificadas de diagnóstico clínico», y HU-014, «Administrar
rondas y desempeño desde panel docente». HU-014 contempla asignar casos, participantes,
tiempos y desempeño, pero no especifica suficientemente grupos permanentes, pertenencia
autenticada ni comparación entre integrantes.

Se amplió HU-014 conservando su identificador. La modalidad de grupos puede
funcionar sin activar gamificación, premios o desempates de HU-013. No se alteran las
estimaciones ni los responsables del backlog sin refinamiento con el equipo.

## Historia de usuario refinada y aceptada

**Como doctor responsable de un grupo de alumnos, quiero crear y administrar grupos,
incorporar alumnos registrados, asignarles casos clínicos y consultar sus resultados
y tiempos de resolución, para comparar su desempeño dentro del grupo y orientar
la retroalimentación de su aprendizaje.**

El nombre visible del apartado será **Panel Doctor**. Los permisos deben seguir
comprobándose en el servidor a partir de roles válidos; cambiar la etiqueta de interfaz
no concede privilegios adicionales.

## Flujo implementado

1. El doctor abre el Panel Doctor y consulta los grupos que administra.
2. Crea un grupo con nombre y descripción; puede mantener varios grupos.
3. Añade alumnos mediante su cuenta registrada. La pertenencia se vincula al identificador
   de Auth, no únicamente a un nombre o correo escrito por el navegador.
4. Asigna un caso curado o un conjunto de casos al grupo. Se conserva el catálogo original.
5. El alumno inicia sesión, abre sus grupos y comienza una actividad asignada.
6. La consulta se vincula a alumno, grupo, asignación, caso y sesión desde el servidor.
7. Al entregar el diagnóstico mediante `/finish`, se conserva la entrega y se calculan
   los resultados con los motores existentes.
8. El doctor consulta el seguimiento individual y la comparación del grupo, con filtros
   por asignación, caso y estado.

La autenticación es obligatoria para pertenecer a grupos y realizar sus actividades.
El requisito no implica por sí mismo cambiar la práctica libre de invitado existente.
La propuesta no incluye envío automático de invitaciones o correos.

## Criterios de aceptación

| ID | Criterio verificable |
| --- | --- |
| CA1 | Los accesos y títulos del módulo muestran «Panel Doctor» y conservan los controles de rol. |
| CA2 | Un doctor autorizado crea grupos, consulta los propios y administra sus integrantes. |
| CA3 | Se incorporan únicamente alumnos registrados; no se duplica una pertenencia al mismo grupo. |
| CA4 | Un alumno sin autenticar no puede inscribirse ni iniciar una actividad de grupo. Un alumno autenticado solo consulta sus grupos y actividades permitidos. |
| CA5 | El doctor asigna un caso curado a un grupo y el alumno recibe exactamente esa asignación. Una sesión no puede atribuirse a otro alumno o grupo mediante campos manipulados. |
| CA6 | Se distinguen alumnos sin iniciar, en curso, finalizados y entregas pendientes de revisión. Un alumno sin entregar no figura como diagnóstico incorrecto. |
| CA7 | Tras el cierre se muestran diagnóstico entregado, estado de acierto, tiempo de resolución y puntajes calculados por el servidor. |
| CA8 | La comparación muestra a los integrantes del grupo para la misma asignación; ofrece filtros y resúmenes grupales sin mezclar actividades diferentes. |
| CA9 | Los datos permanecen en Supabase tras recarga o cambio de instancia; repetir el cierre no duplica entregas ni altera la primera entrega cerrada. |
| CA10 | Un doctor ajeno al grupo, un alumno de otro grupo y un invitado no acceden a participantes ni resultados ajenos. Las políticas de base y API cubren lectura y escritura. |
| CA11 | El diagnóstico de referencia no se revela al alumno antes del cierre. Una vista grupal no permite consultar respuestas o resultados protegidos de compañeros. |
| CA12 | Las pruebas reproducibles incluyen creación, incorporación, asignación, resolución, métricas, comparación, persistencia y denegación de acceso; la documentación de implementación incluye capturas reales. |

## Definición de indicadores

Se interpreta «si aceptó su diagnóstico» como **si acertó el diagnóstico**. La confirmación
de entrega constituye un dato distinto del acierto y debe quedar registrada por separado.

| Indicador | Definición propuesta |
| --- | --- |
| Estado de actividad | Sin iniciar / en curso / finalizada / pendiente de revisión. |
| Inicio del caso | Momento en que el servidor crea la consulta de esa asignación. |
| Entrega final | Momento del primer `/finish` aceptado para la consulta. |
| Tiempo de resolución | Diferencia entre entrega final e inicio, medida en el servidor. Es tiempo transcurrido, incluido el tiempo que el alumno deje abierta la consulta. |
| Diagnóstico entregado | Texto original conservado al cerrar; distinto del diagnóstico canónico. |
| Acierto diagnóstico | Correcto por referencia o sinónimo, incorrecto, sin respuesta o ambiguo/pendiente de revisión, según el resultado persistido del evaluador. |
| Puntaje de diagnóstico | Nota y motivo persistidos de la calificación diagnóstica. |
| Puntaje de proceso | Nota de anamnesis/evidencia disponible; la futura rúbrica de TA-029 puede ampliar su significado. |
| Intentos | Consultas vinculadas a la asignación; el modo de comparación debe indicar cuál se toma como referencia. |

El tiempo de resolución del alumno es diferente de la latencia de respuesta de la API,
el RAG o el modelo. La medición de tiempo activo, pausas o tiempo entre preguntas sería
una ampliación explícita, no un significado implícito de la duración total.

No se inventa una nota combinada entre diagnóstico y proceso. Si se requiere una nota
global, el equipo debe definir su rúbrica y ponderación antes de implementarla.

## Comparación implementada

- Tabla individual: alumno, estado, caso asignado, inicio, cierre, duración, acierto,
  nota diagnóstica y nota del proceso.
- Resumen del grupo: asignados, iniciados, finalizados, pendientes de revisión,
  tasa de acierto de entregas resueltas y promedios de tiempo/puntajes con su denominador.
- Conservar una sesión y una entrega por alumno para una misma asignación; repetir el
  inicio recupera esa consulta. Para nuevos ejercicios se crea otra actividad.
- Mostrar las respuestas ambiguas como pendientes de revisión, sin contabilizarlas
  automáticamente como errores definitivos en el porcentaje de acierto.
- No clasificar alumnos únicamente por velocidad. El doctor puede analizar por separado
  acierto, proceso y duración.
- El acceso a resultados ajenos queda en el Panel Doctor; compartir una clasificación
  con los alumnos necesita una política de privacidad explícita.

## Base técnica reutilizada y ampliación

Ya existen identidad de usuario, autorización por propietario, inicio/cierre de sesión,
eventos, evaluación del proceso y calificación diagnóstica persistida. `build_attempt`
calcula `duracion_segundos` a partir de `started_at` y `finished_at`; ese campo solo llega
al historial cuando su persistencia está habilitada y la tabla correspondiente existe.
El módulo de grupos consulta directamente el estado persistido y no depende de habilitar
ese historial opcional.

Se añadieron entidades para grupos, integrantes, asignaciones y vinculación de entregas,
con claves, ownership, restricciones únicas, RLS y RPC exclusivas del servidor. La migración
0005 fue aplicada y verificada. El código de evaluación existente se reutiliza para que
el reporte del alumno y la tabla del doctor muestren las mismas notas. El cierre condicional
también protege el primer resultado frente a solicitudes concurrentes.

Componentes desarrollados, sin asignar identificadores ni estimaciones nuevas:

1. Renombrado visual y navegación del Panel Doctor.
2. Modelo y permisos de grupos e integrantes.
3. Asignación de casos y acceso del alumno autenticado.
4. Persistencia y consulta de entregas y métricas.
5. Tabla comparativa y resumen del grupo.
6. Pruebas de autorización, recorrido completo y documentación con capturas.

## Corrección de carga y unicidad de nombres

El panel recupera también grupos sin alumnos ni actividades al entrar, aunque el perfil
se verifique antes de cargar el módulo. La carga de grupos no depende de que el catálogo
de casos responda. La selección de casos se completa cuando termina su consulta.

`0006_grupos_nombres_unicos.sql` establece nombres únicos **por doctor**, ignorando
mayúsculas, espacios iniciales/finales y espacios repetidos (incluidos tabuladores y
espacios no separables). El índice único protege creación y edición concurrentes.
Una colisión devuelve HTTP 409 y «Ya tienes un grupo con ese nombre. Elige otro nombre.».
Editar un grupo sin cambiar su nombre lógico sigue permitido.

La migración conserva el nombre del grupo más antiguo y renombra los duplicados con
sufijos disponibles `(2)`, `(3)`, etc.; conserva identificadores, miembros, actividades
y resultados. Puede volver a ejecutarse sin volver a renombrar grupos. Fue aplicada
por el usuario y se verificó la restricción en Supabase real.
