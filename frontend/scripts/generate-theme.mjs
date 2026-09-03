/**
 * Génère src/theme/generated-color.css depuis la couleur source.
 *
 * Le fichier produit est versionné : le build n'a pas besoin de recalculer les
 * palettes, et une revue de code voit exactement ce qui change quand la couleur
 * source bouge.
 *
 * Le passage par esbuild n'est pas décoratif : `@material/material-color-utilities`
 * publie des imports sans extension, que le résolveur ESM de Node refuse et
 * qu'un bundler accepte. On bundle donc en mémoire avant d'exécuter.
 *
 *   npm run theme
 */
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { pathToFileURL, fileURLToPath } from 'node:url';
import { build } from 'esbuild';

const here = dirname(fileURLToPath(import.meta.url));
const scratch = mkdtempSync(join(tmpdir(), 'gl-theme-'));

try {
  const bundled = join(scratch, 'color.mjs');
  await build({
    entryPoints: [join(here, '..', 'src', 'theme', 'color.ts')],
    outfile: bundled,
    bundle: true,
    format: 'esm',
    platform: 'node',
    logLevel: 'error',
  });

  const { buildThemeCss } = await import(pathToFileURL(bundled).href);
  const out = join(here, '..', 'src', 'theme', 'generated-color.css');
  writeFileSync(out, buildThemeCss(), 'utf8');
  console.log(`écrit ${out}`);
} finally {
  rmSync(scratch, { recursive: true, force: true });
}
