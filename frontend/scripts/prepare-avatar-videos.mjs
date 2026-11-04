// Prepara los videos de la escena a partir de los de LivePortrait: node frontend/scripts/prepare-avatar-videos.mjs
// Necesita ffmpeg (en el PATH o en la variable FFMPEG). Se ejecuta solo al cambiar un video: sus resultados se
// guardan en el repositorio, así que npm run build no lo necesita.
import { execFileSync } from 'node:child_process';
import { stat } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const frontendDir = dirname(dirname(fileURLToPath(import.meta.url)));
const ffmpeg = process.env.FFMPEG || 'ffmpeg';
const run = args => execFileSync(ffmpeg, ['-v', 'error', '-y', ...args], { stdio: 'inherit' });

for (const name of ['doctor', 'paciente-hombre', 'paciente-mujer']) {
  const source = join(frontendDir, `src/assets/avatars/videos/${name}-hablando.mp4`);
  // Imagen quieta: el primer fotograma (boca cerrada). Así coincide al píxel con el video y el cambio no se nota.
  const still = join(frontendDir, `src/assets/avatars/${name}.png`);
  run(['-i', source, '-frames:v', '1', still]);
  // Bucle de ida y vuelta: el video termina con la boca abierta y saltaría al volver al inicio. La vuelta
  // omite el primer y el último fotograma para no repetirlos (los videos tienen 75: 5,36 s a 14 fps). Sin audio
  // y con el índice al principio, para que empiece a reproducirse antes de descargarse entero.
  const loop = join(frontendDir, `public/assets/avatars/${name}-hablando.mp4`);
  run(['-i', source, '-filter_complex',
    '[0:v]split[ida][v];[v]reverse,trim=start_frame=1:end_frame=74,setpts=PTS-STARTPTS[vuelta];[ida][vuelta]concat=n=2:v=1[out]',
    '-map', '[out]', '-an', '-c:v', 'libx264', '-crf', '22', '-preset', 'slow', '-pix_fmt', 'yuv420p',
    '-movflags', '+faststart', loop]);
  for (const file of [still, loop]) {
    const { size } = await stat(file);
    console.log(`${file}  ${(size / 1024).toFixed(0)} KB`);
  }
}
