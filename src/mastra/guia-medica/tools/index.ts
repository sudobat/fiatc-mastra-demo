export { buscarProfesionalesTool } from './buscar-profesionales-tool';
export { geolocalizarTool } from './geolocalizar-tool';
export { listarEspecialidadesTool } from './listar-especialidades-tool';
export { mapearSintomaTool } from './mapear-sintoma-tool';
export { obtenerCentroTool } from './obtener-centro-tool';

import { buscarProfesionalesTool } from './buscar-profesionales-tool';
import { geolocalizarTool } from './geolocalizar-tool';
import { listarEspecialidadesTool } from './listar-especialidades-tool';
import { mapearSintomaTool } from './mapear-sintoma-tool';
import { obtenerCentroTool } from './obtener-centro-tool';

export const guiaMedicaTools = {
  buscarProfesionales: buscarProfesionalesTool,
  geolocalizar: geolocalizarTool,
  mapearSintoma: mapearSintomaTool,
  listarEspecialidades: listarEspecialidadesTool,
  obtenerCentro: obtenerCentroTool,
};
