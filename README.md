# Consulta Médica Virtual

Simulador de consulta médica para estudiantes de medicina: el alumno entrevista por voz a un
paciente virtual, plantea y descarta hipótesis, registra su diagnóstico y recibe una hoja de
evaluación.

## Cómo usarlo

Requisitos: Node.js 18 o superior (para compilar estilos e imágenes) y Python 3.11 o superior
(para el backend).

1. Abre la carpeta `consulta-medica` en VS Code.
2. La primera vez, ejecuta `npm install` y luego `npm run setup` (crea `.venv` e instala el backend).
3. Ejecuta `npm start` y abre `http://localhost:3000`.

El micrófono funciona en Chrome o Edge.

## Estructura

```
consulta-medica/
├── public/                         # Lo único que el servidor entrega al navegador
│   ├── index.html                  # Portada: presentación, elección de caso, iniciar sesión y crear cuenta
│   ├── simulacion.html             # Consulta, tablilla médica y hoja de evaluación
│   ├── css/
│   │   ├── styles.css              # Colores de ambas páginas (tema claro y oscuro) y estilos base
│   │   ├── landing.css             # Estilos y animaciones de la portada
│   │   ├── simulacion.css          # Estilos y animaciones de la simulación
│   │   ├── perfil.css              # Menú de perfil y selector de tema (ambas páginas)
│   │   ├── tailwind-portada.css    # Generado con npm run build:css (no editar)
│   │   └── tailwind-simulacion.css # Generado con npm run build:css (no editar)
│   ├── js/
│   │   ├── auth.js                 # Sesión con Supabase compartida por las páginas
│   │   ├── perfil.js               # Encabezado con la sesión, menú de perfil y tema (ambas páginas)
│   │   ├── landing.js              # Ventanas, cuentas y animaciones de la portada
│   │   └── simulacion.js           # Lógica de la consulta, hipótesis y evaluación
│   ├── vendor/supabase.js          # Librería de Supabase (copiada de node_modules al instalar)
│   └── assets/                     # Ilustración en WebP, ícono y vista previa para compartir
├── server/                         # Backend (Python + FastAPI)
│   ├── main.py                     # Aplicación, rutas de la API y archivos de public/
│   ├── config.py                   # Lee las claves de .env
│   └── clinical_case.py            # Lectura del caso y evaluación del razonamiento
├── data/
│   └── caso-demo.json              # Caso clínico con su guion y respuestas (privado, no se publica)
├── src/
│   ├── assets/consulta.png         # Ilustración original (fuente de npm run build:images)
│   └── styles/tailwind.css         # Fuente de Tailwind para las dos páginas
├── supabase/migrations/            # SQL de la base de datos (perfiles e intentos)
├── scripts/
│   ├── python.mjs                  # npm run setup / npm start: entorno y servidor de Python
│   ├── copy-vendor.mjs             # Copia la librería de Supabase a public/vendor/
│   └── optimize-images.mjs         # Genera las imágenes WebP, la vista previa y el ícono
├── tailwind.portada.config.cjs     # Configuración de Tailwind de la portada
├── tailwind.simulacion.config.cjs  # Configuración de Tailwind de la simulación
├── requirements.txt                # Dependencias del backend
├── package.json                    # Comandos y dependencias de estilos e imágenes
├── .env.example                    # Plantilla de claves (copiar como .env, nunca se publica)
└── .vscode/                        # Extensiones y ajustes recomendados
```

Buenas prácticas que sigue esta organización:

- **Solo `public/` es accesible desde el navegador.** El caso clínico con el diagnóstico correcto,
  el código del servidor y la configuración no se pueden descargar.
- **Código fuente separado del generado.** Los archivos `tailwind-*.css` se generan a partir de
  `src/styles/tailwind.css`; no se editan a mano.
- **Sin dependencias de CDN para los estilos.** Las dos páginas usan Tailwind compilado.

## Comandos

| Comando | Qué hace |
|---|---|
| `npm run setup` | Crea `.venv` e instala las dependencias de Python |
| `npm start` | Levanta el backend en `http://localhost:3000` |
| `npm run build:css` | Compila Tailwind de ambas páginas |
| `npm run watch:css:portada` | Recompila la portada mientras editas |
| `npm run watch:css:simulacion` | Recompila la simulación mientras editas |
| `npm run build:images` | Regenera las imágenes a partir de `src/assets/consulta.png` y `public/assets/favicon.svg` |
| `npm run build:vendor` | Copia la librería de Supabase a `public/vendor/` (se hace solo con `npm install`) |
| `npm run build` | Imágenes y estilos |

Si agregas o cambias clases de Tailwind en un HTML o en su JS, vuelve a compilar con
`npm run build:css`.

## API

Documentación interactiva con el servidor encendido: `http://localhost:3000/api/docs`.

| Ruta | Descripción |
|---|---|
| `GET /api/caso` | Caso clínico sin el diagnóstico ni los diferenciales |
| `GET /api/status` | Proveedor de respuestas (guion local) |
| `GET /api/config` | URL de Supabase y clave pública para iniciar sesión (nunca la secreta) |
| `POST /api/chat` | Recibe el turno del alumno y devuelve la pregunta del médico y la respuesta del paciente |
| `POST /api/hipotesis` | Reconoce una hipótesis entre los diferenciales del caso |
| `POST /api/evaluar` | Evalúa las hipótesis y el diagnóstico final |

## Inicio de sesión

Es opcional: sin cuenta se practica igual. Usa Supabase Auth con correo y contraseña.

1. Crea un proyecto en [supabase.com](https://supabase.com) y ejecuta
   `supabase/migrations/0001_perfiles_e_intentos.sql` en **SQL Editor**.
2. Copia `.env.example` como `.env` y completa la URL y las dos claves
   (**Project Settings → API Keys**). `.env` nunca se publica.
3. Reinicia el servidor (`npm start`).

Al registrarse, Supabase envía un correo de confirmación; el enlace vuelve a
`http://localhost:3000` con la sesión iniciada.

## Diagnóstico diferencial

Durante la consulta el alumno escribe o dicta sus hipótesis y las descarta indicando el motivo.
Cada hipótesis se reconoce con los `sinonimos` de `diagnosticos_diferenciales` en
`data/caso-demo.json` (sin distinguir mayúsculas ni tildes). Al finalizar, `/api/evaluar` revisa
si planteó la hipótesis correcta, si consideró las peligrosas y si descartó cada una después de
obtener el dato necesario (`turnos_necesarios`).
