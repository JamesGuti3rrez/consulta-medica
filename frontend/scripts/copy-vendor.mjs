// Copia a public/vendor/ las librerías del navegador instaladas con npm (se ejecuta solo tras npm install).
import { copyFile, mkdir } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const frontendDir = dirname(dirname(fileURLToPath(import.meta.url)));
const repositoryDir = dirname(frontendDir);

const files = [
  [
    join(repositoryDir, 'node_modules/@supabase/supabase-js/dist/umd/supabase.js'),
    join(frontendDir, 'public/vendor/supabase.js'),
  ],
];

await mkdir(join(frontendDir, 'public/vendor'), { recursive: true });
for (const [source, target] of files) {
  await copyFile(source, target);
  console.log(`${source} -> ${target}`);
}
