// Ejecuta el backend de Python desde npm, en Windows, macOS o Linux.
//   node scripts/python.mjs setup   crea .venv e instala requirements.txt
//   node scripts/python.mjs start   levanta el servidor en http://localhost:3000 (o el puerto de PORT)
import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { join } from 'node:path';

const venvPython = process.platform === 'win32'
  ? join('.venv', 'Scripts', 'python.exe')
  : join('.venv', 'bin', 'python');

function run(command, args) {
  const result = spawnSync(command, args, { stdio: 'inherit' });
  if (result.error) {
    console.error(`No se pudo ejecutar "${command}": ${result.error.message}`);
    process.exit(1);
  }
  if (result.status !== 0) process.exit(result.status ?? 1);
}

const task = process.argv[2];

if (task === 'setup') {
  const systemPython = process.platform === 'win32' ? 'python' : 'python3';
  if (!existsSync(venvPython)) run(systemPython, ['-m', 'venv', '.venv']);
  run(venvPython, ['-m', 'pip', 'install', '--upgrade', 'pip']);
  run(venvPython, ['-m', 'pip', 'install', '-r', 'requirements.txt']);
} else if (task === 'start') {
  if (!existsSync(venvPython)) {
    console.error('Falta el entorno de Python. Ejecuta primero: npm run setup');
    process.exit(1);
  }
  const port = process.env.PORT || '3000';
  console.log(`Consulta Médica disponible en http://localhost:${port}`);
  run(venvPython, ['-m', 'uvicorn', 'server.main:app', '--port', port]);
} else {
  console.error('Uso: node scripts/python.mjs setup|start');
  process.exit(1);
}
