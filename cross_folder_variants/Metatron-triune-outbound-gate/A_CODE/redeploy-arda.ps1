$base = "http://10.0.2.2:8888"
Write-Host "=== Stopping ARDACollector service ===" -ForegroundColor Cyan
Stop-Service ARDACollector -Force -ErrorAction SilentlyContinue
Start-Sleep 3

Write-Host "=== Downloading updated source ===" -ForegroundColor Cyan
Invoke-WebRequest "$base/arda-src.zip" -OutFile C:\ARDA\arda-src.zip

Write-Host "=== Extracting ===" -ForegroundColor Cyan
Remove-Item C:\ARDA\unpack -Recurse -Force -ErrorAction SilentlyContinue
Expand-Archive C:\ARDA\arda-src.zip C:\ARDA\unpack -Force

Write-Host "=== Copying source files ===" -ForegroundColor Cyan
Copy-Item -Recurse -Force "C:\ARDA\unpack\Arda Windows\src\arda_windows" C:\ARDA\src\arda_windows

Write-Host "=== Starting ARDACollector service ===" -ForegroundColor Cyan
Start-Service ARDACollector
Start-Sleep 6

Write-Host "=== Checking port 7331 ===" -ForegroundColor Cyan
netstat -ano | findstr 7331

Write-Host "=== Health check ===" -ForegroundColor Cyan
try {
    $r = Invoke-WebRequest "http://127.0.0.1:7331/health" -TimeoutSec 5
    Write-Host "Health OK: $($r.Content)" -ForegroundColor Green
} catch {
    Write-Host "Health check failed: $_" -ForegroundColor Red
}
