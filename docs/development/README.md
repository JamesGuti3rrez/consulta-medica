# Desarrollo del backend

## Entorno recomendado

Se usa Python 3.12 o superior y un entorno virtual local en `backend/.venv`.

## Instalación

Desde la raíz del repositorio:

```bash
cd backend
node scripts/python.mjs setup --extras pipeline,dev
```

Eso crea el entorno virtual y instala `project.dependencies` junto con los extras opcionales definidos en `backend/pyproject.toml`:

- `pipeline`: dependencias de validación y preparación de datos (`jsonschema`)
- `dev`: dependencias de desarrollo y evidencia (`pytest`, `pygments`, `pillow`)

Si solo necesitas la base del servidor, basta con:

```bash
cd backend
node scripts/python.mjs setup
```

## Ejecutar el servidor

```bash
cd backend
node scripts/python.mjs start
```

## Despliegue en Vercel

Vercel publica `main` automáticamente (proyecto `consulta-medica`, preset FastAPI). Archivos de la raíz:

| Archivo | Para qué sirve |
| --- | --- |
| `vercel_app.py` | Punto de entrada: añade `backend/` a la ruta de importación y expone `server.main:app`. |
| `pyproject.toml` | Dependencias de ejecución del servidor publicado y `[tool.vercel] entrypoint`. Si cambian las de `backend/pyproject.toml`, hay que copiarlas aquí. |
| `vercel.json` | Compila el frontend (`npm ci && npm run build`: estilos e imágenes) e incluye `frontend/public` en la función, que sirve las páginas igual que en local. |
| `.vercelignore` | Excluye del despliegue el `.env`, los entornos, las pruebas, los documentos y los datos sin procesar. |

Variables del proyecto en Vercel (Production y Preview): `GROQ_API_KEYS`, `AI_TRACE_PATH=/tmp/ai_traces.jsonl`
y `RAG_LOG_PATH=/tmp/rag_retrieval.jsonl` (en Vercel solo se puede escribir en `/tmp`) y `RAG_EMBEDDED=false`
(el índice LightRAG no se publica; los agentes leen la evidencia del caso). Las claves nunca van en el repositorio.

Limitación: las sesiones de la consulta viven en memoria. Vercel suele reutilizar la misma instancia, pero si una
petición cae en otra, la sesión se pierde y hay que iniciar otra consulta.
