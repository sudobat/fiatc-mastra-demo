const REEMPLAZO_UNICODE = '\uFFFD';

export function normalizar(texto: string): string {
  return texto
    .normalize('NFD')
    .toLowerCase()
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/\./g, ' ')
    .replace(/\//g, ' ')
    .replace(/-/g, ' ')
    .replaceAll(REEMPLAZO_UNICODE, '');
}

export function coincideEspecialidad(filtro: string, especialidad: string): boolean {
  const f = normalizar(filtro);
  const e = normalizar(especialidad);
  if (f === e || f.includes(e) || e.includes(f)) {
    return true;
  }

  const PREFIJO = 7;
  const tokensF = f.split(/\s+/).filter((w) => w.length >= 5).map((w) => w.slice(0, PREFIJO));
  const tokensE = e.split(/\s+/).filter((w) => w.length >= 5).map((w) => w.slice(0, PREFIJO));
  return tokensF.some((tf) => tokensE.includes(tf));
}

export function coincideNombre(filtro: string, nombreCentro: string): boolean {
  const f = normalizar(filtro);
  const n = normalizar(nombreCentro);
  if (f.includes(n) || n.includes(f)) {
    return true;
  }

  const tokens = f.split(/\s+/).filter((t) => t.length > 3);
  if (tokens.length === 0) {
    return f.includes(n);
  }

  for (const t of tokens) {
    if (n.includes(t)) continue;
    if (t.length >= 4 && n.includes(t.slice(0, 4))) continue;
    return false;
  }
  return true;
}

export function haversineKm(lat1: number, lng1: number, lat2: number, lng2: number): number {
  const R = 6371;
  const a1 = (lat1 * Math.PI) / 180;
  const a2 = (lat2 * Math.PI) / 180;
  const da = ((lat2 - lat1) * Math.PI) / 180;
  const doLng = ((lng2 - lng1) * Math.PI) / 180;
  const h =
    Math.sin(da / 2) ** 2 + Math.cos(a1) * Math.cos(a2) * Math.sin(doLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}

export function distanciaEdicion(a: string, b: string): number {
  if (a.length > 20 || b.length > 20) return 999;
  const m = a.length;
  const n = b.length;
  const dp = Array.from({ length: n + 1 }, (_, j) => j);
  for (let i = 1; i <= m; i++) {
    let prev = dp[0];
    dp[0] = i;
    for (let j = 1; j <= n; j++) {
      const temp = dp[j];
      dp[j] =
        a[i - 1] === b[j - 1] ? prev : 1 + Math.min(prev, dp[j], dp[j - 1]);
      prev = temp;
    }
  }
  return dp[n];
}
