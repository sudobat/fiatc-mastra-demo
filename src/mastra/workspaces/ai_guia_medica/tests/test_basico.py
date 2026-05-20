"""
Test básico: ejecuta la batería de 100 preguntas como suite pytest.

Cada caso de la batería se convierte en un test parametrizado independiente.
Uso:
    python -m pytest tests/test_basico.py -v
    python -m pytest tests/test_basico.py -v -k "categoria-A"   # solo una categoría
    python -m pytest tests/test_basico.py --tb=short            # traceback corto
"""
from __future__ import annotations

import pytest
from conftest import preguntar
from bateria_100_preguntas import CASOS, validar


def _id(caso):
    return f"{caso.id:03d}-{caso.categoria}"


@pytest.mark.lento
@pytest.mark.parametrize("caso", CASOS, ids=_id)
def test_pregunta(caso, backend_url):
    datos = preguntar(backend_url, caso.pregunta)
    respuesta = datos.get("respuesta", "")

    ok, motivo = validar(caso, respuesta)

    assert ok, (
        f"\nPregunta  : {caso.pregunta}\n"
        f"Motivo    : {motivo}\n"
        f"Respuesta : {respuesta[:300]}\n"
        f"Herram.   : {datos.get('herramientas_usadas', [])}"
    )
