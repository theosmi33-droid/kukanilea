param(
    [Parameter(Mandatory = $true)]
    [string]$TargetPath
)

if (!(Test-Path $TargetPath)) {
    Write-Error "Target not found: $TargetPath"
    exit 2
}

$signtool = Get-Command signtool -ErrorAction SilentlyContinue
if (-not $signtool) {
    Write-Host "[verify_distribution_windows] signtool not available. Manual verification required."
    Write-Host "Recommended command (on signed-build host): signtool verify /pa `"$TargetPath`""
    exit 3
}

Write-Host "[verify_distribution_windows] target=$TargetPath"
& $signtool.Path verify /pa $TargetPath
exit $LASTEXITCODE
