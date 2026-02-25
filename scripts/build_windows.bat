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
pyinstaller --noconfirm --onedir --windowed --name "KUKANILEA" ^
    --add-data "app;app" ^
    --hidden-import "flask" ^
    --hidden-import "waitress" ^
    kukanilea_server.py

echo [SUCCESS] Build finished. Check the 'dist/KUKANILEA' folder.
pause
