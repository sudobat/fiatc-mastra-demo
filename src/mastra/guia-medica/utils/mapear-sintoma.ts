import sintomaMap from '../data/sintoma-a-especialidad.json';
import { distanciaEdicion } from '../utils/text';

const SINTOMA_A_ESPECIALIDAD = sintomaMap as Record<string, string[]>;

export interface MapearSintomaResult {
  especialidades: string[];
  confianza: 'alta' | 'media' | 'baja';
  metodo?: 'lookup' | 'lookup_parcial' | 'fuzzy' | 'fallback';
  aviso?: string;
}

export function mapearSintoma(texto: string): MapearSintomaResult {
  const normalized = texto.toLowerCase().trim();
  if (!normalized) {
    return { especialidades: [], confianza: 'baja' };
  }

  if (SINTOMA_A_ESPECIALIDAD[normalized]) {
    return {
      especialidades: SINTOMA_A_ESPECIALIDAD[normalized],
      confianza: 'alta',
      metodo: 'lookup',
    };
  }

  const candidatos = new Map<string, number>();
  for (const [clave, especialidades] of Object.entries(SINTOMA_A_ESPECIALIDAD)) {
    if (clave.includes(normalized) || normalized.includes(clave)) {
      for (const esp of especialidades) {
        candidatos.set(esp, (candidatos.get(esp) ?? 0) + 1);
      }
    }
  }

  if (candidatos.size) {
    const ordenadas = [...candidatos.entries()].sort((a, b) => b[1] - a[1]);
    return {
      especialidades: ordenadas.map(([esp]) => esp),
      confianza: 'media',
      metodo: 'lookup_parcial',
    };
  }

  const palabras = normalized.split(/\s+/).filter((w) => w.length >= 5);
  let mejorDist = 3;
  let mejorEsps: string[] = [];

  for (const [clave, especialidades] of Object.entries(SINTOMA_A_ESPECIALIDAD)) {
    for (const palabra of palabras) {
      const d = distanciaEdicion(palabra, clave);
      if (d < mejorDist) {
        mejorDist = d;
        mejorEsps = [...especialidades];
      } else if (d === mejorDist) {
        for (const esp of especialidades) {
          if (!mejorEsps.includes(esp)) {
            mejorEsps.push(esp);
          }
        }
      }
    }
  }

  if (mejorEsps.length) {
    return {
      especialidades: mejorEsps,
      confianza: 'media',
      metodo: 'fuzzy',
    };
  }

  return {
    especialidades: ['Medicina General'],
    confianza: 'baja',
    metodo: 'fallback',
    aviso:
      'No se ha encontrado correspondencia clara. Se sugiere Medicina General como punto de entrada.',
  };
}
