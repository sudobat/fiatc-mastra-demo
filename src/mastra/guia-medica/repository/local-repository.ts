import { readFileSync } from 'node:fs';
import type {
  Centro,
  DoctorCentro,
  FiltroBusqueda,
  GuiaMedicaData,
  GuiaMedicaRepository,
  Profesional,
} from '../types';
import {
  coincideEspecialidad,
  coincideNombre,
  haversineKm,
  normalizar,
} from '../utils/text';
import { resolveGuiaMedicaDataPath } from '../utils/resolve-data-path';

function dedupCentros(centros: Centro[]): Centro[] {
  const vistos = new Map<string, Centro>();

  for (const c of centros) {
    const clave =
      c.latitud != null && c.longitud != null
        ? `c:${c.latitud.toFixed(5)}:${c.longitud.toFixed(5)}`
        : `n:${normalizar(c.nombre)}:${normalizar(c.direccion ?? '')}`;

    const existente = vistos.get(clave);
    if (existente) {
      for (const esp of c.especialidades) {
        if (!existente.especialidades.includes(esp)) {
          existente.especialidades.push(esp);
        }
      }
      if (c.profesionales.length && !existente.profesionales.length) {
        existente.profesionales.push(...c.profesionales);
      }
      if (c.reserva_online) {
        existente.reserva_online = true;
      }
    } else {
      vistos.set(clave, {
        ...c,
        especialidades: [...c.especialidades],
        profesionales: [...c.profesionales],
      });
    }
  }

  return [...vistos.values()];
}

function centroideCentros(centros: Centro[]): [number, number] | null {
  const conCoords = centros.filter((c) => c.latitud != null && c.longitud != null);
  if (!conCoords.length) return null;
  const lat = conCoords.reduce((sum, c) => sum + (c.latitud ?? 0), 0) / conCoords.length;
  const lng = conCoords.reduce((sum, c) => sum + (c.longitud ?? 0), 0) / conCoords.length;
  return [lat, lng];
}

export class LocalFileGuiaMedicaRepository implements GuiaMedicaRepository {
  private readonly profesionales: Profesional[];
  private readonly centros: Map<string, Centro>;
  private readonly especialidades: string[];
  private readonly provincias: string[];
  private readonly profsPorLatLng: Map<string, DoctorCentro[]>;
  private readonly reservaPorLatLng: Map<string, boolean>;

  constructor(rutaFichero?: string) {
    const path = resolveGuiaMedicaDataPath(rutaFichero);

    const datos = JSON.parse(readFileSync(path, 'utf-8')) as GuiaMedicaData;
    this.profesionales = (datos.profesionales ?? []).map((p) => ({
      ...p,
      reserva_online: p.reserva_online ?? false,
    }));
    this.centros = new Map(
      (datos.centros ?? []).map((c) => [
        c.id,
        {
          ...c,
          cuadros: c.cuadros ?? [],
          especialidades: c.especialidades ?? [],
          profesionales: c.profesionales ?? [],
          reserva_online: c.reserva_online ?? false,
          preferente: c.preferente ?? false,
        },
      ]),
    );
    this.especialidades = datos.especialidades ?? [];
    this.provincias = datos.provincias ?? [];

    const merge = new Map<string, Map<string, DoctorCentro>>();
    for (const c of this.centros.values()) {
      if (c.latitud != null && c.longitud != null && c.profesionales.length) {
        const key = `${c.latitud.toFixed(5)}:${c.longitud.toFixed(5)}`;
        const bucket = merge.get(key) ?? new Map<string, DoctorCentro>();
        for (const p of c.profesionales) {
          const existing = bucket.get(p.nombre);
          if (!existing) {
            bucket.set(p.nombre, { ...p });
          } else if (p.reserva_online && !existing.reserva_online) {
            bucket.set(p.nombre, { ...existing, reserva_online: true });
          }
        }
        merge.set(key, bucket);
      }
    }

    this.profsPorLatLng = new Map(
      [...merge.entries()].map(([key, profs]) => [key, [...profs.values()]]),
    );
    this.reservaPorLatLng = new Map(
      [...this.profsPorLatLng.entries()].map(([key, profs]) => [
        key,
        profs.some((p) => p.reserva_online),
      ]),
    );
  }

  getCentros(): Centro[] {
    return [...this.centros.values()];
  }

  buscarProfesionales(filtro: FiltroBusqueda): Profesional[] {
    if (this.profesionales.length) {
      return this.filtrarProfesionales(filtro);
    }
    return this.buscarEnCentros(filtro);
  }

  private filtrarProfesionales(filtro: FiltroBusqueda): Profesional[] {
    let resultado = [...this.profesionales];

    if (filtro.provincia) {
      resultado = resultado.filter(
        (p) => p.provincia.toLowerCase() === filtro.provincia!.toLowerCase(),
      );
    }
    if (filtro.poblacion) {
      resultado = resultado.filter(
        (p) => p.poblacion.toLowerCase() === filtro.poblacion!.toLowerCase(),
      );
    }
    if (filtro.codigo_postal) {
      resultado = resultado.filter((p) => p.codigo_postal === filtro.codigo_postal);
    }
    if (filtro.especialidad) {
      resultado = resultado.filter((p) =>
        coincideEspecialidad(filtro.especialidad!, p.especialidad),
      );
    }
    if (filtro.nombre) {
      resultado = resultado.filter(
        (p) =>
          coincideNombre(filtro.nombre!, p.nombre) ||
          coincideNombre(filtro.nombre!, p.centro),
      );
    }
    if (filtro.reserva_online === true) {
      resultado = resultado.filter((p) => p.reserva_online);
    }
    if (filtro.cuadro && filtro.cuadro.toLowerCase() !== 'cuadro completo') {
      resultado = resultado.filter((p) => (p.cuadros ?? []).includes(filtro.cuadro!));
    }

    return resultado;
  }

  private buscarEnCentros(filtro: FiltroBusqueda): Profesional[] {
    let centros = [...this.centros.values()];
    const modoProximidad =
      filtro.cerca_de_lat != null && filtro.cerca_de_lng != null;

    if (filtro.provincia && !modoProximidad) {
      centros = centros.filter(
        (c) => c.provincia.toLowerCase() === filtro.provincia!.toLowerCase(),
      );
    }
    if (filtro.poblacion) {
      const p = normalizar(filtro.poblacion);
      centros = centros.filter((c) => normalizar(c.poblacion).includes(p));
    }
    if (filtro.codigo_postal && !modoProximidad) {
      centros = centros.filter((c) => c.codigo_postal === filtro.codigo_postal);
    }
    if (filtro.nombre) {
      centros = centros.filter((c) => coincideNombre(filtro.nombre!, c.nombre));
    }

    centros = dedupCentros(centros);

    const distancias = new Map<string, number>();
    if (modoProximidad) {
      const radio = filtro.radio_km ?? 30;
      const conCoords: Centro[] = [];
      for (const c of centros) {
        if (c.latitud != null && c.longitud != null) {
          const d = haversineKm(
            filtro.cerca_de_lat!,
            filtro.cerca_de_lng!,
            c.latitud,
            c.longitud,
          );
          if (d <= radio) {
            distancias.set(c.id, d);
            conCoords.push(c);
          }
        }
      }
      const cpRef = filtro.codigo_postal ?? '';
      conCoords.sort(
        (a, b) =>
          Number(a.codigo_postal !== cpRef) - Number(b.codigo_postal !== cpRef) ||
          (distancias.get(a.id)! - distancias.get(b.id)!),
      );
      centros = conCoords;
    }

    const resultado: Profesional[] = [];
    for (const centro of centros) {
      let tieneReserva = centro.reserva_online;
      if (!tieneReserva && centro.latitud != null && centro.longitud != null) {
        const key = `${centro.latitud.toFixed(5)}:${centro.longitud.toFixed(5)}`;
        tieneReserva = this.reservaPorLatLng.get(key) ?? false;
      }

      if (filtro.reserva_online === true && !tieneReserva) {
        continue;
      }

      const especialidades = centro.especialidades.length ? centro.especialidades : [''];
      for (const esp of especialidades) {
        if (filtro.especialidad && !coincideEspecialidad(filtro.especialidad, esp)) {
          continue;
        }
        resultado.push({
          id: centro.id,
          nombre: centro.nombre,
          especialidad: esp,
          centro: centro.nombre,
          direccion: centro.direccion,
          poblacion: centro.poblacion,
          provincia: centro.provincia,
          codigo_postal: centro.codigo_postal,
          telefono: centro.telefono ?? '',
          cuadros: centro.cuadros,
          reserva_online: tieneReserva,
          latitud: centro.latitud,
          longitud: centro.longitud,
          distancia_km:
            distancias.has(centro.id) ?
              Math.round(distancias.get(centro.id)! * 10) / 10
            : undefined,
        });
      }
    }

    return resultado;
  }

  obtenerCentro(idCentro: string): Centro | null {
    const c = this.centros.get(idCentro);
    if (!c) return null;
    if (c.latitud != null && c.longitud != null) {
      const key = `${c.latitud.toFixed(5)}:${c.longitud.toFixed(5)}`;
      const profs = this.profsPorLatLng.get(key);
      if (profs) {
        return { ...c, profesionales: profs };
      }
    }
    return c;
  }

  listarEspecialidades(): string[] {
    return [...this.especialidades];
  }

  listarProvincias(): string[] {
    return [...this.provincias];
  }
}

export function resolveDefaultDataPath(): string | undefined {
  return process.env.GUIA_MEDICA_FICHERO;
}
