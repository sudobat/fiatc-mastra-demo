"""Herramienta: normaliza una ubicacion (texto/CP) a provincia + poblacion + coordenadas.

Estrategia (de mas precisa a menos):
  1. Texto coincide con un CP -> centroide de centros con ese CP (precisa).
  2. Texto coincide con un nombre de poblacion -> centroide de centros en esa poblacion.
  3. CP no presente en nuestros datos -> pgeocode (datos publicos de CPs espanoles).
  4. Nada -> resuelto=False.

La respuesta incluye `latitud` y `longitud` cuando es posible para que
`buscar_profesionales` pueda hacer busqueda por proximidad ignorando la provincia.
"""
from __future__ import annotations

import unicodedata
from functools import lru_cache
from typing import Optional

from app.repositories.base import GuiaMedicaRepository

# Prefijos de CP (2 digitos) -> clave de provincia tal como aparece en los datos
# Cubre las 50 provincias espanolas segun codigos INE.
_CP_PROVINCIA: dict[str, str] = {
    "01": "ALAVA", "02": "ALBACETE", "03": "ALICANTE", "04": "ALMERIA",
    "05": "AVILA", "06": "BADAJOZ", "07": "BALEARES", "08": "BARCELONA",
    "09": "BURGOS", "10": "CACERES", "11": "CADIZ", "12": "CASTELLON",
    "13": "CIUDAD REAL", "14": "CORDOBA", "15": "A CORUNA", "16": "CUENCA",
    "17": "GIRONA", "18": "GRANADA", "19": "GUADALAJARA", "20": "GUIPUZCOA",
    "21": "HUELVA", "22": "HUESCA", "23": "JAEN", "24": "LEON",
    "25": "LLEIDA", "26": "LA RIOJA", "27": "LUGO", "28": "MADRID",
    "29": "MALAGA", "30": "MURCIA", "31": "NAVARRA", "32": "OURENSE",
    "33": "ASTURIAS", "34": "PALENCIA", "35": "LAS PALMAS", "36": "PONTEVEDRA",
    "37": "SALAMANCA", "38": "SANTA CRUZ DE TENERIFE", "39": "CANTABRIA",
    "40": "SEGOVIA", "41": "SEVILLA", "42": "SORIA", "43": "TARRAGONA",
    "44": "TERUEL", "45": "TOLEDO", "46": "VALENCIA", "47": "VALLADOLID",
    "48": "VIZCAYA", "49": "ZAMORA", "50": "ZARAGOZA",
}


def _norm(texto: str) -> str:
    """Minusculas sin acentos para comparaciones flexibles."""
    s = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


@lru_cache(maxsize=1)
def _nominatim():
    """Carga perezosa de pgeocode. La primera llamada descarga datos (~3MB)."""
    try:
        import pgeocode
        return pgeocode.Nominatim("es")
    except Exception:
        return None


def _pgeocode_lookup(cp: str) -> Optional[tuple[float, float, str]]:
    """Devuelve (lat, lng, place_name) para un CP espanol, o None si falla.

    pgeocode incluye varias entradas por CP (urbanizaciones, campings, barrios...).
    La media que devuelve `query_postal_code` puede estar desplazada respecto al
    nucleo urbano. Por eso aqui pedimos todas las entradas con `query_location`
    filtradas por CP y elegimos la canonica: la que tiene el nombre mas corto y
    sin parentesis ni guiones (suele coincidir con el nombre de la poblacion).
    """
    nomi = _nominatim()
    if nomi is None:
        return None
    try:
        import math
        # Tomamos todas las entradas de la BD con ese CP
        df = nomi._data
        filas = df[df["postal_code"] == cp]
        if len(filas) == 0:
            return None

        # Filtrar las que tienen lat/lng validos
        validas = filas.dropna(subset=["latitude", "longitude"])
        if len(validas) == 0:
            return None

        # Elegir la entrada canonica: nombre mas corto y sin parentesis/guiones
        def es_canonica(nombre: str) -> int:
            nombre = nombre or ""
            penaliza = (("(" in nombre) or (")" in nombre) or ("-" in nombre)) * 100
            return penaliza + len(nombre)

        validas_sorted = validas.copy()
        validas_sorted["__rank"] = validas_sorted["place_name"].apply(es_canonica)
        validas_sorted = validas_sorted.sort_values("__rank")
        mejor = validas_sorted.iloc[0]

        lat = float(mejor["latitude"])
        lng = float(mejor["longitude"])
        if math.isnan(lat) or math.isnan(lng):
            return None
        place = (mejor.get("place_name") or "").strip()
        return lat, lng, place
    except Exception:
        # Fallback al metodo simple si la estructura interna cambia
        try:
            r = nomi.query_postal_code(cp)
            import math
            lat, lng = r.get("latitude"), r.get("longitude")
            if lat is None or lng is None or math.isnan(lat) or math.isnan(lng):
                return None
            place = (r.get("place_name") or "").split(",")[0].strip()
            return float(lat), float(lng), place
        except Exception:
            return None


def _centroide_centros(centros) -> Optional[tuple[float, float]]:
    """Centroide (media de lat/lng) de una lista de objetos Centro con coords."""
    con_coords = [c for c in centros if c.latitud is not None and c.longitud is not None]
    if not con_coords:
        return None
    lat = sum(c.latitud for c in con_coords) / len(con_coords)
    lng = sum(c.longitud for c in con_coords) / len(con_coords)
    return lat, lng


definicion = {
    "name": "geolocalizar",
    "description": (
        "Normaliza una ubicacion expresada en lenguaje natural (nombre de poblacion, "
        "codigo postal o frase como 'cerca de Barcelona') a provincia, poblacion y "
        "coordenadas (latitud/longitud). Las coordenadas devueltas se pueden pasar a "
        "`buscar_profesionales` (campos `cerca_de_lat`, `cerca_de_lng`) para busqueda "
        "por cercania real ignorando los limites administrativos de provincia."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "texto": {
                "type": "string",
                "description": "Texto libre con la ubicacion o codigo postal",
            }
        },
        "required": ["texto"],
    },
}


def ejecutar(args: dict, repo: GuiaMedicaRepository) -> dict:
    texto = args.get("texto", "").strip()
    if not texto:
        return {"resuelto": False, "motivo": "Texto vacio"}

    centros_dict = getattr(repo, "_centros", {})
    todos_centros = list(centros_dict.values())

    # ------------------------------------------------------------------
    # Caso 1: el texto contiene un CP de 5 digitos
    # ------------------------------------------------------------------
    digitos = "".join(c for c in texto if c.isdigit())
    if len(digitos) == 5:
        prefijo = digitos[:2]
        provincia = _CP_PROVINCIA.get(prefijo)

        centros_cp = [c for c in todos_centros if c.codigo_postal == digitos]

        # 1a. pgeocode primero: da el centro geografico real del CP, sin sesgo
        pg = _pgeocode_lookup(digitos)
        if pg:
            lat, lng, place = pg
            prov = centros_cp[0].provincia if centros_cp else provincia
            pob = centros_cp[0].poblacion if centros_cp else place
            return {
                "resuelto": True,
                "provincia": prov,
                "poblacion": pob,
                "codigo_postal": digitos,
                "latitud": lat,
                "longitud": lng,
                "fuente_coords": "pgeocode",
            }

        # 1b. Fallback: centroide de centros con ese CP
        coords = _centroide_centros(centros_cp)
        if coords:
            return {
                "resuelto": True,
                "provincia": centros_cp[0].provincia,
                "poblacion": centros_cp[0].poblacion,
                "codigo_postal": digitos,
                "latitud": coords[0],
                "longitud": coords[1],
                "fuente_coords": "centros",
            }

        # 1c. Fallback final: solo provincia
        if provincia:
            return {
                "resuelto": True,
                "provincia": provincia,
                "codigo_postal": digitos,
            }

    # ------------------------------------------------------------------
    # Caso 2: el texto es un nombre de poblacion (busqueda por tokens)
    # ------------------------------------------------------------------
    texto_norm = _norm(texto)
    tokens = [t for t in texto_norm.split() if len(t) > 3]
    if tokens:
        # Agrupar centros por poblacion normalizada (para construir centroides correctos)
        grupos: dict[str, list] = {}
        nombres_orig: dict[str, str] = {}
        for centro in todos_centros:
            pob_norm = _norm(centro.poblacion)
            grupos.setdefault(pob_norm, []).append(centro)
            nombres_orig.setdefault(pob_norm, centro.poblacion)

        # 2a. Match exacto
        if texto_norm in grupos:
            centros = grupos[texto_norm]
            coords = _centroide_centros(centros)
            return {
                "resuelto": True,
                "provincia": centros[0].provincia,
                "poblacion": nombres_orig[texto_norm],
                "latitud": coords[0] if coords else None,
                "longitud": coords[1] if coords else None,
                "fuente_coords": "centros" if coords else None,
            }

        # 2b. Match por tokens (todos los tokens >3 chars en la poblacion)
        for pob_norm, centros in grupos.items():
            if all(t in pob_norm for t in tokens):
                coords = _centroide_centros(centros)
                return {
                    "resuelto": True,
                    "provincia": centros[0].provincia,
                    "poblacion": nombres_orig[pob_norm],
                    "latitud": coords[0] if coords else None,
                    "longitud": coords[1] if coords else None,
                    "fuente_coords": "centros" if coords else None,
                }

    return {
        "resuelto": False,
        "motivo": (
            "No se ha podido normalizar la ubicacion con los datos disponibles. "
            "Pide al usuario que indique provincia o codigo postal."
        ),
    }
