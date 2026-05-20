import { createTool } from '@mastra/core/tools';
import { z } from 'zod';
import { getGuiaMedicaRepository } from '../repository';
import type { FiltroBusqueda } from '../types';

const cuadroEnum = z.enum([
  'Cuadro completo',
  'Medifiatc Start',
  'Medifiatc CORP - Colectivos - Estudiantes',
  'Medifiatc ADVANCE',
]);

export const buscarProfesionalesTool = createTool({
  id: 'buscar-profesionales',
  description:
    'Busca profesionales del cuadro medico de FIATC segun los filtros. ' +
    'Usa esta herramienta cuando el usuario quiera localizar medicos, especialistas o centros. ' +
    'Para busqueda por cercania real (ignorando limites administrativos de provincia), ' +
    'pasa cercaDeLat y cercaDeLng (obtenidas de geolocalizar); los resultados ' +
    'se ordenan por distancia ascendente y se filtran al radio indicado en radioKm (por defecto 30 km).',
  inputSchema: z.object({
    cuadro: cuadroEnum
      .optional()
      .describe(
        "Omite este campo por defecto. Solo pasa un valor especifico si el usuario ha mencionado EXPLICITAMENTE una modalidad de poliza.",
      ),
    tipoServicio: z
      .enum(['Médicos y hospitales', 'Urgencias Médicas', 'Pruebas diagnósticas'])
      .optional()
      .describe('Tipo de servicio. Por defecto: Médicos y hospitales.'),
    provincia: z
      .string()
      .optional()
      .describe('Provincia (en mayusculas, sin acentos). Se ignora si se usa cercaDeLat/lng.'),
    poblacion: z.string().optional(),
    codigoPostal: z
      .string()
      .optional()
      .describe('Se ignora si se usa cercaDeLat/lng en modo proximidad.'),
    especialidad: z.string().optional().describe('Una de listarEspecialidades()'),
    nombre: z
      .string()
      .optional()
      .describe(
        "Nombre propio real del profesional o centro (p.ej. 'Clinica Corachan'). NO uses este campo para tipos de centro ni especialidades.",
      ),
    reservaOnline: z.boolean().optional(),
    cercaDeLat: z.number().optional().describe('Latitud del punto de referencia para busqueda por proximidad.'),
    cercaDeLng: z.number().optional().describe('Longitud del punto de referencia para busqueda por proximidad.'),
    radioKm: z.number().optional().describe('Radio en km para la busqueda por proximidad (default 30).'),
  }),
  outputSchema: z.object({
    total: z.number(),
    mostrados: z.number(),
    profesionales: z.array(
      z.object({
        id: z.string(),
        nombre: z.string(),
        especialidad: z.string(),
        centro: z.string(),
        direccion: z.string(),
        poblacion: z.string(),
        provincia: z.string(),
        codigo_postal: z.string(),
        telefono: z.string().optional(),
        reserva_online: z.boolean(),
        latitud: z.number().optional(),
        longitud: z.number().optional(),
        distancia_km: z.number().optional(),
      }),
    ),
  }),
  execute: async (inputData) => {
    const repo = getGuiaMedicaRepository();
    const filtro: FiltroBusqueda = {
      cuadro: inputData.cuadro,
      tipo_servicio: inputData.tipoServicio,
      provincia: inputData.provincia,
      poblacion: inputData.poblacion,
      codigo_postal: inputData.codigoPostal,
      especialidad: inputData.especialidad,
      nombre: inputData.nombre,
      reserva_online: inputData.reservaOnline,
      cerca_de_lat: inputData.cercaDeLat,
      cerca_de_lng: inputData.cercaDeLng,
      radio_km: inputData.radioKm,
    };

    const resultados = repo.buscarProfesionales(filtro);
    const profesionales = resultados.slice(0, 20).map(({ cuadros: _cuadros, ...rest }) => rest);

    return {
      total: resultados.length,
      mostrados: profesionales.length,
      profesionales,
    };
  },
});
