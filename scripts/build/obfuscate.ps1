Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "../..")
Set-Location $Root

$SrcDir = Join-Path $Root "app"
$OutRoot = Join-Path $Root "dist/obfuscated"
$OutDir = Join-Path $OutRoot "app"

if (!(Test-Path $SrcDir)) {
    throw "Missing source directory: $SrcDir"
}

New-Item -ItemType Directory -Force -Path $OutRoot | Out-Null
if (Test-Path $OutDir) {
    Remove-Item -Recurse -Force $OutDir
}

$PyArmor = Get-Command pyarmor -ErrorAction SilentlyContinue
if ($null -ne $PyArmor) {
    Write-Host "Obfuscating app/ with PyArmor..."
    & pyarmor gen --recursive --output $OutDir $SrcDir
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Obfuscation output: $OutDir"
    }
    else {
        Write-Warning "PyArmor failed (likely trial/license/runtime issue). Falling back to plain copy (no obfuscation)."
        if (Test-Path $OutDir) {
            Remove-Item -Recurse -Force $OutDir
        }
        Copy-Item -Recurse -Force $SrcDir $OutDir
        Write-Host "Copied source to: $OutDir"
    }
}
else {
    Write-Host "PyArmor not found. Falling back to plain copy (no obfuscation)."
    Copy-Item -Recurse -Force $SrcDir $OutDir
    Write-Host "Copied source to: $OutDir"
}
