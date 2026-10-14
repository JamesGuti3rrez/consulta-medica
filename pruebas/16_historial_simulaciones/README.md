# 16. Historial de simulaciones del alumno

## Objetivo

Como parte del inicio de sesión: cada consulta que termina un alumno **con la sesión iniciada** se guarda
en Supabase (tabla `intentos`) y aparece en «Mis simulaciones». Un invitado puede usar el simulador
igual, pero sus consultas no se guardan.

## Cómo funciona

1. Al **iniciar** la consulta, el simulador envía el token de la sesión del alumno
   (`Authorization: Bearer ...`). El servidor lo comprueba con Supabase Auth y deja la consulta a su
   nombre (`owner_id`, que no se devuelve al navegador).
2. Al **finalizar**, el simulador envía otra vez el token, el diagnóstico y las hipótesis. El servidor
   guarda el intento solo si el token es válido y es del mismo alumno que la empezó.
3. El puntaje es el que calculó el motor clínico en el servidor. La tabla `intentos` no tiene política de
   insert, así que desde el navegador no se puede crear ni inventar un intento: solo el servidor escribe,
   con la clave secreta.
4. «Mis simulaciones» (menú de perfil, en la portada y en el simulador) lee los intentos con el cliente
   de Supabase del navegador; la seguridad por filas (RLS) solo le entrega los del propio alumno. No
   muestra el código del caso.
5. La hoja de evaluación dice si la consulta se guardó o por qué no. Si Supabase falla, la evaluación se
   muestra igual.

Respuesta de `POST /api/ai/sessions/{id}/finish`, campo `attempt`:

| Situación | `attempt` |
| --- | --- |
| Alumno con sesión que empezó la consulta | `{"saved": true, "id": "<uuid>"}` (cerrar otra vez no duplica) |
| Sin token (invitado) | `{"saved": false, "reason": "sin_sesion"}` |
| La consulta empezó sin sesión | `{"saved": false, "reason": "iniciada_sin_sesion"}` |
| Token falso o vencido | `{"saved": false, "reason": "sesion_invalida"}` |
| Token válido de otro alumno | `{"saved": false, "reason": "otro_usuario"}` |
| Supabase no responde | `{"saved": false, "reason": "error"}` |
| Servidor sin Supabase configurado | `{"saved": false, "reason": "no_configurado"}` |

No hizo falta migración: la tabla `intentos` de `0001_perfiles_e_intentos.sql` ya existía en Supabase.
El puntaje se guarda redondeado a entero (`smallint`): 18,75 % queda como 19 %.

## Commits

| Commit | Cambio |
| --- | --- |
| `e6035d6` | Módulo `server/persistence/attempts.py`: verificación del token y guardado del intento |
| `e5a7792` | `/finish` guarda el intento; cerrar dos veces no lo duplica |
| `a5a61cc` | El simulador envía la sesión al finalizar y la hoja avisa si se guardó |
| `5b5492b` | «Mis simulaciones» activo en el menú de perfil, con el historial |
| `e3b3056` | Corrección de seguridad: la consulta queda ligada al alumno que la inicia (ver intento 1) |
| `013e689` | El simulador inicia la consulta a nombre del alumno |

## Comandos

Pruebas automáticas, desde `backend/`:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Prueba en el navegador con el servidor local en el puerto 3000 (modo local, sin Groq) y un alumno de
prueba temporal creado en Supabase Auth. Desde la raíz:

```powershell
$C = "$env:TEMP\alumno_prueba.json"
backend\.venv\Scripts\python.exe pruebas\16_historial_simulaciones\usuario_prueba.py crear $C
$env:CREDENCIALES = $C; node pruebas/16_historial_simulaciones/probar_historial.cjs
backend\.venv\Scripts\python.exe pruebas\16_historial_simulaciones\usuario_prueba.py intentos $C
backend\.venv\Scripts\python.exe pruebas\16_historial_simulaciones\usuario_prueba.py borrar $C
```

`usuario_prueba.py` guarda el correo y la contraseña del alumno de prueba solo en ese archivo, fuera del
repositorio, y nunca los imprime. Al borrarlo, sus intentos se borran en cascada.

## Resultados

| Ejecución | Resultado | Evidencia |
| --- | --- | --- |
| Pruebas del backend | 159 aprobadas (8 nuevas: 4 del módulo de intentos y 4 de la API) | `ejecucion/01_pruebas_backend.txt`, `_terminal.png` |
| Navegador | Invitado: no se guarda y la hoja lo avisa. Con sesión: 2 de 2 consultas guardadas; el historial muestra las 2 en el simulador y en la portada; sin código del caso ni errores de consola | `ejecucion/02_historial_navegador.txt`, `_terminal.png`, `resultados/*.png` |
| Supabase | Los 2 intentos del alumno de prueba con puntaje, diagnóstico, hipótesis, duración y alertas | `ejecucion/03_intentos_en_supabase.txt`, `_terminal.png` |
| Limpieza | Alumno de prueba borrado; quedan 0 intentos suyos | `ejecucion/04_borrar_alumno_prueba.txt`, `_terminal.png` |

Las fotos (`.png`) se guardan en el equipo y no se suben a GitHub.

## Prueba en Vercel (producción)

Tras el push del commit `62afe63`, Vercel desplegó el sitio (`https://consulta-medica-three.vercel.app`,
«Deployment has completed»). Allí responde Groq y los intentos se guardan en el Supabase real. Se repitió la
prueba del navegador con un alumno de prueba temporal, borrado al terminar:

| Comprobación | Resultado |
| --- | --- |
| Invitado | No se guarda (`sin_sesion`) y la hoja lo avisa |
| Con sesión | 2 de 2 consultas guardadas; el historial las muestra en el simulador y en la portada |
| Supabase | 2 intentos con puntaje (100 y 19), diagnóstico, hipótesis, duración y la alerta de contraindicación |
| Limpieza | Alumno borrado; quedan 0 intentos suyos |
| Pantalla | Sin código del caso ni errores de consola |

Evidencia: `vercel/05_historial_vercel.txt`, `vercel/06_intentos_vercel_en_supabase.txt`,
`vercel/07_borrar_alumno_prueba.txt`, sus fotos de terminal y las capturas `vercel/*.png`. La foto de
terminal es de una segunda corrida con otro alumno temporal, también borrado.

## Intento fallido

### Intento 1: cualquiera con el id de la consulta podía quedarse con ella

La primera versión (`e5a7792`) guardaba el intento para cualquier token válido que llegara a `/finish`.
Una revisión automática de seguridad marcó un problema de control de acceso en `api/ai.py`: la consulta
no estaba ligada a quien la empezó, así que otro alumno que conociera el id (por ejemplo, de un
registro) podía cerrarla con su propio token y guardar ese resultado como suyo.

Corrección (`e3b3056`): el token se comprueba también al iniciar y la consulta queda a nombre de ese
alumno. Al cerrar, solo se guarda si el token es del mismo alumno. Las pruebas
`test_only_the_student_who_started_the_consultation_can_save_it` cubren los dos casos: otro alumno
(`otro_usuario`) y una consulta empezada como invitado (`iniciada_sin_sesion`).

## Observaciones

- Las demás rutas de la consulta (`/message`, `/events`) siguen sin exigir dueño: quien tenga el id
  puede seguir la conversación. Como el id es un UUID aleatorio no se puede adivinar, pero conviene
  revisarlo si se comparten registros con ids de consultas.
- Si el alumno inicia sesión con la consulta ya empezada, esa consulta no se guarda; las siguientes sí.
