// Extrae la imagen quieta de cada personaje de su video de LivePortrait: node frontend/scripts/prepare-avatar-videos.mjs
// Necesita ffmpeg (en el PATH o en la variable FFMPEG). Se ejecuta solo al cambiar un video: sus resultados se
// guardan en el repositorio, así que npm run build no lo necesita. Después: npm run build:images y
// python frontend/scripts/generar-bocas.py (la boca y la cabeza de la escena salen de la imagen quieta).
import { execFileSync } from 'node:child_process';
import { stat } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const frontendDir = dirname(dirname(fileURLToPath(import.meta.url)));
const ffmpeg = process.env.FFMPEG || 'ffmpeg';
const run = args => execFileSync(ffmpeg, ['-v', 'error', '-y', ...args], { stdio: 'inherit' });

for (const name of ['doctor', 'paciente-hombre', 'paciente-mujer']) {
  const source = join(frontendDir, `src/assets/avatars/videos/${name}-hablando.mp4`);
  // Imagen quieta: el primer fotograma (boca cerrada).
  const still = join(frontendDir, `src/assets/avatars/${name}.png`);
  run(['-i', source, '-frames:v', '1', still]);
  const { size } = await stat(still);
  console.log(`${still}  ${(size / 1024).toFixed(0)} KB`);
}
