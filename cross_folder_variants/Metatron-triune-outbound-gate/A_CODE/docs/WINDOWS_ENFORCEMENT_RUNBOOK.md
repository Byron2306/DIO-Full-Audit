# Windows Enforcement Runbook (ARDA + Seraph Policy Plane)

## Goal
Bring Windows VM behavior close to Linux prevention posture:
- Enforce execution policy on endpoint (AppLocker and/or WDAC)
- Keep ARDA as control-plane actuator and telemetry source
- Validate with explicit deny outcomes, not just health/sovereignty summaries

## Architecture
- Linux ring-0 BPF LSM has no direct parity on Windows.
- Windows equivalent should be:
  - Decision plane: Seraph policy and governance logic
  - Enforcement plane: WindowsPolicyEnforcementProvider
  - Execution control: AppLocker + WDAC
  - Network containment: Windows Firewall rules

## Prerequisites on Windows VM
Run as Administrator (WinRM session account must be full admin token):

```powershell
# Confirm admin token path
whoami /groups | findstr /i "S-1-5-32-544"

# AppLocker service prerequisite
Get-Service AppIDSvc | Format-List Name,Status,StartType
Set-Service AppIDSvc -StartupType Automatic
Start-Service AppIDSvc

# Confirm Code Integrity baseline status
Get-CimInstance -Namespace root\Microsoft\Windows\DeviceGuard -ClassName Win32_DeviceGuard |
  Select-Object UsermodeCodeIntegrityPolicyEnforcementStatus,CodeIntegrityPolicyEnforcementStatus
```

## Apply posture via ARDA API
If backend API is reachable, use ARDA enforcement endpoint:

```bash
curl -sS -X POST "http://127.0.0.1:8001/platform-sovereignty/apply-posture" \
  -H "Content-Type: application/json" \
  -d '{"node_id":"win11-lab","posture":"enforce","verdict":{}}'
```

Expected action markers in response:
- wdac_policy:enforce:ok|fail
- applocker:enforce:ok

If WDAC policy GUID update fails, AppLocker enforce mode is still a valid prevention path.

## Direct local fallback (if API not wired)

```powershell
$base = 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\SrpV2'
$collections = @('Exe','Msi','Script','Dll','Appx')
if (-not (Test-Path $base)) { New-Item -Path $base -Force | Out-Null }
foreach ($c in $collections) {
  $p = Join-Path $base $c
  if (-not (Test-Path $p)) { New-Item -Path $p -Force | Out-Null }
  Set-ItemProperty -Path $p -Name EnforcementMode -Type DWord -Value 1
}
Set-Service AppIDSvc -StartupType Automatic
Start-Service AppIDSvc
```

## Validation matrix (must pass)
Run these and collect both command result and event evidence.

1. Unsanctioned script execution
- Attempt: launch unsigned script/binary from non-allowed path
- Expected: blocked with access denied or policy restriction

2. Known-safe signed binary
- Attempt: run signed Microsoft binary from system path
- Expected: allowed

3. Path-based deny check
- Add explicit deny for test binary, then execute
- Expected: blocked

4. Atomic technique smoke
- Run 3-5 Atomic tests that previously succeeded
- Expected: at least one policy-driven denial when posture=enforce

5. Firewall containment
- Apply quarantine posture with node IP
- Expected: outbound block rule exists and traffic denied

## Evidence collection commands

```powershell
# AppLocker operational logs
Get-WinEvent -LogName "Microsoft-Windows-AppLocker/EXE and DLL" -MaxEvents 30 |
  Select-Object TimeCreated, Id, LevelDisplayName, Message

# Security policy process failures (if auditing enabled)
Get-WinEvent -FilterHashtable @{LogName='Security'; Id=4688} -MaxEvents 20

# ARDA provider state
Get-Service ARDACollector | Format-List Name,Status,StartType
```

```bash
# ARDA API checks
curl -sS http://127.0.0.1:7331/health
curl -sS http://127.0.0.1:7331/sovereignty
curl -sS http://127.0.0.1:7331/summary
```

## Integrating Seraph logic on Windows
Port and reuse these components first:
- Policy decision and approval logic
- Posture mapping from verdict to enforce/audit/quarantine/off
- Tulkas orchestration hooks that call apply_posture

Do not port Linux-only kernel components:
- eBPF LSM loader and map logic
- Linux syscall hook code

## Rollout sequence
1. Enable AppIDSvc and AppLocker enforce collection keys.
2. Wire ARDA posture endpoint call from governance executor path.
3. Run validation matrix and capture deny events.
4. Only then re-run broad Atomic sweep and compare deny counts.

## Exit criteria
- At least one intentionally unsanctioned execution is blocked by policy.
- ARDA response includes enforcement action success markers.
- Logs show explicit AppLocker/WDAC deny evidence.
- Sweep outcomes include non-zero blocked/denied events when posture=enforce.
