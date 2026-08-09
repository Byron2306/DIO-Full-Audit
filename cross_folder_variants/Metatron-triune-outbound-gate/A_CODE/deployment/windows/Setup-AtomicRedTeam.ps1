param(
  [string]$InstallRoot = "C:\\AtomicRedTeam",
  [string]$AtomicRepo = "redcanaryco/atomic-red-team",
  [string]$InvokeRepo = "redcanaryco/invoke-atomicredteam",
  [string]$Ref = "master"
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

function Write-Step([string]$Message) { Write-Host "[STEP] $Message" -ForegroundColor Cyan }
function Write-OK([string]$Message) { Write-Host "  [OK] $Message" -ForegroundColor Green }
function Write-Warn([string]$Message) { Write-Host "  [WARN] $Message" -ForegroundColor Yellow }

function Get-GitHubZipUrl([string]$Repo, [string]$RepoRef) {
  return "https://github.com/$Repo/archive/refs/heads/$RepoRef.zip"
}

function Download-And-Extract([string]$Repo, [string]$RepoRef, [string]$DestDir) {
  $tmp = Join-Path $env:TEMP ("seraph-art-" + [guid]::NewGuid().ToString("n"))
  New-Item -ItemType Directory -Force -Path $tmp | Out-Null
  try {
    $zipPath = Join-Path $tmp "repo.zip"
    $url = Get-GitHubZipUrl -Repo $Repo -RepoRef $RepoRef
    Write-Step "Downloading $Repo ($RepoRef)..."
    Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $zipPath
    Expand-Archive -Path $zipPath -DestinationPath $tmp -Force

    $extracted = Get-ChildItem -Path $tmp -Directory | Where-Object { $_.Name -notin @("repo.zip") } | Select-Object -First 1
    if (-not $extracted) { throw "Failed to extract $Repo zip" }
    New-Item -ItemType Directory -Force -Path $DestDir | Out-Null
    Copy-Item -Path (Join-Path $extracted.FullName "*") -Destination $DestDir -Recurse -Force
    Write-OK "Installed $Repo to $DestDir"
  } finally {
    Remove-Item -Path $tmp -Recurse -Force -ErrorAction SilentlyContinue
  }
}

Write-Step "Preparing install root: $InstallRoot"
New-Item -ItemType Directory -Force -Path $InstallRoot | Out-Null

$atomicsDir = Join-Path $InstallRoot "atomics"
$invokeDir = Join-Path $InstallRoot "invoke-atomicredteam"

if (Test-Path $atomicsDir) {
  Write-Warn "Atomics already exist at $atomicsDir (leaving as-is). Delete the folder to reinstall."
} else {
  $repoDir = Join-Path $env:TEMP ("atomic-red-team-" + [guid]::NewGuid().ToString("n"))
  Download-And-Extract -Repo $AtomicRepo -RepoRef $Ref -DestDir $repoDir
  $atomicsSrc = Join-Path $repoDir "atomics"
  if (-not (Test-Path $atomicsSrc)) { throw "Expected atomics folder not found in $AtomicRepo ($Ref)" }
  Copy-Item -Path $atomicsSrc -Destination $atomicsDir -Recurse -Force
  Remove-Item -Path $repoDir -Recurse -Force -ErrorAction SilentlyContinue
  Write-OK "Atomics ready: $atomicsDir"
}

if (Test-Path $invokeDir) {
  Write-Warn "Invoke-AtomicRedTeam already exists at $invokeDir (leaving as-is). Delete the folder to reinstall."
} else {
  Download-And-Extract -Repo $InvokeRepo -RepoRef $Ref -DestDir $invokeDir
  $psd1 = Join-Path $invokeDir "Invoke-AtomicRedTeam.psd1"
  if (-not (Test-Path $psd1)) { throw "Invoke-AtomicRedTeam.psd1 not found in $invokeDir" }
  Write-OK "Invoke-AtomicRedTeam module ready: $psd1"
}

Write-Host ""
Write-Host "Atomic install complete." -ForegroundColor Green
Write-Host "  Atomics : $atomicsDir" -ForegroundColor White
Write-Host "  Module  : $(Join-Path $invokeDir 'Invoke-AtomicRedTeam.psd1')" -ForegroundColor White

