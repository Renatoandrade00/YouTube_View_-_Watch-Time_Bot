@echo off
cd /d "%~dp0"
title YouTube Watch-Time Bot - Painel Web

echo ========================================================
echo   YouTube View ^& Watch-Time Bot - Inicializador Web
echo ========================================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [ERRO] Ambiente virtual .venv nao encontrado!
    echo Certifique-se de executar o setup do projeto antes de iniciar.
    pause
    exit /b 1
)

for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000" ^| findstr "LISTENING"') do (
    echo [INFO] Liberando porta 8000 - PID %%a
    taskkill /F /PID %%a >nul 2>&1
)

echo Iniciando o servidor web e abrindo o navegador...
.venv\Scripts\python.exe -m src.main --web --port 8000

pause
