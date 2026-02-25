@echo off
echo [KUKANILEA] Starting Development Server (Windows)...

if not exist .venv (
    echo [.venv] not found. Please run scripts\setup_windows.bat first.
    exit /b 1
)

call .venv\Scripts\activate.bat
set FLASK_ENV=development
set OLLAMA_ENABLED=1
python kukanilea_app.py
pause
