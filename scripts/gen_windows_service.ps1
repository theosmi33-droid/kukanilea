#!/usr/bin/env pwsh
$ServiceName = "KUKANILEA"
$WorkDir = "C:\\kukanilea"
$PythonExe = "$WorkDir\\.venv\\Scripts\\python.exe"
$Entry = "$WorkDir\\kukanilea_server.py"

Write-Output "# Review and run in elevated PowerShell"
Write-Output "sc.exe stop $ServiceName"
Write-Output "sc.exe delete $ServiceName"
Write-Output "sc.exe create $ServiceName binPath= '\"$PythonExe\" \"$Entry\"' start= auto"
Write-Output "sc.exe description $ServiceName 'KUKANILEA always-on service'"
Write-Output "sc.exe start $ServiceName"
