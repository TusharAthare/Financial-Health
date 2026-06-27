# Starts Postgres, Redis, Django API, and Vite frontend.

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$BackendPort = 8000
$FrontendPort = 4200

$BackendProcess = $null
$FrontendProcess = $null
$CeleryProcess = $null

function Stop-ProcessOnPort {
    param([int]$Port)

    $processIds = @()
    try {
        $processIds = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
            Select-Object -ExpandProperty OwningProcess -Unique
    } catch {
        $processIds = netstat -ano |
            Select-String ":$Port\s+.*LISTENING" |
            ForEach-Object {
                if ($_.Line -match '\s+(\d+)\s*$') { [int]$Matches[1] }
            } |
            Select-Object -Unique
    }

    foreach ($processId in $processIds) {
        if ($processId -and $processId -ne 0 -and $processId -ne $PID) {
            Write-Host "Stopping process $processId on port $Port"
            Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
        }
    }
    Start-Sleep -Milliseconds 500
}

function Stop-DevProcesses {
    if ($FrontendProcess -and -not $FrontendProcess.HasExited) {
        Stop-Process -Id $FrontendProcess.Id -Force -ErrorAction SilentlyContinue
    }
    if ($CeleryProcess -and -not $CeleryProcess.HasExited) {
        Stop-Process -Id $CeleryProcess.Id -Force -ErrorAction SilentlyContinue
    }
    if ($BackendProcess -and -not $BackendProcess.HasExited) {
        Stop-Process -Id $BackendProcess.Id -Force -ErrorAction SilentlyContinue
    }
}

function Refresh-Path {
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
        [System.Environment]::GetEnvironmentVariable("Path", "User")
}

function Get-DockerExe {
    Refresh-Path
    $cmd = Get-Command docker -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }

    $defaultPath = "C:\Program Files\Docker\Docker\resources\bin\docker.exe"
    if (Test-Path $defaultPath) {
        $dockerDir = Split-Path $defaultPath
        $env:Path = "$dockerDir;$env:Path"
        return $defaultPath
    }
    return $null
}

function Get-NpmCmdPath {
    Refresh-Path
    $npmCmd = Get-Command npm.cmd -ErrorAction SilentlyContinue
    if ($npmCmd) { return $npmCmd.Source }

    $npmCmd = Get-Command npm -ErrorAction SilentlyContinue
    if ($npmCmd) { return $npmCmd.Source }

    return $null
}

function Start-NpmDev {
    param([string]$WorkingDirectory)

    $npmPath = Get-NpmCmdPath
    if (-not $npmPath) {
        throw "npm is not installed. Restart PowerShell after installing Node.js, then run .\run.ps1 again."
    }

    if ($npmPath -like "*.cmd") {
        return Start-Process `
            -FilePath "cmd.exe" `
            -ArgumentList "/c", "`"$npmPath`" run dev" `
            -WorkingDirectory $WorkingDirectory `
            -PassThru `
            -NoNewWindow
    }

    return Start-Process `
        -FilePath $npmPath `
        -ArgumentList "run", "dev" `
        -WorkingDirectory $WorkingDirectory `
        -PassThru `
        -NoNewWindow
}

function Start-DockerDesktopIfNeeded {
    $dockerExe = Get-DockerExe
    if (-not $dockerExe) {
        throw "Docker is not installed. Install Docker Desktop, then run this script again."
    }

    & $dockerExe version *> $null
    if ($LASTEXITCODE -eq 0) { return $dockerExe }

    $desktopExe = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    if (Test-Path $desktopExe) {
        Write-Host "Starting Docker Desktop (first launch can take 1-2 minutes)..."
        Start-Process $desktopExe | Out-Null
    }

    for ($i = 1; $i -le 60; $i++) {
        Start-Sleep -Seconds 3
        & $dockerExe info *> $null
        if ($LASTEXITCODE -eq 0) { return $dockerExe }
    }

    throw "Docker Desktop did not start in time. Open Docker Desktop manually, wait until it is running, then run .\run.ps1 again."
}

trap {
    Stop-DevProcesses
    throw $_
}

Refresh-Path

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
}

poetry config virtualenvs.in-project true | Out-Null
if (-not (Test-Path ".venv")) {
    poetry install
}

$PythonExe = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
    throw "Missing .venv\Scripts\python.exe - run: poetry install"
}

$DockerExe = Start-DockerDesktopIfNeeded

& $DockerExe compose up -d db redis

$maxAttempts = 30
for ($i = 1; $i -le $maxAttempts; $i++) {
    & $DockerExe compose exec -T db pg_isready -U postgres -d financial_health *> $null
    if ($LASTEXITCODE -eq 0) { break }
    if ($i -eq $maxAttempts) { throw "Postgres did not start in time." }
    Start-Sleep -Seconds 2
}

for ($i = 1; $i -le $maxAttempts; $i++) {
    $ping = & $DockerExe compose exec -T redis redis-cli ping 2>$null
    if ($ping -match "PONG") { break }
    if ($i -eq $maxAttempts) { throw "Redis did not start in time." }
    Start-Sleep -Seconds 2
}

& $PythonExe manage.py migrate --noinput

Stop-ProcessOnPort -Port $BackendPort

$CeleryProcess = Start-Process `
    -FilePath $PythonExe `
    -ArgumentList "-m", "celery", "-A", "api", "worker", "--loglevel=info", "--pool=solo" `
    -WorkingDirectory $PSScriptRoot `
    -PassThru `
    -NoNewWindow

Start-Sleep -Seconds 2
if ($CeleryProcess.HasExited) {
    throw "Celery worker failed to start."
}

$BackendProcess = Start-Process `
    -FilePath $PythonExe `
    -ArgumentList "manage.py", "runserver", "0.0.0.0:$BackendPort" `
    -WorkingDirectory $PSScriptRoot `
    -PassThru `
    -NoNewWindow

Start-Sleep -Seconds 2
if ($BackendProcess.HasExited) {
    throw "Django failed to start."
}

if (-not (Test-Path "frontend\node_modules")) {
    Push-Location frontend
    & npm.cmd install
    Pop-Location
}

Stop-ProcessOnPort -Port $FrontendPort

$FrontendProcess = Start-NpmDev -WorkingDirectory (Join-Path $PSScriptRoot "frontend")

Write-Host ""
Write-Host "Running:"
Write-Host "  Frontend  http://localhost:$FrontendPort"
Write-Host "  API       http://127.0.0.1:$BackendPort"
Write-Host "  Celery    background worker (CSV parsing)"
Write-Host ""
Write-Host "Ctrl+C to stop API, Celery, and frontend."
Write-Host ""

try {
    Wait-Process -Id $FrontendProcess.Id
}
finally {
    Stop-DevProcesses
}
