@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ── Certificate Creator ──────────────────────────
echo.

if not exist venv (
    echo Criando ambiente virtual...
    python -m venv venv
    if errorlevel 1 (
        echo ERRO: Python nao encontrado. Instale Python 3.10+ e tente novamente.
        pause
        exit /b 1
    )
)

call venv\Scripts\activate.bat

echo Instalando dependencias...
pip install -r requirements.txt -q
if errorlevel 1 (
    echo ERRO ao instalar dependencias.
    pause
    exit /b 1
)

echo.
echo Servidor iniciando em http://localhost:8001
echo Pressione Ctrl+C para parar.
echo.

timeout /t 2 /nobreak >nul
start "" "http://localhost:8001"

python run.py
pause
