"""Fixtures compartidos para todos los tests del agente Guía Médica."""
from __future__ import annotations

import pytest
import httpx

URL_BASE = "http://localhost:8000"


def pytest_configure(config):
    config.addinivalue_line("markers", "lento: test que tarda más de 10s por petición a la API")
    config.addinivalue_line("markers", "adversarial: test con entradas incorrectas o límite")


@pytest.fixture(scope="session")
def backend_url() -> str:
    return URL_BASE


@pytest.fixture(scope="session", autouse=True)
def verificar_backend(backend_url: str):
    """Falla rápido si el backend no está levantado."""
    try:
        r = httpx.get(f"{backend_url}/health", timeout=5)
        r.raise_for_status()
    except Exception as exc:
        pytest.exit(
            f"Backend no disponible en {backend_url}: {exc}\n"
            "Arranca el servidor antes de ejecutar los tests.",
            returncode=3,
        )


def preguntar(backend_url: str, pregunta: str, timeout: float = 60.0) -> dict:
    """Llama a POST /chat y devuelve {respuesta, herramientas_usadas}."""
    r = httpx.post(
        f"{backend_url}/chat",
        json={"mensaje": pregunta, "historial": []},
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json()
