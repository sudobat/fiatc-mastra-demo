"""Factoria del repositorio segun configuracion."""
from __future__ import annotations

from app.config import settings
from app.repositories.api_interna import ApiInternaFiatcGuiaMedicaRepository
from app.repositories.base import GuiaMedicaRepository
from app.repositories.fichero_local import FicheroLocalGuiaMedicaRepository


def get_repository() -> GuiaMedicaRepository:
    """Devuelve la implementacion del repositorio segun la variable de entorno."""
    if settings.guia_medica_backend == "local":
        return FicheroLocalGuiaMedicaRepository(settings.guia_medica_fichero)
    return ApiInternaFiatcGuiaMedicaRepository(
        base_url=settings.api_interna_base_url,
        token=settings.api_interna_token,
    )
