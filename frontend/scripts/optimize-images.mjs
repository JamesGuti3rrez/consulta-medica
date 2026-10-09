// Genera las versiones optimizadas de las imágenes: npm run build:images
import sharp from 'sharp';
import { stat } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const frontendDir = dirname(dirname(fileURLToPath(import.meta.url)));
const assetsDir = join(frontendDir, 'public/assets');
// La ilustración original vive fuera de public/: solo se publican sus versiones optimizadas.
const source = join(frontendDir, 'src/assets/consulta.png');
const outputs = [
  // Ilustración principal en WebP, en dos anchos para srcset.
  { file: join(assetsDir, 'consulta-1600.webp'), run: img => img.resize({ width: 1600 }).webp({ quality: 80 }) },
  { file: join(assetsDir, 'consulta-800.webp'), run: img => img.resize({ width: 800 }).webp({ quality: 78 }) },
  // Vista previa al compartir el enlace (1200x630).
  { file: join(assetsDir, 'og-image.jpg'), run: img => img.resize({ width: 1200, height: 630, fit: 'cover', position: 'centre' }).jpeg({ quality: 82, mozjpeg: true }) },
];

for (const { file, run } of outputs) {
  await run(sharp(source)).toFile(file);
  const { size } = await stat(file);
  console.log(`${file}  ${(size / 1024).toFixed(0)} KB`);
}

// Ícono para iOS a partir del favicon vectorial.
await sharp(join(assetsDir, 'favicon.svg'), { density: 384 }).resize(180, 180).png().toFile(join(assetsDir, 'apple-touch-icon.png'));
console.log(join(assetsDir, 'apple-touch-icon.png'));
