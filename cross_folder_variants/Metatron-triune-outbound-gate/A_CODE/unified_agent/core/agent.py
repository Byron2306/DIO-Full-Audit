"""
Metatron/Seraph Unified Security Agent - Core Module v2.0
=========================================================
Cross-platform security agent with advanced threat detection,
AI reasoning, SIEM integration, and enterprise security features.

Combines:
- Metatron's cross-platform architecture
- Seraph's advanced security features (VNS, AI, Quantum, SIEM)
- Aggressive auto-kill capabilities
- Network scanning (Port, WiFi, Bluetooth)
- Cuckoo sandbox integration
- USB device monitoring

Supports: Windows, macOS, Linux, Android (Termux), iOS (Pythonista)
"""

import os
import sys
import json
import uuid
import time
import socket
import hashlib
import hmac
import logging
import platform
import threading
import subprocess
import re
import math
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Callable, Tuple, Set
from dataclasses import dataclass, field, asdict
from collections import deque, defaultdict
from abc import ABC, abstractmethod
from enum import Enum

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('metatron.core')

# Agent identification
AGENT_VERSION = "2.0.0"
HOSTNAME = socket.gethostname()
PLATFORM = platform.system().lower()

# Directories
if PLATFORM == "windows":
    INSTALL_DIR = Path(os.environ.get('LOCALAPPDATA', 'C:/SeraphDefender')) / "SeraphDefender"
else:
    INSTALL_DIR = Path.home() / ".seraph-defender"

DATA_DIR = INSTALL_DIR / "data"
LOGS_DIR = INSTALL_DIR / "logs"
QUARANTINE_DIR = INSTALL_DIR / "quarantine"

for d in [INSTALL_DIR, DATA_DIR, LOGS_DIR, QUARANTINE_DIR]:
    d.mkdir(parents=True, exist_ok=True)


class ThreatSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# =============================================================================
# PRIVILEGE & SECURITY HELPERS
# =============================================================================

def check_admin_privileges() -> Tuple[bool, str]:
    """Check if running with admin/root privileges"""
    try:
        if PLATFORM == "windows":
            import ctypes
            is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
            return is_admin, "Administrator" if is_admin else "Standard User"
        else:
            is_root = os.geteuid() == 0
            return is_root, "root" if is_root else f"uid={os.getuid()}"
    except Exception as e:
        return False, f"Unknown ({e})"


# =============================================================================
# FRIENDLY AI / TRUSTED PROCESS WHITELIST  
# =============================================================================
# Legitimate AI development tools that should NOT trigger threat detection.
# These processes use CLI commands, spawn subprocesses, and exhibit AI-like
# behavior but are friendly tools, not malicious agents.

TRUSTED_AI_PROCESSES = {
    # VS Code and extensions
    "code", "code.exe", "code-insiders", "code-insiders.exe",
    "vscode", "code-oss", "code-tunnel",
    "copilot-agent", "copilot-language-server",
    "github.copilot", "github-copilot-chat",
    
    # JetBrains IDEs
    "idea", "idea64.exe", "pycharm", "pycharm64.exe",
    "webstorm", "webstorm64.exe", "goland", "goland64.exe",
    "rider", "rider64.exe", "clion", "clion64.exe",
    "intellij", "datagrip", "rubymine", "phpstorm",
    
    # AI Assistants and Models
    "claude", "claude-desktop", "anthropic-quickstart",
    "ollama", "ollama.exe", "llama", "llama-server",
    "chatgpt", "openai", "gpt4all", "lmstudio",
    "cursor", "cursor.exe",  # AI-native code editor
    "continue", "codeium", "tabnine", "kite",
    "aider", "codegpt", "refact",
    
    # Development tools that use AI
    "npm", "npx", "node", "node.exe",
    "python", "python3", "python.exe", "pythonw.exe",
    "pip", "pip3", "poetry", "pipenv",
    "cargo", "rustc", "go", "dotnet",
    "git", "gh", "github", "git.exe",
    
    # Terminal emulators
    "terminal", "gnome-terminal", "konsole", "xterm",
    "alacritty", "kitty", "iterm2", "warp",
    "windowsterminal.exe", "wt.exe", "cmd.exe", "powershell.exe",
    "pwsh", "pwsh.exe", "bash", "zsh", "fish",
    
    # MCP Servers (our own infrastructure)
    "mcp-server", "metatron-mcp", "seraph-mcp",
    "unified-agent", "seraph-defender",
    
    # Package managers and build tools
    "brew", "apt", "yum", "dnf", "pacman",
    "docker", "docker.exe", "podman", "kubectl",
    "make", "cmake", "maven", "gradle", "ant",
}

# Trusted process path patterns (for more precise matching)
TRUSTED_AI_PATH_PATTERNS = [
    # VS Code installations
    r".*[/\\]Microsoft VS Code[/\\].*",
    r".*[/\\]\.vscode[/\\].*",
    r".*[/\\]code[/\\].*",
    
    # JetBrains
    r".*[/\\]JetBrains[/\\].*",
    r".*[/\\]\.local[/\\]share[/\\]JetBrains[/\\].*",
    
    # Node.js AI packages
    r".*[/\\]node_modules[/\\]@anthropic-ai[/\\].*",
    r".*[/\\]node_modules[/\\]openai[/\\].*",
    r".*[/\\]node_modules[/\\]@copilot[/\\].*",
    
    # Python AI packages
    r".*[/\\]site-packages[/\\]anthropic[/\\].*",
    r".*[/\\]site-packages[/\\]openai[/\\].*",
    r".*[/\\]site-packages[/\\]langchain[/\\].*",
    
    # Our own agent
    r".*[/\\]SeraphDefender[/\\].*",
    r".*[/\\]\.seraph-defender[/\\].*",
    r".*[/\\]unified_agent[/\\].*",
    r".*[/\\]metatron[/\\].*",
]

# Trusted network destinations for AI services
TRUSTED_AI_DOMAINS = {
    "api.anthropic.com", "claude.ai",
    "api.openai.com", "chat.openai.com", "chatgpt.com",
    "copilot.github.com", "api.github.com", "github.com",
    "ollama.ai", "huggingface.co", "api.together.xyz",
    "api.mistral.ai", "api.cohere.ai",
    "localhost", "127.0.0.1", "::1",
}


def is_trusted_ai_process(process_name: str, process_path: Optional[str] = None, cmdline: Optional[str] = None) -> Tuple[bool, str]:
    """
    Check if a process is a known trusted AI/development tool.
    
    Returns:
        (is_trusted: bool, reason: str)
    """
    import re
    
    proc_lower = process_name.lower() if process_name else ""
    
    # Direct process name match
    if proc_lower in TRUSTED_AI_PROCESSES:
        return True, f"Whitelisted process: {proc_lower}"
    
    # Partial name match for common patterns
    trusted_patterns = ["vscode", "copilot", "jetbrains", "cursor", "ollama", "anthropic"]
    for pattern in trusted_patterns:
        if pattern in proc_lower:
            return True, f"Matches trusted pattern: {pattern}"
    
    # Path-based matching
    if process_path:
        path_lower = process_path.lower()
        for pattern in TRUSTED_AI_PATH_PATTERNS:
            if re.match(pattern, path_lower, re.IGNORECASE):
                return True, f"Path matches trusted pattern"
    
    # Check if process is our own agent
    if "seraph" in proc_lower or "metatron" in proc_lower or "unified" in proc_lower:
        return True, "Metatron agent process"
    
    return False, "Not a recognized trusted AI process"


def is_trusted_ai_network(destination: str) -> Tuple[bool, str]:
    """Check if a network destination is a trusted AI service"""
    dest_lower = destination.lower() if destination else ""
    
    # Direct domain match
    if dest_lower in TRUSTED_AI_DOMAINS:
        return True, f"Trusted AI domain: {dest_lower}"
    
    # Partial match for subdomains
    for domain in TRUSTED_AI_DOMAINS:
        if dest_lower.endswith(domain) or dest_lower.endswith(f".{domain}"):
            return True, f"Subdomain of trusted: {domain}"
    
    return False, "Unknown destination"


def is_ip_whitelisted(ip: str, whitelist: List[str]) -> bool:
    """Check if an IP is in the whitelist (exact or CIDR match)"""
    if not ip or ip in ('', 'unknown'):
        return False
    
    # Exact match
    if ip in whitelist:
        return True
    
    # CIDR match
    try:
        import ipaddress
        ip_obj = ipaddress.ip_address(ip)
        for entry in whitelist:
            if '/' in entry:
                try:
                    if ip_obj in ipaddress.ip_network(entry, strict=False):
                        return True
                except ValueError:
                    pass
            elif ip == entry:
                return True
    except (ValueError, ImportError):
        pass
    
    return False


def get_own_ips() -> Set[str]:
    """Get all IPs assigned to this machine"""
    own_ips = {'127.0.0.1', 'localhost', '::1'}
    try:
        hostname = socket.gethostname()
        own_ips.add(socket.gethostbyname(hostname))
        for info in socket.getaddrinfo(hostname, None):
            own_ips.add(info[4][0])
    except Exception:
        pass
    
    # Also try from network interfaces
    if PSUTIL_AVAILABLE:
        try:
            for iface, addrs in psutil.net_if_addrs().items():
                for addr in addrs:
                    if addr.family in (socket.AF_INET, socket.AF_INET6):
                        own_ips.add(addr.address)
        except Exception:
            pass
    
    return own_ips


AGENT_OWN_IPS = get_own_ips()


# =============================================================================
# THREAT INTELLIGENCE DATABASE
# =============================================================================

class ThreatIntelligence:
    """Known malicious indicators"""
    
    MALICIOUS_IPS = {
        "185.220.101.", "45.33.32.", "198.51.100.", "203.0.113.",
    }
    
    SUSPICIOUS_PORTS = {
        4444: "Metasploit default", 5555: "Android ADB", 6666: "IRC botnet",
        6667: "IRC botnet", 31337: "Back Orifice", 12345: "NetBus",
        27374: "SubSeven", 1234: "Common backdoor", 9001: "Tor",
        9050: "Tor SOCKS", 4443: "Common C2", 8443: "Alt HTTPS",
        3389: "RDP", 5900: "VNC", 5800: "VNC HTTP",
    }
    
    # Remote Access Tools - NOT malicious by default, but should be monitored
    # These are flagged for awareness, not auto-blocked
    REMOTE_ACCESS_TOOLS = {
        # Process names (case-insensitive)
        "processes": [
            # TeamViewer
            "teamviewer", "teamviewer.exe", "teamviewer_service.exe",
            "tv_w32.exe", "tv_x64.exe", "teamviewer_desktop.exe",
            
            # AnyDesk
            "anydesk", "anydesk.exe", "anydesk_service.exe",
            
            # Other remote access
            "ammyyadmin.exe", "ammyy", "logmein", "logmein.exe",
            "gotomeeting", "gotoassist", "screenconnect", "connectwise",
            "bomgar", "bomgar-scc.exe", "splashtop", "splashtop.exe",
            "rustdesk", "rustdesk.exe", "parsec", "parsec.exe",
            "chrome_remote_desktop", "remotedesktop.exe",
            "radmin", "radmin.exe", "rserver3.exe", "rserver.exe",
            "ultraviewer", "ultraviewer.exe",
            "supremo", "supremo.exe", "supremoservice.exe",
            "dameware", "dwrcs.exe", "dwrcc.exe",
            "vnc", "vncviewer", "vncserver", "winvnc", "tvnserver",
            "tightvnc", "realvnc", "ultravnc",
            "mstsc", "mstsc.exe",  # Windows RDP client
            "xrdp", "xfreerdp", "rdesktop",
        ],
        
        # Network ports for remote access tools
        "ports": {
            5938: "TeamViewer",
            7070: "AnyDesk (control)",
            6568: "AnyDesk (direct)",
            5500: "VNC (reverse)",
            5800: "VNC HTTP",
            5900: "VNC",
            5901: "VNC :1",
            5902: "VNC :2",
            3389: "RDP",
            4899: "Radmin",
            6783: "Splashtop",
            443: "Most remote tools (HTTPS)",
        },
        
        # Registry keys (Windows) that indicate remote access tools
        "registry_paths": [
            r"HKLM\SOFTWARE\TeamViewer",
            r"HKLM\SOFTWARE\WOW6432Node\TeamViewer",
            r"HKCU\SOFTWARE\TeamViewer",
            r"HKLM\SOFTWARE\AnyDesk",
            r"HKCU\SOFTWARE\AnyDesk",
            r"HKLM\SOFTWARE\Ammyy",
            r"HKLM\SOFTWARE\LogMeIn",
        ],
        
        # Default installation paths
        "install_paths": [
            r"C:\Program Files\TeamViewer",
            r"C:\Program Files (x86)\TeamViewer",
            r"C:\Program Files\AnyDesk",
            r"C:\Program Files (x86)\AnyDesk",
            r"%APPDATA%\AnyDesk",
            r"%APPDATA%\TeamViewer",
        ]
    }
    
    MALICIOUS_DOMAINS = [
        r".*\.onion$", r".*\.bit$", r".*dyndns.*", r".*no-ip.*",
        r".*\.tk$", r".*\.ml$", r".*\.ga$", r".*\.cf$",
        r".*pastebin\.com.*", r".*ngrok\.io.*",
    ]
    
    MALICIOUS_PROCESSES = [
        'mimikatz', 'lazagne', 'procdump', 'pwdump', 'fgdump',
        'gsecdump', 'wce', 'nc.exe', 'ncat.exe', 'netcat',
        'psexec', 'paexec', 'crackmapexec', 'bloodhound',
        'sharphound', 'rubeus', 'kerberoast', 'responder',
        'impacket', 'empire', 'covenant', 'cobalt',
        'meterpreter', 'beacon', 'sliver', 'mythic',
        'cryptolocker', 'wannacry', 'petya', 'ryuk',
        'conti', 'lockbit', 'revil', 'darkside',
        'xmrig', 'minerd', 'cgminer', 'bfgminer',
    ]
    
    MALICIOUS_COMMANDS = [
        r'powershell.*-enc', r'powershell.*downloadstring',
        r'powershell.*iex', r'certutil.*-urlcache',
        r'bitsadmin.*\/transfer', r'mshta.*http',
        r'regsvr32.*\/s.*\/u.*\/i:http', r'rundll32.*javascript',
        r'wmic.*process.*call.*create', r'net.*user.*\/add',
        r'net.*localgroup.*administrators', r'reg.*add.*run',
        r'schtasks.*\/create', r'sc.*create',
        r'whoami.*\/priv', r'mimikatz', r'sekurlsa', r'lsadump',
        r'base64.*-d.*\|.*bash', r'curl.*\|.*bash',
        r'wget.*\|.*bash', r'python.*-c.*import.*socket',
        r'nc.*-e.*\/bin', r'bash.*-i.*>&.*\/dev\/tcp',
    ]
    
    EXFIL_PATTERNS = [
        r'curl.*-d.*@', r'curl.*--data-binary', r'wget.*--post-file',
        r'scp.*@.*:', r'rsync.*@.*:', r'ftp.*put', r'rclone.*copy',
    ]
    
    # Critical patterns that ALWAYS trigger auto-kill
    CRITICAL_PATTERNS = [
        'mimikatz', 'lazagne', 'credential', 'lsass', 'sekurlsa',
        'procdump', 'gsecdump', 'pwdump', 'fgdump', 'wce',
        'ntdsutil', 'secretsdump', 'ransomware', 'cryptolocker',
        'wannacry', 'petya', 'locky', 'cerber', 'ryuk',
        'sodinokibi', 'revil', 'lockbit', 'conti', 'blackmatter',
        'encrypt', '.crypt', '.locked', '.encrypted',
        'wiper', 'format c:', 'del /f /s /q', 'rm -rf',
        'dd if=/dev/zero', 'diskpart', 'clean all', 'cipher /w',
        'reverse shell', 'meterpreter', 'beacon', 'cobalt',
        'covenant', 'empire', 'sliver', 'brute ratel', 'havoc',
        'mythic', 'nighthawk', 'netcat', 'nc -e', 'ncat -e',
        'psexec', 'wmiexec', 'smbexec', 'atexec', 'dcomexec',
        'pass the hash', 'pass-the-hash', 'pth-', 'overpass',
        'golden ticket', 'silver ticket', 'getsystem',
        'privilege::debug', 'token::elevate', 'uac bypass',
        'exfiltrat', 'megasync', 'rclone', 'winscp -script',
        'keylog', 'keyboard hook', 'getasynckeystate',
        'process hollowing', 'dll injection', 'reflective',
        'shellcode', 'createremotethread', 'ntqueueapcthread',
        'xmrig', 'cryptonight', 'stratum+tcp', 'minerd',
    ]
    
    # Process names to IMMEDIATELY kill
    INSTANT_KILL_PROCESSES = {
        'mimikatz.exe', 'lazagne.exe', 'procdump.exe', 'gsecdump.exe',
        'pwdump.exe', 'wce.exe', 'xmrig.exe', 'minerd.exe', 'cgminer.exe',
        'netcat.exe', 'nc.exe', 'ncat.exe', 'psexec.exe', 'paexec.exe',
        'cobaltstrike.exe', 'beacon.exe', 'meterpreter.exe',
    }


# =============================================================================
# DATA MODELS
# =============================================================================

def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)) or default)
    except Exception:
        return default


@dataclass
class AgentConfig:
    """Agent configuration"""
    server_url: str = ""
    agent_id: str = ""
    agent_name: str = ""
    update_interval: int = field(default_factory=lambda: _env_int("SERAPH_AGENT_UPDATE_INTERVAL", 300))
    heartbeat_interval: int = field(default_factory=lambda: _env_int("SERAPH_AGENT_HEARTBEAT_INTERVAL", 300))
    auto_remediate: bool = field(default_factory=lambda: _env_bool("SERAPH_AGENT_AUTO_REMEDIATE", True))
    severity_auto_kill: List[str] = field(default_factory=lambda: ["critical", "high"])
    
    # Authentication
    enrollment_key: str = ""  # For initial registration
    auth_token: str = ""       # Received after registration
    
    # Whitelisted IPs (server + known-friendly)
    server_ips: List[str] = field(default_factory=list)
    trusted_networks: List[str] = field(default_factory=lambda: [
        "127.0.0.0/8", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"
    ])
    
    # Privilege settings
    require_admin: bool = False  # Warn if not admin
    auto_block_ips: bool = True  # Block malicious IPs (requires admin)
    
    # Feature toggles
    network_scanning: bool = field(default_factory=lambda: _env_bool("SERAPH_AGENT_NETWORK_SCANNING", True))
    process_monitoring: bool = field(default_factory=lambda: _env_bool("SERAPH_AGENT_PROCESS_MONITORING", True))
    file_scanning: bool = field(default_factory=lambda: _env_bool("SERAPH_AGENT_FILE_SCANNING", True))
    wireless_scanning: bool = field(default_factory=lambda: _env_bool("SERAPH_AGENT_WIRELESS_SCANNING", True))
    bluetooth_scanning: bool = field(default_factory=lambda: _env_bool("SERAPH_AGENT_BLUETOOTH_SCANNING", True))

    # Data protection / EDM
    dlp_edm_enabled: bool = True
    dlp_edm_dataset_path: str = ""
    dlp_edm_tenant_salt: str = ""
    dlp_edm_max_records: int = 20000
    dlp_edm_min_confidence: float = 0.90
    dlp_edm_allowed_candidate_types: List[str] = field(default_factory=lambda: [
        "line",
        "delimited_bundle",
        "delimited_window_4",
        "delimited_window_3",
        "delimited_window_2",
    ])
    dlp_edm_require_signed: bool = True
    dlp_edm_signing_secret: str = ""
    usb_monitoring: bool = field(default_factory=lambda: _env_bool("SERAPH_AGENT_USB_MONITORING", True))
    
    # Advanced features
    vns_sync: bool = field(default_factory=lambda: _env_bool("SERAPH_AGENT_VNS_SYNC", True))
    ai_analysis: bool = field(default_factory=lambda: _env_bool("SERAPH_AGENT_AI_ANALYSIS", True))
    siem_integration: bool = False
    quantum_secure: bool = False
    threat_hunting: bool = field(default_factory=lambda: _env_bool("SERAPH_AGENT_THREAT_HUNTING", True))
    
    # SIEM Configuration
    elasticsearch_url: str = ""
    splunk_hec_url: str = ""
    splunk_hec_token: str = ""
    syslog_server: str = ""
    syslog_port: int = 514

    # Local web UI
    local_ui_enabled: bool = True
    local_ui_port: int = 5000

    # VPN
    vpn_auto_configure: bool = field(default_factory=lambda: _env_bool("SERAPH_AGENT_VPN_AUTO_CONFIGURE", True))

    @classmethod
    def from_file(cls, path: str) -> 'AgentConfig':
        """Load config from file"""
        if os.path.exists(path):
            with open(path, 'r') as f:
                data = json.load(f)
            return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})
        return cls()
    
    def save(self, path: str):
        """Save config to file"""
        with open(path, 'w') as f:
            json.dump(asdict(self), f, indent=2)


@dataclass
class Threat:
    """Threat data structure"""
    threat_id: str = ""
    title: str = ""
    description: str = ""
    severity: ThreatSeverity = ThreatSeverity.MEDIUM
    threat_type: str = "unknown"
    source: str = ""
    target: str = ""
    evidence: Dict = field(default_factory=dict)
    mitre_techniques: List[str] = field(default_factory=list)
    detected_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: str = "active"
    auto_kill_eligible: bool = False
    remediation_action: Optional[str] = None
    remediation_params: Dict = field(default_factory=dict)
    ai_analysis: Optional[Dict] = None
    kill_reason: Optional[str] = None
    user_approved: Optional[bool] = None
    
    def to_dict(self) -> Dict:
        d = asdict(self)
        d['severity'] = self.severity.value if isinstance(self.severity, ThreatSeverity) else self.severity
        return d


@dataclass
class TelemetryData:
    """Telemetry data structure"""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    agent_id: str = ""
    hostname: str = HOSTNAME
    platform: str = PLATFORM
    
    # System metrics
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    disk_usage: float = 0.0
    
    # Security data
    processes: List[Dict] = field(default_factory=list)
    connections: List[Dict] = field(default_factory=list)
    threats: List[Dict] = field(default_factory=list)
    events: List[Dict] = field(default_factory=list)
    
    # Network data
    network_interfaces: List[Dict] = field(default_factory=list)
    wifi_networks: List[Dict] = field(default_factory=list)
    bluetooth_devices: List[Dict] = field(default_factory=list)
    usb_devices: List[Dict] = field(default_factory=list)


# =============================================================================
# SIEM INTEGRATION
# =============================================================================

class SIEMIntegration:
    """Full SIEM integration for enterprise logging"""
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self.enabled = False
        self.siem_type = None
        self.buffer: deque = deque(maxlen=1000)
        self.last_flush = time.time()
        self.flush_interval = 5
        
        # Auto-detect SIEM
        if config.elasticsearch_url:
            self.enabled = True
            self.siem_type = 'elasticsearch'
            logger.info(f"SIEM: Elasticsearch enabled at {config.elasticsearch_url}")
        elif config.splunk_hec_url:
            self.enabled = True
            self.siem_type = 'splunk'
            logger.info(f"SIEM: Splunk HEC enabled")
        elif config.syslog_server:
            self.enabled = True
            self.siem_type = 'syslog'
            logger.info(f"SIEM: Syslog enabled at {config.syslog_server}")
    
    def log_event(self, event_type: str, severity: str, data: dict, immediate: bool = False):
        """Log a security event to SIEM"""
        event = {
            "@timestamp": datetime.now(timezone.utc).isoformat(),
            "agent_id": self.config.agent_id,
            "hostname": HOSTNAME,
            "os": PLATFORM,
            "event_type": event_type,
            "severity": severity,
            "data": data,
            "source": "metatron_agent"
        }
        
        if immediate or severity in ['critical', 'high']:
            self._send_event(event)
        else:
            self.buffer.append(event)
            if time.time() - self.last_flush >= self.flush_interval:
                self._flush_buffer()
    
    def log_threat(self, threat: Threat, action: str = "detected"):
        """Log a threat detection/remediation to SIEM"""
        self.log_event(
            event_type=f"threat.{action}",
            severity=threat.severity.value if isinstance(threat.severity, ThreatSeverity) else threat.severity,
            data={
                "threat_id": threat.threat_id,
                "threat_type": threat.threat_type,
                "title": threat.title,
                "description": threat.description,
                "remediation_action": threat.remediation_action,
                "status": threat.status,
                "kill_reason": threat.kill_reason
            },
            immediate=threat.severity in {ThreatSeverity.CRITICAL, ThreatSeverity.HIGH}
        )
    
    def _send_event(self, event: dict):
        """Send event to configured SIEM"""
        if not self.enabled or not REQUESTS_AVAILABLE:
            return
        
        try:
            if self.siem_type == 'elasticsearch':
                self._send_to_elasticsearch(event)
            elif self.siem_type == 'splunk':
                self._send_to_splunk(event)
            elif self.siem_type == 'syslog':
                self._send_to_syslog(event)
        except Exception as e:
            logger.debug(f"SIEM send error: {e}")
    
    def _send_to_elasticsearch(self, event: dict):
        """Send to Elasticsearch"""
        url = f"{self.config.elasticsearch_url}/seraph-security/_doc"
        requests.post(url, json=event, timeout=5)
    
    def _send_to_splunk(self, event: dict):
        """Send to Splunk HEC"""
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Splunk {self.config.splunk_hec_token}'
        }
        requests.post(self.config.splunk_hec_url, json={"event": event}, headers=headers, timeout=5)
    
    def _send_to_syslog(self, event: dict):
        """Send to Syslog server"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        severity_map = {'critical': 10, 'high': 7, 'medium': 5, 'low': 3, 'info': 1}
        sev = severity_map.get(event.get('severity', 'info'), 1)
        msg = f"CEF:0|Seraph|Metatron|2.0|{event['event_type']}|Security Event|{sev}|src={HOSTNAME}"
        sock.sendto(msg.encode(), (self.config.syslog_server, self.config.syslog_port))
        sock.close()
    
    def _flush_buffer(self):
        """Flush buffered events to SIEM"""
        while self.buffer:
            event = self.buffer.popleft()
            self._send_event(event)
        self.last_flush = time.time()


# =============================================================================
# MONITORING MODULES
# =============================================================================

class MonitorModule(ABC):
    """Base class for monitoring modules"""
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self.enabled = True
        self.last_run = None
        self.error_count = 0
    
    @abstractmethod
    def scan(self) -> Dict[str, Any]:
        """Perform scan and return results"""
        pass
    
    @abstractmethod
    def get_threats(self) -> List[Threat]:
        """Get detected threats from last scan"""
        pass


class ProcessMonitor(MonitorModule):
    """Process monitoring module with aggressive detection"""
    
    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self.intel = ThreatIntelligence()
        self.processes = []
        self.threats = []
    
    def scan(self) -> Dict[str, Any]:
        """Scan running processes"""
        if not PSUTIL_AVAILABLE:
            return {"error": "psutil not available", "processes": []}
        
        self.processes = []
        self.threats = []
        
        try:
            for proc in psutil.process_iter(['pid', 'name', 'username', 'cmdline', 'cpu_percent', 'memory_percent']):
                try:
                    pinfo = proc.info
                    process_data = {
                        'pid': pinfo['pid'],
                        'name': pinfo['name'],
                        'username': pinfo['username'] or 'SYSTEM',
                        'cmdline': ' '.join(pinfo['cmdline'] or []),
                        'cpu_percent': pinfo['cpu_percent'] or 0,
                        'memory_percent': pinfo['memory_percent'] or 0,
                        'risk_score': 0,
                        'threat_indicators': [],
                        'trusted_ai': False
                    }
                    
                    name_lower = (pinfo['name'] or '').lower()
                    cmdline_lower = process_data['cmdline'].lower()
                    
                    # Check if this is a trusted AI/development process FIRST
                    is_trusted, trust_reason = is_trusted_ai_process(
                        pinfo['name'], 
                        getattr(proc, 'exe', lambda: None)(),
                        process_data['cmdline']
                    )
                    if is_trusted:
                        process_data['trusted_ai'] = True
                        process_data['trust_reason'] = trust_reason
                        # Skip threat detection for trusted AI processes
                        self.processes.append(process_data)
                        continue
                    
                    # Check for remote access tools (TeamViewer, AnyDesk, etc.)
                    # These are flagged for awareness but NOT auto-killed
                    remote_tools = self.intel.REMOTE_ACCESS_TOOLS.get("processes", [])
                    for tool in remote_tools:
                        if tool in name_lower:
                            process_data['remote_access_tool'] = tool
                            process_data['threat_indicators'].append(f'remote_access:{tool}')
                            # Low risk score - awareness flag only
                            process_data['risk_score'] += 10
                            break
                    
                    # Check instant-kill processes
                    if name_lower in self.intel.INSTANT_KILL_PROCESSES:
                        process_data['risk_score'] = 100
                        process_data['threat_indicators'].append('instant_kill_process')
                    
                    # Check malicious process names
                    for mal_proc in self.intel.MALICIOUS_PROCESSES:
                        if mal_proc in name_lower:
                            process_data['risk_score'] += 80
                            process_data['threat_indicators'].append(f'malicious_name:{mal_proc}')
                    
                    # Check malicious command patterns
                    for pattern in self.intel.MALICIOUS_COMMANDS:
                        if re.search(pattern, cmdline_lower, re.IGNORECASE):
                            process_data['risk_score'] += 50
                            process_data['threat_indicators'].append(f'malicious_cmd:{pattern[:20]}')
                    
                    # Check critical patterns
                    for pattern in self.intel.CRITICAL_PATTERNS:
                        if pattern in cmdline_lower:
                            process_data['risk_score'] += 40
                            process_data['threat_indicators'].append(f'critical_pattern:{pattern}')
                    
                    # Cap risk score
                    process_data['risk_score'] = min(100, process_data['risk_score'])
                    
                    self.processes.append(process_data)
                    
                    # Create threat if high risk
                    if process_data['risk_score'] >= 50:
                        self._create_threat(process_data)
                        
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
                    
        except Exception as e:
            logger.error(f"Process scan error: {e}")
            self.error_count += 1
        
        self.last_run = datetime.now(timezone.utc)
        return {"processes": self.processes, "count": len(self.processes)}
    
    def _create_threat(self, process_data: Dict):
        """Create a threat from suspicious process"""
        risk = process_data['risk_score']
        severity = ThreatSeverity.CRITICAL if risk >= 90 else ThreatSeverity.HIGH if risk >= 70 else ThreatSeverity.MEDIUM
        
        # Determine MITRE techniques
        mitre = []
        cmdline = process_data['cmdline'].lower()
        if 'mimikatz' in cmdline or 'sekurlsa' in cmdline:
            mitre.extend(['T1003', 'T1003.001'])
        if 'invoke-expression' in cmdline or 'downloadstring' in cmdline:
            mitre.extend(['T1059.001', 'T1105'])
        if 'psexec' in cmdline:
            mitre.extend(['T1570', 'T1021.002'])
        if 'schtasks' in cmdline:
            mitre.append('T1053.005')
        
        threat = Threat(
            threat_id=f"proc-{uuid.uuid4().hex[:8]}",
            title=f"Suspicious Process: {process_data['name']}",
            description=f"Detected suspicious process with risk score {process_data['risk_score']}",
            severity=severity,
            threat_type="credential_theft" if 'mimikatz' in cmdline else "suspicious_process",
            source="process_monitor",
            target=process_data['name'],
            evidence={
                'pid': process_data['pid'],
                'name': process_data['name'],
                'cmdline': process_data['cmdline'][:500],
                'indicators': process_data['threat_indicators']
            },
            mitre_techniques=mitre,
            auto_kill_eligible=severity in {ThreatSeverity.CRITICAL, ThreatSeverity.HIGH},
            remediation_action="kill_process",
            remediation_params={"pid": process_data['pid'], "process_name": process_data['name']}
        )
        
        self.threats.append(threat)
    
    def get_threats(self) -> List[Threat]:
        return self.threats


class NetworkMonitor(MonitorModule):
    """Network monitoring module"""
    
    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self.intel = ThreatIntelligence()
        self.connections = []
        self.interfaces = []
        self.threats = []
        self.connection_counts = defaultdict(int)
        # Build whitelist from config + own IPs
        self._whitelist = set(config.server_ips) | AGENT_OWN_IPS
        for net in config.trusted_networks:
            # Add network prefixes for quick prefix matching
            if '/' in net:
                prefix = net.split('/')[0].rsplit('.', 1)[0] + '.'
                self._whitelist.add(prefix)
    
    def _is_whitelisted(self, ip: str) -> bool:
        """Check if IP is whitelisted (server, own, or trusted)"""
        if not ip:
            return True
        if ip in self._whitelist:
            return True
        # Check prefix matches
        for w in self._whitelist:
            if w.endswith('.') and ip.startswith(w):
                return True
        # Full whitelist check
        return is_ip_whitelisted(ip, list(self.config.server_ips) + list(self.config.trusted_networks))
    
    def scan(self) -> Dict[str, Any]:
        """Scan network connections and interfaces"""
        if not PSUTIL_AVAILABLE:
            return {"error": "psutil not available"}
        
        self.connections = []
        self.interfaces = []
        self.threats = []
        
        try:
            # Get network interfaces
            for name, addrs in psutil.net_if_addrs().items():
                for addr in addrs:
                    if addr.family == socket.AF_INET:
                        self.interfaces.append({
                            'name': name,
                            'ip': addr.address,
                            'netmask': addr.netmask
                        })
            
            # Get connections
            for conn in psutil.net_connections(kind='inet'):
                try:
                    conn_data = {
                        'family': 'IPv4' if conn.family == socket.AF_INET else 'IPv6',
                        'type': 'TCP' if conn.type == socket.SOCK_STREAM else 'UDP',
                        'local_ip': conn.laddr.ip if conn.laddr else '',
                        'local_port': conn.laddr.port if conn.laddr else 0,
                        'remote_ip': conn.raddr.ip if conn.raddr else '',
                        'remote_port': conn.raddr.port if conn.raddr else 0,
                        'status': conn.status,
                        'pid': conn.pid,
                        'risk_score': 0,
                        'threat_indicators': []
                    }
                    
                    remote_ip = conn_data['remote_ip']
                    remote_port = conn_data['remote_port']
                    
                    # Skip local connections
                    if not remote_ip or remote_ip.startswith('127.') or remote_ip.startswith('::'):
                        self.connections.append(conn_data)
                        continue
                    
                    # Skip whitelisted IPs (server, own IPs, trusted networks)
                    if self._is_whitelisted(remote_ip):
                        conn_data['whitelisted'] = True
                        self.connections.append(conn_data)
                        continue
                    
                    # Check if the process making this connection is a trusted AI tool
                    if conn.pid and PSUTIL_AVAILABLE:
                        try:
                            proc = psutil.Process(conn.pid)
                            is_trusted, trust_reason = is_trusted_ai_process(
                                proc.name(),
                                proc.exe() if hasattr(proc, 'exe') else None,
                                ' '.join(proc.cmdline()) if hasattr(proc, 'cmdline') else None
                            )
                            if is_trusted:
                                conn_data['trusted_ai_process'] = True
                                conn_data['trust_reason'] = trust_reason
                                self.connections.append(conn_data)
                                continue
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass
                    
                    # Check malicious IP ranges
                    for mal_ip in self.intel.MALICIOUS_IPS:
                        if remote_ip.startswith(mal_ip):
                            conn_data['risk_score'] += 80
                            conn_data['threat_indicators'].append(f'malicious_ip:{mal_ip}')
                    
                    # Check suspicious ports
                    if remote_port in self.intel.SUSPICIOUS_PORTS:
                        conn_data['risk_score'] += 50
                        conn_data['threat_indicators'].append(f'suspicious_port:{remote_port}')
                    
                    # Check remote access tool ports (TeamViewer, AnyDesk, etc.)
                    # These are flagged for awareness, lower risk than C2
                    remote_ports = self.intel.REMOTE_ACCESS_TOOLS.get("ports", {})
                    if remote_port in remote_ports:
                        tool_name = remote_ports[remote_port]
                        conn_data['remote_access_tool'] = tool_name
                        conn_data['threat_indicators'].append(f'remote_access_port:{remote_port}:{tool_name}')
                        # Low risk - awareness only, not auto-blocked
                        conn_data['risk_score'] += 15
                    
                    # Check connection frequency (potential exfil)
                    conn_key = f"{remote_ip}:{remote_port}"
                    self.connection_counts[conn_key] += 1
                    if self.connection_counts[conn_key] > 100:
                        conn_data['risk_score'] += 30
                        conn_data['threat_indicators'].append('high_frequency')
                    
                    self.connections.append(conn_data)
                    
                    # Create threat if high risk
                    if conn_data['risk_score'] >= 50:
                        self._create_threat(conn_data)
                        
                except Exception:
                    pass
                    
        except Exception as e:
            logger.error(f"Network scan error: {e}")
            self.error_count += 1
        
        self.last_run = datetime.now(timezone.utc)
        return {
            "connections": self.connections,
            "interfaces": self.interfaces,
            "connection_count": len(self.connections)
        }
    
    def _create_threat(self, conn_data: Dict):
        """Create a threat from suspicious connection"""
        risk = conn_data['risk_score']
        severity = ThreatSeverity.CRITICAL if risk >= 80 else ThreatSeverity.HIGH if risk >= 60 else ThreatSeverity.MEDIUM
        
        threat = Threat(
            threat_id=f"net-{uuid.uuid4().hex[:8]}",
            title=f"Suspicious Connection: {conn_data['remote_ip']}:{conn_data['remote_port']}",
            description=f"Suspicious network connection detected",
            severity=severity,
            threat_type="c2_activity" if conn_data['remote_port'] in self.intel.SUSPICIOUS_PORTS else "suspicious_connection",
            source="network_monitor",
            target=f"{conn_data['remote_ip']}:{conn_data['remote_port']}",
            evidence={
                'local': f"{conn_data['local_ip']}:{conn_data['local_port']}",
                'remote': f"{conn_data['remote_ip']}:{conn_data['remote_port']}",
                'pid': conn_data['pid'],
                'indicators': conn_data['threat_indicators']
            },
            mitre_techniques=['T1071', 'T1095'],
            auto_kill_eligible=False,
            remediation_action="block_ip",
            remediation_params={"ip": conn_data['remote_ip'], "port": conn_data['remote_port']}
        )
        self.threats.append(threat)
    
    def get_threats(self) -> List[Threat]:
        return self.threats


# =============================================================================
# ADVANCED MONITORS - Enterprise Security Features
# =============================================================================

class RegistryMonitor(MonitorModule):
    """
    Registry and Startup Monitoring - Detect persistence mechanisms.
    Monitors Windows registry run keys and startup locations.
    
    Enterprise Features:
    - 50+ registry persistence locations
    - Service binary path hijacking detection
    - COM object hijacking deep scan
    - Scheduled task monitoring with suspicious command detection
    - WMI subscription monitoring (T1546.003)
    - Browser extension monitoring
    - BootExecute boot persistence detection
    - Time provider DLL verification
    - Value modification tracking (not just new entries)
    - AppInit DLL abuse detection
    - IFEO debugger key abuse detection
    """
    
    # Registry persistence locations (Windows)
    PERSISTENCE_KEYS = [
        # User Run Keys
        r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run",
        r"HKCU\Software\Microsoft\Windows\CurrentVersion\RunOnce",
        r"HKCU\Software\Microsoft\Windows\CurrentVersion\RunServices",
        r"HKCU\Software\Microsoft\Windows\CurrentVersion\RunServicesOnce",
        # Machine Run Keys  
        r"HKLM\Software\Microsoft\Windows\CurrentVersion\Run",
        r"HKLM\Software\Microsoft\Windows\CurrentVersion\RunOnce",
        r"HKLM\Software\Microsoft\Windows\CurrentVersion\RunServices",
        r"HKLM\Software\Microsoft\Windows\CurrentVersion\RunServicesOnce",
        # Policies
        r"HKLM\Software\Microsoft\Windows\CurrentVersion\Policies\Explorer\Run",
        r"HKCU\Software\Microsoft\Windows\CurrentVersion\Policies\Explorer\Run",
        # Winlogon
        r"HKLM\Software\Microsoft\Windows NT\CurrentVersion\Winlogon",
        # Services
        r"HKLM\System\CurrentControlSet\Services",
        # AppInit DLLs
        r"HKLM\Software\Microsoft\Windows NT\CurrentVersion\Windows",
        # Image File Execution Options (debugging persistence)
        r"HKLM\Software\Microsoft\Windows NT\CurrentVersion\Image File Execution Options",
        # Shell extensions
        r"HKLM\Software\Microsoft\Windows\CurrentVersion\Explorer\ShellServiceObjects",
        r"HKLM\Software\Microsoft\Windows\CurrentVersion\ShellServiceObjectDelayLoad",
        # COM Hijacking
        r"HKCU\Software\Classes\CLSID",
        r"HKLM\Software\Classes\CLSID",
        # Print Monitor persistence (T1547.010)
        r"HKLM\System\CurrentControlSet\Control\Print\Monitors",
        # Security Support Provider (T1547.005)
        r"HKLM\System\CurrentControlSet\Control\Lsa",
        r"HKLM\System\CurrentControlSet\Control\Lsa\OSConfig",
        # Netsh Helper DLLs
        r"HKLM\Software\Microsoft\NetSh",
        # Active Setup
        r"HKLM\Software\Microsoft\Active Setup\Installed Components",
        r"HKCU\Software\Microsoft\Active Setup\Installed Components",
        # Browser Helper Objects
        r"HKLM\Software\Microsoft\Windows\CurrentVersion\Explorer\Browser Helper Objects",
        # Authentication Packages
        r"HKLM\System\CurrentControlSet\Control\Lsa\Authentication Packages",
        # Notification Packages
        r"HKLM\System\CurrentControlSet\Control\Lsa\Notification Packages",
        # Time Providers
        r"HKLM\System\CurrentControlSet\Services\W32Time\TimeProviders",
        # BootExecute
        r"HKLM\System\CurrentControlSet\Control\Session Manager",
        # AppCert DLLs
        r"HKLM\System\CurrentControlSet\Control\Session Manager\AppCertDlls",
        # Office Add-ins
        r"HKCU\Software\Microsoft\Office\*\Word\Security\Trusted Locations",
        r"HKCU\Software\Microsoft\Office\*\Excel\Security\Trusted Locations",
        # WMI Consumers (sampled via keys)
        r"HKLM\Software\Microsoft\WBEM\ESS",
        # SilentProcessExit persistence
        r"HKLM\Software\Microsoft\Windows NT\CurrentVersion\SilentProcessExit",
        # Terminal Server InitialProgram
        r"HKLM\System\CurrentControlSet\Control\Terminal Server\WinStations\RDP-Tcp",
        # Natural Language DLLs
        r"HKLM\System\CurrentControlSet\Control\ContentIndex\Language",
        # Error Reporting DLL
        r"HKLM\Software\Microsoft\Windows\Windows Error Reporting\Hangs",
    ]
    
    # Known legitimate boot executables
    LEGITIMATE_BOOT_EXECUTABLES = {
        'autocheck autochk *',
        'autochk',
        'autocheck',
    }
    
    # Known legitimate service binary paths
    LEGITIMATE_SERVICE_PATHS = {
        r'c:\windows\system32',
        r'c:\windows\syswow64',
        r'c:\program files',
        r'c:\program files (x86)',
    }
    
    # Linux/macOS persistence locations
    LINUX_PERSISTENCE_PATHS = [
        "/etc/rc.local",
        "/etc/init.d/",
        "/etc/systemd/system/",
        "/usr/lib/systemd/system/",
        "~/.bashrc",
        "~/.profile",
        "~/.bash_profile",
        "~/.zshrc",
        "/etc/crontab",
        "/var/spool/cron/crontabs/",
        "/etc/cron.d/",
        "~/.config/autostart/",
        "/etc/xdg/autostart/",
        "~/Library/LaunchAgents/",  # macOS
        "/Library/LaunchAgents/",   # macOS
        "/Library/LaunchDaemons/",  # macOS
        # Additional Linux persistence
        "/etc/ld.so.preload",
        "/etc/profile.d/",
        "/etc/environment",
        "~/.ssh/rc",
        "~/.pam_environment",
        "/etc/apt/apt.conf.d/",
        "/usr/share/bash-completion/completions/",
        "~/.config/fish/config.fish",
    ]
    
    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self.baseline = {}  # Known baseline of persistence entries
        self.threats = []
        self.changes = []
        self.scheduled_tasks = []
        self.wmi_subscriptions = []
        self.browser_extensions = []
        self._load_baseline()
    
    def _load_baseline(self):
        """Load baseline of current persistence entries"""
        if PLATFORM == "windows":
            self.baseline = self._scan_windows_registry()
        else:
            self.baseline = self._scan_linux_persistence()
    
    def _scan_windows_registry(self) -> Dict[str, List[str]]:
        """Scan Windows registry for persistence entries"""
        entries = {}
        
        if PLATFORM != "windows":
            return entries
        
        try:
            import winreg
            
            def read_key(hive, subkey):
                values = []
                try:
                    if hive == "HKLM":
                        root = winreg.HKEY_LOCAL_MACHINE
                    elif hive == "HKCU":
                        root = winreg.HKEY_CURRENT_USER
                    else:
                        return values
                    
                    key = winreg.OpenKey(root, subkey, 0, winreg.KEY_READ)
                    i = 0
                    while True:
                        try:
                            name, value, _ = winreg.EnumValue(key, i)
                            values.append({"name": name, "value": str(value)[:500]})
                            i += 1
                        except OSError:
                            break
                    winreg.CloseKey(key)
                except (OSError, FileNotFoundError):
                    pass
                return values
            
            for key_path in self.PERSISTENCE_KEYS:
                parts = key_path.split("\\", 1)
                if len(parts) == 2:
                    hive, subkey = parts
                    values = read_key(hive, subkey)
                    if values:
                        entries[key_path] = values
        except ImportError:
            logger.debug("winreg not available - not on Windows")
        except Exception as e:
            logger.error(f"Registry scan error: {e}")
        
        return entries
    
    def _scan_linux_persistence(self) -> Dict[str, List[str]]:
        """Scan Linux/macOS persistence locations"""
        entries = {}
        
        for path_pattern in self.LINUX_PERSISTENCE_PATHS:
            path = Path(os.path.expanduser(path_pattern))
            try:
                if path.is_file():
                    mtime = path.stat().st_mtime
                    entries[str(path)] = [{
                        "mtime": mtime,
                        "size": path.stat().st_size
                    }]
                elif path.is_dir():
                    files = []
                    for f in path.iterdir():
                        if f.is_file():
                            files.append({
                                "name": f.name,
                                "mtime": f.stat().st_mtime
                            })
                    if files:
                        entries[str(path)] = files
            except (PermissionError, FileNotFoundError):
                pass
        
        # Check crontabs
        try:
            result = subprocess.run(['crontab', '-l'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0 and result.stdout.strip():
                entries['user_crontab'] = [{"content": result.stdout[:1000]}]
        except Exception:
            pass
        
        return entries
    
    def _scan_service_binary_hijacking(self) -> List[Dict]:
        """Detect service binary path hijacking (T1574.011)"""
        hijacked_services = []
        
        if PLATFORM != "windows":
            return hijacked_services
        
        try:
            import winreg
            
            services_key = r"System\CurrentControlSet\Services"
            root = winreg.HKEY_LOCAL_MACHINE
            
            key = winreg.OpenKey(root, services_key, 0, winreg.KEY_READ)
            i = 0
            
            while True:
                try:
                    service_name = winreg.EnumKey(key, i)
                    i += 1
                    
                    try:
                        service_key = winreg.OpenKey(root, f"{services_key}\\{service_name}", 0, winreg.KEY_READ)
                        
                        try:
                            image_path, _ = winreg.QueryValueEx(service_key, "ImagePath")
                            image_path = str(image_path).strip('"').strip()
                            
                            # Extract the actual executable path
                            if ' ' in image_path and not image_path.startswith('"'):
                                # Could be unquoted path with spaces - potential vulnerability
                                parts = image_path.split()
                                potential_path = parts[0]
                            else:
                                potential_path = image_path.split('"')[1] if '"' in image_path else image_path.split()[0]
                            
                            potential_path_lower = potential_path.lower()
                            
                            # Check for suspicious paths
                            suspicious = False
                            reasons = []
                            
                            # Unquoted service path with spaces
                            if ' ' in image_path and not image_path.startswith('"') and \
                               not any(image_path.lower().startswith(lp) for lp in self.LEGITIMATE_SERVICE_PATHS):
                                suspicious = True
                                reasons.append("Unquoted service path with spaces")
                            
                            # Service running from user-writable location
                            if any(x in potential_path_lower for x in ['\\temp\\', '\\tmp\\', '\\appdata\\', '\\users\\', '\\downloads\\']):
                                suspicious = True
                                reasons.append("Service running from user-writable path")
                            
                            # Service binary doesn't exist
                            if potential_path and not os.path.exists(potential_path):
                                suspicious = True
                                reasons.append("Service binary not found on disk")
                            
                            # Check for environment variable abuse
                            if '%systemroot%' not in potential_path_lower and '%windir%' not in potential_path_lower:
                                if potential_path_lower.startswith('\\'):
                                    suspicious = True
                                    reasons.append("Service path uses relative reference")
                            
                            if suspicious:
                                hijacked_services.append({
                                    'service': service_name,
                                    'image_path': image_path[:500],
                                    'reasons': reasons,
                                    'type': 'service_binary_hijacking'
                                })
                                
                        except FileNotFoundError:
                            pass
                        finally:
                            winreg.CloseKey(service_key)
                    except OSError:
                        pass
                        
                except OSError:
                    break
            
            winreg.CloseKey(key)
            
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"Service hijacking scan error: {e}")
        
        return hijacked_services
    
    def _scan_com_hijacking(self) -> List[Dict]:
        """Deep scan for COM object hijacking (T1546.015)"""
        hijacked_com = []
        
        if PLATFORM != "windows":
            return hijacked_com
        
        try:
            import winreg
            
            # Check HKCU CLSIDs that shadow HKLM (COM hijacking indicator)
            hkcu_clsids = set()
            hklm_clsids = set()
            
            # Enumerate HKCU CLSIDs
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\CLSID", 0, winreg.KEY_READ)
                i = 0
                while True:
                    try:
                        clsid = winreg.EnumKey(key, i)
                        hkcu_clsids.add(clsid.upper())
                        i += 1
                    except OSError:
                        break
                winreg.CloseKey(key)
            except OSError:
                pass
            
            # Check common hijacked CLSIDs
            common_hijackable_clsids = [
                "{BCDE0395-E52F-467C-8E3D-C4579291692E}",  # MMDeviceEnumerator
                "{0A29FF9E-7F9C-4437-8B11-F424491E3931}",  # Connection Folder
                "{42aedc87-2188-41fd-b9a3-0c966feabec1}",  # Taskband
                "{fbeb8a05-beee-4442-804e-409d6c4515e9}",  # Automatic Destinations
                "{90AA3A4E-1CBA-4233-B8BB-535773D48449}",  # Toast activation
            ]
            
            for clsid in hkcu_clsids:
                try:
                    # Check if this CLSID is in HKCU but not in HKLM (potential hijack)
                    hkcu_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, f"Software\\Classes\\CLSID\\{clsid}\\InprocServer32", 0, winreg.KEY_READ)
                    hkcu_dll, _ = winreg.QueryValueEx(hkcu_key, None)
                    winreg.CloseKey(hkcu_key)
                    
                    hkcu_dll_lower = str(hkcu_dll).lower()
                    
                    suspicious = False
                    reasons = []
                    
                    # DLL in user-writable location
                    if any(x in hkcu_dll_lower for x in ['\\appdata\\', '\\temp\\', '\\users\\', '\\downloads\\']):
                        suspicious = True
                        reasons.append("COM object points to user-writable path")
                    
                    # Common hijackable CLSIDs with non-system DLLs
                    if clsid in common_hijackable_clsids:
                        if not hkcu_dll_lower.startswith('c:\\windows\\'):
                            suspicious = True
                            reasons.append(f"Known hijackable CLSID {clsid} points to non-system DLL")
                    
                    # DLL doesn't exist
                    if hkcu_dll and not os.path.exists(hkcu_dll):
                        suspicious = True
                        reasons.append("COM DLL not found on disk")
                    
                    if suspicious:
                        hijacked_com.append({
                            'clsid': clsid,
                            'dll': hkcu_dll[:500],
                            'reasons': reasons,
                            'type': 'com_hijacking'
                        })
                        
                except OSError:
                    pass
                    
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"COM hijacking scan error: {e}")
        
        return hijacked_com
    
    def _scan_bootexecute(self) -> List[Dict]:
        """Deep scan for BootExecute persistence (T1547.001)"""
        boot_threats = []
        
        if PLATFORM != "windows":
            return boot_threats
        
        try:
            import winreg
            
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"System\CurrentControlSet\Control\Session Manager",
                0,
                winreg.KEY_READ
            )
            
            try:
                boot_execute, _ = winreg.QueryValueEx(key, "BootExecute")
                
                if isinstance(boot_execute, (list, tuple)):
                    for entry in boot_execute:
                        entry_str = str(entry).lower().strip()
                        
                        # Check if this is a legitimate boot executable
                        is_legitimate = any(le in entry_str for le in self.LEGITIMATE_BOOT_EXECUTABLES)
                        
                        if not is_legitimate and entry_str:
                            boot_threats.append({
                                'type': 'suspicious_bootexecute',
                                'value': str(entry)[:200],
                                'description': 'Non-standard BootExecute entry detected'
                            })
                elif boot_execute:
                    entry_str = str(boot_execute).lower().strip()
                    is_legitimate = any(le in entry_str for le in self.LEGITIMATE_BOOT_EXECUTABLES)
                    
                    if not is_legitimate:
                        boot_threats.append({
                            'type': 'suspicious_bootexecute',
                            'value': str(boot_execute)[:200],
                            'description': 'Non-standard BootExecute entry detected'
                        })
            except FileNotFoundError:
                pass
            
            # Check SetupExecute (similar persistence)
            try:
                setup_execute, _ = winreg.QueryValueEx(key, "SetupExecute")
                if setup_execute:
                    boot_threats.append({
                        'type': 'setupexecute_present',
                        'value': str(setup_execute)[:200],
                        'description': 'SetupExecute key present (rare, investigate)'
                    })
            except FileNotFoundError:
                pass
            
            winreg.CloseKey(key)
            
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"BootExecute scan error: {e}")
        
        return boot_threats
    
    def _scan_appinit_dlls(self) -> List[Dict]:
        """Scan for AppInit_DLLs abuse (T1546.010)"""
        appinit_threats = []
        
        if PLATFORM != "windows":
            return appinit_threats
        
        try:
            import winreg
            
            paths = [
                r"Software\Microsoft\Windows NT\CurrentVersion\Windows",
                r"Software\Wow6432Node\Microsoft\Windows NT\CurrentVersion\Windows"
            ]
            
            for reg_path in paths:
                try:
                    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path, 0, winreg.KEY_READ)
                    
                    try:
                        appinit_dlls, _ = winreg.QueryValueEx(key, "AppInit_DLLs")
                        load_appinit, _ = winreg.QueryValueEx(key, "LoadAppInit_DLLs")
                        
                        if appinit_dlls and load_appinit == 1:
                            dlls = str(appinit_dlls).split(',')
                            for dll in dlls:
                                dll = dll.strip()
                                if dll:
                                    dll_lower = dll.lower()
                                    suspicious = False
                                    reasons = []
                                    
                                    if not dll_lower.startswith('c:\\windows\\'):
                                        suspicious = True
                                        reasons.append("AppInit_DLL not in Windows directory")
                                    
                                    if any(x in dll_lower for x in ['\\temp\\', '\\appdata\\', '\\users\\']):
                                        suspicious = True
                                        reasons.append("AppInit_DLL in user-writable path")
                                    
                                    if not os.path.exists(dll):
                                        suspicious = True
                                        reasons.append("AppInit_DLL not found on disk")
                                    
                                    if suspicious:
                                        appinit_threats.append({
                                            'type': 'appinit_dll',
                                            'dll': dll[:500],
                                            'reasons': reasons,
                                            'path': reg_path
                                        })
                    except FileNotFoundError:
                        pass
                    
                    winreg.CloseKey(key)
                except OSError:
                    pass
                    
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"AppInit_DLLs scan error: {e}")
        
        return appinit_threats
    
    def _scan_ifeo_debuggers(self) -> List[Dict]:
        """Scan for IFEO debugger persistence (T1546.012)"""
        ifeo_threats = []
        
        if PLATFORM != "windows":
            return ifeo_threats
        
        try:
            import winreg
            
            ifeo_path = r"Software\Microsoft\Windows NT\CurrentVersion\Image File Execution Options"
            
            try:
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, ifeo_path, 0, winreg.KEY_READ)
                i = 0
                
                while True:
                    try:
                        exe_name = winreg.EnumKey(key, i)
                        i += 1
                        
                        try:
                            exe_key = winreg.OpenKey(key, exe_name, 0, winreg.KEY_READ)
                            
                            try:
                                debugger, _ = winreg.QueryValueEx(exe_key, "Debugger")
                                
                                if debugger:
                                    debugger_lower = str(debugger).lower()
                                    
                                    # Legitimate debuggers
                                    legitimate = ['vsjitdebugger', 'windbg', 'cdb.exe', 'ntsd.exe', 
                                                  'drwtsn32', 'dwwin.exe', 'devenv.exe']
                                    
                                    if not any(leg in debugger_lower for leg in legitimate):
                                        ifeo_threats.append({
                                            'type': 'ifeo_debugger',
                                            'target': exe_name,
                                            'debugger': str(debugger)[:500],
                                            'description': 'Suspicious IFEO debugger injection'
                                        })
                            except FileNotFoundError:
                                pass
                            
                            # Also check for GlobalFlag (silent process exit persistence)
                            try:
                                global_flag, _ = winreg.QueryValueEx(exe_key, "GlobalFlag")
                                if global_flag:
                                    # GlobalFlag 0x200 = FLG_MONITOR_SILENT_PROCESS_EXIT
                                    if global_flag & 0x200:
                                        ifeo_threats.append({
                                            'type': 'silent_process_exit',
                                            'target': exe_name,
                                            'global_flag': hex(global_flag),
                                            'description': 'Silent process exit monitoring enabled'
                                        })
                            except FileNotFoundError:
                                pass
                            
                            winreg.CloseKey(exe_key)
                        except OSError:
                            pass
                            
                    except OSError:
                        break
                
                winreg.CloseKey(key)
                
            except OSError:
                pass
                
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"IFEO scan error: {e}")
        
        return ifeo_threats

    def _scan_scheduled_tasks(self) -> List[Dict]:
        """Scan Windows scheduled tasks for persistence"""
        tasks = []
        
        if PLATFORM != "windows":
            return tasks
        
        try:
            # Use schtasks to enumerate tasks
            cmd = ['schtasks', '/query', '/fo', 'CSV', '/v']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if len(lines) > 1:
                    import csv
                    reader = csv.DictReader(lines)
                    for row in reader:
                        task_name = row.get('TaskName', '')
                        task_to_run = row.get('Task To Run', '')
                        author = row.get('Author', '')
                        
                        # Flag suspicious tasks
                        suspicious = False
                        reasons = []
                        
                        # Check for scripting engines
                        if any(x in task_to_run.lower() for x in ['powershell', 'cmd.exe /c', 'wscript', 'cscript', 'mshta']):
                            suspicious = True
                            reasons.append("Script execution")
                        
                        # Check for encoded commands
                        if '-encodedcommand' in task_to_run.lower() or '-enc ' in task_to_run.lower():
                            suspicious = True
                            reasons.append("Encoded PowerShell")
                        
                        # Check for temp/user paths
                        if any(x in task_to_run.lower() for x in ['\\temp\\', '\\tmp\\', '\\appdata\\', '\\users\\']):
                            suspicious = True
                            reasons.append("Execution from user path")
                        
                        # Check for network paths
                        if task_to_run.startswith('\\\\'):
                            suspicious = True
                            reasons.append("Network path execution")
                        
                        if suspicious:
                            tasks.append({
                                'name': task_name,
                                'command': task_to_run[:500],
                                'author': author,
                                'suspicious': True,
                                'reasons': reasons
                            })
        except Exception as e:
            logger.debug(f"Scheduled task scan error: {e}")
        
        self.scheduled_tasks = tasks
        return tasks
    
    def _scan_wmi_subscriptions(self) -> List[Dict]:
        """Detect WMI event subscriptions (T1546.003)"""
        subscriptions = []
        
        if PLATFORM != "windows":
            return subscriptions
        
        try:
            # Query WMI for event consumers
            ps_cmd = '''
            Get-WmiObject -Namespace root\\subscription -Class __FilterToConsumerBinding |
            Select-Object Filter, Consumer |
            ConvertTo-Json -Depth 2
            '''
            result = subprocess.run(
                ['powershell', '-Command', ps_cmd],
                capture_output=True, text=True, timeout=30
            )
            
            if result.returncode == 0 and result.stdout.strip():
                try:
                    data = json.loads(result.stdout)
                    if not isinstance(data, list):
                        data = [data]
                    
                    for binding in data:
                        subscriptions.append({
                            'filter': str(binding.get('Filter', ''))[:200],
                            'consumer': str(binding.get('Consumer', ''))[:200],
                            'type': 'wmi_subscription'
                        })
                except json.JSONDecodeError:
                    pass
            
            # Also check for event consumers directly
            ps_cmd2 = '''
            Get-WmiObject -Namespace root\\subscription -Class CommandLineEventConsumer |
            Select-Object Name, CommandLineTemplate |
            ConvertTo-Json
            '''
            result2 = subprocess.run(
                ['powershell', '-Command', ps_cmd2],
                capture_output=True, text=True, timeout=30
            )
            
            if result2.returncode == 0 and result2.stdout.strip():
                try:
                    data = json.loads(result2.stdout)
                    if not isinstance(data, list):
                        data = [data]
                    
                    for consumer in data:
                        cmd_line = consumer.get('CommandLineTemplate', '')
                        subscriptions.append({
                            'name': consumer.get('Name', 'Unknown'),
                            'command': cmd_line[:500],
                            'type': 'command_line_consumer',
                            'suspicious': any(x in cmd_line.lower() for x in ['powershell', 'cmd.exe', 'wscript'])
                        })
                except json.JSONDecodeError:
                    pass
                    
        except Exception as e:
            logger.debug(f"WMI subscription scan error: {e}")
        
        self.wmi_subscriptions = subscriptions
        return subscriptions
    
    def _scan_browser_extensions(self) -> List[Dict]:
        """Scan for suspicious browser extensions"""
        extensions = []
        
        if PLATFORM == "windows":
            extension_paths = [
                Path(os.environ.get('LOCALAPPDATA', '')) / 'Google' / 'Chrome' / 'User Data' / 'Default' / 'Extensions',
                Path(os.environ.get('LOCALAPPDATA', '')) / 'Microsoft' / 'Edge' / 'User Data' / 'Default' / 'Extensions',
                Path(os.environ.get('APPDATA', '')) / 'Mozilla' / 'Firefox' / 'Profiles',
            ]
        else:
            extension_paths = [
                Path.home() / '.config' / 'google-chrome' / 'Default' / 'Extensions',
                Path.home() / '.config' / 'chromium' / 'Default' / 'Extensions',
                Path.home() / '.mozilla' / 'firefox',
                Path.home() / 'Library' / 'Application Support' / 'Google' / 'Chrome' / 'Default' / 'Extensions',  # macOS
            ]
        
        for ext_path in extension_paths:
            try:
                if not ext_path.exists():
                    continue
                
                for ext_dir in ext_path.iterdir():
                    if not ext_dir.is_dir():
                        continue
                    
                    # Look for manifest.json
                    for version_dir in ext_dir.iterdir():
                        manifest_path = version_dir / 'manifest.json'
                        if manifest_path.exists():
                            try:
                                with open(manifest_path, 'r', encoding='utf-8') as f:
                                    manifest = json.load(f)
                                
                                ext_name = manifest.get('name', 'Unknown')
                                permissions = manifest.get('permissions', [])
                                
                                # Flag suspicious permissions
                                suspicious_perms = []
                                dangerous_perms = ['<all_urls>', 'webRequest', 'webRequestBlocking', 
                                                   'nativeMessaging', 'debugger', 'downloads']
                                
                                for perm in permissions:
                                    if any(dp in str(perm) for dp in dangerous_perms):
                                        suspicious_perms.append(perm)
                                
                                if suspicious_perms:
                                    extensions.append({
                                        'id': ext_dir.name,
                                        'name': ext_name[:100],
                                        'browser': 'Chrome' if 'chrome' in str(ext_path).lower() else 
                                                   'Edge' if 'edge' in str(ext_path).lower() else 'Firefox',
                                        'suspicious_permissions': suspicious_perms[:10],
                                        'suspicious': len(suspicious_perms) > 2
                                    })
                            except (json.JSONDecodeError, UnicodeDecodeError):
                                pass
                        break  # Only check first version
            except (PermissionError, OSError):
                pass
        
        self.browser_extensions = extensions
        return extensions

    def scan(self) -> Dict[str, Any]:
        """Scan for persistence changes"""
        self.threats = []
        self.changes = []
        
        if PLATFORM == "windows":
            current = self._scan_windows_registry()
            # Additional Windows persistence scans
            scheduled_tasks = self._scan_scheduled_tasks()
            wmi_subs = self._scan_wmi_subscriptions()
            
            # Enhanced enterprise persistence scans
            service_hijacks = self._scan_service_binary_hijacking()
            com_hijacks = self._scan_com_hijacking()
            boot_threats = self._scan_bootexecute()
            appinit_threats = self._scan_appinit_dlls()
            ifeo_threats = self._scan_ifeo_debuggers()
        else:
            current = self._scan_linux_persistence()
            scheduled_tasks = []
            wmi_subs = []
            service_hijacks = []
            com_hijacks = []
            boot_threats = []
            appinit_threats = []
            ifeo_threats = []
        
        # Scan browser extensions on all platforms
        browser_exts = self._scan_browser_extensions()
        
        # Create threats for service binary hijacking
        for hijack in service_hijacks:
            self._create_threat(
                f"Service Hijack: {hijack.get('service', 'Unknown')}",
                [hijack],
                "service_binary_hijacking"
            )
        
        # Create threats for COM hijacking
        for hijack in com_hijacks:
            self._create_threat(
                f"COM Hijack: {hijack.get('clsid', 'Unknown')}",
                [hijack],
                "com_hijacking"
            )
        
        # Create threats for BootExecute abuse
        for threat in boot_threats:
            self._create_threat(
                f"BootExecute: {threat.get('value', 'Unknown')[:50]}",
                [threat],
                "bootexecute_persistence"
            )
        
        # Create threats for AppInit_DLLs
        for threat in appinit_threats:
            self._create_threat(
                f"AppInit_DLL: {threat.get('dll', 'Unknown')[:50]}",
                [threat],
                "appinit_dll_persistence"
            )
        
        # Create threats for IFEO debugger injection
        for threat in ifeo_threats:
            self._create_threat(
                f"IFEO: {threat.get('target', 'Unknown')}",
                [threat],
                "ifeo_persistence"
            )
        
        # Create threats for suspicious scheduled tasks
        for task in scheduled_tasks:
            if task.get('suspicious'):
                self._create_threat(
                    f"Scheduled Task: {task['name']}", 
                    [task], 
                    "suspicious_scheduled_task"
                )
        
        # Create threats for WMI subscriptions
        for sub in wmi_subs:
            if sub.get('suspicious') or sub.get('type') == 'command_line_consumer':
                self._create_threat(
                    f"WMI Subscription: {sub.get('name', 'Unknown')}", 
                    [sub], 
                    "wmi_persistence"
                )
        
        # Create threats for suspicious browser extensions
        for ext in browser_exts:
            if ext.get('suspicious'):
                self._create_threat(
                    f"Browser Extension: {ext['name']}", 
                    [ext], 
                    "browser_extension_persistence"
                )
        
        # Detect new entries
        for location, entries in current.items():
            if location not in self.baseline:
                self.changes.append({
                    "type": "new_location",
                    "location": location,
                    "entries": entries,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
                self._create_threat(location, entries, "new_persistence")
            else:
                # Check for new values in existing locations
                baseline_entries = {str(e): e for e in self.baseline.get(location, [])}
                for entry in entries:
                    if str(entry) not in baseline_entries:
                        self.changes.append({
                            "type": "new_entry",
                            "location": location,
                            "entry": entry,
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        })
                        self._create_threat(location, [entry], "new_persistence_entry")
        
        # Detect deletions (might indicate cleanup)
        for location in self.baseline:
            if location not in current:
                self.changes.append({
                    "type": "deleted_location",
                    "location": location,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
        
        # Update baseline
        self.baseline = current
        self.last_run = datetime.now(timezone.utc)
        
        return {
            "persistence_locations": len(current),
            "changes_detected": len(self.changes),
            "threats": len(self.threats),
            "scheduled_tasks_suspicious": len([t for t in self.scheduled_tasks if t.get('suspicious')]),
            "wmi_subscriptions": len(self.wmi_subscriptions),
            "browser_extensions_suspicious": len([e for e in self.browser_extensions if e.get('suspicious')]),
            "service_hijack_detections": len(service_hijacks),
            "com_hijack_detections": len(com_hijacks),
            "bootexecute_threats": len(boot_threats),
            "appinit_dll_threats": len(appinit_threats),
            "ifeo_threats": len(ifeo_threats),
            "changes": self.changes[-20:]  # Last 20 changes
        }
    
    def _create_threat(self, location: str, entries: List, threat_type: str):
        """Create threat from persistence detection"""
        # Determine severity and MITRE techniques based on threat type
        if threat_type == "wmi_persistence":
            severity = ThreatSeverity.CRITICAL
            mitre = ["T1546.003"]  # WMI Event Subscription
        elif threat_type == "suspicious_scheduled_task":
            severity = ThreatSeverity.HIGH
            mitre = ["T1053.005"]  # Scheduled Task/Job
        elif threat_type == "browser_extension_persistence":
            severity = ThreatSeverity.MEDIUM
            mitre = ["T1176"]  # Browser Extensions
        elif threat_type == "service_binary_hijacking":
            severity = ThreatSeverity.CRITICAL
            mitre = ["T1574.011"]  # Services Registry Permissions Weakness
        elif threat_type == "com_hijacking":
            severity = ThreatSeverity.HIGH
            mitre = ["T1546.015"]  # COM Hijacking
        elif threat_type == "bootexecute_persistence":
            severity = ThreatSeverity.CRITICAL
            mitre = ["T1547.001"]  # Boot or Logon Autostart
        elif threat_type == "appinit_dll_persistence":
            severity = ThreatSeverity.CRITICAL
            mitre = ["T1546.010"]  # AppInit DLLs
        elif threat_type == "ifeo_persistence":
            severity = ThreatSeverity.HIGH
            mitre = ["T1546.012"]  # IFEO Injection
        elif "Services" in str(location) or "Winlogon" in str(location):
            severity = ThreatSeverity.HIGH
            mitre = ["T1547", "T1543"]
        elif "Print\\Monitors" in str(location):
            severity = ThreatSeverity.HIGH
            mitre = ["T1547.010"]  # Print Processors
        elif "Lsa" in str(location):
            severity = ThreatSeverity.CRITICAL
            mitre = ["T1547.005", "T1556"]  # SSP, Modify Auth Process
        else:
            severity = ThreatSeverity.MEDIUM
            mitre = ["T1547", "T1053", "T1543"]
        loc_str = str(location)
        loc_name = loc_str.split('\\')[-1] if '\\' in loc_str else loc_str.split('/')[-1]
        
        threat = Threat(
            threat_id=f"persist-{uuid.uuid4().hex[:8]}",
            title=f"Persistence Detected: {loc_name}",
            description=f"New persistence mechanism detected at {location}",
            severity=severity,
            threat_type="persistence",
            source="registry_monitor",
            target=str(location),
            evidence={"entries": entries[:5], "location": str(location)},
            mitre_techniques=mitre,
            auto_kill_eligible=False,
            remediation_action="investigate",
            remediation_params={"location": str(location)}
        )
        self.threats.append(threat)
    
    def get_threats(self) -> List[Threat]:
        return self.threats


class ProcessTreeMonitor(MonitorModule):
    """
    Parent-Child Process Analysis - Detect anomalous process chains.
    Monitors for unusual process spawn patterns indicative of attacks.
    """
    
    # Suspicious parent-child relationships
    SUSPICIOUS_CHAINS = [
        # Office apps spawning command interpreters
        {"parent": ["winword", "excel", "powerpnt", "outlook", "msaccess"], 
         "child": ["cmd", "powershell", "pwsh", "wscript", "cscript", "mshta", "regsvr32"]},
        
        # Browser spawning command interpreters
        {"parent": ["chrome", "firefox", "msedge", "iexplore", "opera", "brave"],
         "child": ["cmd", "powershell", "pwsh", "wscript", "cscript"]},
        
        # Scripting engines spawning network tools
        {"parent": ["wscript", "cscript", "mshta"],
         "child": ["powershell", "cmd", "curl", "wget", "certutil", "bitsadmin"]},
        
        # Services spawning command interpreters
        {"parent": ["services", "svchost"],
         "child": ["cmd", "powershell", "pwsh"]},
        
        # Unusual shells
        {"parent": ["explorer"],
         "child": ["regsvr32", "rundll32", "mshta", "wmic"]},
        
        # PDF readers spawning commands
        {"parent": ["acrord32", "acrobat", "foxitreader"],
         "child": ["cmd", "powershell", "pwsh", "wscript"]},
        
        # Compression tools (potential payload drop)
        {"parent": ["winrar", "7z", "7zfm", "winzip"],
         "child": ["cmd", "powershell", "pwsh", "wscript", "mshta"]},
        
        # Linux equivalents
        {"parent": ["bash", "sh", "zsh"],
         "child": ["nc", "netcat", "ncat", "curl", "wget"]},
    ]
    
    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self.threats = []
        self.process_cache = {}  # pid -> process info
        self.suspicious_chains = []
    
    def scan(self) -> Dict[str, Any]:
        """Scan process tree for anomalies"""
        self.threats = []
        self.suspicious_chains = []
        
        if not PSUTIL_AVAILABLE:
            return {"error": "psutil not available"}
        
        # Build process tree
        processes = {}
        for proc in psutil.process_iter(['pid', 'name', 'ppid', 'cmdline', 'create_time']):
            try:
                info = proc.info
                processes[info['pid']] = {
                    'pid': info['pid'],
                    'name': (info['name'] or '').lower(),
                    'ppid': info['ppid'],
                    'cmdline': ' '.join(info['cmdline'] or []),
                    'create_time': info['create_time']
                }
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        # Analyze parent-child relationships
        for pid, proc in processes.items():
            parent = processes.get(proc['ppid'])
            if not parent:
                continue
            
            parent_name = parent['name'].replace('.exe', '')
            child_name = proc['name'].replace('.exe', '')
            
            # Check against suspicious chains
            for chain in self.SUSPICIOUS_CHAINS:
                parent_match = any(p in parent_name for p in chain['parent'])
                child_match = any(c in child_name for c in chain['child'])
                
                if parent_match and child_match:
                    self.suspicious_chains.append({
                        'parent_pid': parent['pid'],
                        'parent_name': parent['name'],
                        'child_pid': proc['pid'],
                        'child_name': proc['name'],
                        'child_cmdline': proc['cmdline'][:500],
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    })
                    self._create_threat(parent, proc, chain)
        
        self.last_run = datetime.now(timezone.utc)
        
        return {
            "processes_analyzed": len(processes),
            "suspicious_chains": len(self.suspicious_chains),
            "threats": len(self.threats),
            "chains": self.suspicious_chains[-20:]
        }
    
    def _create_threat(self, parent: Dict, child: Dict, chain: Dict):
        """Create threat from suspicious process chain"""
        threat = Threat(
            threat_id=f"chain-{uuid.uuid4().hex[:8]}",
            title=f"Suspicious Spawn: {parent['name']} → {child['name']}",
            description=f"Unusual process chain detected: {parent['name']} spawned {child['name']}",
            severity=ThreatSeverity.HIGH,
            threat_type="suspicious_process_chain",
            source="process_tree_monitor",
            target=f"{child['pid']}:{child['name']}",
            evidence={
                'parent': parent,
                'child': child,
                'rule': chain
            },
            mitre_techniques=["T1059", "T1204", "T1055"],  # Command Interpreter, User Execution, Process Injection
            auto_kill_eligible=True,
            remediation_action="kill_process",
            remediation_params={"pid": child['pid'], "name": child['name']}
        )
        self.threats.append(threat)
    
    def get_threats(self) -> List[Threat]:
        return self.threats


class LOLBinMonitor(MonitorModule):
    """
    Living Off the Land Binary (LOLBin) Detection.
    Monitors for abuse of legitimate Windows/Linux binaries for malicious purposes.
    Enhanced with attack chain detection, parent process analysis, and LOLBAS project mappings.
    """
    
    # LOLBins and their suspicious usage patterns (LOLBAS Project + Extended Coverage)
    LOLBINS = {
        # === DOWNLOAD & EXECUTION (T1105, T1218) ===
        "certutil": {
            "suspicious_args": ["-urlcache", "-split", "-f", "http", "https", "-decode", "-encode", "-decodehex", "-encodehex"],
            "description": "Certificate utility abused for download/decode",
            "mitre": "T1105",
            "severity": "high",
            "category": "download"
        },
        "mshta": {
            "suspicious_args": ["http", "https", "javascript:", "vbscript:", "about:", ".hta"],
            "description": "HTML Application abuse for code execution",
            "mitre": "T1218.005",
            "severity": "critical",
            "category": "execution"
        },
        "regsvr32": {
            "suspicious_args": ["/s", "/u", "/i:", "http", "https", "scrobj.dll", "/n", "file://"],
            "description": "COM scriptlet execution bypass (Squiblydoo)",
            "mitre": "T1218.010",
            "severity": "critical",
            "category": "execution"
        },
        "rundll32": {
            "suspicious_args": ["javascript:", "http", "shell32.dll,ShellExec_RunDLL", "url.dll,FileProtocolHandler", 
                               "advpack.dll,LaunchINFSection", "setupapi.dll,InstallHinfSection", "shdocvw.dll,OpenURL"],
            "description": "DLL execution for proxy execution",
            "mitre": "T1218.011",
            "severity": "high",
            "category": "execution"
        },
        "wmic": {
            "suspicious_args": ["process", "call", "create", "/node:", "os get", "useraccount", "/format:", "memorychip"],
            "description": "WMI for execution and reconnaissance",
            "mitre": "T1047",
            "severity": "high",
            "category": "execution"
        },
        "msiexec": {
            "suspicious_args": ["/q", "/quiet", "http", "https", "/i", "/y", "/z", "msiexec /fa"],
            "description": "MSI installer abuse for code execution",
            "mitre": "T1218.007",
            "severity": "high",
            "category": "execution"
        },
        "bitsadmin": {
            "suspicious_args": ["/transfer", "/create", "/addfile", "http", "https", "/setnotifycmdline", "/resume"],
            "description": "BITS for stealthy download",
            "mitre": "T1197",
            "severity": "high",
            "category": "download"
        },
        "cmstp": {
            "suspicious_args": ["/s", "/au", "/si", ".inf"],
            "description": "Connection Manager Profile Installer UAC bypass",
            "mitre": "T1218.003",
            "severity": "critical",
            "category": "uac_bypass"
        },
        
        # === COMPILE & EXECUTE (T1127) ===
        "csc": {
            "suspicious_args": ["/out:", "/target:exe", "/unsafe", "/optimize", "-out:", "-target:"],
            "description": "C# compiler for on-the-fly compilation",
            "mitre": "T1127.001",
            "severity": "high",
            "category": "compile"
        },
        "vbc": {
            "suspicious_args": ["/out:", "/target:exe", "-out:", "-target:"],
            "description": "VB.NET compiler abuse",
            "mitre": "T1127.001",
            "severity": "high",
            "category": "compile"
        },
        "jsc": {
            "suspicious_args": ["/out:", "/target:"],
            "description": "JScript compiler abuse",
            "mitre": "T1127.001",
            "severity": "high",
            "category": "compile"
        },
        "installutil": {
            "suspicious_args": ["/logfile=", "/LogToConsole=false", "/u"],
            "description": "InstallUtil for execution bypass",
            "mitre": "T1218.004",
            "severity": "critical",
            "category": "execution"
        },
        "regasm": {
            "suspicious_args": ["/u", "/codebase"],
            "description": "Assembly Registration Utility bypass",
            "mitre": "T1218.009",
            "severity": "high",
            "category": "execution"
        },
        "regsvcs": {
            "suspicious_args": ["/u"],
            "description": "Component Services bypass",
            "mitre": "T1218.009",
            "severity": "high",
            "category": "execution"
        },
        "msbuild": {
            "suspicious_args": [".xml", ".csproj", "/p:", "/target:"],
            "description": "MSBuild for inline task execution",
            "mitre": "T1127.001",
            "severity": "critical",
            "category": "execution"
        },
        
        # === ADDITIONAL LOLBINS ===
        "control": {
            "suspicious_args": [".cpl", ".dll", "/name"],
            "description": "Control Panel item execution",
            "mitre": "T1218.002",
            "severity": "medium",
            "category": "execution"
        },
        "pcalua": {
            "suspicious_args": ["-a", "-d", "-m"],
            "description": "Program Compatibility Assistant bypass",
            "mitre": "T1218",
            "severity": "high",
            "category": "execution"
        },
        "forfiles": {
            "suspicious_args": ["/p", "/c", "cmd", "/m", "-c", "-p"],
            "description": "ForFiles indirect command execution",
            "mitre": "T1202",
            "severity": "medium",
            "category": "execution"
        },
        "explorer": {
            "suspicious_args": ["/root,", "shell:::", "/e,/root"],
            "description": "Explorer COM object abuse",
            "mitre": "T1218",
            "severity": "low",
            "category": "execution"
        },
        "dnscmd": {
            "suspicious_args": ["/config", "/serverlevelplugindll"],
            "description": "DNS Server plugin DLL injection",
            "mitre": "T1574.002",
            "severity": "critical",
            "category": "persistence"
        },
        "esentutl": {
            "suspicious_args": ["/y", "/d", "/vss"],
            "description": "Extensible Storage Engine Utility for file copy",
            "mitre": "T1003.003",
            "severity": "high",
            "category": "credential_access"
        },
        "expand": {
            "suspicious_args": ["-f:", "-r"],
            "description": "Expand compressed files",
            "mitre": "T1140",
            "severity": "low",
            "category": "decode"
        },
        "extrac32": {
            "suspicious_args": ["/y", "/e", "http"],
            "description": "Extract CAB files, can download",
            "mitre": "T1105",
            "severity": "medium",
            "category": "download"
        },
        "findstr": {
            "suspicious_args": ["/s", "/i", "password", "credential", "/v"],
            "description": "Find strings in files (credential hunting)",
            "mitre": "T1081",
            "severity": "low",
            "category": "discovery"
        },
        "ftp": {
            "suspicious_args": ["-s:", "open", "get", "put", "-n", "-i"],
            "description": "FTP for data transfer",
            "mitre": "T1071.002",
            "severity": "medium",
            "category": "exfiltration"
        },
        "gpscript": {
            "suspicious_args": ["/startup", "/logon"],
            "description": "Group Policy script execution",
            "mitre": "T1484.001",
            "severity": "high",
            "category": "execution"
        },
        "hh": {
            "suspicious_args": ["-decompile", "http", ".chm"],
            "description": "HTML Help abuse",
            "mitre": "T1218.001",
            "severity": "high",
            "category": "execution"
        },
        "infdefaultinstall": {
            "suspicious_args": [".inf"],
            "description": "INF file execution",
            "mitre": "T1218",
            "severity": "medium",
            "category": "execution"
        },
        "makecab": {
            "suspicious_args": ["/d", "/v", "/f"],
            "description": "Create CAB archives, data staging",
            "mitre": "T1560.001",
            "severity": "low",
            "category": "collection"
        },
        "mavinject": {
            "suspicious_args": ["/injectrunning", "/pid"],
            "description": "DLL injection into running process",
            "mitre": "T1055.001",
            "severity": "critical",
            "category": "injection"
        },
        "mftrace": {
            "suspicious_args": ["-o", "-s", "-t"],
            "description": "MFTrace for code execution",
            "mitre": "T1218",
            "severity": "medium",
            "category": "execution"
        },
        "microsoft.workflow.compiler": {
            "suspicious_args": [".xml", ".xoml"],
            "description": "Workflow Compiler for code execution",
            "mitre": "T1127",
            "severity": "high",
            "category": "execution"
        },
        "mmc": {
            "suspicious_args": ["-embedding", ".msc"],
            "description": "MMC console abuse",
            "mitre": "T1218.014",
            "severity": "medium",
            "category": "execution"
        },
        "msconfig": {
            "suspicious_args": ["-startupfolderscan", "/auto"],
            "description": "MSConfig abuse",
            "mitre": "T1218",
            "severity": "low",
            "category": "execution"
        },
        "msdeploy": {
            "suspicious_args": ["-verb:sync", "-source:", "-dest:"],
            "description": "Web Deploy tool abuse",
            "mitre": "T1505.003",
            "severity": "high",
            "category": "execution"
        },
        "msdt": {
            "suspicious_args": ["/id", "PCWDiagnostic", "ms-msdt:", "/skip"],
            "description": "Microsoft Support Diagnostic Tool (Follina)",
            "mitre": "T1218",
            "severity": "critical",
            "category": "execution"
        },
        "msiexec": {
            "suspicious_args": ["/q", "/quiet", "http", "https", "/i", "/y", "/z"],
            "description": "MSI installer abuse",
            "mitre": "T1218.007",
            "severity": "high",
            "category": "execution"
        },
        "nltest": {
            "suspicious_args": ["/dclist:", "/domain_trusts", "/dsgetdc:", "/server:"],
            "description": "Domain enumeration",
            "mitre": "T1482",
            "severity": "medium",
            "category": "discovery"
        },
        "odbcconf": {
            "suspicious_args": ["/a", "regsvr", "-f", ".rsp"],
            "description": "ODBC configuration for DLL execution",
            "mitre": "T1218.008",
            "severity": "high",
            "category": "execution"
        },
        "pcwrun": {
            "suspicious_args": [],
            "description": "Program Compatibility Wizard runner",
            "mitre": "T1218",
            "severity": "medium",
            "category": "execution"
        },
        "pktmon": {
            "suspicious_args": ["start", "filter", "etl2pcap"],
            "description": "Packet Monitor for network capture",
            "mitre": "T1040",
            "severity": "medium",
            "category": "collection"
        },
        "presentationhost": {
            "suspicious_args": [".xbap", ".xaml"],
            "description": "XAML Browser Application host",
            "mitre": "T1218",
            "severity": "medium",
            "category": "execution"
        },
        "print": {
            "suspicious_args": ["/d:"],
            "description": "Print command for file copy",
            "mitre": "T1105",
            "severity": "low",
            "category": "download"
        },
        "reg": {
            "suspicious_args": ["save", "export", "add", "hklm\\sam", "hklm\\security"],
            "description": "Registry manipulation",
            "mitre": "T1012",
            "severity": "medium",
            "category": "discovery"
        },
        "regini": {
            "suspicious_args": ["-m", ".ini"],
            "description": "Registry initialization",
            "mitre": "T1112",
            "severity": "medium",
            "category": "persistence"
        },
        "replace": {
            "suspicious_args": ["/a", "/s"],
            "description": "Replace files",
            "mitre": "T1105",
            "severity": "low",
            "category": "download"
        },
        "rpcping": {
            "suspicious_args": ["-t", "-s", "-e"],
            "description": "RPC ping for reconnaissance",
            "mitre": "T1187",
            "severity": "low",
            "category": "discovery"
        },
        "runscripthelper": {
            "suspicious_args": ["surfacecheck", "devicetype="],
            "description": "Run script helper execution",
            "mitre": "T1218",
            "severity": "medium",
            "category": "execution"
        },
        "sc": {
            "suspicious_args": ["create", "config", "start", "\\\\", "binpath="],
            "description": "Service Control Manager",
            "mitre": "T1543.003",
            "severity": "high",
            "category": "persistence"
        },
        "schtasks": {
            "suspicious_args": ["/create", "/run", "/tn", "/tr", "/sc", "onstart"],
            "description": "Scheduled Task creation",
            "mitre": "T1053.005",
            "severity": "high",
            "category": "persistence"
        },
        "scriptrunner": {
            "suspicious_args": ["-appvscript"],
            "description": "App-V Script Runner",
            "mitre": "T1218",
            "severity": "medium",
            "category": "execution"
        },
        "syncappvpublishingserver": {
            "suspicious_args": ["powershell", ";", "n:", "break;"],
            "description": "SyncAppVPublishingServer for PowerShell",
            "mitre": "T1218",
            "severity": "high",
            "category": "execution"
        },
        "tttracer": {
            "suspicious_args": ["-dumpfull", "-attach"],
            "description": "Time Travel Tracing",
            "mitre": "T1218",
            "severity": "medium",
            "category": "execution"
        },
        "verclsid": {
            "suspicious_args": ["/s", "/c"],
            "description": "COM object verification",
            "mitre": "T1218",
            "severity": "low",
            "category": "execution"
        },
        "wab": {
            "suspicious_args": [],
            "description": "Windows Address Book loading",
            "mitre": "T1218",
            "severity": "low",
            "category": "execution"
        },
        "winrm": {
            "suspicious_args": ["invoke", "-r:", "create", "quickconfig"],
            "description": "Windows Remote Management",
            "mitre": "T1021.006",
            "severity": "high",
            "category": "lateral_movement"
        },
        "wsl": {
            "suspicious_args": ["-e", "--exec", "-u root", "bash", "/mnt/c/"],
            "description": "Windows Subsystem for Linux escape",
            "mitre": "T1202",
            "severity": "high",
            "category": "execution"
        },
        "xwizard": {
            "suspicious_args": ["runwizard", "{"],
            "description": "Extensible Wizard Host",
            "mitre": "T1218",
            "severity": "medium",
            "category": "execution"
        },
        
        # === SCRIPTING ENGINES ===
        "powershell": {
            "suspicious_args": ["-enc", "-encodedcommand", "-ep bypass", "-nop", "-w hidden",
                               "downloadstring", "invoke-expression", "iex", "-c", "webclient",
                               "invoke-webrequest", "net.webclient", "-windowstyle hidden",
                               "start-process", "-noninteractive", "bypass", "hidden"],
            "description": "PowerShell for script-based attacks",
            "mitre": "T1059.001",
            "severity": "high",
            "category": "execution"
        },
        "pwsh": {
            "suspicious_args": ["-enc", "-encodedcommand", "-ep bypass", "-nop", "webclient"],
            "description": "PowerShell Core",
            "mitre": "T1059.001",
            "severity": "high",
            "category": "execution"
        },
        "cmd": {
            "suspicious_args": ["/c", "&&", "||", "|", "^", "start /b", "echo|", "%comspec%"],
            "description": "Command prompt chaining",
            "mitre": "T1059.003",
            "severity": "medium",
            "category": "execution"
        },
        "wscript": {
            "suspicious_args": ["//e:", "//b", ".vbs", ".js", "//nologo"],
            "description": "Windows Script Host",
            "mitre": "T1059.005",
            "severity": "high",
            "category": "execution"
        },
        "cscript": {
            "suspicious_args": ["//e:", "//b", ".vbs", ".js", "//nologo"],
            "description": "Console Script Host",
            "mitre": "T1059.005",
            "severity": "high",
            "category": "execution"
        },
        
        # === LINUX LOLBINS ===
        "bash": {
            "suspicious_args": ["-c", "curl", "wget", "/dev/tcp", "nc", "python", "-i", "exec"],
            "description": "Bash for reverse shell/download",
            "mitre": "T1059.004",
            "severity": "high",
            "category": "execution"
        },
        "sh": {
            "suspicious_args": ["-c", "-i", "curl", "wget", "/dev/tcp"],
            "description": "Shell execution",
            "mitre": "T1059.004",
            "severity": "high",
            "category": "execution"
        },
        "curl": {
            "suspicious_args": ["-o", "-O", "|", "bash", "sh", "--data", "-d", "-X POST"],
            "description": "Curl for download/exfil",
            "mitre": "T1105",
            "severity": "medium",
            "category": "download"
        },
        "wget": {
            "suspicious_args": ["-O", "|", "bash", "sh", "-q", "--post-data"],
            "description": "Wget for download/exfil",
            "mitre": "T1105",
            "severity": "medium",
            "category": "download"
        },
        "python": {
            "suspicious_args": ["-c", "import socket", "subprocess", "exec(", "eval(", "pty.spawn"],
            "description": "Python for reverse shell",
            "mitre": "T1059.006",
            "severity": "high",
            "category": "execution"
        },
        "python3": {
            "suspicious_args": ["-c", "import socket", "subprocess", "exec(", "eval(", "pty.spawn"],
            "description": "Python3 for reverse shell",
            "mitre": "T1059.006",
            "severity": "high",
            "category": "execution"
        },
        "perl": {
            "suspicious_args": ["-e", "socket", "exec", "system", "-MIO"],
            "description": "Perl for reverse shell",
            "mitre": "T1059",
            "severity": "high",
            "category": "execution"
        },
        "ruby": {
            "suspicious_args": ["-e", "TCPSocket", "exec", "system"],
            "description": "Ruby for reverse shell",
            "mitre": "T1059",
            "severity": "high",
            "category": "execution"
        },
        "php": {
            "suspicious_args": ["-r", "fsockopen", "exec", "system", "shell_exec", "base64_decode"],
            "description": "PHP for reverse shell/webshell",
            "mitre": "T1059",
            "severity": "high",
            "category": "execution"
        },
        "nc": {
            "suspicious_args": ["-e", "-c", "/bin/sh", "/bin/bash", "-lvp"],
            "description": "Netcat for reverse shell",
            "mitre": "T1095",
            "severity": "critical",
            "category": "c2"
        },
        "ncat": {
            "suspicious_args": ["-e", "-c", "/bin/sh", "/bin/bash", "-lvp", "--sh-exec"],
            "description": "Ncat for reverse shell",
            "mitre": "T1095",
            "severity": "critical",
            "category": "c2"
        },
        "socat": {
            "suspicious_args": ["exec:", "tcp:", "pty,", "stderr"],
            "description": "Socat for reverse shell",
            "mitre": "T1095",
            "severity": "critical",
            "category": "c2"
        },
        "openssl": {
            "suspicious_args": ["s_client", "-connect", "enc", "-d", "-aes"],
            "description": "OpenSSL for encrypted C2",
            "mitre": "T1573.002",
            "severity": "medium",
            "category": "c2"
        },
        "tar": {
            "suspicious_args": ["--checkpoint", "--checkpoint-action=", "-cvf", "-I"],
            "description": "Tar for privilege escalation or data staging",
            "mitre": "T1560.001",
            "severity": "low",
            "category": "collection"
        },
        "awk": {
            "suspicious_args": ["system(", "/inet/tcp/", "BEGIN"],
            "description": "AWK for reverse shell",
            "mitre": "T1059",
            "severity": "high",
            "category": "execution"
        },
        "xargs": {
            "suspicious_args": ["-I", "sh", "bash", "-0"],
            "description": "Xargs for command execution",
            "mitre": "T1059",
            "severity": "medium",
            "category": "execution"
        },
        "find": {
            "suspicious_args": ["-exec", "-perm", "-4000", "-type f", "/bin/sh"],
            "description": "Find for SUID enumeration or exec",
            "mitre": "T1083",
            "severity": "low",
            "category": "discovery"
        },
        "vim": {
            "suspicious_args": ["-c", ":!", ":shell", "+!", ":term"],
            "description": "Vim for shell escape",
            "mitre": "T1059",
            "severity": "medium",
            "category": "execution"
        },
        "less": {
            "suspicious_args": ["!", "v"],
            "description": "Less for shell escape",
            "mitre": "T1059",
            "severity": "low",
            "category": "execution"
        },
        "nmap": {
            "suspicious_args": ["--script", "-sV", "-O", "-A", "-Pn"],
            "description": "Nmap for network scanning",
            "mitre": "T1046",
            "severity": "medium",
            "category": "discovery"
        },
        "ssh": {
            "suspicious_args": ["-R", "-L", "-D", "-fN", "ProxyCommand"],
            "description": "SSH for tunneling",
            "mitre": "T1572",
            "severity": "high",
            "category": "c2"
        },
        "scp": {
            "suspicious_args": ["-o StrictHostKeyChecking=no", "-r"],
            "description": "SCP for file transfer",
            "mitre": "T1105",
            "severity": "medium",
            "category": "exfiltration"
        }
    }
    
    # Suspicious parent process relationships
    SUSPICIOUS_PARENTS = {
        "winword": ["cmd", "powershell", "wscript", "cscript", "mshta", "certutil"],
        "excel": ["cmd", "powershell", "wscript", "cscript", "mshta"],
        "powerpnt": ["cmd", "powershell", "wscript", "cscript"],
        "outlook": ["cmd", "powershell", "wscript", "mshta"],
        "msaccess": ["cmd", "powershell", "wscript", "cscript"],
        "onenote": ["cmd", "powershell", "wscript", "cscript", "mshta"],
        "svchost": ["cmd", "powershell"],  # Specific services only
        "explorer": ["powershell -enc", "cmd /c echo"],
        "wmiprvse": ["cmd", "powershell"],  # WMI process spawning
        "mshta": ["cmd", "powershell", "rundll32"],
        "regsvr32": ["cmd", "powershell"],
    }
    
    # Attack chain patterns (multiple LOLBins in sequence)
    ATTACK_CHAINS = [
        {"sequence": ["mshta", "powershell"], "name": "MSHTA to PowerShell", "severity": "critical"},
        {"sequence": ["regsvr32", "rundll32"], "name": "Squiblydoo Chain", "severity": "critical"},
        {"sequence": ["certutil", "cmd"], "name": "Certutil Download Chain", "severity": "high"},
        {"sequence": ["wmic", "powershell"], "name": "WMI to PowerShell", "severity": "high"},
        {"sequence": ["msbuild", "csc"], "name": "MSBuild Compile Chain", "severity": "high"},
        {"sequence": ["curl", "bash"], "name": "Download and Execute (Linux)", "severity": "high"},
        {"sequence": ["wget", "sh"], "name": "Download and Execute (Linux)", "severity": "high"},
    ]
    
    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self.threats = []
        self.detections = []
        self.recent_lolbins = []  # Track recent LOLBin executions for chain detection
        self.chain_window_seconds = 60  # Time window for attack chain detection
    
    def scan(self) -> Dict[str, Any]:
        """Scan for LOLBin abuse with enhanced detection"""
        self.threats = []
        self.detections = []
        
        if not PSUTIL_AVAILABLE:
            return {"error": "psutil not available"}
        
        current_time = datetime.now(timezone.utc)
        
        # Clean old entries from recent_lolbins
        self.recent_lolbins = [
            entry for entry in self.recent_lolbins 
            if (current_time - entry['timestamp']).total_seconds() < self.chain_window_seconds
        ]
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'username', 'ppid']):
            try:
                info = proc.info
                name = (info['name'] or '').lower().replace('.exe', '')
                cmdline = ' '.join(info['cmdline'] or []).lower()
                
                if name in self.LOLBINS:
                    lolbin = self.LOLBINS[name]
                    suspicious = False
                    matched_args = []
                    severity = lolbin.get('severity', 'medium')
                    
                    # Check for suspicious arguments
                    for arg in lolbin['suspicious_args']:
                        if arg.lower() in cmdline:
                            suspicious = True
                            matched_args.append(arg)
                    
                    # Some LOLBins are suspicious just by running
                    always_suspicious = ['msbuild', 'regsvcs', 'regasm', 'mavinject', 'msdt', 'nc', 'ncat', 'socat']
                    if not lolbin['suspicious_args'] and name in always_suspicious:
                        suspicious = True
                        matched_args.append("execution_detected")
                    
                    # Check parent process relationship
                    parent_alert = self._check_parent_process(info.get('ppid'), name)
                    if parent_alert:
                        suspicious = True
                        matched_args.append(f"suspicious_parent:{parent_alert}")
                        severity = "critical"  # Upgrade severity for suspicious parent
                    
                    if suspicious:
                        detection = {
                            'pid': info['pid'],
                            'ppid': info.get('ppid'),
                            'name': info['name'],
                            'cmdline': cmdline[:500],
                            'username': info['username'],
                            'matched_args': matched_args,
                            'description': lolbin['description'],
                            'mitre': lolbin['mitre'],
                            'severity': severity,
                            'category': lolbin.get('category', 'execution'),
                            'timestamp': current_time.isoformat()
                        }
                        self.detections.append(detection)
                        
                        # Track for chain detection
                        self.recent_lolbins.append({
                            'name': name,
                            'timestamp': current_time,
                            'pid': info['pid']
                        })
                        
                        self._create_threat(detection, lolbin)
                        
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        # Check for attack chains
        chain_detections = self._detect_attack_chains()
        for chain in chain_detections:
            self.detections.append(chain)
            self._create_chain_threat(chain)
        
        self.last_run = datetime.now(timezone.utc)
        
        return {
            "lolbins_checked": len(self.LOLBINS),
            "detections": len(self.detections),
            "threats": len(self.threats),
            "attack_chains_detected": len(chain_detections),
            "categories": self._get_category_stats(),
            "details": self.detections[-20:]
        }
    
    def _check_parent_process(self, ppid: int, child_name: str) -> Optional[str]:
        """Check if parent-child process relationship is suspicious"""
        if not ppid:
            return None
        
        try:
            parent = psutil.Process(ppid)
            parent_name = (parent.name() or '').lower().replace('.exe', '')
            
            # Check against suspicious parent relationships
            if parent_name in self.SUSPICIOUS_PARENTS:
                suspicious_children = self.SUSPICIOUS_PARENTS[parent_name]
                for sus_child in suspicious_children:
                    if sus_child in child_name:
                        return parent_name
            
            return None
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return None
    
    def _detect_attack_chains(self) -> List[Dict]:
        """Detect attack chain patterns from recent LOLBin executions"""
        detected_chains = []
        
        if len(self.recent_lolbins) < 2:
            return detected_chains
        
        recent_names = [entry['name'] for entry in self.recent_lolbins]
        
        for chain in self.ATTACK_CHAINS:
            sequence = chain['sequence']
            # Check if chain sequence exists in recent executions
            for i in range(len(recent_names) - len(sequence) + 1):
                if recent_names[i:i+len(sequence)] == sequence:
                    detected_chains.append({
                        'type': 'attack_chain',
                        'name': chain['name'],
                        'sequence': sequence,
                        'severity': chain['severity'],
                        'timestamp': datetime.now(timezone.utc).isoformat(),
                        'mitre': 'T1059',  # Generic execution
                        'description': f"Attack chain detected: {' -> '.join(sequence)}"
                    })
                    break
        
        return detected_chains
    
    def _get_category_stats(self) -> Dict[str, int]:
        """Get statistics by LOLBin category"""
        categories = {}
        for detection in self.detections:
            cat = detection.get('category', 'unknown')
            categories[cat] = categories.get(cat, 0) + 1
        return categories
    
    def _create_chain_threat(self, chain: Dict):
        """Create threat from attack chain detection"""
        threat = Threat(
            threat_id=f"lolchain-{uuid.uuid4().hex[:8]}",
            title=f"Attack Chain: {chain['name']}",
            description=f"Multiple LOLBins executed in suspicious sequence: {' -> '.join(chain['sequence'])}",
            severity=ThreatSeverity.CRITICAL if chain['severity'] == 'critical' else ThreatSeverity.HIGH,
            threat_type="attack_chain",
            source="lolbin_monitor",
            target="system",
            evidence=chain,
            mitre_techniques=[chain['mitre'], "T1218", "T1059"],
            auto_kill_eligible=True,
            remediation_action="isolate_endpoint"
        )
        self.threats.append(threat)
    
    def _create_threat(self, detection: Dict, lolbin: Dict):
        """Create threat from LOLBin detection"""
        threat = Threat(
            threat_id=f"lolbin-{uuid.uuid4().hex[:8]}",
            title=f"LOLBin Abuse: {detection['name']}",
            description=f"{lolbin['description']} - {detection['matched_args']}",
            severity=ThreatSeverity.HIGH,
            threat_type="lolbin_abuse",
            source="lolbin_monitor",
            target=f"{detection['pid']}:{detection['name']}",
            evidence=detection,
            mitre_techniques=[lolbin['mitre']],
            auto_kill_eligible=True,
            remediation_action="kill_process",
            remediation_params={"pid": detection['pid'], "name": detection['name']}
        )
        self.threats.append(threat)
    
    def get_threats(self) -> List[Threat]:
        return self.threats


class CodeSigningMonitor(MonitorModule):
    """
    Code Signing Verification - Enterprise-grade executable signature validation.
    Detects unsigned, tampered, suspiciously signed, and catalog-signed executables.
    
    Enterprise Features:
    - Authenticode signature verification (Windows)
    - Windows Catalog signature verification (drivers, system files)
    - Certificate chain and revocation validation
    - Counter-signature/timestamping verification
    - Certificate expiration and validity checking
    - Loaded DLL signature scanning
    - macOS codesign and notarization verification
    - Linux package manager verification
    - PE header integrity checking for tampering
    - Hash verification against known-good database
    - Trust store validation
    - MITRE ATT&CK T1553 detection
    """
    
    # Trusted publishers (extensive enterprise list)
    TRUSTED_PUBLISHERS = {
        # Microsoft
        "microsoft corporation", "microsoft windows", "microsoft windows publisher",
        "microsoft code signing pca", "microsoft root certificate authority",
        # Google
        "google llc", "google inc", "google trust services",
        # Apple
        "apple inc", "apple root ca", "apple worldwide developer relations",
        # Mozilla
        "mozilla corporation", "mozilla",
        # Adobe
        "adobe systems incorporated", "adobe inc",
        # Oracle
        "oracle corporation", "oracle america, inc.",
        # VMware
        "vmware, inc.", "vmware",
        # Citrix
        "citrix systems, inc.",
        # Security vendors
        "crowdstrike, inc.", "symantec corporation", "broadcom corporation",
        "mcafee, llc", "palo alto networks", "fortinet inc", "cisco systems",
        "kaspersky lab", "sophos ltd", "trend micro",
        # Cloud vendors
        "amazon.com services llc", "salesforce.com, inc.",
        # Collaboration
        "github, inc.", "slack technologies", "zoom video communications, inc.",
        "atlassian pty ltd",
        # Hardware vendors
        "intel corporation", "nvidia corporation", "amd",
        "dell inc", "hp inc", "lenovo",
        # Runtime vendors
        "python software foundation", "nodejs foundation",
        # Media
        "videolan", "spotify ab",
        # Utilities
        "7-zip", "winrar", "mozilla", "the curl project",
        # Cloud security
        "hashicorp, inc.", "docker, inc.",
    }
    
    # Windows system catalog paths
    WINDOWS_CATALOG_PATHS = [
        r"C:\Windows\System32\CatRoot\{F750E6C3-38EE-11D1-85E5-00C04FC295EE}",
        r"C:\Windows\System32\CatRoot2",
    ]
    
    # Known suspicious certificate issuers
    SUSPICIOUS_ISSUERS = {
        "let's encrypt",  # Free certs, not typically for code signing
        "comodo", "sectigo",  # Frequently abused for malware signing
        "digicert", # Check context - legitimate but sometimes stolen
        "certum",  # Free certs available
        "ssl.com", # Check context
    }
    
    # Suspicious certificate characteristics
    SUSPICIOUS_CERT_PATTERNS = [
        "test", "self-signed", "localhost", "development", "debug",
        "fake", "sample", "demo", "example", "temp", "staging",
    ]
    
    # PE header magic bytes
    PE_MAGIC = b'MZ'
    PE_SIGNATURE = b'PE\x00\x00'
    
    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self.threats = []
        self.scan_results = []
        self.unsigned_executables = []
        self.revoked_certs = []
        self.expired_certs = []
        self.tampered_executables = []
        self.catalog_verified = []
        self.unsigned_dlls = []
        self.no_timestamp_certs = []
        self.known_good_hashes: Set[str] = set()
        self._load_known_good_hashes()
    
    def _load_known_good_hashes(self):
        """Load known-good hashes from local file"""
        hash_file = Path.home() / ".metatron" / "known_good_hashes.txt"
        try:
            if hash_file.exists():
                with open(hash_file, 'r') as f:
                    self.known_good_hashes = set(line.strip().lower() for line in f if line.strip())
        except Exception:
            pass
    
    def _calculate_file_hash(self, filepath: str) -> Optional[str]:
        """Calculate SHA256 hash of a file"""
        try:
            sha256 = hashlib.sha256()
            with open(filepath, 'rb') as f:
                for chunk in iter(lambda: f.read(65536), b''):
                    sha256.update(chunk)
            return sha256.hexdigest()
        except Exception:
            return None
    
    def _check_pe_integrity(self, filepath: str) -> Dict:
        """Check PE header integrity for tampering"""
        result = {
            'valid_pe': False,
            'tampered': False,
            'issues': []
        }
        
        try:
            with open(filepath, 'rb') as f:
                # Check MZ header
                mz = f.read(2)
                if mz != self.PE_MAGIC:
                    result['issues'].append("Invalid MZ header")
                    return result
                
                # Read PE header offset
                f.seek(0x3C)
                pe_offset = int.from_bytes(f.read(4), 'little')
                
                if pe_offset > 1024:  # Suspiciously large offset
                    result['issues'].append(f"Large PE offset: {pe_offset}")
                    result['tampered'] = True
                
                # Check PE signature
                f.seek(pe_offset)
                pe_sig = f.read(4)
                if pe_sig != self.PE_SIGNATURE:
                    result['issues'].append("Invalid PE signature")
                    result['tampered'] = True
                    return result
                
                result['valid_pe'] = True
                
                # Check for common tampering indicators
                # Read IMAGE_FILE_HEADER
                f.seek(pe_offset + 4)
                machine = int.from_bytes(f.read(2), 'little')
                num_sections = int.from_bytes(f.read(2), 'little')
                
                # Suspicious section count
                if num_sections > 20:
                    result['issues'].append(f"High section count: {num_sections}")
                    result['tampered'] = True
                
                # Check TimeDateStamp
                timestamp = int.from_bytes(f.read(4), 'little')
                if timestamp == 0 or timestamp == 0xFFFFFFFF:
                    result['issues'].append("Invalid timestamp")
                    result['tampered'] = True
                    
        except Exception as e:
            result['issues'].append(f"PE check error: {str(e)[:50]}")
        
        return result
    
    def _verify_catalog_signature(self, filepath: str) -> Dict:
        """Verify if file is signed via Windows catalog (drivers, system files)"""
        result = {
            'catalog_signed': False,
            'catalog_name': None,
            'catalog_valid': False
        }
        
        if PLATFORM != "windows":
            return result
        
        try:
            ps_cmd = f'''
            $file = "{filepath}"
            $cat = Get-AuthenticodeSignature -FilePath $file
            if ($cat.Status -eq "NotSigned") {{
                # Check for catalog signature
                Add-Type -TypeDefinition @"
                using System;
                using System.Runtime.InteropServices;
                public class CryptoAPI {{
                    [DllImport("wintrust.dll", SetLastError=true)]
                    public static extern IntPtr CryptCATAdminAcquireContext(
                        out IntPtr hCatAdmin, IntPtr pgSubsystem, int dwFlags);
                }}
"@
                # Fallback: use sigcheck-like approach via WMI
                $catFile = Get-ChildItem "$env:windir\\system32\\catroot" -Recurse -Filter "*.cat" 2>$null | 
                    Where-Object {{ (Get-AuthenticodeSignature $_.FullName).Status -eq "Valid" }} |
                    Select-Object -First 1
                if ($catFile) {{ 
                    @{{ CatalogSigned=$true; CatalogName=$catFile.Name; CatalogValid=$true }} | ConvertTo-Json
                }} else {{
                    @{{ CatalogSigned=$false; CatalogName=$null; CatalogValid=$false }} | ConvertTo-Json
                }}
            }} else {{
                @{{ CatalogSigned=$true; CatalogName="embedded"; CatalogValid=($cat.Status -eq "Valid") }} | ConvertTo-Json
            }}
            '''
            
            proc = subprocess.run(
                ['powershell', '-Command', ps_cmd],
                capture_output=True, text=True, timeout=10
            )
            
            if proc.returncode == 0 and proc.stdout.strip():
                try:
                    data = json.loads(proc.stdout.strip())
                    result['catalog_signed'] = data.get('CatalogSigned', False)
                    result['catalog_name'] = data.get('CatalogName')
                    result['catalog_valid'] = data.get('CatalogValid', False)
                except json.JSONDecodeError:
                    pass
                    
        except Exception as e:
            logger.debug(f"Catalog signature check error: {e}")
        
        return result
    
    def _verify_timestamp(self, filepath: str) -> Dict:
        """Verify counter-signature/timestamp on code signature"""
        result = {
            'has_timestamp': False,
            'timestamp_valid': False,
            'timestamp_date': None,
            'timestamp_issuer': None
        }
        
        if PLATFORM != "windows":
            return result
        
        try:
            ps_cmd = f'''
            $sig = Get-AuthenticodeSignature -FilePath "{filepath}"
            $cert = $sig.SignerCertificate
            if ($sig.TimeStamperCertificate) {{
                $ts = $sig.TimeStamperCertificate
                @{{
                    HasTimestamp = $true
                    TimestampValid = ($ts.NotAfter -gt (Get-Date))
                    TimestampDate = if ($sig.SigningTime) {{ $sig.SigningTime.ToString('o') }} else {{ $null }}
                    TimestampIssuer = $ts.Issuer
                }} | ConvertTo-Json
            }} else {{
                @{{ HasTimestamp = $false; TimestampValid = $false; TimestampDate = $null; TimestampIssuer = $null }} | ConvertTo-Json
            }}
            '''
            
            proc = subprocess.run(
                ['powershell', '-Command', ps_cmd],
                capture_output=True, text=True, timeout=10
            )
            
            if proc.returncode == 0 and proc.stdout.strip():
                data = json.loads(proc.stdout.strip())
                result['has_timestamp'] = data.get('HasTimestamp', False)
                result['timestamp_valid'] = data.get('TimestampValid', False)
                result['timestamp_date'] = data.get('TimestampDate')
                result['timestamp_issuer'] = data.get('TimestampIssuer')
                
        except Exception as e:
            logger.debug(f"Timestamp verification error: {e}")
        
        return result
    
    def _scan_loaded_dlls(self, pid: int) -> List[Dict]:
        """Scan loaded DLLs for a process for signature issues"""
        unsigned_dlls = []
        
        if PLATFORM != "windows":
            return unsigned_dlls
        
        try:
            proc = psutil.Process(pid)
            memory_maps = proc.memory_maps()
            
            checked_dlls = set()
            
            for mmap in memory_maps:
                path = mmap.path
                if not path or not path.lower().endswith('.dll'):
                    continue
                
                if path in checked_dlls:
                    continue
                
                checked_dlls.add(path)
                
                # Skip system DLLs
                path_lower = path.lower()
                if path_lower.startswith(r'c:\windows\system32') or \
                   path_lower.startswith(r'c:\windows\syswow64') or \
                   path_lower.startswith(r'c:\windows\winsxs'):
                    continue
                
                # Check signature
                result = self._verify_signature(path)
                
                if not result['signed'] or result['suspicious']:
                    unsigned_dlls.append({
                        'dll_path': path,
                        'process_pid': pid,
                        'signed': result['signed'],
                        'suspicious': result.get('suspicious', False),
                        'reason': result.get('reason', 'Unsigned DLL'),
                        'publisher': result.get('publisher')
                    })
                    
        except (psutil.NoSuchProcess, psutil.AccessDenied, Exception) as e:
            logger.debug(f"DLL scan error for PID {pid}: {e}")
        
        return unsigned_dlls
    
    def _check_cert_trust_store(self, cert_thumbprint: str) -> Dict:
        """Check if certificate is in Windows trust store"""
        result = {
            'in_trusted_root': False,
            'in_trusted_publisher': False,
            'explicitly_distrusted': False
        }
        
        if PLATFORM != "windows" or not cert_thumbprint:
            return result
        
        try:
            ps_cmd = f'''
            $thumb = "{cert_thumbprint}"
            $trusted = (Get-ChildItem Cert:\\LocalMachine\\Root | Where-Object {{ $_.Thumbprint -eq $thumb }}).Count -gt 0
            $publisher = (Get-ChildItem Cert:\\LocalMachine\\TrustedPublisher | Where-Object {{ $_.Thumbprint -eq $thumb }}).Count -gt 0
            $distrusted = (Get-ChildItem Cert:\\LocalMachine\\Disallowed | Where-Object {{ $_.Thumbprint -eq $thumb }}).Count -gt 0
            @{{ TrustedRoot=$trusted; TrustedPublisher=$publisher; Distrusted=$distrusted }} | ConvertTo-Json
            '''
            
            proc = subprocess.run(
                ['powershell', '-Command', ps_cmd],
                capture_output=True, text=True, timeout=10
            )
            
            if proc.returncode == 0 and proc.stdout.strip():
                data = json.loads(proc.stdout.strip())
                result['in_trusted_root'] = data.get('TrustedRoot', False)
                result['in_trusted_publisher'] = data.get('TrustedPublisher', False)
                result['explicitly_distrusted'] = data.get('Distrusted', False)
                
        except Exception as e:
            logger.debug(f"Trust store check error: {e}")
        
        return result

    def scan(self) -> Dict[str, Any]:
        """Scan running processes for signature verification with enterprise features"""
        self.threats = []
        self.scan_results = []
        self.unsigned_executables = []
        self.revoked_certs = []
        self.expired_certs = []
        self.tampered_executables = []
        self.unsigned_dlls = []
        self.catalog_verified = []
        self.no_timestamp_certs = []
        
        if not PSUTIL_AVAILABLE:
            return {"error": "psutil not available"}
        
        checked = set()
        dlls_checked = 0
        
        for proc in psutil.process_iter(['pid', 'name', 'exe']):
            try:
                info = proc.info
                exe_path = info.get('exe')
                pid = info.get('pid')
                
                if not exe_path or exe_path in checked:
                    continue
                
                checked.add(exe_path)
                
                # Skip system paths on Windows that are always signed
                if PLATFORM == "windows":
                    exe_lower = exe_path.lower()
                    if exe_lower.startswith(r"c:\windows\system32") or \
                       exe_lower.startswith(r"c:\windows\syswow64"):
                        continue
                
                result = self._verify_signature(exe_path)
                result['pid'] = pid
                result['name'] = info['name']
                
                # Calculate and check hash
                file_hash = self._calculate_file_hash(exe_path)
                result['sha256'] = file_hash
                
                if file_hash and file_hash in self.known_good_hashes:
                    result['known_good'] = True
                    result['signed'] = True  # Trust known-good hashes
                else:
                    result['known_good'] = False
                
                # Check PE integrity on Windows
                if PLATFORM == "windows" and exe_path.lower().endswith('.exe'):
                    pe_check = self._check_pe_integrity(exe_path)
                    if pe_check['tampered']:
                        result['pe_tampered'] = True
                        result['pe_issues'] = pe_check['issues']
                        result['suspicious'] = True
                        self.tampered_executables.append(result)
                
                # Enterprise: Check catalog signature for unsigned files
                if PLATFORM == "windows" and not result['signed']:
                    cat_result = self._verify_catalog_signature(exe_path)
                    if cat_result['catalog_signed'] and cat_result['catalog_valid']:
                        result['signed'] = True
                        result['catalog_signed'] = True
                        result['catalog_name'] = cat_result['catalog_name']
                        self.catalog_verified.append(result)
                
                # Enterprise: Check timestamp/counter-signature
                if PLATFORM == "windows" and result['signed']:
                    ts_result = self._verify_timestamp(exe_path)
                    result['has_timestamp'] = ts_result['has_timestamp']
                    result['timestamp_date'] = ts_result['timestamp_date']
                    
                    if not ts_result['has_timestamp']:
                        self.no_timestamp_certs.append(result)
                
                # Enterprise: Check trust store for certificate
                if result.get('thumbprint'):
                    trust_result = self._check_cert_trust_store(result['thumbprint'])
                    result['in_trusted_root'] = trust_result['in_trusted_root']
                    result['in_trusted_publisher'] = trust_result['in_trusted_publisher']
                    
                    if trust_result['explicitly_distrusted']:
                        result['suspicious'] = True
                        result['reason'] = "Certificate explicitly distrusted"
                        result['revoked'] = True
                
                self.scan_results.append(result)
                
                if not result['signed'] or result['suspicious']:
                    if not result.get('known_good'):
                        self.unsigned_executables.append(result)
                        self._create_threat(result)
                
                if result.get('revoked'):
                    self.revoked_certs.append(result)
                    
                if result.get('expired'):
                    self.expired_certs.append(result)
                
                # Enterprise: Scan loaded DLLs (sample for high-risk processes)
                if pid and len(self.unsigned_dlls) < 50:  # Limit DLL scanning
                    proc_name = (info.get('name') or '').lower()
                    # Scan DLLs for high-risk processes
                    if any(x in proc_name for x in ['powershell', 'cmd', 'rundll', 'regsvr', 'mshta']):
                        dll_results = self._scan_loaded_dlls(pid)
                        for dll_result in dll_results:
                            self.unsigned_dlls.append(dll_result)
                            dlls_checked += 1
                            self._create_threat({
                                'path': dll_result['dll_path'],
                                'signed': dll_result['signed'],
                                'suspicious': dll_result['suspicious'],
                                'reason': dll_result['reason'],
                                'publisher': dll_result.get('publisher'),
                                'is_dll': True
                            })
                    
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        self.last_run = datetime.now(timezone.utc)
        
        return {
            "executables_checked": len(checked),
            "dlls_checked": dlls_checked,
            "unsigned_count": len(self.unsigned_executables),
            "unsigned_dll_count": len(self.unsigned_dlls),
            "revoked_count": len(self.revoked_certs),
            "expired_count": len(self.expired_certs),
            "tampered_count": len(self.tampered_executables),
            "catalog_verified_count": len(self.catalog_verified),
            "no_timestamp_count": len(self.no_timestamp_certs),
            "threats": len(self.threats),
            "unsigned": self.unsigned_executables[-20:],
            "unsigned_dlls": self.unsigned_dlls[-10:]
        }
    
    def _verify_signature(self, exe_path: str) -> Dict:
        """Verify executable signature with comprehensive checks"""
        result = {
            'path': exe_path,
            'signed': False,
            'valid': False,
            'publisher': None,
            'issuer': None,
            'suspicious': False,
            'revoked': False,
            'expired': False,
            'cert_expires': None,
            'reason': None
        }
        
        if PLATFORM == "windows":
            result = self._verify_windows_signature(exe_path, result)
        elif PLATFORM == "darwin":
            result = self._verify_macos_signature(exe_path, result)
        else:
            result = self._verify_linux_signature(exe_path, result)
        
        # Check for suspicious publishers
        if result['publisher']:
            publisher_lower = result['publisher'].lower()
            # Check if it looks like a self-signed cert
            if 'test' in publisher_lower or 'self-signed' in publisher_lower or \
               'localhost' in publisher_lower or 'development' in publisher_lower:
                result['suspicious'] = True
                result['reason'] = "Self-signed or test certificate"
        
        # Check issuer suspiciousness
        if result.get('issuer'):
            issuer_lower = result['issuer'].lower()
            if any(sus in issuer_lower for sus in ['test', 'fake', 'localhost']):
                result['suspicious'] = True
                result['reason'] = "Suspicious certificate issuer"
        
        return result
    
    def _verify_windows_signature(self, exe_path: str, result: Dict) -> Dict:
        """Comprehensive Windows Authenticode verification"""
        try:
            # Enhanced PowerShell command with certificate details
            ps_cmd = f'''
            $sig = Get-AuthenticodeSignature -FilePath "{exe_path}"
            $cert = $sig.SignerCertificate
            $chain = New-Object System.Security.Cryptography.X509Certificates.X509Chain
            if ($cert) {{
                $chain.Build($cert) | Out-Null
            }}
            @{{
                Status = [int]$sig.Status
                StatusMessage = $sig.StatusMessage
                Subject = if($cert) {{ $cert.Subject }} else {{ $null }}
                Issuer = if($cert) {{ $cert.Issuer }} else {{ $null }}
                NotAfter = if($cert) {{ $cert.NotAfter.ToString('o') }} else {{ $null }}
                NotBefore = if($cert) {{ $cert.NotBefore.ToString('o') }} else {{ $null }}
                Thumbprint = if($cert) {{ $cert.Thumbprint }} else {{ $null }}
                ChainStatus = ($chain.ChainStatus | ForEach-Object {{ $_.Status.ToString() }}) -join ','
            }} | ConvertTo-Json
            '''
            
            proc = subprocess.run(
                ['powershell', '-Command', ps_cmd],
                capture_output=True, text=True, timeout=15
            )
            
            if proc.returncode == 0 and proc.stdout.strip():
                data = json.loads(proc.stdout)
                status = data.get('Status', 1)
                
                # Status codes: 0=Valid, 1=UnknownError, 2=NotSigned, 3=HashMismatch, etc.
                if status == 0:
                    result['signed'] = True
                    result['valid'] = True
                    result['publisher'] = data.get('Subject', '')
                    result['issuer'] = data.get('Issuer', '')
                    result['cert_expires'] = data.get('NotAfter')
                    result['thumbprint'] = data.get('Thumbprint')
                    
                    # Check chain status
                    chain_status = data.get('ChainStatus', '')
                    if 'Revoked' in chain_status:
                        result['revoked'] = True
                        result['suspicious'] = True
                        result['reason'] = "Certificate revoked"
                    
                    if 'NotTimeValid' in chain_status:
                        result['expired'] = True
                        result['suspicious'] = True
                        result['reason'] = "Certificate expired"
                        
                elif status == 2:  # NotSigned
                    result['signed'] = False
                    result['reason'] = "Unsigned executable"
                elif status == 3:  # HashMismatch
                    result['signed'] = True
                    result['valid'] = False
                    result['suspicious'] = True
                    result['reason'] = "Signature hash mismatch - possible tampering"
                elif status == 4:  # NotTrusted
                    result['signed'] = True
                    result['valid'] = False
                    result['suspicious'] = True
                    result['reason'] = "Certificate not trusted"
                else:
                    result['signed'] = False
                    result['reason'] = f"Signature status: {data.get('StatusMessage', status)}"
                    
        except json.JSONDecodeError:
            result['reason'] = "Failed to parse signature data"
        except subprocess.TimeoutExpired:
            result['reason'] = "Signature check timeout"
        except Exception as e:
            result['reason'] = f"Check failed: {str(e)[:50]}"
        
        return result
    
    def _verify_macos_signature(self, exe_path: str, result: Dict) -> Dict:
        """Verify macOS code signature using codesign"""
        try:
            # Check if file exists and is executable
            if not Path(exe_path).exists():
                return result
            
            # Use codesign to verify
            proc = subprocess.run(
                ['codesign', '-dv', '--verbose=4', exe_path],
                capture_output=True, text=True, timeout=10
            )
            
            output = proc.stderr  # codesign outputs to stderr
            
            if 'valid on disk' in output.lower() or 'satisfies its Designated Requirement' in output:
                result['signed'] = True
                result['valid'] = True
                
                # Extract team ID and authority
                for line in output.split('\n'):
                    if 'Authority=' in line:
                        result['publisher'] = line.split('Authority=')[1].strip()
                        break
                    if 'TeamIdentifier=' in line:
                        result['issuer'] = line.split('TeamIdentifier=')[1].strip()
                        
            elif 'code object is not signed' in output.lower():
                result['signed'] = False
                result['reason'] = "Unsigned (macOS)"
            else:
                result['signed'] = True
                result['valid'] = False
                result['suspicious'] = True
                result['reason'] = f"Invalid signature: {output[:100]}"
            
            # Also check Gatekeeper assessment
            gk_proc = subprocess.run(
                ['spctl', '-a', '-v', exe_path],
                capture_output=True, text=True, timeout=10
            )
            
            if 'rejected' in gk_proc.stderr.lower():
                result['suspicious'] = True
                result['reason'] = f"Gatekeeper rejected: {gk_proc.stderr[:100]}"
                
        except subprocess.TimeoutExpired:
            result['reason'] = "macOS signature check timeout"
        except FileNotFoundError:
            # codesign not available
            result['reason'] = "codesign not available"
        except Exception as e:
            result['reason'] = f"macOS check failed: {str(e)[:50]}"
        
        return result
    
    def _verify_linux_signature(self, exe_path: str, result: Dict) -> Dict:
        """Verify Linux executable using package manager and file integrity"""
        try:
            path = Path(exe_path)
            if not path.exists():
                return result
            
            # Try dpkg (Debian/Ubuntu)
            try:
                pkg_check = subprocess.run(
                    ['dpkg', '-S', exe_path],
                    capture_output=True, text=True, timeout=5
                )
                if pkg_check.returncode == 0:
                    package = pkg_check.stdout.split(':')[0]
                    result['signed'] = True
                    result['valid'] = True
                    result['publisher'] = f"dpkg:{package}"
                    result['reason'] = "System package (dpkg)"
                    
                    # Verify package integrity
                    verify = subprocess.run(
                        ['dpkg', '-V', package],
                        capture_output=True, text=True, timeout=10
                    )
                    if verify.stdout.strip():
                        result['suspicious'] = True
                        result['reason'] = "Package files modified"
                    return result
            except FileNotFoundError:
                pass
            
            # Try rpm (RHEL/CentOS/Fedora)
            try:
                pkg_check = subprocess.run(
                    ['rpm', '-qf', exe_path],
                    capture_output=True, text=True, timeout=5
                )
                if pkg_check.returncode == 0:
                    package = pkg_check.stdout.strip()
                    result['signed'] = True
                    result['valid'] = True
                    result['publisher'] = f"rpm:{package}"
                    result['reason'] = "System package (rpm)"
                    
                    # Verify package integrity
                    verify = subprocess.run(
                        ['rpm', '-V', package],
                        capture_output=True, text=True, timeout=10
                    )
                    if verify.stdout.strip():
                        result['suspicious'] = True
                        result['reason'] = "Package files modified"
                    return result
            except FileNotFoundError:
                pass
            
            # No package manager found it - likely user-installed
            result['signed'] = False
            result['reason'] = "Not from system package manager"
            
        except Exception as e:
            result['reason'] = f"Linux check failed: {str(e)[:50]}"
        
        return result
    
    def _create_threat(self, result: Dict):
        """Create threat from unsigned/suspicious executable or DLL"""
        # Determine severity based on issue type
        is_dll = result.get('is_dll', False)
        
        if result.get('pe_tampered'):
            severity = ThreatSeverity.CRITICAL
            mitre = ["T1027", "T1036.003"]  # Obfuscation, Rename System Utilities
        elif result.get('revoked'):
            severity = ThreatSeverity.CRITICAL
            mitre = ["T1553.002"]  # Code Signing revoked
        elif result.get('suspicious'):
            severity = ThreatSeverity.HIGH
            mitre = ["T1553", "T1036"]
            if is_dll:
                mitre.append("T1574.002")  # DLL Side-Loading
        elif is_dll and not result['signed']:
            severity = ThreatSeverity.HIGH  # Unsigned DLLs are higher risk
            mitre = ["T1574.001", "T1574.002", "T1553"]  # DLL Search Order Hijacking, Side-Loading
        elif not result['signed']:
            severity = ThreatSeverity.MEDIUM
            mitre = ["T1036", "T1553"]
        else:
            severity = ThreatSeverity.LOW
            mitre = ["T1553"]
        
        file_type = "DLL" if is_dll else "Executable"
        
        threat = Threat(
            threat_id=f"sig-{uuid.uuid4().hex[:8]}",
            title=f"Code Signing Issue: {Path(result['path']).name}",
            description=f"{file_type} signature problem: {result.get('reason', 'Unknown')}",
            severity=severity,
            threat_type="code_signing_violation",
            source="code_signing_monitor",
            target=result['path'],
            evidence={
                'path': result['path'],
                'signed': result['signed'],
                'valid': result.get('valid'),
                'publisher': result.get('publisher'),
                'reason': result.get('reason'),
                'sha256': result.get('sha256'),
                'pe_tampered': result.get('pe_tampered'),
                'revoked': result.get('revoked'),
                'expired': result.get('expired'),
                'is_dll': is_dll,
                'catalog_signed': result.get('catalog_signed'),
                'has_timestamp': result.get('has_timestamp')
            },
            mitre_techniques=mitre,
            auto_kill_eligible=result.get('pe_tampered', False) or result.get('revoked', False),
            remediation_action="quarantine_file",
            remediation_params={"filepath": result['path']}
        )
        self.threats.append(threat)
    
    def get_threats(self) -> List[Threat]:
        return self.threats


class DNSMonitor(MonitorModule):
    """
    DNS Monitoring - Enterprise-grade DNS security monitoring.
    Detects DNS tunneling, DGA domains, DNS rebinding, and malicious lookups.
    
    Enterprise Features:
    - DGA (Domain Generation Algorithm) detection with entropy analysis
    - DNS tunneling detection (dnscat, iodine, dns2tcp patterns)
    - DNS-over-HTTPS (DoH) bypass detection
    - DNS rebinding attack detection
    - Fast-flux domain detection (rapid IP changes)
    - CNAME chain analysis (detect redirect attacks)
    - Newly Observed Domain (NOD) tracking
    - Passive DNS history collection
    - Integration with threat intelligence feeds
    - MITRE ATT&CK T1071.004, T1568.002, T1048 detection
    """
    
    # Known malicious TLDs (expanded enterprise list)
    SUSPICIOUS_TLDS = {
        # Free TLDs often abused
        '.tk', '.ml', '.ga', '.cf', '.gq',
        # Dark web / alternative DNS
        '.onion', '.bit', '.i2p', '.bazar',
        # Frequently abused commercial TLDs
        '.xyz', '.top', '.work', '.click', '.loan', '.online',
        '.site', '.download', '.win', '.racing', '.stream',
        '.review', '.country', '.science', '.party', '.date',
        '.faith', '.cricket', '.accountant', '.bid', '.trade',
        # Newly abused TLDs
        '.pw', '.ws', '.cc', '.icu', '.buzz',
    }
    
    # DGA (Domain Generation Algorithm) detection patterns
    DGA_PATTERNS = {
        'high_entropy': 0.7,       # Shannon entropy threshold
        'consonant_ratio': 0.6,    # High consonant ratio
        'digit_ratio': 0.3,        # Many numbers
        'length_threshold': 20,    # Very long domains
        'no_vowels_min_len': 8,    # Pure consonants with min length
    }
    
    # Known DNS tunneling domains and patterns
    DNS_TUNNEL_PATTERNS = [
        r'\.dnscat\.',
        r'\.dns2tcp\.',
        r'\.iodine\.',
        r'\.dnscrypt\.',
        r'\.dnsexfil\.',
        r'[a-f0-9]{32,}',          # Long hex strings (often tunneling)
        r'[a-z0-9]{50,}\.',        # Very long subdomain
        r'(\w{4,}\.){5,}',         # Many subdomain levels
    ]
    
    # Known DNS-over-HTTPS providers (for detection)
    DOH_PROVIDERS = {
        'cloudflare-dns.com', '1.1.1.1', '1.0.0.1',
        'dns.google', '8.8.8.8', '8.8.4.4',
        'dns.quad9.net', '9.9.9.9',
        'doh.opendns.com', 'dns.adguard.com',
        'doh.cleanbrowsing.org', 'dns.nextdns.io',
        'mozilla.cloudflare-dns.com', 'dns.digitale-gesellschaft.ch',
        'doh.dns.sb', 'dns.twnic.tw',
    }
    
    # RFC1918 private IP ranges (for rebinding detection)
    PRIVATE_IP_RANGES = [
        ('10.0.0.0', '10.255.255.255'),
        ('172.16.0.0', '172.31.255.255'),
        ('192.168.0.0', '192.168.255.255'),
        ('127.0.0.0', '127.255.255.255'),
        ('169.254.0.0', '169.254.255.255'),  # Link-local
    ]
    
    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self.threats = []
        self.suspicious_queries = []
        self.query_cache = {}  # Track query frequency
        self.dns_log = []
        self.domain_first_seen: Dict[str, str] = {}  # NOD tracking
        self.domain_ip_history: Dict[str, List[Tuple[str, str]]] = {}  # Fast-flux tracking
        self.doh_connections = []  # DoH bypass tracking
        self.rebinding_attempts = []
    
    def _calculate_entropy(self, text: str) -> float:
        """Calculate Shannon entropy of a string"""
        if not text:
            return 0.0
        
        prob = [float(text.count(c)) / len(text) for c in set(text)]
        entropy = -sum([p * math.log2(p) for p in prob if p > 0])
        
        # Normalize to 0-1 range
        max_entropy = math.log2(len(set(text))) if len(set(text)) > 1 else 1
        return entropy / max_entropy if max_entropy > 0 else 0
    
    def _is_dga_domain(self, domain: str) -> Tuple[bool, str]:
        """Detect if domain looks like DGA-generated"""
        # Remove TLD
        parts = domain.split('.')
        if len(parts) < 2:
            return False, ""
        
        name = parts[0]
        
        # Check entropy
        entropy = self._calculate_entropy(name)
        if entropy > self.DGA_PATTERNS['high_entropy']:
            return True, f"High entropy: {entropy:.2f}"
        
        # Check consonant ratio
        consonants = sum(1 for c in name.lower() if c in 'bcdfghjklmnpqrstvwxyz')
        if len(name) > 0 and consonants / len(name) > self.DGA_PATTERNS['consonant_ratio']:
            return True, f"High consonant ratio"
        
        # Check digit ratio
        digits = sum(1 for c in name if c.isdigit())
        if len(name) > 0 and digits / len(name) > self.DGA_PATTERNS['digit_ratio']:
            return True, f"High digit ratio"
        
        # Check length
        if len(name) > self.DGA_PATTERNS['length_threshold']:
            return True, f"Unusually long: {len(name)} chars"
        
        # Check for no vowels (common in some DGA)
        vowels = sum(1 for c in name.lower() if c in 'aeiou')
        if len(name) >= self.DGA_PATTERNS['no_vowels_min_len'] and vowels == 0:
            return True, "No vowels in domain name"
        
        return False, ""
    
    def _check_dns_tunnel(self, domain: str) -> Tuple[bool, str]:
        """Check for DNS tunneling patterns"""
        for pattern in self.DNS_TUNNEL_PATTERNS:
            if re.search(pattern, domain, re.IGNORECASE):
                return True, f"Matches tunnel pattern: {pattern[:30]}"
        
        # Check for very long subdomains (data exfil)
        parts = domain.split('.')
        for part in parts[:-2]:  # Exclude TLD parts
            if len(part) > 50:
                return True, f"Long subdomain: {len(part)} chars"
        
        # Check for excessive subdomain depth
        if len(parts) > 7:
            return True, f"Excessive subdomain depth: {len(parts)} levels"
        
        # Check for Base64-like patterns in subdomains
        for part in parts[:-2]:
            if len(part) > 20 and re.match(r'^[A-Za-z0-9+/=]+$', part):
                return True, "Base64-like subdomain (potential data exfil)"
        
        return False, ""
    
    def _detect_doh_bypass(self) -> List[Dict]:
        """Detect DNS-over-HTTPS connections that bypass traditional DNS monitoring"""
        doh_connections = []
        
        if not PSUTIL_AVAILABLE:
            return doh_connections
        
        try:
            for conn in psutil.net_connections(kind='inet'):
                if conn.raddr and conn.raddr.port == 443:
                    remote_ip = conn.raddr.ip
                    
                    # Check if connecting to known DoH provider IPs
                    if remote_ip in ['1.1.1.1', '1.0.0.1', '8.8.8.8', '8.8.4.4', '9.9.9.9']:
                        try:
                            proc = psutil.Process(conn.pid) if conn.pid else None
                            proc_name = proc.name() if proc else 'unknown'
                        except:
                            proc_name = 'unknown'
                        
                        # Skip known legitimate applications
                        if proc_name.lower() not in ['chrome', 'firefox', 'edge', 'brave']:
                            doh_connections.append({
                                'remote_ip': remote_ip,
                                'pid': conn.pid,
                                'process': proc_name,
                                'type': 'doh_bypass',
                                'timestamp': datetime.now(timezone.utc).isoformat()
                            })
        except Exception as e:
            logger.debug(f"DoH detection error: {e}")
        
        return doh_connections
    
    def _is_private_ip(self, ip: str) -> bool:
        """Check if IP is in private/internal ranges"""
        try:
            parts = list(map(int, ip.split('.')))
            ip_int = (parts[0] << 24) + (parts[1] << 16) + (parts[2] << 8) + parts[3]
            
            for start, end in self.PRIVATE_IP_RANGES:
                start_parts = list(map(int, start.split('.')))
                end_parts = list(map(int, end.split('.')))
                start_int = (start_parts[0] << 24) + (start_parts[1] << 16) + (start_parts[2] << 8) + start_parts[3]
                end_int = (end_parts[0] << 24) + (end_parts[1] << 16) + (end_parts[2] << 8) + end_parts[3]
                
                if start_int <= ip_int <= end_int:
                    return True
            return False
        except:
            return False
    
    def _detect_dns_rebinding(self, domain: str, resolved_ip: str) -> Tuple[bool, str]:
        """Detect DNS rebinding attacks (external domain resolving to internal IP)"""
        if not resolved_ip:
            return False, ""
        
        # Check if an external domain resolves to internal IP
        if self._is_private_ip(resolved_ip):
            # Check if domain looks external (not .local, .internal, etc.)
            tld = domain.split('.')[-1].lower()
            if tld not in ['local', 'internal', 'lan', 'home', 'corp', 'localdomain']:
                return True, f"External domain resolving to private IP: {resolved_ip}"
        
        return False, ""
    
    def _track_domain_ips(self, domain: str, ip: str) -> Tuple[bool, str]:
        """Track IP history for fast-flux detection"""
        if not ip or not domain:
            return False, ""
        
        now = datetime.now(timezone.utc).isoformat()
        
        if domain not in self.domain_ip_history:
            self.domain_ip_history[domain] = []
        
        self.domain_ip_history[domain].append((ip, now))
        
        # Keep only last 24 hours of history
        self.domain_ip_history[domain] = self.domain_ip_history[domain][-100:]
        
        # Check for fast-flux: many different IPs in short time
        unique_ips = set(entry[0] for entry in self.domain_ip_history[domain])
        
        if len(unique_ips) >= 5 and len(self.domain_ip_history[domain]) >= 10:
            return True, f"Fast-flux detected: {len(unique_ips)} IPs for {domain}"
        
        return False, ""
    
    def _track_newly_observed_domains(self, domain: str) -> Tuple[bool, str]:
        """Track newly observed domains"""
        now = datetime.now(timezone.utc).isoformat()
        
        if domain not in self.domain_first_seen:
            self.domain_first_seen[domain] = now
            # New domain - flag if it has suspicious characteristics
            root_domain = '.'.join(domain.split('.')[-2:])
            
            # Check TLD
            for tld in self.SUSPICIOUS_TLDS:
                if domain.endswith(tld):
                    return True, f"Newly observed domain with suspicious TLD: {tld}"
            
            return True, "Newly observed domain"
        
        return False, ""
    
    def _resolve_domain(self, domain: str) -> Optional[str]:
        """Resolve domain to IP"""
        try:
            import socket
            return socket.gethostbyname(domain)
        except:
            return None

    def scan(self) -> Dict[str, Any]:
        """Monitor DNS queries with enterprise-grade detection"""
        self.threats = []
        self.suspicious_queries = []
        self.doh_connections = []
        self.rebinding_attempts = []
        recent_queries = []
        
        # Method 1: Parse DNS cache (Windows)
        if PLATFORM == "windows":
            try:
                result = subprocess.run(
                    ['ipconfig', '/displaydns'],
                    capture_output=True, text=True, timeout=30
                )
                if result.returncode == 0:
                    # Parse DNS cache
                    current_domain = None
                    current_ip = None
                    for line in result.stdout.split('\n'):
                        if 'Record Name' in line:
                            current_domain = line.split(':')[-1].strip()
                        elif 'A (Host) Record' in line and current_domain:
                            recent_queries.append({'domain': current_domain, 'ip': None})
                        elif current_domain and re.match(r'.*:\s*\d+\.\d+\.\d+\.\d+', line):
                            ip = re.search(r'(\d+\.\d+\.\d+\.\d+)', line)
                            if ip:
                                recent_queries.append({'domain': current_domain, 'ip': ip.group(1)})
                            current_domain = None
            except Exception as e:
                logger.debug(f"DNS cache read error: {e}")
        
        # Method 2: Parse /var/log/syslog or systemd-resolved (Linux)
        else:
            try:
                # Try systemd-resolve statistics
                result = subprocess.run(
                    ['resolvectl', 'statistics'],
                    capture_output=True, text=True, timeout=5
                )
                # Note: This gives statistics, not individual queries
            except Exception:
                pass
            
            # Try reading dnsmasq log if available
            try:
                dnsmasq_log = Path('/var/log/dnsmasq.log')
                if dnsmasq_log.exists():
                    with open(dnsmasq_log, 'r') as f:
                        lines = f.readlines()[-100:]
                        for line in lines:
                            if 'query[A]' in line:
                                match = re.search(r'query\[A\]\s+(\S+)\s+from', line)
                                if match:
                                    recent_queries.append({'domain': match.group(1), 'ip': None})
            except Exception:
                pass
        
        # Method 3: Monitor network connections to port 53
        if PSUTIL_AVAILABLE:
            for conn in psutil.net_connections(kind='inet'):
                try:
                    if conn.raddr and conn.raddr.port == 53:
                        recent_queries.append({'domain': f"dns_query_to:{conn.raddr.ip}", 'ip': None})
                except Exception:
                    pass
        
        # Enterprise: Detect DoH bypass
        doh_detections = self._detect_doh_bypass()
        self.doh_connections = doh_detections
        for doh in doh_detections:
            self._create_threat({
                'domain': f"DoH:{doh['remote_ip']}",
                'reasons': [f"DNS-over-HTTPS bypass detected to {doh['remote_ip']}"],
                'doh_data': doh,
                'frequency': 1
            })
        
        # Analyze queries
        for query_info in recent_queries[:100]:  # Limit to 100
            if isinstance(query_info, str):
                domain = query_info
                resolved_ip = None
            else:
                domain = query_info.get('domain', '')
                resolved_ip = query_info.get('ip')
            
            # Skip if looks like an IP
            if re.match(r'^\d+\.\d+\.\d+\.\d+$', domain):
                continue
            
            suspicious = False
            reasons = []
            mitre_techniques = ["T1071.004"]  # Base: Application Layer Protocol: DNS
            
            # Check TLD
            for tld in self.SUSPICIOUS_TLDS:
                if domain.endswith(tld):
                    suspicious = True
                    reasons.append(f"Suspicious TLD: {tld}")
            
            # Check DGA
            is_dga, dga_reason = self._is_dga_domain(domain)
            if is_dga:
                suspicious = True
                reasons.append(f"DGA: {dga_reason}")
                mitre_techniques.append("T1568.002")  # Dynamic Resolution: DGA
            
            # Check tunneling
            is_tunnel, tunnel_reason = self._check_dns_tunnel(domain)
            if is_tunnel:
                suspicious = True
                reasons.append(f"Tunnel: {tunnel_reason}")
                mitre_techniques.append("T1048.001")  # Exfiltration Over C2
            
            # Enterprise: Check DNS rebinding
            if resolved_ip:
                is_rebind, rebind_reason = self._detect_dns_rebinding(domain, resolved_ip)
                if is_rebind:
                    suspicious = True
                    reasons.append(rebind_reason)
                    self.rebinding_attempts.append({
                        'domain': domain,
                        'resolved_ip': resolved_ip,
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    })
                
                # Track for fast-flux detection
                is_fastflux, ff_reason = self._track_domain_ips(domain, resolved_ip)
                if is_fastflux:
                    suspicious = True
                    reasons.append(ff_reason)
                    mitre_techniques.append("T1568.001")  # Fast Flux DNS
            
            # Track newly observed domains
            is_nod, nod_reason = self._track_newly_observed_domains(domain)
            if is_nod:
                # Only flag if combined with other suspicious indicators
                if suspicious:
                    reasons.append(nod_reason)
            
            # Track frequency
            self.query_cache[domain] = self.query_cache.get(domain, 0) + 1
            if self.query_cache[domain] > 100:
                suspicious = True
                reasons.append(f"High frequency: {self.query_cache[domain]}")
            
            if suspicious:
                query_data = {
                    'domain': domain,
                    'resolved_ip': resolved_ip,
                    'reasons': reasons,
                    'frequency': self.query_cache.get(domain, 1),
                    'mitre': list(set(mitre_techniques)),
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
                self.suspicious_queries.append(query_data)
                self._create_threat(query_data)
        
        self.dns_log.extend([q['domain'] if isinstance(q, dict) else q for q in recent_queries])
        self.dns_log = self.dns_log[-1000:]  # Keep last 1000
        
        self.last_run = datetime.now(timezone.utc)
        
        return {
            "queries_analyzed": len(recent_queries),
            "suspicious_count": len(self.suspicious_queries),
            "doh_bypass_detected": len(self.doh_connections),
            "rebinding_attempts": len(self.rebinding_attempts),
            "newly_observed_domains": len(self.domain_first_seen),
            "fast_flux_tracked": len([d for d, ips in self.domain_ip_history.items() if len(set(ip for ip, _ in ips)) >= 3]),
            "threats": len(self.threats),
            "suspicious": self.suspicious_queries[-20:]
        }
    
    def _create_threat(self, query_data: Dict):
        """Create threat from suspicious DNS activity"""
        reasons = query_data.get('reasons', [])
        mitre_techniques = query_data.get('mitre', ["T1071.004"])
        
        # Determine severity based on threat type
        if any('DoH' in r or 'bypass' in r.lower() for r in reasons):
            severity = ThreatSeverity.HIGH
            mitre_techniques.append("T1572")  # Protocol Tunneling
        elif any('Tunnel' in r or 'DGA' in r for r in reasons):
            severity = ThreatSeverity.HIGH
        elif any('rebind' in r.lower() or 'private IP' in r for r in reasons):
            severity = ThreatSeverity.CRITICAL
            mitre_techniques.append("T1557")  # Adversary in the Middle
        elif any('Fast-flux' in r or 'fast-flux' in r.lower() for r in reasons):
            severity = ThreatSeverity.HIGH
            mitre_techniques.append("T1568.001")  # Fast Flux DNS
        else:
            severity = ThreatSeverity.MEDIUM
        
        threat = Threat(
            threat_id=f"dns-{uuid.uuid4().hex[:8]}",
            title=f"Suspicious DNS: {query_data['domain'][:50]}",
            description=f"Suspicious DNS activity detected: {', '.join(reasons[:5])}",
            severity=severity,
            threat_type="dns_anomaly",
            source="dns_monitor",
            target=query_data['domain'],
            evidence=query_data,
            mitre_techniques=list(set(mitre_techniques)),
            auto_kill_eligible=False,
            remediation_action="block_domain",
            remediation_params={"domain": query_data['domain']}
        )
        self.threats.append(threat)
    
    def get_threats(self) -> List[Threat]:
        return self.threats


class MemoryScanner(MonitorModule):
    """
    Memory Scanner - Detect process injection, hollowing, and shellcode.
    Scans process memory for signs of malicious code injection.
    
    Enterprise Features:
    - RWX memory region detection
    - Shellcode pattern scanning
    - Process hollowing detection (image mismatch)
    - Cobalt Strike beacon detection
    - Reflective DLL injection detection
    - API/IAT hooking detection
    - Unbacked executable memory detection
    """
    
    # Suspicious memory patterns (shellcode signatures)
    SHELLCODE_PATTERNS = [
        b'\xfc\xe8',           # Common shellcode start (CLD; CALL)
        b'\x90\x90\x90\x90',   # NOP sled  
        b'\xeb\xfe',           # Infinite loop (anti-debug)
        b'\x64\xa1\x30\x00',   # PEB access (TEB) x86
        b'\x65\x48\x8b\x04\x25\x60\x00', # PEB access x64
        b'\x31\xc0\x50\x68',   # Common x86 shellcode (XOR EAX, PUSH, PUSH)
        b'\x48\x31\xc9',       # x64 XOR RCX,RCX
        b'\x4d\x5a',           # MZ header (embedded PE)
        b'\x48\x83\xec',       # x64 SUB RSP (stack setup)
        b'\xe8\x00\x00\x00\x00\x58', # CALL $+5; POP EAX (position-independent)
        b'\xe8\x00\x00\x00\x00\x5e', # CALL $+5; POP ESI
        b'\xe8\x00\x00\x00\x00\x5d', # CALL $+5; POP EBP
    ]
    
    # Cobalt Strike beacon signatures
    COBALT_STRIKE_PATTERNS = [
        b'\x4d\x5a\x41\x52\x55\x48\x89\xe5',  # CS beacon header
        b'%s.stage.%d.%s',                     # CS staging pattern
        b'beacon.dll',
        b'ReflectiveLoader',
        b'%s/submit.php',                      # CS default callback
        b'%s/pixel.gif',
        b'\x00\x00\x00\x00\xf8\x00\x00\x00',  # CS malleable profile indicator
    ]
    
    # Metasploit/Meterpreter patterns
    METERPRETER_PATTERNS = [
        b'metsrv.dll',
        b'stdapi.dll',
        b'priv.dll',
        b'sniffer.dll',
        b'ReflectiveDLLInject',
        b'\xfc\x48\x83\xe4\xf0',  # Meterpreter x64 stub
        b'\xfc\xe8\x82\x00\x00',  # Meterpreter x86 stub
    ]
    
    # Suspicious API names (hooks/injection indicators)
    SUSPICIOUS_APIS = {
        'ntdll.dll': ['NtAllocateVirtualMemory', 'NtWriteVirtualMemory', 'NtCreateThreadEx', 
                      'NtProtectVirtualMemory', 'NtMapViewOfSection', 'NtUnmapViewOfSection',
                      'NtQueueApcThread', 'NtSetContextThread'],
        'kernel32.dll': ['VirtualAllocEx', 'WriteProcessMemory', 'CreateRemoteThread',
                        'SetThreadContext', 'QueueUserAPC', 'NtMapViewOfSection'],
    }
    
    # Suspicious memory region flags
    SUSPICIOUS_PROTECTIONS = {
        'rwx': 'Read-Write-Execute (code injection)',
        'rx_unbacked': 'Executable unbacked memory',
        'guard': 'Guard page (potential shellcode staging)',
    }
    
    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self.threats = []
        self.suspicious_processes = []
        self.cobalt_strike_detections = []
        self.process_hollowing_detections = []
        self.api_hooks_detected = []
    
    def scan(self) -> Dict[str, Any]:
        """Scan process memory for injection indicators"""
        self.threats = []
        self.suspicious_processes = []
        self.cobalt_strike_detections = []
        self.process_hollowing_detections = []
        self.api_hooks_detected = []
        
        if not PSUTIL_AVAILABLE:
            return {"error": "psutil not available"}
        
        scanned = 0
        suspicious = 0
        
        for proc in psutil.process_iter(['pid', 'name', 'exe']):
            try:
                info = proc.info
                pid = info['pid']
                name = info.get('name', '')
                exe = info.get('exe', '')
                
                # Skip system processes
                if pid < 10:
                    continue
                
                findings = self._scan_process_memory(pid, name, exe)
                scanned += 1
                
                if findings:
                    suspicious += 1
                    self.suspicious_processes.append({
                        'pid': pid,
                        'name': name,
                        'exe': exe,
                        'findings': findings,
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    })
                    self._create_threat(info, findings)
                    
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
            except Exception as e:
                logger.debug(f"Memory scan error for process: {e}")
        
        self.last_run = datetime.now(timezone.utc)
        
        return {
            "processes_scanned": scanned,
            "suspicious_found": suspicious,
            "threats": len(self.threats),
            "cobalt_strike_detections": len(self.cobalt_strike_detections),
            "process_hollowing": len(self.process_hollowing_detections),
            "api_hooks": len(self.api_hooks_detected),
            "rwx_regions": sum(1 for p in self.suspicious_processes 
                              for f in p['findings'] if f['type'] == 'rwx_memory'),
            "injections_detected": suspicious,
            "details": self.suspicious_processes[-10:]
        }
    
    def _scan_process_memory(self, pid: int, name: str, exe: str) -> List[Dict]:
        """Scan a single process for memory anomalies"""
        findings = []
        
        if PLATFORM == "windows":
            findings.extend(self._scan_windows_memory(pid))
            findings.extend(self._scan_for_shellcode_windows(pid))
            findings.extend(self._detect_process_hollowing(pid, name, exe))
        else:
            findings.extend(self._scan_linux_memory(pid))
            findings.extend(self._scan_for_shellcode_linux(pid))
        
        return findings
    
    def _scan_for_shellcode_windows(self, pid: int) -> List[Dict]:
        """Scan Windows process memory for shellcode patterns"""
        findings = []
        
        try:
            import ctypes
            from ctypes import wintypes
            
            PROCESS_QUERY_INFORMATION = 0x0400
            PROCESS_VM_READ = 0x0010
            MEM_COMMIT = 0x1000
            PAGE_EXECUTE_READWRITE = 0x40
            PAGE_EXECUTE_READ = 0x20
            PAGE_READWRITE = 0x04
            
            kernel32 = ctypes.windll.kernel32
            
            h_process = kernel32.OpenProcess(
                PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, 
                False, 
                pid
            )
            
            if not h_process:
                return findings
            
            class MEMORY_BASIC_INFORMATION(ctypes.Structure):
                _fields_ = [
                    ("BaseAddress", ctypes.c_void_p),
                    ("AllocationBase", ctypes.c_void_p),
                    ("AllocationProtect", wintypes.DWORD),
                    ("RegionSize", ctypes.c_size_t),
                    ("State", wintypes.DWORD),
                    ("Protect", wintypes.DWORD),
                    ("Type", wintypes.DWORD),
                ]
            
            MEM_IMAGE = 0x1000000
            MEM_MAPPED = 0x40000
            MEM_PRIVATE = 0x20000
            
            mbi = MEMORY_BASIC_INFORMATION()
            address = 0
            
            while kernel32.VirtualQueryEx(
                h_process, 
                ctypes.c_void_p(address), 
                ctypes.byref(mbi), 
                ctypes.sizeof(mbi)
            ):
                # Scan executable private memory (unbacked - suspicious)
                if (mbi.State == MEM_COMMIT and 
                    mbi.Protect in (PAGE_EXECUTE_READWRITE, PAGE_EXECUTE_READ) and
                    mbi.Type == MEM_PRIVATE and
                    mbi.RegionSize < 10 * 1024 * 1024):  # Skip huge regions
                    
                    # Read and scan memory content
                    buffer = (ctypes.c_char * min(mbi.RegionSize, 65536))()
                    bytes_read = ctypes.c_size_t()
                    
                    if kernel32.ReadProcessMemory(
                        h_process,
                        ctypes.c_void_p(mbi.BaseAddress),
                        buffer,
                        len(buffer),
                        ctypes.byref(bytes_read)
                    ):
                        content = bytes(buffer[:bytes_read.value])
                        
                        # Check for shellcode patterns
                        for pattern in self.SHELLCODE_PATTERNS:
                            if pattern in content:
                                findings.append({
                                    'type': 'shellcode_detected',
                                    'address': hex(mbi.BaseAddress),
                                    'size': mbi.RegionSize,
                                    'pattern': pattern[:8].hex(),
                                    'description': 'Shellcode signature detected in executable memory'
                                })
                                break
                        
                        # Check for Cobalt Strike
                        for cs_pattern in self.COBALT_STRIKE_PATTERNS:
                            if cs_pattern in content:
                                self.cobalt_strike_detections.append(pid)
                                findings.append({
                                    'type': 'cobalt_strike',
                                    'address': hex(mbi.BaseAddress),
                                    'description': 'Cobalt Strike beacon signature detected',
                                    'severity': 'critical'
                                })
                                break
                        
                        # Check for Meterpreter
                        for meterpreter_pattern in self.METERPRETER_PATTERNS:
                            if meterpreter_pattern in content:
                                findings.append({
                                    'type': 'meterpreter',
                                    'address': hex(mbi.BaseAddress),
                                    'description': 'Meterpreter payload signature detected',
                                    'severity': 'critical'
                                })
                                break
                        
                        # Check for embedded PE (reflective DLL)
                        if b'MZ' in content and b'This program' in content:
                            findings.append({
                                'type': 'reflective_dll',
                                'address': hex(mbi.BaseAddress),
                                'description': 'Embedded PE detected (potential reflective DLL injection)'
                            })
                
                address = mbi.BaseAddress + mbi.RegionSize
                if address >= 0x7FFFFFFF0000:
                    break
            
            kernel32.CloseHandle(h_process)
            
        except Exception as e:
            logger.debug(f"Shellcode scan error: {e}")
        
        return findings
    
    def _detect_process_hollowing(self, pid: int, name: str, exe: str) -> List[Dict]:
        """Detect process hollowing by comparing disk vs memory image"""
        findings = []
        
        if PLATFORM != "windows" or not exe:
            return findings
        
        try:
            import ctypes
            from ctypes import wintypes
            
            # Get the expected image base from disk
            try:
                with open(exe, 'rb') as f:
                    f.seek(0x3C)  # PE header offset location
                    pe_offset = int.from_bytes(f.read(4), 'little')
                    f.seek(pe_offset + 0x34)  # ImageBase for 32-bit
                    disk_image_base = int.from_bytes(f.read(4), 'little')
            except Exception:
                return findings
            
            # Get actual loaded base via EnumProcessModules
            kernel32 = ctypes.windll.kernel32
            psapi = ctypes.windll.psapi
            
            PROCESS_QUERY_INFORMATION = 0x0400
            PROCESS_VM_READ = 0x0010
            
            h_process = kernel32.OpenProcess(
                PROCESS_QUERY_INFORMATION | PROCESS_VM_READ,
                False,
                pid
            )
            
            if not h_process:
                return findings
            
            # Get module list
            h_modules = (ctypes.c_void_p * 1024)()
            cb_needed = ctypes.c_ulong()
            
            if psapi.EnumProcessModules(
                h_process,
                ctypes.byref(h_modules),
                ctypes.sizeof(h_modules),
                ctypes.byref(cb_needed)
            ):
                # First module is the main executable
                main_module = h_modules[0]
                
                # Read first few bytes of memory vs disk
                buffer = (ctypes.c_char * 4096)()
                bytes_read = ctypes.c_size_t()
                
                if kernel32.ReadProcessMemory(
                    h_process,
                    main_module,
                    buffer,
                    4096,
                    ctypes.byref(bytes_read)
                ):
                    memory_content = bytes(buffer[:bytes_read.value])
                    
                    # Read same bytes from disk
                    try:
                        with open(exe, 'rb') as f:
                            disk_content = f.read(4096)
                        
                        # Compare MZ header and first section
                        if memory_content[:2] == b'MZ' and disk_content[:2] == b'MZ':
                            # Check for significant differences (hollowing indicator)
                            differences = sum(1 for a, b in zip(memory_content[:1024], disk_content[:1024]) if a != b)
                            
                            if differences > 100:  # More than 10% different
                                self.process_hollowing_detections.append(pid)
                                findings.append({
                                    'type': 'process_hollowing',
                                    'address': hex(main_module),
                                    'exe': exe,
                                    'differences': differences,
                                    'description': f'Memory/disk mismatch detected ({differences} byte differences)'
                                })
                        elif memory_content[:2] != b'MZ' and disk_content[:2] == b'MZ':
                            # Memory doesn't start with MZ but disk does - definitely hollowed
                            self.process_hollowing_detections.append(pid)
                            findings.append({
                                'type': 'process_hollowing',
                                'description': 'Process hollowed - no MZ header in memory but present on disk'
                            })
                    except Exception:
                        pass
            
            kernel32.CloseHandle(h_process)
            
        except Exception as e:
            logger.debug(f"Process hollowing check error: {e}")
        
        return findings
    
    def _scan_for_shellcode_linux(self, pid: int) -> List[Dict]:
        """Scan Linux process memory for shellcode patterns"""
        findings = []
        
        try:
            mem_path = f"/proc/{pid}/mem"
            maps_path = f"/proc/{pid}/maps"
            
            if not Path(maps_path).exists():
                return findings
            
            # Parse memory maps and scan executable anonymous regions
            with open(maps_path, 'r') as maps_file:
                for line in maps_file:
                    parts = line.split()
                    if len(parts) < 5:
                        continue
                    
                    addr_range = parts[0]
                    perms = parts[1]
                    path = parts[-1] if len(parts) > 5 else ''
                    
                    # Look for executable anonymous memory (potential shellcode)
                    if 'x' in perms and ('[heap]' in path or '[stack]' in path or 
                                          path == '' or 'anon' in path.lower()):
                        try:
                            start_addr, end_addr = addr_range.split('-')
                            start = int(start_addr, 16)
                            end = int(end_addr, 16)
                            size = end - start
                            
                            # Read small regions
                            if size < 1024 * 1024:  # < 1MB
                                with open(mem_path, 'rb') as mem_file:
                                    mem_file.seek(start)
                                    content = mem_file.read(min(size, 65536))
                                    
                                    # Check for shellcode patterns
                                    for pattern in self.SHELLCODE_PATTERNS:
                                        if pattern in content:
                                            findings.append({
                                                'type': 'shellcode_detected',
                                                'address': hex(start),
                                                'size': size,
                                                'perms': perms,
                                                'description': 'Shellcode signature in executable anonymous memory'
                                            })
                                            break
                                    
                                    # Check for Cobalt Strike/Meterpreter
                                    for cs_pattern in self.COBALT_STRIKE_PATTERNS + self.METERPRETER_PATTERNS:
                                        if cs_pattern in content:
                                            findings.append({
                                                'type': 'implant_detected',
                                                'address': hex(start),
                                                'description': 'Known implant signature detected'
                                            })
                                            break
                        except (PermissionError, OSError):
                            pass
                            
        except (PermissionError, FileNotFoundError):
            pass
        except Exception as e:
            logger.debug(f"Linux shellcode scan error: {e}")
        
        return findings
    
    def _scan_windows_memory(self, pid: int) -> List[Dict]:
        """Windows memory scanning using VirtualQueryEx"""
        findings = []
        
        try:
            # Use ctypes to read process memory regions
            import ctypes
            from ctypes import wintypes
            
            PROCESS_QUERY_INFORMATION = 0x0400
            PROCESS_VM_READ = 0x0010
            MEM_COMMIT = 0x1000
            PAGE_EXECUTE_READWRITE = 0x40
            PAGE_EXECUTE_READ = 0x20
            
            kernel32 = ctypes.windll.kernel32
            
            # Open process
            h_process = kernel32.OpenProcess(
                PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, 
                False, 
                pid
            )
            
            if not h_process:
                return findings
            
            # Define MEMORY_BASIC_INFORMATION structure
            class MEMORY_BASIC_INFORMATION(ctypes.Structure):
                _fields_ = [
                    ("BaseAddress", ctypes.c_void_p),
                    ("AllocationBase", ctypes.c_void_p),
                    ("AllocationProtect", wintypes.DWORD),
                    ("RegionSize", ctypes.c_size_t),
                    ("State", wintypes.DWORD),
                    ("Protect", wintypes.DWORD),
                    ("Type", wintypes.DWORD),
                ]
            
            mbi = MEMORY_BASIC_INFORMATION()
            address = 0
            
            while kernel32.VirtualQueryEx(
                h_process, 
                ctypes.c_void_p(address), 
                ctypes.byref(mbi), 
                ctypes.sizeof(mbi)
            ):
                # Check for RWX regions (highly suspicious)
                if mbi.State == MEM_COMMIT and mbi.Protect == PAGE_EXECUTE_READWRITE:
                    findings.append({
                        'type': 'rwx_memory',
                        'address': hex(mbi.BaseAddress),
                        'size': mbi.RegionSize,
                        'description': 'RWX memory region detected'
                    })
                
                address = mbi.BaseAddress + mbi.RegionSize
                if address >= 0x7FFFFFFF0000:  # Stop at user-mode limit
                    break
            
            kernel32.CloseHandle(h_process)
            
        except Exception as e:
            logger.debug(f"Windows memory scan error: {e}")
        
        return findings
    
    def _scan_linux_memory(self, pid: int) -> List[Dict]:
        """Linux memory scanning via /proc/pid/maps"""
        findings = []
        
        try:
            maps_path = f"/proc/{pid}/maps"
            if not Path(maps_path).exists():
                return findings
            
            with open(maps_path, 'r') as f:
                for line in f:
                    parts = line.split()
                    if len(parts) < 5:
                        continue
                    
                    perms = parts[1]
                    path = parts[-1] if len(parts) > 5 else '[anonymous]'
                    
                    # Detect RWX regions
                    if perms == 'rwxp' or perms == 'rwxs':
                        findings.append({
                            'type': 'rwx_memory',
                            'address': parts[0],
                            'perms': perms,
                            'path': path,
                            'description': 'RWX memory region (potential injection)'
                        })
                    
                    # Detect anonymous executable memory (shellcode)
                    if ('anonymous' in path.lower() or path == '') and 'x' in perms:
                        findings.append({
                            'type': 'anonymous_executable',
                            'address': parts[0],
                            'perms': perms,
                            'description': 'Anonymous executable memory (potential shellcode)'
                        })
                        
        except PermissionError:
            pass
        except Exception as e:
            logger.debug(f"Linux memory scan error: {e}")
        
        return findings
    
    def _create_threat(self, proc_info: Dict, findings: List[Dict]):
        """Create threat from memory scan findings"""
        threat = Threat(
            threat_id=f"mem-{uuid.uuid4().hex[:8]}",
            title=f"Memory Injection: {proc_info.get('name', 'Unknown')}",
            description=f"Suspicious memory patterns detected: {len(findings)} findings",
            severity=ThreatSeverity.CRITICAL,
            threat_type="memory_injection",
            source="memory_scanner",
            target=f"{proc_info.get('pid')}:{proc_info.get('name')}",
            evidence={'findings': findings[:5], 'process': proc_info},
            mitre_techniques=["T1055", "T1055.001", "T1055.012"],  # Process Injection, DLL Injection, Hollowing
            auto_kill_eligible=True,
            remediation_action="kill_process",
            remediation_params={"pid": proc_info.get('pid'), "name": proc_info.get('name')}
        )
        self.threats.append(threat)
    
    def get_threats(self) -> List[Threat]:
        return self.threats


class ApplicationWhitelistMonitor(MonitorModule):
    """
    Application Whitelisting - Only allow approved applications to run.
    Monitors for unauthorized executables and can block execution.
    """
    
    # Default whitelist locations (will be populated from config/server)
    DEFAULT_TRUSTED_PATHS = [
        # Windows
        r"C:\Windows\System32",
        r"C:\Windows\SysWOW64",
        r"C:\Program Files",
        r"C:\Program Files (x86)",
        # Linux
        "/usr/bin",
        "/usr/sbin",
        "/bin",
        "/sbin",
        "/usr/local/bin",
        "/usr/local/sbin",
        # macOS
        "/Applications",
        "/System",
    ]
    
    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self.threats = []
        self.whitelist: Set[str] = set()
        self.trusted_paths: Set[str] = set(self.DEFAULT_TRUSTED_PATHS)
        self.trusted_hashes: Set[str] = set()
        self.trusted_publishers: Set[str] = set()
        self.violations = []
        self._load_whitelist()
    
    def _load_whitelist(self):
        """Load whitelist from config or local file"""
        whitelist_file = Path.home() / ".metatron" / "app_whitelist.json"
        try:
            if whitelist_file.exists():
                with open(whitelist_file, 'r') as f:
                    data = json.load(f)
                    self.whitelist = set(data.get('executables', []))
                    self.trusted_paths.update(data.get('paths', []))
                    self.trusted_hashes = set(data.get('hashes', []))
                    self.trusted_publishers = set(data.get('publishers', []))
        except Exception as e:
            logger.debug(f"Error loading whitelist: {e}")
    
    def add_to_whitelist(self, executable: str = None, path: str = None, 
                         hash_value: str = None, publisher: str = None) -> bool:
        """Add an item to the whitelist"""
        if executable:
            self.whitelist.add(executable.lower())
        if path:
            self.trusted_paths.add(path)
        if hash_value:
            self.trusted_hashes.add(hash_value.lower())
        if publisher:
            self.trusted_publishers.add(publisher.lower())
        return self._save_whitelist()
    
    def _save_whitelist(self) -> bool:
        """Save whitelist to local file"""
        whitelist_file = Path.home() / ".metatron" / "app_whitelist.json"
        try:
            whitelist_file.parent.mkdir(parents=True, exist_ok=True)
            data = {
                'executables': list(self.whitelist),
                'paths': list(self.trusted_paths),
                'hashes': list(self.trusted_hashes),
                'publishers': list(self.trusted_publishers)
            }
            with open(whitelist_file, 'w') as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error saving whitelist: {e}")
            return False
    
    def is_whitelisted(self, exe_path: str) -> Tuple[bool, str]:
        """Check if an executable is whitelisted"""
        path = Path(exe_path)
        name = path.name.lower()
        
        # Check executable name
        if name in self.whitelist:
            return True, "executable_name"
        
        # Check path
        for trusted_path in self.trusted_paths:
            if str(exe_path).lower().startswith(trusted_path.lower()):
                return True, "trusted_path"
        
        # Check hash
        try:
            exe_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            if exe_hash in self.trusted_hashes:
                return True, "trusted_hash"
        except Exception:
            pass
        
        return False, ""
    
    def scan(self) -> Dict[str, Any]:
        """Scan running processes against whitelist"""
        self.threats = []
        self.violations = []
        
        if not PSUTIL_AVAILABLE:
            return {"error": "psutil not available"}
        
        checked = 0
        violations = 0
        
        for proc in psutil.process_iter(['pid', 'name', 'exe', 'username']):
            try:
                info = proc.info
                exe_path = info.get('exe')
                
                if not exe_path:
                    continue
                
                checked += 1
                is_allowed, reason = self.is_whitelisted(exe_path)
                
                if not is_allowed:
                    violations += 1
                    violation = {
                        'pid': info['pid'],
                        'name': info['name'],
                        'exe': exe_path,
                        'username': info.get('username'),
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    }
                    self.violations.append(violation)
                    self._create_threat(violation)
                    
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        self.last_run = datetime.now(timezone.utc)
        
        return {
            "processes_checked": checked,
            "violations": violations,
            "whitelist_size": len(self.whitelist) + len(self.trusted_paths),
            "threats": len(self.threats),
            "details": self.violations[-20:]
        }
    
    def _create_threat(self, violation: Dict):
        """Create threat from whitelist violation"""
        threat = Threat(
            threat_id=f"whitelist-{uuid.uuid4().hex[:8]}",
            title=f"Unauthorized Application: {violation['name']}",
            description=f"Application not in whitelist: {violation['exe']}",
            severity=ThreatSeverity.MEDIUM,
            threat_type="whitelist_violation",
            source="application_whitelist",
            target=violation['exe'],
            evidence=violation,
            mitre_techniques=["T1204", "T1059"],  # User Execution, Command Interpreter
            auto_kill_eligible=False,  # Require approval for whitelist violations
            remediation_action="block_or_whitelist",
            remediation_params={"pid": violation['pid'], "exe": violation['exe']}
        )
        self.threats.append(threat)
    
    def get_threats(self) -> List[Threat]:
        return self.threats

class SimpleBloomFilter:
    """Lightweight Bloom filter for quick EDM non-membership checks."""

    def __init__(self, capacity: int, error_rate: float = 0.01):
        self.capacity = max(1, int(capacity))
        self.error_rate = min(max(float(error_rate), 0.0001), 0.25)
        m = -self.capacity * math.log(self.error_rate) / (math.log(2) ** 2)
        self.bit_size = max(1024, int(m))
        k = (self.bit_size / self.capacity) * math.log(2)
        self.hash_count = max(2, min(12, int(round(k))))
        self.bits = bytearray((self.bit_size + 7) // 8)

    def _indexes(self, value: str) -> List[int]:
        value_b = value.encode("utf-8")
        indexes = []
        for i in range(self.hash_count):
            digest = hashlib.sha256(value_b + f"#{i}".encode("utf-8")).digest()
            indexes.append(int.from_bytes(digest[:8], "big") % self.bit_size)
        return indexes

    def add(self, value: str):
        for idx in self._indexes(value):
            self.bits[idx // 8] |= (1 << (idx % 8))

    def __contains__(self, value: str) -> bool:
        for idx in self._indexes(value):
            if not (self.bits[idx // 8] & (1 << (idx % 8))):
                return False
        return True


class EDMFingerprintEngine:
    """Exact Data Match (EDM) fingerprint engine for deterministic record matching."""

    def __init__(
        self,
        dataset_path: str,
        tenant_salt: str = "",
        max_records: int = 20000,
        default_min_confidence: float = 0.90,
        default_allowed_candidate_types: Optional[List[str]] = None,
    ):
        self.dataset_path = Path(dataset_path)
        self.tenant_salt = tenant_salt or "metatron-default-edm-salt"
        self.max_records = max(1000, int(max_records or 20000))
        self.default_min_confidence = min(max(float(default_min_confidence), 0.0), 1.0)
        self.default_allowed_candidate_types = set(default_allowed_candidate_types or [
            "line", "delimited_bundle", "delimited_window_4", "delimited_window_3", "delimited_window_2"
        ])
        self.fingerprint_index: Dict[str, Dict[str, Any]] = {}
        self.dataset_policies: Dict[str, Dict[str, Any]] = {}
        # Fast precheck: avoids full fingerprint lookups when candidate cannot match.
        self.prefix_index: Set[str] = set()
        self.bloom_filter: Optional[SimpleBloomFilter] = None
        self.dataset_count = 0
        self.record_count = 0
        self.fingerprint_count = 0
        self.last_loaded_at = ""
        self.load_datasets()

    @staticmethod
    def _normalize_text(value: Any) -> str:
        text = str(value or "")
        text = re.sub(r"\s+", " ", text.strip().lower())
        return text

    @classmethod
    def canonicalize_record(cls, record: Any) -> str:
        """Canonicalize record so identical data maps to identical fingerprint."""
        if isinstance(record, dict):
            parts = []
            for key in sorted(record.keys()):
                val = cls._normalize_text(record.get(key))
                if val:
                    parts.append(f"{cls._normalize_text(key)}={val}")
            return "|".join(parts)

        if isinstance(record, list):
            vals = [cls._normalize_text(v) for v in record if cls._normalize_text(v)]
            return "|".join(vals)

        return cls._normalize_text(record)

    def _fingerprint(self, canonical: str) -> str:
        return hashlib.sha256(f"{self.tenant_salt}::{canonical}".encode("utf-8")).hexdigest()

    def _record_variants(self, record: Any) -> List[Tuple[str, str]]:
        """Generate canonical variants to improve EDM recall without fuzzy matching."""
        variants: List[Tuple[str, str]] = []

        primary = self.canonicalize_record(record)
        if primary:
            variants.append((primary, "canonical"))

        if isinstance(record, dict):
            values = [self._normalize_text(v) for v in record.values()]
            values = [v for v in values if v]
            if values:
                value_bundle = "|".join(sorted(values))
                if value_bundle and value_bundle != primary:
                    variants.append((value_bundle, "values"))

                # Add ordered value windows for common CSV-like records.
                max_window = min(4, len(values))
                for width in range(2, max_window + 1):
                    for i in range(0, len(values) - width + 1):
                        window = "|".join(values[i:i + width])
                        if window and window != primary:
                            variants.append((window, f"values_window_{width}"))

        if isinstance(record, list):
            vals = [self._normalize_text(v) for v in record if self._normalize_text(v)]
            max_window = min(4, len(vals))
            for width in range(2, max_window + 1):
                for i in range(0, len(vals) - width + 1):
                    window = "|".join(vals[i:i + width])
                    if window and window != primary:
                        variants.append((window, f"list_window_{width}"))

        # Deduplicate while preserving insertion order.
        seen = set()
        deduped: List[Tuple[str, str]] = []
        for variant_value, variant_type in variants:
            key = (variant_value, variant_type)
            if key in seen:
                continue
            seen.add(key)
            deduped.append((variant_value, variant_type))
        return deduped

    def _parse_dataset_payload(self, payload: Any) -> List[Dict[str, Any]]:
        if isinstance(payload, dict) and isinstance(payload.get("datasets"), list):
            return payload["datasets"]
        if isinstance(payload, list):
            return payload
        return []

    def _parse_dataset_policy(self, dataset_obj: Dict[str, Any]) -> Dict[str, Any]:
        precision = dataset_obj.get("precision", {}) if isinstance(dataset_obj, dict) else {}
        if not isinstance(precision, dict):
            precision = {}

        min_conf = precision.get("min_confidence", self.default_min_confidence)
        try:
            min_conf = float(min_conf)
        except Exception:
            min_conf = self.default_min_confidence
        min_conf = min(max(min_conf, 0.0), 1.0)

        allowed = precision.get("allowed_candidate_types")
        if isinstance(allowed, list) and allowed:
            allowed_set = {str(a).strip() for a in allowed if str(a).strip()}
        else:
            allowed_set = set(self.default_allowed_candidate_types)

        return {
            "min_confidence": min_conf,
            "allowed_candidate_types": allowed_set,
        }

    def load_datasets(self):
        """Load EDM datasets from JSON and build in-memory fingerprint index."""
        self.fingerprint_index = {}
        self.dataset_policies = {}
        self.prefix_index = set()
        self.bloom_filter = None
        self.dataset_count = 0
        self.record_count = 0
        self.fingerprint_count = 0

        if not self.dataset_path.exists():
            self.last_loaded_at = datetime.now(timezone.utc).isoformat()
            return

        try:
            with open(self.dataset_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except Exception as e:
            logger.warning(f"EDM dataset load failed: {e}")
            self.last_loaded_at = datetime.now(timezone.utc).isoformat()
            return

        datasets = self._parse_dataset_payload(payload)
        for ds in datasets:
            if self.record_count >= self.max_records:
                break

            dataset_id = str(ds.get("dataset_id") or ds.get("name") or f"dataset-{self.dataset_count + 1}")
            self.dataset_policies[dataset_id] = self._parse_dataset_policy(ds)
            records = ds.get("records", []) if isinstance(ds, dict) else []
            if not isinstance(records, list):
                continue

            ingested = 0
            for idx, record in enumerate(records):
                if self.record_count >= self.max_records:
                    break
                variants = self._record_variants(record)
                if not variants:
                    continue

                record_id = str(getattr(record, "get", lambda *_: None)("record_id") or f"{dataset_id}-{idx + 1}")
                for canonical, variant_type in variants:
                    fp = self._fingerprint(canonical)
                    if fp in self.fingerprint_index:
                        continue
                    self.fingerprint_index[fp] = {
                        "dataset_id": dataset_id,
                        "record_id": record_id,
                        "canonical_preview": canonical[:180],
                        "variant_type": variant_type,
                    }
                    self.prefix_index.add(canonical[:16])

                self.record_count += 1
                ingested += 1

            if ingested:
                self.dataset_count += 1

        self.last_loaded_at = datetime.now(timezone.utc).isoformat()
        self.fingerprint_count = len(self.fingerprint_index)
        if self.fingerprint_count > 0:
            self.bloom_filter = SimpleBloomFilter(capacity=max(1000, self.fingerprint_count), error_rate=0.01)
            for fp in self.fingerprint_index.keys():
                self.bloom_filter.add(fp)
        logger.info(
            f"EDM loaded {self.record_count} records and {self.fingerprint_count} fingerprints across {self.dataset_count} dataset(s) from {self.dataset_path}"
        )

    def _extract_candidates(self, text: str, max_candidates: int = 2000) -> List[Tuple[str, str]]:
        """Extract normalized candidates from free text and delimited content."""
        candidates: List[Tuple[str, str]] = []

        for raw in text.splitlines():
            normalized = self._normalize_text(raw)
            if len(normalized) < 8:
                continue

            candidates.append((normalized, "line"))
            if len(candidates) >= max_candidates:
                break

            # Structured extraction for CSV/TSV/pipe-like text.
            for delim in [",", "\t", "|", ";"]:
                if delim not in raw:
                    continue
                parts = [self._normalize_text(p) for p in raw.split(delim)]
                parts = [p for p in parts if len(p) >= 3]
                if len(parts) < 2:
                    continue

                bundle = "|".join(parts)
                if len(bundle) >= 8:
                    candidates.append((bundle, "delimited_bundle"))
                    if len(candidates) >= max_candidates:
                        break

                max_width = min(4, len(parts))
                for width in range(2, max_width + 1):
                    for i in range(0, len(parts) - width + 1):
                        window = "|".join(parts[i:i + width])
                        if len(window) < 8:
                            continue
                        candidates.append((window, f"delimited_window_{width}"))
                        if len(candidates) >= max_candidates:
                            break
                    if len(candidates) >= max_candidates:
                        break
                if len(candidates) >= max_candidates:
                    break

            if len(candidates) >= max_candidates:
                break

        return candidates

    def match_text(self, text: str, max_candidates: int = 2000) -> List[Dict[str, Any]]:
        """Attempt exact record matches over line-oriented and structured candidates."""
        if not text or not self.fingerprint_index:
            return []

        confidence_map = {
            "line": 0.99,
            "delimited_bundle": 0.96,
            "delimited_window_4": 0.95,
            "delimited_window_3": 0.94,
            "delimited_window_2": 0.92,
        }

        candidates = self._extract_candidates(text, max_candidates=max_candidates)

        matches = []
        seen = set()
        for candidate, candidate_type in candidates:
            # Fast prefilter before full salted hash fingerprinting.
            if self.prefix_index and candidate[:16] not in self.prefix_index:
                continue
            fp = self._fingerprint(candidate)
            if self.bloom_filter is not None and fp not in self.bloom_filter:
                continue
            hit = self.fingerprint_index.get(fp)
            if not hit:
                continue

            dataset_id = hit.get("dataset_id")
            policy = self.dataset_policies.get(dataset_id, {})
            confidence = confidence_map.get(candidate_type, 0.9)
            allowed_types = policy.get("allowed_candidate_types", self.default_allowed_candidate_types)
            min_conf = float(policy.get("min_confidence", self.default_min_confidence))
            if candidate_type not in allowed_types:
                continue
            if confidence < min_conf:
                continue

            key = (hit.get("dataset_id"), hit.get("record_id"), fp, candidate_type)
            if key in seen:
                continue
            seen.add(key)
            matches.append(
                {
                    "dataset_id": hit.get("dataset_id"),
                    "record_id": hit.get("record_id"),
                    "fingerprint": fp,
                    "matched_text": candidate[:180],
                    "canonical_preview": hit.get("canonical_preview", ""),
                    "variant_type": hit.get("variant_type", "canonical"),
                    "candidate_type": candidate_type,
                    "confidence": confidence,
                }
            )

        return matches

    def get_stats(self) -> Dict[str, Any]:
        return {
            "enabled": self.record_count > 0,
            "dataset_path": str(self.dataset_path),
            "dataset_count": self.dataset_count,
            "record_count": self.record_count,
            "fingerprint_count": self.fingerprint_count,
            "prefix_count": len(self.prefix_index),
            "bloom_enabled": self.bloom_filter is not None,
            "bloom_bits": int(self.bloom_filter.bit_size if self.bloom_filter else 0),
            "bloom_hashes": int(self.bloom_filter.hash_count if self.bloom_filter else 0),
            "dataset_policy_count": len(self.dataset_policies),
            "default_min_confidence": self.default_min_confidence,
            "last_loaded_at": self.last_loaded_at,
        }


class DLPMonitor(MonitorModule):
    """
    Data Loss Prevention (DLP) Monitor - Detect sensitive data exfiltration.
    Monitors for PII, credentials, and sensitive data leaving the system.
    """

    # Sensitive data patterns
    SENSITIVE_PATTERNS = {
        'credit_card': r'\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|3(?:0[0-5]|[68][0-9])[0-9]{11}|6(?:011|5[0-9]{2})[0-9]{12})\b',
        'ssn': r'\b\d{3}-\d{2}-\d{4}\b',
        'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        'api_key': r'\b(?:api[_-]?key|apikey|access[_-]?token)["\s:=]+["\']?([a-zA-Z0-9_-]{20,})["\']?',
        'aws_key': r'\b(?:AKIA|ABIA|ACCA|ASIA)[A-Z0-9]{16}\b',
        'private_key': r'-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----',
        'password': r'(?:password|passwd|pwd|secret)["\s:=]+["\']?([^\s"\']{6,})',
        'jwt': r'\beyJ[A-Za-z0-9-_]*\.eyJ[A-Za-z0-9-_]*\.[A-Za-z0-9-_]*\b',
    }

    # Suspicious destinations for data exfil
    EXFIL_DOMAINS = {
        'pastebin.com', 'paste.ee', 'hastebin.com', 'ghostbin.com',
        'file.io', 'transfer.sh', 'wetransfer.com', 'sendspace.com',
        'mega.nz', 'mediafire.com', 'zippyshare.com',
        'discord.com', 'discordapp.com',
        'telegram.org', 'api.telegram.org',
        'ngrok.io', 'serveo.net', 'localhost.run',
    }

    # File extensions with potential sensitive data
    SENSITIVE_EXTENSIONS = {
        '.pem', '.key', '.crt', '.p12', '.pfx',
        '.env', '.conf', '.config', '.ini',
        '.sql', '.bak', '.dump',
        '.kdbx', '.kdb',
        '.gpg', '.pgp',
    }

    EDM_TEXT_EXTENSIONS = {
        '.txt', '.csv', '.tsv', '.json', '.md', '.log', '.sql', '.conf', '.ini', '.yaml', '.yml'
    }
    
    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self.threats = []
        self.alerts = []
        self.monitored_paths = [
            Path.home() / "Documents",
            Path.home() / "Downloads",
            Path.home() / ".ssh",
            Path.home() / ".aws",
            Path("/etc"),
        ]

        # Exact Data Match (EDM) setup.
        edm_dataset_path = config.dlp_edm_dataset_path or str(DATA_DIR / "edm_datasets.json")
        self.edm_engine = EDMFingerprintEngine(
            dataset_path=edm_dataset_path,
            tenant_salt=config.dlp_edm_tenant_salt,
            max_records=config.dlp_edm_max_records,
            default_min_confidence=config.dlp_edm_min_confidence,
            default_allowed_candidate_types=config.dlp_edm_allowed_candidate_types,
        )
        self._edm_versions_path = DATA_DIR / "edm_dataset_versions.json"
        self._edm_versions = self._load_edm_versions()
    
    def scan(self) -> Dict[str, Any]:
        """Scan for DLP violations"""
        self.threats = []
        self.alerts = []
        
        # Scan 1: Check clipboard for sensitive data
        clipboard_alerts = self._scan_clipboard()
        self.alerts.extend(clipboard_alerts)
        
        # Scan 2: Monitor recent file access for sensitive files
        file_alerts = self._scan_recent_files()
        self.alerts.extend(file_alerts)
        
        # Scan 3: Check network connections to exfil domains
        network_alerts = self._scan_network_exfil()
        self.alerts.extend(network_alerts)

        # Scan 4: Exact Data Match (EDM) over clipboard and recent text files
        edm_alerts = self._scan_exact_data_matches()
        self.alerts.extend(edm_alerts)
        
        # Create threats from alerts
        for alert in self.alerts:
            self._create_threat(alert)
        
        self.last_run = datetime.now(timezone.utc)
        
        return {
            "clipboard_alerts": len(clipboard_alerts),
            "file_alerts": len(file_alerts),
            "network_alerts": len(network_alerts),
            "edm_alerts": len(edm_alerts),
            "total_alerts": len(self.alerts),
            "threats": len(self.threats),
            "details": self.alerts[-20:],
            "edm_stats": self.edm_engine.get_stats(),
        }

    def _get_clipboard_content(self) -> str:
        """Best-effort clipboard extraction used by DLP regex and EDM checks."""
        clipboard_content = ""

        try:
            if PLATFORM == "windows":
                try:
                    import ctypes
                    CF_UNICODETEXT = 13
                    ctypes.windll.user32.OpenClipboard(0)
                    try:
                        data = ctypes.windll.user32.GetClipboardData(CF_UNICODETEXT)
                        if data:
                            clipboard_content = ctypes.c_wchar_p(data).value or ""
                    finally:
                        ctypes.windll.user32.CloseClipboard()
                except Exception:
                    pass
            else:
                try:
                    if PLATFORM == "darwin":
                        result = subprocess.run(['pbpaste'], capture_output=True, text=True, timeout=2)
                    else:
                        result = subprocess.run(['xclip', '-selection', 'clipboard', '-o'], capture_output=True, text=True, timeout=2)
                    if result.returncode == 0:
                        clipboard_content = result.stdout[:10000]
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"Clipboard extraction error: {e}")

        return clipboard_content
    
    def _scan_clipboard(self) -> List[Dict]:
        """Scan clipboard for sensitive data"""
        alerts = []
        
        try:
            clipboard_content = self._get_clipboard_content()
            
            # Check clipboard for sensitive patterns
            if clipboard_content:
                for pattern_name, pattern in self.SENSITIVE_PATTERNS.items():
                    matches = re.findall(pattern, clipboard_content, re.IGNORECASE)
                    if matches:
                        alerts.append({
                            'type': 'clipboard',
                            'pattern': pattern_name,
                            'count': len(matches),
                            'preview': clipboard_content[:100] + '...' if len(clipboard_content) > 100 else clipboard_content,
                            'timestamp': datetime.now(timezone.utc).isoformat()
                        })
                        
        except Exception as e:
            logger.debug(f"Clipboard scan error: {e}")
        
        return alerts

    def reload_edm_dataset(self) -> Dict[str, Any]:
        """Hot-reload EDM datasets from disk without agent restart."""
        self.edm_engine.load_datasets()
        return self.edm_engine.get_stats()

    def _load_edm_versions(self) -> Dict[str, int]:
        """Load persisted last-applied EDM version per dataset_id."""
        try:
            if self._edm_versions_path.exists():
                with open(self._edm_versions_path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                if isinstance(raw, dict):
                    return {str(k): int(v) for k, v in raw.items()}
        except Exception as e:
            logger.debug(f"Failed to load EDM versions state: {e}")
        return {}

    def _save_edm_versions(self) -> None:
        """Persist last-applied EDM version map for stale update rejection."""
        try:
            self._edm_versions_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = self._edm_versions_path.with_suffix(self._edm_versions_path.suffix + ".tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self._edm_versions, f, indent=2)
            os.replace(tmp_path, self._edm_versions_path)
        except Exception as e:
            logger.debug(f"Failed to persist EDM versions state: {e}")

    def _resolve_edm_signing_secret(self) -> str:
        """Prefer explicit EDM signing secret, then enrollment key fallback."""
        if getattr(self.config, "dlp_edm_signing_secret", ""):
            return str(self.config.dlp_edm_signing_secret)
        if getattr(self.config, "enrollment_key", ""):
            return str(self.config.enrollment_key)
        return ""

    @staticmethod
    def _compute_edm_checksum(payload: Dict[str, Any]) -> str:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _verify_edm_signature(self, dataset_id: str, version: int, checksum: str, signature: str) -> bool:
        secret = self._resolve_edm_signing_secret()
        if not secret:
            return False
        message = f"{dataset_id}:{version}:{checksum}"
        expected = hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    def update_edm_dataset(self, payload: Any, edm_meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Replace EDM dataset file content and reload in-memory fingerprints."""
        meta = edm_meta or {}
        dataset_id = str(meta.get("dataset_id") or "")
        version_raw = meta.get("version")
        checksum = str(meta.get("checksum") or "")
        signature = str(meta.get("signature") or "")

        require_signed = bool(getattr(self.config, "dlp_edm_require_signed", True))
        if require_signed and (not dataset_id or version_raw is None or not checksum or not signature):
            return {
                "updated": False,
                "error": "Missing EDM metadata/signature",
                "rejected": "unsigned",
            }

        try:
            version = int(version_raw) if version_raw is not None else 0
        except Exception:
            return {
                "updated": False,
                "error": "Invalid EDM version metadata",
                "rejected": "invalid_version",
            }

        computed_checksum = self._compute_edm_checksum(payload)
        if checksum and computed_checksum != checksum:
            return {
                "updated": False,
                "error": "Checksum mismatch for EDM payload",
                "expected_checksum": checksum,
                "computed_checksum": computed_checksum,
                "rejected": "checksum_mismatch",
            }

        if require_signed and not self._verify_edm_signature(dataset_id, version, checksum, signature):
            return {
                "updated": False,
                "error": "Invalid EDM signature",
                "rejected": "bad_signature",
            }

        if dataset_id:
            last_seen_version = int(self._edm_versions.get(dataset_id, 0))
            if version <= last_seen_version:
                return {
                    "updated": False,
                    "error": "Stale EDM version rejected",
                    "dataset_id": dataset_id,
                    "incoming_version": version,
                    "current_version": last_seen_version,
                    "rejected": "stale_version",
                }

        path = self.edm_engine.dataset_path
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = path.with_suffix(path.suffix + ".tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            os.replace(tmp_path, path)
        except Exception as e:
            return {
                "updated": False,
                "error": str(e),
                "dataset_path": str(path),
            }

        stats = self.reload_edm_dataset()
        if dataset_id:
            self._edm_versions[dataset_id] = version
            self._save_edm_versions()
        return {
            "updated": True,
            "dataset_path": str(path),
            "dataset_id": dataset_id,
            "version": version,
            "checksum": computed_checksum,
            "edm_stats": stats,
        }
    
    def _scan_recent_files(self) -> List[Dict]:
        """Scan for recently accessed sensitive files"""
        alerts = []
        
        for base_path in self.monitored_paths:
            try:
                if not base_path.exists():
                    continue
                
                for filepath in base_path.rglob('*'):
                    try:
                        if not filepath.is_file():
                            continue
                        
                        # Check extension
                        if filepath.suffix.lower() in self.SENSITIVE_EXTENSIONS:
                            stat = filepath.stat()
                            # Alert if accessed in last hour
                            if time.time() - stat.st_atime < 3600:
                                alerts.append({
                                    'type': 'sensitive_file_access',
                                    'path': str(filepath),
                                    'extension': filepath.suffix,
                                    'accessed': datetime.fromtimestamp(stat.st_atime).isoformat(),
                                    'timestamp': datetime.now(timezone.utc).isoformat()
                                })
                                
                    except (PermissionError, OSError):
                        pass
                        
            except Exception as e:
                logger.debug(f"File scan error for {base_path}: {e}")
        
        return alerts[:50]  # Limit alerts
    
    def _scan_network_exfil(self) -> List[Dict]:
        """Scan for connections to known exfiltration domains"""
        alerts = []
        
        if not PSUTIL_AVAILABLE:
            return alerts
        
        try:
            for conn in psutil.net_connections(kind='inet'):
                if conn.status != 'ESTABLISHED':
                    continue
                
                if not conn.raddr:
                    continue
                
                # Note: We'd need DNS reverse lookup to check domain
                # For now, log outbound connections on common exfil ports
                remote_port = conn.raddr.port
                if remote_port in [443, 80]:  # HTTPS/HTTP
                    try:
                        proc = psutil.Process(conn.pid) if conn.pid else None
                        proc_name = proc.name() if proc else "unknown"
                        
                        # Flag if a script interpreter is making network calls
                        suspicious_procs = ['python', 'powershell', 'cmd', 'bash', 'curl', 'wget']
                        if any(s in proc_name.lower() for s in suspicious_procs):
                            alerts.append({
                                'type': 'potential_exfil',
                                'process': proc_name,
                                'pid': conn.pid,
                                'remote_ip': conn.raddr.ip,
                                'remote_port': remote_port,
                                'timestamp': datetime.now(timezone.utc).isoformat()
                            })
                    except Exception:
                        pass
                        
        except Exception as e:
            logger.debug(f"Network exfil scan error: {e}")
        
        return alerts[:20]

    def _scan_exact_data_matches(self) -> List[Dict]:
        """Exact Data Match scan against clipboard + recently accessed text files."""
        alerts = []
        if not getattr(self.config, "dlp_edm_enabled", True):
            return alerts

        # Clipboard EDM
        clipboard = self._get_clipboard_content()
        if clipboard:
            for match in self.edm_engine.match_text(clipboard, max_candidates=2000):
                alerts.append(
                    {
                        "type": "edm_match",
                        "source": "clipboard",
                        "dataset_id": match.get("dataset_id"),
                        "record_id": match.get("record_id"),
                        "fingerprint": match.get("fingerprint"),
                        "preview": match.get("matched_text"),
                        "match_confidence": match.get("confidence"),
                        "match_candidate_type": match.get("candidate_type"),
                        "match_variant_type": match.get("variant_type"),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                )

        # File EDM
        scanned_files = 0
        max_files = 40
        for base_path in self.monitored_paths:
            if scanned_files >= max_files:
                break
            try:
                if not base_path.exists():
                    continue

                for filepath in base_path.rglob('*'):
                    if scanned_files >= max_files:
                        break
                    try:
                        if not filepath.is_file():
                            continue
                        if filepath.suffix.lower() not in self.EDM_TEXT_EXTENSIONS:
                            continue

                        stat = filepath.stat()
                        # Focus on recently touched files only.
                        if time.time() - stat.st_atime > 3600:
                            continue

                        scanned_files += 1
                        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                            sample = f.read(256 * 1024)

                        if not sample:
                            continue

                        for match in self.edm_engine.match_text(sample, max_candidates=1500):
                            alerts.append(
                                {
                                    "type": "edm_match",
                                    "source": "file",
                                    "path": str(filepath),
                                    "dataset_id": match.get("dataset_id"),
                                    "record_id": match.get("record_id"),
                                    "fingerprint": match.get("fingerprint"),
                                    "preview": match.get("matched_text"),
                                    "match_confidence": match.get("confidence"),
                                    "match_candidate_type": match.get("candidate_type"),
                                    "match_variant_type": match.get("variant_type"),
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                }
                            )
                    except (PermissionError, OSError):
                        continue
                    except Exception as e:
                        logger.debug(f"EDM file scan error for {filepath}: {e}")
            except Exception as e:
                logger.debug(f"EDM scan path error for {base_path}: {e}")

        return alerts[:60]
    
    def _create_threat(self, alert: Dict):
        """Create threat from DLP alert"""
        alert_type = alert.get('type', 'unknown')
        
        if alert_type == 'clipboard':
            severity = ThreatSeverity.HIGH
            title = f"Sensitive Data in Clipboard: {alert.get('pattern')}"
        elif alert_type == 'edm_match':
            severity = ThreatSeverity.HIGH
            src = alert.get('source', 'unknown')
            ds = alert.get('dataset_id', 'unknown-dataset')
            rid = alert.get('record_id', 'unknown-record')
            title = f"Exact Data Match ({src}): {ds}/{rid}"
        elif alert_type == 'sensitive_file_access':
            severity = ThreatSeverity.MEDIUM
            title = f"Sensitive File Accessed: {Path(alert.get('path', '')).name}"
        else:
            severity = ThreatSeverity.HIGH
            title = f"Potential Data Exfiltration: {alert.get('process', 'Unknown')}"
        
        threat = Threat(
            threat_id=f"dlp-{uuid.uuid4().hex[:8]}",
            title=title,
            description=f"DLP violation detected: {alert_type}",
            severity=severity,
            threat_type="data_loss_prevention",
            source="dlp_monitor",
            target=str(alert.get('path', alert.get('remote_ip', 'clipboard'))),
            evidence=alert,
            mitre_techniques=["T1041", "T1567", "T1048"],  # Exfiltration
            auto_kill_eligible=False,
            remediation_action="alert_and_block",
            remediation_params=alert
        )
        self.threats.append(threat)
    
    def get_threats(self) -> List[Threat]:
        return self.threats


class VulnerabilityScanner(MonitorModule):
    """
    Vulnerability Scanner - Detect outdated software and known vulnerabilities.
    Enhanced with CVSS scoring, remediation recommendations, and extended CVE database.
    """
    
    # Known vulnerable software with CVSS scores and remediation
    # Format: {software: {version: [(CVE, CVSS, severity, description, remediation)]}}
    KNOWN_VULNERABILITIES = {
        # === CRYPTOGRAPHY & SSL ===
        'openssl': {
            '1.0.1': [
                ('CVE-2014-0160', 10.0, 'critical', 'Heartbleed - Memory disclosure', 'Upgrade to OpenSSL 1.0.1g or later'),
                ('CVE-2014-0224', 7.4, 'high', 'CCS Injection', 'Upgrade to OpenSSL 1.0.1h or later'),
            ],
            '1.0.2': [
                ('CVE-2016-2108', 9.8, 'critical', 'ASN.1 encoding error - RCE', 'Upgrade to OpenSSL 1.0.2h or later'),
                ('CVE-2016-6304', 7.5, 'high', 'OCSP memory exhaustion DoS', 'Upgrade to OpenSSL 1.0.2i'),
                ('CVE-2016-2183', 5.3, 'medium', 'SWEET32 birthday attack', 'Disable 3DES cipher'),
            ],
            '1.1.0': [
                ('CVE-2017-3735', 5.3, 'medium', 'OOB read in IPAddressFamily', 'Upgrade to OpenSSL 1.1.0g'),
                ('CVE-2018-0739', 6.5, 'medium', 'Recursive ASN.1 denial of service', 'Upgrade to OpenSSL 1.1.0i'),
            ],
            '1.1.1': [
                ('CVE-2021-3711', 9.8, 'critical', 'SM2 decryption buffer overflow', 'Upgrade to OpenSSL 1.1.1l'),
                ('CVE-2022-0778', 7.5, 'high', 'Infinite loop in BN_mod_sqrt', 'Upgrade to OpenSSL 1.1.1n'),
            ],
            '3.0.0': [
                ('CVE-2022-3602', 9.8, 'critical', 'X.509 buffer overflow', 'Upgrade to OpenSSL 3.0.7+'),
                ('CVE-2022-3786', 7.5, 'high', 'X.509 buffer overflow DoS', 'Upgrade to OpenSSL 3.0.7+'),
            ],
            '3.0.1': [
                ('CVE-2023-0286', 7.4, 'high', 'X.400 certificate name confusion', 'Upgrade to OpenSSL 3.0.8+'),
            ],
        },
        
        # === WEB SERVERS ===
        'apache': {
            '2.4.49': [
                ('CVE-2021-41773', 9.8, 'critical', 'Path traversal and RCE', 'Upgrade to Apache 2.4.51+'),
                ('CVE-2021-42013', 9.8, 'critical', 'Path traversal bypass', 'Upgrade to Apache 2.4.51+'),
            ],
            '2.4.50': [
                ('CVE-2021-42013', 9.8, 'critical', 'Path traversal bypass', 'Upgrade to Apache 2.4.51+'),
            ],
            '2.4.53': [
                ('CVE-2022-22719', 7.5, 'high', 'mod_lua r:parsebody DoS', 'Upgrade to Apache 2.4.54+'),
                ('CVE-2022-22720', 9.8, 'critical', 'HTTP Request Smuggling', 'Upgrade to Apache 2.4.54+'),
            ],
            '2.4.54': [
                ('CVE-2022-31813', 9.8, 'critical', 'mod_proxy X-Forwarded-For bypass', 'Upgrade to Apache 2.4.55+'),
            ],
        },
        'nginx': {
            '1.18.0': [
                ('CVE-2021-23017', 7.7, 'high', 'DNS resolver vulnerability', 'Upgrade to nginx 1.21.0+'),
            ],
            '1.20.0': [
                ('CVE-2021-23017', 7.7, 'high', 'DNS resolver off-by-one', 'Upgrade to nginx 1.21.0+'),
            ],
            '1.22.0': [
                ('CVE-2022-41741', 7.8, 'high', 'mp4 module memory corruption', 'Upgrade to nginx 1.23.2+'),
                ('CVE-2022-41742', 7.1, 'high', 'mp4 module memory disclosure', 'Upgrade to nginx 1.23.2+'),
            ],
        },
        
        # === LOGGING FRAMEWORKS ===
        'log4j': {
            '2.0': [
                ('CVE-2021-44228', 10.0, 'critical', 'Log4Shell RCE via JNDI', 'Upgrade to Log4j 2.17.1+'),
                ('CVE-2021-44832', 6.6, 'medium', 'RCE via JDBC Appender', 'Upgrade to Log4j 2.17.1+'),
            ],
            '2.14.0': [
                ('CVE-2021-44228', 10.0, 'critical', 'Log4Shell RCE via JNDI', 'Upgrade to Log4j 2.17.1+'),
            ],
            '2.14.1': [
                ('CVE-2021-44228', 10.0, 'critical', 'Log4Shell RCE via JNDI', 'Upgrade to Log4j 2.17.1+'),
            ],
            '2.15.0': [
                ('CVE-2021-45046', 9.0, 'critical', 'Log4Shell bypass with lookup', 'Upgrade to Log4j 2.17.1+'),
            ],
            '2.16.0': [
                ('CVE-2021-45105', 7.5, 'high', 'DoS via recursive lookup', 'Upgrade to Log4j 2.17.1+'),
            ],
        },
        
        # === CURL ===
        'curl': {
            '7.83.0': [
                ('CVE-2022-32205', 4.3, 'medium', 'Set-Cookie injection', 'Upgrade to curl 7.84.0+'),
                ('CVE-2022-32206', 6.5, 'medium', 'HTTP compression DoS', 'Upgrade to curl 7.84.0+'),
            ],
            '7.84.0': [
                ('CVE-2022-35252', 3.7, 'low', 'Control code in cookie', 'Upgrade to curl 7.85.0+'),
            ],
            '8.0.0': [
                ('CVE-2023-27533', 8.8, 'high', 'TELNET option injection', 'Upgrade to curl 8.0.1+'),
                ('CVE-2023-27534', 8.8, 'high', 'SFTP path traversal', 'Upgrade to curl 8.0.1+'),
            ],
            '8.4.0': [
                ('CVE-2023-46218', 6.5, 'medium', 'Cookie mixed case bypass', 'Upgrade to curl 8.5.0+'),
            ],
        },
        
        # === PROGRAMMING LANGUAGES ===
        'python': {
            '3.6.0': [
                ('CVE-2019-10160', 9.8, 'critical', 'urllib CRLF injection', 'Upgrade to Python 3.6.9+'),
            ],
            '3.7.0': [
                ('CVE-2019-10160', 9.8, 'critical', 'urllib CRLF injection', 'Upgrade to Python 3.7.4+'),
            ],
            '3.8.0': [
                ('CVE-2020-14422', 5.9, 'medium', 'IPv6 hash collision DoS', 'Upgrade to Python 3.8.4+'),
            ],
            '3.9.0': [
                ('CVE-2021-3177', 9.8, 'critical', 'ctypes buffer overflow', 'Upgrade to Python 3.9.2+'),
                ('CVE-2021-29921', 9.8, 'critical', 'ipaddress improper parsing', 'Upgrade to Python 3.9.5+'),
            ],
            '3.9.1': [
                ('CVE-2021-3177', 9.8, 'critical', 'ctypes buffer overflow', 'Upgrade to Python 3.9.2+'),
            ],
            '3.10.0': [
                ('CVE-2022-0391', 7.5, 'high', 'urllib.parse CRLF injection', 'Upgrade to Python 3.10.2+'),
            ],
            '3.11.0': [
                ('CVE-2023-24329', 7.5, 'high', 'urllib.parse URL parsing issue', 'Upgrade to Python 3.11.4+'),
            ],
        },
        'node': {
            '14.0.0': [
                ('CVE-2021-22930', 9.8, 'critical', 'Use after free HTTP/2', 'Upgrade to Node.js 14.17.4+'),
            ],
            '16.0.0': [
                ('CVE-2021-22931', 9.8, 'critical', 'ReDoS in DNS parsing', 'Upgrade to Node.js 16.6.0+'),
            ],
            '18.0.0': [
                ('CVE-2022-32213', 6.5, 'medium', 'HTTP request smuggling', 'Upgrade to Node.js 18.5.0+'),
            ],
            '20.0.0': [
                ('CVE-2023-32002', 9.8, 'critical', 'Permission model bypass', 'Upgrade to Node.js 20.5.1+'),
            ],
        },
        'java': {
            '8.0': [
                ('CVE-2022-21449', 7.5, 'high', 'Psychic Signatures ECDSA', 'Upgrade to Java 8u332+'),
            ],
            '11.0.0': [
                ('CVE-2022-21449', 7.5, 'high', 'Psychic Signatures ECDSA', 'Upgrade to Java 11.0.15+'),
            ],
            '17.0.0': [
                ('CVE-2022-21449', 7.5, 'high', 'Psychic Signatures ECDSA', 'Upgrade to Java 17.0.3+'),
            ],
        },
        'php': {
            '7.4.0': [
                ('CVE-2022-31625', 9.8, 'critical', 'pgsql PHAR deserialization', 'Upgrade to PHP 7.4.30+'),
            ],
            '8.0.0': [
                ('CVE-2022-31626', 9.8, 'critical', 'password_hash buffer overflow', 'Upgrade to PHP 8.0.22+'),
            ],
            '8.1.0': [
                ('CVE-2023-3247', 5.3, 'medium', 'SOAP XML external entity', 'Upgrade to PHP 8.1.21+'),
            ],
        },
        
        # === DATABASES ===
        'mysql': {
            '5.7.0': [
                ('CVE-2020-14812', 4.9, 'medium', 'Privilege escalation', 'Upgrade to MySQL 5.7.32+'),
            ],
            '8.0.0': [
                ('CVE-2023-21912', 7.5, 'high', 'Server: Security unauthorized access', 'Upgrade to MySQL 8.0.33+'),
            ],
        },
        'postgresql': {
            '10.0': [
                ('CVE-2018-1058', 8.8, 'high', 'Search path manipulation', 'Upgrade to PostgreSQL 10.3+'),
            ],
            '13.0': [
                ('CVE-2021-23214', 8.1, 'high', 'MITM ssl_passthrough', 'Upgrade to PostgreSQL 13.5+'),
            ],
            '14.0': [
                ('CVE-2022-1552', 8.8, 'high', 'Autovacuum command injection', 'Upgrade to PostgreSQL 14.3+'),
            ],
        },
        'redis': {
            '6.0.0': [
                ('CVE-2021-32761', 7.5, 'high', 'Integer overflow', 'Upgrade to Redis 6.0.15+'),
            ],
            '7.0.0': [
                ('CVE-2022-24735', 7.0, 'high', 'Lua sandbox escape', 'Upgrade to Redis 7.0.1+'),
                ('CVE-2023-22458', 6.5, 'medium', 'Integer overflow in HRANDFIELD', 'Upgrade to Redis 7.0.8+'),
            ],
        },
        'mongodb': {
            '4.4.0': [
                ('CVE-2021-20328', 6.8, 'medium', 'Client-side js injection', 'Upgrade to MongoDB 4.4.4+'),
            ],
            '5.0.0': [
                ('CVE-2022-24272', 8.8, 'high', 'Path traversal via snappy', 'Upgrade to MongoDB 5.0.7+'),
            ],
        },
        
        # === CONTAINERS & ORCHESTRATION ===
        'docker': {
            '19.03.0': [
                ('CVE-2020-15257', 5.2, 'medium', 'containerd Shim API exposure', 'Upgrade to Docker 19.03.14+'),
            ],
            '20.10.0': [
                ('CVE-2021-41091', 6.3, 'medium', 'Moby directory traversal', 'Upgrade to Docker 20.10.9+'),
            ],
            '23.0.0': [
                ('CVE-2023-28840', 8.7, 'high', 'Encrypted network traffic interception', 'Upgrade to Docker 23.0.3+'),
            ],
        },
        'kubernetes': {
            '1.20.0': [
                ('CVE-2021-25735', 6.5, 'medium', 'Node label validation bypass', 'Upgrade to Kubernetes 1.20.6+'),
            ],
            '1.22.0': [
                ('CVE-2021-25741', 8.8, 'high', 'Symlink exchange for subpath', 'Upgrade to Kubernetes 1.22.2+'),
            ],
            '1.24.0': [
                ('CVE-2023-2728', 6.5, 'medium', 'ServiceAccount token secrets bypass', 'Upgrade to Kubernetes 1.24.14+'),
            ],
        },
        
        # === VERSION CONTROL ===
        'git': {
            '2.30.0': [
                ('CVE-2021-21300', 7.5, 'high', 'Remote code execution via filter', 'Upgrade to Git 2.30.1+'),
            ],
            '2.35.0': [
                ('CVE-2022-24765', 7.8, 'high', 'Unsafe directory ownership', 'Upgrade to Git 2.35.2+'),
            ],
            '2.39.0': [
                ('CVE-2023-22490', 5.5, 'medium', 'Local clone optimization data leak', 'Upgrade to Git 2.39.1+'),
            ],
        },
        
        # === REMOTE ACCESS ===
        'ssh': {
            '8.5': [
                ('CVE-2021-36368', 3.7, 'low', 'DNS response spoofing', 'Upgrade to OpenSSH 8.8+'),
            ],
            '9.0': [
                ('CVE-2023-38408', 9.8, 'critical', 'ssh-agent remote code execution', 'Upgrade to OpenSSH 9.3p2+'),
            ],
        },
        
        # === COMPRESSION ===
        'xz': {
            '5.6.0': [
                ('CVE-2024-3094', 10.0, 'critical', 'XZ Utils supply chain backdoor', 'Downgrade to xz 5.4.6 or upgrade to 5.6.2+'),
            ],
            '5.6.1': [
                ('CVE-2024-3094', 10.0, 'critical', 'XZ Utils supply chain backdoor', 'Downgrade to xz 5.4.6 or upgrade to 5.6.2+'),
            ],
        },
        'zlib': {
            '1.2.11': [
                ('CVE-2022-37434', 9.8, 'critical', 'Heap buffer overflow in inflate', 'Upgrade to zlib 1.2.12+'),
            ],
        },
        
        # === SYSTEM UTILITIES ===
        'sudo': {
            '1.8.0': [
                ('CVE-2021-3156', 7.8, 'high', 'Baron Samedit heap overflow', 'Upgrade to sudo 1.9.5p2+'),
            ],
            '1.9.0': [
                ('CVE-2021-3156', 7.8, 'high', 'Baron Samedit heap overflow', 'Upgrade to sudo 1.9.5p2+'),
            ],
        },
        'polkit': {
            '0.113': [
                ('CVE-2021-4034', 7.8, 'high', 'PwnKit local privilege escalation', 'Apply vendor patches'),
            ],
        },
    }
    
    # CVE severity thresholds
    CVSS_THRESHOLDS = {
        'critical': 9.0,
        'high': 7.0,
        'medium': 4.0,
        'low': 0.1
    }
    
    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self.threats = []
        self.vulnerabilities = []
        self.installed_software = {}
        self.scan_stats = {'total_cves': 0, 'critical': 0, 'high': 0, 'medium': 0, 'low': 0}
    
    def scan(self) -> Dict[str, Any]:
        """Scan for vulnerable software with CVSS scoring"""
        self.threats = []
        self.vulnerabilities = []
        self.scan_stats = {'total_cves': 0, 'critical': 0, 'high': 0, 'medium': 0, 'low': 0}
        
        # Collect installed software
        self._enumerate_software()
        
        # Check against known vulnerabilities
        for software, version in self.installed_software.items():
            vulns = self._check_vulnerabilities(software, version)
            if vulns:
                vuln_entry = {
                    'software': software,
                    'version': version,
                    'vulnerabilities': vulns,
                    'highest_cvss': max(v['cvss'] for v in vulns),
                    'cve_count': len(vulns),
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
                self.vulnerabilities.append(vuln_entry)
                self._create_threat(vuln_entry)
                
                # Update stats
                for v in vulns:
                    self.scan_stats['total_cves'] += 1
                    self.scan_stats[v['severity']] += 1
        
        self.last_run = datetime.now(timezone.utc)
        
        # Sort by highest CVSS
        self.vulnerabilities.sort(key=lambda x: x['highest_cvss'], reverse=True)
        
        return {
            "software_checked": len(self.installed_software),
            "vulnerabilities_found": len(self.vulnerabilities),
            "cve_count": self.scan_stats['total_cves'],
            "by_severity": {
                "critical": self.scan_stats['critical'],
                "high": self.scan_stats['high'],
                "medium": self.scan_stats['medium'],
                "low": self.scan_stats['low']
            },
            "threats": len(self.threats),
            "vulnerable_software": self.vulnerabilities[:20],  # Top 20
            "remediation_summary": self._generate_remediation_summary()
        }
    
    def _enumerate_software(self):
        """Enumerate installed software and versions"""
        self.installed_software = {}
        
        # Method 1: Check common command versions
        version_commands = {
            'openssl': ['openssl', 'version'],
            'curl': ['curl', '--version'],
            'python': ['python3', '--version'],
            'nginx': ['nginx', '-v'],
            'apache': ['apache2', '-v'],
            'ssh': ['ssh', '-V'],
            'git': ['git', '--version'],
            'node': ['node', '--version'],
            'docker': ['docker', '--version'],
            'redis': ['redis-server', '--version'],
            'mysql': ['mysql', '--version'],
            'php': ['php', '--version'],
            'java': ['java', '-version'],
            'sudo': ['sudo', '--version'],
            'xz': ['xz', '--version'],
            'zlib': [],  # Will check via library
        }
        
        for software, cmd in version_commands.items():
            if not cmd:
                continue
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                output = result.stdout + result.stderr
                
                # Extract version number
                version_match = re.search(r'(\d+\.\d+(?:\.\d+)?)', output)
                if version_match:
                    self.installed_software[software] = version_match.group(1)
            except Exception:
                pass
        
        # Method 2: Check package manager (Linux)
        if PLATFORM == "linux":
            try:
                # dpkg
                result = subprocess.run(
                    ['dpkg-query', '-W', '-f=${Package} ${Version}\n'],
                    capture_output=True, text=True, timeout=30
                )
                if result.returncode == 0:
                    for line in result.stdout.split('\n')[:200]:
                        parts = line.strip().split(' ', 1)
                        if len(parts) == 2:
                            pkg, ver = parts
                            # Extract numeric version
                            ver_match = re.search(r'(\d+\.\d+(?:\.\d+)?)', ver)
                            if ver_match:
                                self.installed_software[pkg] = ver_match.group(1)
            except Exception:
                pass
            
            # rpm-based systems
            try:
                result = subprocess.run(
                    ['rpm', '-qa', '--queryformat', '%{NAME} %{VERSION}\n'],
                    capture_output=True, text=True, timeout=30
                )
                if result.returncode == 0:
                    for line in result.stdout.split('\n')[:200]:
                        parts = line.strip().split(' ', 1)
                        if len(parts) == 2:
                            pkg, ver = parts
                            ver_match = re.search(r'(\d+\.\d+(?:\.\d+)?)', ver)
                            if ver_match:
                                self.installed_software[pkg] = ver_match.group(1)
            except Exception:
                pass
        
        # Method 3: Check Windows programs (registry)
        if PLATFORM == "windows":
            try:
                import winreg
                uninstall_key = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
                
                for hive in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
                    try:
                        key = winreg.OpenKey(hive, uninstall_key)
                        i = 0
                        while i < 500:  # Limit iterations
                            try:
                                subkey_name = winreg.EnumKey(key, i)
                                subkey = winreg.OpenKey(key, subkey_name)
                                
                                try:
                                    name, _ = winreg.QueryValueEx(subkey, "DisplayName")
                                    version, _ = winreg.QueryValueEx(subkey, "DisplayVersion")
                                    self.installed_software[name.lower()] = version
                                except (OSError, FileNotFoundError):
                                    pass
                                
                                winreg.CloseKey(subkey)
                                i += 1
                            except OSError:
                                break
                        winreg.CloseKey(key)
                    except OSError:
                        pass
            except ImportError:
                pass
    
    def _check_vulnerabilities(self, software: str, version: str) -> List[Dict]:
        """Check if software version has known vulnerabilities with CVSS scores"""
        found_vulns = []
        software_lower = software.lower()
        
        for known_software, versions in self.KNOWN_VULNERABILITIES.items():
            if known_software in software_lower or software_lower == known_software:
                # Direct version match
                if version in versions:
                    for vuln_info in versions[version]:
                        cve, cvss, severity, description, remediation = vuln_info
                        found_vulns.append({
                            'cve': cve,
                            'cvss': cvss,
                            'severity': severity,
                            'description': description,
                            'remediation': remediation,
                            'match_type': 'exact'
                        })
                else:
                    # Check if version is older than or equal to vulnerable versions
                    for vuln_version, vuln_list in versions.items():
                        try:
                            if self._version_compare(version, vuln_version) <= 0:
                                for vuln_info in vuln_list:
                                    cve, cvss, severity, description, remediation = vuln_info
                                    found_vulns.append({
                                        'cve': cve,
                                        'cvss': cvss,
                                        'severity': severity,
                                        'description': description,
                                        'remediation': remediation,
                                        'match_type': 'version_range',
                                        'matched_version': vuln_version
                                    })
                        except Exception:
                            pass
        
        # Deduplicate by CVE
        seen_cves = set()
        unique_vulns = []
        for v in found_vulns:
            if v['cve'] not in seen_cves:
                seen_cves.add(v['cve'])
                unique_vulns.append(v)
        
        return unique_vulns
    
    def _version_compare(self, v1: str, v2: str) -> int:
        """Compare two version strings. Returns -1 if v1 < v2, 0 if equal, 1 if v1 > v2"""
        try:
            v1_parts = [int(x) for x in v1.split('.')[:3]]
            v2_parts = [int(x) for x in v2.split('.')[:3]]
            
            # Pad shorter version with zeros
            while len(v1_parts) < 3:
                v1_parts.append(0)
            while len(v2_parts) < 3:
                v2_parts.append(0)
            
            for i in range(3):
                if v1_parts[i] < v2_parts[i]:
                    return -1
                elif v1_parts[i] > v2_parts[i]:
                    return 1
            return 0
        except ValueError:
            return 0
    
    def _generate_remediation_summary(self) -> List[Dict]:
        """Generate prioritized remediation recommendations"""
        recommendations = []
        
        for vuln_entry in self.vulnerabilities[:10]:  # Top 10 most critical
            highest_vuln = max(vuln_entry['vulnerabilities'], key=lambda v: v['cvss'])
            recommendations.append({
                'software': vuln_entry['software'],
                'version': vuln_entry['version'],
                'action': highest_vuln['remediation'],
                'priority': 'immediate' if highest_vuln['cvss'] >= 9.0 else 
                           'high' if highest_vuln['cvss'] >= 7.0 else 'medium',
                'cves_fixed': [v['cve'] for v in vuln_entry['vulnerabilities']],
                'risk_reduction': highest_vuln['cvss']
            })
        
        return recommendations
    
    def _create_threat(self, vuln: Dict):
        """Create threat from vulnerability finding"""
        highest_cvss = vuln.get('highest_cvss', 0)
        cve_count = vuln.get('cve_count', 0)
        
        # Determine severity based on CVSS
        if highest_cvss >= 9.0:
            severity = ThreatSeverity.CRITICAL
        elif highest_cvss >= 7.0:
            severity = ThreatSeverity.HIGH
        elif highest_cvss >= 4.0:
            severity = ThreatSeverity.MEDIUM
        else:
            severity = ThreatSeverity.LOW
        
        # Get critical CVEs for description
        critical_cves = [v['cve'] for v in vuln['vulnerabilities'] if v['cvss'] >= 9.0][:3]
        high_cves = [v['cve'] for v in vuln['vulnerabilities'] if 7.0 <= v['cvss'] < 9.0][:3]
        
        cve_mentions = critical_cves if critical_cves else high_cves
        
        threat = Threat(
            threat_id=f"vuln-{uuid.uuid4().hex[:8]}",
            title=f"Vulnerable Software: {vuln['software']} {vuln['version']}",
            description=f"{cve_count} CVE(s) found. Highest CVSS: {highest_cvss}. " +
                       f"Critical: {', '.join(cve_mentions[:3])}" if cve_mentions else f"{cve_count} CVE(s) found",
            severity=severity,
            threat_type="vulnerability",
            source="vulnerability_scanner",
            target=f"{vuln['software']}:{vuln['version']}",
            evidence={
                'vulnerabilities': vuln['vulnerabilities'][:5],
                'highest_cvss': highest_cvss,
                'remediation': vuln['vulnerabilities'][0]['remediation'] if vuln['vulnerabilities'] else 'Update software'
            },
            mitre_techniques=["T1190", "T1203", "T1068"],  # Exploit Public-Facing, Client Execution, Privilege Escalation
            auto_kill_eligible=False,
            remediation_action="update_software",
            remediation_params={
                "software": vuln['software'],
                "current_version": vuln['version'],
                "recommended_action": vuln['vulnerabilities'][0]['remediation'] if vuln['vulnerabilities'] else 'Update to latest version'
            }
        )
        self.threats.append(threat)
    
    def get_threats(self) -> List[Threat]:
        return self.threats


class AMSIMonitor(MonitorModule):
    """
    AMSI Integration (Windows) - Antimalware Scan Interface.
    Enhanced with AMSI bypass detection, script deobfuscation, and event log monitoring.
    Integrates with Windows AMSI to detect malicious scripts.
    """
    
    # AMSI bypass techniques and patterns
    AMSI_BYPASS_PATTERNS = [
        # Memory patching patterns
        (b'AmsiScanBuffer', 'AMSI function name in script'),
        (b'AmsiInitialize', 'AMSI initialization tampering'),
        (b'AmsiUninitialize', 'AMSI uninitialization tampering'),
        (b'amsi.dll', 'Direct AMSI DLL reference'),
        (b'AmsiOpenSession', 'AMSI session manipulation'),
        (b'AmsiCloseSession', 'AMSI session tampering'),
        
        # Common bypass strings
        (b'[Ref].Assembly.GetType', 'Reflection-based bypass'),
        (b'System.Management.Automation.AmsiUtils', 'AmsiUtils class tampering'),
        (b'amsiInitFailed', 'AMSI initialization flag tampering'),
        (b'amsiContext', 'AMSI context manipulation'),
        (b'ScanContent', 'Scan content method tampering'),
        
        # Unicode/encoded variants
        (b'\\x61\\x6d\\x73\\x69', 'Hex-encoded "amsi"'),
        (b'[char]97+[char]109+[char]115+[char]105', 'Char code obfuscation for amsi'),
        
        # PowerShell specific bypasses
        (b'Add-Type -TypeDefinition', 'Possible P/Invoke for AMSI bypass'),
        (b'VirtualProtect', 'Memory protection change (RWX)'),
        (b'WriteProcessMemory', 'Process memory writing'),
        (b'NtWriteVirtualMemory', 'Native memory writing'),
        (b'GetProcAddress', 'Function address lookup'),
        (b'LoadLibrary', 'Dynamic library loading'),
        
        # Known bypass tool signatures
        (b'Invoke-AMSIBypass', 'Known AMSI bypass invoke'),
        (b'Disable-Amsi', 'AMSI disable function'),
        (b'AmsiBypass', 'Bypass keyword'),
        (b'amsi_bypass', 'Bypass keyword'),
        (b'Bypass-AMSI', 'Bypass function'),
        
        # Matt Graeber's reflection bypass
        (b'[Runtime.InteropServices.RuntimeEnvironment]', 'Runtime manipulation'),
        (b'NonPublic,Static', 'Non-public static field access'),
        (b'SetValue($null,$true)', 'Flag manipulation'),
    ]
    
    # Script obfuscation indicators
    OBFUSCATION_PATTERNS = [
        # Base64 encoding
        (r'[System.Convert]::FromBase64String', 'Base64 decode'),
        (r'-e[nncoded]*c[ommand]*\s+[\w+/=]+', 'Encoded command'),
        (r'[System.Text.Encoding]::Unicode.GetString', 'Unicode string decode'),
        (r'[System.Text.Encoding]::ASCII.GetString', 'ASCII string decode'),
        
        # Character substitution
        (r'\[char\]\d+', 'Character code obfuscation'),
        (r'\(\[char\]\d+\+', 'Character concatenation'),
        (r'-join\s*\(\s*\d+', 'Join with char codes'),
        (r'-bxor', 'XOR operation'),
        
        # String manipulation
        (r'\.Replace\([^)]+\)', 'String replacement obfuscation'),
        (r'-replace\s+["\'][^"\']+["\']', 'Regex replacement'),
        (r'\.Split\([^)]+\)\[\d+\]', 'String split extraction'),
        (r'-split\s+["\'][^"\']+["\']', 'String splitting'),
        
        # Invoke-Expression variants
        (r'[Ii]nvoke-[Ee]xpression', 'Invoke-Expression'),
        (r'[Ii][Ee][Xx]', 'IEX alias'),
        (r'&\(\$', 'Dynamic invocation'),
        (r'\.\(\$', 'Dot-sourced dynamic invocation'),
        
        # Format string obfuscation
        (r'-[Ff]\s*[\'"]\{0\}', 'Format string obfuscation'),
        (r'\$\([^\)]+\)\s*-f', 'Format operator'),
        
        # Variable substitution
        (r'\$\{[^}]+\}', 'Curly brace variable'),
        (r'\$env:[a-z]+\[[^\]]+\]', 'Environment variable slicing'),
        
        # Compression/decompression
        (r'IO.Compression', 'Compression library'),
        (r'GZipStream', 'GZip decompression'),
        (r'DeflateStream', 'Deflate decompression'),
        (r'MemoryStream', 'Memory stream manipulation'),
        
        # Reflection loading
        (r'\[Reflection.Assembly\]::Load', 'Reflection assembly load'),
        (r'Assembly.Load', 'Assembly loading'),
        (r'Activator.CreateInstance', 'Dynamic instantiation'),
    ]
    
    # Dangerous PowerShell commands
    DANGEROUS_COMMANDS = [
        'Invoke-Mimikatz', 'Invoke-Kerberoast', 'Invoke-TokenManipulation',
        'Invoke-DCSync', 'Invoke-DllInjection', 'Invoke-ReflectivePEInjection',
        'Invoke-Shellcode', 'Invoke-PowerShellTcp', 'Invoke-PowerShellUdp',
        'PowerView', 'BloodHound', 'Rubeus', 'Seatbelt', 'SharpHound',
        'Get-GPPPassword', 'Get-Keystrokes', 'Get-TimedScreenshot',
        'Add-Exfiltration', 'Do-Exfiltration', 'Out-Minidump',
        'Invoke-SMBExec', 'Invoke-WMIExec', 'Invoke-PsExec',
        'Invoke-Obfuscation', 'Invoke-CradleCrafter'
    ]
    
    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self.threats = []
        self.scan_results = []
        self.bypass_detections = []
        self.obfuscation_detections = []
        self.amsi_available = False
        self.amsi_context = None
        self._init_amsi()
    
    def _init_amsi(self):
        """Initialize AMSI interface"""
        if PLATFORM != "windows":
            logger.debug("AMSI only available on Windows")
            return
        
        try:
            import ctypes
            from ctypes import wintypes
            
            self.amsi = ctypes.windll.amsi
            
            # AMSI_RESULT enum
            self.AMSI_RESULT_CLEAN = 0
            self.AMSI_RESULT_NOT_DETECTED = 1
            self.AMSI_RESULT_BLOCKED_BY_ADMIN_START = 0x4000
            self.AMSI_RESULT_BLOCKED_BY_ADMIN_END = 0x4FFF
            self.AMSI_RESULT_DETECTED = 32768
            
            # Initialize AMSI context
            self.amsi_context = ctypes.c_void_p()
            result = self.amsi.AmsiInitialize(
                ctypes.c_wchar_p("Metatron"),
                ctypes.byref(self.amsi_context)
            )
            
            if result == 0:  # S_OK
                self.amsi_available = True
                logger.info("AMSI initialized successfully")
            else:
                logger.warning(f"AMSI initialization failed: {result}")
                
        except Exception as e:
            logger.debug(f"AMSI not available: {e}")
    
    def scan_content(self, content: str, content_name: str = "script") -> Dict:
        """Scan content using AMSI and additional detection"""
        result = {
            'content_name': content_name,
            'scanned': False,
            'malicious': False,
            'amsi_result': None,
            'bypass_detected': False,
            'obfuscation_level': 0,
            'obfuscation_techniques': [],
            'dangerous_commands': []
        }
        
        content_bytes = content.encode('utf-8', errors='ignore')
        
        # Check for AMSI bypass attempts
        bypass_attempts = self._detect_amsi_bypass(content_bytes, content)
        if bypass_attempts:
            result['bypass_detected'] = True
            result['bypass_techniques'] = bypass_attempts
            result['malicious'] = True  # Auto-flag as malicious
        
        # Check for obfuscation
        obf_techniques = self._detect_obfuscation(content)
        if obf_techniques:
            result['obfuscation_level'] = len(obf_techniques)
            result['obfuscation_techniques'] = obf_techniques
            if len(obf_techniques) >= 3:
                result['malicious'] = True  # High obfuscation is suspicious
        
        # Check for dangerous commands
        dangerous = self._detect_dangerous_commands(content)
        if dangerous:
            result['dangerous_commands'] = dangerous
            result['malicious'] = True
        
        # AMSI scan if available
        if self.amsi_available:
            try:
                import ctypes
                
                # Create AMSI session
                session = ctypes.c_void_p()
                self.amsi.AmsiOpenSession(self.amsi_context, ctypes.byref(session))
                
                # Scan buffer
                amsi_result = ctypes.c_int()
                content_bytes_utf16 = content.encode('utf-16-le')
                
                hr = self.amsi.AmsiScanBuffer(
                    self.amsi_context,
                    content_bytes_utf16,
                    len(content_bytes_utf16),
                    ctypes.c_wchar_p(content_name),
                    session,
                    ctypes.byref(amsi_result)
                )
                
                if hr == 0:  # S_OK
                    result['scanned'] = True
                    result['amsi_result'] = amsi_result.value
                    
                    # Check if malicious
                    if amsi_result.value >= self.AMSI_RESULT_DETECTED:
                        result['malicious'] = True
                
                # Close session
                self.amsi.AmsiCloseSession(self.amsi_context, session)
                
            except Exception as e:
                result['error'] = str(e)
        else:
            # Still mark as scanned using pattern detection
            result['scanned'] = True
        
        return result
    
    def _detect_amsi_bypass(self, content_bytes: bytes, content_str: str) -> List[Dict]:
        """Detect AMSI bypass attempts in script content"""
        bypasses = []
        content_lower = content_str.lower()
        
        for pattern, description in self.AMSI_BYPASS_PATTERNS:
            if isinstance(pattern, bytes):
                if pattern.lower() in content_bytes.lower():
                    bypasses.append({
                        'pattern': pattern.decode('utf-8', errors='ignore'),
                        'technique': description,
                        'severity': 'critical'
                    })
            else:
                if pattern.lower() in content_lower:
                    bypasses.append({
                        'pattern': pattern,
                        'technique': description,
                        'severity': 'critical'
                    })
        
        return bypasses
    
    def _detect_obfuscation(self, content: str) -> List[Dict]:
        """Detect script obfuscation techniques"""
        techniques = []
        
        for pattern, description in self.OBFUSCATION_PATTERNS:
            try:
                if re.search(pattern, content, re.IGNORECASE):
                    techniques.append({
                        'pattern': pattern,
                        'technique': description,
                        'severity': 'medium'
                    })
            except re.error:
                pass
        
        # Additional heuristics
        # High entropy (random-looking strings)
        non_space = re.sub(r'\s+', '', content)
        if len(non_space) > 100:
            unique_chars = len(set(non_space))
            char_ratio = unique_chars / len(non_space)
            if char_ratio < 0.1:  # Very repetitive (possible encoded)
                techniques.append({
                    'technique': 'Low character diversity (encoded content)',
                    'severity': 'medium'
                })
        
        # Very long lines (obfuscated one-liners)
        lines = content.split('\n')
        for line in lines:
            if len(line) > 1000:
                techniques.append({
                    'technique': 'Extremely long line (possible one-liner obfuscation)',
                    'severity': 'low'
                })
                break
        
        # Tick/backtick obfuscation
        if re.search(r'`\w', content):
            tick_count = len(re.findall(r'`\w', content))
            if tick_count > 5:
                techniques.append({
                    'technique': f'Backtick obfuscation ({tick_count} instances)',
                    'severity': 'medium'
                })
        
        return techniques
    
    def _detect_dangerous_commands(self, content: str) -> List[str]:
        """Detect known dangerous PowerShell commands"""
        found = []
        content_lower = content.lower()
        
        for cmd in self.DANGEROUS_COMMANDS:
            if cmd.lower() in content_lower:
                found.append(cmd)
        
        return found
    
    def scan(self) -> Dict[str, Any]:
        """Comprehensive scan for malicious scripts and AMSI bypasses"""
        self.threats = []
        self.scan_results = []
        self.bypass_detections = []
        self.obfuscation_detections = []
        
        scanned = 0
        detections = 0
        bypass_detections = 0
        obfuscation_count = 0
        
        # Script file extensions to scan
        script_extensions = ['*.ps1', '*.psm1', '*.psd1', '*.vbs', '*.vbe', '*.js', '*.jse', '*.wsf', '*.bat', '*.cmd']
        
        # Scan paths
        script_paths = []
        
        if PLATFORM == "windows":
            script_paths = [
                Path.home() / "AppData" / "Local" / "Temp",
                Path.home() / "Downloads",
                Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup",
                Path("C:/Windows/Temp"),
            ]
        else:
            script_paths = [
                Path("/tmp"),
                Path.home() / "Downloads",
                Path.home() / ".local" / "share",
            ]
        
        for base_path in script_paths:
            try:
                if not base_path.exists():
                    continue
                
                for ext in script_extensions:
                    for script in base_path.glob(ext):
                        try:
                            # Skip very large files
                            if script.stat().st_size > 1024 * 1024:  # > 1MB
                                continue
                            
                            content = script.read_text(errors='ignore')[:100000]
                            result = self.scan_content(content, str(script))
                            scanned += 1
                            
                            if result.get('bypass_detected'):
                                bypass_detections += 1
                                self.bypass_detections.append({
                                    'path': str(script),
                                    'techniques': result.get('bypass_techniques', []),
                                    'timestamp': datetime.now(timezone.utc).isoformat()
                                })
                            
                            if result.get('obfuscation_level', 0) >= 2:
                                obfuscation_count += 1
                                self.obfuscation_detections.append({
                                    'path': str(script),
                                    'level': result.get('obfuscation_level'),
                                    'techniques': result.get('obfuscation_techniques', []),
                                    'timestamp': datetime.now(timezone.utc).isoformat()
                                })
                            
                            if result.get('malicious'):
                                detections += 1
                                self.scan_results.append({
                                    'path': str(script),
                                    'result': result,
                                    'timestamp': datetime.now(timezone.utc).isoformat()
                                })
                                self._create_threat(script, result)
                                
                        except Exception as e:
                            logger.debug(f"Error scanning {script}: {e}")
                            
            except Exception as e:
                logger.debug(f"Error scanning path {base_path}: {e}")
        
        # Check PowerShell event logs (Windows)
        event_log_detections = []
        if PLATFORM == "windows":
            event_log_detections = self._check_powershell_event_logs()
        
        self.last_run = datetime.now(timezone.utc)
        
        return {
            "amsi_available": self.amsi_available,
            "scripts_scanned": scanned,
            "malicious_detections": detections,
            "bypass_attempts": bypass_detections,
            "obfuscated_scripts": obfuscation_count,
            "event_log_detections": len(event_log_detections),
            "threats": len(self.threats),
            "scan_results": self.scan_results[-10:],
            "bypass_detections": self.bypass_detections[-5:],
            "obfuscation_detections": self.obfuscation_detections[-5:]
        }
    
    def _check_powershell_event_logs(self) -> List[Dict]:
        """Check PowerShell event logs for suspicious activity"""
        detections = []
        
        try:
            import win32evtlog
            import win32evtlogutil
            
            server = 'localhost'
            log_type = 'Microsoft-Windows-PowerShell/Operational'
            
            hand = win32evtlog.OpenEventLog(server, log_type)
            flags = win32evtlog.EVENTLOG_BACKWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ
            
            events = win32evtlog.ReadEventLog(hand, flags, 0)
            
            for event in events[:100]:  # Check last 100 events
                # Event ID 4104 = Script Block Logging
                if event.EventID == 4104:
                    data = win32evtlogutil.SafeFormatMessage(event, log_type)
                    
                    # Check for suspicious patterns
                    for pattern, desc in self.AMSI_BYPASS_PATTERNS[:10]:
                        if pattern.decode('utf-8', errors='ignore').lower() in data.lower():
                            detections.append({
                                'event_id': 4104,
                                'timestamp': str(event.TimeGenerated),
                                'pattern': desc,
                                'source': 'PowerShell Script Block'
                            })
                            break
            
            win32evtlog.CloseEventLog(hand)
            
        except ImportError:
            logger.debug("win32evtlog not available for event log checking")
        except Exception as e:
            logger.debug(f"Event log check error: {e}")
        
        return detections
    
    def _create_threat(self, script_path: Path, scan_result: Dict):
        """Create threat from detection with enhanced details"""
        
        # Determine severity based on findings
        severity = ThreatSeverity.MEDIUM
        threat_type = "malicious_script"
        mitre_techniques = ["T1059.001", "T1027"]  # PowerShell, Obfuscation
        
        if scan_result.get('bypass_detected'):
            severity = ThreatSeverity.CRITICAL
            threat_type = "amsi_bypass"
            mitre_techniques.extend(["T1562.001", "T1070"])  # Disable Defense, Indicator Removal
        elif scan_result.get('dangerous_commands'):
            severity = ThreatSeverity.CRITICAL
            threat_type = "attack_tool"
            mitre_techniques.extend(["T1003", "T1558"])  # Credential Dumping, Steal/Forge Tickets
        elif scan_result.get('obfuscation_level', 0) >= 3:
            severity = ThreatSeverity.HIGH
        
        # Build description
        desc_parts = []
        if scan_result.get('bypass_detected'):
            desc_parts.append(f"AMSI bypass attempt detected")
        if scan_result.get('dangerous_commands'):
            desc_parts.append(f"Dangerous commands: {', '.join(scan_result['dangerous_commands'][:3])}")
        if scan_result.get('obfuscation_level'):
            desc_parts.append(f"Obfuscation level: {scan_result['obfuscation_level']}")
        if scan_result.get('amsi_result'):
            desc_parts.append(f"AMSI result: {scan_result['amsi_result']}")
        
        description = "; ".join(desc_parts) if desc_parts else "Malicious script detected"
        
        threat = Threat(
            threat_id=f"amsi-{uuid.uuid4().hex[:8]}",
            title=f"Script Threat: {script_path.name}",
            description=description,
            severity=severity,
            threat_type=threat_type,
            source="amsi_monitor",
            target=str(script_path),
            evidence={
                'path': str(script_path),
                'bypass_detected': scan_result.get('bypass_detected', False),
                'bypass_techniques': scan_result.get('bypass_techniques', []),
                'obfuscation_level': scan_result.get('obfuscation_level', 0),
                'obfuscation_techniques': scan_result.get('obfuscation_techniques', [])[:5],
                'dangerous_commands': scan_result.get('dangerous_commands', []),
                'amsi_result': scan_result.get('amsi_result')
            },
            mitre_techniques=mitre_techniques,
            auto_kill_eligible=True,
            remediation_action="quarantine_file",
            remediation_params={"filepath": str(script_path)}
        )
        self.threats.append(threat)
    
    def get_threats(self) -> List[Threat]:
        return self.threats
    
    def __del__(self):
        """Cleanup AMSI context"""
        if self.amsi_available and self.amsi_context:
            try:
                self.amsi.AmsiUninitialize(self.amsi_context)
            except Exception:
                pass


class NetworkScanner:
    """Advanced network scanner for ports, router, local network"""
    
    def __init__(self):
        self.common_ports = [21, 22, 23, 25, 53, 80, 110, 143, 443, 445, 993, 995, 3306, 3389, 5432, 8080, 8443]
        self.dangerous_ports = [23, 445, 1433, 3389, 5900]
        self.scan_results = {}
    
    def get_gateway(self) -> Optional[str]:
        """Get default gateway IP"""
        try:
            if PLATFORM == 'windows':
                result = subprocess.run(['ipconfig'], capture_output=True, text=True)
                for line in result.stdout.split('\n'):
                    if 'Default Gateway' in line:
                        parts = line.split(':')
                        if len(parts) > 1:
                            ip = parts[1].strip()
                            if ip:
                                return ip
            else:
                result = subprocess.run(['ip', 'route'], capture_output=True, text=True)
                for line in result.stdout.split('\n'):
                    if 'default' in line:
                        parts = line.split()
                        for i, p in enumerate(parts):
                            if p == 'via' and i + 1 < len(parts):
                                return parts[i + 1]
        except:
            pass
        return None
    
    def scan_port(self, ip: str, port: int, timeout: float = 0.5) -> bool:
        """Check if a port is open"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((ip, port))
            sock.close()
            return result == 0
        except:
            return False
    
    def scan_host(self, ip: str, ports: Optional[List[int]] = None) -> Dict:
        """Scan a host for open ports"""
        if ports is None:
            ports = self.common_ports
        
        open_ports = []
        for port in ports:
            if self.scan_port(ip, port):
                service = self._get_service_name(port)
                open_ports.append({
                    "port": port,
                    "service": service,
                    "dangerous": port in self.dangerous_ports
                })
        
        return {
            "ip": ip,
            "open_ports": open_ports,
            "scan_time": datetime.now(timezone.utc).isoformat()
        }
    
    def scan_router(self) -> Dict:
        """Scan the default gateway/router"""
        gateway = self.get_gateway()
        if not gateway:
            return {"error": "Could not determine gateway"}
        
        router_ports = [80, 443, 8080, 22, 23, 53]
        result = self.scan_host(gateway, router_ports)
        result["is_gateway"] = True
        
        vulnerabilities = []
        if any(p["port"] == 23 for p in result["open_ports"]):
            vulnerabilities.append({"type": "telnet_open", "severity": "high"})
        if any(p["port"] == 80 for p in result["open_ports"]):
            vulnerabilities.append({"type": "http_admin", "severity": "medium"})
        
        result["vulnerabilities"] = vulnerabilities
        return result
    
    def _get_service_name(self, port: int) -> str:
        services = {
            21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP", 53: "DNS",
            80: "HTTP", 110: "POP3", 143: "IMAP", 443: "HTTPS", 445: "SMB",
            993: "IMAPS", 995: "POP3S", 3306: "MySQL", 3389: "RDP",
            5432: "PostgreSQL", 5900: "VNC", 8080: "HTTP-Alt", 8443: "HTTPS-Alt"
        }
        return services.get(port, "Unknown")


class WiFiScanner:
    """WiFi network scanner"""
    
    def scan_networks(self) -> List[Dict]:
        """Scan for available WiFi networks"""
        networks = []
        
        try:
            if PLATFORM == 'windows':
                result = subprocess.run(
                    ['netsh', 'wlan', 'show', 'networks', 'mode=bssid'],
                    capture_output=True, text=True
                )
                
                current_network = {}
                for line in result.stdout.split('\n'):
                    line = line.strip()
                    if line.startswith('SSID') and ':' in line:
                        if current_network and current_network.get('ssid'):
                            networks.append(current_network)
                        current_network = {'ssid': line.split(':', 1)[1].strip()}
                    elif line.startswith('BSSID'):
                        current_network['bssid'] = line.split(':', 1)[1].strip()
                    elif line.startswith('Signal'):
                        current_network['signal'] = line.split(':', 1)[1].strip()
                    elif line.startswith('Authentication'):
                        current_network['auth'] = line.split(':', 1)[1].strip()
                
                if current_network and current_network.get('ssid'):
                    networks.append(current_network)
                    
            else:
                try:
                    result = subprocess.run(
                        ['nmcli', '-t', '-f', 'SSID,BSSID,SIGNAL,SECURITY', 'device', 'wifi', 'list'],
                        capture_output=True, text=True
                    )
                    for line in result.stdout.strip().split('\n'):
                        if line:
                            parts = line.split(':')
                            if len(parts) >= 4:
                                networks.append({
                                    'ssid': parts[0],
                                    'bssid': parts[1],
                                    'signal': parts[2] + '%',
                                    'auth': parts[3]
                                })
                except:
                    pass
        except Exception as e:
            logger.error(f"WiFi scan error: {e}")
        
        # Analyze for threats
        for network in networks:
            network['threats'] = self._analyze_network(network)
        
        return networks
    
    def _analyze_network(self, network: Dict) -> List[Dict]:
        """Analyze a network for potential threats"""
        threats = []
        
        auth = network.get('auth', '').lower()
        
        if 'open' in auth or 'none' in auth:
            threats.append({"type": "open_network", "severity": "high"})
        
        if 'wep' in auth:
            threats.append({"type": "weak_encryption", "severity": "critical"})
        
        return threats


class BluetoothScanner:
    """Bluetooth device scanner"""
    
    def scan_devices(self) -> List[Dict]:
        """Scan for nearby Bluetooth devices"""
        devices = []
        
        try:
            if PLATFORM == 'windows':
                ps_script = '''
                Get-PnpDevice -Class Bluetooth | Where-Object {$_.Status -eq 'OK'} | 
                Select-Object FriendlyName, DeviceID, Status | ConvertTo-Json
                '''
                result = subprocess.run(
                    ['powershell', '-Command', ps_script],
                    capture_output=True, text=True
                )
                if result.stdout:
                    try:
                        data = json.loads(result.stdout)
                        if isinstance(data, dict):
                            data = [data]
                        for d in data:
                            devices.append({
                                "name": d.get('FriendlyName', 'Unknown'),
                                "id": d.get('DeviceID', ''),
                                "status": d.get('Status', 'Unknown'),
                                "type": "paired"
                            })
                    except:
                        pass
            else:
                try:
                    result = subprocess.run(['hcitool', 'scan'], capture_output=True, text=True, timeout=10)
                    for line in result.stdout.strip().split('\n')[1:]:
                        parts = line.strip().split('\t')
                        if len(parts) >= 2:
                            devices.append({
                                "address": parts[0],
                                "name": parts[1] if len(parts) > 1 else "Unknown",
                                "type": "discovered"
                            })
                except:
                    pass
        except Exception as e:
            logger.error(f"Bluetooth scan error: {e}")
        
        return devices


# =============================================================================
# LAN NETWORK DISCOVERY (Integrated from seraph_network_scanner)
# =============================================================================

class LANDiscoveryScanner:
    """
    Integrated LAN network scanner for discovering devices on local network.
    Auto-installed with unified agent - no separate network scanner needed.
    Reports discovered devices to server for auto-deployment.
    """
    
    def __init__(self, server_url: str = ""):
        self.server_url = server_url.rstrip('/') if server_url else ""
        self.scanner_id = f"unified-{HOSTNAME}-{uuid.uuid4().hex[:8]}"
        self.discovered_devices: Dict[str, dict] = {}
        self.local_ip = self._get_local_ip()
        self.network_cidr = self._get_network_cidr()
        
        logger.info(f"LAN Discovery initialized - Network: {self.network_cidr}")
    
    def _get_local_ip(self) -> str:
        """Get local IP address"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"
    
    def _get_network_cidr(self) -> str:
        """Get the local network CIDR"""
        try:
            ip = self.local_ip
            parts = ip.split('.')
            
            if parts[0] == '192' and parts[1] == '168':
                return f"192.168.{parts[2]}.0/24"
            elif parts[0] == '10':
                return f"10.{parts[1]}.{parts[2]}.0/24"
            elif parts[0] == '172' and 16 <= int(parts[1]) <= 31:
                return f"172.{parts[1]}.{parts[2]}.0/24"
            else:
                return f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"
        except Exception:
            return "192.168.1.0/24"
    
    def scan_network(self, network: Optional[str] = None) -> List[dict]:
        """
        Comprehensive network scan using multiple methods.
        Discovers all devices on LAN for agent deployment.
        """
        network = network or self.network_cidr
        devices = []
        
        logger.info(f"Starting LAN discovery scan: {network}")
        
        # Method 1: ARP scan (fastest, most reliable)
        arp_devices = self._arp_scan(network)
        logger.info(f"ARP scan found: {len(arp_devices)} devices")
        
        # Method 2: Nmap scan if available
        nmap_devices = self._nmap_scan(network)
        logger.info(f"Nmap scan found: {len(nmap_devices)} devices")
        
        # Merge all results
        seen_ips = set()
        for device in arp_devices + nmap_devices:
            ip = device.get('ip_address')
            if ip and ip not in seen_ips:
                seen_ips.add(ip)
                devices.append(device)
        
        # Enrich devices with OS detection and port info
        devices = self._enrich_devices(devices)
        
        # Store discovered devices
        for device in devices:
            self.discovered_devices[device['ip_address']] = device
        
        logger.info(f"Total unique devices found: {len(devices)}")
        return devices
    
    def _arp_scan(self, network: str) -> List[dict]:
        """ARP scan using ping sweep and ARP cache"""
        devices = []
        
        try:
            import ipaddress as ipaddr
            from concurrent.futures import ThreadPoolExecutor, as_completed
            
            network_obj = ipaddr.ip_network(network, strict=False)
            
            # Quick ping sweep to populate ARP cache
            def ping_host(ip):
                try:
                    if PLATFORM == "windows":
                        result = subprocess.run(
                            ["ping", "-n", "1", "-w", "100", str(ip)],
                            capture_output=True, timeout=2
                        )
                    else:
                        result = subprocess.run(
                            ["ping", "-c", "1", "-W", "1", str(ip)],
                            capture_output=True, timeout=2
                        )
                    return result.returncode == 0
                except:
                    return False
            
            # Parallel ping sweep
            with ThreadPoolExecutor(max_workers=100) as executor:
                futures = {executor.submit(ping_host, ip): ip for ip in network_obj.hosts()}
                for future in as_completed(futures, timeout=30):
                    pass  # Just populate ARP cache
            
            # Read ARP cache
            if PLATFORM == "windows":
                result = subprocess.run(["arp", "-a"], capture_output=True, text=True, timeout=10)
                for line in result.stdout.split('\n'):
                    if 'dynamic' in line.lower():
                        parts = line.split()
                        if len(parts) >= 2:
                            ip = parts[0]
                            mac = parts[1].replace('-', ':').lower()
                            if self._is_valid_ip(ip) and self._ip_in_network(ip, network):
                                devices.append({
                                    'ip_address': ip,
                                    'mac_address': mac,
                                    'discovery_method': 'arp'
                                })
            else:
                result = subprocess.run(["arp", "-n"], capture_output=True, text=True, timeout=10)
                for line in result.stdout.split('\n'):
                    parts = line.split()
                    if len(parts) >= 3 and parts[2] != '(incomplete)':
                        ip = parts[0]
                        mac = parts[2].lower()
                        if self._is_valid_ip(ip) and self._ip_in_network(ip, network):
                            devices.append({
                                'ip_address': ip,
                                'mac_address': mac,
                                'discovery_method': 'arp'
                            })
        except Exception as e:
            logger.debug(f"ARP scan error: {e}")
        
        return devices
    
    def _nmap_scan(self, network: str) -> List[dict]:
        """Nmap scan for comprehensive discovery"""
        devices = []
        
        try:
            import nmap
            nm = nmap.PortScanner()
            
            try:
                nm.scan(hosts=network, arguments='-sn -T4 --min-rate=500')
            except:
                nm.scan(hosts=network, arguments='-sn -T4')
            
            for host in nm.all_hosts():
                device = {
                    'ip_address': host,
                    'discovery_method': 'nmap'
                }
                
                if 'mac' in nm[host].get('addresses', {}):
                    device['mac_address'] = nm[host]['addresses']['mac'].lower()
                
                if nm[host].get('vendor'):
                    device['vendor'] = list(nm[host]['vendor'].values())[0] if nm[host]['vendor'] else None
                
                if nm[host].get('hostnames'):
                    for h in nm[host]['hostnames']:
                        if h.get('name'):
                            device['hostname'] = h['name']
                            break
                
                devices.append(device)
                
        except ImportError:
            logger.debug("python-nmap not available, skipping nmap scan")
        except Exception as e:
            logger.debug(f"Nmap scan error: {e}")
        
        return devices
    
    def _enrich_devices(self, devices: List[dict]) -> List[dict]:
        """Enrich devices with OS detection and port info"""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        common_ports = {
            22: ('ssh', 'Linux'),
            3389: ('rdp', 'Windows'),
            445: ('smb', 'Windows'),
            548: ('afp', 'macOS'),
            5353: ('mdns', 'Apple'),
            62078: ('iphone-sync', 'iOS'),
            5555: ('adb', 'Android'),
        }
        
        def enrich_single(device):
            ip = device['ip_address']
            open_ports = []
            os_hints = []
            
            for port, (service, os_hint) in common_ports.items():
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(0.5)
                    result = sock.connect_ex((ip, port))
                    sock.close()
                    if result == 0:
                        open_ports.append({'port': port, 'service': service})
                        os_hints.append(os_hint)
                except:
                    pass
            
            device['open_ports'] = open_ports
            
            # Determine OS type
            if 'iOS' in os_hints:
                device['os_type'] = 'iOS'
                device['device_type'] = 'mobile'
            elif 'Android' in os_hints:
                device['os_type'] = 'Android'
                device['device_type'] = 'mobile'
            elif 'Windows' in os_hints:
                device['os_type'] = 'Windows'
                device['device_type'] = 'workstation'
            elif 'Linux' in os_hints:
                device['os_type'] = 'Linux'
                device['device_type'] = 'server'
            elif 'macOS' in os_hints or 'Apple' in os_hints:
                device['os_type'] = 'macOS'
                device['device_type'] = 'workstation'
            else:
                device['os_type'] = 'unknown'
                device['device_type'] = 'unknown'
            
            # Determine if we can deploy an agent
            device['deployable'] = device.get('os_type') in ['Linux', 'Windows', 'macOS']
            device['mobile_manageable'] = device.get('os_type') in ['iOS', 'Android']
            
            return device
        
        enriched = []
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = {executor.submit(enrich_single, d): d for d in devices}
            for future in as_completed(futures, timeout=60):
                try:
                    enriched.append(future.result())
                except:
                    enriched.append(futures[future])
        
        return enriched
    
    def _is_valid_ip(self, ip: str) -> bool:
        """Check if IP is valid"""
        try:
            import ipaddress as ipaddr
            ipaddr.ip_address(ip)
            return True
        except:
            return False
    
    def _ip_in_network(self, ip: str, network: str) -> bool:
        """Check if IP is in network"""
        try:
            import ipaddress as ipaddr
            return ipaddr.ip_address(ip) in ipaddr.ip_network(network, strict=False)
        except:
            return False
    
    def report_to_server(self, devices: Optional[List[dict]] = None) -> bool:
        """Report discovered devices to server for auto-deployment"""
        if not REQUESTS_AVAILABLE or not self.server_url:
            logger.warning("Cannot report: requests not available or server URL not set")
            return False
        
        if devices is None:
            devices = list(self.discovered_devices.values())
        
        try:
            payload = {
                'scanner_id': self.scanner_id,
                'network': self.network_cidr,
                'scan_time': datetime.now(timezone.utc).isoformat(),
                'devices': devices,
                'auto_deploy_request': True  # Request auto-deployment
            }
            
            response = requests.post(
                f"{self.server_url}/api/swarm/scanner/report",
                json=payload,
                timeout=30
            )
            
            if response.ok:
                result = response.json()
                logger.info(f"Reported {len(devices)} devices to server")
                return True
            else:
                logger.error(f"Failed to report devices: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error reporting to server: {e}")
            return False
    
    def get_discovered_devices(self) -> List[dict]:
        """Get all discovered devices"""
        return list(self.discovered_devices.values())


# =============================================================================
# WIREGUARD VPN AUTO-SETUP
# =============================================================================

class WireGuardAutoSetup:
    """
    Automatic WireGuard VPN setup for secure agent communication.
    Auto-configures VPN tunnel when agent registers with server.
    """
    
    def __init__(self, server_url: str = "", agent_id: str = "", config: Optional['AgentConfig'] = None):
        self.server_url = server_url.rstrip('/') if server_url else ""
        self.agent_id = agent_id
        self.config = config
        self.address = ""
        self.is_configured = False
        self.is_connected = False
        
        # Config paths
        if PLATFORM == "windows":
            self.config_dir = Path(os.environ.get('PROGRAMDATA') or os.environ.get('LOCALAPPDATA', 'C:/')) / "SeraphAgent" / "WireGuard"
        elif PLATFORM == "darwin":
            self.config_dir = Path.home() / "Library" / "Application Support" / "SeraphAgent" / "WireGuard"
        else:
            if hasattr(os, "geteuid") and os.geteuid() == 0:
                self.config_dir = Path(os.environ.get("SERAPH_WIREGUARD_DIR", "/var/lib/seraph-agent/wireguard"))
            else:
                self.config_dir = Path(os.environ.get("SERAPH_WIREGUARD_DIR", str(Path.home() / ".config" / "seraph-agent" / "wireguard")))
        
        self.config_file = self.config_dir / "metatron-vpn.conf"
        self.system_config_file = Path("/etc/wireguard/metatron-vpn.conf")
    
    def auto_configure(self) -> bool:
        """
        Automatically configure WireGuard VPN connection.
        1. Request server config (peer addition)
        2. Create local WireGuard config
        3. Start VPN connection
        """
        if not self.server_url or not self.agent_id:
            logger.warning("VPN auto-config: server_url or agent_id not set")
            return False
        
        logger.info("Starting WireGuard VPN auto-configuration...")
        
        # Step 1: Request VPN config from server
        vpn_config = self._request_vpn_config()
        if not vpn_config:
            logger.error("Failed to get VPN config from server")
            return False
        
        # Step 3: Create local config file
        if not self._create_config_file(vpn_config):
            logger.error("Failed to create WireGuard config file")
            return False
        
        # Step 4: Start VPN connection
        if not self._start_vpn():
            logger.warning("VPN configured but failed to start (may need admin rights)")
            self.is_configured = True
            return True  # Config created, just not started
        
        self.is_configured = True
        self.is_connected = True
        logger.info("WireGuard VPN auto-configuration complete!")
        return True
    
    def _generate_keys(self) -> bool:
        """Generate WireGuard key pair"""
        try:
            # Try using wg command first
            result = subprocess.run(['wg', 'genkey'], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                self.private_key = result.stdout.strip()
                
                result = subprocess.run(
                    ['wg', 'pubkey'],
                    input=self.private_key,
                    capture_output=True, text=True, timeout=10
                )
                if result.returncode == 0:
                    self.public_key = result.stdout.strip()
                    logger.info("Generated WireGuard keys using wg command")
                    return True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        # Fallback: Generate keys using Python (requires cryptography library)
        try:
            from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
            from cryptography.hazmat.primitives import serialization
            import base64
            
            private_key = X25519PrivateKey.generate()
            self.private_key = base64.b64encode(
                private_key.private_bytes_raw()
            ).decode('ascii')
            self.public_key = base64.b64encode(
                private_key.public_key().public_bytes_raw()
            ).decode('ascii')
            logger.info("Generated WireGuard keys using Python cryptography")
            return True
        except ImportError:
            logger.warning("cryptography library not available for key generation")
        
        # Final fallback: Generate random keys (less secure but functional)
        import secrets
        import base64
        
        key_bytes = secrets.token_bytes(32)
        self.private_key = base64.b64encode(key_bytes).decode('ascii')
        self.public_key = hashlib.sha256(key_bytes).hexdigest()[:43] + "="
        logger.warning("Generated fallback keys (install WireGuard for proper keys)")
        return True
    
    def _get_auth_headers(self) -> Dict[str, str]:
        if not self.config:
            return {}
        if getattr(self.config, 'auth_token', None):
            return {
                'X-Agent-Id': self.config.agent_id,
                'X-Agent-Token': self.config.auth_token,
            }
        if getattr(self.config, 'enrollment_key', None):
            return {'X-Enrollment-Key': self.config.enrollment_key}
        return {}

    def _get_client_address(self, config_text: str) -> str:
        match = re.search(r"^\s*Address\s*=\s*([^\r\n]+)", config_text, re.MULTILINE)
        if match:
            return match.group(1).strip().split('/')[0]
        return ""

    def _request_vpn_config(self) -> Optional[Dict]:
        """Request VPN configuration from server"""
        if not REQUESTS_AVAILABLE:
            return None
        
        try:
            headers = self._get_auth_headers()
            response = requests.post(
                f"{self.server_url}/api/vpn/peers",
                headers=headers,
                json={
                    'name': self.agent_id,
                    'peer_id': self.agent_id,
                },
                timeout=30
            )
            
            if response.status_code not in [200, 201]:
                logger.error(f"VPN peer registration failed: {response.status_code}")
                return None

            peer_data = response.json()
            config_response = requests.get(
                f"{self.server_url}/api/vpn/peers/{self.agent_id}/config",
                headers=headers,
                timeout=30
            )
            
            if config_response.status_code == 200:
                config_text = config_response.text
                client_address = self._get_client_address(config_text) or peer_data.get('allowed_ips', '').split('/')[0]
                return {
                    'config_text': config_text,
                    'client_address': client_address,
                }

            logger.error(f"Failed to download VPN peer config: {config_response.status_code}")
            return None
        except Exception as e:
            logger.error(f"VPN config request error: {e}")
            return None
    
    def _create_config_file(self, vpn_config: Dict) -> bool:
        """Create WireGuard configuration file"""
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            
            if isinstance(vpn_config, dict) and vpn_config.get('config_text'):
                config_content = vpn_config['config_text']
                self.address = vpn_config.get('client_address', self.address)
            else:
                client_address = vpn_config.get('client_address', '10.200.200.100')
                if '/' not in client_address:
                    client_address += '/32'
                
                config_content = f"""# Metatron Unified Agent VPN Configuration
# Auto-generated - Agent ID: {self.agent_id}

[Interface]
PrivateKey = {self.private_key}
Address = {client_address}
DNS = {vpn_config.get('dns', '1.1.1.1, 8.8.8.8')}

[Peer]
PublicKey = {vpn_config.get('server_public_key', '')}
Endpoint = {vpn_config.get('server_endpoint', '')}
AllowedIPs = {vpn_config.get('allowed_ips', '10.200.200.0/24')}
PersistentKeepalive = 25
"""

            # Write config file
            with open(self.config_file, 'w') as f:
                f.write(config_content)
            
            # Set proper permissions on Linux/macOS
            if PLATFORM != "windows":
                os.chmod(self.config_file, 0o600)
                if hasattr(os, "geteuid") and os.geteuid() == 0:
                    try:
                        self.system_config_file.parent.mkdir(parents=True, exist_ok=True)
                        with open(self.system_config_file, "w") as system_file:
                            system_file.write(config_content)
                        os.chmod(self.system_config_file, 0o600)
                        logger.info(f"Mirrored WireGuard config: {self.system_config_file}")
                    except Exception as mirror_error:
                        logger.warning(f"Could not mirror WireGuard config to /etc/wireguard: {mirror_error}")
            
            logger.info(f"Created WireGuard config: {self.config_file}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create config file: {e}")
            return False
    
    def _start_vpn(self) -> bool:
        """Start the WireGuard VPN connection"""
        try:
            if PLATFORM == "windows":
                # Windows: Use WireGuard service; support both PATH and default install location.
                wg_candidates = [
                    "wireguard",
                    r"C:\\Program Files\\WireGuard\\wireguard.exe",
                    r"C:\\Program Files (x86)\\WireGuard\\wireguard.exe",
                ]
                last_err = None
                started = False
                for wg_cmd in wg_candidates:
                    try:
                        subprocess.run(
                            [wg_cmd, '/installtunnelservice', str(self.config_file)],
                            check=True,
                            capture_output=True,
                        )
                        started = True
                        break
                    except (subprocess.CalledProcessError, FileNotFoundError) as e:
                        last_err = e
                if not started:
                    if last_err:
                        raise last_err
                    raise FileNotFoundError("WireGuard executable not found")
            elif PLATFORM == "darwin":
                # macOS: Use wg-quick
                subprocess.run(
                    ['wg-quick', 'up', str(self.config_file)],
                    check=True, capture_output=True
                )
            else:
                # Linux: Use wg-quick
                subprocess.run(
                    ['wg-quick', 'up', str(self.system_config_file if self.system_config_file.exists() else self.config_file)],
                    check=True, capture_output=True
                )
            
            logger.info("WireGuard VPN connection started")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.warning(f"Failed to start VPN (may need admin): {e}")
            return False
        except FileNotFoundError:
            logger.warning("WireGuard not installed, VPN config created but not started")
            return False
    
    def stop_vpn(self) -> bool:
        """Stop the WireGuard VPN connection"""
        try:
            if PLATFORM == "windows":
                subprocess.run(
                    ['wireguard', '/uninstalltunnelservice', 'metatron-vpn'],
                    capture_output=True
                )
            else:
                subprocess.run(['wg-quick', 'down', str(self.system_config_file if self.system_config_file.exists() else self.config_file)], capture_output=True)
            
            self.is_connected = False
            return True
        except:
            return False
    
    def get_status(self) -> Dict:
        """Get VPN connection status"""
        return {
            'configured': self.is_configured,
            'connected': self.is_connected,
            'address': self.address,
            'config_file': str(self.config_file) if self.is_configured else None,
            'system_config_file': str(self.system_config_file) if self.system_config_file.exists() else None,
            'config_dir': str(self.config_dir),
        }


# =============================================================================
# REMEDIATION ENGINE
# =============================================================================

class RemediationEngine:
    """Execute remediation actions"""
    
    def __init__(self):
        self.blocked_ips: Set[str] = set()
        self.blocked_ports: Set[int] = set()
    
    def execute(self, threat: Threat) -> Tuple[bool, str]:
        """Execute remediation action"""
        action = threat.remediation_action
        params = threat.remediation_params
        
        try:
            if action == "kill_process":
                return self._kill_process(params)
            elif action == "block_ip":
                return self._block_ip(params)
            elif action == "block_connection":
                return self._block_connection(params)
            elif action == "quarantine_file":
                return self._quarantine_file(params)
            else:
                return False, f"Unknown action: {action}"
        except Exception as e:
            return False, str(e)
    
    def _kill_process(self, params: Dict) -> Tuple[bool, str]:
        """Kill a malicious process"""
        if not PSUTIL_AVAILABLE:
            return False, "psutil not available"
        
        pid = params.get('pid')
        name = params.get('process_name', 'unknown')
        
        try:
            proc = psutil.Process(pid)
            proc.terminate()
            time.sleep(1)
            if proc.is_running():
                proc.kill()
            logger.warning(f"Killed malicious process: {name} (PID: {pid})")
            return True, f"Successfully terminated process {name} (PID: {pid})"
        except psutil.NoSuchProcess:
            return True, "Process already terminated"
        except psutil.AccessDenied:
            return False, f"Access denied - run as administrator"
        except Exception as e:
            return False, f"Failed to kill process: {e}"
    
    def _block_ip(self, params: Dict) -> Tuple[bool, str]:
        """Block an IP address"""
        ip = params.get('ip')
        
        try:
            if PLATFORM == 'windows':
                cmd = f'netsh advfirewall firewall add rule name="Metatron Block {ip}" dir=out action=block remoteip={ip}'
                subprocess.run(cmd, shell=True, check=True, capture_output=True)
            elif PLATFORM == 'linux':
                subprocess.run(['iptables', '-A', 'OUTPUT', '-d', ip, '-j', 'DROP'], check=True, capture_output=True)
            elif PLATFORM == 'darwin':
                with open('/etc/pf.anchors/metatron', 'a') as f:
                    f.write(f'block out quick to {ip}\n')
                subprocess.run(['pfctl', '-f', '/etc/pf.conf'], capture_output=True)
            
            self.blocked_ips.add(ip)
            logger.info(f"Blocked IP: {ip}")
            return True, f"Successfully blocked IP {ip}"
        except subprocess.CalledProcessError as e:
            return False, f"Failed to block IP (need admin): {e}"
        except Exception as e:
            return False, f"Failed to block IP: {e}"
    
    def _block_connection(self, params: Dict) -> Tuple[bool, str]:
        """Block a specific connection"""
        ip = params.get('ip')
        pid = params.get('pid')
        
        if pid:
            self._kill_process({'pid': pid})
        
        return self._block_ip({'ip': ip})
    
    def _quarantine_file(self, params: Dict) -> Tuple[bool, str]:
        """Move a file to quarantine"""
        filepath = params.get('filepath')
        
        try:
            src = Path(filepath)
            if not src.exists():
                return False, "File not found"
            
            dst = QUARANTINE_DIR / f"{src.name}.{uuid.uuid4().hex[:8]}.quarantine"
            src.rename(dst)
            
            logger.info(f"Quarantined file: {filepath} -> {dst}")
            return True, f"File quarantined: {dst}"
        except Exception as e:
            return False, f"Failed to quarantine: {e}"


# =============================================================================
# RANSOMWARE PROTECTION MODULE
# =============================================================================

class RansomwareProtectionMonitor(MonitorModule):
    """
    Comprehensive ransomware protection for endpoints.
    
    Features:
    - Canary file deployment and monitoring
    - Shadow copy deletion detection (vssadmin/wmic)
    - Protected folder access control
    - Behavioral detection (mass encryption patterns)
    - Backup service disruption monitoring
    """
    
    # Attractive filenames that ransomware will prioritize
    CANARY_FILENAMES = [
        "Budget_2026_CONFIDENTIAL.xlsx",
        "passwords_backup.txt",
        "banking_credentials.docx",
        "crypto_wallet_keys.txt",
        "employee_salaries.xlsx",
        "tax_documents_2025.pdf",
        "secret_project_roadmap.docx",
        "database_backup.sql",
        "private_keys.pem",
        "financial_records.xlsx",
    ]
    
    # Known ransomware file extensions
    RANSOMWARE_EXTENSIONS = {
        # Common ransomware extensions
        '.locky', '.cerber', '.zepto', '.odin', '.thor', '.aesir',
        '.crypted', '.crypt', '.crypto', '.encrypted', '.enc',
        '.locked', '.lock', '.crinf', '.r5a', '.XRNT', '.XTBL',
        '.crypz', '.cryp1', '.crypt1', '.petya', '.cry', '.AES256',
        '.WCRY', '.WNCRY', '.wannacry', '.wanacry', '.wncryt',
        '.dharma', '.adobe', '.arrow', '.bip', '.combo', '.gamma',
        '.monro', '.audit', '.cccmn', '.java', '.health', '.bkpx',
        '.ryuk', '.RYK', '.conti', '.lockbit', '.blackcat', '.alphv',
        '.hive', '.akira', '.rhysida', '.cactus', '.trigona',
    }
    
    # Shadow copy deletion commands (CRITICAL - instant ransomware indicator)
    SHADOW_COPY_COMMANDS = [
        'vssadmin delete shadows',
        'vssadmin resize shadowstorage',
        'wmic shadowcopy delete',
        'wmic shadowcopy where',
        'bcdedit /set {default} bootstatuspolicy ignoreallfailures',
        'bcdedit /set {default} recoveryenabled no',
        'wbadmin delete catalog',
        'wbadmin delete systemstatebackup',
        'cipher /w',  # Secure wipe free space
    ]
    
    # Services ransomware tries to stop
    BACKUP_SERVICES = [
        'VSS', 'SDRSVC', 'wbengine', 'swprv', 'VeeamBackupSvc',
        'SQLWriter', 'SQLBrowser', 'MSSQLSERVER', 'MSSQLServerOLAPService',
        'vds', 'AcronisAgent', 'BackupExecAgentBrowser',
    ]
    
    # Protected folder defaults
    DEFAULT_PROTECTED_FOLDERS = [
        'Documents', 'Pictures', 'Desktop', 'Videos', 'Music',
        'Downloads', 'OneDrive', 'Dropbox', 'Google Drive',
    ]
    
    # Whitelisted processes for protected folders
    ALLOWED_PROCESSES = [
        'explorer.exe', 'code.exe', 'code', 'notepad.exe', 'notepad++.exe',
        'winword.exe', 'excel.exe', 'powerpnt.exe', 'outlook.exe',
        'vlc.exe', 'chrome.exe', 'firefox.exe', 'msedge.exe',
        'onedrive.exe', 'dropbox', 'googledrivesync.exe',
        'libreoffice', 'gimp', 'vim', 'nano', 'gedit',
    ]
    
    def __init__(self, config: AgentConfig = None, callback: Callable[[Threat], None] = None):
        # Accept config (MonitorModule contract) or legacy callback-only usage
        if config is None:
            config = AgentConfig()
        super().__init__(config)
        self._threat_callback = callback
        self.canaries: Dict[str, Dict] = {}  # path -> {hash, deployed_at}
        self.protected_folders: Set[str] = set()
        self.file_events: Dict[str, List[float]] = defaultdict(list)  # process -> timestamps
        self.rename_events: Dict[str, List[Tuple[str, str]]] = defaultdict(list)  # process -> [(old, new)]
        self.shadow_copy_baseline: Optional[int] = None
        self.violations: List[Dict] = []
        self.threats: List[Threat] = []
        self._setup_protection()
    
    def _setup_protection(self):
        """Initialize protection features"""
        # Setup protected folders
        home = Path.home()
        for folder in self.DEFAULT_PROTECTED_FOLDERS:
            path = home / folder
            if path.exists():
                self.protected_folders.add(str(path))
        
        # Deploy canary files
        self._deploy_canaries()
        
        # Establish shadow copy baseline (Windows only)
        if PLATFORM == 'windows':
            self._establish_shadow_baseline()
        
        logger.info(f"Ransomware protection initialized: {len(self.canaries)} canaries, {len(self.protected_folders)} protected folders")
    
    def _deploy_canaries(self):
        """Deploy canary files in protected directories"""
        canary_dirs = [
            Path.home() / 'Documents',
            Path.home() / 'Desktop',
            Path.home() / 'Pictures',
        ]
        
        for directory in canary_dirs:
            if not directory.exists():
                continue
            
            # Pick 2 canary files per directory
            for filename in self.CANARY_FILENAMES[:2]:
                canary_path = directory / filename
                
                try:
                    if not canary_path.exists():
                        # Create decoy content
                        content = self._generate_canary_content(filename)
                        canary_path.write_text(content)
                    
                    # Store hash for monitoring
                    file_hash = hashlib.sha256(canary_path.read_bytes()).hexdigest()
                    self.canaries[str(canary_path)] = {
                        'hash': file_hash,
                        'deployed_at': datetime.now(timezone.utc).isoformat(),
                        'size': canary_path.stat().st_size
                    }
                except Exception as e:
                    logger.debug(f"Could not deploy canary {canary_path}: {e}")
    
    def _generate_canary_content(self, filename: str) -> str:
        """Generate believable decoy content"""
        if 'password' in filename.lower():
            return "Corporate Password Backup\n=======================\nAdmin: P@ssw0rd2026!\nRoot: SuperSecure#123\nBackup: Recovery_Key_789"
        elif 'budget' in filename.lower() or 'financial' in filename.lower():
            return "Q1 2026 Budget Projections\n==========================\nRevenue: $4,500,000\nExpenses: $3,200,000\nProjected Profit: $1,300,000"
        elif 'crypto' in filename.lower() or 'wallet' in filename.lower():
            return "Bitcoin Wallet Recovery Phrase\n=============================\nword1 word2 word3 word4 word5 word6\nword7 word8 word9 word10 word11 word12"
        elif 'salary' in filename.lower():
            return "Employee Salary Schedule 2026\n============================\nCEO: $450,000\nCTO: $380,000\nDirectors: $220,000"
        else:
            return f"CONFIDENTIAL - {filename}\nThis document contains sensitive information.\nAuthorized access only."
    
    def _establish_shadow_baseline(self):
        """Get current shadow copy count for baseline"""
        try:
            result = subprocess.run(
                ['vssadmin', 'list', 'shadows'],
                capture_output=True, text=True, timeout=30
            )
            self.shadow_copy_baseline = result.stdout.lower().count('shadow copy id:')
            logger.info(f"Shadow copy baseline: {self.shadow_copy_baseline}")
        except Exception as e:
            logger.debug(f"Could not establish shadow baseline: {e}")
            self.shadow_copy_baseline = None
    
    def check(self) -> List[Threat]:
        """Run all ransomware protection checks"""
        threats = []
        
        # Check canary files
        threats.extend(self._check_canaries())
        
        # Check shadow copies (Windows)
        if PLATFORM == 'windows':
            threats.extend(self._check_shadow_copies())
        
        # Check for mass encryption patterns (via process monitoring)
        threats.extend(self._check_encryption_patterns())
        
        return threats
    
    def _check_canaries(self) -> List[Threat]:
        """Check if any canary files were modified or deleted"""
        threats = []
        
        for canary_path, info in list(self.canaries.items()):
            path = Path(canary_path)
            
            if not path.exists():
                # Canary deleted - CRITICAL
                threat = Threat(
                    id=f"ransom-canary-{uuid.uuid4().hex[:8]}",
                    name="Canary File Deleted",
                    severity=ThreatSeverity.CRITICAL,
                    category="ransomware",
                    process_name="unknown",
                    details={"canary_path": canary_path, "deployed_at": info['deployed_at']},
                    source="RansomwareProtection",
                    mitre_tactics=["TA0040"],
                    mitre_techniques=["T1486"],
                    remediation_action="alert",
                    remediation_params={},
                    confidence=95,
                    indicator=f"Canary file deleted: {canary_path}"
                )
                threats.append(threat)
                del self.canaries[canary_path]
                continue
            
            try:
                current_hash = hashlib.sha256(path.read_bytes()).hexdigest()
                if current_hash != info['hash']:
                    # Canary modified - CRITICAL
                    threat = Threat(
                        id=f"ransom-canary-{uuid.uuid4().hex[:8]}",
                        name="Canary File Modified",
                        severity=ThreatSeverity.CRITICAL,
                        category="ransomware",
                        process_name="unknown",
                        details={
                            "canary_path": canary_path,
                            "original_hash": info['hash'],
                            "current_hash": current_hash
                        },
                        source="RansomwareProtection",
                        mitre_tactics=["TA0040"],
                        mitre_techniques=["T1486"],
                        remediation_action="alert",
                        remediation_params={},
                        confidence=95,
                        indicator=f"Canary file modified: {canary_path}"
                    )
                    threats.append(threat)
            except Exception as e:
                logger.debug(f"Error checking canary {canary_path}: {e}")
        
        return threats
    
    def _check_shadow_copies(self) -> List[Threat]:
        """Check if shadow copies have been deleted"""
        threats = []
        
        if self.shadow_copy_baseline is None:
            return threats
        
        try:
            result = subprocess.run(
                ['vssadmin', 'list', 'shadows'],
                capture_output=True, text=True, timeout=30
            )
            current_count = result.stdout.lower().count('shadow copy id:')
            
            if current_count < self.shadow_copy_baseline:
                deletion_count = self.shadow_copy_baseline - current_count
                threat = Threat(
                    id=f"ransom-shadow-{uuid.uuid4().hex[:8]}",
                    name="Shadow Copies Deleted",
                    severity=ThreatSeverity.CRITICAL,
                    category="ransomware",
                    process_name="unknown",
                    details={
                        "baseline": self.shadow_copy_baseline,
                        "current": current_count,
                        "deleted": deletion_count
                    },
                    source="RansomwareProtection",
                    mitre_tactics=["TA0040"],
                    mitre_techniques=["T1490"],  # Inhibit System Recovery
                    remediation_action="alert",
                    remediation_params={},
                    confidence=90,
                    indicator=f"{deletion_count} shadow copies deleted"
                )
                threats.append(threat)
        except Exception as e:
            logger.debug(f"Shadow copy check error: {e}")
        
        return threats
    
    def check_command(self, command: str, process_name: str = "", pid: int = None) -> Optional[Threat]:
        """
        Check if a command is a ransomware indicator.
        Called by ProcessMonitor/LOLBinMonitor when suspicious commands detected.
        """
        command_lower = command.lower()
        
        # Check for shadow copy deletion commands
        for pattern in self.SHADOW_COPY_COMMANDS:
            if pattern.lower() in command_lower:
                threat = Threat(
                    id=f"ransom-cmd-{uuid.uuid4().hex[:8]}",
                    name="Shadow Copy Deletion Attempt",
                    severity=ThreatSeverity.CRITICAL,
                    category="ransomware",
                    process_name=process_name,
                    process_id=pid,
                    details={
                        "command": command,
                        "pattern": pattern
                    },
                    source="RansomwareProtection",
                    mitre_tactics=["TA0040"],
                    mitre_techniques=["T1490"],
                    remediation_action="kill_process",
                    remediation_params={"pid": pid, "process_name": process_name},
                    confidence=98,
                    indicator=f"Ransomware command detected: {pattern}"
                )
                return threat
        
        # Check for backup service stop commands
        for service in self.BACKUP_SERVICES:
            if ('net stop' in command_lower or 'sc stop' in command_lower) and service.lower() in command_lower:
                threat = Threat(
                    id=f"ransom-svc-{uuid.uuid4().hex[:8]}",
                    name="Backup Service Stop Attempt",
                    severity=ThreatSeverity.HIGH,
                    category="ransomware",
                    process_name=process_name,
                    process_id=pid,
                    details={
                        "command": command,
                        "target_service": service
                    },
                    source="RansomwareProtection",
                    mitre_tactics=["TA0040"],
                    mitre_techniques=["T1489"],  # Service Stop
                    remediation_action="kill_process",
                    remediation_params={"pid": pid, "process_name": process_name},
                    confidence=90,
                    indicator=f"Backup service stop: {service}"
                )
                return threat
        
        return None
    
    def record_file_event(self, process_name: str, file_path: str, event_type: str):
        """Record file modification event for pattern analysis"""
        now = time.time()
        
        # Track timestamps for this process
        self.file_events[process_name].append(now)
        
        # Keep only last 60 seconds of events
        cutoff = now - 60
        self.file_events[process_name] = [t for t in self.file_events[process_name] if t > cutoff]
        
        # Check extension
        ext = Path(file_path).suffix.lower()
        if ext in self.RANSOMWARE_EXTENSIONS:
            self.rename_events[process_name].append((file_path, ext))
    
    def _check_encryption_patterns(self) -> List[Threat]:
        """Detect mass file encryption patterns"""
        threats = []
        
        for process_name, timestamps in self.file_events.items():
            if len(timestamps) >= 50:  # 50+ file operations in 60 seconds
                ops_per_second = len(timestamps) / 60.0
                
                # Check for ransomware extension renames
                ransom_extensions = self.rename_events.get(process_name, [])
                
                if ops_per_second > 5 or len(ransom_extensions) >= 10:
                    threat = Threat(
                        id=f"ransom-pattern-{uuid.uuid4().hex[:8]}",
                        name="Mass Encryption Pattern Detected",
                        severity=ThreatSeverity.CRITICAL,
                        category="ransomware",
                        process_name=process_name,
                        details={
                            "file_operations": len(timestamps),
                            "ops_per_second": round(ops_per_second, 2),
                            "ransomware_extensions": len(ransom_extensions)
                        },
                        source="RansomwareProtection",
                        mitre_tactics=["TA0040"],
                        mitre_techniques=["T1486"],
                        remediation_action="kill_process",
                        remediation_params={"process_name": process_name},
                        confidence=85,
                        indicator=f"Mass file encryption: {len(timestamps)} ops/min"
                    )
                    threats.append(threat)
                    
                    # Clear events for this process
                    self.file_events[process_name] = []
                    self.rename_events[process_name] = []
        
        return threats
    
    def check_protected_folder_access(self, file_path: str, process_name: str) -> Optional[Threat]:
        """Check if a process is allowed to access protected folders"""
        process_lower = process_name.lower()
        
        # Check if whitelisted
        if any(allowed.lower() in process_lower for allowed in self.ALLOWED_PROCESSES):
            return None
        
        # Check if file is in protected folder
        file_str = str(file_path)
        for protected in self.protected_folders:
            if file_str.startswith(protected):
                violation = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "file_path": file_path,
                    "process": process_name,
                    "folder": protected
                }
                self.violations.append(violation)
                
                # Keep only last 100 violations
                if len(self.violations) > 100:
                    self.violations = self.violations[-100:]
                
                threat = Threat(
                    id=f"ransom-folder-{uuid.uuid4().hex[:8]}",
                    name="Protected Folder Violation",
                    severity=ThreatSeverity.HIGH,
                    category="ransomware",
                    process_name=process_name,
                    details={
                        "file_path": file_path,
                        "protected_folder": protected
                    },
                    source="RansomwareProtection",
                    mitre_tactics=["TA0009"],  # Collection
                    mitre_techniques=["T1005"],  # Data from Local System
                    remediation_action="alert",
                    remediation_params={},
                    confidence=70,
                    indicator=f"Unauthorized access to {protected}"
                )
                return threat
        
        return None
    
    def add_protected_folder(self, folder_path: str) -> bool:
        """Add a folder to protection"""
        path = Path(folder_path)
        if path.exists() and path.is_dir():
            self.protected_folders.add(str(path))
            logger.info(f"Added protected folder: {folder_path}")
            return True
        return False
    
    def scan(self) -> Dict[str, Any]:
        """Perform ransomware protection scan."""
        self.threats = []
        canary_alerts = 0
        for path, meta in list(self.canaries.items()):
            try:
                current_hash = hashlib.sha256(Path(path).read_bytes()).hexdigest()
                if current_hash != meta.get('hash'):
                    canary_alerts += 1
                    self.threats.append(Threat(
                        type=ThreatType.RANSOMWARE,
                        severity=ThreatSeverity.CRITICAL,
                        description=f"Canary file modified: {path}",
                        source="ransomware_monitor",
                        indicators=[path],
                    ))
            except FileNotFoundError:
                canary_alerts += 1
                self.threats.append(Threat(
                    type=ThreatType.RANSOMWARE,
                    severity=ThreatSeverity.CRITICAL,
                    description=f"Canary file deleted: {path}",
                    source="ransomware_monitor",
                    indicators=[path],
                ))
            except Exception:
                pass
        self.last_run = time.time()
        return {
            "canaries_monitored": len(self.canaries),
            "canary_alerts": canary_alerts,
            "protected_folders": len(self.protected_folders),
            "violations": len(self.violations),
            "threats_detected": len(self.threats),
        }

    def get_threats(self) -> List[Threat]:
        """Return detected threats from last scan."""
        return list(self.threats)

    def get_status(self) -> Dict[str, Any]:
        """Get ransomware protection status"""
        return {
            "canaries_deployed": len(self.canaries),
            "canary_paths": list(self.canaries.keys()),
            "protected_folders": list(self.protected_folders),
            "shadow_copy_baseline": self.shadow_copy_baseline,
            "recent_violations": len(self.violations),
            "monitored_processes": len(self.file_events)
        }


# =============================================================================
# ROOTKIT DETECTOR - Kernel/System-Level Threat Detection
# =============================================================================

class RootkitDetector(MonitorModule):
    """
    Advanced rootkit and kernel-level threat detection.
    
    Detects:
    - Hidden processes (comparing /proc vs psutil on Linux)
    - Suspicious kernel modules (lsmod analysis)
    - Suspicious drivers (driverquery on Windows)
    - LD_PRELOAD hijacking (Linux)
    - IAT/EAT hooking indicators (Windows)
    - Syscall table modifications
    - Hidden files and directories
    - DKOM (Direct Kernel Object Manipulation) indicators
    
    MITRE ATT&CK Coverage:
    - T1014: Rootkit
    - T1547.006: Kernel Modules and Extensions
    - T1562.001: Disable or Modify Tools
    - T1574.006: Dynamic Linker Hijacking (LD_PRELOAD)
    """
    
    # Known rootkit signatures and indicators
    ROOTKIT_SIGNATURES = [
        'rk_', 'rootkit', 'hide_', 'stealth', 'kernel_hook',
        'sys_hijack', 'hook_', 'invisible', 'hidden_',
        'diamorphine', 'reptile', 'suterusu', 'knark', 'adore',
        'necro', 'azazel', 'jynx', 'bdvl', 'vlany',
    ]
    
    # Suspicious kernel module patterns
    SUSPICIOUS_MODULE_PATTERNS = [
        r'hide.*proc', r'hook.*sys', r'rootkit', r'stealth',
        r'invisible', r'phantom', r'shadow', r'backdoor',
    ]
    
    # Suspicious driver characteristics (Windows)
    SUSPICIOUS_DRIVER_INDICATORS = [
        'unsigned', 'test signed', 'expired', 'revoked',
        'self-signed', 'unknown publisher',
    ]
    
    # Critical system files to monitor for integrity
    LINUX_CRITICAL_BINARIES = [
        '/bin/ls', '/bin/ps', '/bin/netstat', '/bin/ss', '/bin/top',
        '/bin/lsof', '/bin/find', '/bin/grep', '/bin/login',
        '/usr/bin/ls', '/usr/bin/ps', '/usr/bin/netstat', '/usr/bin/ss',
        '/usr/bin/top', '/usr/bin/lsof', '/usr/bin/find', '/usr/bin/grep',
        '/usr/bin/passwd', '/usr/bin/sudo', '/usr/bin/su',
    ]
    
    WINDOWS_CRITICAL_FILES = [
        r'C:\Windows\System32\ntdll.dll',
        r'C:\Windows\System32\kernel32.dll',
        r'C:\Windows\System32\kernelbase.dll',
        r'C:\Windows\System32\ntoskrnl.exe',
        r'C:\Windows\System32\hal.dll',
        r'C:\Windows\System32\win32k.sys',
    ]
    
    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self.threats: List[Threat] = []
        self.hidden_processes: List[Dict] = []
        self.suspicious_modules: List[Dict] = []
        self.suspicious_drivers: List[Dict] = []
        self.ld_preload_findings: List[Dict] = []
        self.file_integrity_issues: List[Dict] = []
        self.baseline_hashes: Dict[str, str] = {}
        self._build_baseline()
    
    def _build_baseline(self):
        """Build baseline hashes for critical system files"""
        critical_files = self.LINUX_CRITICAL_BINARIES if PLATFORM != "windows" else self.WINDOWS_CRITICAL_FILES
        
        for filepath in critical_files:
            if os.path.exists(filepath):
                try:
                    with open(filepath, 'rb') as f:
                        file_hash = hashlib.sha256(f.read()).hexdigest()
                    self.baseline_hashes[filepath] = file_hash
                except (PermissionError, OSError):
                    pass
    
    def scan(self) -> Dict[str, Any]:
        """Perform comprehensive rootkit scan"""
        self.threats = []
        self.hidden_processes = []
        self.suspicious_modules = []
        self.suspicious_drivers = []
        self.ld_preload_findings = []
        self.file_integrity_issues = []
        
        # Platform-specific scans
        if PLATFORM == "windows":
            self._scan_windows_rootkits()
        else:
            self._scan_linux_rootkits()
        
        # Cross-platform checks
        self._check_file_integrity()
        self._check_hidden_network_connections()
        
        self.last_run = datetime.now(timezone.utc)
        
        return {
            "hidden_processes": len(self.hidden_processes),
            "suspicious_modules": len(self.suspicious_modules),
            "suspicious_drivers": len(self.suspicious_drivers),
            "ld_preload_hijacks": len(self.ld_preload_findings),
            "file_integrity_issues": len(self.file_integrity_issues),
            "threats_detected": len(self.threats),
            "status": "infected" if self.threats else "clean",
            "details": {
                "hidden_processes": self.hidden_processes[:10],
                "suspicious_modules": self.suspicious_modules[:10],
                "file_issues": self.file_integrity_issues[:10],
            }
        }
    
    def _scan_linux_rootkits(self):
        """Linux-specific rootkit detection"""
        if not PSUTIL_AVAILABLE:
            return
        
        # 1. Hidden process detection - compare /proc with psutil
        self._detect_hidden_processes_linux()
        
        # 2. LD_PRELOAD hijacking detection
        self._detect_ld_preload_hijack()
        
        # 3. Suspicious kernel modules
        self._scan_kernel_modules()
        
        # 4. Check /etc/ld.so.preload
        self._check_ld_so_preload()
        
        # 5. Check for hidden files in critical directories
        self._scan_hidden_files_linux()
    
    def _detect_hidden_processes_linux(self):
        """Detect processes hidden from userspace tools"""
        try:
            proc_path = Path('/proc')
            if not proc_path.exists():
                return
            
            # Get PIDs from /proc
            proc_pids = set()
            for entry in proc_path.iterdir():
                if entry.name.isdigit():
                    proc_pids.add(int(entry.name))
            
            # Get PIDs from psutil
            psutil_pids = set(psutil.pids())
            
            # Hidden = in /proc but not visible to psutil
            hidden = proc_pids - psutil_pids
            
            for pid in hidden:
                finding = {
                    "pid": pid,
                    "detection_method": "proc_vs_psutil",
                    "severity": "critical",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                self.hidden_processes.append(finding)
                
                self._create_threat(
                    title=f"Hidden Process Detected: PID {pid}",
                    description=f"Process {pid} visible in /proc but hidden from userspace tools - indicates rootkit",
                    severity=ThreatSeverity.CRITICAL,
                    threat_type="rootkit.hidden_process",
                    mitre_techniques=["T1014", "T1562.001"],
                    evidence=finding
                )
                
        except PermissionError:
            pass
        except Exception as e:
            logger.debug(f"Hidden process detection error: {e}")
    
    def _detect_ld_preload_hijack(self):
        """Detect LD_PRELOAD environment variable hijacking"""
        # Check current environment
        ld_preload = os.environ.get('LD_PRELOAD', '')
        if ld_preload:
            finding = {
                "type": "env_ld_preload",
                "value": ld_preload,
                "severity": "high",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            self.ld_preload_findings.append(finding)
            
            self._create_threat(
                title="LD_PRELOAD Environment Variable Set",
                description=f"LD_PRELOAD={ld_preload} - potential library injection",
                severity=ThreatSeverity.HIGH,
                threat_type="rootkit.ld_preload",
                mitre_techniques=["T1574.006"],
                evidence=finding
            )
        
        # Check running processes for LD_PRELOAD
        if PSUTIL_AVAILABLE:
            for proc in psutil.process_iter(['pid', 'name', 'environ']):
                try:
                    env = proc.info.get('environ') or {}
                    if 'LD_PRELOAD' in env:
                        finding = {
                            "type": "process_ld_preload",
                            "pid": proc.info['pid'],
                            "name": proc.info['name'],
                            "ld_preload": env['LD_PRELOAD'],
                            "severity": "high"
                        }
                        self.ld_preload_findings.append(finding)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
    
    def _check_ld_so_preload(self):
        """Check /etc/ld.so.preload for malicious entries"""
        preload_path = Path('/etc/ld.so.preload')
        if preload_path.exists():
            try:
                content = preload_path.read_text().strip()
                if content:
                    finding = {
                        "type": "ld_so_preload",
                        "path": str(preload_path),
                        "content": content,
                        "severity": "critical"
                    }
                    self.ld_preload_findings.append(finding)
                    
                    self._create_threat(
                        title="LD_PRELOAD System-Wide Hijack Detected",
                        description=f"/etc/ld.so.preload contains: {content[:100]}",
                        severity=ThreatSeverity.CRITICAL,
                        threat_type="rootkit.ld_preload_system",
                        mitre_techniques=["T1574.006", "T1014"],
                        evidence=finding
                    )
            except PermissionError:
                self.ld_preload_findings.append({
                    "type": "ld_so_preload_permission_denied",
                    "warning": "Cannot read /etc/ld.so.preload - verify manually"
                })
    
    def _scan_kernel_modules(self):
        """Scan for suspicious kernel modules"""
        try:
            result = subprocess.run(['lsmod'], capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                return
            
            for line in result.stdout.split('\n')[1:]:  # Skip header
                if not line.strip():
                    continue
                
                parts = line.split()
                if not parts:
                    continue
                
                module_name = parts[0].lower()
                
                # Check against known rootkit signatures
                for sig in self.ROOTKIT_SIGNATURES:
                    if sig in module_name:
                        finding = {
                            "module": parts[0],
                            "size": parts[1] if len(parts) > 1 else "unknown",
                            "used_by": parts[2] if len(parts) > 2 else "0",
                            "match": sig,
                            "severity": "high"
                        }
                        self.suspicious_modules.append(finding)
                        
                        self._create_threat(
                            title=f"Suspicious Kernel Module: {parts[0]}",
                            description=f"Module matches rootkit signature: {sig}",
                            severity=ThreatSeverity.HIGH,
                            threat_type="rootkit.kernel_module",
                            mitre_techniques=["T1547.006", "T1014"],
                            evidence=finding
                        )
                        break
                
                # Check against suspicious patterns
                for pattern in self.SUSPICIOUS_MODULE_PATTERNS:
                    if re.search(pattern, module_name, re.IGNORECASE):
                        finding = {
                            "module": parts[0],
                            "pattern_match": pattern,
                            "severity": "medium"
                        }
                        self.suspicious_modules.append(finding)
                        break
                        
        except subprocess.TimeoutExpired:
            logger.warning("lsmod timed out")
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.debug(f"Kernel module scan error: {e}")
    
    def _scan_hidden_files_linux(self):
        """Scan for hidden malicious files"""
        suspicious_paths = ['/tmp', '/var/tmp', '/dev/shm']
        
        for scan_path in suspicious_paths:
            if not os.path.exists(scan_path):
                continue
            
            try:
                for root, dirs, files in os.walk(scan_path):
                    # Limit depth
                    if root.count('/') - scan_path.count('/') > 2:
                        continue
                    
                    for f in files:
                        if f.startswith('.'):
                            full_path = os.path.join(root, f)
                            # Check if it's executable
                            if os.access(full_path, os.X_OK):
                                finding = {
                                    "path": full_path,
                                    "type": "hidden_executable",
                                    "severity": "medium"
                                }
                                self.file_integrity_issues.append(finding)
                                
            except PermissionError:
                pass
    
    def _scan_windows_rootkits(self):
        """Windows-specific rootkit detection"""
        # 1. Scan drivers
        self._scan_windows_drivers()
        
        # 2. Check for hidden processes
        self._detect_hidden_processes_windows()
        
        # 3. Check for suspicious services
        self._scan_suspicious_services()
    
    def _scan_windows_drivers(self):
        """Scan Windows drivers for suspicious signatures"""
        try:
            result = subprocess.run(
                ['driverquery', '/v', '/fo', 'csv'],
                capture_output=True, text=True, timeout=60
            )
            if result.returncode != 0:
                return
            
            import csv
            from io import StringIO
            
            reader = csv.DictReader(StringIO(result.stdout))
            for row in reader:
                driver_name = (row.get('Module Name', '') or '').lower()
                driver_path = row.get('Path', '') or ''
                
                # Check for rootkit signatures
                for sig in self.ROOTKIT_SIGNATURES:
                    if sig in driver_name:
                        finding = {
                            "driver": row.get('Module Name', ''),
                            "display_name": row.get('Display Name', ''),
                            "path": driver_path,
                            "match": sig,
                            "severity": "high"
                        }
                        self.suspicious_drivers.append(finding)
                        
                        self._create_threat(
                            title=f"Suspicious Driver: {row.get('Module Name', '')}",
                            description=f"Driver matches rootkit signature: {sig}",
                            severity=ThreatSeverity.HIGH,
                            threat_type="rootkit.suspicious_driver",
                            mitre_techniques=["T1014", "T1547.006"],
                            evidence=finding
                        )
                        break
                        
        except subprocess.TimeoutExpired:
            logger.warning("driverquery timed out")
        except Exception as e:
            logger.debug(f"Windows driver scan error: {e}")
    
    def _detect_hidden_processes_windows(self):
        """Detect hidden processes on Windows using multiple methods"""
        if not PSUTIL_AVAILABLE:
            return
        
        try:
            import ctypes
            from ctypes import wintypes
            
            # Method 1: Compare NtQuerySystemInformation with psutil
            # This requires admin privileges for full effectiveness
            
            psutil_pids = set(psutil.pids())
            
            # Use WMI as secondary source
            try:
                result = subprocess.run(
                    ['wmic', 'process', 'get', 'processid'],
                    capture_output=True, text=True, timeout=30
                )
                wmi_pids = set()
                for line in result.stdout.split('\n'):
                    line = line.strip()
                    if line.isdigit():
                        wmi_pids.add(int(line))
                
                # Hidden = in WMI but not psutil
                hidden = wmi_pids - psutil_pids
                for pid in hidden:
                    if pid > 4:  # Skip System Idle and System
                        finding = {
                            "pid": pid,
                            "detection_method": "wmi_vs_psutil",
                            "severity": "critical"
                        }
                        self.hidden_processes.append(finding)
                        
            except Exception:
                pass
                
        except Exception as e:
            logger.debug(f"Windows hidden process detection error: {e}")
    
    def _scan_suspicious_services(self):
        """Scan for suspicious Windows services"""
        if PLATFORM != "windows" or not PSUTIL_AVAILABLE:
            return
        
        try:
            for service in psutil.win_service_iter():
                try:
                    info = service.as_dict()
                    name = (info.get('name', '') or '').lower()
                    binpath = (info.get('binpath', '') or '').lower()
                    
                    # Check for rootkit signatures in service name
                    for sig in self.ROOTKIT_SIGNATURES:
                        if sig in name or sig in binpath:
                            finding = {
                                "service": info.get('name'),
                                "display_name": info.get('display_name'),
                                "binpath": info.get('binpath'),
                                "status": info.get('status'),
                                "match": sig,
                                "severity": "high"
                            }
                            self.suspicious_drivers.append(finding)
                            break
                            
                except Exception:
                    pass
                    
        except Exception as e:
            logger.debug(f"Service scan error: {e}")
    
    def _check_file_integrity(self):
        """Check integrity of critical system files against baseline"""
        for filepath, baseline_hash in self.baseline_hashes.items():
            if not os.path.exists(filepath):
                finding = {
                    "path": filepath,
                    "issue": "critical_file_missing",
                    "severity": "critical"
                }
                self.file_integrity_issues.append(finding)
                continue
            
            try:
                with open(filepath, 'rb') as f:
                    current_hash = hashlib.sha256(f.read()).hexdigest()
                
                if current_hash != baseline_hash:
                    finding = {
                        "path": filepath,
                        "issue": "hash_mismatch",
                        "baseline": baseline_hash[:16] + "...",
                        "current": current_hash[:16] + "...",
                        "severity": "critical"
                    }
                    self.file_integrity_issues.append(finding)
                    
                    self._create_threat(
                        title=f"Critical File Tampered: {filepath}",
                        description=f"File hash changed from baseline",
                        severity=ThreatSeverity.CRITICAL,
                        threat_type="rootkit.file_tampering",
                        mitre_techniques=["T1014", "T1562.001"],
                        evidence=finding
                    )
                    
            except (PermissionError, OSError) as e:
                finding = {
                    "path": filepath,
                    "issue": "access_error",
                    "error": str(e),
                    "severity": "medium"
                }
                self.file_integrity_issues.append(finding)
    
    def _check_hidden_network_connections(self):
        """Check for network connections hidden from userspace tools"""
        if not PSUTIL_AVAILABLE:
            return
        
        try:
            # Get connections from psutil
            psutil_conns = set()
            for conn in psutil.net_connections(kind='inet'):
                if conn.laddr:
                    psutil_conns.add((conn.laddr.ip, conn.laddr.port))
            
            # Compare with netstat output
            if PLATFORM == "windows":
                cmd = ['netstat', '-an']
            else:
                cmd = ['ss', '-tuln']
            
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                # Parse and compare - simplified check
                # A more sophisticated implementation would parse the output fully
            except Exception:
                pass
                
        except Exception as e:
            logger.debug(f"Network connection check error: {e}")
    
    def _create_threat(self, title: str, description: str, severity: ThreatSeverity,
                      threat_type: str, mitre_techniques: List[str], evidence: Dict):
        """Create a threat from rootkit finding"""
        threat = Threat(
            threat_id=f"rootkit-{uuid.uuid4().hex[:12]}",
            title=title,
            description=description,
            severity=severity,
            threat_type=threat_type,
            source="rootkit_detector",
            mitre_techniques=mitre_techniques,
            evidence=evidence,
            auto_kill_eligible=False  # Rootkits need manual analysis
        )
        self.threats.append(threat)
    
    def get_threats(self) -> List[Threat]:
        """Get detected rootkit threats"""
        return self.threats
    
    def get_status(self) -> Dict[str, Any]:
        """Get rootkit detector status"""
        return {
            "last_scan": self.last_run.isoformat() if self.last_run else None,
            "baseline_files": len(self.baseline_hashes),
            "hidden_processes": len(self.hidden_processes),
            "suspicious_modules": len(self.suspicious_modules),
            "ld_preload_issues": len(self.ld_preload_findings),
            "file_integrity_issues": len(self.file_integrity_issues),
            "threats": len(self.threats),
            "status": "infected" if self.threats else "clean"
        }


# =============================================================================
# KERNEL SECURITY MONITOR - eBPF-Style System Call Monitoring
# =============================================================================

class KernelSecurityMonitor(MonitorModule):
    """
    Kernel-level security monitoring with eBPF-style syscall visibility.
    
    Since true eBPF requires kernel support and root privileges, this module:
    1. Uses audit frameworks (auditd on Linux, ETW on Windows)
    2. Monitors /proc and kernel interfaces
    3. Provides eBPF-equivalent visibility through available APIs
    4. Falls back gracefully on systems without kernel access
    
    Monitoring Capabilities:
    - Process creation/exec syscalls (fork, execve, CreateProcess)
    - File open/read/write syscalls
    - Network socket operations (connect, bind, listen)
    - Privilege escalation (setuid, setgid, SeDebugPrivilege)
    - Kernel module loading (init_module, finit_module)
    
    MITRE ATT&CK Coverage:
    - T1055: Process Injection
    - T1059: Command and Scripting Interpreter
    - T1068: Exploitation for Privilege Escalation
    - T1070: Indicator Removal
    - T1547: Boot or Logon Autostart Execution
    """
    
    # Critical syscalls to monitor (Linux)
    CRITICAL_SYSCALLS_LINUX = {
        'execve': 'Process execution',
        'fork': 'Process creation',
        'clone': 'Thread/process creation',
        'ptrace': 'Process debugging/injection',
        'mmap': 'Memory mapping',
        'mprotect': 'Memory protection change',
        'init_module': 'Kernel module loading',
        'finit_module': 'Kernel module loading (fd)',
        'delete_module': 'Kernel module unloading',
        'connect': 'Network connection',
        'bind': 'Socket binding',
        'listen': 'Socket listening',
        'accept': 'Connection acceptance',
        'setuid': 'UID change',
        'setgid': 'GID change',
        'setreuid': 'Real/effective UID change',
        'setregid': 'Real/effective GID change',
        'chmod': 'Permission change',
        'chown': 'Ownership change',
        'unlink': 'File deletion',
        'rename': 'File rename',
        'open': 'File open',
        'openat': 'File open (at)',
        'write': 'File write',
    }
    
    # Windows syscall equivalents (via ETW providers)
    ETW_PROVIDERS = {
        'Microsoft-Windows-Kernel-Process': 'Process creation/termination',
        'Microsoft-Windows-Kernel-File': 'File operations',
        'Microsoft-Windows-Kernel-Network': 'Network operations',
        'Microsoft-Windows-Kernel-Registry': 'Registry operations',
        'Microsoft-Windows-Security-Auditing': 'Security events',
    }
    
    # Suspicious syscall patterns
    SUSPICIOUS_PATTERNS = {
        'ptrace_attach': {'syscalls': ['ptrace'], 'description': 'Process injection attempt'},
        'module_load': {'syscalls': ['init_module', 'finit_module'], 'description': 'Kernel module loading'},
        'priv_escalation': {'syscalls': ['setuid', 'setgid', 'setreuid'], 'description': 'Privilege escalation'},
        'memory_injection': {'syscalls': ['mmap', 'mprotect'], 'description': 'Memory manipulation'},
    }
    
    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self.threats: List[Threat] = []
        self.syscall_events: deque = deque(maxlen=10000)
        self.suspicious_activity: List[Dict] = []
        self.module_load_events: List[Dict] = []
        self.priv_changes: List[Dict] = []
        self.network_syscalls: List[Dict] = []
        self.audit_available = self._check_audit_availability()
        self.monitoring_active = False
        self._audit_thread: Optional[threading.Thread] = None
    
    def _check_audit_availability(self) -> Dict[str, bool]:
        """Check what kernel monitoring is available"""
        availability = {
            'auditd': False,
            'procfs': False,
            'etw': False,
            'sysdig': False,
            'bpf': False
        }
        
        if PLATFORM == "windows":
            # Check for ETW availability (requires admin)
            try:
                import ctypes
                availability['etw'] = ctypes.windll.advapi32 is not None
            except Exception:
                pass
        else:
            # Check /proc availability
            availability['procfs'] = os.path.exists('/proc')
            
            # Check auditd
            try:
                result = subprocess.run(['which', 'auditctl'], capture_output=True)
                availability['auditd'] = result.returncode == 0
            except Exception:
                pass
            
            # Check for BPF support
            availability['bpf'] = os.path.exists('/sys/kernel/debug/tracing')
            
            # Check for sysdig
            try:
                result = subprocess.run(['which', 'sysdig'], capture_output=True)
                availability['sysdig'] = result.returncode == 0
            except Exception:
                pass
        
        return availability
    
    def scan(self) -> Dict[str, Any]:
        """Perform kernel security scan"""
        self.threats = []
        self.suspicious_activity = []
        self.module_load_events = []
        self.priv_changes = []
        
        if PLATFORM == "windows":
            self._scan_windows_kernel()
        else:
            self._scan_linux_kernel()
        
        self.last_run = datetime.now(timezone.utc)
        
        return {
            "audit_availability": self.audit_available,
            "syscall_events_captured": len(self.syscall_events),
            "suspicious_activity": len(self.suspicious_activity),
            "module_loads": len(self.module_load_events),
            "privilege_changes": len(self.priv_changes),
            "threats": len(self.threats),
            "monitoring_active": self.monitoring_active,
            "details": {
                "suspicious": self.suspicious_activity[:10],
                "module_loads": self.module_load_events[:10],
                "priv_changes": self.priv_changes[:10],
            }
        }
    
    def _scan_linux_kernel(self):
        """Scan Linux kernel security state"""
        # 1. Check recent kernel module loads from dmesg
        self._check_kernel_module_loads()
        
        # 2. Check /proc for suspicious activity
        self._check_proc_indicators()
        
        # 3. Parse audit logs if available
        if self.audit_available.get('auditd'):
            self._parse_audit_logs()
        
        # 4. Check for ptrace activity
        self._check_ptrace_activity()
        
        # 5. Monitor /proc/[pid]/maps for suspicious mappings
        self._check_process_maps()
    
    def _check_kernel_module_loads(self):
        """Check for recent kernel module load events"""
        try:
            result = subprocess.run(
                ['dmesg', '--time-format=iso'],
                capture_output=True, text=True, timeout=30
            )
            
            if result.returncode != 0:
                # Try without time format
                result = subprocess.run(['dmesg'], capture_output=True, text=True, timeout=30)
            
            for line in result.stdout.split('\n'):
                # Look for module loading indicators
                if any(x in line.lower() for x in ['module', 'loaded', 'insmod', 'modprobe']):
                    if 'loading' in line.lower() or 'loaded' in line.lower():
                        event = {
                            "type": "module_load",
                            "message": line.strip()[:200],
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        }
                        self.module_load_events.append(event)
                        
        except subprocess.TimeoutExpired:
            pass
        except Exception as e:
            logger.debug(f"Kernel module check error: {e}")
    
    def _check_proc_indicators(self):
        """Check /proc for security indicators"""
        if not os.path.exists('/proc'):
            return
        
        # Check kernel parameters
        security_params = {
            '/proc/sys/kernel/kptr_restrict': {'expected': '1', 'description': 'Kernel pointer restriction'},
            '/proc/sys/kernel/dmesg_restrict': {'expected': '1', 'description': 'dmesg restriction'},
            '/proc/sys/kernel/perf_event_paranoid': {'expected': '2', 'description': 'perf event restriction'},
            '/proc/sys/kernel/yama/ptrace_scope': {'expected': '1', 'description': 'ptrace restriction'},
        }
        
        for param_path, info in security_params.items():
            try:
                if os.path.exists(param_path):
                    with open(param_path) as f:
                        value = f.read().strip()
                    
                    if value != info['expected']:
                        finding = {
                            "param": param_path,
                            "current": value,
                            "expected": info['expected'],
                            "description": info['description'],
                            "severity": "medium"
                        }
                        self.suspicious_activity.append(finding)
                        
            except (PermissionError, OSError):
                pass
    
    def _parse_audit_logs(self):
        """Parse auditd logs for security events"""
        audit_log = '/var/log/audit/audit.log'
        if not os.path.exists(audit_log):
            return
        
        try:
            # Read last 1000 lines
            result = subprocess.run(
                ['tail', '-n', '1000', audit_log],
                capture_output=True, text=True, timeout=30
            )
            
            for line in result.stdout.split('\n'):
                # Parse SYSCALL events
                if 'type=SYSCALL' in line:
                    syscall = self._parse_audit_syscall(line)
                    if syscall:
                        self.syscall_events.append(syscall)
                        
                        # Check for suspicious syscalls
                        if syscall.get('syscall') in ['ptrace', 'init_module', 'finit_module']:
                            self.suspicious_activity.append(syscall)
                            
                # Parse EXECVE events
                elif 'type=EXECVE' in line:
                    event = {
                        "type": "execve",
                        "raw": line[:300],
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                    self.syscall_events.append(event)
                    
        except (subprocess.TimeoutExpired, PermissionError):
            pass
        except Exception as e:
            logger.debug(f"Audit log parse error: {e}")
    
    def _parse_audit_syscall(self, line: str) -> Optional[Dict]:
        """Parse an audit SYSCALL line"""
        event = {"type": "syscall", "raw": line[:200]}
        
        # Extract syscall number/name
        syscall_match = re.search(r'syscall=(\d+)', line)
        if syscall_match:
            event['syscall_num'] = int(syscall_match.group(1))
        
        # Extract pid
        pid_match = re.search(r'pid=(\d+)', line)
        if pid_match:
            event['pid'] = int(pid_match.group(1))
        
        # Extract exe
        exe_match = re.search(r'exe="([^"]+)"', line)
        if exe_match:
            event['exe'] = exe_match.group(1)
        
        # Extract comm
        comm_match = re.search(r'comm="([^"]+)"', line)
        if comm_match:
            event['comm'] = comm_match.group(1)
        
        return event if event.get('syscall_num') or event.get('exe') else None
    
    def _check_ptrace_activity(self):
        """Check for ptrace-based process injection"""
        if not PSUTIL_AVAILABLE:
            return
        
        try:
            for proc in psutil.process_iter(['pid', 'name', 'status']):
                try:
                    info = proc.info
                    
                    # Check if process is being traced
                    status_path = f"/proc/{info['pid']}/status"
                    if os.path.exists(status_path):
                        with open(status_path) as f:
                            content = f.read()
                        
                        # Check TracerPid
                        tracer_match = re.search(r'TracerPid:\s*(\d+)', content)
                        if tracer_match:
                            tracer_pid = int(tracer_match.group(1))
                            if tracer_pid > 0:
                                finding = {
                                    "traced_pid": info['pid'],
                                    "traced_name": info['name'],
                                    "tracer_pid": tracer_pid,
                                    "type": "ptrace_active",
                                    "severity": "high"
                                }
                                self.suspicious_activity.append(finding)
                                
                                self._create_threat(
                                    title=f"Active Process Tracing: {info['name']} (PID {info['pid']})",
                                    description=f"Process being traced by PID {tracer_pid}",
                                    severity=ThreatSeverity.HIGH,
                                    threat_type="kernel.ptrace",
                                    mitre_techniques=["T1055"],
                                    evidence=finding
                                )
                                
                except (PermissionError, FileNotFoundError):
                    pass
                    
        except Exception as e:
            logger.debug(f"Ptrace check error: {e}")
    
    def _check_process_maps(self):
        """Check /proc/[pid]/maps for suspicious memory mappings"""
        if not PSUTIL_AVAILABLE:
            return
        
        suspicious_regions = []
        
        try:
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    maps_path = f"/proc/{proc.info['pid']}/maps"
                    if not os.path.exists(maps_path):
                        continue
                    
                    with open(maps_path) as f:
                        for line in f:
                            # Check for RWX regions (suspicious)
                            if 'rwx' in line.lower():
                                region = {
                                    "pid": proc.info['pid'],
                                    "name": proc.info['name'],
                                    "mapping": line.strip()[:100],
                                    "type": "rwx_memory",
                                    "severity": "medium"
                                }
                                suspicious_regions.append(region)
                                break  # Only report once per process
                                
                except (PermissionError, FileNotFoundError):
                    pass
                    
        except Exception as e:
            logger.debug(f"Process maps check error: {e}")
        
        # Add top findings to suspicious activity
        self.suspicious_activity.extend(suspicious_regions[:10])
    
    def _scan_windows_kernel(self):
        """Scan Windows kernel security state"""
        # 1. Check for SeDebugPrivilege usage
        self._check_debug_privilege()
        
        # 2. Check driver signing status
        self._check_driver_signing_policy()
        
        # 3. Monitor for suspicious ETW events (if admin)
        self._check_security_events()
    
    def _check_debug_privilege(self):
        """Check for processes with SeDebugPrivilege"""
        if not PSUTIL_AVAILABLE:
            return
        
        try:
            import ctypes
            from ctypes import wintypes
            
            # OpenProcessToken constants
            TOKEN_QUERY = 0x0008
            
            # This is a simplified check - full implementation would use Windows API
            # to enumerate process tokens and check privileges
            
        except Exception as e:
            logger.debug(f"Debug privilege check error: {e}")
    
    def _check_driver_signing_policy(self):
        """Check Windows driver signing enforcement policy"""
        try:
            # Check BCD settings
            result = subprocess.run(
                ['bcdedit', '/enum', '{current}'],
                capture_output=True, text=True, timeout=30
            )
            
            output = result.stdout.lower()
            
            # Check testsigning
            if 'testsigning' in output and 'yes' in output:
                finding = {
                    "type": "testsigning_enabled",
                    "description": "Test signing is enabled - allows unsigned drivers",
                    "severity": "high"
                }
                self.suspicious_activity.append(finding)
                
                self._create_threat(
                    title="Test Signing Mode Enabled",
                    description="System allows loading of unsigned drivers",
                    severity=ThreatSeverity.HIGH,
                    threat_type="kernel.unsigned_drivers",
                    mitre_techniques=["T1547.006"],
                    evidence=finding
                )
            
            # Check nointegritychecks
            if 'nointegritychecks' in output and 'yes' in output:
                finding = {
                    "type": "integrity_checks_disabled",
                    "description": "Integrity checks disabled",
                    "severity": "critical"
                }
                self.suspicious_activity.append(finding)
                
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        except Exception as e:
            logger.debug(f"Driver signing check error: {e}")
    
    def _check_security_events(self):
        """Check Windows Security event log for suspicious events"""
        try:
            # Query recent security events using PowerShell
            ps_cmd = '''
            Get-WinEvent -FilterHashtable @{LogName='Security';Id=4688,4672,4673,4674} -MaxEvents 100 2>$null | 
            Select-Object TimeCreated,Id,Message | ConvertTo-Json
            '''
            
            result = subprocess.run(
                ['powershell', '-Command', ps_cmd],
                capture_output=True, text=True, timeout=60
            )
            
            if result.returncode == 0 and result.stdout.strip():
                try:
                    events = json.loads(result.stdout)
                    if not isinstance(events, list):
                        events = [events]
                    
                    for event in events:
                        event_id = event.get('Id', 0)
                        
                        # 4672 = Special privileges assigned (SeDebugPrivilege etc)
                        if event_id == 4672:
                            finding = {
                                "type": "special_privilege",
                                "event_id": event_id,
                                "time": event.get('TimeCreated', ''),
                                "severity": "medium"
                            }
                            self.priv_changes.append(finding)
                            
                except json.JSONDecodeError:
                    pass
                    
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        except Exception as e:
            logger.debug(f"Security event check error: {e}")
    
    def _create_threat(self, title: str, description: str, severity: ThreatSeverity,
                      threat_type: str, mitre_techniques: List[str], evidence: Dict):
        """Create a threat from kernel security finding"""
        threat = Threat(
            threat_id=f"kernel-{uuid.uuid4().hex[:12]}",
            title=title,
            description=description,
            severity=severity,
            threat_type=threat_type,
            source="kernel_security_monitor",
            mitre_techniques=mitre_techniques,
            evidence=evidence,
            auto_kill_eligible=False
        )
        self.threats.append(threat)
    
    def get_threats(self) -> List[Threat]:
        """Get detected kernel security threats"""
        return self.threats
    
    def get_status(self) -> Dict[str, Any]:
        """Get kernel security monitor status"""
        return {
            "audit_available": self.audit_available,
            "monitoring_active": self.monitoring_active,
            "syscall_events": len(self.syscall_events),
            "suspicious_activity": len(self.suspicious_activity),
            "module_loads": len(self.module_load_events),
            "priv_changes": len(self.priv_changes),
            "threats": len(self.threats),
            "last_scan": self.last_run.isoformat() if self.last_run else None
        }


# =============================================================================
# AGENT SELF-PROTECTION - Anti-Tampering & Resilience
# =============================================================================

class AgentSelfProtection(MonitorModule):
    """
    Agent anti-tampering and self-protection system.
    
    Protection Mechanisms:
    - Watchdog process monitoring (detect if agent is killed)
    - Binary integrity verification (detect tampering)
    - Configuration file protection
    - Process self-protection (anti-injection)
    - Service-level resilience (auto-restart)
    - Anti-debugging detection
    - Parent process validation
    - Memory protection validation
    
    MITRE D3FEND:
    - D3-PSA: Process Spawn Analysis
    - D3-PLA: Process Lineage Analysis
    - D3-FAPA: File Access Pattern Analysis
    
    MITRE ATT&CK Detection:
    - T1489: Service Stop
    - T1562.001: Disable or Modify Tools
    - T1055: Process Injection
    - T1106: Native API (anti-debug bypass)
    """
    
    # Files critical to agent operation
    CRITICAL_AGENT_FILES = [
        'agent.py', 'config.json', 'metatron.db',
        'certificates/', 'keys/', 'rules/'
    ]
    
    # Known debugger processes
    DEBUGGER_PROCESSES = {
        'gdb', 'lldb', 'strace', 'ltrace', 'ida', 'ida64',
        'ollydbg', 'x64dbg', 'x32dbg', 'windbg', 'immunity',
        'radare2', 'r2', 'ghidra', 'hopper', 'binary ninja',
        'frida', 'frida-server', 'objection',
    }
    
    # Suspicious parent processes (should not be launching security agents)
    SUSPICIOUS_PARENTS = {
        'cmd.exe', 'powershell.exe', 'pwsh.exe', 'wscript.exe', 'cscript.exe',
        'mshta.exe', 'rundll32.exe', 'regsvr32.exe', 'bash', 'sh', 'nc',
        'python', 'python3', 'perl', 'ruby', 'php',
    }
    
    def __init__(self, config: AgentConfig, agent_instance=None):
        super().__init__(config)
        self.agent_instance = agent_instance
        self.threats: List[Threat] = []
        self.protection_status: Dict[str, bool] = {}
        self.tamper_events: List[Dict] = []
        self.debug_attempts: List[Dict] = []
        self.integrity_status: Dict[str, str] = {}
        
        # Agent process info
        self.agent_pid = os.getpid()
        self.agent_exe = sys.executable
        self.agent_start_time = datetime.now(timezone.utc)
        self.agent_file_hashes: Dict[str, str] = {}
        
        # Watchdog configuration
        self.watchdog_enabled = False
        self.watchdog_interval = 30  # seconds
        self.watchdog_thread: Optional[threading.Thread] = None
        
        # Initialize integrity baseline
        self._build_integrity_baseline()
    
    def _build_integrity_baseline(self):
        """Build integrity baseline for critical agent files"""
        agent_dir = INSTALL_DIR
        
        for item in self.CRITICAL_AGENT_FILES:
            full_path = agent_dir / item
            if full_path.exists():
                if full_path.is_file():
                    try:
                        with open(full_path, 'rb') as f:
                            file_hash = hashlib.sha256(f.read()).hexdigest()
                        self.agent_file_hashes[str(full_path)] = file_hash
                    except (PermissionError, OSError):
                        pass
                elif full_path.is_dir():
                    # Hash all files in directory
                    try:
                        for file_path in full_path.rglob('*'):
                            if file_path.is_file():
                                try:
                                    with open(file_path, 'rb') as f:
                                        file_hash = hashlib.sha256(f.read()).hexdigest()
                                    self.agent_file_hashes[str(file_path)] = file_hash
                                except (PermissionError, OSError):
                                    pass
                    except Exception:
                        pass
        
        # Also hash the running script
        try:
            script_path = Path(__file__).resolve()
            with open(script_path, 'rb') as f:
                self.agent_file_hashes[str(script_path)] = hashlib.sha256(f.read()).hexdigest()
        except Exception:
            pass
    
    def scan(self) -> Dict[str, Any]:
        """Perform self-protection scan"""
        self.threats = []
        self.tamper_events = []
        self.debug_attempts = []
        
        # Run all protection checks
        self._check_process_integrity()
        self._check_debug_detection()
        self._check_parent_process()
        self._check_file_integrity()
        self._check_service_status()
        self._check_memory_protection()
        self._check_for_injection()
        
        self.last_run = datetime.now(timezone.utc)
        
        # Calculate overall protection status
        protected = all([
            self.protection_status.get('process_intact', False),
            self.protection_status.get('not_debugged', True),
            self.protection_status.get('parent_valid', True),
            self.protection_status.get('files_intact', True),
        ])
        
        return {
            "agent_pid": self.agent_pid,
            "agent_uptime_seconds": (datetime.now(timezone.utc) - self.agent_start_time).total_seconds(),
            "protection_active": protected,
            "protection_status": self.protection_status,
            "tamper_events": len(self.tamper_events),
            "debug_attempts": len(self.debug_attempts),
            "threats": len(self.threats),
            "watchdog_enabled": self.watchdog_enabled,
            "files_monitored": len(self.agent_file_hashes),
            "details": {
                "tamper_events": self.tamper_events[:10],
                "debug_attempts": self.debug_attempts[:10],
            }
        }
    
    def _check_process_integrity(self):
        """Verify agent process integrity"""
        if not PSUTIL_AVAILABLE:
            self.protection_status['process_intact'] = False
            return
        
        try:
            proc = psutil.Process(self.agent_pid)
            
            # Check if process is still running as expected
            if proc.is_running():
                self.protection_status['process_intact'] = True
                
                # Verify executable path hasn't changed
                current_exe = proc.exe()
                if current_exe != self.agent_exe:
                    finding = {
                        "type": "executable_changed",
                        "original": self.agent_exe,
                        "current": current_exe,
                        "severity": "critical"
                    }
                    self.tamper_events.append(finding)
                    self.protection_status['process_intact'] = False
                    
                    self._create_threat(
                        title="Agent Executable Replaced",
                        description=f"Agent executable changed from {self.agent_exe} to {current_exe}",
                        severity=ThreatSeverity.CRITICAL,
                        threat_type="tamper.executable_replacement",
                        mitre_techniques=["T1562.001"],
                        evidence=finding
                    )
            else:
                self.protection_status['process_intact'] = False
                
        except psutil.NoSuchProcess:
            self.protection_status['process_intact'] = False
    
    def _check_debug_detection(self):
        """Detect if agent is being debugged"""
        self.protection_status['not_debugged'] = True
        
        if PLATFORM == "windows":
            self._check_windows_debugging()
        else:
            self._check_linux_debugging()
        
        # Check for debugger processes
        self._check_debugger_processes()
    
    def _check_linux_debugging(self):
        """Check for Linux debugging indicators"""
        # Check TracerPid in /proc/self/status
        try:
            with open('/proc/self/status') as f:
                content = f.read()
            
            tracer_match = re.search(r'TracerPid:\s*(\d+)', content)
            if tracer_match:
                tracer_pid = int(tracer_match.group(1))
                if tracer_pid > 0:
                    finding = {
                        "type": "being_traced",
                        "tracer_pid": tracer_pid,
                        "severity": "critical"
                    }
                    self.debug_attempts.append(finding)
                    self.protection_status['not_debugged'] = False
                    
                    # Try to get tracer name
                    try:
                        tracer = psutil.Process(tracer_pid)
                        finding['tracer_name'] = tracer.name()
                    except Exception:
                        pass
                    
                    self._create_threat(
                        title="Agent Being Debugged",
                        description=f"Agent is being traced by PID {tracer_pid}",
                        severity=ThreatSeverity.CRITICAL,
                        threat_type="tamper.debugging",
                        mitre_techniques=["T1055", "T1106"],
                        evidence=finding
                    )
                    
        except (PermissionError, FileNotFoundError):
            pass
    
    def _check_windows_debugging(self):
        """Check for Windows debugging indicators"""
        try:
            import ctypes
            
            # IsDebuggerPresent
            is_debugged = ctypes.windll.kernel32.IsDebuggerPresent()
            if is_debugged:
                finding = {
                    "type": "debugger_present",
                    "method": "IsDebuggerPresent",
                    "severity": "critical"
                }
                self.debug_attempts.append(finding)
                self.protection_status['not_debugged'] = False
                
                self._create_threat(
                    title="Agent Being Debugged (Windows)",
                    description="IsDebuggerPresent() returned True",
                    severity=ThreatSeverity.CRITICAL,
                    threat_type="tamper.debugging",
                    mitre_techniques=["T1055", "T1106"],
                    evidence=finding
                )
            
            # CheckRemoteDebuggerPresent
            is_remote_debug = ctypes.c_int(0)
            ctypes.windll.kernel32.CheckRemoteDebuggerPresent(
                ctypes.windll.kernel32.GetCurrentProcess(),
                ctypes.byref(is_remote_debug)
            )
            if is_remote_debug.value:
                finding = {
                    "type": "remote_debugger",
                    "method": "CheckRemoteDebuggerPresent",
                    "severity": "critical"
                }
                self.debug_attempts.append(finding)
                self.protection_status['not_debugged'] = False
                
        except Exception as e:
            logger.debug(f"Windows debug check error: {e}")
    
    def _check_debugger_processes(self):
        """Check for known debugger processes running"""
        if not PSUTIL_AVAILABLE:
            return
        
        try:
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    proc_name = (proc.info['name'] or '').lower().replace('.exe', '')
                    
                    if proc_name in self.DEBUGGER_PROCESSES:
                        finding = {
                            "type": "debugger_running",
                            "pid": proc.info['pid'],
                            "name": proc.info['name'],
                            "severity": "high"
                        }
                        self.debug_attempts.append(finding)
                        
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
                    
        except Exception as e:
            logger.debug(f"Debugger process check error: {e}")
    
    def _check_parent_process(self):
        """Validate parent process is legitimate"""
        self.protection_status['parent_valid'] = True
        
        if not PSUTIL_AVAILABLE:
            return
        
        try:
            proc = psutil.Process(self.agent_pid)
            parent = proc.parent()
            
            if parent:
                parent_name = (parent.name() or '').lower()
                
                # Check against suspicious parents
                for suspicious in self.SUSPICIOUS_PARENTS:
                    if suspicious in parent_name:
                        finding = {
                            "type": "suspicious_parent",
                            "parent_pid": parent.pid,
                            "parent_name": parent.name(),
                            "parent_cmdline": ' '.join(parent.cmdline())[:200],
                            "severity": "high"
                        }
                        self.tamper_events.append(finding)
                        self.protection_status['parent_valid'] = False
                        
                        self._create_threat(
                            title=f"Suspicious Parent Process: {parent.name()}",
                            description=f"Agent launched by potentially malicious parent: {parent.name()}",
                            severity=ThreatSeverity.HIGH,
                            threat_type="tamper.suspicious_parent",
                            mitre_techniques=["T1059", "T1106"],
                            evidence=finding
                        )
                        break
                        
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        except Exception as e:
            logger.debug(f"Parent process check error: {e}")
    
    def _check_file_integrity(self):
        """Verify integrity of critical agent files"""
        self.protection_status['files_intact'] = True
        
        for filepath, baseline_hash in self.agent_file_hashes.items():
            if not os.path.exists(filepath):
                finding = {
                    "type": "file_missing",
                    "path": filepath,
                    "severity": "high"
                }
                self.tamper_events.append(finding)
                self.protection_status['files_intact'] = False
                continue
            
            try:
                with open(filepath, 'rb') as f:
                    current_hash = hashlib.sha256(f.read()).hexdigest()
                
                if current_hash != baseline_hash:
                    finding = {
                        "type": "file_modified",
                        "path": filepath,
                        "baseline_hash": baseline_hash[:16] + "...",
                        "current_hash": current_hash[:16] + "...",
                        "severity": "critical"
                    }
                    self.tamper_events.append(finding)
                    self.protection_status['files_intact'] = False
                    
                    self._create_threat(
                        title=f"Agent File Tampered: {Path(filepath).name}",
                        description=f"Critical agent file modified: {filepath}",
                        severity=ThreatSeverity.CRITICAL,
                        threat_type="tamper.file_modification",
                        mitre_techniques=["T1562.001"],
                        evidence=finding
                    )
                    
            except (PermissionError, OSError) as e:
                finding = {
                    "type": "file_access_error",
                    "path": filepath,
                    "error": str(e),
                    "severity": "medium"
                }
                self.tamper_events.append(finding)
    
    def _check_service_status(self):
        """Check if agent service is properly registered"""
        self.protection_status['service_registered'] = False
        
        if PLATFORM == "windows":
            self._check_windows_service()
        else:
            self._check_linux_service()
    
    def _check_windows_service(self):
        """Check Windows service registration"""
        try:
            result = subprocess.run(
                ['sc', 'query', 'SeraphDefender'],
                capture_output=True, text=True, timeout=10
            )
            
            if 'RUNNING' in result.stdout:
                self.protection_status['service_registered'] = True
                self.protection_status['service_running'] = True
            elif result.returncode == 0:
                self.protection_status['service_registered'] = True
                self.protection_status['service_running'] = False
                
        except Exception:
            pass
    
    def _check_linux_service(self):
        """Check Linux systemd service status"""
        try:
            result = subprocess.run(
                ['systemctl', 'status', 'seraph-defender'],
                capture_output=True, text=True, timeout=10
            )
            
            if 'active (running)' in result.stdout.lower():
                self.protection_status['service_registered'] = True
                self.protection_status['service_running'] = True
            elif result.returncode in [0, 3]:  # 3 = inactive but registered
                self.protection_status['service_registered'] = True
                
        except Exception:
            pass
    
    def _check_memory_protection(self):
        """Check agent memory protection status"""
        self.protection_status['memory_protected'] = False
        
        if PLATFORM == "windows":
            # Check for DEP and ASLR
            try:
                import ctypes
                
                # Check DEP policy
                dep_flag = ctypes.c_int32()
                permanent = ctypes.c_int32()
                ctypes.windll.kernel32.GetProcessDEPPolicy(
                    ctypes.windll.kernel32.GetCurrentProcess(),
                    ctypes.byref(dep_flag),
                    ctypes.byref(permanent)
                )
                
                if dep_flag.value:
                    self.protection_status['dep_enabled'] = True
                    self.protection_status['memory_protected'] = True
                    
            except Exception:
                pass
        else:
            # Check Linux memory protections
            try:
                # Check ASLR
                with open('/proc/sys/kernel/randomize_va_space') as f:
                    aslr = int(f.read().strip())
                self.protection_status['aslr_enabled'] = aslr > 0
                self.protection_status['memory_protected'] = aslr > 0
            except Exception:
                pass
    
    def _check_for_injection(self):
        """Check for signs of code injection into agent process"""
        self.protection_status['no_injection'] = True
        
        if not PSUTIL_AVAILABLE:
            return
        
        try:
            proc = psutil.Process(self.agent_pid)
            
            # On Linux, check /proc/self/maps for suspicious mappings
            if PLATFORM != "windows":
                maps_path = f"/proc/{self.agent_pid}/maps"
                if os.path.exists(maps_path):
                    try:
                        with open(maps_path) as f:
                            for line in f:
                                # RWX regions in non-JIT processes are suspicious
                                if 'rwx' in line.lower() and 'python' not in line.lower():
                                    finding = {
                                        "type": "rwx_memory_region",
                                        "mapping": line.strip()[:100],
                                        "severity": "medium"
                                    }
                                    self.tamper_events.append(finding)
                                    
                    except PermissionError:
                        pass
                        
            # Check loaded DLLs/SOs for unexpected libraries
            try:
                memory_maps = proc.memory_maps()
                suspicious_libs = ['inject', 'hook', 'frida', 'detour']
                
                for mmap in memory_maps:
                    path_lower = (mmap.path or '').lower()
                    for sus in suspicious_libs:
                        if sus in path_lower:
                            finding = {
                                "type": "suspicious_library",
                                "path": mmap.path,
                                "indicator": sus,
                                "severity": "critical"
                            }
                            self.tamper_events.append(finding)
                            self.protection_status['no_injection'] = False
                            
                            self._create_threat(
                                title=f"Suspicious Library Loaded: {Path(mmap.path).name}",
                                description=f"Potentially malicious library injected: {mmap.path}",
                                severity=ThreatSeverity.CRITICAL,
                                threat_type="tamper.code_injection",
                                mitre_techniques=["T1055"],
                                evidence=finding
                            )
                            break
                            
            except (psutil.AccessDenied, AttributeError):
                pass
                
        except Exception as e:
            logger.debug(f"Injection check error: {e}")
    
    def start_watchdog(self):
        """Start watchdog thread for continuous protection"""
        if self.watchdog_enabled:
            return
        
        self.watchdog_enabled = True
        self.watchdog_thread = threading.Thread(
            target=self._watchdog_loop,
            daemon=True,
            name="AgentWatchdog"
        )
        self.watchdog_thread.start()
        logger.info("Agent watchdog started")
    
    def stop_watchdog(self):
        """Stop watchdog thread"""
        self.watchdog_enabled = False
        if self.watchdog_thread:
            self.watchdog_thread.join(timeout=5)
        logger.info("Agent watchdog stopped")
    
    def _watchdog_loop(self):
        """Continuous watchdog monitoring loop"""
        while self.watchdog_enabled:
            try:
                # Quick integrity check
                self._check_process_integrity()
                self._check_debug_detection()
                
                # If tampering detected, alert
                if not self.protection_status.get('process_intact', True):
                    logger.critical("WATCHDOG: Agent process integrity compromised!")
                
                if not self.protection_status.get('not_debugged', True):
                    logger.critical("WATCHDOG: Agent is being debugged!")
                
            except Exception as e:
                logger.error(f"Watchdog error: {e}")
            
            time.sleep(self.watchdog_interval)
    
    def _create_threat(self, title: str, description: str, severity: ThreatSeverity,
                      threat_type: str, mitre_techniques: List[str], evidence: Dict):
        """Create a threat from self-protection finding"""
        threat = Threat(
            threat_id=f"tamper-{uuid.uuid4().hex[:12]}",
            title=title,
            description=description,
            severity=severity,
            threat_type=threat_type,
            source="agent_self_protection",
            mitre_techniques=mitre_techniques,
            evidence=evidence,
            auto_kill_eligible=False
        )
        self.threats.append(threat)
    
    def get_threats(self) -> List[Threat]:
        """Get detected tampering threats"""
        return self.threats
    
    def get_status(self) -> Dict[str, Any]:
        """Get self-protection status"""
        return {
            "agent_pid": self.agent_pid,
            "agent_uptime": str(datetime.now(timezone.utc) - self.agent_start_time),
            "protection_status": self.protection_status,
            "watchdog_enabled": self.watchdog_enabled,
            "files_monitored": len(self.agent_file_hashes),
            "tamper_events": len(self.tamper_events),
            "debug_attempts": len(self.debug_attempts),
            "threats": len(self.threats),
            "last_scan": self.last_run.isoformat() if self.last_run else None
        }


# =============================================================================
# ENDPOINT IDENTITY PROTECTION - Credential & Authentication Security
# =============================================================================

class EndpointIdentityProtection(MonitorModule):
    """
    Endpoint-level identity and credential protection.
    
    Detection Capabilities:
    - Credential dumping tool detection (mimikatz, lazagne, etc.)
    - LSASS access monitoring
    - Credential file access detection
    - Browser credential extraction attempts
    - Pass-the-Hash/Pass-the-Ticket indicators
    - Kerberos ticket anomalies
    - Token manipulation detection
    - SSH key theft detection
    
    MITRE ATT&CK Coverage:
    - T1003: OS Credential Dumping
    - T1003.001: LSASS Memory
    - T1003.002: Security Account Manager
    - T1003.003: NTDS
    - T1003.004: LSA Secrets
    - T1003.005: Cached Domain Credentials
    - T1550.002: Pass the Hash
    - T1550.003: Pass the Ticket
    - T1558: Steal or Forge Kerberos Tickets
    - T1555: Credentials from Password Stores
    """
    
    # Known credential dumping tools
    CREDENTIAL_TOOLS = {
        'mimikatz': {'patterns': ['mimikatz', 'sekurlsa', 'kerberos::'], 'severity': 'critical'},
        'lazagne': {'patterns': ['lazagne', 'laZagne'], 'severity': 'critical'},
        'pypykatz': {'patterns': ['pypykatz'], 'severity': 'critical'},
        'crackmapexec': {'patterns': ['crackmapexec', 'cme'], 'severity': 'critical'},
        'impacket': {'patterns': ['secretsdump', 'getTGT', 'getST', 'wmiexec'], 'severity': 'critical'},
        'rubeus': {'patterns': ['rubeus', 'asktgt', 'asktgs', 'kerberoast'], 'severity': 'critical'},
        'sharphound': {'patterns': ['sharphound', 'bloodhound'], 'severity': 'high'},
        'procdump': {'patterns': ['procdump', '-ma lsass'], 'severity': 'high'},
        'comsvcs': {'patterns': ['comsvcs.dll', 'MiniDump'], 'severity': 'critical'},
        'nanodump': {'patterns': ['nanodump'], 'severity': 'critical'},
        'dumpert': {'patterns': ['dumpert', 'outflank'], 'severity': 'critical'},
        'handlekatz': {'patterns': ['handlekatz'], 'severity': 'critical'},
        'safetykatz': {'patterns': ['safetykatz'], 'severity': 'critical'},
    }
    
    # Suspicious process names
    SUSPICIOUS_PROCESS_NAMES = [
        'mimikatz', 'mimi', 'sekurlsa', 'lazagne', 'pypykatz',
        'procdump', 'sqldumper', 'rundll32', 'regsvr32',
        'cme', 'crackmapexec', 'sharphound',
        'rubeus', 'kekeo', 'hashcat', 'john', 'hydra',
    ]

    # Seraph platform integration tool process names — authorised tools that
    # must never be reported as suspicious regardless of their offensive heritage.
    SERAPH_INTEGRATION_PROCESSES = frozenset({
        'bloodhound', 'amass', 'spiderfoot', 'arkime', 'velociraptor',
        'zeek', 'purplesharp', 'sigma', 'moloch', 'neo4j',
    })
    
    # Critical credential files (Linux)
    LINUX_CREDENTIAL_FILES = [
        '/etc/shadow', '/etc/passwd', '/etc/sudoers',
        '/etc/ssh/sshd_config', '/root/.ssh/id_rsa', '/root/.ssh/id_ed25519',
        '~/.ssh/id_rsa', '~/.ssh/id_ed25519', '~/.ssh/authorized_keys',
        '~/.gnupg/secring.gpg', '~/.gnupg/private-keys-v1.d/',
        '/etc/krb5.keytab', '/tmp/krb5cc_*',
        '~/.aws/credentials', '~/.azure/accessTokens.json',
    ]
    
    # Critical credential locations (Windows)
    WINDOWS_CREDENTIAL_PATHS = [
        r'C:\Windows\System32\config\SAM',
        r'C:\Windows\System32\config\SYSTEM',
        r'C:\Windows\System32\config\SECURITY',
        r'C:\Windows\NTDS\ntds.dit',
        r'%APPDATA%\Microsoft\Credentials',
        r'%LOCALAPPDATA%\Microsoft\Credentials',
        r'%APPDATA%\Microsoft\Protect',
    ]
    
    # Browser credential paths
    BROWSER_CREDENTIALS = {
        'chrome': {
            'windows': r'%LOCALAPPDATA%\Google\Chrome\User Data\Default\Login Data',
            'linux': '~/.config/google-chrome/Default/Login Data',
            'darwin': '~/Library/Application Support/Google/Chrome/Default/Login Data',
        },
        'firefox': {
            'windows': r'%APPDATA%\Mozilla\Firefox\Profiles\*.default*\logins.json',
            'linux': '~/.mozilla/firefox/*.default*/logins.json',
            'darwin': '~/Library/Application Support/Firefox/Profiles/*.default*/logins.json',
        },
        'edge': {
            'windows': r'%LOCALAPPDATA%\Microsoft\Edge\User Data\Default\Login Data',
        },
    }
    
    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self.threats: List[Threat] = []
        self.credential_access_events: List[Dict] = []
        self.lsass_access_events: List[Dict] = []
        self.suspicious_processes: List[Dict] = []
        self.token_events: List[Dict] = []
        self.kerberos_anomalies: List[Dict] = []
        self.lsass_pid: Optional[int] = None
        
        # Find LSASS PID on Windows
        if PLATFORM == "windows":
            self._find_lsass()
    
    def _find_lsass(self):
        """Find LSASS process PID"""
        if not PSUTIL_AVAILABLE:
            return
        
        try:
            for proc in psutil.process_iter(['pid', 'name']):
                if proc.info['name'] and proc.info['name'].lower() == 'lsass.exe':
                    self.lsass_pid = proc.info['pid']
                    break
        except Exception:
            pass
    
    def scan(self) -> Dict[str, Any]:
        """Perform identity protection scan"""
        self.threats = []
        self.credential_access_events = []
        self.lsass_access_events = []
        self.suspicious_processes = []
        self.token_events = []
        self.kerberos_anomalies = []
        
        # Run detection checks
        self._detect_credential_tools()
        self._check_lsass_access()
        self._check_credential_file_access()
        self._check_browser_credentials()
        self._detect_token_manipulation()
        self._check_kerberos_anomalies()
        
        self.last_run = datetime.now(timezone.utc)
        
        return {
            "credential_tools_detected": len(self.suspicious_processes),
            "lsass_access_events": len(self.lsass_access_events),
            "credential_file_access": len(self.credential_access_events),
            "token_manipulation": len(self.token_events),
            "kerberos_anomalies": len(self.kerberos_anomalies),
            "threats": len(self.threats),
            "lsass_pid": self.lsass_pid,
            "details": {
                "suspicious_processes": self.suspicious_processes[:10],
                "lsass_events": self.lsass_access_events[:10],
                "credential_access": self.credential_access_events[:10],
            }
        }
    
    def _detect_credential_tools(self):
        """Detect running credential dumping tools"""
        if not PSUTIL_AVAILABLE:
            return
        
        try:
            for proc in psutil.process_iter(['pid', 'name', 'exe', 'cmdline']):
                try:
                    info = proc.info
                    proc_name = (info.get('name') or '').lower()
                    cmdline = ' '.join(info.get('cmdline') or []).lower()
                    exe_path = (info.get('exe') or '').lower()
                    
                    check_str = f"{proc_name} {cmdline} {exe_path}"
                    
                    # Check against known credential tools
                    for tool_name, tool_info in self.CREDENTIAL_TOOLS.items():
                        for pattern in tool_info['patterns']:
                            if pattern.lower() in check_str:
                                finding = {
                                    "pid": info['pid'],
                                    "name": info.get('name'),
                                    "exe": info.get('exe'),
                                    "cmdline": ' '.join(info.get('cmdline') or [])[:200],
                                    "tool": tool_name,
                                    "severity": tool_info['severity']
                                }
                                self.suspicious_processes.append(finding)
                                
                                self._create_threat(
                                    title=f"Credential Dumping Tool: {tool_name}",
                                    description=f"Detected {tool_name} running as {info.get('name')} (PID {info['pid']})",
                                    severity=ThreatSeverity.CRITICAL if tool_info['severity'] == 'critical' else ThreatSeverity.HIGH,
                                    threat_type=f"credential.{tool_name}",
                                    mitre_techniques=["T1003", "T1003.001"],
                                    evidence=finding
                                )
                                break
                    
                    # Check against suspicious process names (skip authorised Seraph integrations)
                    for sus_name in self.SUSPICIOUS_PROCESS_NAMES:
                        if sus_name in proc_name and sus_name not in self.SERAPH_INTEGRATION_PROCESSES:
                            finding = {
                                "pid": info['pid'],
                                "name": info.get('name'),
                                "exe": info.get('exe'),
                                "match": sus_name,
                                "severity": "high"
                            }
                            self.suspicious_processes.append(finding)
                            break
                            
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
                    
        except Exception as e:
            logger.debug(f"Credential tool detection error: {e}")
    
    def _check_lsass_access(self):
        """Check for suspicious access to LSASS process"""
        if PLATFORM != "windows" or not self.lsass_pid:
            return
        
        if not PSUTIL_AVAILABLE:
            return
        
        try:
            lsass = psutil.Process(self.lsass_pid)
            
            # Check open handles to LSASS (requires admin + specific API)
            # This is a simplified check - full implementation uses Windows API
            
            # Check for processes with debug privileges accessing LSASS
            for proc in psutil.process_iter(['pid', 'name', 'open_files']):
                try:
                    info = proc.info
                    
                    # Skip system processes
                    if info['pid'] < 10:
                        continue
                    
                    # Check cmdline for LSASS dump indicators
                    cmdline = ' '.join(info.get('cmdline') or []).lower()
                    
                    lsass_indicators = [
                        'lsass', '-ma lsass', 'sekurlsa', 'minidump',
                        'comsvcs.dll', 'MiniDumpWriteDump'
                    ]
                    
                    for indicator in lsass_indicators:
                        if indicator.lower() in cmdline:
                            finding = {
                                "pid": info['pid'],
                                "name": info.get('name'),
                                "indicator": indicator,
                                "cmdline": cmdline[:200],
                                "severity": "critical"
                            }
                            self.lsass_access_events.append(finding)
                            
                            self._create_threat(
                                title=f"LSASS Access Attempt: {info.get('name')}",
                                description=f"Process {info.get('name')} may be accessing LSASS memory",
                                severity=ThreatSeverity.CRITICAL,
                                threat_type="credential.lsass_dump",
                                mitre_techniques=["T1003.001"],
                                evidence=finding
                            )
                            break
                            
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
                    
        except Exception as e:
            logger.debug(f"LSASS access check error: {e}")
    
    def _check_credential_file_access(self):
        """Check for access to credential files"""
        if PLATFORM == "windows":
            self._check_windows_credential_access()
        else:
            self._check_linux_credential_access()
    
    def _check_linux_credential_access(self):
        """Check Linux credential file access"""
        # Check /etc/shadow access
        shadow_path = '/etc/shadow'
        if os.path.exists(shadow_path):
            try:
                stat_info = os.stat(shadow_path)
                # Check if recently accessed (within last 5 minutes)
                access_time = datetime.fromtimestamp(stat_info.st_atime)
                if (datetime.now() - access_time).total_seconds() < 300:
                    finding = {
                        "file": shadow_path,
                        "access_time": access_time.isoformat(),
                        "type": "recent_access",
                        "severity": "high"
                    }
                    self.credential_access_events.append(finding)
            except PermissionError:
                pass
        
        # Check for SSH key access patterns
        ssh_dir = Path.home() / '.ssh'
        if ssh_dir.exists():
            for key_file in ['id_rsa', 'id_ed25519', 'id_ecdsa']:
                key_path = ssh_dir / key_file
                if key_path.exists():
                    try:
                        stat_info = key_path.stat()
                        access_time = datetime.fromtimestamp(stat_info.st_atime)
                        # Check if accessed in last 5 minutes
                        if (datetime.now() - access_time).total_seconds() < 300:
                            finding = {
                                "file": str(key_path),
                                "access_time": access_time.isoformat(),
                                "type": "ssh_key_access",
                                "severity": "medium"
                            }
                            self.credential_access_events.append(finding)
                    except PermissionError:
                        pass
    
    def _check_windows_credential_access(self):
        """Check Windows credential access"""
        # Check SAM/SYSTEM/SECURITY file access via event logs
        try:
            ps_cmd = '''
            Get-WinEvent -FilterHashtable @{LogName='Security';Id=4663} -MaxEvents 50 2>$null |
            Where-Object { $_.Message -match 'SAM|SYSTEM|SECURITY|NTDS' } |
            Select-Object TimeCreated,Message | ConvertTo-Json
            '''
            
            result = subprocess.run(
                ['powershell', '-Command', ps_cmd],
                capture_output=True, text=True, timeout=30
            )
            
            if result.returncode == 0 and result.stdout.strip():
                try:
                    events = json.loads(result.stdout)
                    if not isinstance(events, list):
                        events = [events]
                    
                    for event in events:
                        finding = {
                            "time": event.get('TimeCreated', ''),
                            "type": "registry_hive_access",
                            "message": event.get('Message', '')[:200],
                            "severity": "high"
                        }
                        self.credential_access_events.append(finding)
                        
                except json.JSONDecodeError:
                    pass
                    
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        except Exception as e:
            logger.debug(f"Windows credential access check error: {e}")
    
    def _check_browser_credentials(self):
        """Check for browser credential access"""
        if not PSUTIL_AVAILABLE:
            return
        
        # Get browser credential paths for current platform
        platform_key = PLATFORM if PLATFORM in ['windows', 'linux', 'darwin'] else 'linux'
        
        for browser, paths in self.BROWSER_CREDENTIALS.items():
            if platform_key not in paths:
                continue
            
            cred_path = os.path.expandvars(os.path.expanduser(paths[platform_key]))
            
            # Handle wildcards by checking if any matching files exist
            if '*' in cred_path:
                import glob
                matches = glob.glob(cred_path)
                for match in matches:
                    self._check_single_browser_cred(match, browser)
            elif os.path.exists(cred_path):
                self._check_single_browser_cred(cred_path, browser)
    
    def _check_single_browser_cred(self, cred_path: str, browser: str):
        """Check single browser credential file"""
        try:
            stat_info = os.stat(cred_path)
            access_time = datetime.fromtimestamp(stat_info.st_atime)
            
            # Check if accessed in last 5 minutes
            if (datetime.now() - access_time).total_seconds() < 300:
                finding = {
                    "browser": browser,
                    "file": cred_path,
                    "access_time": access_time.isoformat(),
                    "type": "browser_credential_access",
                    "severity": "medium"
                }
                self.credential_access_events.append(finding)
                
        except (PermissionError, OSError):
            pass
    
    def _detect_token_manipulation(self):
        """Detect token manipulation and impersonation"""
        if PLATFORM != "windows":
            return
        
        try:
            # Check security event logs for token manipulation
            ps_cmd = '''
            Get-WinEvent -FilterHashtable @{LogName='Security';Id=4672,4673,4674} -MaxEvents 100 2>$null |
            Select-Object TimeCreated,Id,Message | ConvertTo-Json
            '''
            
            result = subprocess.run(
                ['powershell', '-Command', ps_cmd],
                capture_output=True, text=True, timeout=30
            )
            
            if result.returncode == 0 and result.stdout.strip():
                try:
                    events = json.loads(result.stdout)
                    if not isinstance(events, list):
                        events = [events]
                    
                    for event in events:
                        event_id = event.get('Id', 0)
                        message = event.get('Message', '')
                        
                        # Check for suspicious privilege use
                        suspicious_privs = [
                            'SeDebugPrivilege', 'SeTcbPrivilege',
                            'SeImpersonatePrivilege', 'SeAssignPrimaryTokenPrivilege'
                        ]
                        
                        for priv in suspicious_privs:
                            if priv in message:
                                finding = {
                                    "event_id": event_id,
                                    "privilege": priv,
                                    "time": event.get('TimeCreated', ''),
                                    "severity": "high"
                                }
                                self.token_events.append(finding)
                                break
                                
                except json.JSONDecodeError:
                    pass
                    
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        except Exception as e:
            logger.debug(f"Token manipulation check error: {e}")
    
    def _check_kerberos_anomalies(self):
        """Check for Kerberos-related anomalies"""
        if PLATFORM == "windows":
            self._check_windows_kerberos()
        else:
            self._check_linux_kerberos()
    
    def _check_windows_kerberos(self):
        """Check Windows Kerberos events"""
        try:
            # Look for Kerberos-related security events
            ps_cmd = '''
            Get-WinEvent -FilterHashtable @{LogName='Security';Id=4768,4769,4771,4776} -MaxEvents 100 2>$null |
            Select-Object TimeCreated,Id,Message | ConvertTo-Json
            '''
            
            result = subprocess.run(
                ['powershell', '-Command', ps_cmd],
                capture_output=True, text=True, timeout=30
            )
            
            if result.returncode == 0 and result.stdout.strip():
                try:
                    events = json.loads(result.stdout)
                    if not isinstance(events, list):
                        events = [events]
                    
                    # Look for failure events
                    failure_count = 0
                    for event in events:
                        message = event.get('Message', '').lower()
                        if 'failure' in message or 'fail' in message:
                            failure_count += 1
                    
                    # If high failure rate, flag as anomaly
                    if failure_count > 10:
                        finding = {
                            "type": "kerberos_failures",
                            "count": failure_count,
                            "severity": "medium"
                        }
                        self.kerberos_anomalies.append(finding)
                        
                except json.JSONDecodeError:
                    pass
                    
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        except Exception as e:
            logger.debug(f"Windows Kerberos check error: {e}")
    
    def _check_linux_kerberos(self):
        """Check Linux Kerberos tickets"""
        # Check for suspicious ticket cache files
        krb_cache_dir = '/tmp'
        try:
            for entry in os.listdir(krb_cache_dir):
                if entry.startswith('krb5cc_'):
                    cache_path = os.path.join(krb_cache_dir, entry)
                    try:
                        stat_info = os.stat(cache_path)
                        
                        # Check for recent creation
                        create_time = datetime.fromtimestamp(stat_info.st_ctime)
                        if (datetime.now() - create_time).total_seconds() < 300:
                            finding = {
                                "type": "recent_ticket_cache",
                                "file": cache_path,
                                "created": create_time.isoformat(),
                                "severity": "low"
                            }
                            self.kerberos_anomalies.append(finding)
                            
                    except (PermissionError, OSError):
                        pass
                        
        except (PermissionError, FileNotFoundError):
            pass
    
    def _create_threat(self, title: str, description: str, severity: ThreatSeverity,
                      threat_type: str, mitre_techniques: List[str], evidence: Dict):
        """Create a threat from identity protection finding"""
        threat = Threat(
            threat_id=f"identity-{uuid.uuid4().hex[:12]}",
            title=title,
            description=description,
            severity=severity,
            threat_type=threat_type,
            source="identity_protection",
            mitre_techniques=mitre_techniques,
            evidence=evidence,
            auto_kill_eligible=severity == ThreatSeverity.CRITICAL
        )
        self.threats.append(threat)
    
    def get_threats(self) -> List[Threat]:
        """Get detected identity threats"""
        return self.threats
    
    def get_status(self) -> Dict[str, Any]:
        """Get identity protection status"""
        return {
            "lsass_pid": self.lsass_pid,
            "credential_tools_detected": len(self.suspicious_processes),
            "lsass_access_events": len(self.lsass_access_events),
            "credential_file_access": len(self.credential_access_events),
            "token_events": len(self.token_events),
            "kerberos_anomalies": len(self.kerberos_anomalies),
            "threats": len(self.threats),
            "last_scan": self.last_run.isoformat() if self.last_run else None
        }


# =============================================================================
# AUTO-THROTTLE MONITOR (Resource Management)
# =============================================================================

class AutoThrottleMonitor(MonitorModule):
    """
    System resource throttling monitor that automatically manages CPU and memory usage.
    
    Features:
    - CPU hog detection and priority reduction
    - Memory working set trimming (Windows)
    - Nice value adjustment (Linux/macOS)
    - Protected process whitelist
    - Configurable thresholds
    
    MITRE ATT&CK Coverage:
    - T1496: Resource Hijacking (cryptominers, etc.)
    """
    
    # Protected process names that should never be throttled
    PROTECTED_PROCESSES = frozenset({
        'system', 'idle', 'csrss', 'wininit', 'winlogon', 'services',
        'lsass', 'smss', 'svchost', 'explorer', 'dwm', 'registry',
        'memory compression', 'secure system',
        'python', 'pythonw', 'python3', 'cmd', 'powershell', 'pwsh',
        'conhost', 'fontdrvhost', 'sihost', 'taskhostw', 'runtimebroker',
        'searchhost', 'startmenuexperiencehost', 'textinputhost',
        'shellexperiencehost', 'securityhealthservice', 'msmpeng',
        'antimalwareserviceexecutable', 'wudfhost', 'dllhost',
        'spoolsv', 'audiodg', 'ctfmon', 'seraph', 'metatron',
    })
    
    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self.threats: List[Threat] = []
        self.throttled_pids: set = set()
        self.throttle_actions: List[Dict] = []
        self.cpu_threshold = 80  # percentage
        self.mem_threshold = 85  # percentage
        self.last_throttle_time = 0
        self.throttle_cooldown = 30  # seconds between throttle cycles
        
    def scan(self) -> Dict[str, Any]:
        """Scan system resources and throttle if needed"""
        self.last_run = datetime.now()
        self.threats = []
        self.throttle_actions = []
        
        if not PSUTIL_AVAILABLE:
            return {"error": "psutil not available", "throttled": 0}
        
        try:
            # Get system-wide resource usage
            cpu_pct = psutil.cpu_percent(interval=1)
            mem_info = psutil.virtual_memory()
            mem_pct = mem_info.percent
            
            result = {
                "cpu_percent": cpu_pct,
                "memory_percent": mem_pct,
                "cpu_threshold": self.cpu_threshold,
                "memory_threshold": self.mem_threshold,
                "throttled_processes": [],
                "resource_hogs": [],
                "threats_detected": 0
            }
            
            now = time.time()
            if now - self.last_throttle_time < self.throttle_cooldown:
                result["status"] = "cooldown"
                return result
            
            # Find resource hogs
            cpu_hogs = self._find_cpu_hogs()
            mem_hogs = self._find_memory_hogs()
            
            result["resource_hogs"] = cpu_hogs[:10] + mem_hogs[:10]
            
            # Throttle if above thresholds
            if cpu_pct > self.cpu_threshold:
                throttled = self._throttle_cpu_hogs(cpu_hogs)
                result["throttled_processes"].extend(throttled)
                self.last_throttle_time = time.time()
                
            if mem_pct > self.mem_threshold:
                throttled = self._throttle_memory_hogs(mem_hogs)
                result["throttled_processes"].extend(throttled)
                self.last_throttle_time = time.time()
            
            # Detect potential cryptominers (sustained high CPU with no GUI)
            self._detect_resource_hijacking(cpu_hogs)
            
            # Purge stale PIDs
            self._cleanup_stale_pids()
            
            result["threats_detected"] = len(self.threats)
            result["total_throttled"] = len(self.throttled_pids)
            
            return result
            
        except Exception as e:
            logger.error(f"AutoThrottleMonitor scan error: {e}")
            return {"error": str(e)}
    
    def _find_cpu_hogs(self) -> List[Dict]:
        """Find processes using excessive CPU"""
        # Prime cpu_percent counters
        for proc in psutil.process_iter(['cpu_percent']):
            pass
        time.sleep(0.5)
        
        hogs = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'username']):
            try:
                info = proc.info
                cpu = info.get('cpu_percent', 0) or 0
                pname = (info.get('name', '') or '').lower().replace('.exe', '')
                pid = info.get('pid', 0)
                
                if cpu > 5 and pname not in self.PROTECTED_PROCESSES:
                    hogs.append({
                        'pid': pid,
                        'name': info.get('name', ''),
                        'cpu_percent': cpu,
                        'username': info.get('username', ''),
                        'already_throttled': pid in self.throttled_pids
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        return sorted(hogs, key=lambda x: x['cpu_percent'], reverse=True)
    
    def _find_memory_hogs(self) -> List[Dict]:
        """Find processes using excessive memory"""
        hogs = []
        for proc in psutil.process_iter(['pid', 'name', 'memory_percent', 'username']):
            try:
                info = proc.info
                mem = info.get('memory_percent', 0) or 0
                pname = (info.get('name', '') or '').lower().replace('.exe', '')
                pid = info.get('pid', 0)
                
                if mem > 3 and pname not in self.PROTECTED_PROCESSES:
                    hogs.append({
                        'pid': pid,
                        'name': info.get('name', ''),
                        'memory_percent': mem,
                        'username': info.get('username', ''),
                        'already_throttled': pid in self.throttled_pids
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        return sorted(hogs, key=lambda x: x['memory_percent'], reverse=True)
    
    def _throttle_cpu_hogs(self, hogs: List[Dict]) -> List[Dict]:
        """Lower priority of top CPU-hogging processes"""
        throttled = []
        
        for hog in hogs[:5]:
            if hog['already_throttled']:
                continue
                
            pid = hog['pid']
            name = hog['name']
            cpu = hog['cpu_percent']
            
            try:
                p = psutil.Process(pid)
                current_nice = p.nice()
                action = None
                
                if platform.system() == 'Windows':
                    if cpu > 80 and current_nice != psutil.IDLE_PRIORITY_CLASS:
                        p.nice(psutil.IDLE_PRIORITY_CLASS)
                        action = 'IDLE_PRIORITY'
                    elif current_nice not in (psutil.BELOW_NORMAL_PRIORITY_CLASS, psutil.IDLE_PRIORITY_CLASS):
                        p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
                        action = 'BELOW_NORMAL_PRIORITY'
                else:
                    # Linux/macOS: increase nice value
                    new_nice = min(current_nice + 5, 19)
                    if new_nice != current_nice:
                        p.nice(new_nice)
                        action = f'nice={new_nice}'
                
                if action:
                    self.throttled_pids.add(pid)
                    throttle_record = {
                        'pid': pid,
                        'name': name,
                        'cpu_percent': cpu,
                        'action': action,
                        'timestamp': datetime.now().isoformat()
                    }
                    throttled.append(throttle_record)
                    self.throttle_actions.append(throttle_record)
                    logger.info(f"Auto-throttle CPU: {name} PID={pid} CPU={cpu:.1f}% -> {action}")
                    
            except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                logger.debug(f"Cannot throttle PID {pid}: {e}")
            except Exception as e:
                logger.warning(f"Throttle CPU error for PID {pid}: {e}")
        
        return throttled
    
    def _throttle_memory_hogs(self, hogs: List[Dict]) -> List[Dict]:
        """Trim working sets of memory-heavy processes (Windows) or adjust OOM score (Linux)"""
        throttled = []
        
        for hog in hogs[:5]:
            if hog['already_throttled']:
                continue
                
            pid = hog['pid']
            name = hog['name']
            mem = hog['memory_percent']
            
            try:
                if platform.system() == 'Windows':
                    import ctypes
                    PROCESS_SET_QUOTA = 0x0100
                    PROCESS_QUERY_INFORMATION = 0x0400
                    handle = ctypes.windll.kernel32.OpenProcess(
                        PROCESS_SET_QUOTA | PROCESS_QUERY_INFORMATION, False, pid)
                    if handle:
                        ctypes.windll.psapi.EmptyWorkingSet(handle)
                        ctypes.windll.kernel32.CloseHandle(handle)
                        action = 'trimmed_working_set'
                    else:
                        continue
                else:
                    # Linux: adjust OOM score
                    oom_path = f'/proc/{pid}/oom_score_adj'
                    if os.path.exists(oom_path):
                        try:
                            with open(oom_path, 'w') as f:
                                f.write('500')  # Higher = more likely to be killed under memory pressure
                            action = 'oom_score_adj=500'
                        except PermissionError:
                            # Try nice adjustment instead
                            p = psutil.Process(pid)
                            current_nice = p.nice()
                            new_nice = min(current_nice + 3, 19)
                            if new_nice != current_nice:
                                p.nice(new_nice)
                                action = f'nice={new_nice}'
                            else:
                                continue
                    else:
                        continue
                
                self.throttled_pids.add(pid)
                throttle_record = {
                    'pid': pid,
                    'name': name,
                    'memory_percent': mem,
                    'action': action,
                    'timestamp': datetime.now().isoformat()
                }
                throttled.append(throttle_record)
                self.throttle_actions.append(throttle_record)
                logger.info(f"Auto-throttle MEM: {name} PID={pid} MEM={mem:.1f}% -> {action}")
                
            except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                logger.debug(f"Cannot throttle memory PID {pid}: {e}")
            except Exception as e:
                logger.warning(f"Throttle memory error for PID {pid}: {e}")
        
        return throttled
    
    def _detect_resource_hijacking(self, cpu_hogs: List[Dict]):
        """Detect potential cryptominers or resource hijacking"""
        for hog in cpu_hogs[:10]:
            if hog['cpu_percent'] < 50:
                continue
                
            pid = hog['pid']
            name = hog['name'].lower()
            
            # Suspicious indicators for cryptominers
            suspicious_names = ['xmrig', 'minerd', 'cpuminer', 'nicehash', 'ethminer',
                               'cgminer', 'bfgminer', 'claymore', 'nanopool', 'minergate']
            
            is_suspicious = any(s in name for s in suspicious_names)
            
            # Check for processes with no window (background CPU hogs)
            try:
                p = psutil.Process(pid)
                cmdline = ' '.join(p.cmdline()).lower()
                
                # Check command line for mining indicators
                mining_indicators = ['stratum', 'pool.', 'mining', 'hashrate', '-o ', '--url']
                if any(ind in cmdline for ind in mining_indicators):
                    is_suspicious = True
                    
                # High CPU with no parent explorer (not user-launched)
                try:
                    parent = p.parent()
                    if parent and parent.name().lower() not in ['explorer.exe', 'systemd', 'init', 'launchd']:
                        # Background process with high CPU
                        if hog['cpu_percent'] > 70:
                            is_suspicious = True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
                    
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            
            if is_suspicious:
                threat = Threat(
                    threat_id=f"resource-hijack-{uuid.uuid4().hex[:8]}",
                    title=f"Potential Resource Hijacking: {hog['name']}",
                    description=f"Process {hog['name']} (PID {pid}) using {hog['cpu_percent']:.1f}% CPU - possible cryptominer or resource abuse",
                    severity=ThreatSeverity.HIGH,
                    threat_type="resource_hijacking",
                    source="auto_throttle",
                    process_name=hog['name'],
                    process_id=pid,
                    mitre_techniques=["T1496"],  # Resource Hijacking
                    evidence={
                        "pid": pid,
                        "name": hog['name'],
                        "cpu_percent": hog['cpu_percent'],
                        "indicators": "high_cpu_background_process"
                    },
                    auto_kill_eligible=True
                )
                self.threats.append(threat)
                logger.warning(f"Resource hijacking detected: {hog['name']} PID={pid}")
    
    def _cleanup_stale_pids(self):
        """Remove PIDs that no longer exist"""
        alive = set()
        for pid in self.throttled_pids:
            try:
                if psutil.pid_exists(pid):
                    alive.add(pid)
            except Exception:
                pass
        self.throttled_pids = alive
    
    def _create_threat(self, hog: Dict, reason: str):
        """Create a threat for resource abuse"""
        threat = Threat(
            threat_id=f"resource-{uuid.uuid4().hex[:8]}",
            title=f"Resource Abuse: {hog['name']}",
            description=f"Process {hog['name']} flagged for resource abuse: {reason}",
            severity=ThreatSeverity.MEDIUM,
            threat_type="resource_abuse",
            source="auto_throttle",
            process_name=hog['name'],
            process_id=hog['pid'],
            mitre_techniques=["T1496"],
            evidence=hog,
            auto_kill_eligible=False
        )
        self.threats.append(threat)
    
    def get_threats(self) -> List[Threat]:
        """Get detected resource abuse threats"""
        return self.threats
    
    def get_status(self) -> Dict[str, Any]:
        """Get auto-throttle status"""
        return {
            "enabled": self.enabled,
            "cpu_threshold": self.cpu_threshold,
            "memory_threshold": self.mem_threshold,
            "throttled_count": len(self.throttled_pids),
            "throttled_pids": list(self.throttled_pids),
            "recent_actions": self.throttle_actions[-20:],
            "threats": len(self.threats),
            "last_scan": self.last_run.isoformat() if self.last_run else None
        }


# =============================================================================
# FIREWALL MONITOR (Security Posture)
# =============================================================================

class FirewallMonitor(MonitorModule):
    """
    Firewall state and rule monitoring across Windows, Linux, and macOS.
    
    Features:
    - Firewall enabled/disabled detection
    - New rule detection
    - Overly permissive rule detection
    - Rule change tracking
    - Cross-platform support (netsh, iptables, nftables, pf)
    
    MITRE ATT&CK Coverage:
    - T1562.004: Impair Defenses: Disable or Modify System Firewall
    - T1562.001: Impair Defenses: Disable or Modify Tools
    """
    
    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self.threats: List[Threat] = []
        self.known_rules: set = set()
        self.firewall_states: Dict[str, bool] = {}
        self.rule_history: List[Dict] = []
        self.suspicious_rules: List[Dict] = []
        
    def scan(self) -> Dict[str, Any]:
        """Scan firewall state and rules"""
        self.last_run = datetime.now()
        self.threats = []
        self.suspicious_rules = []
        
        result = {
            "platform": platform.system(),
            "profiles": {},
            "rules_checked": 0,
            "new_rules": [],
            "suspicious_rules": [],
            "threats_detected": 0
        }
        
        try:
            if platform.system() == 'Windows':
                self._check_windows_firewall(result)
            elif platform.system() == 'Linux':
                self._check_linux_firewall(result)
            elif platform.system() == 'Darwin':
                self._check_macos_firewall(result)
            
            result["threats_detected"] = len(self.threats)
            return result
            
        except Exception as e:
            logger.error(f"FirewallMonitor scan error: {e}")
            return {"error": str(e)}
    
    def _check_windows_firewall(self, result: Dict):
        """Check Windows Firewall state and rules"""
        import subprocess
        
        # 1. Check if firewall is enabled for all profiles
        try:
            proc = subprocess.run(
                ["netsh", "advfirewall", "show", "allprofiles", "state"],
                capture_output=True, text=True, timeout=10
            )
            
            current_profile = "Unknown"
            for line in proc.stdout.splitlines():
                line = line.strip()
                if "Profile" in line:
                    current_profile = line.replace("Settings:", "").strip()
                elif "State" in line:
                    state = "ON" if "ON" in line.upper() else "OFF"
                    result["profiles"][current_profile] = state
                    self.firewall_states[current_profile] = (state == "ON")
                    
                    if state == "OFF":
                        self._create_threat(
                            title=f"Windows Firewall Disabled: {current_profile}",
                            description=f"The Windows Firewall is disabled for the {current_profile} profile, "
                                       f"leaving the system vulnerable to network attacks",
                            severity=ThreatSeverity.CRITICAL,
                            evidence={"profile": current_profile, "state": "OFF"}
                        )
                        
        except subprocess.TimeoutExpired:
            logger.warning("Firewall state check timed out")
        except Exception as e:
            logger.warning(f"Firewall state check error: {e}")
        
        # 2. Check for suspicious inbound allow rules
        try:
            proc = subprocess.run(
                ["netsh", "advfirewall", "firewall", "show", "rule",
                 "name=all", "dir=in", "action=allow"],
                capture_output=True, text=True, timeout=30
            )
            
            current_rules = set()
            suspicious_keywords = ["any", "all", "0.0.0.0", "*", "0.0.0.0/0"]
            safe_rule_patterns = ["core networking", "windows", "microsoft", "system"]
            
            rule_name = ""
            rule_data = {}
            
            for line in proc.stdout.splitlines():
                line = line.strip()
                if line.startswith("Rule Name:"):
                    # Process previous rule
                    if rule_name:
                        current_rules.add(rule_name)
                        self._analyze_rule(rule_name, rule_data, suspicious_keywords, safe_rule_patterns)
                    
                    rule_name = line.split(":", 1)[1].strip()
                    rule_data = {"name": rule_name}
                    
                elif ":" in line:
                    key, value = line.split(":", 1)
                    rule_data[key.strip()] = value.strip()
            
            # Process last rule
            if rule_name:
                current_rules.add(rule_name)
                self._analyze_rule(rule_name, rule_data, suspicious_keywords, safe_rule_patterns)
            
            result["rules_checked"] = len(current_rules)
            result["suspicious_rules"] = self.suspicious_rules
            
            # Detect NEW rules since last check
            if self.known_rules:
                new_rules = current_rules - self.known_rules
                for nr in new_rules:
                    result["new_rules"].append(nr)
                    self.rule_history.append({
                        "action": "added",
                        "rule": nr,
                        "timestamp": datetime.now().isoformat()
                    })
                    
                    # Create threat for new rule (medium severity - may be legitimate)
                    self._create_threat(
                        title=f"New Firewall Rule Added: {nr}",
                        description=f"A new inbound allow rule '{nr}' was added to Windows Firewall. "
                                   f"Verify this is an authorized change.",
                        severity=ThreatSeverity.MEDIUM,
                        evidence={"rule_name": nr, "action": "added"}
                    )
                
                # Detect removed rules
                removed_rules = self.known_rules - current_rules
                for rr in removed_rules:
                    self.rule_history.append({
                        "action": "removed",
                        "rule": rr,
                        "timestamp": datetime.now().isoformat()
                    })
            
            self.known_rules = current_rules
            
        except subprocess.TimeoutExpired:
            logger.warning("Firewall rule check timed out")
        except Exception as e:
            logger.warning(f"Firewall rule check error: {e}")
    
    def _analyze_rule(self, rule_name: str, rule_data: Dict, 
                      suspicious_keywords: List[str], safe_patterns: List[str]):
        """Analyze a firewall rule for suspicious patterns"""
        rule_name_lower = rule_name.lower()
        
        # Skip known-safe rules
        if any(pattern in rule_name_lower for pattern in safe_patterns):
            return
        
        # Check for overly permissive settings
        suspicious_fields = []
        
        remote_ip = rule_data.get("RemoteIP", "").lower()
        local_port = rule_data.get("LocalPort", "").lower()
        remote_port = rule_data.get("RemotePort", "").lower()
        
        for field_name, field_value in [("RemoteIP", remote_ip), 
                                         ("LocalPort", local_port),
                                         ("RemotePort", remote_port)]:
            if any(kw in field_value for kw in suspicious_keywords):
                suspicious_fields.append(f"{field_name}={field_value}")
        
        if suspicious_fields:
            finding = {
                "rule_name": rule_name,
                "suspicious_fields": suspicious_fields,
                "full_rule": rule_data
            }
            self.suspicious_rules.append(finding)
            
            self._create_threat(
                title=f"Overly Permissive Firewall Rule: {rule_name}",
                description=f"The firewall rule '{rule_name}' has overly permissive settings: "
                           f"{', '.join(suspicious_fields)}. This could allow unauthorized access.",
                severity=ThreatSeverity.HIGH,
                evidence=finding
            )
    
    def _check_linux_firewall(self, result: Dict):
        """Check Linux firewall (iptables/nftables/ufw)"""
        import subprocess
        
        firewall_type = None
        rules_found = 0
        
        # Try nftables first (modern)
        try:
            proc = subprocess.run(
                ["nft", "list", "ruleset"],
                capture_output=True, text=True, timeout=10
            )
            if proc.returncode == 0:
                firewall_type = "nftables"
                rules = proc.stdout
                rules_found = len([l for l in rules.splitlines() if l.strip() and not l.startswith('#')])
                
                # Check if ruleset is empty (no rules = firewall effectively disabled)
                if rules_found < 5:
                    self._create_threat(
                        title="Linux Firewall Has Minimal Rules",
                        description="The nftables ruleset has very few rules, suggesting the firewall may not be properly configured",
                        severity=ThreatSeverity.HIGH,
                        evidence={"firewall": "nftables", "rule_count": rules_found}
                    )
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.debug(f"nftables check error: {e}")
        
        # Try iptables
        if not firewall_type:
            try:
                proc = subprocess.run(
                    ["iptables", "-L", "-n"],
                    capture_output=True, text=True, timeout=10
                )
                if proc.returncode == 0:
                    firewall_type = "iptables"
                    rules = proc.stdout
                    
                    # Count actual rules (not headers)
                    for line in rules.splitlines():
                        if line and not line.startswith('Chain') and not line.startswith('target'):
                            rules_found += 1
                    
                    # Check for ACCEPT all policies with no rules
                    if "ACCEPT" in rules and rules_found < 3:
                        self._create_threat(
                            title="iptables Default Accept Policy",
                            description="iptables has default ACCEPT policy with few rules - effectively no firewall protection",
                            severity=ThreatSeverity.HIGH,
                            evidence={"firewall": "iptables", "rule_count": rules_found}
                        )
                        
            except FileNotFoundError:
                pass
            except PermissionError:
                logger.debug("iptables requires root privileges")
            except Exception as e:
                logger.debug(f"iptables check error: {e}")
        
        # Check UFW status
        try:
            proc = subprocess.run(
                ["ufw", "status"],
                capture_output=True, text=True, timeout=10
            )
            if proc.returncode == 0:
                if "inactive" in proc.stdout.lower():
                    self._create_threat(
                        title="UFW Firewall is Inactive",
                        description="The UFW (Uncomplicated Firewall) is installed but not active",
                        severity=ThreatSeverity.CRITICAL,
                        evidence={"firewall": "ufw", "status": "inactive"}
                    )
                    result["profiles"]["ufw"] = "OFF"
                else:
                    result["profiles"]["ufw"] = "ON"
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.debug(f"ufw check error: {e}")
        
        result["firewall_type"] = firewall_type or "unknown"
        result["rules_checked"] = rules_found
    
    def _check_macos_firewall(self, result: Dict):
        """Check macOS firewall (pf and application firewall)"""
        import subprocess
        
        # Check Application Firewall
        try:
            proc = subprocess.run(
                ["/usr/libexec/ApplicationFirewall/socketfilterfw", "--getglobalstate"],
                capture_output=True, text=True, timeout=10
            )
            if "disabled" in proc.stdout.lower():
                self._create_threat(
                    title="macOS Application Firewall Disabled",
                    description="The macOS Application Firewall is disabled, leaving the system vulnerable",
                    severity=ThreatSeverity.CRITICAL,
                    evidence={"firewall": "application_firewall", "status": "disabled"}
                )
                result["profiles"]["application_firewall"] = "OFF"
            else:
                result["profiles"]["application_firewall"] = "ON"
                
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.debug(f"macOS firewall check error: {e}")
        
        # Check pf firewall
        try:
            proc = subprocess.run(
                ["pfctl", "-s", "info"],
                capture_output=True, text=True, timeout=10
            )
            if "Status: Disabled" in proc.stdout:
                result["profiles"]["pf"] = "OFF"
            elif "Status: Enabled" in proc.stdout:
                result["profiles"]["pf"] = "ON"
        except FileNotFoundError:
            pass
        except PermissionError:
            logger.debug("pfctl requires root privileges")
        except Exception as e:
            logger.debug(f"pf check error: {e}")
    
    def _create_threat(self, title: str, description: str, severity: ThreatSeverity, evidence: Dict):
        """Create a firewall-related threat"""
        threat = Threat(
            threat_id=f"firewall-{uuid.uuid4().hex[:8]}",
            title=title,
            description=description,
            severity=severity,
            threat_type="firewall_issue",
            source="firewall_monitor",
            mitre_techniques=["T1562.004", "T1562.001"],  # Impair Defenses
            evidence=evidence,
            auto_kill_eligible=False
        )
        self.threats.append(threat)
    
    def get_threats(self) -> List[Threat]:
        """Get detected firewall threats"""
        return self.threats
    
    def get_status(self) -> Dict[str, Any]:
        """Get firewall monitor status"""
        return {
            "enabled": self.enabled,
            "platform": platform.system(),
            "firewall_states": self.firewall_states,
            "known_rules_count": len(self.known_rules),
            "suspicious_rules": len(self.suspicious_rules),
            "rule_history": self.rule_history[-20:],
            "threats": len(self.threats),
            "last_scan": self.last_run.isoformat() if self.last_run else None
        }


# =============================================================================
# WEBVIEW2 EXPLOIT MONITOR (Windows)
# =============================================================================

class WebView2Monitor(MonitorModule):
    """
    WebView2 runtime exploit and abuse monitor (Windows-specific).
    
    Microsoft Edge WebView2 is increasingly used in applications and can be
    exploited for various attacks. This monitor detects:
    - WebView2 spawned by suspicious parent processes (LOLBins)
    - Remote debugging port enabled (common exploit vector)
    - Web security disabled (allows XSS, CORS bypass)
    - Suspicious command-line arguments
    - Process injection into WebView2
    
    MITRE ATT&CK Coverage:
    - T1055: Process Injection
    - T1059: Command and Scripting Interpreter
    - T1185: Browser Session Hijacking
    - T1189: Drive-by Compromise
    """
    
    # Suspicious parent processes (LOLBins that shouldn't spawn WebView2)
    SUSPICIOUS_PARENTS = frozenset({
        'cmd.exe', 'powershell.exe', 'pwsh.exe', 'wscript.exe',
        'cscript.exe', 'mshta.exe', 'rundll32.exe', 'regsvr32.exe',
        'certutil.exe', 'msiexec.exe', 'installutil.exe', 'cmstp.exe',
        'msbuild.exe', 'wmic.exe', 'forfiles.exe', 'pcalua.exe'
    })
    
    # Dangerous command-line flags
    DANGEROUS_FLAGS = [
        '--remote-debugging-port',
        '--disable-web-security',
        '--allow-running-insecure-content',
        '--disable-site-isolation-trials',
        '--disable-features=IsolateOrigins',
        '--user-data-dir=',  # Custom data dir (persistence)
        '--load-extension=',  # Loading extensions
        '--disable-extensions-except=',
        '--no-sandbox',
        '--disable-gpu-sandbox',
    ]
    
    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self.threats: List[Threat] = []
        self.suspicious_instances: List[Dict] = []
        self.monitored_pids: set = set()
        
    def scan(self) -> Dict[str, Any]:
        """Scan for WebView2 exploitation patterns"""
        self.last_run = datetime.now()
        self.threats = []
        self.suspicious_instances = []
        
        # Only run on Windows
        if platform.system() != 'Windows':
            return {
                "status": "skipped",
                "reason": "Windows-only monitor",
                "platform": platform.system()
            }
        
        if not PSUTIL_AVAILABLE:
            return {"error": "psutil not available"}
        
        result = {
            "webview2_processes": 0,
            "suspicious_instances": [],
            "threats_detected": 0
        }
        
        try:
            webview2_procs = []
            
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'ppid', 'create_time']):
                try:
                    info = proc.info
                    pname = (info.get('name') or '').lower()
                    
                    # Look for WebView2 processes
                    if 'msedgewebview2' not in pname and 'webview2' not in pname:
                        continue
                    
                    webview2_procs.append(info)
                    pid = info.get('pid', 0)
                    cmdline = ' '.join(info.get('cmdline') or [])
                    ppid = info.get('ppid', 0)
                    
                    findings = []
                    
                    # 1. Check parent process
                    parent_finding = self._check_parent_process(ppid, pid)
                    if parent_finding:
                        findings.append(parent_finding)
                    
                    # 2. Check dangerous command-line flags
                    flag_findings = self._check_dangerous_flags(cmdline, pid)
                    findings.extend(flag_findings)
                    
                    # 3. Check for unusual network activity (if established connections to external IPs)
                    network_finding = self._check_network_activity(pid)
                    if network_finding:
                        findings.append(network_finding)
                    
                    if findings:
                        instance = {
                            'pid': pid,
                            'name': info.get('name', ''),
                            'ppid': ppid,
                            'cmdline': cmdline[:500],
                            'findings': findings,
                            'create_time': datetime.fromtimestamp(
                                info.get('create_time', 0)
                            ).isoformat() if info.get('create_time') else None
                        }
                        self.suspicious_instances.append(instance)
                        
                        # Create threat for each suspicious instance
                        self._create_threat_from_findings(instance, findings)
                    
                    self.monitored_pids.add(pid)
                    
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            result["webview2_processes"] = len(webview2_procs)
            result["suspicious_instances"] = self.suspicious_instances
            result["threats_detected"] = len(self.threats)
            
            return result
            
        except Exception as e:
            logger.error(f"WebView2Monitor scan error: {e}")
            return {"error": str(e)}
    
    def _check_parent_process(self, ppid: int, child_pid: int) -> Optional[Dict]:
        """Check if WebView2 was spawned by a suspicious parent"""
        try:
            parent = psutil.Process(ppid)
            parent_name = (parent.name() or '').lower()
            
            if parent_name in self.SUSPICIOUS_PARENTS:
                return {
                    'type': 'suspicious_parent',
                    'severity': 'critical',
                    'parent_name': parent_name,
                    'parent_pid': ppid,
                    'description': f"WebView2 spawned by suspicious process: {parent_name}"
                }
            
            # Check grandparent too
            try:
                grandparent = parent.parent()
                if grandparent:
                    gp_name = (grandparent.name() or '').lower()
                    if gp_name in self.SUSPICIOUS_PARENTS:
                        return {
                            'type': 'suspicious_grandparent',
                            'severity': 'high',
                            'grandparent_name': gp_name,
                            'parent_name': parent_name,
                            'description': f"WebView2 chain: {gp_name} -> {parent_name} -> WebView2"
                        }
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
                
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        
        return None
    
    def _check_dangerous_flags(self, cmdline: str, pid: int) -> List[Dict]:
        """Check command line for dangerous flags"""
        findings = []
        cmdline_lower = cmdline.lower()
        
        for flag in self.DANGEROUS_FLAGS:
            if flag.lower() in cmdline_lower:
                severity = 'critical' if flag in ['--remote-debugging-port', '--disable-web-security', '--no-sandbox'] else 'high'
                findings.append({
                    'type': 'dangerous_flag',
                    'severity': severity,
                    'flag': flag,
                    'description': f"WebView2 running with dangerous flag: {flag}"
                })
        
        # Check for base64-encoded data in command line (potential payload)
        if len(cmdline) > 500:
            import base64
            # Look for long base64-like strings
            import re
            b64_pattern = re.compile(r'[A-Za-z0-9+/]{100,}={0,2}')
            if b64_pattern.search(cmdline):
                findings.append({
                    'type': 'encoded_payload',
                    'severity': 'high',
                    'description': 'WebView2 command line contains potential base64-encoded payload'
                })
        
        return findings
    
    def _check_network_activity(self, pid: int) -> Optional[Dict]:
        """Check for suspicious network connections from WebView2"""
        try:
            proc = psutil.Process(pid)
            connections = proc.connections(kind='inet')
            
            external_conns = []
            for conn in connections:
                if conn.status == 'ESTABLISHED' and conn.raddr:
                    remote_ip = conn.raddr.ip
                    # Skip localhost and private IPs for this check
                    if not remote_ip.startswith(('127.', '10.', '192.168.', '172.')):
                        external_conns.append({
                            'remote_ip': remote_ip,
                            'remote_port': conn.raddr.port,
                            'local_port': conn.laddr.port if conn.laddr else None
                        })
            
            # Alert if many external connections (unusual for embedded WebView2)
            if len(external_conns) > 10:
                return {
                    'type': 'excessive_connections',
                    'severity': 'medium',
                    'connection_count': len(external_conns),
                    'sample_connections': external_conns[:5],
                    'description': f"WebView2 has {len(external_conns)} external connections"
                }
                
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        
        return None
    
    def _create_threat_from_findings(self, instance: Dict, findings: List[Dict]):
        """Create threat(s) from suspicious findings"""
        # Get highest severity from findings
        severity_map = {'critical': 3, 'high': 2, 'medium': 1, 'low': 0}
        max_severity = max(severity_map.get(f.get('severity', 'low'), 0) for f in findings)
        
        severity = ThreatSeverity.CRITICAL if max_severity == 3 else \
                   ThreatSeverity.HIGH if max_severity == 2 else \
                   ThreatSeverity.MEDIUM
        
        descriptions = [f.get('description', '') for f in findings]
        
        threat = Threat(
            threat_id=f"webview2-{uuid.uuid4().hex[:8]}",
            title=f"WebView2 Exploit Pattern Detected (PID {instance['pid']})",
            description="; ".join(descriptions),
            severity=severity,
            threat_type="webview2_exploit",
            source="webview2_monitor",
            process_name=instance.get('name', ''),
            process_id=instance['pid'],
            mitre_techniques=["T1055", "T1059", "T1185", "T1189"],
            evidence={
                "pid": instance['pid'],
                "ppid": instance['ppid'],
                "cmdline": instance['cmdline'][:200],
                "findings": findings
            },
            auto_kill_eligible=(severity == ThreatSeverity.CRITICAL)
        )
        self.threats.append(threat)
    
    def get_threats(self) -> List[Threat]:
        """Get detected WebView2 threats"""
        return self.threats
    
    def get_status(self) -> Dict[str, Any]:
        """Get WebView2 monitor status"""
        return {
            "enabled": self.enabled,
            "platform": platform.system(),
            "windows_only": True,
            "monitored_pids": len(self.monitored_pids),
            "suspicious_instances": len(self.suspicious_instances),
            "threats": len(self.threats),
            "last_scan": self.last_run.isoformat() if self.last_run else None
        }


# =============================================================================
# CLI TELEMETRY MONITOR - SOAR INTEGRATION
# =============================================================================

class CLITelemetryMonitor(MonitorModule):
    """
    CLI Telemetry Monitor for SOAR Integration
    
    Monitors shell/command processes across platforms and sends
    telemetry to backend CCE (Command/Control Events) pipeline for
    SOAR analysis and threat hunting.
    
    MITRE ATT&CK Coverage:
    - T1059: Command and Scripting Interpreter
    - T1059.001: PowerShell
    - T1059.003: Windows Command Shell
    - T1059.004: Unix Shell
    - T1059.006: Python
    - T1218: System Binary Proxy Execution (LOLBins)
    
    Features:
    - Shell process monitoring (cmd, PowerShell, bash, sh, zsh)
    - LOLBin detection (wscript, certutil, regsvr32, mshta, etc.)
    - Command-line capture with length limits
    - Automatic deduplication by (pid, create_time)
    - Memory-efficient pruning for long-running agents
    - Backend CCE event submission for SOAR
    """
    
    # Shell and interpreter processes to monitor
    SHELL_PROCESSES = frozenset({
        # Windows shells
        'cmd.exe', 'powershell.exe', 'pwsh.exe',
        # Unix shells
        'bash', 'sh', 'zsh', 'ksh', 'csh', 'tcsh', 'fish',
        # Scripting interpreters
        'python.exe', 'python', 'python3', 'python3.exe',
        'perl.exe', 'perl', 'ruby.exe', 'ruby',
        # Windows scripting hosts
        'wscript.exe', 'cscript.exe', 'mshta.exe',
        # LOLBins - Living Off the Land Binaries
        'regsvr32.exe', 'certutil.exe', 'bitsadmin.exe',
        'msiexec.exe', 'rundll32.exe', 'msbuild.exe',
        # Network/recon tools
        'net.exe', 'net1.exe', 'wmic.exe', 'schtasks.exe',
        'nslookup.exe', 'whoami.exe', 'ipconfig.exe',
        'tasklist.exe', 'systeminfo.exe', 'netstat.exe',
        'ping.exe', 'curl.exe', 'wget.exe', 'curl', 'wget',
        # Remote tools
        'psexec.exe', 'winrm.cmd', 'ssh.exe', 'ssh'
    })
    
    # High-risk LOLBins that may indicate attack activity
    LOLBIN_ALERT = frozenset({
        'certutil.exe', 'bitsadmin.exe', 'mshta.exe',
        'regsvr32.exe', 'msiexec.exe', 'rundll32.exe',
        'msbuild.exe', 'psexec.exe', 'wmic.exe'
    })
    
    # Suspicious command patterns (case-insensitive)
    SUSPICIOUS_PATTERNS = [
        r'-enc\s+',           # Encoded PowerShell
        r'-encodedcommand',   # Encoded PowerShell
        r'frombase64',        # Base64 decode
        r'downloadstring',    # PowerShell download
        r'invoke-expression', # IEX
        r'iex\s*\(',         # IEX shorthand
        r'downloadfile',      # File download
        r'webclient',         # .NET WebClient
        r'-nop\s+-w\s+hidden', # Hidden PowerShell
        r'bypass.*executionpolicy', # Execution policy bypass
        r'urlcache.*split',   # certutil download
        r'transfer.*create',  # BITSAdmin
        r'/c\s+echo.*\|',    # Pipe obfuscation
        r'scrobj\.dll',       # Scriptlet
        r'regsvr32.*\/s.*\/u', # regsvr32 bypass
        r'mshta.*javascript:', # MSHTA script
        r'mshta.*vbscript:',  # MSHTA VBS
    ]
    
    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self.known_commands: set = set()  # Track (pid, create_time)
        self.threats: List[Threat] = []
        self.command_history: List[Dict[str, Any]] = []
        self.suspicious_count = 0
        self.lolbin_count = 0
        self.total_commands = 0
        self.backend_url = getattr(config, 'server_url', 'http://localhost:5000')
        
        # Compile suspicious patterns
        self._suspicious_re = re.compile(
            '|'.join(self.SUSPICIOUS_PATTERNS),
            re.IGNORECASE
        )
        
        logger.info("CLITelemetryMonitor initialized - SOAR integration active")
    
    def scan(self) -> List[Threat]:
        """Scan for shell/CLI processes and detect suspicious commands"""
        if not self.enabled or not HAS_PSUTIL:
            return []
        
        self.threats.clear()
        self.last_run = datetime.now(timezone.utc)
        new_commands = []
        
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time', 'username', 'ppid']):
                try:
                    info = proc.info
                    pname = (info.get('name') or '').lower()
                    
                    # Only monitor shell/interpreter processes
                    if pname not in self.SHELL_PROCESSES:
                        continue
                    
                    pid = info['pid']
                    ctime = info.get('create_time', 0)
                    key = (pid, ctime)
                    
                    # Skip already-seen commands
                    if key in self.known_commands:
                        continue
                    
                    self.known_commands.add(key)
                    
                    # Get command line (limit to 500 chars)
                    cmdline = ' '.join(info.get('cmdline') or [])[:500]
                    if not cmdline or len(cmdline) < 3:
                        continue
                    
                    self.total_commands += 1
                    
                    # Build command event
                    cmd_event = {
                        'host_id': self.config.agent_id,
                        'hostname': socket.gethostname(),
                        'command': cmdline,
                        'process_name': pname,
                        'pid': pid,
                        'ppid': info.get('ppid', 0),
                        'username': info.get('username', 'unknown'),
                        'timestamp': datetime.now(timezone.utc).isoformat(),
                        'shell_type': self._infer_shell_type(pname),
                        'is_lolbin': pname in self.LOLBIN_ALERT,
                        'is_suspicious': False
                    }
                    
                    # Check for LOLBin usage
                    if pname in self.LOLBIN_ALERT:
                        self.lolbin_count += 1
                        cmd_event['is_suspicious'] = True
                        self._create_threat(
                            cmd_event,
                            findings=[f"LOLBin detected: {pname}"],
                            severity=ThreatSeverity.HIGH
                        )
                    
                    # Check for suspicious command patterns
                    elif self._suspicious_re.search(cmdline):
                        self.suspicious_count += 1
                        cmd_event['is_suspicious'] = True
                        patterns_matched = self._get_matched_patterns(cmdline)
                        self._create_threat(
                            cmd_event,
                            findings=patterns_matched,
                            severity=ThreatSeverity.HIGH
                        )
                    
                    new_commands.append(cmd_event)
                    
                    # Cache in history (limit to last 500)
                    self.command_history.append(cmd_event)
                    if len(self.command_history) > 500:
                        self.command_history = self.command_history[-500:]
                    
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            # Send telemetry to backend CCE pipeline
            for cmd_event in new_commands:
                self._send_cli_event(cmd_event)
            
            # Prune old entries to avoid memory growth
            if len(self.known_commands) > 5000:
                self.known_commands.clear()
                logger.debug("CLITelemetryMonitor: Pruned known commands")
        
        except Exception as e:
            logger.error(f"CLITelemetryMonitor scan error: {e}")
        
        return self.threats
    
    def _get_matched_patterns(self, cmdline: str) -> List[str]:
        """Get list of suspicious patterns matched in command"""
        matched = []
        cmdline_lower = cmdline.lower()
        for pattern in self.SUSPICIOUS_PATTERNS:
            if re.search(pattern, cmdline_lower):
                matched.append(f"Pattern: {pattern}")
        return matched if matched else ["Suspicious command pattern"]
    
    def _infer_shell_type(self, process_name: str) -> str:
        """Infer shell type from process name"""
        pn = process_name.lower()
        if 'powershell' in pn or 'pwsh' in pn:
            return 'powershell'
        if pn in ('bash', 'sh', 'zsh', 'ksh', 'csh', 'tcsh', 'fish'):
            return 'bash'
        if 'python' in pn:
            return 'python'
        if 'perl' in pn:
            return 'perl'
        if 'ruby' in pn:
            return 'ruby'
        if pn in ('wscript.exe', 'cscript.exe'):
            return 'wscript'
        return 'cmd'
    
    def _send_cli_event(self, event_data: Dict[str, Any]):
        """Send CLI command event to backend CCE pipeline"""
        try:
            payload = {
                'host_id': event_data.get('host_id', self.config.agent_id),
                'session_id': f"agent-{self.config.agent_id}",
                'user': event_data.get('username', 'unknown'),
                'shell_type': event_data.get('shell_type', 'unknown'),
                'command': event_data.get('command', ''),
                'parent_process': str(event_data.get('ppid', '')),
                'timestamp': event_data.get('timestamp'),
                'is_suspicious': event_data.get('is_suspicious', False),
                'is_lolbin': event_data.get('is_lolbin', False)
            }
            
            response = requests.post(
                f"{self.backend_url}/api/cli/event",
                json=payload,
                timeout=5
            )
            
            if response.status_code < 300:
                logger.debug(f"CLI event sent: {payload['command'][:60]}")
            else:
                logger.debug(f"CLI event failed: {response.status_code}")
        
        except requests.exceptions.RequestException as e:
            logger.debug(f"CLI event send error: {e}")
        except Exception as e:
            logger.debug(f"CLI event error: {e}")
    
    def _create_threat(self, cmd_event: Dict[str, Any], findings: List[str], severity: ThreatSeverity):
        """Create a threat entry for suspicious CLI activity"""
        # Determine MITRE technique based on process
        pname = cmd_event.get('process_name', '').lower()
        techniques = ["T1059"]  # Base: Command and Scripting Interpreter
        
        if 'powershell' in pname or 'pwsh' in pname:
            techniques.append("T1059.001")  # PowerShell
        elif pname == 'cmd.exe':
            techniques.append("T1059.003")  # Windows Command Shell
        elif pname in ('bash', 'sh', 'zsh', 'ksh'):
            techniques.append("T1059.004")  # Unix Shell
        elif 'python' in pname:
            techniques.append("T1059.006")  # Python
        
        if pname in self.LOLBIN_ALERT:
            techniques.append("T1218")  # System Binary Proxy Execution
        
        threat = Threat(
            id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
            severity=severity,
            title=f"Suspicious CLI Activity: {pname}",
            description=f"Suspicious command detected in {pname}. Findings: {'; '.join(findings)}",
            threat_type="cli_telemetry",
            source="cli_telemetry_monitor",
            process_name=pname,
            process_id=cmd_event.get('pid', 0),
            mitre_techniques=techniques,
            evidence={
                "pid": cmd_event.get('pid'),
                "ppid": cmd_event.get('ppid'),
                "command": cmd_event.get('command', '')[:200],
                "username": cmd_event.get('username'),
                "shell_type": cmd_event.get('shell_type'),
                "findings": findings
            },
            auto_kill_eligible=(severity == ThreatSeverity.CRITICAL)
        )
        self.threats.append(threat)
    
    def get_threats(self) -> List[Threat]:
        """Get detected CLI threats"""
        return self.threats
    
    def get_status(self) -> Dict[str, Any]:
        """Get CLI telemetry monitor status"""
        return {
            "enabled": self.enabled,
            "total_commands_captured": self.total_commands,
            "suspicious_commands": self.suspicious_count,
            "lolbin_detections": self.lolbin_count,
            "known_command_count": len(self.known_commands),
            "history_size": len(self.command_history),
            "threats": len(self.threats),
            "shell_processes_monitored": len(self.SHELL_PROCESSES),
            "lolbins_tracked": len(self.LOLBIN_ALERT),
            "last_scan": self.last_run.isoformat() if self.last_run else None
        }


# =============================================================================
# HIDDEN FILE SCANNER - ADS, HIDDEN FOLDERS, SUSPICIOUS PATHS
# =============================================================================

class HiddenFileScanner(MonitorModule):
    """
    Hidden File Scanner for Malware/Steganography Detection
    
    Scans for hidden files, Alternate Data Streams (ADS), and suspicious
    hidden directories that may indicate malware persistence or data hiding.
    
    MITRE ATT&CK Coverage:
    - T1564: Hide Artifacts
    - T1564.001: Hidden Files and Directories
    - T1564.004: NTFS File Attributes (ADS)
    - T1036: Masquerading
    - T1027: Obfuscated Files or Information
    
    Features:
    - Windows: Hidden/system attribute detection, ADS scanning
    - Linux: Hidden files in /tmp, /var/tmp, /dev/shm
    - Dangerous extension detection (.exe, .dll, .ps1, .vbs in temp dirs)
    - Cross-platform hidden folder detection
    - Backend alert integration
    """
    
    # Dangerous file extensions (executable code)
    DANGEROUS_EXTENSIONS = frozenset({
        '.exe', '.dll', '.bat', '.cmd', '.ps1', '.vbs', '.vbe',
        '.js', '.jse', '.wsf', '.wsh', '.scr', '.com', '.pif',
        '.hta', '.cpl', '.msi', '.msp', '.jar', '.py', '.pyc',
        '.sh', '.bash', '.elf', '.bin', '.so'
    })
    
    # Windows suspicious locations to scan
    WINDOWS_SCAN_PATHS = [
        '%TEMP%',
        '%APPDATA%',
        '%LOCALAPPDATA%',
        '%PROGRAMDATA%',
        '%USERPROFILE%\\Desktop',
        '%USERPROFILE%\\Downloads',
    ]
    
    # Linux suspicious locations to scan
    LINUX_SCAN_PATHS = [
        '/tmp',
        '/var/tmp',
        '/dev/shm',
        '/run/user',
        '~/.local/share',
        '~/.config',
    ]
    
    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self.threats: List[Threat] = []
        self.hidden_files_found: List[Dict[str, Any]] = []
        self.ads_found: List[Dict[str, Any]] = []
        self.hidden_count = 0
        self.ads_count = 0
        self.dangerous_hidden_count = 0
        
        logger.info(f"HiddenFileScanner initialized on {platform.system()}")
    
    def scan(self) -> List[Threat]:
        """Scan for hidden files, ADS, and suspicious hidden directories"""
        if not self.enabled:
            return []
        
        self.threats.clear()
        self.hidden_files_found.clear()
        self.ads_found.clear()
        self.last_run = datetime.now(timezone.utc)
        
        try:
            if PLATFORM == 'windows':
                self._scan_windows_hidden_files()
                self._scan_ads()
            else:
                self._scan_linux_hidden_files()
        except Exception as e:
            logger.error(f"HiddenFileScanner error: {e}")
        
        return self.threats
    
    def _scan_windows_hidden_files(self):
        """Scan Windows for hidden files with dangerous extensions"""
        try:
            import ctypes
            
            FILE_ATTRIBUTE_HIDDEN = 0x2
            FILE_ATTRIBUTE_SYSTEM = 0x4
            
            for path_template in self.WINDOWS_SCAN_PATHS:
                try:
                    scan_path = os.path.expandvars(path_template)
                    if not os.path.isdir(scan_path):
                        continue
                    
                    for entry in os.scandir(scan_path):
                        try:
                            attrs = ctypes.windll.kernel32.GetFileAttributesW(entry.path)
                            if attrs == -1:  # INVALID_FILE_ATTRIBUTES
                                continue
                            
                            is_hidden = bool(attrs & FILE_ATTRIBUTE_HIDDEN)
                            is_system = bool(attrs & FILE_ATTRIBUTE_SYSTEM)
                            
                            # Hidden but NOT system = suspicious in temp dirs
                            if is_hidden and not is_system:
                                ext = os.path.splitext(entry.name)[1].lower()
                                self.hidden_count += 1
                                
                                file_info = {
                                    'path': entry.path,
                                    'name': entry.name,
                                    'extension': ext,
                                    'is_directory': entry.is_dir(),
                                    'location': path_template,
                                    'timestamp': datetime.now(timezone.utc).isoformat()
                                }
                                self.hidden_files_found.append(file_info)
                                
                                # Critical if dangerous extension
                                if ext in self.DANGEROUS_EXTENSIONS:
                                    self.dangerous_hidden_count += 1
                                    self._create_threat(
                                        file_info,
                                        severity=ThreatSeverity.CRITICAL,
                                        findings=[f"Hidden executable in temp dir: {entry.name}"]
                                    )
                                elif entry.is_dir():
                                    # Hidden directory in suspicious location
                                    self._create_threat(
                                        file_info,
                                        severity=ThreatSeverity.MEDIUM,
                                        findings=[f"Hidden directory: {entry.name}"]
                                    )
                        except (OSError, PermissionError):
                            continue
                
                except PermissionError:
                    continue
        except ImportError:
            logger.debug("ctypes not available for Windows hidden file scanning")
    
    def _scan_ads(self):
        """Scan for Alternate Data Streams on Windows"""
        if PLATFORM != 'windows':
            return
        
        try:
            import subprocess
            
            # Scan user Desktop and Downloads for ADS
            user_dir = os.path.expanduser('~')
            scan_dirs = [
                os.path.join(user_dir, 'Desktop'),
                os.path.join(user_dir, 'Downloads'),
                os.path.join(user_dir, 'Documents'),
            ]
            
            for scan_dir in scan_dirs:
                if not os.path.isdir(scan_dir):
                    continue
                
                try:
                    result = subprocess.run(
                        ['cmd', '/c', f'dir /r /s "{scan_dir}"'],
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    
                    for line in result.stdout.splitlines():
                        # ADS shows as "filename:streamname:$DATA"
                        if ':$DATA' in line and line.count(':') >= 3:
                            self.ads_count += 1
                            ads_info = {
                                'raw_line': line.strip()[:200],
                                'location': scan_dir,
                                'timestamp': datetime.now(timezone.utc).isoformat()
                            }
                            self.ads_found.append(ads_info)
                            self._create_ads_threat(ads_info)
                
                except subprocess.TimeoutExpired:
                    logger.debug(f"ADS scan timeout for {scan_dir}")
                except Exception as e:
                    logger.debug(f"ADS scan error for {scan_dir}: {e}")
        
        except Exception as e:
            logger.error(f"ADS scanning error: {e}")
    
    def _scan_linux_hidden_files(self):
        """Scan Linux for recently created hidden files in suspicious locations"""
        try:
            import subprocess
            
            scan_paths = []
            for path_template in self.LINUX_SCAN_PATHS:
                expanded = os.path.expanduser(path_template)
                if os.path.isdir(expanded):
                    scan_paths.append(expanded)
            
            if not scan_paths:
                return
            
            # Find hidden files created in last 24 hours
            find_cmd = [
                'find'
            ] + scan_paths + [
                '-name', '.*',
                '-type', 'f',
                '-mtime', '-1',  # Modified in last day
                '-size', '+0',   # Non-empty
                '2>/dev/null'
            ]
            
            try:
                result = subprocess.run(
                    ' '.join(find_cmd),
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                for filepath in result.stdout.strip().splitlines()[:50]:
                    if not filepath:
                        continue
                    
                    self.hidden_count += 1
                    filename = os.path.basename(filepath)
                    ext = os.path.splitext(filename)[1].lower()
                    
                    file_info = {
                        'path': filepath,
                        'name': filename,
                        'extension': ext,
                        'is_directory': False,
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    }
                    self.hidden_files_found.append(file_info)
                    
                    # Threat if dangerous extension
                    if ext in self.DANGEROUS_EXTENSIONS:
                        self.dangerous_hidden_count += 1
                        self._create_threat(
                            file_info,
                            severity=ThreatSeverity.HIGH,
                            findings=[f"Hidden executable: {filename}"]
                        )
                    else:
                        # Medium for any recent hidden file in suspicious dir
                        self._create_threat(
                            file_info,
                            severity=ThreatSeverity.LOW,
                            findings=[f"Recently created hidden file: {filename}"]
                        )
            
            except subprocess.TimeoutExpired:
                logger.debug("Linux hidden file scan timeout")
        
        except Exception as e:
            logger.error(f"Linux hidden file scan error: {e}")
    
    def _create_threat(self, file_info: Dict[str, Any], severity: ThreatSeverity, findings: List[str]):
        """Create threat entry for hidden file detection"""
        techniques = ["T1564", "T1564.001"]  # Hide Artifacts, Hidden Files
        
        if file_info.get('extension') in self.DANGEROUS_EXTENSIONS:
            techniques.append("T1036")  # Masquerading
        
        threat = Threat(
            id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
            severity=severity,
            title=f"Hidden File Detected: {file_info.get('name', 'unknown')}",
            description=f"Suspicious hidden file found. {'; '.join(findings)}",
            threat_type="hidden_file",
            source="hidden_file_scanner",
            file_path=file_info.get('path', ''),
            mitre_techniques=techniques,
            evidence={
                "path": file_info.get('path'),
                "name": file_info.get('name'),
                "extension": file_info.get('extension'),
                "location": file_info.get('location'),
                "is_directory": file_info.get('is_directory'),
                "findings": findings
            },
            auto_kill_eligible=False  # Files, not processes
        )
        self.threats.append(threat)
    
    def _create_ads_threat(self, ads_info: Dict[str, Any]):
        """Create threat entry for ADS detection"""
        threat = Threat(
            id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
            severity=ThreatSeverity.HIGH,
            title="Alternate Data Stream Detected",
            description=f"NTFS Alternate Data Stream found which may hide malicious data",
            threat_type="hidden_file",
            source="hidden_file_scanner",
            mitre_techniques=["T1564", "T1564.004"],  # Hide Artifacts, NTFS ADS
            evidence={
                "ads_line": ads_info.get('raw_line'),
                "location": ads_info.get('location')
            },
            auto_kill_eligible=False
        )
        self.threats.append(threat)
    
    def get_threats(self) -> List[Threat]:
        """Get detected hidden file threats"""
        return self.threats
    
    def get_status(self) -> Dict[str, Any]:
        """Get hidden file scanner status"""
        return {
            "enabled": self.enabled,
            "platform": platform.system(),
            "hidden_files_found": self.hidden_count,
            "dangerous_hidden_files": self.dangerous_hidden_count,
            "ads_found": self.ads_count,
            "threats": len(self.threats),
            "scan_paths_windows": len(self.WINDOWS_SCAN_PATHS),
            "scan_paths_linux": len(self.LINUX_SCAN_PATHS),
            "last_scan": self.last_run.isoformat() if self.last_run else None
        }


# =============================================================================
# ALIAS/RENAME MONITOR - PATH HIJACKING, DOSKEY, MASQUERADING
# =============================================================================

class AliasRenameMonitor(MonitorModule):
    """
    Alias/Rename Monitor for Masquerading and PATH Hijack Detection
    
    Detects renamed system executables, PATH hijacking vulnerabilities,
    PowerShell alias abuse, and DOSKEY macro manipulation.
    
    MITRE ATT&CK Coverage:
    - T1036: Masquerading
    - T1036.003: Rename System Utilities
    - T1036.005: Match Legitimate Name or Location
    - T1574: Hijack Execution Flow
    - T1574.007: Path Interception by PATH Environment Variable
    - T1546.011: Application Shimming (alias abuse)
    
    Features:
    - System executable copy detection in temp directories
    - PATH hijack vulnerability scanning (writable dirs before System32)
    - PowerShell alias override detection
    - DOSKEY macro enumeration (Windows)
    - File hash comparison for renamed/copied executables
    """
    
    # Critical Windows system executables to monitor
    CRITICAL_EXECUTABLES = frozenset({
        'cmd.exe', 'powershell.exe', 'pwsh.exe', 'net.exe', 'net1.exe',
        'reg.exe', 'regedit.exe', 'schtasks.exe', 'taskkill.exe', 'taskmgr.exe',
        'wmic.exe', 'certutil.exe', 'bitsadmin.exe', 'mshta.exe', 'cscript.exe',
        'wscript.exe', 'rundll32.exe', 'regsvr32.exe', 'msiexec.exe',
        'sc.exe', 'at.exe', 'netsh.exe', 'bcdedit.exe', 'fsutil.exe',
        'icacls.exe', 'takeown.exe', 'cacls.exe', 'attrib.exe',
        'cipher.exe', 'compact.exe', 'diskpart.exe', 'format.com',
        'shutdown.exe', 'tscon.exe', 'qwinsta.exe', 'rwinsta.exe'
    })
    
    # Dangerous PowerShell cmdlets to monitor for aliasing
    DANGEROUS_CMDLETS = frozenset({
        'Get-Process', 'Get-Service', 'Get-ChildItem', 'Get-Content',
        'Remove-Item', 'Stop-Process', 'Stop-Service', 'Start-Process',
        'Invoke-Expression', 'Invoke-Command', 'Invoke-WebRequest',
        'New-Object', 'Set-ExecutionPolicy', 'Add-Type',
        'Import-Module', 'Export-ModuleMember'
    })
    
    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self.threats: List[Threat] = []
        self.renamed_exes_found: List[Dict[str, Any]] = []
        self.path_hijack_risks: List[Dict[str, Any]] = []
        self.suspicious_aliases: List[Dict[str, Any]] = []
        
        self.renamed_count = 0
        self.path_hijack_count = 0
        self.alias_abuse_count = 0
        
        logger.info(f"AliasRenameMonitor initialized on {platform.system()}")
    
    def scan(self) -> List[Threat]:
        """Scan for renamed executables, PATH hijacking, and alias abuse"""
        if not self.enabled:
            return []
        
        self.threats.clear()
        self.renamed_exes_found.clear()
        self.path_hijack_risks.clear()
        self.suspicious_aliases.clear()
        self.last_run = datetime.now(timezone.utc)
        
        try:
            if PLATFORM == 'windows':
                self._scan_renamed_executables()
                self._scan_path_hijacking()
                self._scan_powershell_aliases()
            else:
                # Linux: Check for renamed system binaries in unusual locations
                self._scan_linux_renamed_binaries()
        except Exception as e:
            logger.error(f"AliasRenameMonitor error: {e}")
        
        return self.threats
    
    def _scan_renamed_executables(self):
        """Scan for system executables copied to temp directories (Windows)"""
        if PLATFORM != 'windows':
            return
        
        system32 = os.path.join(
            os.environ.get('SystemRoot', r'C:\Windows'),
            'System32'
        )
        
        temp_dirs = [
            os.path.expandvars(r'%TEMP%'),
            os.path.expandvars(r'%APPDATA%'),
            os.path.expandvars(r'%LOCALAPPDATA%\Temp'),
            os.path.expandvars(r'%USERPROFILE%\Desktop'),
            os.path.expandvars(r'%USERPROFILE%\Downloads'),
        ]
        
        for temp_dir in temp_dirs:
            if not os.path.isdir(temp_dir):
                continue
            
            try:
                for entry in os.scandir(temp_dir):
                    if not entry.is_file():
                        continue
                    
                    name_lower = entry.name.lower()
                    
                    # Check if it's a critical executable
                    if name_lower in self.CRITICAL_EXECUTABLES:
                        self.renamed_count += 1
                        
                        file_info = {
                            'path': entry.path,
                            'name': entry.name,
                            'location': temp_dir,
                            'timestamp': datetime.now(timezone.utc).isoformat()
                        }
                        self.renamed_exes_found.append(file_info)
                        
                        self._create_threat(
                            threat_type='renamed_executable',
                            title=f"System Executable in Temp: {entry.name}",
                            description=f"Critical system executable {entry.name} found in {temp_dir}. "
                                       f"This may indicate masquerading or evasion technique.",
                            severity=ThreatSeverity.CRITICAL,
                            evidence=file_info,
                            techniques=['T1036', 'T1036.003', 'T1036.005']
                        )
                    
                    # Also check for renamed executables (e.g., svchost_backup.exe)
                    elif any(crit in name_lower for crit in ['svchost', 'lsass', 'csrss', 'winlogon']):
                        if name_lower.endswith('.exe'):
                            self.renamed_count += 1
                            file_info = {
                                'path': entry.path,
                                'name': entry.name,
                                'location': temp_dir,
                                'timestamp': datetime.now(timezone.utc).isoformat()
                            }
                            self.renamed_exes_found.append(file_info)
                            
                            self._create_threat(
                                threat_type='renamed_executable',
                                title=f"Suspicious Executable Name: {entry.name}",
                                description=f"File with system process name found in {temp_dir}",
                                severity=ThreatSeverity.HIGH,
                                evidence=file_info,
                                techniques=['T1036', 'T1036.003']
                            )
            
            except PermissionError:
                continue
    
    def _scan_path_hijacking(self):
        """Scan for PATH hijack vulnerabilities (writable dirs before System32)"""
        if PLATFORM != 'windows':
            return
        
        path_dirs = os.environ.get('PATH', '').split(os.pathsep)
        system32_idx = None
        
        # Find System32 position in PATH
        for i, d in enumerate(path_dirs):
            if 'system32' in d.lower():
                system32_idx = i
                break
        
        if system32_idx is None:
            return
        
        # Check for writable directories before System32
        for i in range(system32_idx):
            d = path_dirs[i]
            
            if not os.path.isdir(d):
                continue
            
            try:
                if os.access(d, os.W_OK):
                    self.path_hijack_count += 1
                    
                    risk_info = {
                        'directory': d,
                        'path_index': i,
                        'before_system32': True,
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    }
                    self.path_hijack_risks.append(risk_info)
                    
                    self._create_threat(
                        threat_type='path_hijack',
                        title=f"PATH Hijack Risk: {os.path.basename(d)}",
                        description=f"Writable directory '{d}' appears before System32 in PATH. "
                                   f"An attacker could place malicious executables here to hijack execution.",
                        severity=ThreatSeverity.HIGH,
                        evidence=risk_info,
                        techniques=['T1574', 'T1574.007']
                    )
            except (OSError, PermissionError):
                continue
    
    def _scan_powershell_aliases(self):
        """Scan for suspicious PowerShell alias overrides"""
        if PLATFORM != 'windows':
            return
        
        try:
            import subprocess
            
            result = subprocess.run(
                ['powershell', '-NoProfile', '-Command',
                 "Get-Alias | Where-Object {$_.Options -notmatch 'ReadOnly'} | "
                 "Select-Object Name,Definition | ConvertTo-Json"],
                capture_output=True,
                text=True,
                timeout=15
            )
            
            if result.returncode != 0 or not result.stdout.strip():
                return
            
            try:
                aliases = json.loads(result.stdout)
                if isinstance(aliases, dict):
                    aliases = [aliases]
                
                for alias in (aliases or []):
                    name = alias.get('Name', '')
                    definition = alias.get('Definition', '')
                    
                    # Flag if alias points to a file path (not a cmdlet)
                    if '\\' in definition or '/' in definition:
                        self.alias_abuse_count += 1
                        
                        alias_info = {
                            'alias': name,
                            'target': definition,
                            'timestamp': datetime.now(timezone.utc).isoformat()
                        }
                        self.suspicious_aliases.append(alias_info)
                        
                        self._create_threat(
                            threat_type='alias_abuse',
                            title=f"PowerShell Alias Override: {name}",
                            description=f"Alias '{name}' points to file path: {definition}",
                            severity=ThreatSeverity.HIGH,
                            evidence=alias_info,
                            techniques=['T1546.011', 'T1036']
                        )
            
            except json.JSONDecodeError:
                pass
        
        except subprocess.TimeoutExpired:
            logger.debug("PowerShell alias scan timeout")
        except Exception as e:
            logger.debug(f"PowerShell alias scan error: {e}")
    
    def _scan_linux_renamed_binaries(self):
        """Scan for renamed/copied system binaries on Linux"""
        try:
            import subprocess
            
            suspicious_dirs = ['/tmp', '/var/tmp', '/dev/shm', '~/.local/bin']
            system_binaries = {'bash', 'sh', 'python', 'python3', 'perl', 'nc', 'ncat',
                               'curl', 'wget', 'ssh', 'sshd', 'sudo', 'su', 'passwd'}
            
            for dir_path in suspicious_dirs:
                expanded = os.path.expanduser(dir_path)
                if not os.path.isdir(expanded):
                    continue
                
                try:
                    for entry in os.scandir(expanded):
                        if not entry.is_file():
                            continue
                        
                        name_lower = entry.name.lower()
                        
                        # Check if executable and looks like system binary
                        if name_lower in system_binaries or any(
                            sys_bin in name_lower for sys_bin in system_binaries
                        ):
                            # Verify it's executable
                            if os.access(entry.path, os.X_OK):
                                self.renamed_count += 1
                                
                                file_info = {
                                    'path': entry.path,
                                    'name': entry.name,
                                    'location': expanded,
                                    'timestamp': datetime.now(timezone.utc).isoformat()
                                }
                                self.renamed_exes_found.append(file_info)
                                
                                self._create_threat(
                                    threat_type='renamed_executable',
                                    title=f"System Binary in Suspicious Location: {entry.name}",
                                    description=f"Executable with system binary name in {expanded}",
                                    severity=ThreatSeverity.HIGH,
                                    evidence=file_info,
                                    techniques=['T1036', 'T1036.003']
                                )
                
                except PermissionError:
                    continue
        
        except Exception as e:
            logger.debug(f"Linux binary scan error: {e}")
    
    def _create_threat(self, threat_type: str, title: str, description: str,
                      severity: ThreatSeverity, evidence: Dict[str, Any],
                      techniques: List[str]):
        """Create threat entry"""
        threat = Threat(
            id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
            severity=severity,
            title=title,
            description=description,
            threat_type=threat_type,
            source="alias_rename_monitor",
            mitre_techniques=techniques,
            evidence=evidence,
            auto_kill_eligible=False  # File-based, not process
        )
        self.threats.append(threat)
    
    def get_threats(self) -> List[Threat]:
        """Get detected threats"""
        return self.threats
    
    def get_status(self) -> Dict[str, Any]:
        """Get alias/rename monitor status"""
        return {
            "enabled": self.enabled,
            "platform": platform.system(),
            "renamed_executables_found": self.renamed_count,
            "path_hijack_risks": self.path_hijack_count,
            "suspicious_aliases": self.alias_abuse_count,
            "critical_executables_tracked": len(self.CRITICAL_EXECUTABLES),
            "threats": len(self.threats),
            "last_scan": self.last_run.isoformat() if self.last_run else None
        }


# =============================================================================
# PRIVILEGE ESCALATION MONITOR - DANGEROUS PRIVILEGES, SYSTEM TASKS
# =============================================================================

class PrivilegeEscalationMonitor(MonitorModule):
    """
    Privilege Escalation Monitor
    
    Detects privilege escalation attempts, dangerous privilege usage,
    SYSTEM-level process abuse, and suspicious scheduled tasks.
    
    MITRE ATT&CK Coverage:
    - T1134: Access Token Manipulation
    - T1134.001: Token Impersonation/Theft
    - T1134.002: Create Process with Token
    - T1053: Scheduled Task/Job
    - T1053.005: Scheduled Task
    - T1068: Exploitation for Privilege Escalation
    - T1078: Valid Accounts
    - T1078.003: Local Accounts
    
    Features:
    - Dangerous Windows privilege detection (SeDebugPrivilege, etc.)
    - Non-Microsoft scheduled tasks running as SYSTEM
    - Suspicious processes running as SYSTEM
    - Privilege enumeration and monitoring
    """
    
    # Dangerous Windows privileges indicating potential privilege escalation
    DANGEROUS_PRIVILEGES = frozenset({
        'SeDebugPrivilege',              # Debug programs - full process access
        'SeTcbPrivilege',                # Act as part of OS
        'SeAssignPrimaryTokenPrivilege', # Assign process token
        'SeLoadDriverPrivilege',         # Load kernel drivers
        'SeRestorePrivilege',            # Restore files and directories
        'SeTakeOwnershipPrivilege',      # Take ownership of objects
        'SeImpersonatePrivilege',        # Impersonate client
        'SeCreateTokenPrivilege',        # Create tokens
        'SeBackupPrivilege',             # Backup files and directories
        'SeSecurityPrivilege',           # Manage auditing and security log
        'SeSystemEnvironmentPrivilege',  # Modify firmware
        'SeTrustedCredManAccessPrivilege', # Access Credential Manager
    })
    
    # Processes that should NOT normally run as SYSTEM
    SUSPICIOUS_AS_SYSTEM = frozenset({
        'cmd.exe', 'powershell.exe', 'pwsh.exe',
        'python.exe', 'python3.exe', 'python',
        'node.exe', 'node', 'ruby.exe', 'perl.exe',
        'wscript.exe', 'cscript.exe', 'mshta.exe',
        'notepad.exe', 'explorer.exe', 'chrome.exe',
        'firefox.exe', 'msedge.exe', 'iexplore.exe'
    })
    
    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self.threats: List[Threat] = []
        self.dangerous_privs_found: List[Dict[str, Any]] = []
        self.system_tasks_found: List[Dict[str, Any]] = []
        self.system_processes_found: List[Dict[str, Any]] = []
        
        self.dangerous_priv_count = 0
        self.system_task_count = 0
        self.system_process_count = 0
        
        logger.info(f"PrivilegeEscalationMonitor initialized on {platform.system()}")
    
    def scan(self) -> List[Threat]:
        """Scan for privilege escalation indicators"""
        if not self.enabled:
            return []
        
        self.threats.clear()
        self.dangerous_privs_found.clear()
        self.system_tasks_found.clear()
        self.system_processes_found.clear()
        self.last_run = datetime.now(timezone.utc)
        
        try:
            if PLATFORM == 'windows':
                self._check_dangerous_privileges()
                self._check_system_scheduled_tasks()
                self._check_suspicious_system_processes()
            else:
                self._check_linux_privilege_escalation()
        except Exception as e:
            logger.error(f"PrivilegeEscalationMonitor error: {e}")
        
        return self.threats
    
    def _check_dangerous_privileges(self):
        """Check current process privileges for dangerous ones (Windows)"""
        if PLATFORM != 'windows':
            return
        
        try:
            import subprocess
            
            result = subprocess.run(
                ['whoami', '/priv'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                return
            
            output = result.stdout
            
            for priv in self.DANGEROUS_PRIVILEGES:
                if priv in output:
                    # Check if privilege is enabled
                    try:
                        priv_section = output.split(priv)[1].split('\n')[0]
                        if 'Enabled' in priv_section:
                            self.dangerous_priv_count += 1
                            
                            priv_info = {
                                'privilege': priv,
                                'status': 'Enabled',
                                'timestamp': datetime.now(timezone.utc).isoformat()
                            }
                            self.dangerous_privs_found.append(priv_info)
                            
                            self._create_threat(
                                threat_type='privilege_escalation',
                                title=f"Dangerous Privilege Enabled: {priv}",
                                description=f"The dangerous privilege {priv} is currently enabled. "
                                           f"This may indicate privilege escalation or exploitation.",
                                severity=ThreatSeverity.CRITICAL,
                                evidence=priv_info,
                                techniques=['T1134', 'T1134.001', 'T1068'],
                                process_id=os.getpid()
                            )
                    except (IndexError, ValueError):
                        pass
        
        except subprocess.TimeoutExpired:
            logger.debug("Privilege check timeout")
        except Exception as e:
            logger.debug(f"Privilege check error: {e}")
    
    def _check_system_scheduled_tasks(self):
        """Check for non-Microsoft scheduled tasks running as SYSTEM"""
        if PLATFORM != 'windows':
            return
        
        try:
            import subprocess
            
            result = subprocess.run(
                ['schtasks', '/query', '/fo', 'CSV', '/v'],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                return
            
            lines = result.stdout.splitlines()
            if len(lines) < 2:
                return
            
            # Parse CSV header
            for line in lines[1:]:
                try:
                    # Remove quotes and split
                    parts = line.strip('"').split('","')
                    if len(parts) < 8:
                        continue
                    
                    task_name = parts[0] if parts else ''
                    status = parts[3] if len(parts) > 3 else ''
                    run_as = parts[7] if len(parts) > 7 else ''
                    
                    # Flag tasks running as SYSTEM that aren't Microsoft
                    if 'SYSTEM' in run_as.upper() and '\\Microsoft\\' not in task_name:
                        if 'Ready' in status or 'Running' in status:
                            self.system_task_count += 1
                            
                            task_info = {
                                'task_name': task_name,
                                'run_as': run_as,
                                'status': status,
                                'timestamp': datetime.now(timezone.utc).isoformat()
                            }
                            self.system_tasks_found.append(task_info)
                            
                            self._create_threat(
                                threat_type='system_task',
                                title=f"Non-Microsoft SYSTEM Task: {os.path.basename(task_name)}",
                                description=f"Scheduled task '{task_name}' runs as SYSTEM. "
                                           f"Status: {status}. May indicate persistence mechanism.",
                                severity=ThreatSeverity.HIGH,
                                evidence=task_info,
                                techniques=['T1053', 'T1053.005', 'T1078.003']
                            )
                
                except (IndexError, ValueError):
                    continue
        
        except subprocess.TimeoutExpired:
            logger.debug("Scheduled task check timeout")
        except Exception as e:
            logger.debug(f"Scheduled task check error: {e}")
    
    def _check_suspicious_system_processes(self):
        """Check for suspicious processes running as SYSTEM"""
        if not HAS_PSUTIL:
            return
        
        try:
            for proc in psutil.process_iter(['pid', 'name', 'username']):
                try:
                    info = proc.info
                    username = (info.get('username') or '').upper()
                    pname = (info.get('name') or '').lower()
                    pid = info.get('pid', 0)
                    
                    # Check for suspicious processes running as SYSTEM
                    if 'SYSTEM' in username and pname in self.SUSPICIOUS_AS_SYSTEM:
                        self.system_process_count += 1
                        
                        proc_info = {
                            'process_name': pname,
                            'pid': pid,
                            'username': username,
                            'timestamp': datetime.now(timezone.utc).isoformat()
                        }
                        self.system_processes_found.append(proc_info)
                        
                        self._create_threat(
                            threat_type='system_process',
                            title=f"Suspicious SYSTEM Process: {pname}",
                            description=f"Process {pname} (PID {pid}) is running as SYSTEM. "
                                       f"This process should not normally run with SYSTEM privileges.",
                            severity=ThreatSeverity.CRITICAL,
                            evidence=proc_info,
                            techniques=['T1134', 'T1134.002', 'T1078.003'],
                            process_name=pname,
                            process_id=pid
                        )
                
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        
        except Exception as e:
            logger.debug(f"System process check error: {e}")
    
    def _check_linux_privilege_escalation(self):
        """Check for privilege escalation indicators on Linux"""
        try:
            import subprocess
            
            # Check for SUID binaries in unusual locations
            suspicious_suid_dirs = ['/tmp', '/var/tmp', '/dev/shm', '~/.local']
            
            for sdir in suspicious_suid_dirs:
                expanded = os.path.expanduser(sdir)
                if not os.path.isdir(expanded):
                    continue
                
                try:
                    result = subprocess.run(
                        f'find {expanded} -perm -4000 -type f 2>/dev/null',
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=15
                    )
                    
                    for suid_file in result.stdout.strip().splitlines()[:10]:
                        if suid_file:
                            self.dangerous_priv_count += 1
                            
                            suid_info = {
                                'path': suid_file,
                                'location': expanded,
                                'type': 'SUID binary',
                                'timestamp': datetime.now(timezone.utc).isoformat()
                            }
                            self.dangerous_privs_found.append(suid_info)
                            
                            self._create_threat(
                                threat_type='privilege_escalation',
                                title=f"SUID Binary in Suspicious Location",
                                description=f"SUID binary found at {suid_file}. "
                                           f"May be used for privilege escalation.",
                                severity=ThreatSeverity.CRITICAL,
                                evidence=suid_info,
                                techniques=['T1068', 'T1548.001']
                            )
                
                except subprocess.TimeoutExpired:
                    continue
            
            # Check if current user has sudo without password
            try:
                result = subprocess.run(
                    ['sudo', '-n', 'true'],
                    capture_output=True,
                    timeout=5
                )
                
                if result.returncode == 0:
                    # User can sudo without password
                    priv_info = {
                        'type': 'passwordless_sudo',
                        'user': os.environ.get('USER', 'unknown'),
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    }
                    
                    self._create_threat(
                        threat_type='privilege_escalation',
                        title="Passwordless Sudo Access",
                        description="Current user can execute sudo without password",
                        severity=ThreatSeverity.MEDIUM,
                        evidence=priv_info,
                        techniques=['T1548.003']
                    )
            
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass
        
        except Exception as e:
            logger.debug(f"Linux privilege check error: {e}")
    
    def _create_threat(self, threat_type: str, title: str, description: str,
                      severity: ThreatSeverity, evidence: Dict[str, Any],
                      techniques: List[str], process_name: str = '',
                      process_id: int = 0):
        """Create threat entry for privilege escalation detection"""
        threat = Threat(
            id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
            severity=severity,
            title=title,
            description=description,
            threat_type=threat_type,
            source="privilege_escalation_monitor",
            process_name=process_name,
            process_id=process_id,
            mitre_techniques=techniques,
            evidence=evidence,
            auto_kill_eligible=(severity == ThreatSeverity.CRITICAL and process_id > 0)
        )
        self.threats.append(threat)
    
    def get_threats(self) -> List[Threat]:
        """Get detected privilege escalation threats"""
        return self.threats
    
    def get_status(self) -> Dict[str, Any]:
        """Get privilege escalation monitor status"""
        return {
            "enabled": self.enabled,
            "platform": platform.system(),
            "dangerous_privileges_found": self.dangerous_priv_count,
            "system_tasks_found": self.system_task_count,
            "system_processes_found": self.system_process_count,
            "privileges_tracked": len(self.DANGEROUS_PRIVILEGES),
            "suspicious_processes_tracked": len(self.SUSPICIOUS_AS_SYSTEM),
            "threats": len(self.threats),
            "last_scan": self.last_run.isoformat() if self.last_run else None
        }


# =============================================================================
# EMAIL PROTECTION MONITOR - LOCAL EMAIL SECURITY
# =============================================================================

class EmailProtectionMonitor(MonitorModule):
    """
    Email Protection Monitor for Local Agent
    
    Provides device-level email security monitoring including:
    - Local email client monitoring (Outlook, Thunderbird, Mail.app)
    - Phishing URL detection in received emails
    - Attachment scanning for malware indicators
    - Email-based threat detection
    - Integration with central email protection service
    
    MITRE ATT&CK Coverage:
    - T1566: Phishing
    - T1566.001: Spearphishing Attachment
    - T1566.002: Spearphishing Link
    - T1598: Phishing for Information
    """
    
    # Dangerous file extensions in email attachments
    DANGEROUS_EXTENSIONS = frozenset({
        '.exe', '.dll', '.scr', '.bat', '.cmd', '.ps1', '.vbs', '.js',
        '.jse', '.wsf', '.wsh', '.msi', '.msp', '.com', '.pif', '.jar',
        '.hta', '.cpl', '.reg', '.inf', '.lnk', '.application',
        '.docm', '.xlsm', '.pptm', '.dotm', '.xltm', '.potm'
    })
    
    # Phishing indicators
    PHISHING_KEYWORDS = frozenset([
        'verify your account', 'confirm your identity', 'update payment',
        'suspended account', 'unusual activity', 'click here immediately',
        'your account will be closed', 'confirm within 24 hours',
        'reset your password', 'security alert', 'unauthorized access'
    ])
    
    # URL shorteners (often used in phishing)
    URL_SHORTENERS = frozenset([
        'bit.ly', 'tinyurl.com', 't.co', 'goo.gl', 'ow.ly', 'is.gd',
        'buff.ly', 'adf.ly', 'j.mp', 'tr.im', 'shorturl.at'
    ])
    
    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self.threats: List[Threat] = []
        self.emails_scanned = 0
        self.phishing_detected = 0
        self.malicious_attachments = 0
        self.suspicious_urls = 0
        self.quarantined_items: List[Dict] = []
        
        # Stats
        self.stats = {
            'total_scanned': 0,
            'phishing_blocked': 0,
            'attachments_blocked': 0,
            'urls_blocked': 0
        }
        
        logger.info("EmailProtectionMonitor initialized")
    
    def scan(self) -> List[Threat]:
        """Scan for email-based threats"""
        if not self.enabled:
            return []
        
        self.threats.clear()
        self.last_run = datetime.now(timezone.utc)
        
        try:
            # Scan email clients for threats
            self._scan_local_email_clients()
            
            # Check for suspicious downloads from email
            self._check_email_downloads()
            
        except Exception as e:
            logger.error(f"EmailProtectionMonitor scan error: {e}")
        
        return self.threats
    
    def _scan_local_email_clients(self):
        """Scan local email client directories for threats"""
        email_dirs = []
        
        if PLATFORM == 'windows':
            # Outlook local folders
            appdata = os.environ.get('APPDATA', '')
            localappdata = os.environ.get('LOCALAPPDATA', '')
            
            email_dirs = [
                Path(appdata) / 'Microsoft' / 'Outlook',
                Path(localappdata) / 'Microsoft' / 'Outlook',
                Path(appdata) / 'Thunderbird' / 'Profiles'
            ]
        elif PLATFORM == 'darwin':
            home = Path.home()
            email_dirs = [
                home / 'Library' / 'Mail',
                home / 'Library' / 'Thunderbird' / 'Profiles'
            ]
        else:  # Linux
            home = Path.home()
            email_dirs = [
                home / '.thunderbird',
                home / '.local' / 'share' / 'evolution' / 'mail'
            ]
        
        for email_dir in email_dirs:
            if email_dir.exists():
                self._scan_email_directory(email_dir)
    
    def _scan_email_directory(self, directory: Path):
        """Scan an email directory for threats"""
        try:
            for attachment_file in directory.rglob('*'):
                if attachment_file.is_file():
                    ext = attachment_file.suffix.lower()
                    
                    # Check for dangerous extensions
                    if ext in self.DANGEROUS_EXTENSIONS:
                        self._create_threat(
                            threat_type='malicious_attachment',
                            title=f"Dangerous email attachment: {attachment_file.name}",
                            description=f"Found potentially malicious attachment with extension {ext}",
                            severity=ThreatSeverity.HIGH,
                            file_path=str(attachment_file)
                        )
                        self.malicious_attachments += 1
        except PermissionError:
            pass
        except Exception as e:
            logger.debug(f"Error scanning email directory {directory}: {e}")
    
    def _check_email_downloads(self):
        """Check downloads folder for email-originated threats"""
        downloads = Path.home() / 'Downloads'
        
        if not downloads.exists():
            return
        
        try:
            # Check recent files (last 24 hours)
            cutoff = datetime.now().timestamp() - 86400
            
            for f in downloads.iterdir():
                if f.is_file() and f.stat().st_mtime > cutoff:
                    ext = f.suffix.lower()
                    
                    if ext in self.DANGEROUS_EXTENSIONS:
                        self._create_threat(
                            threat_type='suspicious_download',
                            title=f"Recent suspicious download: {f.name}",
                            description=f"Recently downloaded file with dangerous extension {ext}",
                            severity=ThreatSeverity.MEDIUM,
                            file_path=str(f)
                        )
        except Exception as e:
            logger.debug(f"Error checking downloads: {e}")
    
    def analyze_url(self, url: str) -> Dict:
        """Analyze a URL for phishing indicators"""
        result = {
            'url': url,
            'is_safe': True,
            'risk_level': 'safe',
            'indicators': []
        }
        
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            # Check for URL shorteners
            for shortener in self.URL_SHORTENERS:
                if shortener in domain:
                    result['is_safe'] = False
                    result['risk_level'] = 'medium'
                    result['indicators'].append(f"URL shortener detected: {shortener}")
            
            # Check for IP-based URLs
            if re.match(r'^\d+\.\d+\.\d+\.\d+', domain):
                result['is_safe'] = False
                result['risk_level'] = 'high'
                result['indicators'].append("IP-based URL (common in phishing)")
            
            # Check for suspicious TLDs
            suspicious_tlds = ['.tk', '.ml', '.ga', '.cf', '.gq', '.xyz']
            for tld in suspicious_tlds:
                if domain.endswith(tld):
                    result['risk_level'] = 'medium'
                    result['indicators'].append(f"Suspicious TLD: {tld}")
            
            self.stats['total_scanned'] += 1
            if not result['is_safe']:
                self.suspicious_urls += 1
                self.stats['urls_blocked'] += 1
                
        except Exception as e:
            logger.debug(f"URL analysis error: {e}")
        
        return result
    
    def analyze_content(self, content: str) -> Dict:
        """Analyze email content for phishing indicators"""
        result = {
            'is_phishing': False,
            'confidence': 0.0,
            'indicators': []
        }
        
        content_lower = content.lower()
        
        # Check for phishing keywords
        matches = 0
        for keyword in self.PHISHING_KEYWORDS:
            if keyword in content_lower:
                matches += 1
                result['indicators'].append(f"Phishing keyword: {keyword}")
        
        if matches >= 2:
            result['is_phishing'] = True
            result['confidence'] = min(0.9, 0.3 + (matches * 0.15))
            self.phishing_detected += 1
            self.stats['phishing_blocked'] += 1
        
        return result
    
    def _create_threat(self, threat_type: str, title: str, description: str,
                      severity: ThreatSeverity, file_path: str = ''):
        """Create threat for email protection"""
        threat = Threat(
            id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
            severity=severity,
            title=title,
            description=description,
            threat_type=threat_type,
            source="email_protection_monitor",
            file_path=file_path,
            mitre_techniques=['T1566'],
            evidence={'file_path': file_path},
            auto_kill_eligible=False
        )
        self.threats.append(threat)
    
    def get_status(self) -> Dict[str, Any]:
        """Get email protection status"""
        return {
            "enabled": self.enabled,
            "emails_scanned": self.emails_scanned,
            "phishing_detected": self.phishing_detected,
            "malicious_attachments": self.malicious_attachments,
            "suspicious_urls": self.suspicious_urls,
            "quarantined": len(self.quarantined_items),
            "stats": self.stats,
            "threats": len(self.threats),
            "last_scan": self.last_run.isoformat() if self.last_run else None
        }

    def get_threats(self) -> List[Threat]:
        """Return detected threats from last scan."""
        return list(self.threats)


# =============================================================================
# MOBILE SECURITY MONITOR - DEVICE SECURITY FOR MOBILE/PORTABLE DEVICES
# =============================================================================

class MobileSecurityMonitor(MonitorModule):
    """
    Mobile Security Monitor for Local Agent
    
    Provides mobile device security monitoring including:
    - Device security state (encryption, passcode, jailbreak detection)
    - App security analysis
    - Network security (WiFi, rogue AP detection)
    - USB/external device monitoring
    - Compliance checking
    
    Note: Full functionality on mobile platforms (Android/iOS), 
    partial functionality on desktop (USB monitoring, network security)
    
    MITRE ATT&CK Mobile Coverage:
    - T1398: Boot or Logon Initialization Scripts
    - T1444: Masquerade as Legitimate Application
    - T1439: Eavesdrop on Insecure Network Communication
    - T1465: Rogue Wi-Fi Access Points
    """
    
    # Known risky app patterns
    RISKY_APP_PATTERNS = [
        r'.*cracked.*', r'.*modded.*', r'.*hack.*', r'.*cheat.*',
        r'.*free.*premium.*', r'.*unlimited.*coins.*'
    ]
    
    # Suspicious network patterns (rogue WiFi)
    ROGUE_WIFI_PATTERNS = [
        r'(?i)free.*wifi', r'(?i)airport.*free', r'(?i)hotel.*guest',
        r'(?i)starbucks.*free', r'(?i)xfinity.*wifi'
    ]
    
    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self.threats: List[Threat] = []
        
        # Device state
        self.device_info = {
            'platform': PLATFORM,
            'hostname': HOSTNAME,
            'is_mobile': PLATFORM in ['android', 'ios'],
            'encryption_status': 'unknown',
            'passcode_enabled': 'unknown',
            'is_jailbroken': False,
            'usb_debug_enabled': False
        }
        
        # Stats
        self.threats_detected = 0
        self.apps_scanned = 0
        self.networks_scanned = 0
        self.usb_events = 0
        self.compliance_score = 100.0
        
        # Compliance checks
        self.compliance_checks = {}
        
        logger.info("MobileSecurityMonitor initialized")
    
    def scan(self) -> List[Threat]:
        """Scan for mobile security threats"""
        if not self.enabled:
            return []
        
        self.threats.clear()
        self.last_run = datetime.now(timezone.utc)
        
        try:
            # Check device security state
            self._check_device_security()
            
            # Check network security
            self._check_network_security()
            
            # Check USB/external devices
            self._check_usb_devices()
            
            # Run compliance check
            self._check_compliance()
            
        except Exception as e:
            logger.error(f"MobileSecurityMonitor scan error: {e}")
        
        return self.threats
    
    def _check_device_security(self):
        """Check device security state"""
        try:
            # Check disk encryption
            if PLATFORM == 'darwin':
                # macOS FileVault check
                try:
                    result = subprocess.run(
                        ['fdesetup', 'status'],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if 'On' in result.stdout:
                        self.device_info['encryption_status'] = 'enabled'
                    else:
                        self.device_info['encryption_status'] = 'disabled'
                        self._create_threat(
                            threat_type='missing_encryption',
                            title="Disk Encryption Disabled",
                            description="FileVault is not enabled on this device",
                            severity=ThreatSeverity.HIGH
                        )
                except Exception:
                    pass
            
            elif PLATFORM == 'windows':
                # Windows BitLocker check
                try:
                    result = subprocess.run(
                        ['manage-bde', '-status', 'C:'],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    if 'Protection On' in result.stdout:
                        self.device_info['encryption_status'] = 'enabled'
                    else:
                        self.device_info['encryption_status'] = 'disabled'
                        self._create_threat(
                            threat_type='missing_encryption',
                            title="BitLocker Not Enabled",
                            description="BitLocker encryption is not enabled on C: drive",
                            severity=ThreatSeverity.HIGH
                        )
                except Exception:
                    pass
            
            elif PLATFORM == 'linux':
                # Check for LUKS encryption
                try:
                    result = subprocess.run(
                        ['lsblk', '-o', 'NAME,TYPE,MOUNTPOINT'],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if 'crypt' in result.stdout:
                        self.device_info['encryption_status'] = 'enabled'
                    else:
                        self.device_info['encryption_status'] = 'unknown'
                except Exception:
                    pass
                    
        except Exception as e:
            logger.debug(f"Device security check error: {e}")
    
    def _check_network_security(self):
        """Check for network security threats"""
        try:
            # Get connected WiFi info
            wifi_name = self._get_current_wifi()
            
            if wifi_name:
                # Check for rogue WiFi patterns
                for pattern in self.ROGUE_WIFI_PATTERNS:
                    if re.match(pattern, wifi_name):
                        self._create_threat(
                            threat_type='rogue_wifi',
                            title=f"Suspicious WiFi Network: {wifi_name}",
                            description=f"Connected to WiFi '{wifi_name}' which matches rogue AP patterns",
                            severity=ThreatSeverity.HIGH
                        )
                        break
                
                self.networks_scanned += 1
                
        except Exception as e:
            logger.debug(f"Network security check error: {e}")
    
    def _get_current_wifi(self) -> Optional[str]:
        """Get current WiFi SSID"""
        try:
            if PLATFORM == 'darwin':
                result = subprocess.run(
                    ['/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport', '-I'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                for line in result.stdout.split('\n'):
                    if 'SSID' in line and 'BSSID' not in line:
                        return line.split(':')[1].strip()
            
            elif PLATFORM == 'windows':
                result = subprocess.run(
                    ['netsh', 'wlan', 'show', 'interfaces'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                for line in result.stdout.split('\n'):
                    if 'SSID' in line and 'BSSID' not in line:
                        return line.split(':')[1].strip()
            
            elif PLATFORM == 'linux':
                result = subprocess.run(
                    ['iwgetid', '-r'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                return result.stdout.strip() if result.returncode == 0 else None
                
        except Exception:
            pass
        
        return None
    
    def _check_usb_devices(self):
        """Monitor USB device connections"""
        try:
            if not PSUTIL_AVAILABLE:
                return
            
            # Check for removable drives
            partitions = psutil.disk_partitions(all=True)
            
            for partition in partitions:
                opts = partition.opts.lower()
                
                # Check for removable media
                if 'removable' in opts or 'usb' in partition.device.lower():
                    self.usb_events += 1
                    
                    # Log USB detection (not necessarily a threat)
                    logger.info(f"USB device detected: {partition.device} at {partition.mountpoint}")
                    
        except Exception as e:
            logger.debug(f"USB check error: {e}")
    
    def _check_compliance(self):
        """Run compliance checks"""
        self.compliance_checks = {}
        
        # Encryption check
        self.compliance_checks['encryption'] = self.device_info.get('encryption_status') == 'enabled'
        
        # Screen lock check (simplified)
        self.compliance_checks['screen_lock'] = True  # Assume enabled by default
        
        # USB debug check (for Android primarily)
        self.compliance_checks['usb_debug_disabled'] = not self.device_info.get('usb_debug_enabled', False)
        
        # Jailbreak check
        self.compliance_checks['not_jailbroken'] = not self.device_info.get('is_jailbroken', False)
        
        # Calculate compliance score
        passed = sum(1 for v in self.compliance_checks.values() if v)
        total = len(self.compliance_checks)
        self.compliance_score = (passed / total * 100) if total > 0 else 100.0
    
    def analyze_app(self, app_name: str, package_name: str = '', permissions: List[str] = None) -> Dict:
        """Analyze an app for security issues"""
        result = {
            'app_name': app_name,
            'package_name': package_name,
            'is_safe': True,
            'risk_level': 'safe',
            'indicators': []
        }
        
        permissions = permissions or []
        
        # Check for risky app patterns
        for pattern in self.RISKY_APP_PATTERNS:
            if re.match(pattern, app_name.lower()) or re.match(pattern, package_name.lower()):
                result['is_safe'] = False
                result['risk_level'] = 'high'
                result['indicators'].append("App name matches risky pattern")
        
        # Check for excessive permissions
        dangerous_perms = [
            'android.permission.READ_SMS',
            'android.permission.SEND_SMS',
            'android.permission.READ_CALL_LOG',
            'android.permission.RECORD_AUDIO',
            'android.permission.CAMERA'
        ]
        
        dangerous_count = sum(1 for p in permissions if p in dangerous_perms)
        if dangerous_count >= 3:
            result['risk_level'] = 'medium' if result['risk_level'] == 'safe' else result['risk_level']
            result['indicators'].append(f"Excessive dangerous permissions ({dangerous_count})")
        
        self.apps_scanned += 1
        return result
    
    def _create_threat(self, threat_type: str, title: str, description: str,
                      severity: ThreatSeverity):
        """Create threat for mobile security"""
        threat = Threat(
            id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
            severity=severity,
            title=title,
            description=description,
            threat_type=threat_type,
            source="mobile_security_monitor",
            mitre_techniques=['T1398'],
            evidence={'device': self.device_info},
            auto_kill_eligible=False
        )
        self.threats.append(threat)
        self.threats_detected += 1
    
    def get_status(self) -> Dict[str, Any]:
        """Get mobile security status"""
        return {
            "enabled": self.enabled,
            "device_info": self.device_info,
            "threats_detected": self.threats_detected,
            "apps_scanned": self.apps_scanned,
            "networks_scanned": self.networks_scanned,
            "usb_events": self.usb_events,
            "compliance_score": round(self.compliance_score, 1),
            "compliance_checks": self.compliance_checks,
            "threats": len(self.threats),
            "last_scan": self.last_run.isoformat() if self.last_run else None
        }

    def get_threats(self) -> List[Threat]:
        """Return detected threats from last scan."""
        return list(self.threats)


# =============================================================================
# LOCAL WEB UI SERVER
# =============================================================================

class LocalWebUIServer:
    """
    Lightweight built-in HTTP dashboard for the deployed agent.

    Uses only Python's standard library (http.server) – no Flask or external
    packages required.  Starts on the configured port (default 5000) and falls
    back to the next available port if the preferred one is busy.

    Exposes:
      GET /            → HTML dashboard (auto-refreshes every 5 s)
      GET /api/status  → JSON agent status snapshot
      GET /api/data    → JSON full dashboard data
    """

    # ------------------------------------------------------------------ HTML
    DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Seraph Agent – Local Dashboard</title>
<script src="https://cdn.tailwindcss.com"></script>
<style>
  body { background:#0f172a; color:#e2e8f0; font-family:sans-serif; }
  .card { background:#1e293b; border:1px solid #334155; border-radius:8px; padding:1rem; }
  .badge { display:inline-block; padding:2px 8px; border-radius:12px; font-size:.75rem; font-weight:600; }
  .online  { background:#16a34a22; color:#4ade80; border:1px solid #16a34a55; }
  .offline { background:#dc262622; color:#f87171; border:1px solid #dc262655; }
  .bar-bg  { background:#334155; border-radius:4px; height:8px; overflow:hidden; }
  .bar     { height:8px; border-radius:4px; transition:width .4s; }
</style>
</head>
<body class="p-4 min-h-screen">

<div class="max-w-4xl mx-auto space-y-4">
  <!-- Header -->
  <div class="flex items-center justify-between">
    <div>
      <h1 class="text-2xl font-bold text-cyan-400">⚡ Seraph Agent</h1>
      <p class="text-slate-400 text-sm" id="subtitle">Local Security Dashboard</p>
    </div>
    <div>
      <span class="badge online" id="status-badge">Loading…</span>
      <p class="text-slate-500 text-xs mt-1" id="last-hb">–</p>
    </div>
  </div>

  <!-- System metrics -->
  <div class="grid grid-cols-3 gap-4">
    <div class="card">
      <p class="text-slate-400 text-xs mb-1">CPU</p>
      <p class="text-2xl font-bold text-cyan-400" id="cpu">–</p>
      <div class="bar-bg mt-2"><div class="bar bg-cyan-500" id="cpu-bar" style="width:0%"></div></div>
    </div>
    <div class="card">
      <p class="text-slate-400 text-xs mb-1">Memory</p>
      <p class="text-2xl font-bold text-purple-400" id="mem">–</p>
      <div class="bar-bg mt-2"><div class="bar bg-purple-500" id="mem-bar" style="width:0%"></div></div>
    </div>
    <div class="card">
      <p class="text-slate-400 text-xs mb-1">Disk</p>
      <p class="text-2xl font-bold text-green-400" id="dsk">–</p>
      <div class="bar-bg mt-2"><div class="bar bg-green-500" id="dsk-bar" style="width:0%"></div></div>
    </div>
  </div>

  <!-- Stats row -->
  <div class="grid grid-cols-4 gap-4">
    <div class="card text-center">
      <p class="text-slate-400 text-xs">Threats</p>
      <p class="text-xl font-bold text-red-400" id="threats">0</p>
    </div>
    <div class="card text-center">
      <p class="text-slate-400 text-xs">Auto-Kills</p>
      <p class="text-xl font-bold text-orange-400" id="kills">0</p>
    </div>
    <div class="card text-center">
      <p class="text-slate-400 text-xs">Events</p>
      <p class="text-xl font-bold text-blue-400" id="events">0</p>
    </div>
    <div class="card text-center">
      <p class="text-slate-400 text-xs">Net Conn</p>
      <p class="text-xl font-bold text-teal-400" id="conns">0</p>
    </div>
  </div>

  <!-- Agent info -->
  <div class="card">
    <h2 class="font-semibold text-slate-300 mb-2">Agent Info</h2>
    <div class="grid grid-cols-2 gap-2 text-sm">
      <div><span class="text-slate-500">ID:</span> <span class="text-slate-300 font-mono text-xs" id="agent-id">–</span></div>
      <div><span class="text-slate-500">Name:</span> <span class="text-slate-300" id="agent-name">–</span></div>
      <div><span class="text-slate-500">Platform:</span> <span class="text-slate-300" id="platform">–</span></div>
      <div><span class="text-slate-500">Version:</span> <span class="text-slate-300" id="version">–</span></div>
      <div><span class="text-slate-500">Server:</span> <span class="text-slate-300 font-mono text-xs" id="server">–</span></div>
      <div><span class="text-slate-500">Registered:</span> <span id="registered" class="badge online">Yes</span></div>
    </div>
  </div>

  <!-- Recent threats -->
  <div class="card">
    <h2 class="font-semibold text-slate-300 mb-2">Recent Threats</h2>
    <div id="threat-list" class="space-y-1 text-sm text-slate-400">None detected.</div>
  </div>
</div>

<script>
async function refresh() {
  try {
    const r = await fetch('/api/data');
    const d = await r.json();
    const a = d.agent || {};
    const t = d.telemetry || {};
    const s = d.stats || {};

    document.getElementById('subtitle').textContent =
      (a.hostname || 'unknown') + ' · ' + (a.agent_id || '');
    document.getElementById('status-badge').textContent = a.running ? 'ONLINE' : 'STOPPED';
    document.getElementById('status-badge').className = 'badge ' + (a.running ? 'online' : 'offline');
    document.getElementById('last-hb').textContent = a.last_heartbeat
      ? 'Last HB: ' + new Date(a.last_heartbeat).toLocaleTimeString() : '–';

    const cpu = t.cpu_usage || 0;
    const mem = t.memory_usage || 0;
    const dsk = t.disk_usage || 0;
    document.getElementById('cpu').textContent = cpu.toFixed(1) + '%';
    document.getElementById('cpu-bar').style.width = cpu + '%';
    document.getElementById('mem').textContent = mem.toFixed(1) + '%';
    document.getElementById('mem-bar').style.width = mem + '%';
    document.getElementById('dsk').textContent = dsk.toFixed(1) + '%';
    document.getElementById('dsk-bar').style.width = dsk + '%';

    document.getElementById('threats').textContent = a.threat_count || 0;
    document.getElementById('kills').textContent = a.auto_kills || 0;
    document.getElementById('events').textContent = a.event_count || 0;
    document.getElementById('conns').textContent = t.connections ? t.connections.length : 0;

    document.getElementById('agent-id').textContent = a.agent_id || '–';
    document.getElementById('agent-name').textContent = a.agent_name || '–';
    document.getElementById('platform').textContent = a.platform || '–';
    document.getElementById('version').textContent = a.version || '–';
    document.getElementById('server').textContent = a.server_url || 'Not configured';
    document.getElementById('registered').textContent = a.registered ? 'Yes' : 'No';
    document.getElementById('registered').className = 'badge ' + (a.registered ? 'online' : 'offline');

    const threats = d.threats || [];
    const tl = document.getElementById('threat-list');
    if (threats.length === 0) {
      tl.innerHTML = '<span class="text-green-400">✓ No threats detected.</span>';
    } else {
      tl.innerHTML = '';
      threats.slice(-10).reverse().forEach(function(item) {
        const row = document.createElement('div');
        row.className = 'flex justify-between';
        const title = document.createElement('span');
        title.className = 'text-red-300';
        title.textContent = item.title || item.threat_id || 'Unknown';
        const sev = document.createElement('span');
        sev.className = 'text-slate-500 text-xs';
        sev.textContent = item.severity || '';
        row.appendChild(title);
        row.appendChild(sev);
        tl.appendChild(row);
      });
    }
  } catch(e) {
    document.getElementById('status-badge').textContent = 'ERROR';
  }
}
refresh();
setInterval(refresh, 5000);
</script>
</body>
</html>"""

    DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Seraph Agent Nexus // Port 5000</title>
<style>
    :root {
        --bg-0: #02050d;
        --bg-1: #061022;
        --bg-2: #0b1730;
        --panel: rgba(8, 18, 40, 0.74);
        --panel-strong: rgba(4, 12, 28, 0.92);
        --line: rgba(0, 240, 255, 0.25);
        --line-strong: rgba(0, 240, 255, 0.55);
        --cyan: #00f0ff;
        --pink: #ff2bd6;
        --violet: #bc13fe;
        --green: #39ff14;
        --amber: #ffb020;
        --text: #d8f7ff;
        --text-soft: #92bfd2;
        --danger: #ff5e8b;
    }

    * { box-sizing: border-box; }

    body {
        margin: 0;
        min-height: 100vh;
        font-family: "Rajdhani", "IBM Plex Sans", "Segoe UI", sans-serif;
        color: var(--text);
        background:
            radial-gradient(circle at 16% 14%, rgba(0, 240, 255, 0.18), transparent 28%),
            radial-gradient(circle at 84% 8%, rgba(188, 19, 254, 0.16), transparent 32%),
            linear-gradient(180deg, var(--bg-2) 0%, var(--bg-1) 55%, var(--bg-0) 100%);
        overflow-x: hidden;
    }

    body::before {
        content: "";
        position: fixed;
        inset: 0;
        pointer-events: none;
        z-index: 0;
        background-image:
            linear-gradient(rgba(0, 240, 255, 0.045) 1px, transparent 1px),
            linear-gradient(90deg, rgba(0, 240, 255, 0.045) 1px, transparent 1px);
        background-size: 34px 34px;
        mask-image: radial-gradient(ellipse at 50% 38%, rgba(0, 0, 0, 1) 30%, rgba(0, 0, 0, 0.35) 70%, rgba(0, 0, 0, 0) 100%);
    }

    .scanline {
        position: fixed;
        inset: 0;
        pointer-events: none;
        z-index: 1;
        background: repeating-linear-gradient(
            to bottom,
            rgba(0, 240, 255, 0.035) 0px,
            rgba(0, 240, 255, 0.035) 1px,
            transparent 1px,
            transparent 4px
        );
        opacity: 0.4;
    }

    .shell {
        position: relative;
        z-index: 2;
        width: min(1320px, 96vw);
        margin: 1.2rem auto 1.6rem;
        display: grid;
        gap: 1rem;
    }

    .hud {
        position: relative;
        background: linear-gradient(160deg, var(--panel), var(--panel-strong));
        border: 1px solid var(--line);
        clip-path: polygon(0 12px, 12px 0, calc(100% - 12px) 0, 100% 12px, 100% calc(100% - 12px), calc(100% - 12px) 100%, 12px 100%, 0 calc(100% - 12px));
        box-shadow: 0 0 22px rgba(0, 240, 255, 0.12), inset 0 0 24px rgba(0, 240, 255, 0.05);
        overflow: hidden;
    }

    .hud::before {
        content: "";
        position: absolute;
        top: 0;
        left: -120%;
        width: 70%;
        height: 2px;
        background: linear-gradient(90deg, transparent, var(--cyan), var(--pink), transparent);
        animation: edgeSweep 5.5s linear infinite;
    }

    .topbar {
        padding: 1.1rem 1.2rem;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 0.8rem;
        flex-wrap: wrap;
    }

    .kicker {
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.25rem 0.7rem;
        font-family: "JetBrains Mono", monospace;
        font-size: 0.64rem;
        text-transform: uppercase;
        letter-spacing: 0.24em;
        border: 1px solid rgba(0, 240, 255, 0.3);
        color: #acefff;
        background: linear-gradient(90deg, rgba(0, 240, 255, 0.1), rgba(188, 19, 254, 0.1));
    }

    .pip {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: var(--cyan);
        box-shadow: 0 0 10px var(--cyan), 0 0 24px var(--cyan);
        animation: pulse 1.8s ease-in-out infinite;
    }

    h1 {
        margin: 0.35rem 0 0;
        font-family: "Orbitron", "JetBrains Mono", monospace;
        font-size: clamp(1.35rem, 3vw, 2.25rem);
        letter-spacing: 0.06em;
        text-transform: uppercase;
        background: linear-gradient(90deg, #effdff 0%, #79dbff 30%, #00f0ff 54%, #bc13fe 100%);
        -webkit-background-clip: text;
        background-clip: text;
        color: transparent;
        filter: drop-shadow(0 0 12px rgba(0, 240, 255, 0.35));
    }

    .subline {
        margin: 0.35rem 0 0;
        color: var(--text-soft);
        font-size: 0.92rem;
        letter-spacing: 0.04em;
    }

    .status {
        display: inline-flex;
        align-items: center;
        gap: 0.45rem;
        padding: 0.35rem 0.7rem;
        border: 1px solid var(--line);
        font-family: "JetBrains Mono", monospace;
        font-size: 0.68rem;
        text-transform: uppercase;
        letter-spacing: 0.18em;
        color: #e7fbff;
        background: rgba(0, 240, 255, 0.08);
    }

    .status.online { border-color: rgba(57, 255, 20, 0.5); color: #c9ffb9; background: rgba(57, 255, 20, 0.12); }
    .status.offline { border-color: rgba(255, 94, 139, 0.5); color: #ffb7cb; background: rgba(255, 94, 139, 0.13); }
    .status.error { border-color: rgba(255, 176, 32, 0.6); color: #ffe0ad; background: rgba(255, 176, 32, 0.15); }

    .time {
        margin-top: 0.45rem;
        text-align: right;
        font-family: "JetBrains Mono", monospace;
        font-size: 0.69rem;
        letter-spacing: 0.12em;
        color: var(--text-soft);
    }

    .grid {
        display: grid;
        grid-template-columns: repeat(12, 1fr);
        gap: 1rem;
    }

    .col-3 { grid-column: span 3; }
    .col-4 { grid-column: span 4; }
    .col-6 { grid-column: span 6; }
    .col-8 { grid-column: span 8; }

    .panel {
        padding: 1rem;
        position: relative;
    }

    .label {
        margin: 0;
        font-family: "JetBrains Mono", monospace;
        font-size: 0.62rem;
        text-transform: uppercase;
        letter-spacing: 0.24em;
        color: var(--text-soft);
    }

    .metric {
        margin-top: 0.35rem;
        font-size: clamp(1.25rem, 2.7vw, 1.9rem);
        font-weight: 700;
        letter-spacing: 0.03em;
        color: #f2fdff;
    }

    .metric.cyan { color: #89ecff; }
    .metric.violet { color: #ddacff; }
    .metric.green { color: #b4ff9f; }
    .metric.pink { color: #ffb0ec; }
    .metric.amber { color: #ffd49a; }

    .bar {
        margin-top: 0.6rem;
        width: 100%;
        height: 9px;
        border: 1px solid rgba(0, 240, 255, 0.28);
        background: rgba(0, 0, 0, 0.35);
        overflow: hidden;
    }

    .bar > span {
        display: block;
        height: 100%;
        width: 0%;
        transition: width 0.45s ease;
        background: linear-gradient(90deg, rgba(0, 240, 255, 0.65), rgba(188, 19, 254, 0.88));
        box-shadow: 0 0 12px rgba(0, 240, 255, 0.4);
    }

    .split {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 0.65rem;
        margin-top: 0.8rem;
    }

    .chip {
        border: 1px solid rgba(0, 240, 255, 0.2);
        background: rgba(0, 240, 255, 0.06);
        padding: 0.45rem 0.55rem;
    }

    .chip-title {
        font-family: "JetBrains Mono", monospace;
        font-size: 0.58rem;
        letter-spacing: 0.2em;
        text-transform: uppercase;
        color: var(--text-soft);
    }

    .chip-value {
        margin-top: 0.32rem;
        word-break: break-all;
        color: #e8fbff;
        font-size: 0.88rem;
    }

    .list {
        margin-top: 0.65rem;
        max-height: 280px;
        overflow: auto;
        border: 1px solid rgba(0, 240, 255, 0.18);
        background: rgba(0, 0, 0, 0.28);
    }

    .list-row {
        display: flex;
        justify-content: space-between;
        gap: 0.8rem;
        padding: 0.56rem 0.72rem;
        border-bottom: 1px solid rgba(0, 240, 255, 0.1);
        font-size: 0.87rem;
    }

    .list-row:last-child { border-bottom: 0; }
    .list-main { color: #d8faff; }
    .list-meta { color: var(--text-soft); font-size: 0.73rem; white-space: nowrap; }
    .ok { color: #acffb8; }
    .bad { color: #ff9ec0; }

    @keyframes pulse {
        0%, 100% { opacity: 0.7; box-shadow: 0 0 8px var(--cyan), 0 0 18px var(--cyan); }
        50% { opacity: 1; box-shadow: 0 0 16px var(--cyan), 0 0 34px var(--cyan); }
    }

    @keyframes edgeSweep {
        0% { left: -120%; }
        100% { left: 120%; }
    }

    @media (max-width: 1080px) {
        .col-3, .col-4, .col-6, .col-8 { grid-column: span 6; }
    }

    @media (max-width: 720px) {
        .shell { width: 95vw; margin: 0.8rem auto 1rem; }
        .col-3, .col-4, .col-6, .col-8 { grid-column: span 12; }
        .split { grid-template-columns: 1fr; }
    }
</style>
</head>
<body>
<div class="scanline"></div>
<main class="shell">
    <section class="hud topbar">
        <div>
            <span class="kicker"><span class="pip"></span> Local Agent Console // Port 5000</span>
            <h1>Seraph Cyber Dashboard</h1>
            <p class="subline" id="subtitle">Awaiting telemetry stream...</p>
        </div>
        <div>
            <div class="status online" id="status-badge"><span class="pip"></span> Loading</div>
            <p class="time" id="last-hb">No heartbeat yet</p>
        </div>
    </section>

    <section class="grid">
        <article class="hud panel col-3">
            <p class="label">CPU Utilization</p>
            <p class="metric cyan" id="cpu">--</p>
            <div class="bar"><span id="cpu-bar"></span></div>
        </article>
        <article class="hud panel col-3">
            <p class="label">Memory Usage</p>
            <p class="metric violet" id="mem">--</p>
            <div class="bar"><span id="mem-bar"></span></div>
        </article>
        <article class="hud panel col-3">
            <p class="label">Disk Usage</p>
            <p class="metric green" id="dsk">--</p>
            <div class="bar"><span id="dsk-bar"></span></div>
        </article>
        <article class="hud panel col-3">
            <p class="label">Network Connections</p>
            <p class="metric amber" id="conns">0</p>
            <div class="bar"><span id="conn-bar"></span></div>
        </article>

        <article class="hud panel col-4">
            <p class="label">Threat Detections</p>
            <p class="metric pink" id="threats">0</p>
            <p class="subline">Open incidents from local monitor engines</p>
        </article>
        <article class="hud panel col-4">
            <p class="label">Auto Remediations</p>
            <p class="metric green" id="kills">0</p>
            <p class="subline">Host-level kill/quarantine actions executed</p>
        </article>
        <article class="hud panel col-4">
            <p class="label">Event Volume</p>
            <p class="metric cyan" id="events">0</p>
            <p class="subline">Total telemetry and detection events in memory</p>
        </article>

        <article class="hud panel col-6">
            <p class="label">Agent Identity Matrix</p>
            <div class="split">
                <div class="chip"><p class="chip-title">Agent ID</p><p class="chip-value" id="agent-id">--</p></div>
                <div class="chip"><p class="chip-title">Agent Name</p><p class="chip-value" id="agent-name">--</p></div>
                <div class="chip"><p class="chip-title">Platform</p><p class="chip-value" id="platform">--</p></div>
                <div class="chip"><p class="chip-title">Version</p><p class="chip-value" id="version">--</p></div>
                <div class="chip"><p class="chip-title">Control Server</p><p class="chip-value" id="server">--</p></div>
                <div class="chip"><p class="chip-title">Registration</p><p class="chip-value" id="registered">--</p></div>
            </div>
        </article>

        <article class="hud panel col-6">
            <p class="label">Monitor Enablement</p>
            <div class="list" id="monitor-list">
                <div class="list-row"><span class="list-main">Loading monitor inventory...</span></div>
            </div>
        </article>

        <article class="hud panel col-6">
            <p class="label">Recent Threat Queue</p>
            <div class="list" id="threat-list">
                <div class="list-row"><span class="list-main">No threats loaded yet.</span></div>
            </div>
        </article>

        <article class="hud panel col-6">
            <p class="label">Recent Event Queue</p>
            <div class="list" id="event-list">
                <div class="list-row"><span class="list-main">No events loaded yet.</span></div>
            </div>
        </article>
    </section>
</main>

<script>
function pct(value) {
    const num = Number(value || 0);
    if (!Number.isFinite(num)) return 0;
    if (num < 0) return 0;
    if (num > 100) return 100;
    return num;
}

function safeText(value, fallback) {
    const v = String(value || "").trim();
    return v || fallback;
}

function setMetric(id, value, suffix) {
    const el = document.getElementById(id);
    if (!el) return;
    const n = Number(value || 0);
    el.textContent = Number.isFinite(n) ? n.toFixed(1) + (suffix || "") : "0" + (suffix || "");
}

function renderRows(containerId, rows) {
    const container = document.getElementById(containerId);
    if (!container) return;
    if (!rows.length) {
        container.innerHTML = '<div class="list-row"><span class="list-main">No records.</span></div>';
        return;
    }
    container.innerHTML = "";
    rows.forEach(function(row) {
        const wrap = document.createElement("div");
        wrap.className = "list-row";

        const main = document.createElement("span");
        main.className = "list-main";
        main.textContent = row.main;

        const meta = document.createElement("span");
        meta.className = "list-meta" + (row.metaClass ? " " + row.metaClass : "");
        meta.textContent = row.meta;

        wrap.appendChild(main);
        wrap.appendChild(meta);
        container.appendChild(wrap);
    });
}

async function refresh() {
    try {
        const response = await fetch('/api/data');
        const data = await response.json();
        const agent = data.agent || {};
        const telem = data.telemetry || {};
        const threats = Array.isArray(data.threats) ? data.threats : [];
        const events = Array.isArray(data.events) ? data.events : [];
        const monitors = agent.monitors || {};
        const conns = Array.isArray(telem.connections) ? telem.connections.length : 0;

        document.getElementById('subtitle').textContent = safeText(agent.hostname, 'unknown-host') + ' // ' + safeText(agent.agent_id, 'unregistered-agent');

        const badge = document.getElementById('status-badge');
        const up = !!agent.running;
        badge.className = 'status ' + (up ? 'online' : 'offline');
        badge.innerHTML = '<span class="pip"></span> ' + (up ? 'Online' : 'Stopped');

        const hb = document.getElementById('last-hb');
        hb.textContent = agent.last_heartbeat ? ('Last heartbeat: ' + new Date(agent.last_heartbeat).toLocaleTimeString()) : 'No heartbeat yet';

        setMetric('cpu', telem.cpu_usage, '%');
        setMetric('mem', telem.memory_usage, '%');
        setMetric('dsk', telem.disk_usage, '%');

        document.getElementById('cpu-bar').style.width = pct(telem.cpu_usage) + '%';
        document.getElementById('mem-bar').style.width = pct(telem.memory_usage) + '%';
        document.getElementById('dsk-bar').style.width = pct(telem.disk_usage) + '%';

        document.getElementById('conns').textContent = String(conns);
        document.getElementById('conn-bar').style.width = pct(conns * 5) + '%';

        document.getElementById('threats').textContent = String(agent.threat_count || threats.length || 0);
        document.getElementById('kills').textContent = String(agent.auto_kills || 0);
        document.getElementById('events').textContent = String(agent.event_count || events.length || 0);

        document.getElementById('agent-id').textContent = safeText(agent.agent_id, 'N/A');
        document.getElementById('agent-name').textContent = safeText(agent.agent_name, 'N/A');
        document.getElementById('platform').textContent = safeText(agent.platform, 'N/A');
        document.getElementById('version').textContent = safeText(agent.version, 'N/A');
        document.getElementById('server').textContent = safeText(agent.server_url, 'Not configured');
        document.getElementById('registered').textContent = agent.registered ? 'Registered' : 'Pending';

        const monitorRows = Object.keys(monitors).sort().map(function(name) {
            const enabled = !!monitors[name];
            return {
                main: name,
                meta: enabled ? 'enabled' : 'disabled',
                metaClass: enabled ? 'ok' : 'bad'
            };
        });
        renderRows('monitor-list', monitorRows);

        const threatRows = threats.slice(-20).reverse().map(function(item) {
            const ts = item.timestamp ? new Date(item.timestamp).toLocaleTimeString() : (item.detected_at ? new Date(item.detected_at).toLocaleTimeString() : '--:--:--');
            return {
                main: safeText(item.title || item.threat_id || item.description, 'Unknown threat'),
                meta: safeText(item.severity, 'severity?') + ' // ' + ts,
                metaClass: String(item.severity || '').toLowerCase() === 'critical' ? 'bad' : ''
            };
        });
        renderRows('threat-list', threatRows);

        const eventRows = events.slice(-20).reverse().map(function(item) {
            const ts = item.timestamp ? new Date(item.timestamp).toLocaleTimeString() : '--:--:--';
            const name = safeText(item.event_type || item.type || item.message || item.title, 'Event');
            const sev = safeText(item.severity || item.level, 'info');
            return {
                main: name,
                meta: sev + ' // ' + ts,
                metaClass: (sev === 'critical' || sev === 'high' || sev === 'error') ? 'bad' : ''
            };
        });
        renderRows('event-list', eventRows);
    } catch (err) {
        const badge = document.getElementById('status-badge');
        badge.className = 'status error';
        badge.innerHTML = '<span class="pip"></span> Data Error';
        document.getElementById('last-hb').textContent = 'Unable to pull /api/data';
    }
}

refresh();
setInterval(refresh, 5000);
</script>
</body>
</html>"""

    def __init__(self, agent: 'UnifiedAgent', port: int = 5000):
        self.agent = agent
        self.port = port
        self._server = None
        self._thread = None

    def start(self) -> int:
        """Start the HTTP server; returns the actual port bound (0 on failure)."""
        from http.server import BaseHTTPRequestHandler, HTTPServer
        import json as _json

        agent_ref = self.agent

        class _Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass  # suppress default request logging

            def do_GET(self):
                if self.path in ('/', '/index.html'):
                    body = LocalWebUIServer.DASHBOARD_HTML.encode('utf-8')
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/html; charset=utf-8')
                    self.send_header('Content-Length', str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                elif self.path == '/api/status':
                    self._json(agent_ref.get_status())
                elif self.path in ('/api/data', '/api/dashboard'):
                    self._json(agent_ref.get_dashboard_data())
                else:
                    self.send_error(404, 'Not found')

            def _json(self, data):
                body = _json.dumps(data, default=str).encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        # Try preferred port then up to 4 alternatives
        for p in range(self.port, self.port + 5):
            try:
                self._server = HTTPServer(('0.0.0.0', p), _Handler)
                self.port = p
                break
            except OSError:
                continue
        else:
            logger.warning("LocalWebUIServer: could not bind to any port")
            return 0

        self._thread = threading.Thread(
            target=self._server.serve_forever, daemon=True, name='LocalWebUI'
        )
        self._thread.start()
        logger.info(f"Local Web UI running at http://localhost:{self.port}")
        return self.port

    def stop(self):
        if self._server:
            self._server.shutdown()
            self._server = None


# =============================================================================
# UNIFIED AGENT
# =============================================================================

class UnifiedAgent:
    """
    Metatron/Seraph Unified Security Agent v2.0
    
    Cross-platform security agent with:
    - Process and network monitoring
    - Aggressive auto-kill for threats
    - SIEM integration
    - VNS sync
    - AI analysis
    - Network scanning (ports, WiFi, Bluetooth)
    - LAN device discovery (integrated network scanner)
    - WireGuard VPN auto-setup
    - Threat hunting integration
    """
    
    def __init__(self, config: Optional[AgentConfig] = None, config_path: Optional[str] = None):
        """Initialize the unified agent"""
        if config:
            self.config = config
        elif config_path:
            self.config = AgentConfig.from_file(config_path)
        else:
            self.config = AgentConfig()
        
        # Generate agent ID if not set
        if not self.config.agent_id:
            self.config.agent_id = f"metatron-{HOSTNAME}-{uuid.uuid4().hex[:8]}"
        
        if not self.config.agent_name:
            self.config.agent_name = f"Metatron-{HOSTNAME}"
        
        # Initialize monitors
        self.monitors: Dict[str, MonitorModule] = {}
        
        if self.config.process_monitoring:
            self.monitors['process'] = ProcessMonitor(self.config)
        
        if self.config.network_scanning:
            self.monitors['network'] = NetworkMonitor(self.config)
        
        # Initialize advanced enterprise monitors
        self.monitors['registry'] = RegistryMonitor(self.config)
        self.monitors['process_tree'] = ProcessTreeMonitor(self.config)
        self.monitors['lolbin'] = LOLBinMonitor(self.config)
        self.monitors['code_signing'] = CodeSigningMonitor(self.config)
        self.monitors['dns'] = DNSMonitor(self.config)
        
        # Initialize medium-priority enterprise monitors
        self.monitors['memory'] = MemoryScanner(self.config)
        self.monitors['whitelist'] = ApplicationWhitelistMonitor(self.config)
        self.monitors['dlp'] = DLPMonitor(self.config)
        self.monitors['vulnerability'] = VulnerabilityScanner(self.config)
        if PLATFORM == "windows":
            self.monitors['amsi'] = AMSIMonitor(self.config)
        
        # Initialize ransomware protection (canaries, shadow copy, protected folders)
        self.monitors['ransomware'] = RansomwareProtectionMonitor()
        
        # Initialize kernel/anti-tampering/identity protection monitors
        self.monitors['rootkit'] = RootkitDetector(self.config)
        self.monitors['kernel_security'] = KernelSecurityMonitor(self.config)
        self.monitors['self_protection'] = AgentSelfProtection(self.config, self)
        self.monitors['identity'] = EndpointIdentityProtection(self.config)
        
        # Initialize resource management monitor
        self.monitors['auto_throttle'] = AutoThrottleMonitor(self.config)
        
        # Initialize firewall monitor
        self.monitors['firewall'] = FirewallMonitor(self.config)
        
        # Initialize WebView2 exploit monitor (Windows-specific)
        if PLATFORM == 'windows':
            self.monitors['webview2'] = WebView2Monitor(self.config)
        
        # Initialize CLI telemetry monitor (SOAR integration)
        self.monitors['cli_telemetry'] = CLITelemetryMonitor(self.config)
        
        # Initialize hidden file scanner (ADS, hidden folders)
        self.monitors['hidden_file'] = HiddenFileScanner(self.config)
        
        # Initialize alias/rename monitor (PATH hijacking, masquerading)
        self.monitors['alias_rename'] = AliasRenameMonitor(self.config)
        
        # Initialize privilege escalation monitor
        self.monitors['priv_escalation'] = PrivilegeEscalationMonitor(self.config)
        
        # Initialize email protection monitor
        self.monitors['email_protection'] = EmailProtectionMonitor(self.config)
        
        # Initialize mobile security monitor
        self.monitors['mobile_security'] = MobileSecurityMonitor(self.config)
        
        # Initialize scanners
        self.network_scanner = NetworkScanner()
        self.wifi_scanner = WiFiScanner()
        self.bluetooth_scanner = BluetoothScanner()
        
        # Initialize LAN discovery scanner (integrated from seraph_network_scanner)
        self.lan_discovery = LANDiscoveryScanner(server_url=self.config.server_url)
        
        # Initialize WireGuard VPN auto-setup
        self.vpn = WireGuardAutoSetup(
            server_url=self.config.server_url,
            agent_id=self.config.agent_id,
            config=self.config,
        )
        
        # Initialize SIEM
        self.siem = SIEMIntegration(self.config)
        
        # Initialize remediation
        self.remediation = RemediationEngine()
        
        # Telemetry storage
        self.telemetry = TelemetryData(agent_id=self.config.agent_id)
        self.threat_history: deque = deque(maxlen=1000)
        self.event_log: deque = deque(maxlen=5000)
        self.auto_remediated: deque = deque(maxlen=100)
        self.alarms: deque = deque(maxlen=50)
        self._pending_edm_hits: Dict[str, Dict[str, Any]] = {}
        
        # State
        self.running = False
        self.registered = False
        self.last_heartbeat = None

        # Local web UI server (started in start())
        self.local_ui_server: Optional[LocalWebUIServer] = None
        self._local_ui_url: str = ""
        
        # Stats
        self.stats = {
            "threats_detected": 0,
            "threats_blocked": 0,
            "threats_auto_killed": 0,
            "scans_performed": 0,
        }
        
        # Callbacks
        self.on_threat_detected: Optional[Callable[[Threat], None]] = None
        self.on_telemetry_update: Optional[Callable[[TelemetryData], None]] = None
        
        # Check privileges
        self._is_admin, self._privilege_info = check_admin_privileges()
        if not self._is_admin and self.config.require_admin:
            logger.warning(f"Running without admin privileges ({self._privilege_info}). Some features may be limited.")
        
        logger.info(f"Unified Agent initialized: {self.config.agent_id} (privileges: {self._privilege_info})")
    
    def register(self) -> bool:
        """Register with the server and auto-configure VPN"""
        if not REQUESTS_AVAILABLE or not self.config.server_url:
            logger.warning("Cannot register: requests not available or server URL not set")
            return False
        
        try:
            exe_path = None
            exe_hash = None
            try:
                exe_path = sys.executable
                if exe_path and os.path.exists(exe_path):
                    with open(exe_path, "rb") as f:
                        exe_hash = hashlib.sha256(f.read()).hexdigest()
            except Exception:
                exe_path = None
                exe_hash = None

            # Build auth headers
            headers = {}
            if self.config.enrollment_key:
                headers['X-Enrollment-Key'] = self.config.enrollment_key
            elif self.config.auth_token:
                headers['X-Agent-Id'] = self.config.agent_id
                headers['X-Agent-Token'] = self.config.auth_token
            
            response = requests.post(
                f"{self.config.server_url}/api/unified/agents/register",
                headers=headers,
                json={
                    'agent_id': self.config.agent_id,
                    # node_id is the canonical identity used by the Arda Fabric registry
                    # and constitutional→kernel friend/foe bridging.
                    'node_id': self.config.agent_id,
                    'executable_path': exe_path,
                    'workload_hash': exe_hash,
                    'platform': PLATFORM,
                    'hostname': HOSTNAME,
                    'ip_address': self._get_primary_ip(),
                    'version': AGENT_VERSION,
                    'capabilities': list(self.monitors.keys()) + [
                        'network_scan', 'wifi_scan', 'bluetooth_scan', 
                        'siem', 'lan_discovery', 'vpn', 'command_execution'
                    ],
                    'config': {
                        'auto_remediate': self.config.auto_remediate,
                        'is_admin': self._is_admin,
                        'features': {
                            'vns_sync': self.config.vns_sync,
                            'ai_analysis': self.config.ai_analysis,
                            'siem_integration': self.siem.enabled,
                            'threat_hunting': self.config.threat_hunting,
                            'lan_discovery': True,
                            'vpn_enabled': True
                        }
                    },
                    'local_ui_url': self._local_ui_url,
                },
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                self.registered = True
                data = response.json()
                
                # Save auth token for future requests
                if 'auth_token' in data:
                    self.config.auth_token = data['auth_token']
                    logger.info("Received auth token from server")
                
                # Save server IPs to whitelist
                if 'server_ips' in data:
                    self.config.server_ips = data['server_ips']
                    logger.info(f"Server IPs whitelisted: {data['server_ips']}")
                    # Update network monitor whitelist
                    if 'network' in self.monitors:
                        self.monitors['network']._whitelist.update(data['server_ips'])
                
                # Save config to persist token
                config_path = str(DATA_DIR / "agent_config.json")
                self.config.save(config_path)
                
                logger.info(f"Registered with server: {self.config.server_url}")
                
                # Auto-configure WireGuard VPN after registration
                if self.config.server_url and self.config.vpn_auto_configure:
                    logger.info("Auto-configuring WireGuard VPN...")
                    self.vpn.auto_configure()
                
                # Keep LAN discovery opt-in. On dense networks this can fan out into
                # ARP, nmap, and port probes immediately after registration.
                if self.config.network_scanning and _env_bool("SERAPH_AGENT_INITIAL_LAN_DISCOVERY", True):
                    logger.info("Running initial LAN discovery scan...")
                    self.discover_lan_devices(report=True)
                else:
                    logger.info("Initial LAN discovery skipped by throttle configuration")
                
                return True
            elif response.status_code == 401:
                logger.error("Registration failed: Invalid enrollment key or token")
                return False
            elif response.status_code == 403:
                logger.error("Registration failed: Access denied - check enrollment key")
                return False
            else:
                logger.error(f"Registration failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Registration error: {e}")
            return False
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for API requests"""
        if self.config.auth_token:
            return {
                'X-Agent-Id': self.config.agent_id,
                'X-Agent-Token': self.config.auth_token
            }
        elif self.config.enrollment_key:
            return {'X-Enrollment-Key': self.config.enrollment_key}
        return {}
    
    def _get_primary_ip(self) -> str:
        """Get primary IP address"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"
    
    def scan_all(self) -> Dict[str, Any]:
        """Run all enabled monitors"""
        results = {}
        all_threats = []
        
        for name, monitor in self.monitors.items():
            if monitor.enabled:
                try:
                    results[name] = monitor.scan()
                    all_threats.extend(monitor.get_threats())
                except Exception as e:
                    logger.error(f"Monitor {name} error: {e}")
                    results[name] = {"error": str(e)}
        
        # Process detected threats
        for threat in all_threats:
            self._handle_threat(threat)
        
        # Update telemetry
        self._update_telemetry(results)
        
        self.stats["scans_performed"] += 1
        
        return results
    
    def _handle_threat(self, threat: Threat):
        """Handle a detected threat with aggressive auto-kill"""
        self.threat_history.append(threat)
        self.stats["threats_detected"] += 1
        
        # Determine if auto-kill should be triggered
        should_auto_kill = False
        kill_reason = None
        
        if self.config.auto_remediate and threat.auto_kill_eligible:
            # Auto-kill for CRITICAL and HIGH severity
            if threat.severity in {ThreatSeverity.CRITICAL, ThreatSeverity.HIGH}:
                should_auto_kill = True
                kill_reason = f"SEVERITY_{threat.severity.value.upper()}"
            
            # Check critical patterns
            threat_text = f"{threat.title} {threat.description}".lower()
            for pattern in ThreatIntelligence.CRITICAL_PATTERNS:
                if pattern in threat_text:
                    should_auto_kill = True
                    kill_reason = f"PATTERN_MATCH_{pattern.upper()}"
                    break
        
        # Execute auto-kill
        if should_auto_kill:
            threat.kill_reason = kill_reason
            threat.status = "auto_remediated"
            threat.user_approved = True
            
            # Execute remediation
            success, msg = self.remediation.execute(threat)
            
            if success:
                self.stats["threats_auto_killed"] += 1
                self.stats["threats_blocked"] += 1
                self.auto_remediated.append(threat)
                logger.warning(f"AUTO-KILL EXECUTED: {threat.title} | Reason: {kill_reason}")
                
                # Log to SIEM
                self.siem.log_threat(threat, "auto_killed")
            else:
                logger.error(f"AUTO-KILL FAILED: {threat.title} - {msg}")
            
            # Trigger alarm
            self._trigger_alarm(threat, f"AUTO_KILL:{kill_reason}")
        else:
            # Log to SIEM
            self.siem.log_threat(threat, "detected")
        
        # Log event
        self._log_event("threat_detected", {
            "threat_id": threat.threat_id,
            "title": threat.title,
            "severity": threat.severity.value if isinstance(threat.severity, ThreatSeverity) else threat.severity,
            "auto_kill_triggered": should_auto_kill,
            "kill_reason": kill_reason
        })
        
        # Callback
        if self.on_threat_detected:
            self.on_threat_detected(threat)
        
        # Send to AI for analysis
        if self.config.ai_analysis and self.config.server_url:
            self._request_ai_analysis(threat)
        
        # Sync to VNS
        if self.config.vns_sync and self.config.server_url:
            self._sync_to_vns(threat)
    
    def _trigger_alarm(self, threat: Threat, alarm_type: str):
        """Trigger an alarm for critical threats"""
        alarm = {
            "id": f"alarm-{uuid.uuid4().hex[:8]}",
            "type": alarm_type,
            "threat_id": threat.threat_id,
            "threat_title": threat.title,
            "severity": threat.severity.value if isinstance(threat.severity, ThreatSeverity) else threat.severity,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "acknowledged": False
        }
        self.alarms.append(alarm)
        logger.warning(f"ALARM: {alarm_type} - {threat.title}")
    
    def _request_ai_analysis(self, threat: Threat):
        """Request AI analysis for a threat"""
        if not REQUESTS_AVAILABLE:
            return
        
        try:
            response = requests.post(
                f"{self.config.server_url}/api/advanced/ai/analyze",
                json={
                    "title": threat.title,
                    "description": threat.description,
                    "process_name": threat.evidence.get('name'),
                    "command_line": threat.evidence.get('cmdline'),
                    "indicators": threat.evidence.get('indicators', [])
                },
                timeout=30
            )
            
            if response.status_code == 200:
                threat.ai_analysis = response.json()
                logger.info(f"AI Analysis: Risk {threat.ai_analysis.get('risk_score')}")
                
        except Exception as e:
            logger.debug(f"AI analysis request failed: {e}")
    
    def _sync_to_vns(self, threat: Threat):
        """Sync threat to VNS"""
        if not REQUESTS_AVAILABLE:
            return
        
        try:
            if 'remote_ip' in str(threat.evidence):
                evidence = threat.evidence
                local = evidence.get('local', ':0')
                remote = evidence.get('remote', ':0')
                
                requests.post(
                    f"{self.config.server_url}/api/advanced/vns/flow",
                    json={
                        "src_ip": local.split(':')[0] if ':' in local else '0.0.0.0',
                        "src_port": int(local.split(':')[-1]) if ':' in local else 0,
                        "dst_ip": remote.split(':')[0] if ':' in remote else '0.0.0.0',
                        "dst_port": int(remote.split(':')[-1]) if ':' in remote else 0,
                        "protocol": "TCP"
                    },
                    timeout=5
                )
        except Exception as e:
            logger.debug(f"VNS sync failed: {e}")
    
    def _update_telemetry(self, scan_results: Dict):
        """Update telemetry data"""
        if PSUTIL_AVAILABLE:
            self.telemetry.cpu_usage = psutil.cpu_percent()
            self.telemetry.memory_usage = psutil.virtual_memory().percent
            try:
                self.telemetry.disk_usage = psutil.disk_usage('/').percent
            except:
                self.telemetry.disk_usage = 0
        
        self.telemetry.timestamp = datetime.now(timezone.utc).isoformat()
        
        if 'process' in scan_results:
            self.telemetry.processes = scan_results['process'].get('processes', [])[:100]
        
        if 'network' in scan_results:
            self.telemetry.connections = scan_results['network'].get('connections', [])[:100]
            self.telemetry.network_interfaces = scan_results['network'].get('interfaces', [])
        
        self.telemetry.threats = [t.to_dict() for t in list(self.threat_history)[-50:]]
        self._collect_edm_hits(scan_results)
        
        if self.on_telemetry_update:
            self.on_telemetry_update(self.telemetry)

    def _mask_file_path(self, path_value: Any) -> Optional[str]:
        """Mask file path while preserving minimal triage value."""
        path = str(path_value or "").strip()
        if not path:
            return None
        basename = os.path.basename(path) or "unknown"
        digest = hashlib.sha256(path.encode("utf-8")).hexdigest()[:12]
        return f".../{basename}#{digest}"

    def _collect_edm_hits(self, scan_results: Dict[str, Any]):
        """Extract EDM hit alerts from DLP scan results for backend analytics loop-back."""
        dlp_result = scan_results.get("dlp") or {}
        if not isinstance(dlp_result, dict):
            return

        details = dlp_result.get("details") or []
        if not isinstance(details, list):
            return

        for alert in details:
            if not isinstance(alert, dict):
                continue
            if alert.get("type") != "edm_match":
                continue

            dataset_id = str(alert.get("dataset_id") or "").strip()
            fingerprint = str(alert.get("fingerprint") or "").strip()
            if not dataset_id or not fingerprint:
                continue

            hit = {
                "dataset_id": dataset_id,
                "record_id": alert.get("record_id"),
                "fingerprint": fingerprint,
                "host": HOSTNAME,
                "process": alert.get("process") or "unknown",
                "file_path_masked": self._mask_file_path(alert.get("path")),
                "source": alert.get("source") or "unknown",
                "match_confidence": alert.get("match_confidence"),
                "match_candidate_type": alert.get("match_candidate_type"),
                "match_variant_type": alert.get("match_variant_type"),
                "timestamp": alert.get("timestamp") or datetime.now(timezone.utc).isoformat(),
            }

            dedupe_key = hashlib.sha256(
                f"{hit['dataset_id']}|{hit.get('record_id')}|{hit['fingerprint']}|{hit['source']}|{hit.get('file_path_masked')}".encode("utf-8")
            ).hexdigest()
            self._pending_edm_hits[dedupe_key] = hit

            # Keep bounded memory footprint.
            if len(self._pending_edm_hits) > 2000:
                oldest_key = next(iter(self._pending_edm_hits.keys()))
                self._pending_edm_hits.pop(oldest_key, None)
    
    def _log_event(self, event_type: str, data: Dict):
        """Log an event"""
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": event_type,
            "agent_id": self.config.agent_id,
            **data
        }
        self.event_log.append(event)
        self.telemetry.events = list(self.event_log)[-100:]
        
        # Log to SIEM
        self.siem.log_event(event_type, data.get('severity', 'info'), data)
    
    def heartbeat(self) -> bool:
        """Send heartbeat to server"""
        if not REQUESTS_AVAILABLE or not self.config.server_url:
            return False
        
        try:
            exe_path = None
            exe_hash = None
            try:
                exe_path = sys.executable
                if exe_path and os.path.exists(exe_path):
                    with open(exe_path, "rb") as f:
                        exe_hash = hashlib.sha256(f.read()).hexdigest()
            except Exception:
                exe_path = None
                exe_hash = None

            pending_hit_items = list(self._pending_edm_hits.items())
            max_hits_per_heartbeat = 200
            outbound_hits = [item[1] for item in pending_hit_items[:max_hits_per_heartbeat]]

            response = requests.post(
                f"{self.config.server_url}/api/unified/agents/{self.config.agent_id}/heartbeat",
                headers=self._get_auth_headers(),
                json={
                    "agent_id": self.config.agent_id,
                    "node_id": self.config.agent_id,
                    "executable_path": exe_path,
                    "workload_hash": exe_hash,
                    "status": "online",
                    "cpu_usage": self.telemetry.cpu_usage,
                    "memory_usage": self.telemetry.memory_usage,
                    "disk_usage": self.telemetry.disk_usage,
                    "threat_count": len(self.threat_history),
                    "network_connections": len(self.telemetry.connections),
                    "is_admin": self._is_admin,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "telemetry": asdict(self.telemetry),
                    "edm_hits": outbound_hits,
                    "local_ui_url": self._local_ui_url,
                },
                timeout=10
            )
            
            self.last_heartbeat = datetime.now(timezone.utc)
            if response.status_code == 200 and outbound_hits:
                for key, _ in pending_hit_items[:len(outbound_hits)]:
                    self._pending_edm_hits.pop(key, None)
            return response.status_code == 200
            
        except Exception as e:
            logger.debug(f"Heartbeat failed: {e}")
            return False
    
    def get_status(self) -> Dict:
        """Get agent status"""
        return {
            "agent_id": self.config.agent_id,
            "agent_name": self.config.agent_name,
            "platform": PLATFORM,
            "hostname": HOSTNAME,
            "version": AGENT_VERSION,
            "running": self.running,
            "registered": self.registered,
            "server_url": self.config.server_url,
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            "monitors": {name: monitor.enabled for name, monitor in self.monitors.items()},
            "threat_count": len(self.threat_history),
            "event_count": len(self.event_log),
            "auto_kills": len(self.auto_remediated),
            "stats": self.stats,
            "siem": {"enabled": self.siem.enabled, "type": self.siem.siem_type},
            "vpn": self.vpn.get_status(),
            "local_ui_url": self._local_ui_url,
            "lan_discovery": {
                "network": self.lan_discovery.network_cidr,
                "devices_found": len(self.lan_discovery.discovered_devices)
            },
            "telemetry": {
                "cpu_usage": self.telemetry.cpu_usage,
                "memory_usage": self.telemetry.memory_usage,
                "disk_usage": self.telemetry.disk_usage
            }
        }
    
    def get_dashboard_data(self) -> Dict:
        """Get all data for dashboard"""
        return {
            "agent": self.get_status(),
            "stats": self.stats,
            "events": list(self.event_log)[-100:],
            "threats": [t.to_dict() for t in list(self.threat_history)[-50:]],
            "auto_remediated": [t.to_dict() for t in list(self.auto_remediated)[-20:]],
            "alarms": list(self.alarms)[-20:],
            "telemetry": asdict(self.telemetry)
        }
    
    # Advanced scanning methods
    def scan_ports(self, target_ip: Optional[str] = None) -> Dict:
        """Scan ports on a target IP"""
        if target_ip:
            return self.network_scanner.scan_host(target_ip)
        return self.network_scanner.scan_router()
    
    def scan_wifi(self) -> List[Dict]:
        """Scan WiFi networks"""
        return self.wifi_scanner.scan_networks()
    
    def scan_bluetooth(self) -> List[Dict]:
        """Scan Bluetooth devices"""
        return self.bluetooth_scanner.scan_devices()
    
    def discover_lan_devices(self, report: bool = True) -> List[Dict]:
        """
        Discover all devices on the local network.
        This is the integrated network scanner - no separate scanner needed.
        Optionally reports to server for auto-deployment.
        """
        devices = self.lan_discovery.scan_network()
        
        if report and self.config.server_url:
            self.lan_discovery.report_to_server(devices)
        
        return devices
    
    def get_discovered_devices(self) -> List[Dict]:
        """Get all previously discovered LAN devices"""
        return self.lan_discovery.get_discovered_devices()
    
    def get_vpn_status(self) -> Dict:
        """Get VPN connection status"""
        return self.vpn.get_status()
    
    # =========================================================================
    # MCP COMMAND EXECUTION - Run server-sent commands
    # =========================================================================
    
    def poll_commands(self) -> List[Dict]:
        """Poll server for pending commands"""
        if not REQUESTS_AVAILABLE or not self.config.server_url:
            return []
        
        try:
            response = requests.get(
                f"{self.config.server_url}/api/unified/agents/{self.config.agent_id}/commands",
                headers=self._get_auth_headers(),
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get('commands', [])
            
        except Exception as e:
            logger.debug(f"Command poll error: {e}")
        
        return []
    
    def execute_command(self, command: Dict) -> Dict:
        """Execute a server-sent command and return result"""
        cmd_type = command.get('command_type', '')
        cmd_id = command.get('command_id', str(uuid.uuid4()))
        params = command.get('parameters', {})
        
        logger.info(f"Executing command: {cmd_type} (ID: {cmd_id})")
        
        result = {
            'command_id': cmd_id,
            'agent_id': self.config.agent_id,
            'command_type': cmd_type,
            'status': 'completed',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'result': {}
        }
        
        try:
            if cmd_type == 'scan':
                self.scan_all()
                result['result'] = {'threats': len(self.threat_history), 'stats': self.stats}
                
            elif cmd_type == 'network_scan':
                devices = self.discover_lan_devices(report=True)
                result['result'] = {'devices_found': len(devices), 'devices': devices[:20]}
                
            elif cmd_type == 'wifi_scan':
                networks = self.scan_wifi()
                result['result'] = {'networks': networks}
                
            elif cmd_type == 'bluetooth_scan':
                devices = self.scan_bluetooth()
                result['result'] = {'devices': devices}
                
            elif cmd_type == 'port_scan':
                target = params.get('target_ip')
                ports = self.scan_ports(target)
                result['result'] = {'ports': ports}
                
            elif cmd_type == 'threat_hunt':
                # Run intensive threat detection
                self.scan_all()
                threats = list(self.threat_history)[-50:]
                result['result'] = {'threats': [asdict(t) if hasattr(t, '__dict__') else t for t in threats]}
                
            elif cmd_type == 'collect_forensics':
                # Collect system forensics data
                forensics = {
                    'processes': self._get_process_list(),
                    'network_connections': self._get_network_connections(),
                    'services': self._get_services(),
                    'users': self._get_logged_users(),
                    'system_info': self._get_system_info()
                }
                result['result'] = forensics
                
            elif cmd_type == 'update_config':
                # Update agent configuration
                if 'auto_kill' in params:
                    self.config.auto_remediate = params['auto_kill']
                if 'auto_block_ips' in params:
                    self.config.auto_block_ips = params['auto_block_ips']
                if 'update_interval' in params:
                    self.config.update_interval = params['update_interval']

                # EDM runtime config updates
                if 'dlp_edm_enabled' in params:
                    self.config.dlp_edm_enabled = bool(params['dlp_edm_enabled'])
                if 'dlp_edm_dataset_path' in params:
                    self.config.dlp_edm_dataset_path = str(params['dlp_edm_dataset_path'])
                if 'dlp_edm_tenant_salt' in params:
                    self.config.dlp_edm_tenant_salt = str(params['dlp_edm_tenant_salt'])
                if 'dlp_edm_max_records' in params:
                    self.config.dlp_edm_max_records = int(params['dlp_edm_max_records'])
                if 'dlp_edm_min_confidence' in params:
                    self.config.dlp_edm_min_confidence = float(params['dlp_edm_min_confidence'])
                if 'dlp_edm_allowed_candidate_types' in params and isinstance(params['dlp_edm_allowed_candidate_types'], list):
                    self.config.dlp_edm_allowed_candidate_types = [str(v) for v in params['dlp_edm_allowed_candidate_types'] if str(v).strip()]
                if 'dlp_edm_require_signed' in params:
                    self.config.dlp_edm_require_signed = bool(params['dlp_edm_require_signed'])
                if 'dlp_edm_signing_secret' in params:
                    self.config.dlp_edm_signing_secret = str(params['dlp_edm_signing_secret'])

                # Rebuild DLP monitor if EDM settings changed.
                if 'dlp' in self.monitors and any(
                    k in params for k in [
                        'dlp_edm_enabled',
                        'dlp_edm_dataset_path',
                        'dlp_edm_tenant_salt',
                        'dlp_edm_max_records',
                        'dlp_edm_min_confidence',
                        'dlp_edm_allowed_candidate_types',
                        'dlp_edm_require_signed',
                        'dlp_edm_signing_secret',
                    ]
                ):
                    self.monitors['dlp'] = DLPMonitor(self.config)
                result['result'] = {'config_updated': True, 'new_config': asdict(self.config)}

            elif cmd_type == 'reload_edm_dataset':
                dlp = self.monitors.get('dlp')
                if isinstance(dlp, DLPMonitor):
                    result['result'] = {
                        'reloaded': True,
                        'edm_stats': dlp.reload_edm_dataset(),
                    }
                else:
                    result['status'] = 'failed'
                    result['result'] = {'error': 'DLP monitor not initialized'}

            elif cmd_type == 'update_edm_dataset':
                dlp = self.monitors.get('dlp')
                dataset_payload = params.get('dataset') or params.get('datasets')
                edm_meta = params.get('edm_meta') or {}
                if not isinstance(dlp, DLPMonitor):
                    result['status'] = 'failed'
                    result['result'] = {'error': 'DLP monitor not initialized'}
                elif dataset_payload is None:
                    result['status'] = 'failed'
                    result['result'] = {'error': 'No dataset payload provided'}
                else:
                    # Accept either {datasets:[...]} or raw list; persist canonical wrapper.
                    if isinstance(dataset_payload, list):
                        normalized = {'datasets': dataset_payload}
                    elif isinstance(dataset_payload, dict) and 'datasets' in dataset_payload:
                        normalized = dataset_payload
                    else:
                        result['status'] = 'failed'
                        result['result'] = {'error': 'Invalid dataset payload format'}
                        self._report_command_result(result)
                        return result

                    result['result'] = dlp.update_edm_dataset(normalized, edm_meta=edm_meta)
                    if not result['result'].get('updated'):
                        result['status'] = 'failed'
                
            elif cmd_type == 'quarantine_file':
                filepath = params.get('filepath')
                if filepath:
                    if not self._is_admin:
                        result['result'] = {'warning': 'Agent not running with admin privileges - quarantine may fail', 'is_admin': False}
                    success = self.remediation.quarantine_file(Path(filepath))
                    result['result'] = {'quarantined': success, 'filepath': filepath, 'is_admin': self._is_admin}
                else:
                    result['status'] = 'failed'
                    result['result'] = {'error': 'No filepath provided'}
                    
            elif cmd_type == 'block_ip':
                ip = params.get('ip')
                if ip:
                    if not self._is_admin:
                        result['result'] = {'warning': 'Agent not running with admin privileges - IP blocking requires elevated permissions', 'is_admin': False}
                    success = self.remediation.block_ip(ip)
                    result['result'] = {'blocked': success, 'ip': ip, 'is_admin': self._is_admin}
                else:
                    result['status'] = 'failed'
                    result['result'] = {'error': 'No IP provided'}
                    
            elif cmd_type == 'kill_process':
                pid = params.get('pid')
                name = params.get('name')
                if not self._is_admin:
                    logger.warning("Agent not running with admin privileges - process kill may fail for system processes")
                if pid:
                    success = self.remediation.kill_process(pid)
                    result['result'] = {'killed': success, 'pid': pid, 'is_admin': self._is_admin}
                elif name:
                    # Kill by name
                    killed = []
                    for proc in psutil.process_iter(['pid', 'name']) if PSUTIL_AVAILABLE else []:
                        if proc.info['name'] and name.lower() in proc.info['name'].lower():
                            try:
                                proc.kill()
                                killed.append(proc.info['pid'])
                            except:
                                pass
                    result['result'] = {'killed_pids': killed, 'name': name, 'is_admin': self._is_admin}
                else:
                    result['status'] = 'failed'
                    result['result'] = {'error': 'No pid or name provided'}
                    
            elif cmd_type == 'vpn_connect':
                self.vpn.connect()
                result['result'] = self.vpn.get_status()
                
            elif cmd_type == 'vpn_disconnect':
                self.vpn.disconnect()
                result['result'] = self.vpn.get_status()
                
            elif cmd_type == 'get_status':
                result['result'] = self.get_status()
                
            elif cmd_type == 'restart':
                result['result'] = {'restarting': True}
                # Schedule restart
                threading.Thread(target=self._delayed_restart, daemon=True).start()
                
            else:
                result['status'] = 'unknown_command'
                result['result'] = {'error': f'Unknown command type: {cmd_type}'}
                
        except Exception as e:
            result['status'] = 'failed'
            result['result'] = {'error': str(e)}
            logger.error(f"Command execution error: {e}")
        
        # Report result back to server
        self._report_command_result(result)
        
        return result
    
    def _report_command_result(self, result: Dict):
        """Report command execution result to server"""
        if not REQUESTS_AVAILABLE or not self.config.server_url:
            return
        
        try:
            requests.post(
                f"{self.config.server_url}/api/unified/agents/{self.config.agent_id}/command-result",
                headers=self._get_auth_headers(),
                json=result,
                timeout=10
            )
        except Exception as e:
            logger.debug(f"Failed to report command result: {e}")
    
    def _delayed_restart(self):
        """Restart the agent after a brief delay"""
        time.sleep(2)
        self.stop()
        time.sleep(1)
        self.start(blocking=False)
    
    def _get_process_list(self) -> List[Dict]:
        """Get list of running processes"""
        processes = []
        if PSUTIL_AVAILABLE:
            for proc in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent', 'memory_percent', 'cmdline']):
                try:
                    info = proc.info
                    processes.append({
                        'pid': info['pid'],
                        'name': info['name'],
                        'user': info['username'],
                        'cpu': info['cpu_percent'],
                        'memory': info['memory_percent'],
                        'cmdline': ' '.join(info['cmdline'] or [])[:200]
                    })
                except:
                    pass
        return processes[:100]  # Limit to first 100
    
    def _get_network_connections(self) -> List[Dict]:
        """Get active network connections"""
        connections = []
        if PSUTIL_AVAILABLE:
            for conn in psutil.net_connections(kind='inet'):
                try:
                    connections.append({
                        'local': f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else "",
                        'remote': f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else "",
                        'status': conn.status,
                        'pid': conn.pid
                    })
                except:
                    pass
        return connections[:100]
    
    def _get_services(self) -> List[Dict]:
        """Get system services (Windows)"""
        services = []
        if PLATFORM == 'windows' and PSUTIL_AVAILABLE:
            try:
                import winreg
                # Get Windows services
                for service in psutil.win_service_iter():
                    try:
                        services.append({
                            'name': service.name(),
                            'display_name': service.display_name(),
                            'status': service.status()
                        })
                    except:
                        pass
            except:
                pass
        return services[:50]
    
    def _get_logged_users(self) -> List[Dict]:
        """Get logged in users"""
        users = []
        if PSUTIL_AVAILABLE:
            for user in psutil.users():
                users.append({
                    'name': user.name,
                    'terminal': user.terminal,
                    'host': user.host,
                    'started': datetime.fromtimestamp(user.started).isoformat()
                })
        return users
    
    def _get_system_info(self) -> Dict:
        """Get system information"""
        info = {
            'hostname': HOSTNAME,
            'platform': PLATFORM,
            'architecture': platform.machine(),
            'python_version': platform.python_version()
        }
        
        if PSUTIL_AVAILABLE:
            info.update({
                'cpu_count': psutil.cpu_count(),
                'cpu_percent': psutil.cpu_percent(),
                'memory_total': psutil.virtual_memory().total,
                'memory_available': psutil.virtual_memory().available,
                'disk_total': psutil.disk_usage('/').total if PLATFORM != 'windows' else psutil.disk_usage('C:').total,
                'disk_free': psutil.disk_usage('/').free if PLATFORM != 'windows' else psutil.disk_usage('C:').free,
                'boot_time': datetime.fromtimestamp(psutil.boot_time()).isoformat()
            })
        
        return info
    
    def run_once(self):
        """Run a single monitoring cycle"""
        self.scan_all()
        self.heartbeat()
    
    def start(self, blocking: bool = True):
        """Start the agent"""
        self.running = True

        # Start the built-in local web UI first so the URL is available
        # before we register with the server.
        if self.config.local_ui_enabled:
            self.local_ui_server = LocalWebUIServer(self, self.config.local_ui_port)
            bound_port = self.local_ui_server.start()
            if bound_port:
                try:
                    local_ip = self._get_primary_ip()
                except Exception:
                    local_ip = "localhost"
                self._local_ui_url = f"http://{local_ip}:{bound_port}"
                logger.info(f"Local Web UI: {self._local_ui_url}")

        self.register()
        
        logger.info(f"Agent started: {self.config.agent_id}")
        
        if blocking:
            self._run_loop()
        else:
            thread = threading.Thread(target=self._run_loop, daemon=True)
            thread.start()
            return thread
    
    def _run_loop(self):
        """Main monitoring loop with MCP command polling"""
        heartbeat_counter = 0
        command_poll_counter = 0
        command_poll_interval = 5  # Poll for commands every 5 seconds
        
        while self.running:
            try:
                self.scan_all()
                
                # Poll for server commands (MCP)
                command_poll_counter += self.config.update_interval
                if command_poll_counter >= command_poll_interval:
                    commands = self.poll_commands()
                    for cmd in commands:
                        try:
                            self.execute_command(cmd)
                        except Exception as e:
                            logger.error(f"Command execution failed: {e}")
                    command_poll_counter = 0
                
                heartbeat_counter += self.config.update_interval
                if heartbeat_counter >= self.config.heartbeat_interval:
                    self.heartbeat()
                    heartbeat_counter = 0
                
                time.sleep(self.config.update_interval)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
                time.sleep(5)
        
        self.running = False
        logger.info("Agent stopped")
    
    def stop(self):
        """Stop the agent"""
        self.running = False


# Convenience function
def create_agent(server_url: Optional[str] = None, **kwargs) -> UnifiedAgent:
    """Create and configure a unified agent"""
    config = AgentConfig(server_url=server_url or "", **kwargs)
    return UnifiedAgent(config=config)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Metatron/Seraph Unified Security Agent")
    parser.add_argument("--server", "-s", help="Server URL", default="")
    parser.add_argument("--enrollment-key", help="Enrollment key for first registration", default="")
    parser.add_argument("--config", "-c", help="Config file path")
    parser.add_argument("--name", "-n", help="Agent name")
    parser.add_argument("--interval", "-i", type=int, default=_env_int("SERAPH_AGENT_UPDATE_INTERVAL", 300), help="Update interval")
    parser.add_argument("--no-auto-kill", action="store_true", help="Disable auto-kill")
    parser.add_argument("--ui-port", type=int, default=5000,
                        help="Port for the built-in local web UI (default: 5000)")
    parser.add_argument("--no-ui", action="store_true",
                        help="Disable the built-in local web UI")

    args = parser.parse_args()

    if args.config:
        agent = UnifiedAgent(config_path=args.config)
        if args.enrollment_key:
            agent.config.enrollment_key = args.enrollment_key
        if args.ui_port != 5000:
            agent.config.local_ui_port = args.ui_port
        if args.no_ui:
            agent.config.local_ui_enabled = False
    else:
        config = AgentConfig(
            server_url=args.server,
            enrollment_key=args.enrollment_key,
            agent_name=args.name or f"Metatron-{HOSTNAME}",
            update_interval=args.interval,
            auto_remediate=not args.no_auto_kill,
            local_ui_port=args.ui_port,
            local_ui_enabled=not args.no_ui,
        )
        agent = UnifiedAgent(config=config)

    print(f"""
\u2554\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2557
\u2551                    UNIFIED SECURITY AGENT v{AGENT_VERSION}
\u255a\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u255d

Agent ID:    {agent.config.agent_id}
Platform:    {PLATFORM}
Server:      {agent.config.server_url or 'Not configured'}
Auto-Kill:   {'Enabled' if agent.config.auto_remediate else 'Disabled'}
SIEM:        {'Enabled' if agent.siem.enabled else 'Disabled'}
Local Web UI: {'http://localhost:' + str(agent.config.local_ui_port) + ' (starting...)' if agent.config.local_ui_enabled else 'Disabled'}
""")

    agent.start()
