param(
  [string]$BackendUrl = "http://localhost:8001",
  [string]$ResultsLog = "C:\\ProgramData\\osquery\\log\\osqueryd.results.log",
  [int]$MaxLines = 200
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

function Write-Step([string]$Message) { Write-Host "[STEP] $Message" -ForegroundColor Cyan }
function Write-OK([string]$Message) { Write-Host "  [OK] $Message" -ForegroundColor Green }
function Write-Warn([string]$Message) { Write-Host "  [WARN] $Message" -ForegroundColor Yellow }

if (-not (Test-Path $ResultsLog)) {
  throw "osquery results log not found: $ResultsLog (run deployment/windows/Setup-Osquery.ps1 and ensure osquery is running)"
}

$token = $env:INTEGRATION_API_KEY
if (-not $token) {
  Write-Warn "INTEGRATION_API_KEY not set. Using default dev token (matches docker-compose.windows.stack.yml unless you changed it)."
  $token = "dev-integration-key-change-me"
}

$base = ($BackendUrl.TrimEnd("/")) + "/api"

Write-Step "Reading last $MaxLines lines from $ResultsLog"
$lines = Get-Content -Path $ResultsLog -Tail $MaxLines -ErrorAction Stop

$records = @()
foreach ($line in $lines) {
  $trim = ($line | ForEach-Object { $_.Trim() })
  if (-not $trim) { continue }
  try {
    $records += ($trim | ConvertFrom-Json -ErrorAction Stop)
  } catch {
    continue
  }
}

if ($records.Count -eq 0) {
  Write-Warn "No JSON records parsed from osquery results log."
  exit 0
}

Write-Step "Posting $($records.Count) record(s) to $base/osquery/ingest"
$payload = @{ records = $records } | ConvertTo-Json -Depth 20
$headers = @{ "x-internal-token" = $token }

$resp = Invoke-RestMethod -Method Post -Uri "$base/osquery/ingest" -Headers $headers -ContentType "application/json" -Body $payload
Write-OK "Ingested: $($resp.ingested)  Stored: $($resp.path)"

