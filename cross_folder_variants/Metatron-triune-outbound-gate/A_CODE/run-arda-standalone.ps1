# Run ARDA collector standalone — no Windows service / no pywin32 needed
$python = "C:\ARDA\python\python.exe"
$script = "C:\ARDA\src\arda_windows\service\arda_collector_svc.py"
$base   = "http://10.0.2.2:8888"

Write-Host "=== Stopping ARDACollector service (if running) ===" -ForegroundColor Cyan
Stop-Service ARDACollector -Force -ErrorAction SilentlyContinue
Start-Sleep 2

Write-Host "=== Downloading updated source ===" -ForegroundColor Cyan
Invoke-WebRequest "$base/arda-src.zip" -OutFile C:\ARDA\arda-src.zip
Remove-Item C:\ARDA\unpack -Recurse -Force -ErrorAction SilentlyContinue
Expand-Archive C:\ARDA\arda-src.zip C:\ARDA\unpack -Force
Copy-Item -Recurse -Force "C:\ARDA\unpack\Arda Windows\src\arda_windows" C:\ARDA\src\arda_windows

Write-Host "=== Killing anything on port 7331 ===" -ForegroundColor Cyan
$pids = netstat -ano | Select-String ':7331\s' | ForEach-Object { ($_ -split '\s+')[-1] } | Sort-Object -Unique
foreach ($p in $pids) { if ($p -match '^\d+$') { taskkill /F /PID $p 2>$null } }
Start-Sleep 1

Write-Host "=== Starting ARDA standalone ===" -ForegroundColor Cyan
$env:PYTHONPATH = "C:\ARDA\src"
$proc = Start-Process -FilePath $python -ArgumentList $script `
    -RedirectStandardOutput C:\ARDA\arda-stdout.log `
    -RedirectStandardError  C:\ARDA\arda-stderr.log `
    -WindowStyle Hidden -PassThru
Write-Host "PID: $($proc.Id)"
Start-Sleep 6

Write-Host "=== Health check ===" -ForegroundColor Cyan
try {
    $r = Invoke-WebRequest "http://127.0.0.1:7331/health" -TimeoutSec 5
    Write-Host "SUCCESS: $($r.Content)" -ForegroundColor Green
} catch {
    Write-Host "FAILED. Last log lines:" -ForegroundColor Red
    Get-Content C:\ARDA\arda-stderr.log -Tail 20 -ErrorAction SilentlyContinue
    Get-Content C:\ARDA\arda-stdout.log -Tail 20 -ErrorAction SilentlyContinue
}
