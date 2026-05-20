@echo off
title Agente Guia Medica FIATC
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

if exist ".venv\Scripts\python.exe" (
    set UVICORN_CMD=.venv\Scripts\python.exe -m uvicorn
) else (
    set UVICORN_CMD=python -m uvicorn
)

echo  Arrancando servidor backend...
start "Servidor Guia Medica" cmd /k "%UVICORN_CMD% app.main:app --reload --port 8000"

echo  Esperando a que el servidor este listo...
:esperar
timeout /t 2 /nobreak > nul
curl -s http://localhost:8000/health > nul 2>&1
if errorlevel 1 goto esperar

echo  Servidor listo. Abriendo navegador...
start "" "%~dp0frontend\demo.html"

echo.
echo  El servidor esta activo en http://localhost:8000
echo  Cierra la ventana "Servidor Guia Medica" para detenerlo.
echo.
pause
