// Ejecuta el backend de Python desde npm, en Windows, macOS o Linux.
//   node scripts/python.mjs setup   crea .venv e instala las dependencias de pyproject.toml
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
  run(venvPython, ['-m', 'ensurepip', '--upgrade']);
  run(venvPython, ['-m', 'pip', 'install', '--upgrade', 'pip']);
  // Las dependencias se declaran una sola vez, en pyproject.toml (Vercel también las lee de ahí).
  const installFromPyproject = [
    'import subprocess, sys, tomllib',
    'deps = tomllib.load(open("pyproject.toml", "rb"))["project"]["dependencies"]',
    'subprocess.run([sys.executable, "-m", "pip", "install", *deps], check=True)',
  ].join('; ');
  run(venvPython, ['-c', installFromPyproject]);
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
