# Real-Pepper launcher for OmniLLM (PowerShell, run from repo root).
#
# What it does
# ------------
# 1. Pre-flight checks: Python 3 venv, .env keys, Ollama, ping to Pepper.
# 2. Spawns the AI server (Python 3) in a new PowerShell window.
# 3. Spawns the NAOqi bridge server (Python 2.7) in another window, pointed
#    at Pepper's LAN IP at port 9559.
# 4. Waits until both /health and /ping report ok, then prints a green
#    "READY" line and the exact command to run the subject experiment.
#
# It does NOT run the experiment itself -- that's a deliberate choice so you
# can verify the windows look healthy before kicking off a real participant.
#
# Usage
# -----
#     scripts\pepper_demo\launch_real_pepper.ps1 -PepperIp 192.168.1.42
#
#     # Optional override:
#     scripts\pepper_demo\launch_real_pepper.ps1 -PepperIp 192.168.1.42 -BridgePort 6000

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string] $PepperIp,

    [int] $RobotPort = 9559,
    [int] $BridgePort = 6000,
    [int] $ServerPort = 5000
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Get-Item $PSScriptRoot).Parent.Parent.FullName
Set-Location $RepoRoot

Write-Host "OmniLLM real-Pepper launcher" -ForegroundColor Cyan
Write-Host "Repo: $RepoRoot"
Write-Host "Pepper: $PepperIp`:$RobotPort"
Write-Host "AI server: http://0.0.0.0:$ServerPort"
Write-Host "NAOqi bridge: http://0.0.0.0:$BridgePort"
Write-Host ""

# 1. Pre-flight checks.

$VenvPython = Join-Path $RepoRoot "venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    throw "venv Python not found at $VenvPython. Run: python -m venv venv"
}

$Py27 = "C:\Python27\python.exe"
if (-not (Test-Path $Py27)) {
    throw "Python 2.7 not found at $Py27 -- needed for the NAOqi bridge."
}

if (-not (Test-Path (Join-Path $RepoRoot ".env"))) {
    Write-Warning ".env file not found -- LLM calls will fail without API keys."
}

Write-Host "Pinging Pepper at $PepperIp ..."
if (-not (Test-Connection -ComputerName $PepperIp -Count 1 -Quiet)) {
    Write-Warning "Cannot ping $PepperIp. The launcher continues, but the bridge may fail."
} else {
    Write-Host "  OK -- Pepper is reachable on the LAN." -ForegroundColor Green
}

Write-Host "Checking Ollama (needed for Condition B) ..."
try {
    $ollama = Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -UseBasicParsing -TimeoutSec 2
    if ($ollama.StatusCode -eq 200) {
        Write-Host "  OK -- Ollama responding." -ForegroundColor Green
    }
} catch {
    Write-Warning "Ollama unreachable on 11434. Condition B will fall back to the cloud."
}

# 2. Launch the AI server (Python 3).

Write-Host ""
Write-Host "Starting AI server in a new window ..." -ForegroundColor Cyan
$serverCmd = "Set-Location '$RepoRoot'; & '$VenvPython' -m omnillm.server.app --host 0.0.0.0 --port $ServerPort"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $serverCmd | Out-Null

# 3. Launch the NAOqi bridge (Python 2.7).

Write-Host "Starting NAOqi bridge in a new window ..." -ForegroundColor Cyan
$bridgeScript = Join-Path $RepoRoot "omnillm\server\naoqi_bridge_server.py"
$bridgeCmd = "Set-Location '$RepoRoot'; & '$Py27' '$bridgeScript' --robot-ip $PepperIp --robot-port $RobotPort --bind 0.0.0.0 --bridge-port $BridgePort"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $bridgeCmd | Out-Null

# 4. Wait for both services to come up.

Write-Host ""
Write-Host "Waiting for /health and /ping ..." -ForegroundColor Cyan
$deadline = (Get-Date).AddSeconds(40)
$serverOk = $false
$bridgeOk = $false
while ((Get-Date) -lt $deadline -and -not ($serverOk -and $bridgeOk)) {
    Start-Sleep -Seconds 2
    if (-not $serverOk) {
        try {
            $r = Invoke-WebRequest -Uri "http://127.0.0.1:$ServerPort/health" -UseBasicParsing -TimeoutSec 2
            if ($r.StatusCode -eq 200) { $serverOk = $true }
        } catch { }
    }
    if (-not $bridgeOk) {
        try {
            $r = Invoke-WebRequest -Uri "http://127.0.0.1:$BridgePort/ping" -UseBasicParsing -TimeoutSec 2
            if ($r.StatusCode -eq 200) { $bridgeOk = $true }
        } catch { }
    }
}

if (-not $serverOk) { Write-Warning "AI server did not respond on /health in time." }
if (-not $bridgeOk) { Write-Warning "NAOqi bridge did not respond on /ping in time." }

if ($serverOk -and $bridgeOk) {
    Write-Host ""
    Write-Host "READY" -ForegroundColor Green
    Write-Host "  AI server  : http://127.0.0.1:$ServerPort  (also 0.0.0.0 for LAN)"
    Write-Host "  NAOqi bridge: http://127.0.0.1:$BridgePort -> Pepper $PepperIp`:$RobotPort"
    Write-Host ""
    Write-Host "Run the pilot subject experiment:" -ForegroundColor Cyan
    Write-Host ("  $VenvPython scripts\pepper_demo\run_subject_experiment.py " +
                "--participant P000 " +
                "--server http://127.0.0.1:$ServerPort " +
                "--bridge http://127.0.0.1:$BridgePort")
}
