import { cp, mkdir, readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { hostingConfigScript } from './hosting-config.mjs';

const root = fileURLToPath(new URL('../', import.meta.url));
const dist = path.join(root, 'dist');
// Solo copiar archivos públicos del build; nunca .env, fuentes ni node_modules.
await readFile(path.join(dist, 'index.html'));
for (const cloud of ['aws', 'azure']) {
  const destination = path.join(dist, cloud);
  await mkdir(destination, { recursive: true });
  for (const file of ['index.html', 'favicon.svg']) {
    await cp(path.join(dist, file), path.join(destination, file));
  }
  await cp(path.join(dist, 'assets'), path.join(destination, 'assets'), { recursive: true });
  await writeFile(path.join(destination, 'config.js'), hostingConfigScript(cloud), 'utf8');
  console.log(`Hosting ${cloud}: ${path.relative(root, destination)} (modo real)`);
}
