# =============================================================================
# Infalette — PowerShell runner for Windows.
#
# Mirrors ./run.sh. Use this from a normal PowerShell (no admin needed).
#
# Usage:
#   .\run.ps1           # full stack
#   .\run.ps1 backend   # only api + workers
#   .\run.ps1 web       # only the three frontends
#   .\run.ps1 stop      # stop everything we started
#   .\run.ps1 status    # report service health
# =============================================================================
[CmdletBinding()]
param(
  [ValidateSet('all','backend','web','stop','down','status','')]
  [string]$Command = 'all'
)

$ErrorActionPreference = 'Stop'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

$Venv = Join-Path $ScriptDir '.venv'
$Python = Join-Path $Venv 'Scripts\python.exe'
$Pip = Join-Path $Venv 'Scripts\pip.exe'
$RedisCli = Join-Path $Venv 'Scripts\redis-cli.exe'
$RedisSrv = Join-Path $Venv 'Scripts\redis-server.exe'
$RedisDir = Join-Path $env:USERPROFILE '.local\infalette\redis'
$RedisPort = 6379
$LogsDir = Join-Path $ScriptDir 'logs'
$PidsFile = Join-Path $ScriptDir '.run.pids'

New-Item -ItemType Directory -Force -Path $LogsDir, $RedisDir | Out-Null

function Log($msg)  { Write-Host "[run] $msg" -ForegroundColor Cyan }
function Ok($msg)   { Write-Host "[ ok] $msg" -ForegroundColor Green }
function Warn($msg) { Write-Host "[warn] $msg" -ForegroundColor Yellow }
function Err($msg)  { Write-Host "[fail] $msg" -ForegroundColor Red }

# Activate venv
if (-not (Test-Path $Python)) {
  Err ".venv not found at $Venv"
  exit 1
}
& "$Venv\Scripts\Activate.ps1"

function Stop-All {
  if (Test-Path $PidsFile) {
    Get-Content $PidsFile | ForEach-Object {
      $pid_ = $_
      if ($pid_ -and (Get-Process -Id $pid_ -ErrorAction SilentlyContinue)) {
        Stop-Process -Id $pid_ -Force -ErrorAction SilentlyContinue
      }
    }
    Remove-Item $PidsFile -Force -ErrorAction SilentlyContinue
  }
  Get-Process -Name 'uvicorn','celery','next' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
  if (Test-Path $RedisCli) {
    & $RedisCli -p $RedisPort shutdown nosave 2>$null
  }
  Ok "Stopped."
}

function Status {
  Log "Service status:"
  $ports = @(8000, 3000, 3001, 3002)
  foreach ($p in $ports) {
    $conn = Test-NetConnection -ComputerName localhost -Port $p -WarningAction SilentlyContinue
    if ($conn.TcpTestSucceeded) { Ok "  Port $p is listening" }
    else { Err "  Port $p is closed" }
  }
  if (Test-Path $RedisCli) {
    $r = & $RedisCli -p $RedisPort ping 2>$null
    if ($r -eq 'PONG') { Ok "  Redis: PONG" } else { Err "  Redis: down" }
  }
}

function Start-Infra-Local {
  Warn "Docker fallback path is best-effort on Windows. Assuming native Redis."
  if (-not (Test-Path $RedisSrv)) {
    Log "Installing redislite to get redis-server.exe"
    & $Pip install --quiet redislite
  }
  if (-not (Test-Path $RedisCli)) {
    Err "redis-cli.exe still missing after install"
    exit 1
  }
  $test = & $RedisCli -p $RedisPort ping 2>$null
  if ($test -eq 'PONG') { Ok "Redis already running"; return }
  Log "Starting redis-server on :$RedisPort"
  Start-Process -FilePath $RedisSrv -ArgumentList @(
    "--port", $RedisPort,
    "--bind", "127.0.0.1",
    "--dir", $RedisDir,
    "--logfile", (Join-Path $RedisDir 'redis.log'),
    "--save", "60", "1000"
  ) -WindowStyle Hidden
  Start-Sleep -Seconds 1
  $tries = 10
  while ($tries -gt 0) {
    if ((& $RedisCli -p $RedisPort ping 2>$null) -eq 'PONG') { Ok "Redis up"; return }
    Start-Sleep -Milliseconds 500
    $tries--
  }
  Err "Redis failed to start"
  exit 1
}

function Install-Python-Deps {
  Log "Installing Python deps (editable)"
  Get-ChildItem -Path $ScriptDir -Recurse -Directory -Filter __pycache__ |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
  & $Pip install --quiet -e packages/database -e packages/config -e packages/validation `
    -e packages/auth -e packages/commerce -e packages/automation `
    -e packages/analytics -e packages/seo -e packages/integrations `
    -e apps
  & $Pip install --quiet redislite
  Ok "Python deps installed"
}

function Run-Migrations {
  Push-Location (Join-Path $ScriptDir 'packages\database')
  & "$Venv\Scripts\alembic.exe" upgrade head
  Pop-Location
  Ok "Migrations applied"
}

function Launch-Bg($name, $cmd) {
  $logfile = Join-Path $LogsDir "$name.log"
  Log "  starting $name (logs: $logfile)"
  $proc = Start-Process -FilePath 'cmd.exe' -ArgumentList "/c $cmd >> `"$logfile`" 2>&1" `
    -WindowStyle Hidden -PassThru
  Add-Content -Path $PidsFile -Value $proc.Id
}

function Start-Backend {
  Log "Starting backend"
  Launch-Bg api "$Python -m uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 --reload"
  Launch-Bg workers "$Python -m celery -A apps.workers.main worker --loglevel=info"
}

function Start-Web {
  Log "Starting frontends"
  Launch-Bg storefront "cd apps\storefront && pnpm dev --port 3000"
  Launch-Bg admin "cd apps\admin && pnpm dev --port 3001"
  Launch-Bg platform-admin "cd apps\platform-admin && pnpm dev --port 3002"
}

function Wait-For-Http($url, $name) {
  Log "Waiting for $name at $url"
  $tries = 40
  while ($tries -gt 0) {
    try {
      Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop | Out-Null
      Ok "$name is up"
      return
    } catch {}
    Start-Sleep -Seconds 1
    $tries--
  }
  Warn "$name did not respond in time"
}

switch ($Command) {
  'stop'   { Stop-All; exit 0 }
  'down'   { Stop-All; Ok "Torn down."; exit 0 }
  'status' { Status; exit 0 }
  'backend' {
    Stop-All
    Install-Python-Deps
    Start-Infra-Local
    Run-Migrations
    Start-Backend
    Wait-For-Http 'http://localhost:8000/health' 'API'
    Log "Backend running. Press Ctrl-C to stop."
    while ($true) { Start-Sleep -Seconds 60 }
  }
  'web' {
    Stop-All
    Start-Web
    Wait-For-Http 'http://localhost:3000' 'Storefront'
    while ($true) { Start-Sleep -Seconds 60 }
  }
  default {
    Stop-All
    Install-Python-Deps
    Start-Infra-Local
    Run-Migrations
    Start-Backend
    Start-Web
    Wait-For-Http 'http://localhost:8000/health' 'API'
    Wait-For-Http 'http://localhost:3000' 'Storefront'
    @"

  Storefront:      http://localhost:3000/demo-store
  Admin:           http://localhost:3001   (owner@demo.test / demo1234)
  Platform admin:  http://localhost:3002
  API docs:        http://localhost:8000/api/v1/docs

  Stop:            .\run.ps1 stop

"@
    while ($true) { Start-Sleep -Seconds 60 }
  }
}
