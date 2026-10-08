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

echo Iniciando o servidor web e abrindo o navegador...
.venv\Scripts\python.exe -m src.main --web --port 8000

pause
