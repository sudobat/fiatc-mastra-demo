"""Verifica:
1. Si Cunit (CP 43881) tiene centros en el JSON.
2. Las coordenadas medias de Cunit, Vilanova y Tarragona ciudad.
3. La distancia real entre Cunit y los centros candidatos.
"""
import json
import math
import sys
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Distancia en km entre dos pares lat/lng."""
    R = 6371.0
    a1, a2 = math.radians(lat1), math.radians(lat2)
    da = math.radians(lat2 - lat1)
    do = math.radians(lng2 - lng1)
    h = math.sin(da / 2) ** 2 + math.cos(a1) * math.cos(a2) * math.sin(do / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


with open("data/cuadro_medico_sample.json", encoding="utf-8") as f:
    datos = json.load(f)

centros = datos["centros"]

def coords_medias(filtro):
    matches = [c for c in centros if filtro(c) and c.get("latitud") and c.get("longitud")]
    if not matches:
        return None, 0
    lat = sum(c["latitud"] for c in matches) / len(matches)
    lng = sum(c["longitud"] for c in matches) / len(matches)
    return (lat, lng), len(matches)

cunit_coords, cunit_n = coords_medias(lambda c: c["codigo_postal"] == "43881")
vilanova_coords, vilanova_n = coords_medias(lambda c: c["codigo_postal"] == "08800")
tarragona_coords, tarragona_n = coords_medias(lambda c: c["codigo_postal"] == "43001")

print(f"Cunit (43881):    {cunit_n} centros, coord = {cunit_coords}")
print(f"Vilanova (08800): {vilanova_n} centros, coord = {vilanova_coords}")
print(f"Tarragona (43001):{tarragona_n} centros, coord = {tarragona_coords}")

if cunit_coords:
    print()
    print("=== Distancia Cunit -> Vilanova vs Tarragona ===")
    if vilanova_coords:
        d_v = haversine(*cunit_coords, *vilanova_coords)
        print(f"  Cunit -> Vilanova:  {d_v:.2f} km")
    if tarragona_coords:
        d_t = haversine(*cunit_coords, *tarragona_coords)
        print(f"  Cunit -> Tarragona: {d_t:.2f} km")

# Centros mas cercanos a Cunit (ordenados por distancia)
if cunit_coords:
    print("\n=== 10 centros mas cercanos a Cunit ===")
    con_coords = [c for c in centros if c.get("latitud") and c.get("longitud")]
    distancias = [
        (haversine(*cunit_coords, c["latitud"], c["longitud"]), c)
        for c in con_coords
    ]
    distancias.sort(key=lambda x: x[0])
    for d, c in distancias[:10]:
        print(f"  {d:6.2f} km  | {c['nombre'][:50]:50s} | {c['poblacion']:30s} | CP {c['codigo_postal']} | {c['provincia']}")
