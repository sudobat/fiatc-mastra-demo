"""Catalogo de herramientas que el agente puede invocar."""
from __future__ import annotations

from app.agent.tools import (
    buscar_profesionales,
    geolocalizar,
    listar_especialidades,
    mapear_sintoma,
    obtener_centro,
)

# Cada herramienta expone:
#   - definicion: dict con el esquema para el LLM (formato Anthropic tool spec)
#   - ejecutar(args, repo): funcion sincrona que devuelve un dict serializable

HERRAMIENTAS = {
    "buscar_profesionales": buscar_profesionales,
    "obtener_centro": obtener_centro,
    "listar_especialidades": listar_especialidades,
    "mapear_sintoma_a_especialidad": mapear_sintoma,
    "geolocalizar": geolocalizar,
}


def definiciones_para_llm() -> list[dict]:
    """Devuelve la lista de definiciones de herramientas en el formato del SDK de Anthropic."""
    return [h.definicion for h in HERRAMIENTAS.values()]


def ejecutar(nombre: str, args: dict, repo) -> dict:
    if nombre not in HERRAMIENTAS:
        return {"error": f"Herramienta desconocida: {nombre}"}
    return HERRAMIENTAS[nombre].ejecutar(args, repo)
