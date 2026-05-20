@echo off
title Agente Guia Medica FIATC - Servidor
echo.
echo  =========================================
echo   Agente Guia Medica FIATC - POC
echo  =========================================
echo.

cd /d "%~dp0backend"

if not exist ".env" (
    echo  ERROR: Falta el fichero backend\.env
    echo  Copia backend\.env.example a backend\.env y pon tu ANTHROPIC_API_KEY
    echo.
    pause
    exit /b 1
)

echo  Comprobando instancias previas en el puerto 8000...
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":8000 " ^| findstr "LISTENING"') do (
    echo  Eliminando proceso %%P...
    taskkill /PID %%P /F >nul 2>&1
)
echo  Puerto 8000 libre.
echo.
echo  Servidor arrancando en http://localhost:8000
echo  Abre frontend\demo.html en el navegador una vez aparezca "Application startup complete"
echo  Pulsa Ctrl+C para detener.
echo.

if exist ".venv\Scripts\python.exe" (
    .venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
) else (
    python -m uvicorn app.main:app --reload --port 8000
)

echo.
echo  El servidor se ha detenido.
pause
