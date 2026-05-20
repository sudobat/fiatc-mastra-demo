import sys
import json

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

with open("data/cuadro_medico_sample.json", encoding="utf-8") as f:
    datos = json.load(f)

centros = datos["centros"]

for termino in ["smp", "vilanova", "geltr"]:
    matches = [
        c for c in centros
        if termino.lower() in c["nombre"].lower()
        or termino.lower() in c["poblacion"].lower()
    ]
    print(f"=== '{termino}' -> {len(matches)} resultados ===")
    for c in matches[:8]:
        print(f"  {c['id']} | {c['nombre']!r} | {c['poblacion']!r} | CP {c['codigo_postal']}")
