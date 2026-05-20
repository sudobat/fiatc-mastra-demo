import { existsSync } from 'node:fs';
import { dirname, isAbsolute, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const moduleDir = dirname(fileURLToPath(import.meta.url));

function findProjectRoot(): string {
  const starts = new Set<string>([
    process.cwd(),
    moduleDir,
    process.env.INIT_CWD ?? '',
    process.env.PWD ?? '',
  ]);

  for (const start of starts) {
    if (!start) continue;
    let dir = start;
    for (let i = 0; i < 12; i++) {
      if (
        existsSync(join(dir, 'package.json')) &&
        existsSync(join(dir, 'src/mastra/index.ts'))
      ) {
        return dir;
      }
      const parent = dirname(dir);
      if (parent === dir) break;
      dir = parent;
    }
  }

  return process.cwd();
}

export function resolveGuiaMedicaDataPath(configuredPath?: string): string {
  const projectRoot = findProjectRoot();
  const envPath = configuredPath ?? process.env.GUIA_MEDICA_FICHERO;

  const candidates: string[] = [];

  if (envPath) {
    if (isAbsolute(envPath)) {
      candidates.push(envPath);
    } else {
      candidates.push(resolve(projectRoot, envPath));
      candidates.push(resolve(process.cwd(), envPath));
    }
  }

  candidates.push(
    resolve(
      projectRoot,
      'src/mastra/workspaces/ai_guia_medica/data/cuadro_medico_sample.json',
    ),
    resolve(projectRoot, 'src/mastra/guia-medica/data/cuadro-medico-sample.json'),
    resolve(moduleDir, '../data/cuadro-medico-sample.json'),
  );

  const uniqueCandidates = [...new Set(candidates)];
  const found = uniqueCandidates.find((candidate) => existsSync(candidate));

  if (!found) {
    throw new Error(
      `No se encuentra el fichero del cuadro medico. Rutas probadas: ${uniqueCandidates.join(', ')}`,
    );
  }

  return found;
}
