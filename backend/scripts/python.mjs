// Ejecuta el backend de Python desde npm, en Windows, macOS o Linux.
//   node backend/scripts/python.mjs setup   crea backend/.venv e instala las dependencias
//   node backend/scripts/python.mjs start   levanta el servidor en http://localhost:3000
import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const backendDir = dirname(dirname(fileURLToPath(import.meta.url)));
const venvPython = process.platform === 'win32'
  ? join(backendDir, '.venv', 'Scripts', 'python.exe')
  : join(backendDir, '.venv', 'bin', 'python');

function run(command, args) {
  const result = spawnSync(command, args, { stdio: 'inherit', cwd: backendDir });
  if (result.error) {
    console.error(`No se pudo ejecutar "${command}": ${result.error.message}`);
    process.exit(1);
  }
  if (result.status !== 0) process.exit(result.status ?? 1);
}

function parseExtras(inputArgs) {
  const extrasIndex = inputArgs.indexOf('--extras');
  if (extrasIndex === -1) return [];
  const extraValue = inputArgs[extrasIndex + 1];
  if (!extraValue) {
    console.error('Falta el valor de --extras (por ejemplo: pipeline,dev)');
    process.exit(1);
  }
  return extraValue.split(',').map((value) => value.trim()).filter(Boolean);
}

const task = process.argv[2];

if (task === 'setup') {
  const systemPython = process.platform === 'win32' ? 'python' : 'python3';
  const extraGroups = parseExtras(process.argv.slice(2));

  if (!existsSync(venvPython)) run(systemPython, ['-m', 'venv', '.venv']);
  run(venvPython, ['-m', 'ensurepip', '--upgrade']);
  run(venvPython, ['-m', 'pip', 'install', '--upgrade', 'pip']);

  const extrasSpec = extraGroups.length > 0 ? `[${extraGroups.join(',')}]` : '';
  run(venvPython, ['-m', 'pip', 'install', '-e', `.${extrasSpec}`]);
} else if (task === 'start') {
  if (!existsSync(venvPython)) {
    console.error('Falta el entorno de Python. Ejecuta primero: node backend/scripts/python.mjs setup --extras pipeline,dev');
    process.exit(1);
  }
  const port = process.env.PORT || '3000';
  console.log(`Consulta Médica disponible en http://localhost:${port}`);
  run(venvPython, ['-m', 'uvicorn', 'server.main:app', '--port', port]);
} else {
  console.error('Uso: node backend/scripts/python.mjs setup [--extras pipeline,dev]|start');
  process.exit(1);
}
