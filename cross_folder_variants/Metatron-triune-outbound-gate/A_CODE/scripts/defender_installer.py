#!/usr/bin/env python3
"""
Anti-AI Defense System - Complete Security Suite Installer v3.0
================================================================
This is a SINGLE-FILE installer that downloads and sets up the complete
local security agent with all features:

- Network Scanning (nmap)
- Intrusion Detection (Suricata, Falco)
- Malware/Virus Detection (YARA, ClamAV)
- Packet Capture (scapy)
- Process Monitoring
- Data Recovery Tools
- Local Web Dashboard

NEW IN v3.0:
- Live Task Manager Monitoring
- Suspicious Services/Processes Detection & Auto-Kill
- PUP (Potentially Unwanted Programs) Detection
- Privilege Escalation Monitoring
- Hidden File/Folder Scanner
- Rootkit Detection & Repair
- Advanced Scan Functions

USAGE:
    python defender_installer.py              # Interactive install
    python defender_installer.py --auto       # Automatic install
    python defender_installer.py --uninstall  # Remove installation
    python defender_installer.py --run        # Install and run immediately

Supports: Windows, macOS, Linux (Ubuntu/Debian/Fedora/Arch)

Author: Anti-AI Defense System
"""

import os
import sys
import json
import platform
import subprocess
import shutil
import urllib.request
import tempfile
import zipfile
import tarfile
import hashlib
import socket
import time
import threading
import argparse
from pathlib import Path
from datetime import datetime
from collections import deque

# =============================================================================
# CONFIGURATION
# =============================================================================

VERSION = "3.0.0"
INSTALL_DIR = Path.home() / ".anti-ai-defense"
VENV_DIR = INSTALL_DIR / "venv"
RULES_DIR = INSTALL_DIR / "yara_rules"
LOGS_DIR = INSTALL_DIR / "logs"
DATA_DIR = INSTALL_DIR / "data"
QUARANTINE_DIR = INSTALL_DIR / "quarantine"
RECOVERY_DIR = INSTALL_DIR / "recovery"
MODULES_DIR = INSTALL_DIR / "modules"
CONFIG_FILE = INSTALL_DIR / "config.json"


def normalize_server_url(url: str) -> str:
    """Normalize a base server URL to avoid duplicate /api path segments."""
    if not url:
        return ""

    normalized = str(url).strip().rstrip("/")
    if normalized.lower().endswith("/api"):
        normalized = normalized[:-4]

    return normalized.rstrip("/")


# Cloud API endpoint - UPDATE THIS TO YOUR DEPLOYMENT
CLOUD_API_URL = normalize_server_url(os.getenv("METATRON_API_URL", "https://seraph-security.preview.emergentagent.com"))

# Python packages required
PYTHON_PACKAGES = [
    "requests",
    "psutil",
    "flask",
    "flask-cors",
    "scapy",
    "yara-python",
    "python-nmap",
    "netifaces",
    "watchdog",
    "colorama",
]

# System packages for different OS
SYSTEM_PACKAGES = {
    "linux_apt": {
        "update": "sudo apt-get update -qq",
        "packages": ["python3-pip", "python3-venv", "nmap", "libpcap-dev", "tcpdump", "net-tools", "clamav", "clamav-daemon"],
        "suricata": "sudo apt-get install -y suricata",
        "falco": "curl -fsSL https://falco.org/repo/falcosecurity-packages.asc | sudo gpg --dearmor -o /usr/share/keyrings/falco-archive-keyring.gpg && echo 'deb [signed-by=/usr/share/keyrings/falco-archive-keyring.gpg] https://download.falco.org/packages/deb stable main' | sudo tee /etc/apt/sources.list.d/falcosecurity.list && sudo apt-get update -qq && sudo apt-get install -y falco",
        "install_cmd": "sudo apt-get install -y",
    },
    "linux_dnf": {
        "update": "sudo dnf check-update -q || true",
        "packages": ["python3-pip", "python3-virtualenv", "nmap", "libpcap-devel", "tcpdump", "net-tools", "clamav", "clamav-update"],
        "suricata": "sudo dnf install -y suricata",
        "falco": "sudo rpm --import https://falco.org/repo/falcosecurity-packages.asc && sudo curl -o /etc/yum.repos.d/falcosecurity.repo https://falco.org/repo/falcosecurity-rpm.repo && sudo dnf install -y falco",
        "install_cmd": "sudo dnf install -y",
    },
    "linux_pacman": {
        "update": "sudo pacman -Sy --noconfirm",
        "packages": ["python-pip", "python-virtualenv", "nmap", "libpcap", "tcpdump", "net-tools", "clamav"],
        "suricata": "sudo pacman -S --noconfirm suricata",
        "install_cmd": "sudo pacman -S --noconfirm",
    },
    "darwin": {
        "update": "brew update",
        "packages": ["python3", "nmap", "libpcap", "tcpdump", "clamav"],
        "suricata": "brew install suricata",
        "falco": "brew install falco",
        "install_cmd": "brew install",
    },
    "windows": {
        "packages": [],
        "note": "Windows requires manual installation of nmap, npcap, and ClamAV"
    }
}

# =============================================================================
# CONSOLE COLORS
# =============================================================================

class Colors:
    if platform.system() == "Windows":
        HEADER = BLUE = CYAN = GREEN = WARNING = FAIL = ENDC = BOLD = ""
    else:
        HEADER = '\033[95m'
        BLUE = '\033[94m'
        CYAN = '\033[96m'
        GREEN = '\033[92m'
        WARNING = '\033[93m'
        FAIL = '\033[91m'
        ENDC = '\033[0m'
        BOLD = '\033[1m'

def print_banner():
    banner = f"""
{Colors.CYAN}╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║     ██████╗ ███████╗███████╗███████╗███╗   ██╗██████╗ ███████╗██████╗ {Colors.ENDC}
{Colors.CYAN}║     ██╔══██╗██╔════╝██╔════╝██╔════╝████╗  ██║██╔══██╗██╔════╝██╔══██╗{Colors.ENDC}
{Colors.CYAN}║     ██║  ██║█████╗  █████╗  █████╗  ██╔██╗ ██║██║  ██║█████╗  ██████╔╝{Colors.ENDC}
{Colors.CYAN}║     ██║  ██║██╔══╝  ██╔══╝  ██╔══╝  ██║╚██╗██║██║  ██║██╔══╝  ██╔══██╗{Colors.ENDC}
{Colors.CYAN}║     ██████╔╝███████╗██║     ███████╗██║ ╚████║██████╔╝███████╗██║  ██║{Colors.ENDC}
{Colors.CYAN}║     ╚═════╝ ╚══════╝╚═╝     ╚══════╝╚═╝  ╚═══╝╚═════╝ ╚══════╝╚═╝  ╚═╝{Colors.ENDC}
{Colors.CYAN}║                                                                  ║
║          ANTI-AI DEFENSE SYSTEM - SECURITY SUITE v{VERSION}          ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝{Colors.ENDC}
"""
    print(banner)

def log(level, msg):
    icons = {"info": f"{Colors.BLUE}[*]{Colors.ENDC}", "ok": f"{Colors.GREEN}[✓]{Colors.ENDC}", 
             "warn": f"{Colors.WARNING}[!]{Colors.ENDC}", "err": f"{Colors.FAIL}[✗]{Colors.ENDC}"}
    print(f"{icons.get(level, '[*]')} {msg}")

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def run_cmd(cmd, shell=True, capture=False, check=True, timeout=300):
    """Run shell command with error handling"""
    try:
        if capture:
            result = subprocess.run(cmd, shell=shell, capture_output=True, text=True, check=check, timeout=timeout)
            return result.stdout.strip()
        else:
            subprocess.run(cmd, shell=shell, check=check, timeout=timeout)
            return True
    except subprocess.CalledProcessError:
        return None if capture else False
    except subprocess.TimeoutExpired:
        log("warn", f"Command timed out: {cmd[:50]}...")
        return None if capture else False
    except Exception as e:
        return None if capture else False

def detect_os():
    """Detect OS and package manager"""
    system = platform.system().lower()
    if system == "linux":
        if shutil.which("apt-get"):
            return "linux_apt"
        elif shutil.which("dnf"):
            return "linux_dnf"
        elif shutil.which("pacman"):
            return "linux_pacman"
        return "linux_apt"
    elif system == "darwin":
        return "darwin"
    elif system == "windows":
        return "windows"
    return None

def is_admin():
    """Check for admin/root privileges"""
    if platform.system() == "Windows":
        try:
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except:
            return False
    return os.geteuid() == 0

def get_pip():
    """Get pip path in venv"""
    if platform.system() == "Windows":
        return VENV_DIR / "Scripts" / "pip.exe"
    return VENV_DIR / "bin" / "pip"

def get_python():
    """Get python path in venv"""
    if platform.system() == "Windows":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"

# =============================================================================
# INSTALLATION FUNCTIONS
# =============================================================================

def create_directories():
    """Create all required directories"""
    log("info", "Creating directory structure...")
    for d in [INSTALL_DIR, VENV_DIR, RULES_DIR, LOGS_DIR, DATA_DIR, QUARANTINE_DIR, RECOVERY_DIR, MODULES_DIR]:
        d.mkdir(parents=True, exist_ok=True)
    log("ok", "Directories created")

def install_system_packages(os_type, auto=False):
    """Install system packages"""
    log("info", "Installing system packages...")
    
    if os_type == "windows":
        return install_windows_packages(auto)
    
    config = SYSTEM_PACKAGES.get(os_type, {})
    if not config:
        log("err", f"Unsupported OS: {os_type}")
        return False
    
    # Check for Homebrew on macOS
    if os_type == "darwin" and not shutil.which("brew"):
        log("info", "Installing Homebrew...")
        run_cmd('/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"', check=False)
    
    # Update package manager
    if config.get("update"):
        log("info", "Updating package manager...")
        run_cmd(config["update"], check=False)
    
    # Install packages
    if config.get("packages"):
        pkgs = " ".join(config["packages"])
        log("info", f"Installing: {pkgs}")
        run_cmd(f"{config['install_cmd']} {pkgs}", check=False)
    
    log("ok", "System packages installed")
    return True

def install_windows_packages(auto=False):
    """Install packages on Windows with automated download support"""
    log("info", "Windows detected - checking for available package managers...")
    
    # Check for winget (Windows Package Manager)
    has_winget = shutil.which("winget") is not None
    # Check for chocolatey
    has_choco = shutil.which("choco") is not None
    # Check for scoop
    has_scoop = shutil.which("scoop") is not None
    
    packages_installed = []
    packages_manual = []
    
    if has_winget:
        log("ok", "Found Windows Package Manager (winget)")
        # Install nmap via winget
        if not shutil.which("nmap"):
            log("info", "Installing Nmap via winget...")
            result = run_cmd("winget install Insecure.Nmap --accept-source-agreements --accept-package-agreements", check=False)
            if result:
                packages_installed.append("nmap")
            else:
                packages_manual.append(("nmap", "https://nmap.org/download.html"))
        else:
            log("ok", "Nmap already installed")
            packages_installed.append("nmap")
        
        # Install ClamAV via winget
        if not shutil.which("clamscan"):
            log("info", "Installing ClamAV via winget...")
            result = run_cmd("winget install ClamAV.ClamAV --accept-source-agreements --accept-package-agreements", check=False)
            if result:
                packages_installed.append("clamav")
            else:
                packages_manual.append(("ClamAV", "https://www.clamav.net/downloads"))
        else:
            log("ok", "ClamAV already installed")
            packages_installed.append("clamav")
            
    elif has_choco:
        log("ok", "Found Chocolatey package manager")
        # Install via chocolatey
        if not shutil.which("nmap"):
            log("info", "Installing Nmap via chocolatey...")
            result = run_cmd("choco install nmap -y", check=False)
            if result:
                packages_installed.append("nmap")
            else:
                packages_manual.append(("nmap", "https://nmap.org/download.html"))
        else:
            packages_installed.append("nmap")
            
        if not shutil.which("clamscan"):
            log("info", "Installing ClamAV via chocolatey...")
            result = run_cmd("choco install clamav -y", check=False)
            if result:
                packages_installed.append("clamav")
            else:
                packages_manual.append(("ClamAV", "https://www.clamav.net/downloads"))
        else:
            packages_installed.append("clamav")
            
    elif has_scoop:
        log("ok", "Found Scoop package manager")
        if not shutil.which("nmap"):
            log("info", "Installing Nmap via scoop...")
            result = run_cmd("scoop install nmap", check=False)
            if result:
                packages_installed.append("nmap")
            else:
                packages_manual.append(("nmap", "https://nmap.org/download.html"))
        else:
            packages_installed.append("nmap")
    else:
        log("warn", "No package manager found (winget, chocolatey, or scoop)")
        packages_manual = [
            ("nmap", "https://nmap.org/download.html"),
            ("npcap", "https://npcap.com/"),
            ("ClamAV", "https://www.clamav.net/downloads"),
        ]
    
    # Always need npcap for packet capture
    if not Path("C:/Windows/System32/Npcap").exists():
        packages_manual.append(("npcap", "https://npcap.com/"))
    
    # Summary
    if packages_installed:
        log("ok", f"Automatically installed: {', '.join(packages_installed)}")
    
    if packages_manual:
        log("warn", "The following tools require manual installation:")
        for name, url in packages_manual:
            print(f"  - {name}: {url}")
        
        if not auto:
            print()
            print("Would you like to open the download pages in your browser? [Y/n]")
            resp = input().strip().lower()
            if resp != 'n':
                import webbrowser
                for name, url in packages_manual:
                    webbrowser.open(url)
    
    # Additional Windows-specific tools suggestion
    log("info", "Windows Security Recommendations:")
    print("  - Consider installing Windows Defender (built-in)")
    print("  - Consider enabling Windows Firewall with Advanced Security")
    print("  - For container scanning, install Docker Desktop and Trivy")
    print("  - For VPN, install WireGuard from https://www.wireguard.com/install/")
    
    return True

def install_suricata(os_type, auto=False):
    """Install Suricata IDS"""
    config = SYSTEM_PACKAGES.get(os_type, {})
    if not config.get("suricata"):
        log("warn", "Suricata not available for this OS")
        return False
    
    if not auto:
        resp = input("Install Suricata IDS (intrusion detection)? [Y/n]: ").strip().lower()
        if resp == 'n':
            return False
    
    log("info", "Installing Suricata IDS...")
    result = run_cmd(config["suricata"], check=False)
    if result:
        log("ok", "Suricata installed")
        # Update rules
        run_cmd("sudo suricata-update", check=False)
    return result

def install_wireguard(os_type, auto=False):
    """Install WireGuard VPN"""
    if not auto:
        resp = input("Install WireGuard VPN? [Y/n]: ").strip().lower()
        if resp == 'n':
            return False
    
    log("info", "Installing WireGuard VPN...")
    
    if os_type == "windows":
        log("info", "For Windows, download WireGuard from: https://www.wireguard.com/install/")
        return False
    elif os_type == "darwin":
        result = run_cmd("brew install wireguard-tools", check=False)
    elif os_type == "linux_apt":
        result = run_cmd("sudo apt-get install -y wireguard wireguard-tools", check=False)
    elif os_type == "linux_dnf":
        result = run_cmd("sudo dnf install -y wireguard-tools", check=False)
    elif os_type == "linux_pacman":
        result = run_cmd("sudo pacman -S --noconfirm wireguard-tools", check=False)
    else:
        log("warn", "WireGuard installation not supported for this OS")
        return False
    
    if result:
        log("ok", "WireGuard installed")
    return result

def install_trivy(os_type, auto=False):
    """Install Trivy container scanner"""
    if not auto:
        resp = input("Install Trivy (container vulnerability scanner)? [Y/n]: ").strip().lower()
        if resp == 'n':
            return False
    
    log("info", "Installing Trivy container scanner...")
    
    if os_type == "windows":
        # Check for winget or chocolatey
        if shutil.which("winget"):
            result = run_cmd("winget install AquaSecurity.Trivy --accept-source-agreements --accept-package-agreements", check=False)
        elif shutil.which("choco"):
            result = run_cmd("choco install trivy -y", check=False)
        else:
            log("info", "For Windows, download Trivy from: https://github.com/aquasecurity/trivy/releases")
            return False
    elif os_type == "darwin":
        result = run_cmd("brew install trivy", check=False)
    elif os_type in ["linux_apt", "linux_dnf"]:
        # Install via official script
        log("info", "Installing Trivy via official installer...")
        result = run_cmd('curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sudo sh -s -- -b /usr/local/bin', check=False, timeout=300)
    elif os_type == "linux_pacman":
        result = run_cmd("sudo pacman -S --noconfirm trivy", check=False)
    else:
        log("warn", "Trivy installation not supported for this OS")
        return False
    
    if result:
        log("ok", "Trivy installed")
    return result

def install_volatility(os_type, auto=False):
    """Install Volatility 3 memory forensics framework"""
    if not auto:
        resp = input("Install Volatility 3 (memory forensics)? [Y/n]: ").strip().lower()
        if resp == 'n':
            return False
    
    log("info", "Installing Volatility 3 memory forensics...")
    
    pip = get_pip()
    
    # Install volatility3 via pip
    result = run_cmd(f"{pip} install volatility3", check=False)
    
    if result:
        log("ok", "Volatility 3 installed")
        # Download symbol tables (optional but recommended)
        log("info", "Note: For full functionality, download symbol tables from:")
        print("  https://downloads.volatilityfoundation.org/volatility3/symbols/")
    else:
        log("warn", "Volatility 3 installation failed - you can install manually with:")
        print("  pip install volatility3")
    
    return result

def install_falco(os_type, auto=False):
    """Install Falco runtime security"""
    config = SYSTEM_PACKAGES.get(os_type, {})
    if not config.get("falco"):
        log("warn", "Falco not available for this OS")
        return False
    
    if not auto:
        resp = input("Install Falco (container/host runtime security)? [Y/n]: ").strip().lower()
        if resp == 'n':
            return False
    
    log("info", "Installing Falco...")
    result = run_cmd(config["falco"], check=False, timeout=600)
    if result:
        log("ok", "Falco installed")
    return result

def setup_clamav():
    """Setup ClamAV antivirus"""
    log("info", "Configuring ClamAV antivirus...")
    
    if not shutil.which("clamscan") and not shutil.which("clamdscan"):
        log("warn", "ClamAV not found - skipping configuration")
        return False
    
    # Update virus definitions
    log("info", "Updating virus definitions (this may take a while)...")
    if shutil.which("freshclam"):
        run_cmd("sudo freshclam", check=False, timeout=600)
    
    log("ok", "ClamAV configured")
    return True

def create_venv():
    """Create Python virtual environment"""
    log("info", "Creating Python virtual environment...")
    if VENV_DIR.exists():
        shutil.rmtree(VENV_DIR)
    run_cmd(f"{sys.executable} -m venv {VENV_DIR}")
    log("ok", "Virtual environment created")

def install_python_packages():
    """Install Python packages"""
    log("info", "Installing Python packages...")
    pip = get_pip()
    
    # Upgrade pip
    run_cmd(f"{pip} install --upgrade pip -q", check=False)
    
    for pkg in PYTHON_PACKAGES:
        log("info", f"  Installing {pkg}...")
        result = run_cmd(f"{pip} install {pkg} -q", check=False)
        if result:
            log("ok", f"  {pkg} installed")
        else:
            log("warn", f"  {pkg} failed (non-critical)")
    
    log("ok", "Python packages installed")

def create_yara_rules():
    """Create comprehensive YARA rules"""
    log("info", "Creating YARA malware detection rules...")
    
    rules = '''
/*
 * Anti-AI Defense System - Comprehensive YARA Rules
 * Detects malware, ransomware, cryptominers, backdoors, and more
 */

rule SuspiciousScript {
    meta:
        description = "Detects suspicious script execution patterns"
        severity = "medium"
        category = "script"
    strings:
        $s1 = "eval(base64_decode" nocase
        $s2 = "exec(base64" nocase
        $s3 = "powershell -enc" nocase
        $s4 = "powershell -e " nocase
        $s5 = "IEX (New-Object" nocase
        $s6 = "/dev/tcp/" nocase
        $s7 = "nc -e /bin" nocase
        $s8 = "python -c \\"import socket" nocase
        $s9 = "bash -c \\"bash -i" nocase
    condition:
        any of them
}

rule CryptoMiner {
    meta:
        description = "Detects cryptocurrency mining software"
        severity = "high"
        category = "cryptominer"
    strings:
        $s1 = "stratum+tcp://" nocase
        $s2 = "stratum+ssl://" nocase
        $s3 = "xmrig" nocase fullword
        $s4 = "minerd" nocase fullword
        $s5 = "cryptonight" nocase
        $s6 = "monero" nocase fullword
        $s7 = "coinhive" nocase
        $s8 = "coin-hive" nocase
        $s9 = "hashrate" nocase fullword
        $s10 = "mining pool" nocase
    condition:
        any of them
}

rule WebShell {
    meta:
        description = "Detects web shell backdoors"
        severity = "critical"
        category = "webshell"
    strings:
        $php1 = "<?php eval($_" nocase
        $php2 = "<?php system($_" nocase
        $php3 = "<?php passthru(" nocase
        $php4 = "<?php shell_exec(" nocase
        $php5 = "<?php exec($_" nocase
        $php6 = "<?php assert(" nocase
        $asp1 = "<%eval request" nocase
        $asp2 = "<%execute request" nocase
        $jsp1 = "Runtime.getRuntime().exec" nocase
        $jsp2 = "ProcessBuilder" nocase
    condition:
        any of them
}

rule ReverseShell {
    meta:
        description = "Detects reverse shell patterns"
        severity = "critical"
        category = "backdoor"
    strings:
        $s1 = "bash -i >& /dev/tcp" nocase
        $s2 = "nc -e /bin/bash" nocase
        $s3 = "nc -e /bin/sh" nocase
        $s4 = "python -c \\'import socket,subprocess" nocase
        $s5 = "perl -e \\'use Socket" nocase
        $s6 = "ruby -rsocket -e" nocase
        $s7 = "socat exec:" nocase
        $s8 = "mknod backpipe p" nocase
        $s9 = "mkfifo /tmp/f" nocase
        $s10 = "0<&196;exec 196<>/dev/tcp" nocase
    condition:
        any of them
}

rule Ransomware {
    meta:
        description = "Detects ransomware indicators"
        severity = "critical"
        category = "ransomware"
    strings:
        $s1 = "Your files have been encrypted" nocase
        $s2 = "send bitcoin to" nocase
        $s3 = "decrypt your files" nocase
        $s4 = "DECRYPT_INSTRUCTIONS" nocase
        $s5 = "HOW_TO_DECRYPT" nocase
        $s6 = "ransom" nocase fullword
        $s7 = "!!! IMPORTANT !!!" nocase
        $s8 = "pay the ransom" nocase
        $s9 = "bitcoin wallet" nocase
        $ext1 = ".locked"
        $ext2 = ".encrypted"
        $ext3 = ".crypted"
        $ext4 = ".enc"
        $ext5 = ".cryptolocker"
    condition:
        2 of ($s*) or any of ($ext*)
}

rule Keylogger {
    meta:
        description = "Detects keylogger indicators"
        severity = "high"
        category = "spyware"
    strings:
        $s1 = "GetAsyncKeyState" nocase
        $s2 = "SetWindowsHookEx" nocase
        $s3 = "keylog" nocase
        $s4 = "keystroke" nocase
        $s5 = "keyboard hook" nocase
        $s6 = "GetKeyState" nocase
        $s7 = "WH_KEYBOARD" nocase
    condition:
        2 of them
}

rule CredentialStealer {
    meta:
        description = "Detects credential stealing malware"
        severity = "critical"
        category = "stealer"
    strings:
        $s1 = "chrome/User Data" nocase
        $s2 = "Login Data" nocase
        $s3 = "logins.json" nocase
        $s4 = "signons.sqlite" nocase
        $s5 = "cookies.sqlite" nocase
        $s6 = "key3.db" nocase
        $s7 = "key4.db" nocase
        $s8 = "Credentials" nocase
        $s9 = "Software\\\\Microsoft\\\\Windows\\\\CurrentVersion\\\\Explorer" nocase
        $s10 = "mimikatz" nocase
    condition:
        3 of them
}

rule Rootkit {
    meta:
        description = "Detects rootkit indicators"
        severity = "critical"
        category = "rootkit"
    strings:
        $s1 = "LD_PRELOAD" nocase
        $s2 = "/etc/ld.so.preload" nocase
        $s3 = "sys_call_table" nocase
        $s4 = "hide_pid" nocase
        $s5 = "rootkit" nocase
        $s6 = "intercept" nocase
        $s7 = "hook_" nocase
    condition:
        2 of them
}

rule BotnetC2 {
    meta:
        description = "Detects botnet command and control patterns"
        severity = "critical"
        category = "botnet"
    strings:
        $s1 = "PRIVMSG #" nocase
        $s2 = "JOIN #" nocase
        $s3 = "PING :" nocase
        $s4 = "PONG :" nocase
        $s5 = "dga" nocase fullword
        $s6 = "c2server" nocase
        $s7 = "command_and_control" nocase
        $s8 = "beacon" nocase fullword
    condition:
        2 of them
}

rule Trojan {
    meta:
        description = "Detects trojan horse indicators"
        severity = "high"
        category = "trojan"
    strings:
        $s1 = "VirtualAlloc" nocase
        $s2 = "WriteProcessMemory" nocase
        $s3 = "CreateRemoteThread" nocase
        $s4 = "NtUnmapViewOfSection" nocase
        $s5 = "IsDebuggerPresent" nocase
        $s6 = "CheckRemoteDebuggerPresent" nocase
        $mz = "MZ"
    condition:
        $mz at 0 and 3 of ($s*)
}

rule Adware {
    meta:
        description = "Detects adware indicators"
        severity = "medium"
        category = "adware"
    strings:
        $s1 = "ad injection" nocase
        $s2 = "popup" nocase fullword
        $s3 = "advertisement" nocase
        $s4 = "ad network" nocase
        $s5 = "browser hijack" nocase
    condition:
        2 of them
}

rule DataExfiltration {
    meta:
        description = "Detects data exfiltration patterns"
        severity = "high"
        category = "exfiltration"
    strings:
        $s1 = "upload" nocase fullword
        $s2 = "exfil" nocase
        $s3 = "steal" nocase fullword
        $s4 = "compress" nocase fullword
        $s5 = "archive" nocase fullword
        $s6 = "ftp://" nocase
        $s7 = "pastebin" nocase
    condition:
        3 of them
}
'''
    
    rules_file = RULES_DIR / "comprehensive_rules.yar"
    with open(rules_file, 'w') as f:
        f.write(rules)
    
    log("ok", "YARA rules created")

def create_config(os_type):
    """Create configuration file"""
    log("info", "Creating configuration...")
    
    config = {
        "version": VERSION,
        "api_url": CLOUD_API_URL,
        "agent_name": platform.node(),
        "agent_id": hashlib.md5(platform.node().encode()).hexdigest()[:16],
        "install_dir": str(INSTALL_DIR),
        "venv_dir": str(VENV_DIR),
        "yara_rules_dir": str(RULES_DIR),
        "logs_dir": str(LOGS_DIR),
        "quarantine_dir": str(QUARANTINE_DIR),
        "recovery_dir": str(RECOVERY_DIR),
        "local_dashboard_port": 5000,
        "suricata_log_path": "/var/log/suricata/eve.json" if os_type != "darwin" else "/usr/local/var/log/suricata/eve.json",
        "falco_log_path": "/var/log/falco/events.txt",
        "scan_directories": [
            str(Path.home() / "Downloads"),
            "/tmp" if os_type != "windows" else str(Path.home() / "AppData" / "Local" / "Temp"),
        ],
        "heartbeat_interval": 30,
        "network_scan_interval": 300,
        "yara_scan_interval": 600,
        "clamav_scan_interval": 3600,
        "features": {
            "packet_capture": True,
            "network_scan": shutil.which("nmap") is not None,
            "yara_scan": True,
            "clamav_scan": shutil.which("clamscan") is not None or shutil.which("clamdscan") is not None,
            "process_monitor": True,
            "suricata_monitor": shutil.which("suricata") is not None,
            "falco_monitor": shutil.which("falco") is not None,
            "local_dashboard": True,
            "data_recovery": True,
        }
    }
    
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)
    
    log("ok", "Configuration saved")
    return config

def create_agent_script():
    """Create the main agent script"""
    log("info", "Creating agent script...")
    
    agent_script = INSTALL_DIR / "defender_agent.py"
    
    # The agent script is comprehensive - embedding it here
    agent_code = '''#!/usr/bin/env python3
"""
Anti-AI Defense System - Local Security Agent v2.0
===================================================
Complete security monitoring with local dashboard.

Features:
- Network scanning (nmap)
- Intrusion detection (Suricata, Falco)
- Malware scanning (YARA, ClamAV)
- Packet capture (scapy)
- Process monitoring
- Data recovery tools
- Local web dashboard
- Cloud sync

Usage:
    sudo python defender_agent.py              # Start with dashboard
    sudo python defender_agent.py --headless   # No dashboard
    sudo python defender_agent.py --port 8080  # Custom port
"""

import os
import sys
import json
import time
import socket
import hashlib
import platform
import threading
import subprocess
import argparse
import shutil
from datetime import datetime
from pathlib import Path
from collections import deque

# Load configuration
CONFIG_PATH = Path(__file__).parent / "config.json"
if CONFIG_PATH.exists():
    with open(CONFIG_PATH) as f:
        CONFIG = json.load(f)
else:
    print("ERROR: config.json not found. Run installer first.")
    sys.exit(1)

# =============================================================================
# IMPORTS
# =============================================================================

def safe_import(module_name):
    try:
        return __import__(module_name)
    except ImportError:
        return None

requests = safe_import('requests')
psutil = safe_import('psutil')

if not requests or not psutil:
    print("ERROR: Missing core dependencies. Run installer.")
    sys.exit(1)

# Optional imports
flask = safe_import('flask')
scapy_module = safe_import('scapy.all')
yara = safe_import('yara')
nmap = safe_import('nmap')

FLASK_AVAILABLE = flask is not None
SCAPY_AVAILABLE = scapy_module is not None
YARA_AVAILABLE = yara is not None
NMAP_AVAILABLE = nmap is not None
CLAMAV_AVAILABLE = shutil.which('clamscan') or shutil.which('clamdscan')
FALCO_AVAILABLE = shutil.which('falco') is not None

if flask:
    from flask import Flask, render_template_string, jsonify
    from flask_cors import CORS

if scapy_module:
    from scapy.all import sniff, IP, TCP, UDP

# =============================================================================
# GLOBAL STATE
# =============================================================================

class AgentState:
    def __init__(self):
        self.running = True
        self.events = deque(maxlen=1000)
        self.alerts = deque(maxlen=200)
        self.threats = deque(maxlen=200)
        self.discovered_hosts = {}
        self.quarantined_files = []
        self.recovered_files = []
        self.packet_stats = {"total": 0, "tcp": 0, "udp": 0, "suspicious": 0}
        self.system_info = {}
        self.cloud_connected = False
        self.last_heartbeat = None
        self.scan_status = {"yara": "idle", "clamav": "idle", "network": "idle"}

state = AgentState()

# =============================================================================
# API CLIENT
# =============================================================================

class CloudAPI:
    def __init__(self):
        self.url = str(CONFIG.get("api_url", "")).strip().rstrip('/')
        if self.url.lower().endswith('/api'):
            self.url = self.url[:-4]
        self.agent_id = CONFIG.get("agent_id", hashlib.md5(platform.node().encode()).hexdigest()[:16])
        self.agent_name = CONFIG.get("agent_name", platform.node())
        self.session = requests.Session()
        self.session.headers.update({
            "X-Agent-Key": "local-agent",
            "X-Agent-ID": self.agent_id,
            "Content-Type": "application/json"
        })
    
    def send(self, event_type, data):
        payload = {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "event_type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "data": data
        }
        state.events.append({"type": event_type, "data": data, "timestamp": datetime.now().isoformat()})
        
        try:
            resp = self.session.post(f"{self.url}/api/agent/event", json=payload, timeout=10)
            state.cloud_connected = resp.status_code == 200
            return resp.status_code == 200
        except:
            state.cloud_connected = False
            return False

api = CloudAPI()

# =============================================================================
# SYSTEM MONITOR
# =============================================================================

def get_system_info():
    info = {
        "hostname": platform.node(),
        "os": platform.system(),
        "os_version": platform.version(),
        "architecture": platform.machine(),
        "cpu_count": psutil.cpu_count(),
        "cpu_percent": psutil.cpu_percent(interval=1),
        "memory_total": psutil.virtual_memory().total,
        "memory_percent": psutil.virtual_memory().percent,
        "disk_percent": psutil.disk_usage('/').percent if platform.system() != 'Windows' else psutil.disk_usage('C:\\\\').percent,
        "network_interfaces": [],
        "uptime_seconds": time.time() - psutil.boot_time(),
    }
    for name, addrs in psutil.net_if_addrs().items():
        for addr in addrs:
            if addr.family == socket.AF_INET and not addr.address.startswith('127.'):
                info["network_interfaces"].append({"name": name, "ip": addr.address, "netmask": addr.netmask})
    state.system_info = info
    return info

def get_suspicious_processes():
    suspicious = []
    patterns = ['nc -l', 'ncat -l', '/dev/tcp/', 'python -c "import socket', 'base64 -d', 
                'curl | bash', 'wget | bash', 'cryptominer', 'xmrig', 'coinhive']
    
    for proc in psutil.process_iter(['pid', 'name', 'username', 'cmdline']):
        try:
            cmdline = ' '.join(proc.info['cmdline'] or []).lower()
            for pattern in patterns:
                if pattern.lower() in cmdline:
                    suspicious.append({
                        "pid": proc.info['pid'], "name": proc.info['name'],
                        "cmdline": cmdline[:200], "pattern": pattern
                    })
                    break
        except:
            pass
    return suspicious

# =============================================================================
# NETWORK SCANNER
# =============================================================================

class NetworkScanner:
    def __init__(self):
        self.previous_hosts = set()
    
    def get_subnet(self):
        for iface, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if addr.family == socket.AF_INET and not addr.address.startswith('127.'):
                    parts = addr.address.split('.')
                    return f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"
        return None
    
    def scan(self):
        if not NMAP_AVAILABLE:
            return [], []
        
        subnet = self.get_subnet()
        if not subnet:
            return [], []
        
        state.scan_status["network"] = "scanning"
        try:
            nm = nmap.PortScanner()
            nm.scan(hosts=subnet, arguments='-sn -T4')
            
            hosts = []
            for host in nm.all_hosts():
                host_info = {
                    "ip": host,
                    "hostname": nm[host].hostname() or "unknown",
                    "state": nm[host].state(),
                    "mac": nm[host]['addresses'].get('mac'),
                    "vendor": list(nm[host].get('vendor', {}).values())[0] if nm[host].get('vendor') else None,
                    "last_seen": datetime.now().isoformat()
                }
                hosts.append(host_info)
                state.discovered_hosts[host] = host_info
            
            current = set(h["ip"] for h in hosts)
            new_hosts = current - self.previous_hosts
            self.previous_hosts = current
            
            state.scan_status["network"] = "idle"
            return hosts, list(new_hosts)
        except Exception as e:
            state.scan_status["network"] = f"error: {str(e)}"
            return [], []

network_scanner = NetworkScanner()

# =============================================================================
# YARA SCANNER
# =============================================================================

class YaraScanner:
    def __init__(self):
        self.rules = None
        self.scanned_files = {}
    
    def load_rules(self):
        if not YARA_AVAILABLE:
            return False
        
        rules_dir = Path(CONFIG.get("yara_rules_dir", ""))
        if not rules_dir.exists():
            return False
        
        try:
            rule_files = {f.name: str(f) for f in rules_dir.iterdir() if f.suffix in ['.yar', '.yara']}
            if rule_files:
                self.rules = yara.compile(filepaths=rule_files)
                return True
        except:
            pass
        return False
    
    def scan_file(self, filepath):
        if not self.rules:
            return []
        try:
            return [{"rule": m.rule, "meta": m.meta} for m in self.rules.match(filepath)]
        except:
            return []
    
    def scan_directory(self, directory):
        if not self.rules:
            return []
        
        results = []
        state.scan_status["yara"] = "scanning"
        
        try:
            for root, dirs, files in os.walk(directory):
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                for filename in files:
                    filepath = os.path.join(root, filename)
                    try:
                        if os.path.getsize(filepath) > 50 * 1024 * 1024:
                            continue
                        mtime = os.path.getmtime(filepath)
                        if filepath in self.scanned_files and self.scanned_files[filepath] == mtime:
                            continue
                        self.scanned_files[filepath] = mtime
                    except:
                        continue
                    
                    matches = self.scan_file(filepath)
                    if matches:
                        result = {"filepath": filepath, "matches": matches, "timestamp": datetime.now().isoformat()}
                        results.append(result)
                        state.threats.append(result)
        except:
            pass
        
        state.scan_status["yara"] = "idle"
        return results

yara_scanner = YaraScanner()

# =============================================================================
# CLAMAV SCANNER
# =============================================================================

class ClamAVScanner:
    def __init__(self):
        self.quarantine_dir = Path(CONFIG.get("quarantine_dir", ""))
    
    def scan_file(self, filepath):
        if not CLAMAV_AVAILABLE:
            return None
        
        cmd = "clamdscan" if shutil.which("clamdscan") else "clamscan"
        try:
            result = subprocess.run([cmd, "--infected", "--no-summary", filepath],
                                  capture_output=True, text=True, timeout=300)
            if result.returncode == 1:  # Infected
                return {"filepath": filepath, "output": result.stdout.strip()}
        except:
            pass
        return None
    
    def scan_directory(self, directory):
        if not CLAMAV_AVAILABLE:
            return []
        
        state.scan_status["clamav"] = "scanning"
        results = []
        cmd = "clamdscan" if shutil.which("clamdscan") else "clamscan"
        
        try:
            result = subprocess.run([cmd, "-r", "--infected", "--no-summary", directory],
                                  capture_output=True, text=True, timeout=3600)
            if result.returncode == 1:
                for line in result.stdout.strip().split('\\n'):
                    if ': ' in line and 'FOUND' in line:
                        filepath, threat = line.rsplit(': ', 1)
                        results.append({"filepath": filepath.strip(), "threat": threat.replace(' FOUND', ''),
                                       "timestamp": datetime.now().isoformat()})
                        state.threats.append(results[-1])
        except:
            pass
        
        state.scan_status["clamav"] = "idle"
        return results
    
    def quarantine_file(self, filepath):
        if not self.quarantine_dir.exists():
            self.quarantine_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            dest = self.quarantine_dir / (hashlib.md5(filepath.encode()).hexdigest() + "_" + Path(filepath).name)
            shutil.move(filepath, dest)
            state.quarantined_files.append({"original": filepath, "quarantined": str(dest), 
                                           "timestamp": datetime.now().isoformat()})
            return True
        except:
            return False

clamav_scanner = ClamAVScanner()

# =============================================================================
# DATA RECOVERY
# =============================================================================

class DataRecovery:
    def __init__(self):
        self.recovery_dir = Path(CONFIG.get("recovery_dir", ""))
    
    def find_deleted_files(self, directory, file_types=None):
        """Find recently deleted files using filesystem metadata"""
        # This is a simplified version - real recovery needs low-level disk access
        results = []
        
        # Check trash/recycle bin
        trash_paths = [
            Path.home() / ".local/share/Trash/files",  # Linux
            Path.home() / ".Trash",  # macOS
        ]
        
        for trash in trash_paths:
            if trash.exists():
                for f in trash.iterdir():
                    if file_types is None or f.suffix.lower() in file_types:
                        results.append({
                            "path": str(f),
                            "name": f.name,
                            "size": f.stat().st_size if f.exists() else 0,
                            "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat() if f.exists() else None
                        })
        
        return results
    
    def recover_file(self, trash_path, dest_dir=None):
        """Recover a file from trash"""
        if dest_dir is None:
            dest_dir = self.recovery_dir
        
        dest_dir = Path(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            src = Path(trash_path)
            dest = dest_dir / src.name
            shutil.copy2(src, dest)
            state.recovered_files.append({"original": trash_path, "recovered": str(dest),
                                         "timestamp": datetime.now().isoformat()})
            return str(dest)
        except:
            return None

data_recovery = DataRecovery()

# =============================================================================
# SURICATA MONITOR
# =============================================================================

class SuricataMonitor:
    def __init__(self):
        self.log_path = CONFIG.get("suricata_log_path", "/var/log/suricata/eve.json")
        self.last_position = 0
        self.running = False
    
    def parse_logs(self):
        if not os.path.exists(self.log_path):
            return []
        
        alerts = []
        try:
            with open(self.log_path, 'r') as f:
                f.seek(self.last_position)
                for line in f:
                    try:
                        event = json.loads(line.strip())
                        if event.get('event_type') == 'alert':
                            alert = {
                                "timestamp": event.get('timestamp'),
                                "src_ip": event.get('src_ip'),
                                "dest_ip": event.get('dest_ip'),
                                "signature": event.get('alert', {}).get('signature'),
                                "severity": event.get('alert', {}).get('severity'),
                                "category": event.get('alert', {}).get('category'),
                            }
                            alerts.append(alert)
                            state.alerts.append(alert)
                    except:
                        continue
                self.last_position = f.tell()
        except:
            pass
        return alerts
    
    def start(self):
        self.running = True
        def loop():
            while self.running:
                self.parse_logs()
                time.sleep(5)
        thread = threading.Thread(target=loop, daemon=True)
        thread.start()
        return thread
    
    def stop(self):
        self.running = False

suricata_monitor = SuricataMonitor()

# =============================================================================
# FALCO MONITOR
# =============================================================================

class FalcoMonitor:
    def __init__(self):
        self.log_path = CONFIG.get("falco_log_path", "/var/log/falco/events.txt")
        self.last_position = 0
        self.running = False
    
    def parse_logs(self):
        if not os.path.exists(self.log_path):
            return []
        
        alerts = []
        try:
            with open(self.log_path, 'r') as f:
                f.seek(self.last_position)
                for line in f:
                    if line.strip():
                        alert = {
                            "timestamp": datetime.now().isoformat(),
                            "message": line.strip(),
                            "source": "falco"
                        }
                        alerts.append(alert)
                        state.alerts.append(alert)
                self.last_position = f.tell()
        except:
            pass
        return alerts
    
    def start(self):
        self.running = True
        def loop():
            while self.running:
                self.parse_logs()
                time.sleep(5)
        thread = threading.Thread(target=loop, daemon=True)
        thread.start()
        return thread
    
    def stop(self):
        self.running = False

falco_monitor = FalcoMonitor()

# =============================================================================
# PACKET CAPTURE
# =============================================================================

class PacketCapture:
    SUSPICIOUS_PORTS = {4444, 5555, 6666, 6667, 31337, 12345, 12346, 1337, 9001}
    
    def __init__(self):
        self.running = False
        self.port_tracker = {}
    
    def analyze(self, packet):
        state.packet_stats["total"] += 1
        
        if not packet.haslayer(IP):
            return None
        
        src_ip = packet[IP].src
        
        if packet.haslayer(TCP):
            state.packet_stats["tcp"] += 1
            dst_port = packet[TCP].dport
            
            if dst_port in self.SUSPICIOUS_PORTS:
                state.packet_stats["suspicious"] += 1
                return {"type": "suspicious_port", "src_ip": src_ip, "dst_port": dst_port}
            
            if src_ip not in self.port_tracker:
                self.port_tracker[src_ip] = set()
            self.port_tracker[src_ip].add(dst_port)
            
            if len(self.port_tracker[src_ip]) > 20:
                state.packet_stats["suspicious"] += 1
                self.port_tracker[src_ip] = set()
                return {"type": "port_scan", "src_ip": src_ip}
        
        elif packet.haslayer(UDP):
            state.packet_stats["udp"] += 1
        
        return None
    
    def start(self, interface=None):
        if not SCAPY_AVAILABLE:
            return None
        
        self.running = True
        def capture():
            try:
                sniff(iface=interface, prn=lambda p: self._handle(p), store=False,
                      stop_filter=lambda x: not self.running)
            except:
                pass
        
        thread = threading.Thread(target=capture, daemon=True)
        thread.start()
        return thread
    
    def _handle(self, packet):
        result = self.analyze(packet)
        if result:
            state.alerts.append({**result, "timestamp": datetime.now().isoformat()})
    
    def stop(self):
        self.running = False

packet_capture = PacketCapture()

# =============================================================================
# LOCAL DASHBOARD
# =============================================================================

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Defender - Local Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=IBM+Plex+Sans:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'IBM Plex Sans', sans-serif; background: #020617; color: #F8FAFC; }
        .font-mono { font-family: 'JetBrains Mono', monospace; }
        .card { background: rgba(15, 23, 42, 0.8); backdrop-filter: blur(12px); border: 1px solid rgba(255, 255, 255, 0.1); }
    </style>
</head>
<body class="min-h-screen p-4 md:p-6">
    <div class="max-w-7xl mx-auto">
        <div class="flex items-center justify-between mb-6">
            <div class="flex items-center gap-3">
                <div class="w-10 h-10 rounded bg-blue-500/20 flex items-center justify-center">
                    <svg class="w-6 h-6 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"></path>
                    </svg>
                </div>
                <div>
                    <h1 class="text-xl font-mono font-bold">DEFENDER</h1>
                    <p class="text-xs text-slate-400">Anti-AI Defense System</p>
                </div>
            </div>
            <div class="flex items-center gap-2">
                <div id="cloud-status" class="px-3 py-1.5 rounded bg-slate-800 text-xs"></div>
                <div class="px-3 py-1.5 rounded bg-green-500/20 border border-green-500/30 text-xs text-green-400 font-mono">ACTIVE</div>
            </div>
        </div>

        <div class="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
            <div class="card rounded-lg p-3">
                <p class="text-slate-400 text-xs mb-1">Packets</p>
                <p id="stat-packets" class="text-xl font-mono font-bold text-cyan-400">0</p>
            </div>
            <div class="card rounded-lg p-3">
                <p class="text-slate-400 text-xs mb-1">Suspicious</p>
                <p id="stat-suspicious" class="text-xl font-mono font-bold text-red-400">0</p>
            </div>
            <div class="card rounded-lg p-3">
                <p class="text-slate-400 text-xs mb-1">Hosts</p>
                <p id="stat-hosts" class="text-xl font-mono font-bold text-blue-400">0</p>
            </div>
            <div class="card rounded-lg p-3">
                <p class="text-slate-400 text-xs mb-1">Threats</p>
                <p id="stat-threats" class="text-xl font-mono font-bold text-amber-400">0</p>
            </div>
            <div class="card rounded-lg p-3">
                <p class="text-slate-400 text-xs mb-1">Alerts</p>
                <p id="stat-alerts" class="text-xl font-mono font-bold text-purple-400">0</p>
            </div>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div class="card rounded-lg p-4">
                <h3 class="font-mono font-semibold mb-3 text-sm">System Info</h3>
                <div id="system-info" class="space-y-2 text-xs"></div>
            </div>

            <div class="card rounded-lg p-4 lg:col-span-2">
                <h3 class="font-mono font-semibold mb-3 text-sm">Network Traffic</h3>
                <canvas id="traffic-chart" height="120"></canvas>
            </div>

            <div class="card rounded-lg p-4">
                <h3 class="font-mono font-semibold mb-3 text-sm">Discovered Hosts</h3>
                <div id="hosts-list" class="space-y-2 max-h-48 overflow-y-auto text-xs"></div>
            </div>

            <div class="card rounded-lg p-4">
                <h3 class="font-mono font-semibold mb-3 text-sm">Recent Alerts</h3>
                <div id="alerts-list" class="space-y-2 max-h-48 overflow-y-auto text-xs"></div>
            </div>

            <div class="card rounded-lg p-4">
                <h3 class="font-mono font-semibold mb-3 text-sm">Malware Detections</h3>
                <div id="threats-list" class="space-y-2 max-h-48 overflow-y-auto text-xs"></div>
            </div>

            <div class="card rounded-lg p-4 lg:col-span-3">
                <h3 class="font-mono font-semibold mb-3 text-sm">Quick Actions</h3>
                <div class="flex flex-wrap gap-2">
                    <button onclick="triggerScan('network')" class="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 rounded text-xs">Network Scan</button>
                    <button onclick="triggerScan('yara')" class="px-3 py-1.5 bg-purple-600 hover:bg-purple-500 rounded text-xs">YARA Scan</button>
                    <button onclick="triggerScan('clamav')" class="px-3 py-1.5 bg-green-600 hover:bg-green-500 rounded text-xs">Antivirus Scan</button>
                    <button onclick="openRecovery()" class="px-3 py-1.5 bg-amber-600 hover:bg-amber-500 rounded text-xs">Data Recovery</button>
                </div>
            </div>
        </div>

        <div class="mt-4 text-center text-slate-500 text-xs">
            <p>Anti-AI Defense System v2.0 | Cloud: <a href="{{ cloud_url }}" target="_blank" class="text-blue-400 hover:underline">{{ cloud_url }}</a></p>
        </div>
    </div>

    <script>
        const ctx = document.getElementById('traffic-chart').getContext('2d');
        const chartData = {labels: [], datasets: [
            {label: 'TCP', data: [], borderColor: '#3B82F6', backgroundColor: 'rgba(59,130,246,0.1)', fill: true},
            {label: 'UDP', data: [], borderColor: '#10B981', backgroundColor: 'rgba(16,185,129,0.1)', fill: true},
            {label: 'Suspicious', data: [], borderColor: '#EF4444', backgroundColor: 'rgba(239,68,68,0.1)', fill: true}
        ]};
        const chart = new Chart(ctx, {type: 'line', data: chartData, options: {
            responsive: true, scales: {x: {display: true, grid: {color: '#1E293B'}}, y: {display: true, grid: {color: '#1E293B'}, beginAtZero: true}},
            plugins: {legend: {labels: {color: '#94A3B8', font: {size: 10}}}}
        }});

        let prevTcp = 0, prevUdp = 0, prevSus = 0;

        async function update() {
            try {
                const resp = await fetch('/api/status');
                const data = await resp.json();

                document.getElementById('stat-packets').textContent = data.packet_stats.total.toLocaleString();
                document.getElementById('stat-suspicious').textContent = data.packet_stats.suspicious;
                document.getElementById('stat-hosts').textContent = Object.keys(data.discovered_hosts).length;
                document.getElementById('stat-threats').textContent = data.threats.length;
                document.getElementById('stat-alerts').textContent = data.alerts.length;

                const cs = document.getElementById('cloud-status');
                cs.innerHTML = data.cloud_connected ? '<span class="text-green-400">Cloud Connected</span>' : '<span class="text-red-400">Cloud Offline</span>';

                const si = data.system_info;
                document.getElementById('system-info').innerHTML = `
                    <div class="flex justify-between"><span class="text-slate-500">Host</span><span>${si.hostname || 'N/A'}</span></div>
                    <div class="flex justify-between"><span class="text-slate-500">OS</span><span>${si.os || 'N/A'}</span></div>
                    <div class="flex justify-between"><span class="text-slate-500">CPU</span><span class="text-cyan-400">${si.cpu_percent || 0}%</span></div>
                    <div class="flex justify-between"><span class="text-slate-500">Memory</span><span class="text-cyan-400">${si.memory_percent || 0}%</span></div>
                    <div class="flex justify-between"><span class="text-slate-500">Disk</span><span class="text-cyan-400">${si.disk_percent || 0}%</span></div>
                `;

                chartData.labels.push(new Date().toLocaleTimeString());
                chartData.datasets[0].data.push(data.packet_stats.tcp - prevTcp);
                chartData.datasets[1].data.push(data.packet_stats.udp - prevUdp);
                chartData.datasets[2].data.push(data.packet_stats.suspicious - prevSus);
                prevTcp = data.packet_stats.tcp; prevUdp = data.packet_stats.udp; prevSus = data.packet_stats.suspicious;
                if (chartData.labels.length > 20) { chartData.labels.shift(); chartData.datasets.forEach(d => d.data.shift()); }
                chart.update();

                const hosts = Object.values(data.discovered_hosts);
                document.getElementById('hosts-list').innerHTML = hosts.length ? hosts.map(h => `
                    <div class="p-2 bg-slate-800/50 rounded"><span class="font-mono text-white">${h.ip}</span> - <span class="text-slate-400">${h.hostname || 'unknown'}</span></div>
                `).join('') : '<p class="text-slate-500">No hosts discovered</p>';

                document.getElementById('alerts-list').innerHTML = data.alerts.length ? data.alerts.slice(-10).reverse().map(a => `
                    <div class="p-2 bg-red-500/10 border-l-2 border-red-500 rounded-r">${a.type || a.signature || 'Alert'}</div>
                `).join('') : '<p class="text-slate-500">No alerts</p>';

                document.getElementById('threats-list').innerHTML = data.threats.length ? data.threats.slice(-10).reverse().map(t => `
                    <div class="p-2 bg-amber-500/10 border-l-2 border-amber-500 rounded-r">${t.matches ? t.matches.map(m => m.rule).join(', ') : t.threat || 'Threat'}</div>
                `).join('') : '<p class="text-slate-500">No threats detected</p>';

            } catch (err) { console.error(err); }
        }

        async function triggerScan(type) {
            try {
                await fetch('/api/scan/' + type, {method: 'POST'});
                alert(type + ' scan triggered!');
            } catch (err) { alert('Failed to trigger scan'); }
        }

        function openRecovery() {
            window.open('/recovery', '_blank');
        }

        setInterval(update, 2000);
        update();
    </script>
</body>
</html>
"""

def create_dashboard(config):
    if not FLASK_AVAILABLE:
        return None
    
    app = Flask(__name__)
    CORS(app)
    
    @app.route('/')
    def index():
        return render_template_string(DASHBOARD_HTML, cloud_url=config.get("api_url", "").replace("/api", ""))
    
    @app.route('/api/status')
    def status():
        return jsonify({
            "packet_stats": state.packet_stats,
            "discovered_hosts": state.discovered_hosts,
            "alerts": list(state.alerts)[-50:],
            "threats": list(state.threats)[-50:],
            "system_info": state.system_info,
            "cloud_connected": state.cloud_connected,
            "scan_status": state.scan_status,
            "quarantined": state.quarantined_files[-10:],
            "recovered": state.recovered_files[-10:]
        })
    
    @app.route('/api/scan/<scan_type>', methods=['POST'])
    def trigger_scan(scan_type):
        if scan_type == 'network':
            threading.Thread(target=lambda: network_scanner.scan(), daemon=True).start()
        elif scan_type == 'yara':
            def run_yara():
                if yara_scanner.load_rules():
                    for d in CONFIG.get("scan_directories", []):
                        if os.path.exists(d):
                            yara_scanner.scan_directory(d)
            threading.Thread(target=run_yara, daemon=True).start()
        elif scan_type == 'clamav':
            def run_clamav():
                for d in CONFIG.get("scan_directories", []):
                    if os.path.exists(d):
                        clamav_scanner.scan_directory(d)
            threading.Thread(target=run_clamav, daemon=True).start()
        return jsonify({"status": "triggered"})
    
    @app.route('/recovery')
    def recovery_page():
        deleted = data_recovery.find_deleted_files(str(Path.home()))
        return jsonify({"deleted_files": deleted, "recovered": state.recovered_files})
    
    return app

# =============================================================================
# MAIN AGENT
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description='Defender Security Agent')
    parser.add_argument('--port', type=int, default=5000, help='Dashboard port')
    parser.add_argument('--headless', action='store_true', help='Run without dashboard')
    args = parser.parse_args()
    
    print()
    print("=" * 60)
    print("  ANTI-AI DEFENSE SYSTEM - LOCAL SECURITY AGENT v2.0")
    print("=" * 60)
    print(f"  Agent: {CONFIG.get('agent_name', 'unknown')}")
    print(f"  Cloud: {CONFIG.get('api_url', 'N/A')}")
    print(f"  Dashboard: http://localhost:{args.port}")
    print("=" * 60)
    print()
    
    threads = []
    
    # Heartbeat
    def heartbeat_loop():
        while state.running:
            info = get_system_info()
            api.send("heartbeat", info)
            state.last_heartbeat = datetime.now().isoformat()
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Heartbeat - CPU: {info['cpu_percent']:.1f}%")
            time.sleep(CONFIG.get("heartbeat_interval", 30))
    
    t = threading.Thread(target=heartbeat_loop, daemon=True)
    t.start()
    threads.append(t)
    print("[+] Heartbeat started")
    
    # Network scanner
    if CONFIG.get("features", {}).get("network_scan") and NMAP_AVAILABLE:
        def network_loop():
            while state.running:
                hosts, new = network_scanner.scan()
                if hosts:
                    api.send("network_scan", {"hosts": hosts})
                    for ip in new:
                        api.send("alert", {"alert_type": "new_host", "severity": "low", "title": f"New host: {ip}", "details": {"ip": ip}})
                time.sleep(CONFIG.get("network_scan_interval", 300))
        t = threading.Thread(target=network_loop, daemon=True)
        t.start()
        threads.append(t)
        print("[+] Network scanner started")
    
    # YARA scanner
    if CONFIG.get("features", {}).get("yara_scan") and YARA_AVAILABLE:
        def yara_loop():
            while state.running:
                if yara_scanner.load_rules():
                    for d in CONFIG.get("scan_directories", []):
                        if os.path.exists(d):
                            results = yara_scanner.scan_directory(d)
                            for r in results:
                                api.send("yara_match", r)
                time.sleep(CONFIG.get("yara_scan_interval", 600))
        t = threading.Thread(target=yara_loop, daemon=True)
        t.start()
        threads.append(t)
        print("[+] YARA scanner started")
    
    # ClamAV scanner
    if CONFIG.get("features", {}).get("clamav_scan") and CLAMAV_AVAILABLE:
        def clamav_loop():
            while state.running:
                for d in CONFIG.get("scan_directories", []):
                    if os.path.exists(d):
                        results = clamav_scanner.scan_directory(d)
                        for r in results:
                            api.send("alert", {"alert_type": "malware", "severity": "critical", 
                                              "title": f"Malware: {r['threat']}", "details": r})
                time.sleep(CONFIG.get("clamav_scan_interval", 3600))
        t = threading.Thread(target=clamav_loop, daemon=True)
        t.start()
        threads.append(t)
        print("[+] ClamAV scanner started")
    
    # Process monitor
    if CONFIG.get("features", {}).get("process_monitor"):
        def process_loop():
            while state.running:
                suspicious = get_suspicious_processes()
                for p in suspicious:
                    state.alerts.append({**p, "type": "suspicious_process", "timestamp": datetime.now().isoformat()})
                    api.send("alert", {"alert_type": "suspicious_process", "severity": "high",
                                      "title": f"Suspicious: {p.get('name')}", "details": p})
                time.sleep(30)
        t = threading.Thread(target=process_loop, daemon=True)
        t.start()
        threads.append(t)
        print("[+] Process monitor started")
    
    # Suricata monitor
    if CONFIG.get("features", {}).get("suricata_monitor") and os.path.exists(CONFIG.get("suricata_log_path", "")):
        t = suricata_monitor.start()
        threads.append(t)
        print("[+] Suricata monitor started")
    
    # Falco monitor
    if CONFIG.get("features", {}).get("falco_monitor") and os.path.exists(CONFIG.get("falco_log_path", "")):
        t = falco_monitor.start()
        threads.append(t)
        print("[+] Falco monitor started")
    
    # Packet capture
    if CONFIG.get("features", {}).get("packet_capture") and SCAPY_AVAILABLE:
        t = packet_capture.start()
        if t:
            threads.append(t)
            print("[+] Packet capture started")
    
    print()
    
    # Dashboard
    if FLASK_AVAILABLE and not args.headless:
        app = create_dashboard(CONFIG)
        print(f"[+] Dashboard at http://localhost:{args.port}")
        print()
        print("Press Ctrl+C to stop")
        print()
        app.run(host='0.0.0.0', port=args.port, debug=False, use_reloader=False)
    else:
        print("[*] Running headless. Press Ctrl+C to stop.")
        try:
            while state.running:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
    
    print("\\n[*] Stopping...")
    state.running = False
    packet_capture.stop()
    suricata_monitor.stop()
    falco_monitor.stop()
    print("[*] Agent stopped")

if __name__ == "__main__":
    main()
'''
    
    with open(agent_script, 'w') as f:
        f.write(agent_code)
    
    os.chmod(agent_script, 0o755)
    log("ok", "Agent script created")

def create_advanced_security_module():
    """Create the advanced security monitoring module"""
    log("info", "Creating advanced security module...")
    
    module_path = MODULES_DIR / "advanced_security.py"
    
    # Download the advanced security module from the cloud API
    # For now, we embed a minimal version that will be enhanced
    module_code = '''#!/usr/bin/env python3
"""
Advanced Security Module v3.0
=============================
Live task manager monitoring, suspicious process detection,
PUP scanning, hidden file detection, and rootkit repair.
"""

import os
import sys
import json
import time
import hashlib
import platform
import threading
import subprocess
import re
import stat
from pathlib import Path
from datetime import datetime, timedelta
from collections import deque
from typing import Dict, List, Optional, Set, Any

try:
    import psutil
except ImportError:
    print("ERROR: psutil required")
    sys.exit(1)

# Suspicious patterns
SUSPICIOUS_PATTERNS = [
    r"nc\\s+-[el]", r"ncat\\s+-[el]", r"/dev/tcp/", r"bash\\s+-i.*>&",
    r"python.*socket.*subprocess", r"xmrig", r"minerd", r"cgminer",
    r"base64\\s+-d.*\\|.*sh", r"curl.*\\|.*bash", r"wget.*\\|.*sh",
    r"powershell.*-enc", r"mimikatz", r"rm\\s+-rf\\s+/",
]

SUSPICIOUS_SERVICES = {"cryptominer", "miner", "xmrig", "backdoor", "rootkit", "trojan", "keylogger", "rat", "botnet"}

PUP_SIGNATURES = {"adware", "toolbar", "browser helper", "popup", "registry cleaner", "driver updater", "opencandy", "installcore"}


class AdvancedSecurityMonitor:
    def __init__(self, config=None):
        self.config = config or {}
        self.running = False
        self.alerts = deque(maxlen=1000)
        self.flagged_processes = deque(maxlen=500)
        self.killed_processes = deque(maxlen=100)
        self.auto_kill_enabled = self.config.get("auto_kill_enabled", False)
        self.alert_callback = self.config.get("alert_callback")
        self.scan_interval = self.config.get("scan_interval", 10)
        self.threads = []
        self.process_baseline = {}
        self._build_baseline()
    
    def _build_baseline(self):
        for proc in psutil.process_iter(["pid", "name", "exe"]):
            try:
                self.process_baseline[proc.info["pid"]] = {"name": proc.info["name"], "exe": proc.info.get("exe")}
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    
    def _emit_alert(self, alert_type, severity, details):
        alert = {"type": alert_type, "severity": severity, "details": details, "timestamp": datetime.now().isoformat()}
        self.alerts.append(alert)
        if self.alert_callback:
            try:
                self.alert_callback(alert)
            except Exception:
                pass
        return alert
    
    def get_live_processes(self) -> List[Dict]:
        processes = []
        for proc in psutil.process_iter(["pid", "name", "username", "cpu_percent", "memory_percent", "status", "create_time", "exe", "cmdline", "connections"]):
            try:
                info = proc.info
                cmdline = " ".join(info.get("cmdline", []) or [])
                runtime = str(timedelta(seconds=int(time.time() - info.get("create_time", time.time()))))
                is_suspicious = self._is_suspicious(info["name"], cmdline, info.get("exe"))
                processes.append({
                    "pid": info["pid"], "name": info["name"], "username": info.get("username", "unknown"),
                    "cpu_percent": round(info.get("cpu_percent", 0), 1), "memory_percent": round(info.get("memory_percent", 0), 1),
                    "status": info.get("status", "unknown"), "runtime": runtime, "exe": info.get("exe"),
                    "cmdline": cmdline[:200], "connections": len(info.get("connections", []) or []),
                    "is_suspicious": is_suspicious, "is_new": info["pid"] not in self.process_baseline
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return sorted(processes, key=lambda x: x["cpu_percent"], reverse=True)
    
    def _is_suspicious(self, name, cmdline, exe):
        check_str = f"{name} {cmdline} {exe or ''}".lower()
        for pattern in SUSPICIOUS_PATTERNS:
            if re.search(pattern, check_str, re.IGNORECASE):
                return True
        return False
    
    def detect_suspicious_processes(self) -> List[Dict]:
        suspicious = []
        for proc in psutil.process_iter(["pid", "name", "exe", "cmdline", "username", "connections"]):
            try:
                info = proc.info
                cmdline = " ".join(info.get("cmdline", []) or [])
                check_str = f"{info['name']} {cmdline}".lower()
                reasons = []
                severity = "medium"
                
                for pattern in SUSPICIOUS_PATTERNS:
                    if re.search(pattern, check_str, re.IGNORECASE):
                        reasons.append(f"Pattern: {pattern}")
                        severity = "high"
                        if any(p in pattern for p in ["xmrig", "minerd", "mimikatz", "rm -rf /"]):
                            severity = "critical"
                
                connections = info.get("connections", []) or []
                suspicious_ports = {4444, 5555, 6666, 6667, 31337, 12345, 1337, 9001}
                for conn in connections:
                    if hasattr(conn, "raddr") and conn.raddr and conn.raddr.port in suspicious_ports:
                        reasons.append(f"Suspicious port: {conn.raddr.port}")
                        severity = "high"
                
                if reasons:
                    detection = {"pid": info["pid"], "name": info["name"], "exe": info.get("exe"),
                                "cmdline": cmdline[:200], "username": info.get("username"), "reasons": reasons,
                                "severity": severity, "timestamp": datetime.now().isoformat()}
                    suspicious.append(detection)
                    self.flagged_processes.append(detection)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return suspicious
    
    def kill_process(self, pid: int, reason: str = "Manual kill") -> Dict:
        try:
            proc = psutil.Process(pid)
            proc_info = {"pid": pid, "name": proc.name(), "exe": proc.exe() if hasattr(proc, "exe") else None,
                        "reason": reason, "timestamp": datetime.now().isoformat()}
            proc.kill()
            self.killed_processes.append(proc_info)
            self._emit_alert("process_killed", "info", proc_info)
            return {"success": True, "process": proc_info}
        except psutil.NoSuchProcess:
            return {"success": False, "error": "Process not found"}
        except psutil.AccessDenied:
            return {"success": False, "error": "Access denied"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_services(self) -> List[Dict]:
        services = []
        system = platform.system()
        if system == "Linux":
            try:
                result = subprocess.run(["systemctl", "list-units", "--type=service", "--all", "--no-pager"],
                                       capture_output=True, text=True, timeout=30)
                for line in result.stdout.split("\\n")[1:]:
                    if ".service" in line:
                        parts = line.split()
                        if len(parts) >= 4:
                            name = parts[0].replace(".service", "")
                            is_suspicious = any(s in name.lower() for s in SUSPICIOUS_SERVICES)
                            services.append({"name": name, "state": parts[2] if len(parts) > 2 else "unknown",
                                           "sub_state": parts[3] if len(parts) > 3 else "unknown", "is_suspicious": is_suspicious})
            except Exception:
                pass
        elif system == "Windows":
            try:
                for service in psutil.win_service_iter():
                    try:
                        svc_info = service.as_dict()
                        name = svc_info.get("name", "")
                        is_suspicious = any(s in name.lower() for s in SUSPICIOUS_SERVICES)
                        services.append({"name": name, "display_name": svc_info.get("display_name"),
                                        "status": svc_info.get("status"), "is_suspicious": is_suspicious})
                    except Exception:
                        pass
            except Exception:
                pass
        return services
    
    def scan_for_pups(self) -> List[Dict]:
        pups = []
        for proc in psutil.process_iter(["pid", "name", "exe"]):
            try:
                info = proc.info
                name_lower = info["name"].lower()
                exe_lower = (info.get("exe") or "").lower()
                reasons = []
                for sig in PUP_SIGNATURES:
                    if sig in name_lower or sig in exe_lower:
                        reasons.append(f"PUP signature: {sig}")
                if reasons:
                    pups.append({"type": "process", "pid": info["pid"], "name": info["name"],
                                "exe": info.get("exe"), "reasons": reasons, "timestamp": datetime.now().isoformat()})
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return pups
    
    def scan_hidden_files(self, directories=None) -> List[Dict]:
        if directories is None:
            directories = [str(Path.home()), "/tmp", "/var/tmp", "/dev/shm"]
        hidden = []
        for directory in directories:
            dir_path = Path(directory)
            if not dir_path.exists():
                continue
            try:
                for item in dir_path.rglob(".*"):
                    try:
                        stat_info = item.stat()
                        is_suspicious = False
                        reasons = []
                        if item.is_file() and (stat_info.st_mode & stat.S_IXUSR):
                            reasons.append("Hidden executable")
                            is_suspicious = True
                        mtime = datetime.fromtimestamp(stat_info.st_mtime)
                        if datetime.now() - mtime < timedelta(hours=24):
                            reasons.append("Recently modified")
                        suspicious_names = [".backdoor", ".shell", ".hack", ".pwn", ".rootkit", ".miner", ".crypto"]
                        for sname in suspicious_names:
                            if sname in item.name.lower():
                                reasons.append(f"Suspicious name: {sname}")
                                is_suspicious = True
                        hidden.append({"path": str(item), "name": item.name, "type": "directory" if item.is_dir() else "file",
                                      "size": stat_info.st_size if item.is_file() else 0, "modified": mtime.isoformat(),
                                      "is_suspicious": is_suspicious, "reasons": reasons})
                    except (PermissionError, OSError):
                        pass
            except (PermissionError, OSError):
                pass
        return hidden
    
    def detect_rootkits(self) -> Dict:
        findings = {"ld_preload_hijack": [], "hidden_processes": [], "hidden_modules": [],
                   "overall_status": "clean", "timestamp": datetime.now().isoformat()}
        if platform.system() != "Linux":
            findings["note"] = "Full rootkit detection only on Linux"
            return findings
        
        # Check LD_PRELOAD
        ld_path = Path("/etc/ld.so.preload")
        if ld_path.exists():
            try:
                content = ld_path.read_text()
                if content.strip():
                    findings["ld_preload_hijack"].append({"path": str(ld_path), "content": content, "severity": "critical"})
                    findings["overall_status"] = "infected"
            except PermissionError:
                pass
        
        # Check hidden processes
        try:
            proc_pids = {int(e.name) for e in Path("/proc").iterdir() if e.name.isdigit()}
            psutil_pids = set(psutil.pids())
            hidden = proc_pids - psutil_pids
            for pid in hidden:
                findings["hidden_processes"].append({"pid": pid, "severity": "critical"})
                findings["overall_status"] = "infected"
        except Exception:
            pass
        
        # Check kernel modules
        try:
            result = subprocess.run(["lsmod"], capture_output=True, text=True)
            for line in result.stdout.split("\\n")[1:]:
                if line:
                    module = line.split()[0].lower()
                    for indicator in ["rootkit", "hide", "stealth"]:
                        if indicator in module:
                            findings["hidden_modules"].append({"name": module, "severity": "high"})
                            findings["overall_status"] = "suspicious"
        except Exception:
            pass
        
        return findings
    
    def repair_rootkit_damage(self) -> Dict:
        repairs = {"actions_taken": [], "success": True, "timestamp": datetime.now().isoformat()}
        if platform.system() != "Linux":
            repairs["note"] = "Repair only on Linux"
            return repairs
        
        ld_path = Path("/etc/ld.so.preload")
        if ld_path.exists():
            try:
                content = ld_path.read_text()
                if content.strip():
                    Path("/tmp/ld.so.preload.backup").write_text(content)
                    ld_path.write_text("")
                    repairs["actions_taken"].append({"action": "cleared_ld_preload", "backup": "/tmp/ld.so.preload.backup"})
            except PermissionError:
                repairs["success"] = False
        
        return repairs
    
    def full_system_scan(self) -> Dict:
        results = {"scan_id": hashlib.md5(datetime.now().isoformat().encode()).hexdigest()[:16],
                  "start_time": datetime.now().isoformat(), "suspicious_processes": [], "suspicious_services": [],
                  "pup_detections": [], "hidden_files": [], "rootkit_findings": {}, "risk_score": 0, "summary": ""}
        
        results["suspicious_processes"] = self.detect_suspicious_processes()
        results["suspicious_services"] = [s for s in self.get_services() if s.get("is_suspicious")]
        results["pup_detections"] = self.scan_for_pups()
        results["hidden_files"] = self.scan_hidden_files()
        results["rootkit_findings"] = self.detect_rootkits()
        
        risk = len(results["suspicious_processes"]) * 10 + len(results["suspicious_services"]) * 5
        risk += len(results["pup_detections"]) * 3 + len([f for f in results["hidden_files"] if f.get("is_suspicious")]) * 5
        if results["rootkit_findings"].get("overall_status") == "infected":
            risk += 50
        elif results["rootkit_findings"].get("overall_status") == "suspicious":
            risk += 25
        
        results["risk_score"] = min(100, risk)
        if results["risk_score"] >= 75:
            results["summary"] = "CRITICAL: Multiple severe security issues detected."
        elif results["risk_score"] >= 50:
            results["summary"] = "HIGH: Significant security concerns found."
        elif results["risk_score"] >= 25:
            results["summary"] = "MEDIUM: Some potential issues detected."
        else:
            results["summary"] = "LOW: System appears relatively clean."
        
        results["end_time"] = datetime.now().isoformat()
        return results
    
    def monitor_processes(self):
        while self.running:
            try:
                suspicious = self.detect_suspicious_processes()
                for proc in suspicious:
                    self._emit_alert("suspicious_process", proc.get("severity", "high"), proc)
                    if self.auto_kill_enabled and proc.get("severity") == "critical":
                        self.kill_process(proc["pid"], "Auto-kill: Critical threat")
            except Exception:
                pass
            time.sleep(self.scan_interval)
    
    def start_all(self):
        self.running = True
        t = threading.Thread(target=self.monitor_processes, daemon=True)
        t.start()
        self.threads.append(t)
        return self.threads
    
    def stop_all(self):
        self.running = False
        for t in self.threads:
            t.join(timeout=5)
    
    def get_status(self) -> Dict:
        return {"running": self.running, "alerts_count": len(self.alerts), "killed_processes": len(self.killed_processes),
                "flagged_processes": len(self.flagged_processes), "auto_kill_enabled": self.auto_kill_enabled}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Advanced Security Monitor")
    parser.add_argument("--scan", choices=["full", "processes", "services", "hidden", "pup", "rootkit"], help="Run scan")
    parser.add_argument("--monitor", action="store_true", help="Start monitoring")
    parser.add_argument("--auto-kill", action="store_true", help="Enable auto-kill")
    args = parser.parse_args()
    
    monitor = AdvancedSecurityMonitor({"auto_kill_enabled": args.auto_kill})
    
    if args.scan:
        if args.scan == "full":
            result = monitor.full_system_scan()
        elif args.scan == "processes":
            result = monitor.detect_suspicious_processes()
        elif args.scan == "services":
            result = monitor.get_services()
        elif args.scan == "hidden":
            result = monitor.scan_hidden_files()
        elif args.scan == "pup":
            result = monitor.scan_for_pups()
        elif args.scan == "rootkit":
            result = monitor.detect_rootkits()
        print(json.dumps(result, indent=2))
    elif args.monitor:
        print("Starting monitor... Press Ctrl+C to stop")
        try:
            monitor.start_all()
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            monitor.stop_all()
    else:
        print(json.dumps(monitor.full_system_scan(), indent=2))
'''
    
    with open(module_path, 'w') as f:
        f.write(module_code)
    
    os.chmod(module_path, 0o755)
    log("ok", "Advanced security module created")

def create_launcher():
    """Create launcher scripts"""
    log("info", "Creating launcher scripts...")
    
    # Unix launcher
    if platform.system() != "Windows":
        launcher = INSTALL_DIR / "start_defender.sh"
        content = f'''#!/bin/bash
echo "Starting Anti-AI Defense System..."
cd "{INSTALL_DIR}"
sudo "{get_python()}" defender_agent.py "$@"
'''
        with open(launcher, 'w') as f:
            f.write(content)
        os.chmod(launcher, 0o755)
    
    # Windows launcher
    else:
        launcher = INSTALL_DIR / "start_defender.bat"
        content = f'''@echo off
echo Starting Anti-AI Defense System...
cd /d "{INSTALL_DIR}"
"{get_python()}" defender_agent.py %*
pause
'''
        with open(launcher, 'w') as f:
            f.write(content)
    
    log("ok", "Launcher created")

# =============================================================================
# MAIN INSTALLER
# =============================================================================

def install(auto=False):
    """Run full installation"""
    print_banner()
    
    os_type = detect_os()
    if not os_type:
        log("err", "Unsupported operating system")
        return False
    
    log("ok", f"Detected OS: {os_type}")
    log("info", f"Install directory: {INSTALL_DIR}")
    print()
    
    if not is_admin() and os_type != "windows":
        log("warn", "Not running as root. Some features may not install correctly.")
        if not auto:
            resp = input("Continue anyway? [y/N]: ").strip().lower()
            if resp != 'y':
                return False
    
    if not auto:
        resp = input("Proceed with installation? [Y/n]: ").strip().lower()
        if resp == 'n':
            return False
    
    print()
    print("=" * 60)
    print("INSTALLING ANTI-AI DEFENSE SYSTEM")
    print("=" * 60)
    print()
    
    create_directories()
    install_system_packages(os_type, auto)
    install_suricata(os_type, auto)
    install_falco(os_type, auto)
    install_wireguard(os_type, auto)
    install_trivy(os_type, auto)
    setup_clamav()
    create_venv()
    install_python_packages()
    install_volatility(os_type, auto)
    create_yara_rules()
    create_config(os_type)
    create_agent_script()
    create_advanced_security_module()
    create_launcher()
    
    print()
    print("=" * 60)
    print(f"{Colors.GREEN}INSTALLATION COMPLETE!{Colors.ENDC}")
    print("=" * 60)
    print()
    print("To start the security agent:")
    if platform.system() == "Windows":
        print(f"  {INSTALL_DIR}\\start_defender.bat")
    else:
        print(f"  sudo {INSTALL_DIR}/start_defender.sh")
    print()
    print("Or run directly:")
    print(f"  sudo {get_python()} {INSTALL_DIR}/defender_agent.py")
    print()
    print(f"Local dashboard will be at: http://localhost:5000")
    print(f"Cloud dashboard: {CLOUD_API_URL}")
    print()
    print("Installed components:")
    print(f"  - Core Agent: {INSTALL_DIR}/defender_agent.py")
    print(f"  - YARA Rules: {RULES_DIR}")
    print(f"  - WireGuard: {'Installed' if shutil.which('wg') else 'Manual install required'}")
    print(f"  - Trivy: {'Installed' if shutil.which('trivy') else 'Manual install required'}")
    print(f"  - Volatility: Check with 'vol3 --help'")
    print()
    
    return True

def uninstall():
    """Remove installation"""
    print_banner()
    log("warn", f"This will remove: {INSTALL_DIR}")
    resp = input("Are you sure? [y/N]: ").strip().lower()
    if resp == 'y':
        if INSTALL_DIR.exists():
            shutil.rmtree(INSTALL_DIR)
            log("ok", "Uninstalled successfully")
        else:
            log("info", "Nothing to uninstall")

def main():
    parser = argparse.ArgumentParser(description='Anti-AI Defense System Installer')
    parser.add_argument('--auto', action='store_true', help='Automatic installation')
    parser.add_argument('--uninstall', action='store_true', help='Remove installation')
    parser.add_argument('--run', action='store_true', help='Install and run immediately')
    args = parser.parse_args()
    
    if args.uninstall:
        uninstall()
    else:
        success = install(auto=args.auto or args.run)
        if success and args.run:
            print("Starting agent...")
            os.system(f"sudo {get_python()} {INSTALL_DIR}/defender_agent.py")

if __name__ == "__main__":
    main()
