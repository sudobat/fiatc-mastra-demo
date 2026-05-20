"""Herramienta: busca profesionales del cuadro medico segun filtros."""
from __future__ import annotations

from app.repositories.base import FiltroBusqueda, GuiaMedicaRepository

definicion = {
    "name": "buscar_profesionales",
    "description": (
        "Busca profesionales del cuadro medico de FIATC segun los filtros. "
        "Usa esta herramienta cuando el usuario quiera localizar medicos, especialistas o centros. "
        "Para busqueda por cercania real (ignorando limites administrativos de provincia), "
        "pasa `cerca_de_lat` y `cerca_de_lng` (obtenidas de `geolocalizar`); los resultados "
        "se ordenan por distancia ascendente y se filtran al radio indicado en `radio_km` "
        "(por defecto 30 km). Esto es util cuando el usuario esta cerca de una frontera de "
        "provincia (ej.: Cunit en CP 43881 esta a 7 km de Vilanova/Barcelona y a 30 km de "
        "Tarragona ciudad — la busqueda por proximidad encuentra ambas)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "cuadro": {
                "type": "string",
                "enum": [
                    "Cuadro completo",
                    "Medifiatc Start",
                    "Medifiatc CORP - Colectivos - Estudiantes",
                    "Medifiatc ADVANCE",
                ],
                "default": "Cuadro completo",
                "description": "Omite este campo (o usa 'Cuadro completo') por defecto. Solo pasa un valor especifico si el usuario ha mencionado EXPLICITAMENTE una modalidad de poliza.",
            },
            "tipo_servicio": {
                "type": "string",
                "enum": ["Médicos y hospitales", "Urgencias Médicas", "Pruebas diagnósticas"],
                "default": "Médicos y hospitales",
            },
            "provincia": {"type": "string", "description": "Provincia (en mayusculas, sin acentos). Se ignora si se usa cerca_de_lat/lng."},
            "poblacion": {"type": "string"},
            "codigo_postal": {"type": "string", "description": "Se ignora si se usa cerca_de_lat/lng (el filtro estricto excluiria centros vecinos)."},
            "especialidad": {"type": "string", "description": "Una de listar_especialidades()"},
            "nombre": {"type": "string", "description": "Nombre propio real del profesional o centro (p.ej. 'Clinica Corachan'). NO uses este campo para tipos de centro ni especialidades ('centro de traumatologia', 'clinica de cardiologia'): eso va en `especialidad`."},
            "reserva_online": {"type": "boolean"},
            "cerca_de_lat": {"type": "number", "description": "Latitud del punto de referencia para busqueda por proximidad."},
            "cerca_de_lng": {"type": "number", "description": "Longitud del punto de referencia para busqueda por proximidad."},
            "radio_km": {"type": "number", "description": "Radio en km para la busqueda por proximidad (default 30)."},
        },
        "required": [],
    },
}


def ejecutar(args: dict, repo: GuiaMedicaRepository) -> dict:
    filtro = FiltroBusqueda(**args)
    resultados = repo.buscar_profesionales(filtro)
    # Ocultamos el campo `cuadros` del payload visible al LLM: si va incluido,
    # el modelo tiende a inventar disclaimers sobre cobertura. La cobertura ya
    # esta garantizada (si el centro sale, esta cubierto) y el filtro real se
    # aplica en el repositorio.
    profesionales = [p.model_dump(exclude={"cuadros"}) for p in resultados[:20]]
    return {
        "total": len(resultados),
        "mostrados": len(profesionales),
        "profesionales": profesionales,
    }
