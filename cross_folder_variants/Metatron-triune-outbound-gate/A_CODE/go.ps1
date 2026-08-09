Set-ExecutionPolicy Bypass -Scope Process -Force
$base = "http://10.0.2.2:8888"
$tmp = "$env:TEMP\arda"
New-Item -ItemType Directory -Force -Path $tmp | Out-Null
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
Write-Host "Downloading ARDA source..." -ForegroundColor Cyan
Invoke-WebRequest "$base/arda-src.zip" -OutFile "$tmp\arda-src.zip" -UseBasicParsing
Expand-Archive "$tmp\arda-src.zip" -DestinationPath $tmp -Force
Write-Host "Downloading installer..." -ForegroundColor Cyan
Invoke-WebRequest "$base/infra/arda-windows-vm/install-arda.ps1" -OutFile "$tmp\install-arda.ps1" -UseBasicParsing
& "$tmp\install-arda.ps1" -ArdaSrc "$tmp\Arda Windows\src"
