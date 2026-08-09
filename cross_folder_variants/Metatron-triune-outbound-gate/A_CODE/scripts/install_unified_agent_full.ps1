<#!
Full Windows installer for Unified Agent.  Downloads latest build, unpacks,
configures and registers service with mTLS options.

Intended to be run from any Windows box with Internet access and administrative
privileges.  Adjust $DownloadUrl to your build artifact location.

Usage:
    .\install_unified_agent_full.ps1 [-ServerUrl <url>] [-ClientCert <path>]
        [-ServerCA <path>] [-ServiceName <name>] [-UIport <port>]

Example:
    .\install_unified_agent_full.ps1 \
       -ServerUrl https://seraph.local \
       -ClientCert C:\certs\agent.pem \
       -ServerCA C:\certs\ca.pem
#>

param(
    # environment variable may be empty; use simple conditional assignment
    [string]$DownloadUrl = (
        if ($env:AGENT_DOWNLOAD_URL) { $env:AGENT_DOWNLOAD_URL } else { "https://example.com/metatron-unified-agent-windows.zip" }
    ),
    [string]$InstallDir = "${env:ProgramFiles}\Metatron\Agent",
    [string]$ServerUrl = ${env:SERAPH_SERVER_URL},
    [string]$ClientCert = ${env:SERAPH_CLIENT_CERT},
    [string]$ServerCA = ${env:SERAPH_SERVER_CA},
    [string]$ServiceName = "MetatronAgent",
    [int]$UIport = 5000
)

[switch]$FetchServerCert

function Download-Agent {
    param([string]$Url,[string]$Dest)
    Write-Host "Downloading agent from $Url to $Dest"
    try {
        Invoke-WebRequest -Uri $Url -OutFile $Dest -UseBasicParsing
        return $true
    } catch {
        Write-Error "Download failed: $_"
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

function Extract-Zip {
    param([string]$ZipFile, [string]$Destination)
    Write-Host "Extracting $ZipFile to $Destination"
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::ExtractToDirectory($ZipFile, $Destination)
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
    # build the command line for the service; use += for clarity
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
Write-Host "Full agent installer starting"

# if no server URL provided, assume localhost for single‑machine lab
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
    # parse host and port
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

# prepare download location
$tmpZip = Join-Path $env:TEMP "unified_agent.zip"

# allow DownloadUrl to be a local file path as convenience
if (Test-Path $DownloadUrl) {
    Write-Host "Using local agent bundle at $DownloadUrl"
    Copy-Item -Path $DownloadUrl -Destination $tmpZip -Force
} else {
    if ($DownloadUrl -like "*example.com*") {
        Write-Warning "DownloadUrl is placeholder – replace with real location or supply a local file."
    }
    if (-not (Download-Agent -Url $DownloadUrl -Dest $tmpZip)) { exit 1 }
}

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

Ensure-Directory $InstallDir
Extract-Zip -ZipFile $tmpZip -Destination $InstallDir

# write configuration and register service
Write-AgentConfig -Path "$InstallDir\agent.json"
Install-Service -ExePath "$InstallDir\unified_agent.exe"

Write-Host "Installation finished.  Use 'Start-Service $ServiceName' to run the agent."