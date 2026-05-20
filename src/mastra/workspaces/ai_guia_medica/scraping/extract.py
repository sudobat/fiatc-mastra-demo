"""
Scraping del cuadro médico público de guiamedica.fiatc.es.

Estrategia (minimiza peticiones HTTP):
  1. Leer sitemaps de las 47 provincias → lista de URLs.
  2. Separar URLs de doctores individuales (/dr-*, /dra-*) de URLs de centros.
     - Doctores: nombre extraído del slug, especialidad del mapa, consul=clave de vínculo.
     - Centros: agrupados por clave_centro (slug + número sin últimos 3 dígitos).
  3. Construir mapa código_especialidad → nombre (1 petición por código único).
  4. Por cada centro único, hacer 1 petición para obtener datos base.
  5. Agregar especialidades + profesionales individuales a cada centro.
  6. Guardar en data/cuadro_medico_sample.json.

Nota: la extracción de doctores NO requiere peticiones extra — el nombre viene del
slug de la URL y la especialidad del mapa construido en el paso 3.

Uso:
  python scraping/extract.py            # ejecución completa
  python scraping/extract.py --dry-run  # solo muestra estadísticas, no descarga fichas
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import time
from collections import defaultdict
from pathlib import Path

import httpx

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

MAPA_CUADROS: dict[str, str] = {
    "0": "Cuadro completo",
    "2": "Medifiatc Start",
    "4": "Medifiatc CORP - Colectivos - Estudiantes",
    "5": "Medifiatc ADVANCE",
}

PROVINCIAS: dict[str, str] = {
    "ALAVA": "alava",
    "ALBACETE": "albacete",
    "ALICANTE": "alicante",
    "ALMERIA": "almeria",
    "ASTURIAS": "asturias",
    "AVILA": "avila",
    "BADAJOZ": "badajoz",
    "BALEARES": "baleares",
    "BARCELONA": "barcelona",
    "BURGOS": "burgos",
    "CACERES": "caceres",
    "CADIZ": "cadiz",
    "CANTABRIA": "cantabria",
    "CASTELLON": "castellon",
    "CIUDAD REAL": "ciudad-real",
    "CORDOBA": "cordoba",
    "CUENCA": "cuenca",
    "GIRONA": "girona",
    "GRANADA": "granada",
    "GUADALAJARA": "guadalajara",
    "GUIPUZCOA": "guipuzcoa",
    "HUELVA": "huelva",
    "HUESCA": "huesca",
    "JAEN": "jaen",
    "LA RIOJA": "la-rioja",
    "LAS PALMAS": "las-palmas",
    "LEON": "leon",
    "LLEIDA": "lleida",
    "LUGO": "lugo",
    "MADRID": "madrid",
    "MALAGA": "malaga",
    "MURCIA": "murcia",
    "NAVARRA": "navarra",
    "PALENCIA": "palencia",
    "PONTEVEDRA": "pontevedra",
    "SALAMANCA": "salamanca",
    "SEGOVIA": "segovia",
    "SEVILLA": "sevilla",
    "SORIA": "soria",
    "TARRAGONA": "tarragona",
    "TERUEL": "teruel",
    "TOLEDO": "toledo",
    "VALENCIA": "valencia",
    "VALLADOLID": "valladolid",
    "VIZCAYA": "vizcaya",
    "ZAMORA": "zamora",
    "ZARAGOZA": "zaragoza",
}

BASE_URL = "https://guiamedica.fiatc.es"
HEADERS = {"User-Agent": "FIATC-POC-Scraper/1.0 (poc-interno-fiatc)"}
CONCURRENCIA = 5       # peticiones simultáneas máximas
DELAY_LOTE = 0.25      # segundos de pausa tras cada petición (dentro del semáforo)
TIMEOUT = 15           # segundos de timeout por petición
REINTENTOS = 2
MAX_DOCTORES_POR_CENTRO = 100  # límite para la POC

DESTINO = Path(__file__).parent.parent / "data" / "cuadro_medico_sample.json"

# ---------------------------------------------------------------------------
# Helpers de nombres
# ---------------------------------------------------------------------------

def slug_a_nombre_doctor(slug: str) -> str:
    """Convierte 'dr-jose-maria-segura-movellan' → 'Dr. Jose Maria Segura Movellan'."""
    if slug.startswith("dra-"):
        prefijo, resto = "Dra.", slug[4:]
    elif slug.startswith("dr-"):
        prefijo, resto = "Dr.", slug[3:]
    else:
        return slug.replace("-", " ").title()
    # Eliminar sufijos numéricos de desambiguación al final (ej: "dr-garcia-1")
    resto = re.sub(r"-\d+$", "", resto)
    return f"{prefijo} {resto.replace('-', ' ').title()}"


def es_url_doctor(slug: str) -> bool:
    return slug.startswith("dr-") or slug.startswith("dra-")


# ---------------------------------------------------------------------------
# Parsing de URLs del sitemap
# ---------------------------------------------------------------------------

def extraer_clave_centro(url: str) -> tuple[str, int] | tuple[None, None]:
    """
    Devuelve (clave_centro, codigo_especialidad) a partir de una URL del sitemap.

    URL ejemplo:
      .../centro-medico-profesional/clinica-diagonal-750500000089120001/
    clave_centro  → "clinica-diagonal-7505000000891200"  (todo menos últimos 3 dígitos)
    codigo_esp    → 1  (últimos 3 dígitos como int)
    """
    url_limpia = url.rstrip("/")
    segmento = url_limpia.rsplit("/", 1)[-1]
    match = re.match(r"^(.+\d{12,})(\d{3})$", segmento)
    if not match:
        return None, None
    return match.group(1), int(match.group(2))


def extraer_componentes_url(url: str) -> tuple[str, str, int] | tuple[None, None, None]:
    """
    Devuelve (slug, consul_5chars, codi_esp) de una URL del sitemap con número de 18 dígitos.
    El consul es la clave que vincula un doctor con su centro.
    """
    url_limpia = url.rstrip("/")
    segmento = url_limpia.rsplit("/", 1)[-1]
    match = re.match(r"^(.+?)(\d{18})$", segmento)
    if not match:
        return None, None, None
    slug = match.group(1).rstrip("-")
    numero = match.group(2)
    consul = numero[10:15]   # posiciones 10-14 del número de 18 dígitos
    codi_esp = int(numero[15:18])
    return slug, consul, codi_esp


# ---------------------------------------------------------------------------
# Peticiones HTTP asíncronas
# ---------------------------------------------------------------------------

async def fetch(
    client: httpx.AsyncClient,
    url: str,
    semaforo: asyncio.Semaphore,
) -> str | None:
    async with semaforo:
        for intento in range(REINTENTOS + 1):
            try:
                r = await client.get(url, timeout=TIMEOUT, follow_redirects=True)
                await asyncio.sleep(DELAY_LOTE)
                if r.status_code == 200:
                    texto = r.text
                    if "â€" in texto or "Ã" in texto or "�" in texto:
                        try:
                            texto_alt = r.content.decode("windows-1252")
                            if "�" not in texto_alt:
                                return texto_alt
                        except (UnicodeDecodeError, LookupError):
                            pass
                    return texto
                if r.status_code in (404, 410):
                    return None
            except httpx.HTTPError as exc:
                if intento < REINTENTOS:
                    await asyncio.sleep(1.5 * (intento + 1))
                else:
                    print(f"  [!] Fallo tras {REINTENTOS + 1} intentos: {url} - {exc}")
    return None


async def obtener_urls_sitemap(
    client: httpx.AsyncClient,
    slug_provincia: str,
) -> list[str]:
    url = f"{BASE_URL}/sitemap_provincia_{slug_provincia}-es.xml"
    try:
        r = await client.get(url, timeout=TIMEOUT, follow_redirects=True)
        if r.status_code == 200:
            return re.findall(r"<loc>(.*?)</loc>", r.text)
    except Exception as exc:
        print(f"  [!] Error leyendo sitemap {slug_provincia}: {exc}")
    return []


# ---------------------------------------------------------------------------
# Extracción de datos desde el HTML de una ficha
# ---------------------------------------------------------------------------

def extraer_json_ficha(html: str) -> dict | None:
    """Extrae el objeto JSON embebido en la página de una ficha centro-profesional."""
    match = re.search(r'\{[^{}]*"codi_postal"[^{}]*\}', html)
    if not match:
        return None
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return None


def normalizar_especialidad(nombre: str) -> str:
    return nombre.strip().title()


# ---------------------------------------------------------------------------
# Lógica principal
# ---------------------------------------------------------------------------

async def ejecutar(dry_run: bool = False, provincias_filtro: list[str] | None = None) -> None:
    semaforo = asyncio.Semaphore(CONCURRENCIA)

    # Provincias a procesar (todas o solo las indicadas)
    provincias_activas = {
        k: v for k, v in PROVINCIAS.items()
        if provincias_filtro is None or k in provincias_filtro
    }
    modo_parcial = provincias_filtro is not None

    async with httpx.AsyncClient(headers=HEADERS) as client:

        # ------------------------------------------------------------------
        # Paso 1: Leer los sitemaps de provincia
        # ------------------------------------------------------------------
        print("=" * 60)
        print("Paso 1 — Leyendo sitemaps de provincia")
        if modo_parcial:
            print(f"  (filtro: {', '.join(provincias_activas)})")
        print("=" * 60)
        todas_urls: list[str] = []
        for nombre_prov, slug in provincias_activas.items():
            urls = await obtener_urls_sitemap(client, slug)
            print(f"  {nombre_prov:12s}: {len(urls):>6,} URLs")
            todas_urls.extend(urls)
        print(f"\n  Total URLs: {len(todas_urls):,}")

        # ------------------------------------------------------------------
        # Paso 2: Separar doctores de centros; agrupar por clave/consul
        # ------------------------------------------------------------------
        print("\n" + "=" * 60)
        print("Paso 2 — Separando centros de doctores individuales")
        print("=" * 60)

        # centros: clave_centro → lista de (cod_esp, url)
        centros_urls: dict[str, list[tuple[int, str]]] = defaultdict(list)
        # doctores: consul_5chars → {ref_completo → set(codi_esp)}
        # ref_completo = segmento URL completo (slug + número 18 dígitos), ej:
        #   "dr-daniel-martin-casola-008140000089120040"
        # De él se extrae: prof=[0:5], consul=[10:15], codi_esp=[15:18]
        doctores_por_consul: dict[str, dict[str, set[int]]] = defaultdict(lambda: defaultdict(set))
        # especialidades: cod_esp → una URL de ejemplo para construir el mapa de nombres
        ejemplo_por_codigo: dict[int, str] = {}

        for url in todas_urls:
            slug, consul, codi_esp = extraer_componentes_url(url)
            if slug is None:
                continue

            if es_url_doctor(slug):
                # Doctor individual → indexar por consul usando el segmento completo como clave
                # para preservar el número de 18 dígitos (prof, consul, codi_esp codificados)
                segmento_completo = url.rstrip("/").rsplit("/", 1)[-1]
                doctores_por_consul[consul][segmento_completo].add(codi_esp)
                if codi_esp not in ejemplo_por_codigo:
                    ejemplo_por_codigo[codi_esp] = url
            else:
                # Centro / clínica → lógica original
                clave, cod_esp = extraer_clave_centro(url)
                if clave is not None:
                    centros_urls[clave].append((cod_esp, url))
                    if cod_esp not in ejemplo_por_codigo:
                        ejemplo_por_codigo[cod_esp] = url

        total_doctores = sum(len(docs) for docs in doctores_por_consul.values())
        print(f"  Centros únicos:            {len(centros_urls):,}")
        print(f"  Cónsules con doctores:     {len(doctores_por_consul):,}")
        print(f"  Doctores únicos (slugs):   {total_doctores:,}")
        print(f"  Códigos de especialidad:   {len(ejemplo_por_codigo)}")

        if dry_run:
            print("\n[dry-run] Estadísticas listas. Sin peticiones adicionales.")
            return

        # ------------------------------------------------------------------
        # Paso 3: Construir mapa código_especialidad → nombre
        # ------------------------------------------------------------------
        total_codigos = len(ejemplo_por_codigo)
        print(f"\n{'=' * 60}")
        print(f"Paso 3 — Mapeando {total_codigos} especialidades (1 petición/código)")
        print("=" * 60)

        mapa_especialidades: dict[int, str] = {}
        urls_codigo = list(ejemplo_por_codigo.values())
        codigos_lista = list(ejemplo_por_codigo.keys())

        tareas = [fetch(client, u, semaforo) for u in urls_codigo]
        resultados = await asyncio.gather(*tareas, return_exceptions=True)

        for codigo, html in zip(codigos_lista, resultados):
            if isinstance(html, Exception) or not html:
                continue
            datos = extraer_json_ficha(html)
            if datos and datos.get("lit_esp"):
                mapa_especialidades[codigo] = normalizar_especialidad(datos["lit_esp"])

        print(f"  Especialidades mapeadas: {len(mapa_especialidades)}/{total_codigos}")

        # ------------------------------------------------------------------
        # Paso 4: Obtener datos base de cada centro único (1 petición/centro)
        # ------------------------------------------------------------------
        total_centros = len(centros_urls)
        print(f"\n{'=' * 60}")
        print(f"Paso 4 — Descargando {total_centros:,} fichas de centro")
        print("  (puede tardar varios minutos — 1 petición por centro único)")
        print("=" * 60)

        claves_centros = list(centros_urls.keys())
        primeras_urls = [centros_urls[c][0][1] for c in claves_centros]
        tareas_centros = [fetch(client, u, semaforo) for u in primeras_urls]

        resultados_centros: list[str | None] = []
        LOTE = 100
        for i in range(0, len(tareas_centros), LOTE):
            lote_res = await asyncio.gather(*tareas_centros[i: i + LOTE], return_exceptions=True)
            resultados_centros.extend(
                None if isinstance(r, Exception) else r for r in lote_res
            )
            procesados = min(i + LOTE, total_centros)
            print(f"  Procesados: {procesados:,}/{total_centros:,}", end="\r")
        print()

        # ------------------------------------------------------------------
        # Paso 5: Construir la lista de centros (con profesionales)
        # ------------------------------------------------------------------
        print(f"\n{'=' * 60}")
        print("Paso 5 — Construyendo JSON final con profesionales")
        print("=" * 60)

        centros_json: list[dict] = []
        especialidades_encontradas: set[str] = set()
        errores = 0

        for idx, (clave, html) in enumerate(zip(claves_centros, resultados_centros)):
            if not html:
                errores += 1
                continue
            datos = extraer_json_ficha(html)
            if not datos:
                errores += 1
                continue

            # Especialidades del centro
            esp_centro: list[str] = []
            for cod_esp, _ in centros_urls[clave]:
                nombre_esp = mapa_especialidades.get(cod_esp)
                if nombre_esp and nombre_esp not in esp_centro:
                    esp_centro.append(nombre_esp)
                    especialidades_encontradas.add(nombre_esp)

            # Profesionales del centro: vinculados por consul
            consul_raw = datos.get("consul", "")
            consul_key = consul_raw.zfill(5)
            ccita_centro = datos.get("ccita", "0") == "1"

            fact_centro = str(datos.get("fact", "") or "")
            profesionales_lista: list[dict] = []
            for ref_completo, esp_set in sorted(doctores_por_consul.get(consul_key, {}).items()):
                # Extraer slug (nombre) y número de 18 dígitos del ref completo
                m_ref = re.match(r'^(.+?)(\d{18})$', ref_completo)
                if m_ref:
                    slug_doc = m_ref.group(1).rstrip("-")
                    numero_ref = m_ref.group(2)
                    prof_code = str(int(numero_ref[0:5]))
                else:
                    slug_doc = ref_completo
                    numero_ref = ""
                    prof_code = ""
                nombre_doc = slug_a_nombre_doctor(slug_doc)
                especialidades_doc = sorted({
                    mapa_especialidades[c] for c in esp_set if c in mapa_especialidades
                })
                if not especialidades_doc:
                    continue
                profesionales_lista.append({
                    "nombre": nombre_doc,
                    "especialidades": especialidades_doc,
                    "reserva_online": ccita_centro,
                    "prof": prof_code,
                    "ref": ref_completo,
                })

            profesionales_lista = profesionales_lista[:MAX_DOCTORES_POR_CENTRO]

            # Cuadros médicos: campo "quadre" es una cadena ",2,4,5," con IDs separados por comas.
            # Todo centro que aparece en la guía pertenece siempre a "Cuadro completo".
            quadre_raw = str(datos.get("quadre") or "")
            cuadros = sorted({
                "Cuadro completo",
                *( MAPA_CUADROS[q] for q in quadre_raw.split(",") if q.strip() in MAPA_CUADROS )
            })

            centro = {
                "id": f"C{idx + 1:05d}",
                "nombre": (datos.get("nom_propi") or datos.get("nom", "")).strip().title(),
                "direccion": datos.get("direccio", "").strip().title(),
                "poblacion": datos.get("lit_pob", "").strip().title(),
                "provincia": datos.get("lit_prov", "").strip().upper(),
                "codigo_postal": datos.get("codi_postal", "").strip(),
                "telefono": datos.get("telefon1", "").strip(),
                "horario": datos.get("horari", "").strip(),
                "latitud": float(datos["lat"]) if datos.get("lat") else None,
                "longitud": float(datos["lng"]) if datos.get("lng") else None,
                "especialidades": sorted(esp_centro),
                "cuadros": cuadros,
                "reserva_online": ccita_centro,
                "profesionales": profesionales_lista,
                # Campos XWM para la reserva online.
                "consul": consul_key if consul_key else None,
                "fact": fact_centro if fact_centro else None,
            }
            centros_json.append(centro)

        # ------------------------------------------------------------------
        # Paso 6: Guardar (merge si es scraping parcial, reemplazo si es completo)
        # ------------------------------------------------------------------
        if modo_parcial and DESTINO.exists():
            # Cargar JSON existente y reemplazar solo los centros de las provincias scrapeadas
            existente = json.loads(DESTINO.read_text(encoding="utf-8"))
            centros_otros = [
                c for c in existente.get("centros", [])
                if c.get("provincia", "").upper() not in provincias_activas
            ]
            # Reasignar IDs secuenciales a los centros nuevos, continuando tras el máximo existente
            max_id = max(
                (int(c["id"][1:]) for c in existente.get("centros", []) if c["id"][1:].isdigit()),
                default=0,
            )
            for i, c in enumerate(centros_json, start=max_id + 1):
                c["id"] = f"C{i:05d}"
            centros_finales = centros_otros + centros_json
            # Especialidades: unir las existentes con las nuevas
            esp_existentes = set(existente.get("especialidades", []))
            especialidades_finales = sorted(esp_existentes | especialidades_encontradas)
            print(f"\n  Centros anteriores (otras provincias): {len(centros_otros):,}")
            print(f"  Centros nuevos ({'/'.join(provincias_activas)}): {len(centros_json):,}")
        else:
            centros_finales = centros_json
            especialidades_finales = sorted(especialidades_encontradas)

        resultado = {
            "_aviso": (
                f"Datos reales extraídos de guiamedica.fiatc.es el {time.strftime('%Y-%m-%d')}. "
                "Uso interno POC. No contiene datos de asegurados."
            ),
            "especialidades": especialidades_finales,
            "provincias": list(PROVINCIAS.keys()),
            "centros": centros_finales,
            "profesionales": [],
        }

        DESTINO.write_text(
            json.dumps(resultado, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        total_con_docs = sum(1 for c in centros_finales if c["profesionales"])
        print(f"\n  Centros totales guardados: {len(centros_finales):,}")
        print(f"  Centros con profesionales: {total_con_docs:,}")
        print(f"  Especialidades:            {len(especialidades_finales)}")
        print(f"  Errores/sin datos:         {errores}")
        print(f"\n  Archivo: {DESTINO}")
        print("\n¡Scraping completado!")


# ---------------------------------------------------------------------------
# Entrada
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Scraping cuadro médico FIATC")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Solo muestra estadísticas del sitemap sin descargar fichas",
    )
    parser.add_argument(
        "--provincias",
        nargs="+",
        metavar="PROV",
        help="Scraping parcial: indica una o más provincias (ej: BARCELONA MADRID). "
             "Los centros de esas provincias se reemplazan en el JSON existente; "
             "el resto se conserva sin cambios.",
    )
    args = parser.parse_args()

    filtro = None
    if args.provincias:
        filtro = [p.upper() for p in args.provincias]
        invalidas = [p for p in filtro if p not in PROVINCIAS]
        if invalidas:
            parser.error(f"Provincias no reconocidas: {invalidas}. Válidas: {sorted(PROVINCIAS)}")

    asyncio.run(ejecutar(dry_run=args.dry_run, provincias_filtro=filtro))


if __name__ == "__main__":
    main()
