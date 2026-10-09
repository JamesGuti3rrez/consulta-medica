# Uso con Codex

Codex es útil para continuar este proyecto localmente porque puede leer el repositorio, editar varios archivos y ejecutar pruebas desde el terminal/IDE.

## CLI

Con Node.js/npm instalado:

```bash
npm i -g @openai/codex
cd paciente_virtual_benchmark
codex
```

Inicia sesión cuando Codex lo solicite. El archivo `AGENTS.md` de este repositorio contiene las reglas experimentales que Codex debe conservar.

## Primer encargo recomendado para Codex

```text
Lee AGENTS.md y README.md. Ejecuta pytest -q y el benchmark mock. No cambies casos,
preguntas, prompts ni métricas. Revisa únicamente errores de ejecución y compatibilidad
con Windows/Colab. No fabriques resultados experimentales.
```

Después de validar la infraestructura, configura `.env` con `GROQ_API_KEY` y ejecuta el benchmark real con `--provider groq`.
