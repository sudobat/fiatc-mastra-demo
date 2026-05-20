import type { Centro } from '../types';
import { normalizar } from './text';

export const CP_PROVINCIA: Record<string, string> = {
  '01': 'ALAVA',
  '02': 'ALBACETE',
  '03': 'ALICANTE',
  '04': 'ALMERIA',
  '05': 'AVILA',
  '06': 'BADAJOZ',
  '07': 'BALEARES',
  '08': 'BARCELONA',
  '09': 'BURGOS',
  '10': 'CACERES',
  '11': 'CADIZ',
  '12': 'CASTELLON',
  '13': 'CIUDAD REAL',
  '14': 'CORDOBA',
  '15': 'A CORUNA',
  '16': 'CUENCA',
  '17': 'GIRONA',
  '18': 'GRANADA',
  '19': 'GUADALAJARA',
  '20': 'GUIPUZCOA',
  '21': 'HUELVA',
  '22': 'HUESCA',
  '23': 'JAEN',
  '24': 'LEON',
  '25': 'LLEIDA',
  '26': 'LA RIOJA',
  '27': 'LUGO',
  '28': 'MADRID',
  '29': 'MALAGA',
  '30': 'MURCIA',
  '31': 'NAVARRA',
  '32': 'OURENSE',
  '33': 'ASTURIAS',
  '34': 'PALENCIA',
  '35': 'LAS PALMAS',
  '36': 'PONTEVEDRA',
  '37': 'SALAMANCA',
  '38': 'SANTA CRUZ DE TENERIFE',
  '39': 'CANTABRIA',
  '40': 'SEGOVIA',
  '41': 'SEVILLA',
  '42': 'SORIA',
  '43': 'TARRAGONA',
  '44': 'TERUEL',
  '45': 'TOLEDO',
  '46': 'VALENCIA',
  '47': 'VALLADOLID',
  '48': 'VIZCAYA',
  '49': 'ZAMORA',
  '50': 'ZARAGOZA',
};

function centroideCentros(centros: Centro[]): [number, number] | null {
  const conCoords = centros.filter((c) => c.latitud != null && c.longitud != null);
  if (!conCoords.length) return null;
  const lat = conCoords.reduce((sum, c) => sum + (c.latitud ?? 0), 0) / conCoords.length;
  const lng = conCoords.reduce((sum, c) => sum + (c.longitud ?? 0), 0) / conCoords.length;
  return [lat, lng];
}

async function geocodePostalCode(
  cp: string,
): Promise<{ lat: number; lng: number; place: string } | null> {
  const url = `https://nominatim.openstreetmap.org/search?postalcode=${encodeURIComponent(cp)}&country=Spain&format=json&limit=1`;
  try {
    const response = await fetch(url, {
      headers: { 'User-Agent': 'mastra-demo-guia-medica/1.0' },
    });
    if (!response.ok) return null;
    const data = (await response.json()) as Array<{ lat: string; lon: string; display_name: string }>;
    const hit = data[0];
    if (!hit) return null;
    return {
      lat: Number(hit.lat),
      lng: Number(hit.lon),
      place: hit.display_name.split(',')[0]?.trim() ?? '',
    };
  } catch {
    return null;
  }
}

export interface GeolocalizarResult {
  resuelto: boolean;
  motivo?: string;
  provincia?: string;
  poblacion?: string;
  codigo_postal?: string;
  latitud?: number;
  longitud?: number;
  fuente_coords?: 'nominatim' | 'centros';
}

export async function geolocalizarTexto(
  texto: string,
  centros: Centro[],
): Promise<GeolocalizarResult> {
  const trimmed = texto.trim();
  if (!trimmed) {
    return { resuelto: false, motivo: 'Texto vacio' };
  }

  const digitos = [...trimmed].filter((c) => c >= '0' && c <= '9').join('');
  if (digitos.length === 5) {
    const prefijo = digitos.slice(0, 2);
    const provincia = CP_PROVINCIA[prefijo];
    const centrosCp = centros.filter((c) => c.codigo_postal === digitos);

    const geo = await geocodePostalCode(digitos);
    if (geo) {
      return {
        resuelto: true,
        provincia: centrosCp[0]?.provincia ?? provincia,
        poblacion: centrosCp[0]?.poblacion ?? geo.place,
        codigo_postal: digitos,
        latitud: geo.lat,
        longitud: geo.lng,
        fuente_coords: 'nominatim',
      };
    }

    const coords = centroideCentros(centrosCp);
    if (coords) {
      return {
        resuelto: true,
        provincia: centrosCp[0].provincia,
        poblacion: centrosCp[0].poblacion,
        codigo_postal: digitos,
        latitud: coords[0],
        longitud: coords[1],
        fuente_coords: 'centros',
      };
    }

    if (provincia) {
      return { resuelto: true, provincia, codigo_postal: digitos };
    }
  }

  const textoNorm = normalizar(trimmed);
  const tokens = textoNorm.split(/\s+/).filter((t) => t.length > 3);
  if (tokens.length) {
    const grupos = new Map<string, Centro[]>();
    const nombresOrig = new Map<string, string>();

    for (const centro of centros) {
      const pobNorm = normalizar(centro.poblacion);
      const list = grupos.get(pobNorm) ?? [];
      list.push(centro);
      grupos.set(pobNorm, list);
      nombresOrig.set(pobNorm, centro.poblacion);
    }

    if (grupos.has(textoNorm)) {
      const matched = grupos.get(textoNorm)!;
      const coords = centroideCentros(matched);
      return {
        resuelto: true,
        provincia: matched[0].provincia,
        poblacion: nombresOrig.get(textoNorm),
        latitud: coords?.[0],
        longitud: coords?.[1],
        fuente_coords: coords ? 'centros' : undefined,
      };
    }

    for (const [pobNorm, matched] of grupos.entries()) {
      if (tokens.every((t) => pobNorm.includes(t))) {
        const coords = centroideCentros(matched);
        return {
          resuelto: true,
          provincia: matched[0].provincia,
          poblacion: nombresOrig.get(pobNorm),
          latitud: coords?.[0],
          longitud: coords?.[1],
          fuente_coords: coords ? 'centros' : undefined,
        };
      }
    }
  }

  return {
    resuelto: false,
    motivo:
      'No se ha podido normalizar la ubicacion con los datos disponibles. Pide al usuario que indique provincia o codigo postal.',
  };
}
