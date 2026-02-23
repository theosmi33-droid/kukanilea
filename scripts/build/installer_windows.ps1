Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "../..")
Set-Location $Root

$NSISPath = Join-Path $PSScriptRoot "kukanilea.nsi"
$DistExe = Join-Path $Root "dist/KUKANILEA.exe"

# 1. Check if the bundle exists
if (!(Test-Path $DistExe)) {
    Write-Host "Bundled executable not found at $DistExe. Running bundle_windows.ps1 first..." -ForegroundColor Yellow
    & (Join-Path $PSScriptRoot "bundle_windows.ps1")
}

# 2. Run NSIS
if ($null -eq (Get-Command makensis -ErrorAction SilentlyContinue)) {
    throw "NSIS (makensis.exe) not found. Please install NSIS and add it to your PATH."
}

Write-Host "Generating Windows Setup with NSIS..." -ForegroundColor Cyan
& makensis /V4 $NSISPath

$SetupFile = Get-ChildItem -Path (Join-Path $Root "dist") -Filter "KUKANILEA_Setup_v*.exe" | Sort-Object LastWriteTime -Descending | Select-Object -First 1

if ($null -eq $SetupFile) {
    throw "Setup generation failed. No installer found in dist/."
}

Write-Host "Windows Installer ready: $($SetupFile.FullName)" -ForegroundColor Green
