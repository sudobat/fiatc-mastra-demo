# POC — Agente Guía Médica FIATC

Prueba de concepto de un agente conversacional sobre el cuadro médico de FIATC, autónomo y desconectado de cualquier sistema interno. Pensado para construirse y mantenerse con Claude Code.

## Estructura

```
poc-guia-medica-agent/
├── CLAUDE.md                    # Contexto del proyecto para Claude Code
├── README.md
├── backend/
│   ├── requirements.txt
│   ├── .env.example
│   └── app/
│       ├── main.py              # FastAPI app
│       ├── config.py
│       ├── agent/
│       │   ├── orchestrator.py  # Bucle de tool-calling con Claude
│       │   ├── prompts.py       # Prompt del sistema
│       │   └── tools/
│       │       ├── __init__.py
│       │       ├── buscar_profesionales.py
│       │       ├── obtener_centro.py
│       │       ├── listar_especialidades.py
│       │       ├── mapear_sintoma.py
│       │       └── geolocalizar.py
│       └── repositories/
│           ├── __init__.py
│           ├── base.py          # Interfaz GuiaMedicaRepository
│           ├── fichero_local.py # Implementación POC
│           └── api_interna.py   # Stub para producción
├── data/
│   └── cuadro_medico_sample.json
├── frontend/
│   ├── demo.html                # Página con el chat embebido
│   ├── chat-widget.js
│   └── chat-widget.css
└── scraping/
    └── extract.py               # Placeholder del script de scraping
```

## Arranque rápido

1. **Backend.**
   ```bash
   cd backend
   python -m venv .venv && source .venv/bin/activate    # o .venv\Scripts\activate en Windows
   pip install -r requirements.txt
   cp .env.example .env
   # editar .env y poner ANTHROPIC_API_KEY
   uvicorn app.main:app --reload --port 8000
   ```

2. **Frontend.** Abrir `frontend/demo.html` en el navegador (o servirlo con `python -m http.server 5500` desde `frontend/`).

3. **Probar.** Escribir en el chat preguntas como:
   - "Busco un cardiólogo en Barcelona"
   - "Necesito un traumatólogo en Madrid con reserva online"
   - "Tengo dolor de espalda fuerte, ¿qué especialista necesito?"

## Cómo está pensado para evolucionar

El agente nunca habla directamente con la fuente de datos: lo hace siempre a través de un **repositorio**. Hoy hay dos:

- `FicheroLocalGuiaMedicaRepository` — lee de `data/cuadro_medico_sample.json`. Es la implementación viva de la POC.
- `ApiInternaFiatcGuiaMedicaRepository` — esqueleto vacío que hay que rellenar cuando la API interna esté disponible.

Para cambiar de uno a otro:
```bash
# en .env
GUIA_MEDICA_BACKEND=local   # o 'api'
```

El resto del código no cambia.
