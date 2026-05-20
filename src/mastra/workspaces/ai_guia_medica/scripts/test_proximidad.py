"""Test directo: geolocalizar 43881 + buscar_profesionales por proximidad."""
import sys
sys.path.insert(0, "backend")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.repositories.fichero_local import FicheroLocalGuiaMedicaRepository
from app.repositories.base import FiltroBusqueda
from app.agent.tools import geolocalizar

repo = FicheroLocalGuiaMedicaRepository("data/cuadro_medico_sample.json")

# 1. Geolocalizar Cunit
print("=== geolocalizar('43881') ===")
res = geolocalizar.ejecutar({"texto": "43881"}, repo)
for k, v in res.items():
    print(f"  {k}: {v}")

# 2. Si nos da coords, buscar por proximidad
if res.get("latitud") and res.get("longitud"):
    print("\n=== buscar_profesionales(cerca_de=Cunit, radio=15km, especialidad=Medicina General) ===")
    f = FiltroBusqueda(
        cerca_de_lat=res["latitud"],
        cerca_de_lng=res["longitud"],
        radio_km=15.0,
        especialidad="Medicina General",
    )
    profs = repo.buscar_profesionales(f)
    print(f"  Total: {len(profs)} resultados")
    for p in profs[:8]:
        print(f"  {p.distancia_km:5.1f} km | {p.nombre[:45]:45s} | {p.poblacion[:25]:25s} | {p.provincia}")

# 3. Comparativa: busqueda clasica por provincia (TARRAGONA)
print("\n=== buscar_profesionales(provincia=TARRAGONA, especialidad=Medicina General) [COMPARATIVA] ===")
f2 = FiltroBusqueda(provincia="TARRAGONA", especialidad="Medicina General")
profs2 = repo.buscar_profesionales(f2)
print(f"  Total: {len(profs2)} resultados (sin info de proximidad)")
for p in profs2[:5]:
    print(f"  {p.nombre[:45]:45s} | {p.poblacion[:25]:25s} | {p.provincia}")
