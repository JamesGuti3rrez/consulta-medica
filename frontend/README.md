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

Evidencia visual del hito: `docs/evidence/simulador-caso-curado.png`.
