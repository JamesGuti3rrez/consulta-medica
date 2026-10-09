# Consulta Médica Virtual

Prototipo de consulta médica virtual con un catálogo versionado de diez casos curados para
demostración. El simulador muestra una ficha pública de un caso; la conversación clínica interactiva
y el guardado de intentos aún no están implementados.

## Estructura

```text
consulta-medica/
├── frontend/
│   ├── public/                 # HTML, CSS, JavaScript y recursos servidos al navegador
│   ├── src/                    # Fuentes de Tailwind, imagen original y módulos futuros
│   ├── scripts/                # Generación de imágenes y copia de librerías de navegador
│   └── tailwind.*.config.cjs   # Configuración de estilos de cada página
├── backend/
│   ├── server/                 # API FastAPI: lógica sin IA (engine/, rag/, ...) y capa de IA (ai/)
│   ├── case_preparation/       # Pipeline fuera de línea: descarga, conversión y validación de casos
│   ├── tests/                  # Pruebas automatizadas
│   ├── evals/                  # Medición de la capa de IA
│   ├── supabase/migrations/    # SQL para las tablas de acceso
│   ├── scripts/                # Instalación del entorno Python e inicio del servidor
│   ├── pyproject.toml          # Dependencias del backend
│   └── uv.lock                 # Versiones bloqueadas de dependencias Python
├── schemas/                    # Esquema oficial del caso clínico (caso.schema.json)
├── data/                       # Datasets y casos por etapa (raw, validated, curated, ...)
├── docs/                       # Documentación técnica y decisiones de arquitectura
├── package.json                # Comandos de desarrollo y construcción del frontend
├── package-lock.json           # Versiones bloqueadas de dependencias Node
├── .env.example                # Plantilla de variables de entorno
└── .env                        # Configuración local; no compartir ni subir al repositorio
```

Cada carpeta nueva tiene un `README.md` que explica qué va en ella. La arquitectura completa está en
`docs/architecture/README.md`.

## Requisitos

- Node.js 18 o superior
- Python 3.12 o superior

## Inicio local

Desde la raíz del repositorio:

1. Copia `.env.example` como `.env` y completa los valores de Supabase (es opcional para ver la interfaz).
2. Instala las dependencias de frontend con `npm install`. Al terminar, copia el cliente de Supabase a
   `frontend/public/vendor/`.
3. Prepara el entorno Python y sus dependencias con `npm run setup`.
4. Inicia la aplicación con `npm start` y abre `http://localhost:3000`. El comando genera
   automáticamente las imágenes optimizadas y los estilos antes de levantar el servidor.

Estos comandos crean archivos que no se guardan en el repositorio (están en `.gitignore`): los CSS de
Tailwind, las imágenes optimizadas y `frontend/public/vendor/`. Si cambias las clases de Tailwind o la
imagen original mientras el servidor está en marcha, vuelve a ejecutar `npm run build`.

La aplicación entrega las páginas desde `frontend/public/`; el backend de `backend/server/` atiende
las rutas `/api`.

## Comandos del frontend

| Comando | Qué hace |
|---|---|
| `npm run build:css` | Compila Tailwind para la portada y el simulador |
| `npm run watch:css:portada` | Observa y recompila estilos de la portada |
| `npm run watch:css:simulacion` | Observa y recompila estilos del simulador |
| `npm run build:images` | Genera imágenes optimizadas desde `frontend/src/assets/consulta.png` |
| `npm run build:vendor` | Copia el cliente de Supabase a `frontend/public/vendor/` |
| `npm run build` | Genera imágenes y estilos |

Los CSS `frontend/public/css/tailwind-*.css` son generados con Tailwind CSS 4. Las fuentes comunes
están en `frontend/src/styles/tailwind.css`; los archivos `tailwind.portada.css` y
`tailwind.simulacion.css` determinan qué HTML y JavaScript se escanean para cada página. Vuelve a
ejecutar `npm run build:css` cuando cambien las clases Tailwind.

## Backend y datos

- `GET /api/status` informa si hay casos curados y cuántos están disponibles.
- `GET /api/caso` selecciona un caso curado y devuelve solo datos públicos aptos para el estudiante;
  diagnóstico, diferenciales y datos revelables quedan en el servidor.
- La ficha de demostración no constituye una simulación clínica interactiva ni ofrece consejo médico.
- `GET /api/config` entrega al navegador únicamente la URL y la clave pública de Supabase.
- La configuración local se carga desde `.env` en la raíz. El acceso a Supabase es opcional.
- Para preparar las tablas de acceso, ejecuta `backend/supabase/migrations/0001_perfiles_e_intentos.sql`
  en el SQL Editor de tu proyecto Supabase.
- La documentación interactiva de la API está disponible en `http://localhost:3000/api/docs`.
