import { createTool } from '@mastra/core/tools';
import { z } from 'zod';
import { getGuiaMedicaRepository } from '../repository';

export const obtenerCentroTool = createTool({
  id: 'obtener-centro',
  description:
    'Devuelve la ficha completa de un centro medico (direccion, telefono, horario, ' +
    'especialidades). Se usa cuando el usuario pide detalles de un centro concreto.',
  inputSchema: z.object({
    idCentro: z.string().describe('Identificador del centro'),
  }),
  outputSchema: z.object({
    error: z.string().optional(),
    id: z.string().optional(),
    nombre: z.string().optional(),
    direccion: z.string().optional(),
    poblacion: z.string().optional(),
    provincia: z.string().optional(),
    codigo_postal: z.string().optional(),
    telefono: z.string().optional(),
    horario: z.string().optional(),
    especialidades: z.array(z.string()).optional(),
    latitud: z.number().optional(),
    longitud: z.number().optional(),
    reserva_online: z.boolean().optional(),
    preferente: z.boolean().optional(),
    profesionales: z
      .array(
        z.object({
          nombre: z.string(),
          especialidades: z.array(z.string()),
          reserva_online: z.boolean(),
        }),
      )
      .optional(),
  }),
  execute: async (inputData) => {
    const repo = getGuiaMedicaRepository();
    const centro = repo.obtenerCentro(inputData.idCentro);
    if (!centro) {
      return { error: `No se ha encontrado el centro con id '${inputData.idCentro}'.` };
    }
    return centro;
  },
});
