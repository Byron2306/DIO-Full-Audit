param(
  [string]$ConfigDir = "C:\\ProgramData\\osquery",
  [string]$LogDir = "C:\\ProgramData\\osquery\\log"
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

function Write-Step([string]$Message) { Write-Host "[STEP] $Message" -ForegroundColor Cyan }
function Write-OK([string]$Message) { Write-Host "  [OK] $Message" -ForegroundColor Green }
function Write-Warn([string]$Message) { Write-Host "  [WARN] $Message" -ForegroundColor Yellow }

function Test-Command([string]$Name) {
  return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Find-OsquerydExe {
  $candidates = @(
    "C:\\Program Files\\osquery\\osqueryd\\osqueryd.exe",
    "C:\\Program Files\\osquery\\osqueryd.exe",
    "C:\\Program Files (x86)\\osquery\\osqueryd\\osqueryd.exe",
    "C:\\Program Files (x86)\\osquery\\osqueryd.exe"
  )
  foreach ($p in $candidates) { if (Test-Path $p) { return $p } }
  return $null
}

function Try-Install-Osquery {
  if (Test-Command "winget") {
    foreach ($id in @("osquery.osquery", "Facebook.osquery", "osquery.osqueryd")) {
      try {
        Write-Step "Trying winget install: $id"
        winget install --id $id --silent --accept-package-agreements --accept-source-agreements | Out-Null
        Start-Sleep -Seconds 2
        $exe = Find-OsquerydExe
        if ($exe) { return $exe }
      } catch {}
    }
  }
  if (Test-Command "choco") {
    try {
      Write-Step "Trying Chocolatey install: osquery"
      choco install osquery -y | Out-Null
      Start-Sleep -Seconds 2
      $exe = Find-OsquerydExe
      if ($exe) { return $exe }
    } catch {}
  }
  return $null
}

Write-Step "Ensuring osquery directories"
New-Item -ItemType Directory -Force -Path $ConfigDir | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $ConfigDir "packs") | Out-Null
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
Write-OK "Dirs ready"

$osqueryd = Find-OsquerydExe
if (-not $osqueryd) {
  Write-Warn "osqueryd.exe not found; attempting install..."
  $osqueryd = Try-Install-Osquery
}

if (-not $osqueryd) {
  throw "osquery not installed. Install osquery (MSI/winget/choco), then re-run this script."
}
Write-OK "Found osqueryd.exe: $osqueryd"

$configPath = Join-Path $ConfigDir "osquery.conf"
$packPath = Join-Path (Join-Path $ConfigDir "packs") "seraph_mitre_pack.conf"

Write-Step "Writing osquery config: $configPath"
$config = @{
  options = @{
    config_plugin = "filesystem"
    logger_plugin = "filesystem"
    logger_path   = $LogDir
    disable_logging = "false"
    log_result_events = "true"
    utc = "true"
    schedule_splay_percent = "10"
    events_expiry = "3600"
  }
  packs = @{
    seraph_mitre = $packPath
  }
}
($config | ConvertTo-Json -Depth 12) | Set-Content -Path $configPath -Encoding UTF8
Write-OK "Config written"

Write-Step "Writing Seraph pack: $packPath"
$pack = @{
  queries = @{
    seraph_processes = @{
      query = "SELECT pid, name, path, cmdline FROM processes LIMIT 200;"
      interval = 60
      description = "Process inventory for baseline + suspicious activity hunting"
    }
    seraph_listening_ports = @{
      query = "SELECT pid, address, port, protocol FROM listening_ports LIMIT 500;"
      interval = 120
      description = "Local listeners (useful during C2 atomics)"
    }
    seraph_powershell_encoded = @{
      query = "SELECT pid, name, cmdline FROM processes WHERE lower(name)='powershell.exe' AND (cmdline LIKE '% -enc %' OR cmdline LIKE '% -encodedcommand %') LIMIT 200;"
      interval = 60
      description = "Detect encoded PowerShell usage (T1059.001 / T1027)"
    }
    seraph_startup_items = @{
      query = "SELECT * FROM startup_items LIMIT 200;"
      interval = 600
      description = "Startup items (persistence hygiene)"
    }
  }
}
($pack | ConvertTo-Json -Depth 12) | Set-Content -Path $packPath -Encoding UTF8
Write-OK "Pack written"

Write-Step "Attempting to start osquery service (if installed as a service)"
try {
  $svc = Get-Service -Name "osqueryd" -ErrorAction SilentlyContinue
  if ($svc) {
    Set-Service -Name "osqueryd" -StartupType Automatic | Out-Null
    if ($svc.Status -ne "Running") {
      Start-Service -Name "osqueryd" | Out-Null
    }
    Write-OK "osqueryd service running"
  } else {
    Write-Warn "osqueryd service not found. If you installed via MSI, it may install a service automatically; otherwise run osqueryd with --config_path."
  }
} catch {
  Write-Warn "Failed to start osqueryd service: $($_.Exception.Message)"
}

Write-Host ""
Write-Host "osquery setup complete." -ForegroundColor Green
Write-Host "  Config : $configPath" -ForegroundColor White
Write-Host "  Logs   : $LogDir" -ForegroundColor White

