"""Configuracion central del backend, leida de variables de entorno."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env", override=True)


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str
    anthropic_model: str
    guia_medica_backend: str  # 'local' | 'api'
    guia_medica_fichero: Path
    api_interna_base_url: str
    api_interna_token: str
    # URL base para invocar el módulo XWM sld_guia_medica.
    # Ejemplo: http://servidor-intranet/xwm/sld_guia_medica
    # Si está vacío, los endpoints de reserva devuelven respuesta de POC simulada.
    xwm_base_url: str
    xwm_token: str


def cargar_settings() -> Settings:
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY no esta definida. Copia .env.example a .env y configurala."
        )

    backend = os.getenv("GUIA_MEDICA_BACKEND", "local").lower()
    if backend not in ("local", "api"):
        raise RuntimeError(
            f"GUIA_MEDICA_BACKEND invalida: {backend!r}. Valores validos: 'local' o 'api'."
        )

    fichero = Path(os.getenv("GUIA_MEDICA_FICHERO", "../data/cuadro_medico_sample.json"))

    return Settings(
        anthropic_api_key=api_key,
        anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        guia_medica_backend=backend,
        guia_medica_fichero=fichero,
        api_interna_base_url=os.getenv("API_INTERNA_BASE_URL", ""),
        api_interna_token=os.getenv("API_INTERNA_TOKEN", ""),
        xwm_base_url=os.getenv("XWM_BASE_URL", ""),
        xwm_token=os.getenv("XWM_TOKEN", ""),
    )


settings = cargar_settings()
