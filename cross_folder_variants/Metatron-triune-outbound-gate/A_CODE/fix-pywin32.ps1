# fix-pywin32.ps1 — Stop ARDACollector, fix pywin32 DLLs, restart service
$ErrorActionPreference = "Stop"
$PY = "C:\ARDA\python\python.exe"

Write-Host "[1] Stopping ARDACollector..."
Stop-Service ARDACollector -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

Write-Host "[2] Running pywin32_postinstall..."
$post = Get-ChildItem "C:\ARDA\python" -Recurse -Filter "pywin32_postinstall.py" -ErrorAction SilentlyContinue | Select-Object -First 1
if ($post) {
    & $PY $post.FullName -install
} else {
    Write-Host "  pywin32_postinstall.py not found, copying DLLs manually..."
    Get-ChildItem "C:\ARDA\python" -Recurse -Filter "pywintypes*.dll" | ForEach-Object {
        Write-Host "  Copying $($_.Name)"
        Copy-Item $_.FullName "C:\Windows\System32\" -Force
    }
    Get-ChildItem "C:\ARDA\python" -Recurse -Filter "pythoncom*.dll" | ForEach-Object {
        Write-Host "  Copying $($_.Name)"
        Copy-Item $_.FullName "C:\Windows\System32\" -Force
    }
}

Write-Host "[3] Starting ARDACollector..."
Start-Service ARDACollector
Start-Sleep -Seconds 6

Write-Host "[4] Status:"
Get-Service ARDACollector | Format-Table Name, Status -AutoSize
netstat -ano | findstr "7331"
