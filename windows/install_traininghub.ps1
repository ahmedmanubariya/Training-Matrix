$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $PSScriptRoot
$InstallRoot = Join-Path $env:LOCALAPPDATA 'TrainingHub'
$DataRoot = Join-Path $env:LOCALAPPDATA 'TrainingHubData'
$Venv = Join-Path $InstallRoot '.venv'
$Desktop = [Environment]::GetFolderPath('Desktop')
$ShortcutPath = Join-Path $Desktop 'TrainingHub.lnk'

Write-Host 'Installing TrainingHub...' -ForegroundColor Cyan

if (-not (Get-Command py -ErrorAction SilentlyContinue) -and -not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host 'Python 3.10+ is required. Install Python from python.org and tick Add Python to PATH.' -ForegroundColor Red
    exit 1
}

if (Test-Path $InstallRoot) {
    Remove-Item $InstallRoot -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $InstallRoot | Out-Null
New-Item -ItemType Directory -Force -Path $DataRoot | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $DataRoot 'uploads') | Out-Null

Get-ChildItem $RepoRoot -Force | Where-Object {
    $_.Name -notin @('.git', '.venv', 'instance', 'uploads', 'traininghub.db')
} | Copy-Item -Destination $InstallRoot -Recurse -Force

$PythonCmd = if (Get-Command py -ErrorAction SilentlyContinue) { 'py' } else { 'python' }
& $PythonCmd -m venv $Venv
& (Join-Path $Venv 'Scripts\python.exe') -m pip install --upgrade pip
& (Join-Path $Venv 'Scripts\python.exe') -m pip install -r (Join-Path $InstallRoot 'requirements.txt')

$EnvFile = Join-Path $InstallRoot '.env.local.ps1'
@"
`$env:SECRET_KEY = '$(New-Guid)$(New-Guid)'
`$env:DATABASE = '$($DataRoot.Replace("'","''"))\traininghub.db'
`$env:UPLOAD_FOLDER = '$($DataRoot.Replace("'","''"))\uploads'
`$env:HOST = '127.0.0.1'
`$env:PORT = '5000'
`$env:FLASK_DEBUG = '0'
`$env:ALERT_THRESHOLD = '80'
`$env:APPROVED_DOCS_ROOT = ''
"@ | Set-Content -Path $EnvFile -Encoding UTF8

$Launcher = Join-Path $InstallRoot 'Launch TrainingHub.cmd'
@"
@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0windows\launch_traininghub.ps1"
"@ | Set-Content -Path $Launcher -Encoding ASCII

$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $Launcher
$Shortcut.WorkingDirectory = $InstallRoot
$Shortcut.Description = 'Open Eaststone TrainingHub'
$Shortcut.Save()

Write-Host ''
Write-Host 'TrainingHub installed successfully.' -ForegroundColor Green
Write-Host "Desktop shortcut created: $ShortcutPath"
Write-Host 'Opening TrainingHub now...'
Start-Process $Launcher
