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
