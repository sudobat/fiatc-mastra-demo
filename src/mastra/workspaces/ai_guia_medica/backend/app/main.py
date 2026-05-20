"""Punto de entrada FastAPI del backend del agente Guia Medica."""
from __future__ import annotations

import json

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.agent.orchestrator import Orchestrator
from app.config import settings

app = FastAPI(title="POC Agente Guia Medica FIATC", version="0.1.0")

# CORS abierto solo en POC. En produccion restringir a dominios FIATC.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

orchestrator = Orchestrator()


class MensajeHistorial(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    mensaje: str
    historial: list[MensajeHistorial] = []


class ChatResponse(BaseModel):
    respuesta: str
    herramientas_usadas: list[str]


@app.get("/health")
def health() -> dict:
    return {
        "estado": "ok",
        "backend": settings.guia_medica_backend,
        "modelo": settings.anthropic_model,
    }


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    historial_dict = [{"role": m.role, "content": m.content} for m in req.historial]
    resultado = orchestrator.responder(historial_dict, req.mensaje)
    return ChatResponse(**resultado)


@app.post("/chat/stream")
def chat_stream(req: ChatRequest) -> StreamingResponse:
    """Endpoint streaming (Server-Sent Events). Cada evento es un JSON en una linea `data: ...`."""
    historial_dict = [{"role": m.role, "content": m.content} for m in req.historial]

    def generar():
        try:
            for evento in orchestrator.responder_stream(historial_dict, req.mensaje):
                yield f"data: {json.dumps(evento, ensure_ascii=False)}\n\n"
        except Exception as e:  # noqa: BLE001
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        generar(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # desactiva buffering en proxies tipo nginx
        },
    )
