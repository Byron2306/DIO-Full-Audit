#!/usr/bin/env python3
"""
Anti-AI Defense System - Universal Installer
=============================================
This script automatically installs all dependencies and sets up the local security agent.

Supports: Windows, macOS, Linux (Ubuntu/Debian/Fedora/Arch)

Usage:
    python install.py          # Interactive installation
    python install.py --auto   # Automatic installation with defaults
    python install.py --help   # Show help

Author: Anti-AI Defense System
"""

import os
import sys
import platform
import subprocess
import shutil
import urllib.request
import json
import tempfile
import zipfile
import tarfile
from pathlib import Path

# =============================================================================
# CONFIGURATION
# =============================================================================

INSTALL_DIR = Path.home() / ".anti-ai-defense"
VENV_DIR = INSTALL_DIR / "venv"
AGENT_DIR = INSTALL_DIR / "agent"
RULES_DIR = INSTALL_DIR / "yara_rules"
LOGS_DIR = INSTALL_DIR / "logs"
CONFIG_FILE = INSTALL_DIR / "config.json"

PYTHON_PACKAGES = [
    "requests",
    "psutil", 
    "flask",
    "flask-cors",
    "flask-socketio",
    "scapy",
    "yara-python",
    "python-nmap",
    "watchdog",
    "netifaces",
    "colorama",
    "rich",
]

# Package manager commands for different systems
SYSTEM_PACKAGES = {
    "linux_apt": {
        "update": "sudo apt-get update",
        "packages": [
            "python3-pip",
            "python3-venv",
            "nmap",
            "libpcap-dev",
            "tcpdump",
            "net-tools",
        ],
        "suricata": "sudo apt-get install -y suricata",
        "install_cmd": "sudo apt-get install -y",
    },
    "linux_dnf": {
        "update": "sudo dnf check-update || true",
        "packages": [
            "python3-pip",
            "python3-virtualenv",
            "nmap",
            "libpcap-devel",
            "tcpdump",
            "net-tools",
        ],
        "suricata": "sudo dnf install -y suricata",
        "install_cmd": "sudo dnf install -y",
    },
    "linux_pacman": {
        "update": "sudo pacman -Sy",
        "packages": [
            "python-pip",
            "python-virtualenv",
            "nmap",
            "libpcap",
            "tcpdump",
            "net-tools",
        ],
        "suricata": "sudo pacman -S --noconfirm suricata",
        "install_cmd": "sudo pacman -S --noconfirm",
    },
    "darwin": {
        "update": "brew update",
        "packages": [
            "python3",
            "nmap",
            "libpcap",
            "tcpdump",
        ],
        "suricata": "brew install suricata",
        "install_cmd": "brew install",
    },
    "windows": {
        "packages": [],
        "suricata": None,
    }
}


def normalize_server_url(url: str) -> str:
    """Normalize a base server URL to avoid duplicate /api path segments."""
    if not url:
        return ""

    normalized = str(url).strip().rstrip("/")
    if normalized.lower().endswith("/api"):
        normalized = normalized[:-4]

    return normalized.rstrip("/")

# =============================================================================
# UTILITIES
# =============================================================================

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_banner():
    banner = """
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║     █████╗ ███╗   ██╗████████╗██╗      █████╗ ██╗                ║
║    ██╔══██╗████╗  ██║╚══██╔══╝██║     ██╔══██╗██║                ║
║    ███████║██╔██╗ ██║   ██║   ██║     ███████║██║                ║
║    ██╔══██║██║╚██╗██║   ██║   ██║     ██╔══██║██║                ║
║    ██║  ██║██║ ╚████║   ██║   ██║     ██║  ██║██║                ║
║    ╚═╝  ╚═╝╚═╝  ╚═══╝   ╚═╝   ╚═╝     ╚═╝  ╚═╝╚═╝                ║
║                                                                  ║
║              DEFENSE SYSTEM - LOCAL AGENT INSTALLER              ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
    """
    print(f"{Colors.CYAN}{banner}{Colors.ENDC}")

def print_step(msg):
    print(f"{Colors.BLUE}[*]{Colors.ENDC} {msg}")

def print_success(msg):
    print(f"{Colors.GREEN}[✓]{Colors.ENDC} {msg}")

def print_warning(msg):
    print(f"{Colors.WARNING}[!]{Colors.ENDC} {msg}")

def print_error(msg):
    print(f"{Colors.FAIL}[✗]{Colors.ENDC} {msg}")

def run_command(cmd, shell=True, capture=False, check=True):
    """Run a shell command"""
    try:
        if capture:
            result = subprocess.run(cmd, shell=shell, capture_output=True, text=True, check=check)
            return result.stdout.strip()
        else:
            subprocess.run(cmd, shell=shell, check=check)
            return True
    except subprocess.CalledProcessError as e:
        if capture:
            return None
        return False

def detect_os():
    """Detect operating system and package manager"""
    system = platform.system().lower()
    
    if system == "linux":
        # Detect package manager
        if shutil.which("apt-get"):
            return "linux_apt"
        elif shutil.which("dnf"):
            return "linux_dnf"
        elif shutil.which("pacman"):
            return "linux_pacman"
        else:
            return "linux_apt"  # Default to apt
    elif system == "darwin":
        return "darwin"
    elif system == "windows":
        return "windows"
    else:
        return None

def check_admin():
    """Check if running with admin/root privileges"""
    if platform.system() == "Windows":
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    else:
        return os.geteuid() == 0

# =============================================================================
# INSTALLERS
# =============================================================================

def install_system_packages(os_type, auto=False):
    """Install system-level packages"""
    print_step("Installing system packages...")
    
    if os_type == "windows":
        print_warning("Windows detected. Some features require manual installation.")
        print("  - Download nmap from: https://nmap.org/download.html")
        print("  - Download Wireshark/npcap from: https://npcap.com/")
        return True
    
    config = SYSTEM_PACKAGES.get(os_type, {})
    
    if not config:
        print_error(f"Unsupported OS: {os_type}")
        return False
    
    # Check for brew on macOS
    if os_type == "darwin" and not shutil.which("brew"):
        print_warning("Homebrew not found. Installing...")
        run_command('/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"')
    
    # Update package manager
    if "update" in config:
        print_step("Updating package manager...")
        run_command(config["update"], check=False)
    
    # Install packages
    if config.get("packages"):
        packages = " ".join(config["packages"])
        cmd = f"{config['install_cmd']} {packages}"
        print_step(f"Installing: {packages}")
        run_command(cmd, check=False)
    
    print_success("System packages installed")
    return True

def install_suricata(os_type, auto=False):
    """Install Suricata IDS"""
    config = SYSTEM_PACKAGES.get(os_type, {})
    
    if not config.get("suricata"):
        print_warning("Suricata installation not available for this OS")
        return False
    
    if not auto:
        response = input("Install Suricata IDS? (recommended) [Y/n]: ").strip().lower()
        if response == 'n':
            return False
    
    print_step("Installing Suricata IDS...")
    run_command(config["suricata"], check=False)
    print_success("Suricata installed")
    return True

def create_virtual_environment():
    """Create Python virtual environment"""
    print_step("Creating Python virtual environment...")
    
    if VENV_DIR.exists():
        shutil.rmtree(VENV_DIR)
    
    run_command(f"{sys.executable} -m venv {VENV_DIR}")
    print_success("Virtual environment created")
    return True

def get_pip_path():
    """Get path to pip in virtual environment"""
    if platform.system() == "Windows":
        return VENV_DIR / "Scripts" / "pip.exe"
    else:
        return VENV_DIR / "bin" / "pip"

def get_python_path():
    """Get path to python in virtual environment"""
    if platform.system() == "Windows":
        return VENV_DIR / "Scripts" / "python.exe"
    else:
        return VENV_DIR / "bin" / "python"

def install_python_packages():
    """Install Python packages in virtual environment"""
    print_step("Installing Python packages...")
    
    pip_path = get_pip_path()
    
    # Upgrade pip
    run_command(f"{pip_path} install --upgrade pip", check=False)
    
    # Install packages
    for package in PYTHON_PACKAGES:
        print_step(f"  Installing {package}...")
        result = run_command(f"{pip_path} install {package}", check=False)
        if result:
            print_success(f"  {package} installed")
        else:
            print_warning(f"  {package} failed (non-critical)")
    
    print_success("Python packages installed")
    return True

def create_directory_structure():
    """Create installation directory structure"""
    print_step("Creating directory structure...")
    
    dirs = [INSTALL_DIR, AGENT_DIR, RULES_DIR, LOGS_DIR]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
    
    print_success("Directory structure created")
    return True

def create_default_yara_rules():
    """Create default YARA rules"""
    print_step("Creating default YARA rules...")
    
    rules_content = '''
rule SuspiciousScript {
    meta:
        description = "Detects suspicious script patterns"
        severity = "medium"
    strings:
        $s1 = "eval(base64_decode" nocase
        $s2 = "exec(base64" nocase
        $s3 = "powershell -enc" nocase
        $s4 = "IEX (New-Object" nocase
        $s5 = "/dev/tcp/" nocase
        $s6 = "nc -e /bin" nocase
        $s7 = "python -c \\"import socket" nocase
    condition:
        any of them
}

rule CryptoMiner {
    meta:
        description = "Detects cryptocurrency miners"
        severity = "high"
    strings:
        $s1 = "stratum+tcp://" nocase
        $s2 = "xmrig" nocase fullword
        $s3 = "minerd" nocase fullword
        $s4 = "cryptonight" nocase
        $s5 = "monero" nocase fullword
        $s6 = "coinhive" nocase
        $s7 = "coin-hive" nocase
    condition:
        any of them
}

rule WebShell {
    meta:
        description = "Detects potential web shells"
        severity = "critical"
    strings:
        $php1 = "<?php eval($_" nocase
        $php2 = "<?php system($_" nocase
        $php3 = "<?php passthru(" nocase
        $php4 = "<?php shell_exec(" nocase
        $php5 = "<?php exec($_" nocase
        $asp1 = "<%eval request" nocase
        $asp2 = "<%execute request" nocase
        $jsp1 = "Runtime.getRuntime().exec" nocase
    condition:
        any of them
}

rule ReverseShell {
    meta:
        description = "Detects reverse shell patterns"
        severity = "critical"
    strings:
        $s1 = "bash -i >& /dev/tcp" nocase
        $s2 = "nc -e /bin/bash" nocase
        $s3 = "nc -e /bin/sh" nocase
        $s4 = "python -c \\'import socket,subprocess" nocase
        $s5 = "perl -e \\'use Socket" nocase
        $s6 = "ruby -rsocket -e" nocase
        $s7 = "socat exec:" nocase
        $s8 = "mknod backpipe p" nocase
    condition:
        any of them
}

rule Ransomware {
    meta:
        description = "Detects potential ransomware"
        severity = "critical"
    strings:
        $s1 = "Your files have been encrypted" nocase
        $s2 = "send bitcoin to" nocase
        $s3 = "decrypt your files" nocase
        $s4 = ".locked" nocase
        $s5 = ".encrypted" nocase
        $s6 = "DECRYPT_INSTRUCTIONS" nocase
        $s7 = "HOW_TO_DECRYPT" nocase
        $s8 = "ransom" nocase fullword
    condition:
        2 of them
}

rule Keylogger {
    meta:
        description = "Detects potential keyloggers"
        severity = "high"
    strings:
        $s1 = "GetAsyncKeyState" nocase
        $s2 = "SetWindowsHookEx" nocase
        $s3 = "keylog" nocase
        $s4 = "keystroke" nocase
        $s5 = "keyboard hook" nocase
    condition:
        2 of them
}

rule CredentialStealer {
    meta:
        description = "Detects credential stealing malware"
        severity = "critical"
    strings:
        $s1 = "chrome/User Data" nocase
        $s2 = "Login Data" nocase
        $s3 = "logins.json" nocase
        $s4 = "signons.sqlite" nocase
        $s5 = "password" nocase fullword
        $s6 = "credential" nocase fullword
        $s7 = "Software\\\\Microsoft\\\\Windows\\\\CurrentVersion\\\\Explorer" nocase
    condition:
        3 of them
}

rule SuspiciousExecutable {
    meta:
        description = "Detects suspicious executable patterns"
        severity = "medium"
    strings:
        $mz = "MZ"
        $s1 = "VirtualAlloc" nocase
        $s2 = "WriteProcessMemory" nocase
        $s3 = "CreateRemoteThread" nocase
        $s4 = "NtUnmapViewOfSection" nocase
        $s5 = "IsDebuggerPresent" nocase
    condition:
        $mz at 0 and 3 of ($s*)
}
'''
    
    rules_file = RULES_DIR / "default_rules.yar"
    with open(rules_file, 'w') as f:
        f.write(rules_content)
    
    print_success("YARA rules created")
    return True

# =============================================================================
# MAIN INSTALLATION
# =============================================================================

def main():
    print_banner()
    
    # Parse arguments
    auto = "--auto" in sys.argv
    
    if "--help" in sys.argv:
        print("""
Usage: python install.py [OPTIONS]

Options:
    --auto      Automatic installation with defaults (no prompts)
    --help      Show this help message

The installer will:
1. Detect your operating system
2. Install required system packages (nmap, libpcap, etc.)
3. Optionally install Suricata IDS
4. Create a Python virtual environment
5. Install Python dependencies
6. Create default YARA malware rules
7. Set up the local security agent and dashboard
        """)
        return
    
    # Check permissions
    if not check_admin() and platform.system() != "Windows":
        print_warning("Not running as root. Some installations may fail.")
        print("Consider running: sudo python install.py")
        if not auto:
            response = input("Continue anyway? [y/N]: ").strip().lower()
            if response != 'y':
                return
    
    # Detect OS
    os_type = detect_os()
    if not os_type:
        print_error("Could not detect operating system")
        return
    
    print_success(f"Detected OS: {os_type}")
    print(f"Installation directory: {INSTALL_DIR}")
    print()
    
    if not auto:
        response = input("Proceed with installation? [Y/n]: ").strip().lower()
        if response == 'n':
            print("Installation cancelled")
            return
    
    print()
    print("=" * 60)
    print("STARTING INSTALLATION")
    print("=" * 60)
    print()
    
    # Create directory structure
    create_directory_structure()
    
    # Install system packages
    if os_type != "windows" or auto:
        install_system_packages(os_type, auto)
    
    # Install Suricata (optional)
    if os_type != "windows":
        install_suricata(os_type, auto)
    
    # Create virtual environment
    create_virtual_environment()
    
    # Install Python packages
    install_python_packages()
    
    # Create YARA rules
    create_default_yara_rules()
    
    # Create configuration
    print_step("Creating configuration...")
    config = {
        "api_url": normalize_server_url(os.getenv("METATRON_API_URL", "https://seraph-security.preview.emergentagent.com")),
        "agent_name": platform.node(),
        "install_dir": str(INSTALL_DIR),
        "venv_dir": str(VENV_DIR),
        "yara_rules_dir": str(RULES_DIR),
        "logs_dir": str(LOGS_DIR),
        "local_dashboard_port": 5000,
        "features": {
            "packet_capture": True,
            "network_scan": True,
            "yara_scan": True,
            "process_monitor": True,
            "suricata_monitor": shutil.which("suricata") is not None,
        }
    }
    
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)
    print_success("Configuration created")
    
    # Download agent files
    print_step("Setting up agent files...")
    # The agent files will be created by the next script
    
    print()
    print("=" * 60)
    print(f"{Colors.GREEN}INSTALLATION COMPLETE!{Colors.ENDC}")
    print("=" * 60)
    print()
    print("Next steps:")
    print(f"  1. cd {INSTALL_DIR}")
    print(f"  2. Run the agent: {get_python_path()} agent.py")
    print(f"  3. Open local dashboard: http://localhost:5000")
    print()
    print("Or use the quick start command:")
    if platform.system() == "Windows":
        print(f'  {VENV_DIR}\\Scripts\\python.exe {AGENT_DIR}\\agent.py')
    else:
        print(f"  sudo {get_python_path()} {AGENT_DIR}/agent.py")
    print()

if __name__ == "__main__":
    main()
