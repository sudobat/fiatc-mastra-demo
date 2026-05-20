# Proyecto: POC Agente Guía Médica FIATC

Contexto que Claude Code debe tener siempre presente al trabajar en este repositorio.

## Qué es esto

POC de un agente conversacional que responde preguntas sobre el cuadro médico de FIATC en lenguaje natural. Sustituye al buscador clásico de https://guiamedica.fiatc.es/ por un chat que entiende intención, mapea síntomas a especialidades y devuelve recomendaciones.

## Estado actual

- **Modo POC**: el agente lee los datos de un fichero JSON local (`data/cuadro_medico_sample.json`).
- **NO** conecta a ningún sistema interno de FIATC.
- **NO** usa datos reales de asegurados ni profesionales.
- Los datos del fichero son sintéticos, generados sólo para la demo.

## Objetivo de la integración futura

El agente está diseñado con un patrón Repository: cuando la API interna de FIATC esté disponible, basta con implementar `ApiInternaFiatcGuiaMedicaRepository` y cambiar la variable de entorno `GUIA_MEDICA_BACKEND=api`. El resto del agente no se toca.

## Stack

- Backend: Python 3.11+, FastAPI, SDK oficial de Anthropic (Claude).
- Frontend: JavaScript vanilla, HTML, CSS. Sin frameworks.
- Persistencia (futura): SQL Server on-premise. En la POC: fichero JSON.

## Convenciones de código

- Tipado estricto con type hints. Pydantic para los esquemas de las herramientas.
- Una herramienta = un fichero en `backend/app/agent/tools/`.
- Cada herramienta expone `definicion` (esquema JSON para el LLM) y `ejecutar(args)`.
- Tests unitarios por cada herramienta y repositorio.
- Comentarios y mensajes de error en castellano (es el idioma del cliente final).

## Restricciones que Claude Code debe respetar

- **Nunca** subir credenciales reales. Sólo `.env.example` con valores ficticios.
- **Nunca** procesar ni guardar datos reales de asegurados. Si en algún momento se introducen datos reales, pararse y avisar.
- No introducir librerías nuevas sin justificarlo.
- Mantener el código en castellano para variables de dominio (profesionales, especialidades, provincias) y en inglés para conceptos técnicos genéricos (orchestrator, repository, tool).

## Cómo arrancar la POC

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env   # editar y poner ANTHROPIC_API_KEY
uvicorn app.main:app --reload
```

Después abrir `frontend/demo.html` en el navegador.

## Roadmap de la POC

1. Esqueleto del proyecto.
2. Implementar `mapear_sintoma_a_especialidad` con embeddings o lista curada.
3. Mejorar la geolocalización (ahora es un dict mock).
4. Añadir más casos de prueba al fichero de datos.
5. Tests unitarios.
6. Cuando la API interna esté disponible, implementar `ApiInternaFiatcGuiaMedicaRepository`.
