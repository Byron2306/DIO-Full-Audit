<#
Windows installer helper for the Unified Agent.
This script is intended to be packaged into the .msi or run manually during
setup.  It configures the agent to use:

 * built-in UI listening on port 5050
 * optional client certificate for mTLS to the management server
 * optional CA bundle for server certificate verification

Usage examples (run as administrator):

  # basic install with default UI port
  .\install_unified_agent.ps1 \
      -InstallDir "C:\Program Files\Metatron\Agent" \
      -ServerUrl "https://seraph.local" \
      -ClientCert "C:\certs\agent.pem" \
      -ServerCA "C:\certs\ca.pem"

  # unattended install using environment variables set by MSI
  .\install_unified_agent.ps1

Parameters:
  -InstallDir   Target directory where agent binaries/config are placed.
  -ServerUrl    URL of the backend (must start with https://)
  -ClientCert   Path to PEM file containing client certificate+private key.
  -ServerCA     Path to CA bundle to validate backend server certificate.
  -ServiceName  Name of the Windows service (default: MetatronAgent)
  -UIport       Port for local lightweight UI (default: 5050)
#>

param(
    [string]$InstallDir = "${env:ProgramFiles}\Metatron\Agent",
    [string]$ServerUrl = ${env:SERAPH_SERVER_URL},
    [string]$ClientCert = ${env:SERAPH_CLIENT_CERT},
    [string]$ServerCA = ${env:SERAPH_SERVER_CA},
    [string]$ServiceName = "MetatronAgent",
    [int]$UIport = 5000,
    [switch]$OpenFirewall,
    [switch]$FetchServerCert
)

# Normalize ServerUrl: default to localhost if not supplied and ensure scheme
if (-not $ServerUrl) {
    Write-Host "No ServerUrl specified; defaulting to http://localhost:8001"
    $ServerUrl = "http://localhost:8001"
}
if ($ServerUrl -notmatch '^https?://') {
    Write-Warning "ServerUrl appears to be missing a scheme; assuming http://"
    $ServerUrl = "http://$ServerUrl"
}

function Export-ServerCertificatePem {
    param([string]$Url, [string]$OutPath)
    $uri = [uri]$Url
    $host = $uri.Host
    $port = if ($uri.Port -and $uri.Port -gt 0) { $uri.Port } else { 443 }
    Write-Host "Fetching TLS certificate from $host:$port"
    try {
        $tcp = New-Object System.Net.Sockets.TcpClient($host, $port)
        $stream = $tcp.GetStream()
        $ssl = New-Object System.Net.Security.SslStream($stream,$false,({$true}))
        $ssl.AuthenticateAsClient($host)
        $raw = $ssl.RemoteCertificate
        if (-not $raw) { throw "No certificate returned" }
        $x509 = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2 $raw
        $der = $x509.Export([System.Security.Cryptography.X509Certificates.X509ContentType]::Cert)
        $b64 = [System.Convert]::ToBase64String($der)
        $pem = "-----BEGIN CERTIFICATE-----`n"
        $pem += ($b64 -split "(.{64})" | Where-Object { $_ -ne '' } ) -join "`n"
        $pem += "`n-----END CERTIFICATE-----`n"
        [System.IO.File]::WriteAllText($OutPath, $pem)
        $ssl.Close()
        $tcp.Close()
        Write-Host "Wrote server certificate to $OutPath"
        return $true
    } catch {
        Write-Warning "Failed to fetch certificate: $_"
        return $false
    }
}

function Ensure-Directory {
    param([string]$Path)
    if (-not (Test-Path $Path)) {
        Write-Host "Creating $Path"
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
    }
}

function Write-AgentConfig {
    param([string]$Path)
    $cfg = [ordered]@{
        server_url     = $ServerUrl
        local_ui_port  = $UIport
    }
    if ($ClientCert) { $cfg.client_cert = $ClientCert }
    if ($ServerCA)   { $cfg.server_ca   = $ServerCA }

    $json = $cfg | ConvertTo-Json -Depth 5
    Write-Host "Writing configuration to $Path"
    $json | Out-File -FilePath $Path -Encoding UTF8
}

function Install-Service {
    param([string]$ExePath)
    # build command line for service registration
    $bin = "`"$ExePath`" --config `"$InstallDir\agent.json`""
    $bin += " --ui-port $UIport"
    if ($ClientCert) { $bin += " --client-cert `"$ClientCert`"" }
    if ($ServerCA)   { $bin += " --server-ca `"$ServerCA`"" }

    Write-Host "Creating service $ServiceName"
    sc.exe create $ServiceName binPath= "$bin" start= auto | Out-Null
    sc.exe description $ServiceName "Unified Agent service for Seraph" | Out-Null
    sc.exe failure $ServiceName reset= 86400 actions= restart/60000 | Out-Null
}

# ---- main ----

Write-Host "Installing Unified Agent to $InstallDir"
Ensure-Directory $InstallDir

# copy binaries (assumes script shipped alongside the agent binary)
$sourceExe = "$(Split-Path -Parent $MyInvocation.MyCommand.Definition)\unified_agent.exe"
if (Test-Path $sourceExe) {
    Copy-Item -Path $sourceExe -Destination $InstallDir -Force
} else {
    Write-Warning "Agent executable not found at $sourceExe; you must copy it manually."
}

# write config
Ensure-Directory $InstallDir
Write-AgentConfig -Path "$InstallDir\agent.json"

# if requested, attempt to fetch the server certificate and use it as ServerCA
if ($FetchServerCert -and ($ServerUrl -match '^https://')) {
    $pemPath = Join-Path $env:TEMP "seraph_server_cert.pem"
    if (Export-ServerCertificatePem -Url $ServerUrl -OutPath $pemPath) {
        Write-Host "Using fetched server certificate for verification: $pemPath"
        $ServerCA = $pemPath
    } else {
        Write-Warning "Could not obtain server certificate; continuing without custom CA."
    }
}

# install Windows service
Install-Service -ExePath "$InstallDir\unified_agent.exe"

Write-Host "Installation complete.  Use 'Start-Service $ServiceName' to run the agent." 

if ($OpenFirewall) {
    try {
        Write-Host "Adding firewall rule to allow local UI port $UIport"
        New-NetFirewallRule -DisplayName "Metatron Agent UI" -Direction Inbound -LocalPort $UIport -Protocol TCP -Action Allow -Profile Any -Enabled True | Out-Null
        Write-Host "Firewall rule added."
    } catch {
        Write-Warning "Failed to add firewall rule: $_"
    }
}
