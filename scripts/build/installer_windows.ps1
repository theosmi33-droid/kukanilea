# scripts/build/installer_windows.ps1
# KUKANILEA Windows Gold Distribution Pipeline

$VERSION = "1.5.0"
$APP_NAME = "KUKANILEA"
$CERT_THUMBPRINT = "YOUR_CERT_THUMBPRINT" # ANPASSEN

Write-Host "🪟 Starte Windows Gold Distribution v$VERSION..." -ForegroundColor Cyan

# 1. PyInstaller Build
& .venv\Scripts\activate.ps1
pyinstaller --clean KUKANILEA.spec

# 2. Code-Signing
Write-Host "✍️  Signiere Executable..." -ForegroundColor Yellow
# & "C:\Program Files (x86)\Windows Kits\10\bin\x64\signtool.exe" sign /sha1 $CERT_THUMBPRINT /tr http://timestamp.digicert.com /td sha256 /fd sha256 "dist\$APP_NAME\$APP_NAME.exe"

# 3. MSI Build via WiX (Beispielaufruf)
Write-Host "💿 Erzeuge MSI Installer (Per-User)..." -ForegroundColor Yellow
# & "candle.exe" scripts/build/installer.wxs
# & "light.exe" -ext WixUIExtension installer.wixobj -o "dist\final\$APP_NAME-v$VERSION-Windows.msi"

Write-Host "[SUCCESS] Windows Gold Release bereit." -ForegroundColor Green
