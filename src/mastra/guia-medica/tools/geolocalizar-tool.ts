import { createTool } from '@mastra/core/tools';
import { z } from 'zod';
import { getGuiaMedicaRepository } from '../repository';
import { geolocalizarTexto } from '../utils/geolocalizar';

export const geolocalizarTool = createTool({
  id: 'geolocalizar',
  description:
    'Normaliza una ubicacion expresada en lenguaje natural (nombre de poblacion, ' +
    'codigo postal o frase como "cerca de Barcelona") a provincia, poblacion y ' +
    'coordenadas (latitud/longitud). Las coordenadas devueltas se pueden pasar a ' +
    'buscarProfesionales (campos cercaDeLat, cercaDeLng) para busqueda por cercania real.',
  inputSchema: z.object({
    texto: z.string().describe('Texto libre con la ubicacion o codigo postal'),
  }),
  outputSchema: z.object({
    resuelto: z.boolean(),
    motivo: z.string().optional(),
    provincia: z.string().optional(),
    poblacion: z.string().optional(),
    codigo_postal: z.string().optional(),
    latitud: z.number().optional(),
    longitud: z.number().optional(),
    fuente_coords: z.enum(['nominatim', 'centros']).optional(),
  }),
  execute: async (inputData) => {
    const repo = getGuiaMedicaRepository();
    return geolocalizarTexto(inputData.texto, repo.getCentros());
  },
});
