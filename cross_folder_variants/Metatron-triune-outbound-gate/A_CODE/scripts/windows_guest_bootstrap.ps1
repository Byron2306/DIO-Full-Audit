param(
    [string]$AtomicRoot = 'C:\AtomicRedTeam\atomics',
    [string]$InvokeAtomicModulePath = 'C:\AtomicRedTeam\invoke-atomicredteam\Invoke-AtomicRedTeam.psd1',
    [switch]$EnableLabBasicAuth = $true
)

$ErrorActionPreference = 'Stop'

function Assert-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'Run this script from an elevated PowerShell session.'
    }
}

function Ensure-PathExists {
    param(
        [string]$Path,
        [string]$Label
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "$Label not found: $Path"
    }
}

Assert-Administrator

Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope LocalMachine -Force
Enable-PSRemoting -SkipNetworkProfileCheck -Force
Set-Service -Name WinRM -StartupType Automatic
Start-Service -Name WinRM

if ($EnableLabBasicAuth) {
    # This is for an isolated lab VM only. Do not reuse these settings on a production network.
    Set-Item -Path WSMan:\localhost\Service\Auth\Basic -Value $true
    Set-Item -Path WSMan:\localhost\Service\AllowUnencrypted -Value $true
}

if (-not (Get-NetFirewallRule -DisplayName 'Windows Remote Management (HTTP-In)' -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -DisplayName 'Windows Remote Management (HTTP-In)' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 5985 | Out-Null
}

Ensure-PathExists -Path $AtomicRoot -Label 'Atomic Red Team atomics root'
Ensure-PathExists -Path $InvokeAtomicModulePath -Label 'Invoke-AtomicRedTeam module'

Import-Module $InvokeAtomicModulePath -Force

if (-not (Get-Command Invoke-AtomicTest -ErrorAction SilentlyContinue)) {
    throw 'Invoke-AtomicTest was not available after importing Invoke-AtomicRedTeam.'
}

$hostname = $env:COMPUTERNAME
$wsman = Test-WSMan -ComputerName localhost
$sampleAtomic = Get-ChildItem -Path $AtomicRoot -Filter '*.yaml' -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName

[pscustomobject]@{
    Hostname = $hostname
    WinRMService = (Get-Service WinRM).Status
    WSManProductVersion = $wsman.ProductVersion
    AtomicRoot = $AtomicRoot
    InvokeAtomicModulePath = $InvokeAtomicModulePath
    SampleAtomicYaml = $sampleAtomic
    InvokeAtomicTestAvailable = $true
    LabBasicAuthEnabled = [bool]$EnableLabBasicAuth
} | Format-List