"""Herramienta: devuelve la ficha completa de un centro o profesional."""
from __future__ import annotations

from app.repositories.base import GuiaMedicaRepository

definicion = {
    "name": "obtener_centro",
    "description": (
        "Devuelve la ficha completa de un centro medico (direccion, telefono, horario, "
        "especialidades). Se usa cuando el usuario pide detalles de un centro concreto."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "id_centro": {"type": "string", "description": "Identificador del centro"},
        },
        "required": ["id_centro"],
    },
}


def ejecutar(args: dict, repo: GuiaMedicaRepository) -> dict:
    id_centro = args.get("id_centro", "")
    centro = repo.obtener_centro(id_centro)
    if centro is None:
        return {"error": f"No se ha encontrado el centro con id '{id_centro}'."}
    return centro.model_dump()
