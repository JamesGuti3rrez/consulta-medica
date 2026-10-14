# frontend/

Interfaz web del estudiante: portada, simulación, reporte y voz.

## Se conserva sin cambios

`public/` (páginas, `js/`, `css/`, `assets/`, `vendor/`), `scripts/`, los archivos ya existentes de `src/` y las dos configuraciones de Tailwind. El simulador puede cargar un expediente de demostración desde el catálogo curado. La conversación clínica interactiva y la persistencia de intentos siguen pendientes.

## Estructura preparada en `src/`

| Carpeta | Responsabilidad |
| --- | --- |
| `api/` | Único punto de contacto con el backend (`/api/...`). Ningún otro módulo hace `fetch` directo. |
| `features/landing/` | Portada, elección de especialidad, inicio de sesión. |
| `features/simulation/` | Consulta, tablilla, hipótesis, diagnóstico y tratamiento. |
| `features/report/` | Hoja de evaluación final. |
| `features/account/` | Perfil, sesión y preferencias (tema). |
| `avatar/` | Integración de Rive (o Three.js): traduce el estado que envía el backend a animaciones. No decide nada clínico. |
| `voice/` | Web Speech API (reconocimiento y síntesis) y alternativa por texto. |
| `state/` | Estado de la vista en el cliente. El estado clínico lo decide el backend. |
| `ui/` | Componentes reutilizables y accesibles (ventanas, pestañas, botones). |

`public/assets/avatars/` guardará los archivos del avatar (por ejemplo `.riv`).

## Decisión pendiente

El prototipo es HTML + JavaScript + Tailwind sin empaquetador; documentos anteriores proponían React. Los módulos de `src/` solo se usarán cuando se adopte un empaquetador o framework. Hasta entonces, el código del navegador sigue en `public/js/`.

El frontend nunca recibe `protected`: solo lo que la API ya filtró.

## Demo del catálogo curado

Al iniciar el simulador, `GET /api/status` comprueba si existen casos curados y habilita el botón
para solicitar uno. `GET /api/caso` entrega una selección aleatoria con campos permitidos del
expediente; el navegador muestra la ficha usando `textContent`. No se envían al frontend las
secciones `on_request` ni `protected`. Esta etapa carga datos para demostración, pero no implementa
todavía turnos de conversación, evaluación clínica ni guardado de intentos.

Evidencia visual del hito: `pruebas/04_frontend/` (las fotos se guardan en el equipo, no en GitHub).

## Alertas y hoja de evaluación

Cada respuesta de `POST /api/ai/sessions/{id}/message` puede traer `safety_alerts`: cuando el estudiante
propone un tratamiento que coincide con una alergia registrada o una contraindicación del caso, el
simulador muestra el aviso del motor clínico, que no nombra el fármaco ni el motivo protegido.

Al guardar el diagnóstico, `POST /api/ai/sessions/{id}/finish` devuelve `evaluation` (puntaje, datos clave
obtenidos y conteo de omisiones por tipo de error) y el simulador llena la «Hoja de evaluación clínica»
de `simulacion.html`. Las hipótesis y el diagnóstico de la hoja salen de lo que registró el estudiante;
el puntaje no califica el diagnóstico escrito. El botón «Realizar Diagnóstico» pasa a «Ver hoja de
evaluación» para reabrirla. Evidencia: `pruebas/15_integracion_motor_clinico/`.

## Mis simulaciones

Con la sesión iniciada, el simulador envía el token de Supabase al iniciar y al finalizar la consulta; el
servidor guarda el intento (puntaje del motor clínico, diagnóstico, hipótesis y duración) solo si la
consulta la empezó ese mismo alumno. La hoja de evaluación avisa si se guardó o por qué no. «Mis
simulaciones», en el menú de perfil (`public/js/perfil.js`), lista los intentos del alumno leyendo
`intentos` con el cliente de Supabase; RLS solo le entrega los suyos. Evidencia:
`pruebas/16_historial_simulaciones/`.
