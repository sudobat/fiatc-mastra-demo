"""Mira que CPs cercanos a 43881 tenemos (para geocodificacion fallback)
y verifica si pgeocode esta instalado.
"""
import json
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# 1. CPs en rango 4380X-4389X
with open("data/cuadro_medico_sample.json", encoding="utf-8") as f:
    datos = json.load(f)

cps = {}
for c in datos["centros"]:
    cp = c.get("codigo_postal", "")
    if cp.startswith("438") and c.get("latitud") and c.get("longitud"):
        cps.setdefault(cp, []).append((c["latitud"], c["longitud"], c["poblacion"]))

print("=== CPs 438xx con datos ===")
for cp in sorted(cps.keys()):
    n = len(cps[cp])
    lat_avg = sum(x[0] for x in cps[cp]) / n
    lng_avg = sum(x[1] for x in cps[cp]) / n
    poblacion = cps[cp][0][2]
    print(f"  {cp} -> ({lat_avg:.4f}, {lng_avg:.4f})  {n:3d} centros  {poblacion}")

# 2. CPs en rango 088xx (Vilanova, El Vendrell area)
print("\n=== CPs 088xx (norte de Cunit) ===")
cps2 = {}
for c in datos["centros"]:
    cp = c.get("codigo_postal", "")
    if cp.startswith("088") and c.get("latitud") and c.get("longitud"):
        cps2.setdefault(cp, []).append((c["latitud"], c["longitud"], c["poblacion"]))
for cp in sorted(cps2.keys())[:10]:
    n = len(cps2[cp])
    lat_avg = sum(x[0] for x in cps2[cp]) / n
    lng_avg = sum(x[1] for x in cps2[cp]) / n
    poblacion = cps2[cp][0][2]
    print(f"  {cp} -> ({lat_avg:.4f}, {lng_avg:.4f})  {n:3d} centros  {poblacion}")

# 3. pgeocode disponible?
print("\n=== pgeocode ===")
try:
    import pgeocode  # noqa
    print("  pgeocode: INSTALADO")
except ImportError:
    print("  pgeocode: NO instalado")
