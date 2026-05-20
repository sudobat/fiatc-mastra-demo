import type { GuiaMedicaRepository } from '../types';
import { LocalFileGuiaMedicaRepository, resolveDefaultDataPath } from './local-repository';

let instance: GuiaMedicaRepository | null = null;

export function getGuiaMedicaRepository(): GuiaMedicaRepository {
  if (!instance) {
    const backend = process.env.GUIA_MEDICA_BACKEND ?? 'local';
    if (backend !== 'local') {
      throw new Error(
        'GUIA_MEDICA_BACKEND=api no esta implementado en Mastra. Usa GUIA_MEDICA_BACKEND=local.',
      );
    }
    instance = new LocalFileGuiaMedicaRepository(resolveDefaultDataPath());
  }
  return instance;
}

export function resetGuiaMedicaRepository(): void {
  instance = null;
}
