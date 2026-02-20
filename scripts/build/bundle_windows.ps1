Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "../..")
Set-Location $Root

$ObfApp = Join-Path $Root "dist/obfuscated/app"
if (!(Test-Path $ObfApp)) {
    & (Join-Path $PSScriptRoot "obfuscate.ps1")
}
if (!(Test-Path $ObfApp)) {
    throw "Missing obfuscated app directory: $ObfApp"
}

if ($null -eq (Get-Command pyinstaller -ErrorAction SilentlyContinue)) {
    throw "pyinstaller not found. Install build tools first."
}

$EntryPoint = Join-Path $Root "dist/_packaging_entrypoint_windows.py"
@"
from __future__ import annotations

if __name__ == "__main__":
    from app.desktop import main

    raise SystemExit(main())
"@ | Set-Content -Encoding UTF8 $EntryPoint

$DistExe = Join-Path $Root "dist/KUKANILEA.exe"
$DistDir = Join-Path $Root "dist/KUKANILEA"
$BuildDir = Join-Path $Root "build/KUKANILEA"
if (Test-Path $DistExe) { Remove-Item -Force $DistExe }
if (Test-Path $DistDir) { Remove-Item -Recurse -Force $DistDir }
if (Test-Path $BuildDir) { Remove-Item -Recurse -Force $BuildDir }

$Args = @(
    "--clean",
    "--noconfirm",
    "--name", "KUKANILEA",
    "--windowed",
    "--onefile",
    "--paths", (Join-Path $Root "dist/obfuscated"),
    "--paths", $Root,
    "--hidden-import", "kukanilea_core_v3_fixed",
    "--hidden-import", "webview",
    "--hidden-import", "webview.platforms.winforms",
    "--hidden-import", "webview.platforms.edgechromium",
    "--add-data", "templates;templates",
    "--add-data", "static;static",
    $EntryPoint
)

pyinstaller @Args

if (!(Test-Path $DistExe)) {
    throw "Expected executable not found: $DistExe"
}

Write-Host "Executable ready: $DistExe"
