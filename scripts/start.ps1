# AgentDock one-click host start (Windows).
# Default: Runtime + Pets HTTP + Pi gateway + Haibara GPT-SoVITS. Web UI is OFF.
#
#   .\scripts\start.ps1
#   .\scripts\start.ps1 -Web          # also open desktop Web preview
#   .\scripts\start.ps1 -NoTts        # skip GPT-SoVITS (Edge fallback)
#   .\scripts\start.ps1 -NoPi         # skip Pi coding gateway
#   .\scripts\stop.ps1
#
# Optional env:
#   AGENTDOCK_GPT_SOVITS_ROOT      — GPT-SoVITS repo (api_v2.py)
#   AGENTDOCK_GPT_SOVITS_PYTHON    — python for api_v2.py

param(
    [switch]$Web,
    [switch]$NoTts,
    [switch]$NoPi,
    [int]$ReadyTimeoutSec = 300
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root

function Test-PortListen([int]$Port) {
    return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1)
}

function Wait-PortListen([int]$Port, [int]$TimeoutSec, [string]$Label) {
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        if (Test-PortListen $Port) {
            Write-Host "  ready: $Label (:$Port)"
            return $true
        }
        Start-Sleep -Milliseconds 500
    }
    Write-Host "  timeout: $Label (:$Port) after ${TimeoutSec}s"
    return $false
}

function Start-Console([string]$Title, [string]$WorkDir, [string]$Command) {
    $ps = @(
        "`$Host.UI.RawUI.WindowTitle = '$Title'"
        "Set-Location -LiteralPath '$WorkDir'"
        "`$env:PYTHONUNBUFFERED = '1'"
        $Command
    ) -join "; "
    Start-Process -FilePath "powershell.exe" -WorkingDirectory $WorkDir -ArgumentList @(
        "-NoExit", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $ps
    ) | Out-Null
    Write-Host "  started: $Title"
}

Write-Host "AgentDock start (repo: $Root)"
Write-Host "  Web UI: $(if ($Web) { 'ON' } else { 'OFF (use -Web to enable)' })"

# --- Runtime (:8765 + pets :8766) ---
if (Test-PortListen 8765) {
    Write-Host "  skip Runtime — :8765 already listening"
} else {
    Start-Console "AgentDock Runtime :8765" $Root "python -m runtime"
}

[void](Wait-PortListen 8765 $ReadyTimeoutSec "Runtime WS")
if (Test-PortListen 8766) {
    Write-Host "  ready: Pets HTTP (:8766)"
} else {
    [void](Wait-PortListen 8766 30 "Pets HTTP")
}

# --- Pi gateway (:9001) ---
if (-not $NoPi) {
    if (Test-PortListen 9001) {
        Write-Host "  skip Pi — :9001 already listening"
    } else {
        $piCmd = @(
            "`$env:PI_GATEWAY_PORT = '9001'"
            "Remove-Item Env:PI_NO_TOOLS -ErrorAction SilentlyContinue"
            "Remove-Item Env:PI_NO_SESSION -ErrorAction SilentlyContinue"
            "python agents\pi-coding\gateway.py"
        ) -join "; "
        Start-Console "AgentDock Pi :9001" $Root $piCmd
    }
    [void](Wait-PortListen 9001 60 "Pi gateway")
} else {
    Write-Host "  skip Pi (-NoPi)"
}

# --- GPT-SoVITS / Haibara (:9880) ---
if (-not $NoTts) {
    if (Test-PortListen 9880) {
        Write-Host "  skip SoVITS — :9880 already listening"
    } else {
        $sovitsRoot = $env:AGENTDOCK_GPT_SOVITS_ROOT
        if (-not $sovitsRoot) {
            $sovitsRoot = "E:\Projects\Base Projects\VoiceForge\third_party\GPT-SoVITS"
        }
        $sovitsPy = $env:AGENTDOCK_GPT_SOVITS_PYTHON
        if (-not $sovitsPy) {
            $candidate = "E:\Projects\Base Projects\VoiceForge\.venv\Scripts\python.exe"
            if (Test-Path $candidate) { $sovitsPy = $candidate } else { $sovitsPy = "python" }
        }
        $api = Join-Path $sovitsRoot "api_v2.py"
        if (-not (Test-Path $api)) {
            Write-Host "  skip SoVITS — api_v2.py not found at $sovitsRoot"
        } else {
            $ttsCmd = @(
                "`$env:AGENTVOICE_GPT_SOVITS_ROOT = '$sovitsRoot'"
                "& '$sovitsPy' api_v2.py -a 127.0.0.1 -p 9880"
            ) -join "; "
            Start-Console "GPT-SoVITS TTS :9880" $sovitsRoot $ttsCmd
            [void](Wait-PortListen 9880 $ReadyTimeoutSec "GPT-SoVITS TTS")
        }
    }
} else {
    Write-Host "  skip TTS (-NoTts)"
}

# --- optional Web UI (:8090) ---
if ($Web) {
    if (Test-PortListen 8090) {
        Write-Host "  skip Web — :8090 already listening"
    } else {
        Start-Console "AgentDock Web :8090" $Root "python clients\cli\main.py --ui"
        [void](Wait-PortListen 8090 30 "Web UI")
    }
}

Write-Host ""
Write-Host "Endpoints:"
Write-Host "  Runtime WS   ws://127.0.0.1:8765"
Write-Host "  Pets HTTP    http://127.0.0.1:8766/pets/"
if (-not $NoPi) { Write-Host "  Pi gateway   http://127.0.0.1:9001" }
if (-not $NoTts) { Write-Host "  GPT-SoVITS   http://127.0.0.1:9880" }
if ($Web) { Write-Host "  Web UI       http://127.0.0.1:8090/" }
Write-Host "Stop with: .\scripts\stop.ps1"
