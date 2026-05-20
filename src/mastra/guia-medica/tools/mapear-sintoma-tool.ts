import { createTool } from '@mastra/core/tools';
import { z } from 'zod';
import { mapearSintoma } from '../utils/mapear-sintoma';

export const mapearSintomaTool = createTool({
  id: 'mapear-sintoma',
  description:
    'Mapea un sintoma, motivo de consulta o nombre de especialista expresado en lenguaje natural ' +
    'a una o varias especialidades del cuadro medico FIATC. Usala antes de buscarProfesionales ' +
    'cuando el usuario describa un sintoma o mencione un tipo de especialista.',
  inputSchema: z.object({
    texto: z.string().describe('Descripcion libre del sintoma o motivo de consulta'),
  }),
  outputSchema: z.object({
    especialidades: z.array(z.string()),
    confianza: z.enum(['alta', 'media', 'baja']),
    metodo: z.enum(['lookup', 'lookup_parcial', 'fuzzy', 'fallback']).optional(),
    aviso: z.string().optional(),
  }),
  execute: async (inputData) => mapearSintoma(inputData.texto),
});
