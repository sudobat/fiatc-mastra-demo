import { createTool } from '@mastra/core/tools';
import { z } from 'zod';
import { getGuiaMedicaRepository } from '../repository';

export const listarEspecialidadesTool = createTool({
  id: 'listar-especialidades',
  description:
    'Devuelve la lista cerrada de especialidades validas en el cuadro medico. ' +
    'Usala cuando necesites validar el nombre exacto de una especialidad.',
  inputSchema: z.object({}),
  outputSchema: z.object({
    especialidades: z.array(z.string()),
  }),
  execute: async () => {
    const repo = getGuiaMedicaRepository();
    return { especialidades: repo.listarEspecialidades() };
  },
});
