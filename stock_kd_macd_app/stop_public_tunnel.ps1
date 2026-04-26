$ErrorActionPreference = "SilentlyContinue"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$pidPath = Join-Path $root "tools\\cloudflared.pid"

if (Test-Path $pidPath) {
    $pid = Get-Content $pidPath | Select-Object -First 1
    if ($pid) {
        Stop-Process -Id $pid -Force
        Write-Host "Stopped cloudflared PID $pid"
    }
    Remove-Item $pidPath -ErrorAction SilentlyContinue
} else {
    Get-Process cloudflared | Stop-Process -Force
    Write-Host "Stopped running cloudflared processes"
}
