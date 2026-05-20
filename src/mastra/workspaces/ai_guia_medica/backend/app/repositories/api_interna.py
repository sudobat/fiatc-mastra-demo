"""Implementacion del repositorio contra la API interna de FIATC.

ESTADO: STUB. No implementado todavia.

Cuando el equipo propietario de la Guia Medica publique el contrato de la API,
hay que rellenar los metodos de esta clase. El resto del agente NO necesita
ningun cambio: gracias al patron Repository, basta con cambiar la variable
GUIA_MEDICA_BACKEND=api en el fichero .env.
"""
from __future__ import annotations

from typing import Optional

import httpx

from app.repositories.base import (
    Centro,
    FiltroBusqueda,
    GuiaMedicaRepository,
    Profesional,
)


class ApiInternaFiatcGuiaMedicaRepository(GuiaMedicaRepository):
    def __init__(self, base_url: str, token: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._cliente = httpx.Client(
            base_url=self._base_url,
            headers={"Authorization": f"Bearer {token}"} if token else {},
            timeout=10.0,
        )

    def buscar_profesionales(self, filtro: FiltroBusqueda) -> list[Profesional]:
        # TODO: ajustar al contrato real de la API interna FIATC.
        # Ejemplo orientativo:
        # response = self._cliente.get("/cuadro-medico/profesionales", params=filtro.model_dump(exclude_none=True))
        # response.raise_for_status()
        # return [Profesional(**p) for p in response.json()]
        raise NotImplementedError(
            "ApiInternaFiatcGuiaMedicaRepository.buscar_profesionales: pendiente de implementar."
        )

    def obtener_centro(self, id_centro: str) -> Optional[Centro]:
        # TODO: ajustar al contrato real.
        raise NotImplementedError(
            "ApiInternaFiatcGuiaMedicaRepository.obtener_centro: pendiente de implementar."
        )

    def listar_especialidades(self) -> list[str]:
        # TODO: ajustar al contrato real.
        raise NotImplementedError(
            "ApiInternaFiatcGuiaMedicaRepository.listar_especialidades: pendiente de implementar."
        )

    def listar_provincias(self) -> list[str]:
        # TODO: ajustar al contrato real.
        raise NotImplementedError(
            "ApiInternaFiatcGuiaMedicaRepository.listar_provincias: pendiente de implementar."
        )

    def __del__(self) -> None:
        try:
            self._cliente.close()
        except Exception:
            pass
