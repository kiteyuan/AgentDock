# Stop AgentDock host processes by well-known ports.
#   .\scripts\stop.ps1
#   .\scripts\stop.ps1 -KeepTts   # leave GPT-SoVITS :9880 running

param(
    [switch]$KeepTts,
    [switch]$KeepWeb
)

$ports = @(8765, 8766, 9001)
if (-not $KeepWeb) { $ports += 8090 }
if (-not $KeepTts) {
    $ports += 9880   # GPT-SoVITS
}

foreach ($port in $ports) {
    $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if (-not $conns) {
        Write-Host "free :$port"
        continue
    }
    $pids = $conns | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($procId in $pids) {
        try {
            $p = Get-Process -Id $procId -ErrorAction Stop
            Write-Host "stop :$port pid=$procId ($($p.ProcessName))"
            Stop-Process -Id $procId -Force -ErrorAction Stop
        } catch {
            Write-Host "skip :$port pid=$procId ($($_.Exception.Message))"
        }
    }
}

Start-Sleep -Seconds 1
foreach ($port in $ports) {
    if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) {
        Write-Host "still held :$port"
    } else {
        Write-Host "ok free :$port"
    }
}
