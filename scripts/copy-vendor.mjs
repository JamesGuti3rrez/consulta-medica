// Copia a public/vendor/ las librerías del navegador instaladas con npm (se ejecuta solo tras npm install).
import { copyFile, mkdir } from 'node:fs/promises';

const files = [
  ['node_modules/@supabase/supabase-js/dist/umd/supabase.js', 'public/vendor/supabase.js'],
];

await mkdir('public/vendor', { recursive: true });
for (const [source, target] of files) {
  await copyFile(source, target);
  console.log(`${source} -> ${target}`);
}
