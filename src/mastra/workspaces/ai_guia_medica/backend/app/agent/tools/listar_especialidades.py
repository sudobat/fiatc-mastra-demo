"""Herramienta: devuelve el catalogo cerrado de especialidades validas."""
from __future__ import annotations

from app.repositories.base import GuiaMedicaRepository

definicion = {
    "name": "listar_especialidades",
    "description": (
        "Devuelve la lista cerrada de especialidades validas en el cuadro medico. "
        "Usala cuando necesites validar el nombre exacto de una especialidad."
    ),
    "input_schema": {"type": "object", "properties": {}, "required": []},
}


def ejecutar(args: dict, repo: GuiaMedicaRepository) -> dict:
    return {"especialidades": repo.listar_especialidades()}
