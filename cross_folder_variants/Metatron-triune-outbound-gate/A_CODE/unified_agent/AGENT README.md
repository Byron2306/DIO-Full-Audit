# Metatron Unified Security Agent v2.0

A comprehensive, cross-platform enterprise security agent with advanced threat detection, automated remediation, and extensive security monitoring capabilities.

```
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║     ███╗   ███╗███████╗████████╗ █████╗ ████████╗██████╗  ██████╗ ███╗   ██╗
║     ████╗ ████║██╔════╝╚══██╔══╝██╔══██╗╚══██╔══╝██╔══██╗██╔═══██╗████╗  ██║
║     ██╔████╔██║█████╗     ██║   ███████║   ██║   ██████╔╝██║   ██║██╔██╗ ██║
║     ██║╚██╔╝██║██╔══╝     ██║   ██╔══██║   ██║   ██╔══██╗██║   ██║██║╚██╗██║
║     ██║ ╚═╝ ██║███████╗   ██║   ██║  ██║   ██║   ██║  ██║╚██████╔╝██║ ╚████║
║     ╚═╝     ╚═╝╚══════╝   ╚═╝   ╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝
║                                                                  ║
║                    UNIFIED SECURITY AGENT v2.0                   ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
```

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Architecture](#architecture)
- [Monitor Modules](#monitor-modules)
- [Threat Intelligence](#threat-intelligence)
- [Auto-Remediation Engine](#auto-remediation-engine)
- [Installation](#installation)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [MITRE ATT&CK Coverage](#mitre-attck-coverage)
- [Platform Support](#platform-support)

---

## Overview

The Metatron Unified Security Agent is an enterprise-grade endpoint security solution comprising **13,398 lines** of Python code with **29 specialized security monitors**. It combines real-time threat detection, aggressive auto-remediation, SIEM integration, and AI-powered threat analysis into a single deployable agent.

### Core Capabilities

| Capability | Description |
|------------|-------------|
| **Real-time Monitoring** | 29 concurrent security monitors scanning processes, network, registry, memory, and more |
| **Auto-Kill** | Automatic termination of critical threats (ransomware, credential theft, C2) |
| **SIEM Integration** | Native support for Elasticsearch, Splunk HEC, and Syslog |
| **AI Analysis** | Server-side AI reasoning for threat classification |
| **VNS Sync** | Virtual Network Sensor synchronization for flow analysis |
| **LAN Discovery** | Automatic network device discovery and reporting |
| **WireGuard VPN** | Automated VPN configuration and management |
| **MCP Commands** | Remote command execution from central server |

---

## Key Features

### Security Monitoring
- **29 specialized monitors** covering all attack surfaces
- Process, network, registry, memory, kernel, and identity protection
- Living-off-the-Land Binary (LOLBin) detection
- Code signing verification
- Ransomware canary files and shadow copy protection

### Automated Response
- Aggressive auto-kill for CRITICAL/HIGH severity threats
- Pattern-based instant process termination
- IP blocking and firewall rule creation
- File quarantine with secure storage
- Privilege escalation prevention

### Enterprise Integration
- SIEM: Elasticsearch, Splunk HEC, Syslog (CEF format)
- Server registration with enrollment keys
- Heartbeat monitoring with telemetry
- Remote command execution via MCP
- AI-powered threat analysis

### Network Capabilities
- Port scanning and network discovery
- WiFi network scanning
- Bluetooth device detection
- LAN device auto-discovery
- WireGuard VPN auto-setup

### AI-Friendly Whitelisting
Built-in recognition of legitimate AI/development tools:
- VS Code, Copilot, JetBrains IDEs
- Claude, ChatGPT, Ollama, Cursor
- Node.js, Python, Docker, Git
- MCP servers and development terminals

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         METATRON UNIFIED AGENT                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                      UnifiedAgent (Main Controller)                 │ │
│  │  • Agent registration & authentication                              │ │
│  │  • Monitor orchestration                                            │ │
│  │  • Threat handling & auto-remediation                               │ │
│  │  • MCP command execution                                            │ │
│  │  • Heartbeat & telemetry                                            │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                    │                                    │
│  ┌─────────────────┬───────────────┼───────────────┬─────────────────┐  │
│  │                 │               │               │                 │  │
│  ▼                 ▼               ▼               ▼                 ▼  │
│ ┌─────────┐  ┌──────────┐  ┌─────────────┐  ┌───────────┐  ┌─────────┐ │
│ │ PROCESS │  │ NETWORK  │  │  REGISTRY   │  │  MEMORY   │  │ KERNEL  │ │
│ │ MONITORS│  │ MONITORS │  │  MONITORS   │  │  SCANNER  │  │ SECURITY│ │
│ ├─────────┤  ├──────────┤  ├─────────────┤  ├───────────┤  ├─────────┤ │
│ │Process  │  │Network   │  │Registry     │  │Memory     │  │Rootkit  │ │
│ │Monitor  │  │Monitor   │  │Monitor      │  │Scanner    │  │Detector │ │
│ ├─────────┤  ├──────────┤  ├─────────────┤  └───────────┘  ├─────────┤ │
│ │Process  │  │DNS       │  │Scheduled    │                 │Kernel   │ │
│ │Tree     │  │Monitor   │  │Task Scanner │                 │Security │ │
│ ├─────────┤  ├──────────┤  ├─────────────┤                 │Monitor  │ │
│ │LOLBin   │  │Firewall  │  │WMI Scanner  │                 └─────────┘ │
│ │Monitor  │  │Monitor   │  │COM Hijack   │                             │
│ ├─────────┤  └──────────┘  │Detection    │                             │
│ │Code     │                └─────────────┘                             │
│ │Signing  │                                                            │
│ └─────────┘                                                            │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    ENTERPRISE MONITORS                           │   │
│  ├─────────────────┬───────────────┬───────────────┬───────────────┤   │
│  │ Ransomware      │ DLP Monitor   │ Vulnerability │ AMSI Monitor  │   │
│  │ Protection      │               │ Scanner       │ (Windows)     │   │
│  ├─────────────────┼───────────────┼───────────────┼───────────────┤   │
│  │ App Whitelist   │ Self-Protect  │ Identity      │ Auto-Throttle │   │
│  │ Monitor         │ Agent         │ Protection    │ Monitor       │   │
│  ├─────────────────┼───────────────┼───────────────┼───────────────┤   │
│  │ WebView2        │ CLI Telemetry │ Hidden File   │ Alias/Rename  │   │
│  │ Monitor         │ Monitor       │ Scanner       │ Monitor       │   │
│  ├─────────────────┴───────────────┴───────────────┴───────────────┤   │
│  │                    Privilege Escalation Monitor                  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                     INTEGRATION LAYER                               │ │
│  ├────────────────┬────────────────┬────────────────┬─────────────────┤ │
│  │ SIEMIntegration│ Remediation    │ WireGuard VPN  │ LAN Discovery   │ │
│  │ • Elasticsearch│ Engine         │ Auto-Setup     │ Scanner         │ │
│  │ • Splunk HEC   │ • Kill Process │                │                 │ │
│  │ • Syslog (CEF) │ • Block IP     │                │                 │ │
│  │                │ • Quarantine   │                │                 │ │
│  └────────────────┴────────────────┴────────────────┴─────────────────┘ │
│                                                                         │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                     NETWORK SCANNERS                                │ │
│  ├──────────────────┬──────────────────┬──────────────────────────────┤ │
│  │ NetworkScanner   │ WiFiScanner      │ BluetoothScanner             │ │
│  │ (Port Scanning)  │ (SSID Detection) │ (Device Discovery)           │ │
│  └──────────────────┴──────────────────┴──────────────────────────────┘ │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Monitor Modules

### Core Monitors (Always Active)

| Module | Class | Description |
|--------|-------|-------------|
| **Process Monitor** | `ProcessMonitor` | Process scanning with threat indicators, risk scoring, and trusted AI whitelisting |
| **Network Monitor** | `NetworkMonitor` | Connection monitoring, C2 detection, frequency analysis, IP whitelisting |
| **Registry Monitor** | `RegistryMonitor` | 50+ persistence locations, COM hijacking, WMI subscriptions, IFEO debuggers |
| **Process Tree Monitor** | `ProcessTreeMonitor` | Parent-child relationship analysis for injection detection |
| **LOLBin Monitor** | `LOLBinMonitor` | Living-off-the-Land Binary detection (100+ LOLBins, LOLBas, LOL drivers) |
| **Code Signing Monitor** | `CodeSigningMonitor` | Executable signature verification, revocation checking |
| **DNS Monitor** | `DNSMonitor` | DNS query monitoring, DGA detection, tunneling detection |

### Enterprise Security Monitors

| Module | Class | Description |
|--------|-------|-------------|
| **Memory Scanner** | `MemoryScanner` | Injected code detection, PE header verification, shellcode patterns |
| **Application Whitelist** | `ApplicationWhitelistMonitor` | Enforce allowed application lists |
| **DLP Monitor** | `DLPMonitor` | Data Loss Prevention, sensitive data pattern detection |
| **Vulnerability Scanner** | `VulnerabilityScanner` | CVE matching, outdated software detection |
| **AMSI Monitor** | `AMSIMonitor` | Antimalware Scan Interface bypass detection (Windows) |
| **Ransomware Protection** | `RansomwareProtectionMonitor` | Canary files, shadow copy protection, protected folders |
| **Rootkit Detector** | `RootkitDetector` | Hidden process/file detection, kernel hook scanning |
| **Kernel Security** | `KernelSecurityMonitor` | Kernel module verification, SSDT hook detection |
| **Self-Protection** | `AgentSelfProtection` | Anti-tampering, process protection, file integrity |
| **Identity Protection** | `EndpointIdentityProtection` | Credential guard, token manipulation detection |

### Advanced Monitors (v2.0)

| Module | Class | Description |
|--------|-------|-------------|
| **Auto-Throttle** | `AutoThrottleMonitor` | CPU throttling detection, cryptominer detection, thermal monitoring |
| **Firewall Monitor** | `FirewallMonitor` | Firewall status monitoring, rule change detection |
| **WebView2 Monitor** | `WebView2Monitor` | WebView2 exploit detection, debugging abuse (Windows) |
| **CLI Telemetry** | `CLITelemetryMonitor` | Command-line auditing, LOLBin execution tracking |
| **Hidden File Scanner** | `HiddenFileScanner` | ADS detection, hidden/system file scanning |
| **Alias/Rename Monitor** | `AliasRenameMonitor` | PATH hijacking, binary masquerading detection |
| **Privilege Escalation** | `PrivilegeEscalationMonitor` | Dangerous privilege detection, SYSTEM process monitoring |

---

## Threat Intelligence

The agent includes a comprehensive `ThreatIntelligence` database:

### Malicious Indicators

```python
MALICIOUS_IPS = ["185.220.101.", "45.33.32.", "198.51.100.", "203.0.113."]

SUSPICIOUS_PORTS = {
    4444: "Metasploit", 5555: "Android ADB", 6666: "IRC botnet",
    31337: "Back Orifice", 12345: "NetBus", 9001: "Tor"
}

INSTANT_KILL_PROCESSES = {
    'mimikatz.exe', 'lazagne.exe', 'xmrig.exe', 'netcat.exe',
    'cobaltstrike.exe', 'beacon.exe', 'meterpreter.exe'
}
```

### Critical Auto-Kill Patterns

These patterns trigger immediate process termination:

- **Credential Theft**: mimikatz, lazagne, secretsdump, lsass
- **Ransomware**: cryptolocker, wannacry, petya, lockbit, revil
- **C2 Frameworks**: cobalt strike, meterpreter, sliver, covenant
- **Lateral Movement**: psexec, wmiexec, pass-the-hash
- **Cryptominers**: xmrig, cryptonight, stratum+tcp

### Remote Access Tool Monitoring

The agent monitors (but doesn't auto-kill) legitimate remote access tools:

- TeamViewer, AnyDesk, LogMeIn, Splashtop
- VNC variants, RDP, Radmin
- Associated ports and registry keys

---

## Auto-Remediation Engine

### Remediation Actions

| Action | Description | Requires Admin |
|--------|-------------|----------------|
| `kill_process` | Terminate process by PID or name | Partial |
| `block_ip` | Add firewall rule to block IP | Yes |
| `quarantine_file` | Move file to secure quarantine | Yes |
| `isolate_network` | Disable network adapters | Yes |

### Auto-Kill Logic

```
IF threat.auto_kill_eligible = True
   AND (threat.severity = CRITICAL OR threat.severity = HIGH)
   AND config.auto_remediate = True
   THEN
      Execute remediation immediately
      Log to SIEM
      Trigger alarm
      Notify server
```

---

## Installation

### Prerequisites

- Python 3.8+
- psutil (for system monitoring)
- requests (for server communication)

### Quick Start

```bash
# Clone the repository
git clone https://github.com/your-org/metatron.git
cd metatron/unified_agent

# Install dependencies
pip install -r requirements.txt

# Run the agent
python core/agent.py --server https://your-server.com
```

### Command-Line Options

```
usage: agent.py [-h] [--server SERVER] [--config CONFIG] [--name NAME]
                [--interval INTERVAL] [--no-auto-kill]

Metatron/Seraph Unified Security Agent

optional arguments:
  -h, --help            Show this help message
  --server, -s SERVER   Server URL for registration
  --config, -c CONFIG   Path to configuration file
  --name, -n NAME       Agent display name
  --interval, -i INT    Scan interval in seconds (default: 30)
  --no-auto-kill        Disable automatic threat remediation
```

---

## Configuration

### AgentConfig Dataclass

```python
@dataclass
class AgentConfig:
    # Server connection
    server_url: str = ""
    agent_id: str = ""
    agent_name: str = ""
    enrollment_key: str = ""
    auth_token: str = ""
    
    # Timing
    update_interval: int = 30
    heartbeat_interval: int = 60
    
    # Remediation
    auto_remediate: bool = True
    severity_auto_kill: List[str] = ["critical", "high"]
    auto_block_ips: bool = True
    
    # Feature toggles
    network_scanning: bool = True
    process_monitoring: bool = True
    file_scanning: bool = True
    wireless_scanning: bool = True
    bluetooth_scanning: bool = True
    usb_monitoring: bool = True
    
    # Advanced features
    vns_sync: bool = True
    ai_analysis: bool = True
    siem_integration: bool = False
    threat_hunting: bool = True
    
    # SIEM Configuration
    elasticsearch_url: str = ""
    splunk_hec_url: str = ""
    splunk_hec_token: str = ""
    syslog_server: str = ""
    syslog_port: int = 514
    
    # Trusted networks
    server_ips: List[str] = []
    trusted_networks: List[str] = [
        "127.0.0.0/8", "10.0.0.0/8", 
        "172.16.0.0/12", "192.168.0.0/16"
    ]
```

### Configuration File

Create `agent_config.json`:

```json
{
  "server_url": "https://metatron-server.example.com",
  "enrollment_key": "your-enrollment-key",
  "auto_remediate": true,
  "update_interval": 30,
  "elasticsearch_url": "http://elasticsearch:9200",
  "trusted_networks": ["10.0.0.0/8", "192.168.0.0/16"]
}
```

---

## API Reference

### UnifiedAgent Methods

#### Lifecycle

| Method | Description |
|--------|-------------|
| `start(blocking=True)` | Start the agent monitoring loop |
| `stop()` | Stop the agent |
| `register()` | Register with the server |
| `heartbeat()` | Send heartbeat to server |

#### Scanning

| Method | Description |
|--------|-------------|
| `scan_all()` | Run all enabled monitors |
| `scan_ports(target_ip)` | Scan ports on target |
| `scan_wifi()` | Scan WiFi networks |
| `scan_bluetooth()` | Scan Bluetooth devices |
| `discover_lan_devices()` | Discover LAN devices |

#### Status

| Method | Description |
|--------|-------------|
| `get_status()` | Get agent status summary |
| `get_dashboard_data()` | Get all data for dashboard display |
| `get_vpn_status()` | Get VPN connection status |
| `get_discovered_devices()` | Get discovered LAN devices |

### MCP Commands

The agent supports remote commands from the server:

| Command | Parameters | Description |
|---------|------------|-------------|
| `scan` | - | Full security scan |
| `network_scan` | - | LAN device discovery |
| `wifi_scan` | - | WiFi network scan |
| `bluetooth_scan` | - | Bluetooth device scan |
| `port_scan` | `target_ip` | Port scan target |
| `threat_hunt` | - | Intensive threat detection |
| `collect_forensics` | - | Collect system forensics |
| `kill_process` | `pid` or `name` | Terminate process |
| `block_ip` | `ip` | Block IP address |
| `quarantine_file` | `filepath` | Quarantine file |
| `vpn_connect` | - | Connect VPN |
| `vpn_disconnect` | - | Disconnect VPN |
| `update_config` | config params | Update configuration |
| `restart` | - | Restart agent |
| `get_status` | - | Return agent status |

---

## MITRE ATT&CK Coverage

The agent detects techniques across the ATT&CK framework:

### Initial Access
- T1078: Valid Accounts
- T1190: Exploit Public-Facing Application

### Execution
- T1059: Command and Scripting Interpreter
- T1059.001: PowerShell
- T1059.003: Windows Command Shell
- T1047: WMI
- T1053: Scheduled Task/Job

### Persistence
- T1547: Boot or Logon Autostart Execution
- T1546: Event Triggered Execution
- T1546.003: WMI Event Subscription
- T1546.010: AppInit DLLs
- T1546.012: Image File Execution Options
- T1546.015: COM Hijacking
- T1053.005: Scheduled Task
- T1176: Browser Extensions
- T1574: Hijack Execution Flow
- T1574.011: Service Binary Hijacking

### Privilege Escalation
- T1548: Abuse Elevation Control
- T1134: Access Token Manipulation
- T1068: Exploitation for Privilege Escalation

### Defense Evasion
- T1070: Indicator Removal
- T1027: Obfuscated Files
- T1055: Process Injection
- T1218: System Binary Proxy Execution (LOLBins)
- T1562: Impair Defenses
- T1562.001: Disable Security Tools
- T1562.004: Disable Windows Firewall

### Credential Access
- T1003: OS Credential Dumping
- T1003.001: LSASS Memory
- T1110: Brute Force
- T1552: Unsecured Credentials

### Discovery
- T1082: System Information
- T1083: File and Directory Discovery
- T1057: Process Discovery
- T1046: Network Service Scanning

### Lateral Movement
- T1021: Remote Services
- T1021.002: SMB/Windows Admin Shares
- T1570: Lateral Tool Transfer

### Collection
- T1005: Data from Local System
- T1039: Network Shared Drive

### Command & Control
- T1071: Application Layer Protocol
- T1095: Non-Application Layer Protocol
- T1571: Non-Standard Port

### Exfiltration
- T1048: Exfiltration Over Alternative Protocol

### Impact
- T1486: Data Encrypted for Impact (Ransomware)
- T1489: Service Stop
- T1490: Inhibit System Recovery

---

## Platform Support

| Platform | Status | Notes |
|----------|--------|-------|
| **Windows** | Full | Registry monitoring, AMSI, Code Signing, WebView2 |
| **Linux** | Full | systemd, crontab, /etc persistence |
| **macOS** | Full | LaunchAgents/Daemons, plist monitoring |
| **Android** | Termux | Limited to userspace monitoring |
| **iOS** | Pythonista | Limited capabilities |

---

## Data Storage

| Directory | Purpose |
|-----------|---------|
| `~/.seraph-defender/` (Linux/macOS) | Main installation directory |
| `%LOCALAPPDATA%/SeraphDefender/` (Windows) | Main installation directory |
| `data/` | Configuration and state files |
| `logs/` | Agent log files |
| `quarantine/` | Quarantined malicious files |

---

## Classes Reference

### Core Classes

| Class | Lines | Description |
|-------|-------|-------------|
| `ThreatSeverity` | Enum | LOW, MEDIUM, HIGH, CRITICAL severity levels |
| `ThreatIntelligence` | 150+ | Malicious IPs, ports, processes, patterns database |
| `AgentConfig` | 60+ | Configuration dataclass with feature toggles |
| `Threat` | 25+ | Threat data structure with MITRE mapping |
| `TelemetryData` | 30+ | System and security telemetry |
| `SIEMIntegration` | 110+ | Elasticsearch, Splunk, Syslog integration |
| `RemediationEngine` | 100+ | Kill, block, quarantine actions |
| `UnifiedAgent` | 700+ | Main agent controller |

### Monitor Classes (29 Total)

| Class | Purpose |
|-------|---------|
| `MonitorModule` | Abstract base class for all monitors |
| `ProcessMonitor` | Process scanning with risk scoring |
| `NetworkMonitor` | Network connection monitoring |
| `RegistryMonitor` | Registry/persistence monitoring |
| `ProcessTreeMonitor` | Parent-child process analysis |
| `LOLBinMonitor` | Living-off-the-Land detection |
| `CodeSigningMonitor` | Signature verification |
| `DNSMonitor` | DNS query monitoring |
| `MemoryScanner` | Memory injection detection |
| `ApplicationWhitelistMonitor` | App whitelist enforcement |
| `DLPMonitor` | Data Loss Prevention |
| `VulnerabilityScanner` | CVE/vulnerability detection |
| `AMSIMonitor` | AMSI bypass detection |
| `RansomwareProtectionMonitor` | Ransomware canary/shadow copy |
| `RootkitDetector` | Rootkit detection |
| `KernelSecurityMonitor` | Kernel security checks |
| `AgentSelfProtection` | Agent anti-tampering |
| `EndpointIdentityProtection` | Credential protection |
| `AutoThrottleMonitor` | CPU/thermal monitoring |
| `FirewallMonitor` | Firewall status monitoring |
| `WebView2Monitor` | WebView2 exploit detection |
| `CLITelemetryMonitor` | CLI command auditing |
| `HiddenFileScanner` | ADS/hidden file detection |
| `AliasRenameMonitor` | PATH hijacking detection |
| `PrivilegeEscalationMonitor` | Privilege abuse detection |

### Scanner Classes

| Class | Purpose |
|-------|---------|
| `NetworkScanner` | Port scanning |
| `WiFiScanner` | WiFi network discovery |
| `BluetoothScanner` | Bluetooth device discovery |
| `LANDiscoveryScanner` | LAN device auto-discovery |
| `WireGuardAutoSetup` | VPN auto-configuration |

---

## Trusted AI Process Whitelist

The agent recognizes ~100 legitimate development tools to prevent false positives:

### IDEs & Editors
- VS Code, Code Insiders, Code OSS, Code Tunnel
- JetBrains: IntelliJ, PyCharm, WebStorm, GoLand, Rider, CLion
- Cursor (AI code editor)

### AI Assistants
- GitHub Copilot, Copilot Chat, Copilot Language Server
- Claude, Claude Desktop, Anthropic Quickstart
- Ollama, LLaMA Server, GPT4All, LM Studio
- ChatGPT, OpenAI API clients
- Continue, Codeium, TabNine, Kite, Aider

### Development Tools
- Python, pip, poetry, pipenv
- Node.js, npm, npx
- Docker, Podman, kubectl
- Git, GitHub CLI
- Cargo, Rust, Go, .NET

### Terminals
- Windows Terminal, PowerShell, cmd
- Bash, Zsh, Fish
- iTerm2, Alacritty, Kitty, Warp
- GNOME Terminal, Konsole

### Trusted Network Destinations
- api.anthropic.com, claude.ai
- api.openai.com, chat.openai.com
- copilot.github.com, api.github.com
- huggingface.co, ollama.ai
- localhost, 127.0.0.1

---

## Logging

The agent uses Python's logging module:

```python
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('metatron.core')
```

Log levels:
- **INFO**: Normal operation, scan results
- **WARNING**: Auto-kill executions, alarms
- **ERROR**: Failed operations, scan errors
- **DEBUG**: Detailed debugging (SIEM errors, etc.)

---

## Security Considerations

### Agent Self-Protection
- Process protection against termination
- File integrity monitoring
- Registry key protection (Windows)
- Anti-debugging features

### Network Whitelisting
- Server IPs automatically whitelisted after registration
- Private networks (RFC1918) trusted by default
- Agent's own IPs excluded from monitoring

### Privilege Handling
- Agent checks for admin/root privileges on startup
- Warns when operations require elevated privileges
- Reports privilege status to server

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 2.0.0 | 2025 | Unified agent with 29 monitors, MCP commands, VPN integration, 7 new advanced monitors |
| 1.0.0 | 2024 | Initial release with core monitoring |

---

## File Statistics

```
Total Lines: 13,398
Classes: 38
Monitor Modules: 29
Functions: 200+
Threat Patterns: 100+
LOLBins Tracked: 100+
Registry Keys: 50+
```

---

## Related Files

| File | Purpose |
|------|---------|
| `/unified_agent/core/agent.py` | Main agent implementation |
| `/frontend/src/pages/UnifiedAgentPage.jsx` | Dashboard UI |
| `/backend/server.py` | Server API |
| `/memory/PRD.md` | Product Requirements |
| `/memory/FEATURE_REALITY_MATRIX.md` | Feature implementation status |

---

## License

Proprietary - Metatron Security Systems

---

## Support

- Documentation: `/memory/PRD.md`
- Dashboard: `/frontend/src/pages/UnifiedAgentPage.jsx`
- Server API: `/backend/server.py`
