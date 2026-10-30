# HU-011 · Panel Doctor, grupos y desempeño

Implementación del refinamiento aprobado el 30/10/2026. El nombre visible del panel es
**Panel Doctor**, conservando `docente.html` y los roles de servidor profesor/administrativo.
El código actual es **HU-011**, antes HU-014, por indicación del usuario y pendiente de
incorporación manual al backlog. La carpeta `pruebas/HU-014` conserva la evidencia
original. Este informe no da por completada HU-010 (rondas gamificadas).

## Uso

1. El doctor inicia sesión y abre `docente.html?seccion=grupos`.
2. Crea un grupo y añade el correo de alumnos ya registrados. No se envían invitaciones.
3. Asigna casos curados con un título que no revele el diagnóstico.
4. El alumno inicia sesión y abre **Mis grupos**, desde su menú o `grupos.html`.
5. Resuelve el caso asignado. La actividad se vincula a su sesión desde el servidor.
6. El doctor pulsa **Actualizar** para consultar estados, diagnósticos entregados,
   acierto, duración y notas de diagnóstico/proceso. El filtro compara la misma actividad.

Se conserva una entrega por alumno y actividad: recargar reutiliza la consulta y su
primer cierre. El doctor puede crear otra actividad cuando necesita un nuevo ejercicio.
Los integrantes incorporados reciben las actividades que están abiertas en ese momento;
las actividades cerradas mantienen su roster histórico. La reapertura sirve al roster ya
asignado; para otra cohorte se crea una actividad nueva.

Retirar un integrante revoca el acceso a sus sesiones del grupo y conserva su historial
para el doctor. Los resultados de retirados se excluyen de los promedios actuales.

## Persistencia y configuración

Migración: `backend/supabase/migrations/0005_grupos_doctor.sql`. El usuario confirmó su
ejecución y se verificaron las RPC, las tablas y sus privilegios en Supabase real.
Después se aplica `0006_grupos_nombres_unicos.sql`: nombre único por doctor, ignorando
mayúsculas y espacios repetidos. Rechaza creación y edición duplicadas con HTTP 409,
incluidas peticiones simultáneas. Los duplicados anteriores reciben un sufijo disponible
`(2)`, `(3)`, etc., sin eliminar grupos ni modificar sus vínculos. También fue aplicada.
Requiere `0002` (sesiones) y `0003` (casos); no depende de `perfiles`, `intentos` ni de
habilitar el historial opcional. Las sesiones de grupo requieren `SESSION_STORE=supabase`.

Tablas: `doctor_grupos`, `doctor_grupo_miembros`, `doctor_asignaciones` y
`doctor_participaciones`. RLS activado y acceso directo revocado a anon/authenticated.
Las RPC son exclusivas del backend; validan rol y propietario. El actor proviene de
Supabase Auth y nunca de un campo editable del navegador.

Los resultados se proyectan desde `sma_sesiones.state`, evitando duplicar o recalcular
notas. Los RPC de lectura excluyen diagnóstico y puntuación antes del cierre. El inicio
de actividad crea sesión, evento y vinculación dentro de una transacción con bloqueo
de grupo; llamadas simultáneas devuelven la misma consulta.

## Indicadores

- Tiempo: cierre menos inicio, calculado con timestamps del servidor; incluye pausas y
  no mide la latencia del LLM ni tiempo activo frente a pantalla.
- Acierto: correctos / entregas evaluadas. Incorrecto y vacío cuentan como no acertados;
  ambiguo queda pendiente de revisión y fuera del denominador de acierto.
- Sin iniciar/en curso: sin nota ni diagnóstico publicado. No se convierten en cero.
- Diagnóstico y proceso: puntajes independientes, sin inventar una ponderación global.
- No se implementa adjudicación manual de ambiguos ni ranking público entre alumnos.
- La práctica libre conserva su flujo; las actividades de grupo requieren cuenta.

## Pruebas y evidencia

| Evidencia | Resultado |
| --- | --- |
| `pytest.xml` | 16 pruebas HTTP/métricas contra las migraciones ejecutadas en PostgreSQL local |
| `regresion.xml` | 704 pruebas aprobadas; 3 de servicios vivos deseleccionadas |
| `sql.json` | 14 escenarios SQL; unicidad, migración de duplicados, transacciones y permisos |
| `navegador.json` | Recorrido real de la interfaz y API, con Auth y voz controlados |
| `carga_grupos.json` | 8 comprobaciones de grupos vacíos, salida/regreso, carreras de carga, catálogo lento/fallido y nombres duplicados |
| `ui_adicional.json` | Vista de 390 px y cambio de identidad que abandona el panel |
| `supabase_real.json` | Auth, grupos, casos, sesiones y métricas reales; limpieza confirmada |

La prueba remota incorporó cinco alumnos: tres finalizados (correcto, incorrecto y
ambiguo), uno en curso y uno sin iniciar. Resultado: un acierto sobre dos entregas
evaluadas = 50%. Se verificó persistencia entre instancias, cierre inmutable, revocación
del integrante retirado y denegación directa de tablas/RPC con clave de navegador.
Se eliminaron siete cuentas temporales, un grupo y cuatro sesiones con sus eventos.
No se modificaron los casos curados, usuarios existentes ni el `.env`.

El cierre de grupo usa una actualización condicional: dos solicitudes concurrentes
conservan la primera calificación y producen un único evento de cierre. Un turno tardío
no puede reabrir una sesión finalizada. Esta condición se comprobó localmente y con
Supabase real, sin requerir otra migración.

El motor local de pruebas es PostgreSQL en WASM (PGlite), con la migración real; Auth y
datos son fixtures. No se lo presenta como un despliegue de Supabase productivo.
En la comprobación real se usa un LLM local controlado: el flujo de grupos y la nota
diagnóstica no requieren generación externa para comprobarse.

## Ejecutar en la terminal de VS Code

```powershell
npm install
npm run test:groups
npm run test:groups:sql
npm run test:sprint2 -- --junitxml=../pruebas/HU-014/regresion.xml
```

Para repetir el navegador, mantener las dos primeras órdenes en terminales separadas:

```powershell
node pruebas/HU-014/sql_server.mjs
.\backend\.venv\Scripts\python.exe pruebas/HU-014/servidor_evidencia.py
node pruebas/HU-014/probar_carga_grupos.mjs
node pruebas/HU-014/probar_navegador.mjs
node pruebas/HU-014/capturas_adicionales.mjs
```

Solo escuchan en loopback: PostgreSQL HTTP de fixture 3039 y API/UI de prueba 3037.
`tests/groups/conftest.py` levanta su propio PostgreSQL en un puerto libre para pytest.
PGlite es una dependencia de desarrollo; no entra en el frontend del simulador.
Las pruebas del navegador se ejecutan consecutivamente: ambas preparan sus propios
grupos en el fixture. La prueba de carga controla los tiempos de respuesta del perfil,
del módulo y del catálogo; mantiene las consultas reales de la API a PostgreSQL.
Pytest limpia las tablas de grupos/sesiones entre pruebas conservando el motor y los
casos/usuarios de fixture, evitando acumular grupos de pruebas anteriores.

Prueba remota (crea y limpia datos temporales, necesita las claves del `.env`):

```powershell
.\backend\.venv\Scripts\python.exe pruebas/HU-014/verificar_supabase.py
```

Capturas y Word:

```powershell
.\backend\.venv\Scripts\python.exe pruebas/HU-014/capturar_terminal.py
.\backend\.venv\Scripts\python.exe pruebas/HU-014/documentar.py
```

Las capturas nativas muestran registros originales en ventanas propias de PowerShell;
no se presentan como capturas de la terminal integrada de VS Code. El manifiesto conserva
SHA-256 de cada registro. Las imágenes del navegador provienen de la UI y API ejecutadas.
El documento queda en `Entregables/Sprint2/HU-011_Panel_Doctor_Grupos_y_Desempeno.docx`.
