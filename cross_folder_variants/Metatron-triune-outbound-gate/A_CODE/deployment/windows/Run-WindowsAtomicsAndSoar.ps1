param(
  [string]$BackendUrl = "http://localhost:8001",
  [string]$Techniques = "",
  [string]$OutputDir = ".\\artifacts\\windows-atomics",
  [string]$ModulePath = "C:\\AtomicRedTeam\\invoke-atomicredteam\\Invoke-AtomicRedTeam.psd1",
  [string]$AtomicsPath = "C:\\AtomicRedTeam\\atomics",
  [int]$TimeoutSeconds = 600,
  [switch]$SkipPrereqs,
  [switch]$IUnderstandThisRunsAdversarySimulation
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

if (-not $IUnderstandThisRunsAdversarySimulation) {
  throw "Refusing to run. Re-run with -IUnderstandThisRunsAdversarySimulation to execute Atomic Red Team tests on this Windows host."
}

if (-not (Test-Path $ModulePath)) { throw "Invoke-AtomicRedTeam module not found: $ModulePath (run deployment/windows/Setup-AtomicRedTeam.ps1 first)" }
if (-not (Test-Path $AtomicsPath)) { throw "Atomics folder not found: $AtomicsPath (run deployment/windows/Setup-AtomicRedTeam.ps1 first)" }

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

function Now-IsoUtc {
  return (Get-Date).ToUniversalTime().ToString("o")
}

function New-RunPayload([string]$Technique, [string]$Status, [string]$Outcome, [int]$ExitCode, [string]$Stdout, [string]$Stderr, [string]$StartedAt, [string]$FinishedAt) {
  $runId = ([guid]::NewGuid().ToString("n"))
  return @{
    run_id = $runId
    job_id = "windows-local-atomics"
    job_name = "Windows Local Atomics (PowerShell)"
    status = $Status
    outcome = $Outcome
    message = "Local PowerShell execution for $Technique"
    techniques = @($Technique)
    techniques_executed = @($Technique)
    runner = "windows_local"
    exit_code = $ExitCode
    stdout = ($Stdout.Substring(0, [Math]::Min($Stdout.Length, 8000)))
    stderr = ($Stderr.Substring(0, [Math]::Min($Stderr.Length, 4000)))
    started_at = $StartedAt
    finished_at = $FinishedAt
    dry_run = $false
    execution_mode = "local_windows"
    runner_profile = "windows-local"
  }
}

function Invoke-SoarRespond([string]$Technique, [string]$Token) {
  if (-not $Token) { return }
  $base = ($BackendUrl.TrimEnd("/")) + "/api"
  $headers = @{ Authorization = "Bearer $Token" }
  $body = @{
    host_id = $env:COMPUTERNAME
    reason  = "SOAR response evidence for Windows atomic execution"
  } | ConvertTo-Json -Depth 6
  try {
    Invoke-RestMethod -Method Post -Uri "$base/soar/techniques/$Technique/respond" -Headers $headers -ContentType "application/json" -Body $body | Out-Null
  } catch {
    Write-Host "  [WARN] SOAR respond failed for $Technique: $($_.Exception.Message)" -ForegroundColor Yellow
  }
}

$token = $env:SERAPH_TOKEN
if (-not $token -and (Test-Path ".seraph-token.txt")) {
  try { $token = (Get-Content ".seraph-token.txt" -ErrorAction Stop | Select-Object -First 1).Trim() } catch {}
}

Import-Module $ModulePath -Force
$env:PathToAtomicsFolder = $AtomicsPath

if (-not $Techniques.Trim()) {
  throw "No techniques provided. Example: -Techniques T1059.001,T1105"
}

$techList = $Techniques.Split(",") | ForEach-Object { $_.Trim().ToUpperInvariant() } | Where-Object { $_ }
Write-Host "Running $($techList.Count) technique(s)..." -ForegroundColor Cyan

$ok = 0
$fail = 0
$skip = 0

foreach ($t in $techList) {
  Write-Host ""
  Write-Host "[TECH] $t" -ForegroundColor White

  $started = Now-IsoUtc
  $stdout = ""
  $stderr = ""
  $status = "failed"
  $outcome = "unknown"
  $exitCode = -1

  try {
    if (-not $SkipPrereqs) {
      try {
        Invoke-AtomicTest $t -PathToAtomicsFolder $AtomicsPath -GetPrereqs 2>&1 | Out-Null
      } catch {}
    }

    $job = Start-Job -ScriptBlock {
      param($technique, $atomics)
      $ErrorActionPreference = "Continue"
      Invoke-AtomicTest $technique -PathToAtomicsFolder $atomics 2>&1 | Out-String
    } -ArgumentList $t, $AtomicsPath

    if (-not (Wait-Job -Job $job -Timeout $TimeoutSeconds)) {
      Stop-Job $job -Force | Out-Null
      Remove-Job $job -Force | Out-Null
      throw "Timeout after $TimeoutSeconds seconds"
    }

    $stdout = (Receive-Job $job -Keep | Out-String)
    Remove-Job $job -Force | Out-Null

    if ($stdout -match "Executing test:") {
      $status = "success"
      $outcome = "real_execution"
      $exitCode = 0
      $ok += 1
      Write-Host "  [OK] Executed (marker found)" -ForegroundColor Green
      Invoke-SoarRespond -Technique $t -Token $token
    } elseif ($stdout -match "Found 0 atomic tests") {
      $status = "skipped"
      $outcome = "no_windows_atom"
      $exitCode = 0
      $skip += 1
      Write-Host "  [SKIP] No atomic tests for this technique" -ForegroundColor Yellow
    } else {
      $status = "skipped"
      $outcome = "no_execution_marker"
      $exitCode = 0
      $skip += 1
      Write-Host "  [SKIP] No execution marker (check stdout)" -ForegroundColor Yellow
    }
  } catch {
    $stderr = $_.Exception.Message
    $status = "failed"
    $outcome = "runner_exception"
    $exitCode = -1
    $fail += 1
    Write-Host "  [FAIL] $stderr" -ForegroundColor Red
  }

  $finished = Now-IsoUtc
  $payload = New-RunPayload -Technique $t -Status $status -Outcome $outcome -ExitCode $exitCode -Stdout $stdout -Stderr $stderr -StartedAt $started -FinishedAt $finished
  $runId = $payload.run_id
  $outPath = Join-Path $OutputDir ("run_" + $runId + ".json")
  ($payload | ConvertTo-Json -Depth 12) | Set-Content -Path $outPath -Encoding UTF8
  Write-Host "  [OUT] $outPath" -ForegroundColor Gray
}

Write-Host ""
Write-Host "Done. OK=$ok SKIP=$skip FAIL=$fail" -ForegroundColor Cyan
if ($fail -gt 0) { exit 1 }
exit 0

