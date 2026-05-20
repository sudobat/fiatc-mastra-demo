"""
Enriquecimiento rápido del cuadro médico con profesionales individuales.

Actualiza el cuadro_medico_sample.json existente añadiendo la lista de
profesionales (doctores) a cada centro, SIN necesidad de re-descargar las
28k fichas de centro (el scraping completo tarda decenas de minutos).

Estrategia (~300 peticiones en lugar de ~28.000):
  1. Descargar los 47 sitemaps de provincia.
  2. Separar URLs de doctores individuales (slugs /dr-*, /dra-*).
  3. Construir mapa código_especialidad → nombre (1 petición/código único, ~200 req).
  4. Para cada consul con doctores, localizar su centro en el JSON existente
     buscando 1 URL de centro del mismo consul para extraer lat/lng + consul.
  5. Actualizar el JSON con profesionales y reserva_online.

Uso:
  cd backend
  python ../scraping/enriquecer_doctores.py
"""
from __future__ import annotations

import asyncio
import json
import re
import time
from collections import defaultdict
from pathlib import Path

import httpx

BASE_URL = "https://guiamedica.fiatc.es"
HEADERS = {"User-Agent": "FIATC-POC-Scraper/1.0 (poc-interno-fiatc)"}
CONCURRENCIA = 8
DELAY_LOTE = 0.2
TIMEOUT = 15
REINTENTOS = 2
MAX_DOCTORES_POR_CENTRO = 100

PROVINCIAS_SLUGS = [
    "alava", "albacete", "alicante", "almeria", "asturias", "avila", "badajoz",
    "baleares", "barcelona", "burgos", "caceres", "cadiz", "cantabria", "castellon",
    "ciudad-real", "cordoba", "cuenca", "girona", "granada", "guadalajara",
    "guipuzcoa", "huelva", "huesca", "jaen", "la-rioja", "las-palmas", "leon",
    "lleida", "lugo", "madrid", "malaga", "murcia", "navarra", "palencia",
    "pontevedra", "salamanca", "segovia", "sevilla", "soria", "tarragona",
    "teruel", "toledo", "valencia", "valladolid", "vizcaya", "zamora", "zaragoza",
]

DESTINO = Path(__file__).parent.parent / "data" / "cuadro_medico_sample.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def slug_a_nombre_doctor(slug: str) -> str:
    if slug.startswith("dra-"):
        prefijo, resto = "Dra.", slug[4:]
    elif slug.startswith("dr-"):
        prefijo, resto = "Dr.", slug[3:]
    else:
        return slug.replace("-", " ").title()
    # Eliminar sufijos numéricos de desambiguación al final (ej: "dr-garcia-1")
    resto = re.sub(r"-\d+$", "", resto)
    return f"{prefijo} {resto.replace('-', ' ').title()}"


def extraer_componentes(url: str) -> tuple[str, str, int] | tuple[None, None, None]:
    segmento = url.rstrip("/").rsplit("/", 1)[-1]
    m = re.match(r"^(.+?)(\d{18})$", segmento)
    if not m:
        return None, None, None
    slug = m.group(1).rstrip("-")
    numero = m.group(2)
    consul = numero[10:15]
    codi_esp = int(numero[15:18])
    return slug, consul, codi_esp


async def fetch(client: httpx.AsyncClient, url: str, sem: asyncio.Semaphore) -> str | None:
    async with sem:
        for intento in range(REINTENTOS + 1):
            try:
                r = await client.get(url, timeout=TIMEOUT, follow_redirects=True)
                await asyncio.sleep(DELAY_LOTE)
                if r.status_code == 200:
                    texto = r.text
                    if "â€" in texto or "Ã" in texto or "�" in texto:
                        try:
                            alt = r.content.decode("windows-1252")
                            if "�" not in alt:
                                return alt
                        except (UnicodeDecodeError, LookupError):
                            pass
                    return texto
                if r.status_code in (404, 410):
                    return None
            except httpx.HTTPError as exc:
                if intento < REINTENTOS:
                    await asyncio.sleep(1.5 * (intento + 1))
                else:
                    print(f"  [!] {url}: {exc}")
    return None


def extraer_json_ficha(html: str) -> dict | None:
    m = re.search(r'\{[^{}]*"codi_postal"[^{}]*\}', html)
    if not m:
        return None
    try:
        return json.loads(m.group())
    except json.JSONDecodeError:
        return None


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    import math
    R = 6371.0
    da = math.radians(lat2 - lat1)
    do = math.radians(lng2 - lng1)
    a = math.sin(da / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(do / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


# ---------------------------------------------------------------------------
# Lógica principal
# ---------------------------------------------------------------------------

async def ejecutar() -> None:
    sem = asyncio.Semaphore(CONCURRENCIA)

    # Cargar JSON existente
    print("Cargando JSON existente...")
    datos_json = json.loads(DESTINO.read_text(encoding="utf-8"))
    centros_existentes = datos_json["centros"]
    print(f"  {len(centros_existentes):,} centros cargados")

    # Índice lat/lng → lista de índices (varios centros pueden compartir coordenadas)
    indice_latlng: dict[tuple[float, float], list[int]] = defaultdict(list)
    for i, c in enumerate(centros_existentes):
        if c.get("latitud") and c.get("longitud"):
            clave = (round(c["latitud"], 4), round(c["longitud"], 4))
            indice_latlng[clave].append(i)

    async with httpx.AsyncClient(headers=HEADERS) as client:

        # Paso 1: Descargar sitemaps
        print("\nPaso 1 — Descargando sitemaps...")
        todas_urls: list[str] = []
        for slug in PROVINCIAS_SLUGS:
            url = f"{BASE_URL}/sitemap_provincia_{slug}-es.xml"
            r = await client.get(url, timeout=TIMEOUT, follow_redirects=True)
            if r.status_code == 200:
                urls = re.findall(r"<loc>(.*?)</loc>", r.text)
                todas_urls.extend(urls)
        print(f"  {len(todas_urls):,} URLs totales")

        # Paso 2: Separar doctores de centros; indexar por consul
        print("\nPaso 2 — Indexando doctores y centros por consul...")
        doctores_por_consul: dict[str, dict[str, set[int]]] = defaultdict(lambda: defaultdict(set))
        centros_url_por_consul: dict[str, str] = {}    # consul → primera URL de centro
        ejemplo_por_codigo: dict[int, str] = {}

        for url in todas_urls:
            slug, consul, codi_esp = extraer_componentes(url)
            if slug is None:
                continue
            if slug.startswith("dr-") or slug.startswith("dra-"):
                doctores_por_consul[consul][slug].add(codi_esp)
                if codi_esp not in ejemplo_por_codigo:
                    ejemplo_por_codigo[codi_esp] = url
            else:
                if consul not in centros_url_por_consul:
                    centros_url_por_consul[consul] = url
                if codi_esp not in ejemplo_por_codigo:
                    ejemplo_por_codigo[codi_esp] = url

        total_doctores = sum(len(d) for d in doctores_por_consul.values())
        consuls_con_doctores = set(doctores_por_consul.keys())
        print(f"  Doctores únicos:           {total_doctores:,}")
        print(f"  Cónsules con doctores:     {len(consuls_con_doctores):,}")
        print(f"  Códigos de especialidad:   {len(ejemplo_por_codigo)}")

        # Paso 3: Mapa especialidad
        print(f"\nPaso 3 — Mapeando {len(ejemplo_por_codigo)} especialidades...")
        mapa_especialidades: dict[int, str] = {}
        codigos = list(ejemplo_por_codigo.keys())
        urls_esp = [ejemplo_por_codigo[c] for c in codigos]
        resultados = await asyncio.gather(
            *[fetch(client, u, sem) for u in urls_esp], return_exceptions=True
        )
        for codigo, html in zip(codigos, resultados):
            if isinstance(html, Exception) or not html:
                continue
            datos = extraer_json_ficha(html)
            if datos and datos.get("lit_esp"):
                mapa_especialidades[codigo] = datos["lit_esp"].strip().title()
        print(f"  Mapeadas: {len(mapa_especialidades)}/{len(ejemplo_por_codigo)}")

        # Paso 4: Obtener lat/lng de un centro por cada consul con doctores
        # (necesario para vincular consul → centro en el JSON existente)
        print(f"\nPaso 4 — Localizando {len(consuls_con_doctores):,} cónsules con doctores...")
        consul_a_idx: dict[str, list[int]] = {}
        consul_a_ccita: dict[str, bool] = {}   # consul → reserva_online real del centro

        consuls_a_resolver = [c for c in consuls_con_doctores if c in centros_url_por_consul]
        print(f"  Cónsules con URL de centro disponible: {len(consuls_a_resolver):,}")

        LOTE = 200
        for i in range(0, len(consuls_a_resolver), LOTE):
            lote_consuls = consuls_a_resolver[i: i + LOTE]
            lote_urls = [centros_url_por_consul[c] for c in lote_consuls]
            lote_res = await asyncio.gather(
                *[fetch(client, u, sem) for u in lote_urls], return_exceptions=True
            )
            for consul, html in zip(lote_consuls, lote_res):
                if isinstance(html, Exception) or not html:
                    continue
                datos = extraer_json_ficha(html)
                if not datos:
                    continue
                lat = float(datos["lat"]) if datos.get("lat") else None
                lng = float(datos["lng"]) if datos.get("lng") else None
                consul_a_ccita[consul] = datos.get("ccita", "0") == "1"
                if lat is None or lng is None:
                    continue
                clave = (round(lat, 4), round(lng, 4))
                if clave in indice_latlng:
                    consul_a_idx[consul] = indice_latlng[clave]
                else:
                    # Buscar la clave más cercana (tolerancia 50 m)
                    mejor_d, mejor_indices = float("inf"), []
                    for (clat, clng), indices in indice_latlng.items():
                        d = _haversine_km(lat, lng, clat, clng)
                        if d < mejor_d:
                            mejor_d, mejor_indices = d, indices
                    if mejor_d < 0.05 and mejor_indices:
                        consul_a_idx[consul] = mejor_indices
            procesados = min(i + LOTE, len(consuls_a_resolver))
            print(f"  Procesados: {procesados:,}/{len(consuls_a_resolver):,}", end="\r")
        print()
        print(f"  Cónsules vinculados a centros: {len(consul_a_idx):,}")

        # Paso 5: Actualizar centros con profesionales
        print("\nPaso 5 — Actualizando centros con profesionales...")
        centros_actualizados = 0

        for consul, indices_centro in consul_a_idx.items():
            ccita = consul_a_ccita.get(consul, False)

            profesionales_lista: list[dict] = []
            for slug_doc, esp_set in sorted(doctores_por_consul[consul].items()):
                nombre_doc = slug_a_nombre_doctor(slug_doc)
                especialidades_doc = sorted({
                    mapa_especialidades[c] for c in esp_set if c in mapa_especialidades
                })
                if not especialidades_doc:
                    continue
                profesionales_lista.append({
                    "nombre": nombre_doc,
                    "especialidades": especialidades_doc,
                    "reserva_online": ccita,
                })

            for idx_centro in indices_centro:
                centros_existentes[idx_centro]["reserva_online"] = ccita
                if profesionales_lista:
                    centros_existentes[idx_centro]["profesionales"] = profesionales_lista[:MAX_DOCTORES_POR_CENTRO]
                    centros_actualizados += 1

        # Asegurar que todos los centros tengan el campo (aunque vacío)
        for centro in centros_existentes:
            if "profesionales" not in centro:
                centro["profesionales"] = []
            if "reserva_online" not in centro:
                centro["reserva_online"] = False

        # Guardar
        datos_json["_aviso"] = (
            f"Datos extraídos de guiamedica.fiatc.es. "
            f"Profesionales enriquecidos el {time.strftime('%Y-%m-%d')}. "
            "Uso interno POC. No contiene datos de asegurados."
        )
        datos_json["centros"] = centros_existentes
        DESTINO.write_text(
            json.dumps(datos_json, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        print(f"  Centros actualizados con profesionales: {centros_actualizados:,}")
        print(f"\n  Archivo guardado: {DESTINO}")
        print("\n¡Enriquecimiento completado!")


if __name__ == "__main__":
    asyncio.run(ejecutar())
