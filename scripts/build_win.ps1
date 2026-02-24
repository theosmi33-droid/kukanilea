# KUKANILEA Windows Build Script (v1.5.0 Gold)

Write-Host "🛠 Starte Windows Build Prozess..." -ForegroundColor Cyan

# 1. Environment vorbereiten
if (!(Test-Path ".venv")) {
    Write-Error "❌ Virtual Environment nicht gefunden!"
    exit 1
}

& .venv\Scripts\activate.ps1
pip install pyinstaller

# 2. PyInstaller ausführen
Write-Host "📦 Bündele Applikation via PyInstaller..." -ForegroundColor Yellow
pyinstaller --clean KUKANILEA.spec

# 3. Code-Signing (Placeholder)
# & "C:\Program Files (x86)\Windows Kits\10\bin\x64\signtool.exe" sign /f MyCert.pfx /p MyPassword /tr http://timestamp.digicert.com /td sha256 /fd sha256 dist\KUKANILEA\KUKANILEA.exe

# 4. MSI Installer (Placeholder für WiX oder InnoSetup)
Write-Host "💿 Hinweis: Für ein fertiges MSI wird WiX Toolset oder InnoSetup empfohlen."
Write-Host "✅ Binary verfügbar unter: dist\KUKANILEA\KUKANILEA.exe" -ForegroundColor Green
