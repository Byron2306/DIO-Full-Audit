param(
  [string]$BackendUrl = "http://localhost:8001",
  [string]$OutFile = ".seraph-token.txt",
  [string]$Email = "",
  [string]$Password = "",
  [string]$Name = "Seraph Lab Admin"
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

function Read-Secret([string]$Prompt) {
  $sec = Read-Host -AsSecureString $Prompt
  $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)
  try { [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr) }
  finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
}

if (-not $Email) { $Email = Read-Host "Email" }
if (-not $Password) { $Password = Read-Secret "Password" }

$base = ($BackendUrl.TrimEnd("/")) + "/api"

function Invoke-JsonPost([string]$Url, [hashtable]$Body) {
  $json = ($Body | ConvertTo-Json -Depth 10)
  return Invoke-RestMethod -Method Post -Uri $Url -ContentType "application/json" -Body $json
}

Write-Host "[STEP] Requesting Seraph auth token from $base..." -ForegroundColor Cyan

$token = $null
try {
  $resp = Invoke-JsonPost -Url "$base/auth/login" -Body @{ email = $Email; password = $Password }
  $token = $resp.access_token
  Write-Host "  [OK] Logged in as $Email" -ForegroundColor Green
} catch {
  Write-Host "  [WARN] Login failed; trying register (first user becomes admin)..." -ForegroundColor Yellow
  $resp = Invoke-JsonPost -Url "$base/auth/register" -Body @{ email = $Email; password = $Password; name = $Name }
  $token = $resp.access_token
  Write-Host "  [OK] Registered $Email" -ForegroundColor Green
}

if (-not $token) { throw "Failed to obtain access token" }

Set-Content -Path $OutFile -Value $token -Encoding ASCII
Write-Host "  [OK] Wrote token to $OutFile" -ForegroundColor Green
Write-Host ""
Write-Host "Next:" -ForegroundColor White
Write-Host "  `$env:SERAPH_TOKEN = Get-Content $OutFile" -ForegroundColor Gray

