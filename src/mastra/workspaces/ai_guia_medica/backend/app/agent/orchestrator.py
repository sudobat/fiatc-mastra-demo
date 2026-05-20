"""Orquestador del agente: bucle de tool-calling con Claude (modo bloqueante y streaming)."""
from __future__ import annotations

from typing import Iterator

from anthropic import Anthropic

from app.agent import tools as catalogo_tools
from app.agent.prompts import PROMPT_SISTEMA
from app.config import settings
from app.repositories import get_repository

MAX_ITERACIONES = 8


class Orchestrator:
    def __init__(self) -> None:
        self._cliente = Anthropic(api_key=settings.anthropic_api_key)
        self._repo = get_repository()

    # ── Modo bloqueante (compatibilidad con el endpoint /chat clasico) ────────
    def responder(self, historial: list[dict], mensaje_usuario: str) -> dict:
        mensajes = list(historial)
        mensajes.append({"role": "user", "content": mensaje_usuario})

        herramientas_usadas: list[str] = []

        for _ in range(MAX_ITERACIONES):
            response = self._cliente.messages.create(
                model=settings.anthropic_model,
                max_tokens=1024,
                system=PROMPT_SISTEMA,
                tools=catalogo_tools.definiciones_para_llm(),
                messages=mensajes,
            )

            if response.stop_reason == "tool_use":
                mensajes.append({"role": "assistant", "content": response.content})

                resultados_tool: list[dict] = []
                for bloque in response.content:
                    if bloque.type == "tool_use":
                        herramientas_usadas.append(bloque.name)
                        salida = catalogo_tools.ejecutar(bloque.name, bloque.input, self._repo)
                        resultados_tool.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": bloque.id,
                                "content": _serializar(salida),
                            }
                        )

                mensajes.append({"role": "user", "content": resultados_tool})
                continue

            texto = ""
            for bloque in response.content:
                if bloque.type == "text":
                    texto += bloque.text
            return {
                "respuesta": texto.strip(),
                "herramientas_usadas": herramientas_usadas,
            }

        return {
            "respuesta": (
                "Lo siento, no he podido completar la consulta dentro del limite de pasos. "
                "Por favor, reformula la pregunta."
            ),
            "herramientas_usadas": herramientas_usadas,
        }

    # ── Modo streaming (endpoint /chat/stream) ────────────────────────────────
    def responder_stream(
        self, historial: list[dict], mensaje_usuario: str
    ) -> Iterator[dict]:
        """Generador que produce eventos a medida que el agente procesa la pregunta.

        Eventos posibles (todos son dicts JSON-serializables):
          - {"type": "delta", "text": "..."}             texto incremental del LLM
          - {"type": "tool",  "name": "buscar_..."}      el LLM va a ejecutar una herramienta
          - {"type": "centros", "items": [...]}          centros estructurados (con coords)
          - {"type": "done",  "herramientas_usadas": [...]}
          - {"type": "error", "message": "..."}
        """
        mensajes = list(historial)
        mensajes.append({"role": "user", "content": mensaje_usuario})

        herramientas_usadas: list[str] = []
        ultimos_centros: dict[str, dict] = {}

        for _ in range(MAX_ITERACIONES):
            with self._cliente.messages.stream(
                model=settings.anthropic_model,
                max_tokens=1024,
                system=PROMPT_SISTEMA,
                tools=catalogo_tools.definiciones_para_llm(),
                messages=mensajes,
            ) as stream:
                for fragmento in stream.text_stream:
                    if fragmento:
                        yield {"type": "delta", "text": fragmento}
                final = stream.get_final_message()

            if final.stop_reason == "tool_use":
                mensajes.append({"role": "assistant", "content": final.content})

                resultados_tool: list[dict] = []
                for bloque in final.content:
                    if bloque.type == "tool_use":
                        herramientas_usadas.append(bloque.name)
                        yield {"type": "tool", "name": bloque.name}
                        salida = catalogo_tools.ejecutar(bloque.name, bloque.input, self._repo)
                        # Cada nueva busqueda reemplaza los centros previos
                        if bloque.name == "buscar_profesionales":
                            ultimos_centros = {}
                            _agregar_centros(ultimos_centros, salida)
                            # Enriquecer con profesionales y consul del repo (fuera del tool_result
                            # para no saturar el contexto del LLM)
                            for cid, card in ultimos_centros.items():
                                centro = self._repo.obtener_centro(cid)
                                if centro:
                                    if centro.consul and not card.get("consul"):
                                        card["consul"] = centro.consul
                                    if centro.fact and not card.get("fact"):
                                        card["fact"] = centro.fact
                                    card["preferente"] = centro.preferente
                                if centro and centro.profesionales:
                                    esps_card = set(card.get("especialidades") or [])
                                    if esps_card:
                                        profs = [
                                            p for p in centro.profesionales
                                            if any(e in esps_card for e in p.especialidades)
                                        ]
                                    else:
                                        profs = list(centro.profesionales)
                                    if profs:
                                        card["profesionales"] = [p.model_dump() for p in profs]
                        resultados_tool.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": bloque.id,
                                "content": _serializar(salida),
                            }
                        )

                mensajes.append({"role": "user", "content": resultados_tool})
                continue

            # Respuesta final del modelo: preferentes primero, resto por distancia
            if ultimos_centros:
                def _clave_distancia(c: dict) -> tuple:
                    d = c.get("distancia_km")
                    return (d is None, d or 0)

                preferentes = sorted(
                    [c for c in ultimos_centros.values() if c.get("preferente")],
                    key=_clave_distancia,
                )
                normales = sorted(
                    [c for c in ultimos_centros.values() if not c.get("preferente")],
                    key=_clave_distancia,
                )

                if preferentes:
                    yield {"type": "preferentes", "items": preferentes}
                yield {"type": "centros", "items": normales[:15]}
            yield {"type": "done", "herramientas_usadas": herramientas_usadas}
            return

        yield {
            "type": "error",
            "message": "Limite de iteraciones alcanzado. Reformula la pregunta, por favor.",
        }


def _agregar_centros(acumulado: dict[str, dict], salida_tool: dict) -> None:
    """Deduplica `profesionales` por id de centro y agrupa especialidades."""
    profesionales = salida_tool.get("profesionales", [])
    for p in profesionales:
        cid = p.get("id")
        if not cid:
            continue
        if cid not in acumulado:
            acumulado[cid] = {
                "id": cid,
                "nombre": p.get("centro") or p.get("nombre"),
                "direccion": p.get("direccion"),
                "poblacion": p.get("poblacion"),
                "provincia": p.get("provincia"),
                "codigo_postal": p.get("codigo_postal"),
                "telefono": p.get("telefono"),
                "latitud": p.get("latitud"),
                "longitud": p.get("longitud"),
                "distancia_km": p.get("distancia_km"),
                "especialidades": [],
                "reserva_online": p.get("reserva_online"),
                "consul": None,
                "fact": None,
            }
        esp = p.get("especialidad")
        if esp and esp not in acumulado[cid]["especialidades"]:
            acumulado[cid]["especialidades"].append(esp)


def _serializar(salida: dict) -> str:
    """Convierte la salida de una herramienta en texto JSON para enviarla al modelo."""
    import json

    return json.dumps(salida, ensure_ascii=False, default=str)
