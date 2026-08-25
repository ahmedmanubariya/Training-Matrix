$ErrorActionPreference = 'Stop'
$InstallRoot = Split-Path -Parent $PSScriptRoot
$EnvFile = Join-Path $InstallRoot '.env.local.ps1'
$Python = Join-Path $InstallRoot '.venv\Scripts\python.exe'
$AppUrl = 'http://127.0.0.1:5000'

if (-not (Test-Path $Python)) {
    [System.Windows.Forms.MessageBox]::Show('TrainingHub is not installed correctly. Run the installer again.','TrainingHub') | Out-Null
    exit 1
}

if (Test-Path $EnvFile) { . $EnvFile }

$alreadyRunning = $false
try {
    $r = Invoke-WebRequest -Uri "$AppUrl/login" -UseBasicParsing -TimeoutSec 2
    if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500) { $alreadyRunning = $true }
} catch {}

if (-not $alreadyRunning) {
    $logDir = Join-Path $env:LOCALAPPDATA 'TrainingHubData\logs'
    New-Item -ItemType Directory -Force -Path $logDir | Out-Null
    $stdout = Join-Path $logDir 'traininghub-out.log'
    $stderr = Join-Path $logDir 'traininghub-error.log'
    Start-Process -FilePath $Python -ArgumentList 'app.py' -WorkingDirectory $InstallRoot -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr

    $ready = $false
    for ($i=0; $i -lt 30; $i++) {
        Start-Sleep -Milliseconds 500
        try {
            $r = Invoke-WebRequest -Uri "$AppUrl/login" -UseBasicParsing -TimeoutSec 1
            if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500) { $ready = $true; break }
        } catch {}
    }
    if (-not $ready) {
        Start-Process notepad.exe $stderr
        throw 'TrainingHub did not start. The error log has been opened.'
    }
}

Start-Process $AppUrl
