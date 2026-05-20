export interface Profesional {
  id: string;
  nombre: string;
  especialidad: string;
  centro: string;
  direccion: string;
  poblacion: string;
  provincia: string;
  codigo_postal: string;
  telefono?: string;
  cuadros?: string[];
  reserva_online: boolean;
  latitud?: number;
  longitud?: number;
  distancia_km?: number;
}

export interface DoctorCentro {
  nombre: string;
  especialidades: string[];
  reserva_online: boolean;
  prof?: string;
  ref?: string;
}

export interface Centro {
  id: string;
  nombre: string;
  direccion: string;
  poblacion: string;
  provincia: string;
  codigo_postal: string;
  telefono?: string;
  horario?: string;
  especialidades: string[];
  cuadros: string[];
  latitud?: number;
  longitud?: number;
  reserva_online: boolean;
  preferente: boolean;
  profesionales: DoctorCentro[];
  consul?: string;
  fact?: string;
}

export interface FiltroBusqueda {
  cuadro?: string;
  tipo_servicio?: string;
  provincia?: string;
  poblacion?: string;
  codigo_postal?: string;
  especialidad?: string;
  nombre?: string;
  reserva_online?: boolean;
  cerca_de_lat?: number;
  cerca_de_lng?: number;
  radio_km?: number;
}

export interface GuiaMedicaData {
  profesionales?: Profesional[];
  centros: Centro[];
  especialidades: string[];
  provincias: string[];
}

export interface GuiaMedicaRepository {
  buscarProfesionales(filtro: FiltroBusqueda): Profesional[];
  obtenerCentro(idCentro: string): Centro | null;
  listarEspecialidades(): string[];
  listarProvincias(): string[];
  getCentros(): Centro[];
}
