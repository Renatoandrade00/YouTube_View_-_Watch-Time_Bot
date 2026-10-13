@echo off
chcp 65001 > nul
title YouTube Watch-Time Bot - Painel Web

echo ========================================================
echo   YouTube View ^& Watch-Time Bot - Inicializador Web
echo ========================================================
echo.

IF NOT EXIST ".venv\Scripts\python.exe" (
    echo [ERRO] Ambiente virtual .venv nao encontrado!
    echo Certifique-se de executar o setup do projeto antes de iniciar.
    pause
    exit /b 1
)

:: Verifica se a porta 8000 já está em uso por uma instância anterior e libera
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000" ^| findstr "LISTENING"') do (
    echo [INFO] Porta 8000 ocupada por instancia anterior (PID %%a). Finalizando processo...
    taskkill /F /PID %%a >nul 2>&1
    timeout /t 1 >nul
)

echo Iniciando o servidor web e abrindo o navegador...
.venv\Scripts\python.exe -m src.main --web --port 8000

pause
