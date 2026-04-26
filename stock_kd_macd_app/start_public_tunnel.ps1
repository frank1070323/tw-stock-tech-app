$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$cloudflared = Join-Path $root "tools\\cloudflared.exe"
$logPath = Join-Path $root "tools\\cloudflared.log"
$pidPath = Join-Path $root "tools\\cloudflared.pid"

if (-not (Test-Path $cloudflared)) {
    throw "cloudflared.exe not found: $cloudflared"
}

Get-Process cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force
Remove-Item $logPath -ErrorAction SilentlyContinue
Remove-Item $pidPath -ErrorAction SilentlyContinue

$proc = Start-Process -FilePath $cloudflared `
    -ArgumentList "tunnel --url http://127.0.0.1:5051 --logfile `"$logPath`"" `
    -WorkingDirectory $root `
    -WindowStyle Hidden `
    -PassThru

$proc.Id | Set-Content -Path $pidPath

Write-Host "cloudflared started (PID $($proc.Id))."
Write-Host "Log: $logPath"
Write-Host "Waiting for public URL..."

$publicUrl = $null
for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Seconds 1
    if (Test-Path $logPath) {
        $match = Select-String -Path $logPath -Pattern 'https://[-a-z0-9]+\.trycloudflare\.com' | Select-Object -Last 1
        if ($match) {
            $publicUrl = $match.Matches.Value
            break
        }
    }
}

if (-not $publicUrl) {
    throw "Public URL not found in time. Check log: $logPath"
}

Write-Host ""
Write-Host "Public URL:"
Write-Host $publicUrl
