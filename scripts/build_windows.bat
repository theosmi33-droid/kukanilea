@echo off
echo [KUKANILEA] Starting Build Sequence (Windows)...

if not exist .venv (
    echo Creating virtual environment...
    python -m venv .venv
)

call .venv\Scripts\activate.bat
echo Installing dependencies...
pip install -r requirements.txt
pip install pyinstaller

echo Running PyInstaller...
pyinstaller --noconfirm --clean --onefile --name "KUKANILEA" ^
    --add-data "app;app" ^
    run.py

if not exist dist\KUKANILEA.exe (
    echo [ERROR] Build finished but dist\KUKANILEA.exe not found.
    exit /b 1
)

echo [SUCCESS] Build finished. Check the 'dist\KUKANILEA.exe' file.
pause
