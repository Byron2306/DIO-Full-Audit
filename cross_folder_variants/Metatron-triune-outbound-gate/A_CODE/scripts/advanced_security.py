#!/usr/bin/env python3
"""
Anti-AI Defense System - Advanced Process Monitor & Security Scanner v3.0
=========================================================================
Advanced security monitoring module with:

- Live Task Manager Monitoring
- Suspicious Services/Processes Detection & Auto-Kill
- PUP (Potentially Unwanted Programs) Detection
- Privilege Escalation Monitoring
- Hidden File/Folder Scanner
- Rootkit Detection & Repair
- Advanced Scan Functions

This module integrates with the main defender agent.

Usage:
    from advanced_security import AdvancedSecurityMonitor
    monitor = AdvancedSecurityMonitor()
    monitor.start_all()
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
from typing import Dict, List, Optional, Set, Tuple, Any

# Try importing psutil
try:
    import psutil
except ImportError:
    print("ERROR: psutil is required. Install with: pip install psutil")
    sys.exit(1)

# =============================================================================
# CONFIGURATION
# =============================================================================

# Suspicious process patterns
SUSPICIOUS_PROCESS_PATTERNS = [
    # Reverse shells
    r"nc\s+-[el]",
    r"ncat\s+-[el]",
    r"/dev/tcp/",
    r"bash\s+-i.*>&",
    r"python.*socket.*subprocess",
    r"perl.*socket",
    r"ruby.*socket",
    r"php.*socket",
    # Cryptominers
    r"xmrig",
    r"minerd",
    r"cgminer",
    r"bfgminer",
    r"ethminer",
    r"stratum\+tcp://",
    r"coinhive",
    r"monero",
    # Malware patterns
    r"base64\s+-d.*\|.*sh",
    r"curl.*\|.*bash",
    r"wget.*\|.*sh",
    r"powershell.*-enc",
    r"powershell.*downloadstring",
    r"certutil.*decode",
    # Suspicious behavior
    r"rm\s+-rf\s+/",
    r"dd\s+if=/dev/zero",
    r"chmod\s+777\s+/",
    r"chown\s+root.*\s+/",
    # Credential stealing
    r"mimikatz",
    r"lazagne",
    r"procdump",
    r"secretsdump",
    r"hashdump",
]

# Suspicious service names
SUSPICIOUS_SERVICES = {
    "cryptominer", "miner", "xmrig", "minerd", "cgminer",
    "backdoor", "rootkit", "trojan", "keylogger",
    "rat", "botnet", "c2", "beacon",
}

# PUP (Potentially Unwanted Programs) signatures
PUP_SIGNATURES = {
    # Adware
    "adware", "toolbar", "browser helper", "search redirect",
    "popup", "ad-injection", "coupon", "deal",
    # System modifiers
    "registry cleaner", "driver updater", "pc optimizer",
    "system mechanic", "speed booster", "tune-up",
    # Bundleware
    "opencandy", "installcore", "installiq", "outbrowse",
    "softpulse", "somoto", "crossrider", "conduit",
}

# Critical system paths (should not be modified by unprivileged processes)
CRITICAL_PATHS = {
    "/etc/passwd", "/etc/shadow", "/etc/sudoers",
    "/etc/ssh/sshd_config", "/root/.ssh/authorized_keys",
    "/usr/bin", "/usr/sbin", "/bin", "/sbin",
    "/boot", "/lib", "/lib64",
}

# Rootkit indicators
ROOTKIT_INDICATORS = {
    # Hidden processes indicators
    "proc_hiding": ["/proc", "sys_call_table", "getdents"],
    # LD_PRELOAD hijacking
    "ld_preload": ["/etc/ld.so.preload", "LD_PRELOAD"],
    # Module hiding
    "module_hiding": ["sys_module", "hidden_module", "rootkit"],
    # Network hiding
    "network_hiding": ["tcp_seq_show", "udp_seq_show"],
}

# =============================================================================
# ADVANCED SECURITY MONITOR
# =============================================================================

class AdvancedSecurityMonitor:
    """
    Comprehensive security monitoring system with real-time process monitoring,
    suspicious activity detection, and automated response capabilities.
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.running = False
        self.threads = []
        
        # State tracking
        self.process_baseline = {}
        self.service_baseline = {}
        self.file_baseline = {}
        self.alerts = deque(maxlen=1000)
        self.killed_processes = deque(maxlen=100)
        self.flagged_processes = deque(maxlen=500)
        self.hidden_files = []
        self.pup_detections = []
        self.rootkit_findings = []
        
        # Configuration
        self.auto_kill_enabled = self.config.get("auto_kill_enabled", False)
        self.scan_interval = self.config.get("scan_interval", 10)
        self.alert_callback = self.config.get("alert_callback", None)
        
        # Initialize baselines
        self._build_process_baseline()
        self._build_service_baseline()
    
    def _build_process_baseline(self):
        """Build baseline of known good processes"""
        for proc in psutil.process_iter(['pid', 'name', 'exe', 'username']):
            try:
                self.process_baseline[proc.info['pid']] = {
                    'name': proc.info['name'],
                    'exe': proc.info.get('exe'),
                    'username': proc.info.get('username'),
                    'seen_at': datetime.now().isoformat()
                }
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    
    def _build_service_baseline(self):
        """Build baseline of known services (Linux/Windows)"""
        system = platform.system()
        
        if system == "Linux":
            try:
                result = subprocess.run(
                    ["systemctl", "list-units", "--type=service", "--all", "--output=json"],
                    capture_output=True, text=True, timeout=30
                )
                if result.returncode == 0:
                    services = json.loads(result.stdout)
                    for svc in services:
                        self.service_baseline[svc.get('unit', '')] = {
                            'state': svc.get('active'),
                            'seen_at': datetime.now().isoformat()
                        }
            except Exception:
                pass
        
        elif system == "Windows":
            try:
                for service in psutil.win_service_iter():
                    try:
                        svc_info = service.as_dict()
                        self.service_baseline[svc_info['name']] = {
                            'display_name': svc_info.get('display_name'),
                            'status': svc_info.get('status'),
                            'seen_at': datetime.now().isoformat()
                        }
                    except Exception:
                        pass
            except Exception:
                pass
    
    def _emit_alert(self, alert_type: str, severity: str, details: Dict):
        """Emit an alert"""
        alert = {
            "type": alert_type,
            "severity": severity,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        self.alerts.append(alert)
        
        if self.alert_callback:
            try:
                self.alert_callback(alert)
            except Exception as e:
                print(f"Alert callback error: {e}")
        
        return alert
    
    # =========================================================================
    # LIVE TASK MANAGER / PROCESS MONITORING
    # =========================================================================
    
    def get_live_processes(self) -> List[Dict]:
        """Get live list of all running processes with detailed info"""
        processes = []
        for proc in psutil.process_iter([
            'pid', 'name', 'username', 'cpu_percent', 'memory_percent',
            'status', 'create_time', 'exe', 'cmdline', 'connections'
        ]):
            try:
                info = proc.info
                
                # Calculate runtime
                if info.get('create_time'):
                    runtime = datetime.now() - datetime.fromtimestamp(info['create_time'])
                    runtime_str = str(timedelta(seconds=int(runtime.total_seconds())))
                else:
                    runtime_str = "unknown"
                
                # Check for suspicious patterns
                cmdline = ' '.join(info.get('cmdline', []) or [])
                is_suspicious = self._is_suspicious_process(info['name'], cmdline, info.get('exe'))
                
                processes.append({
                    "pid": info['pid'],
                    "name": info['name'],
                    "username": info.get('username', 'unknown'),
                    "cpu_percent": round(info.get('cpu_percent', 0), 1),
                    "memory_percent": round(info.get('memory_percent', 0), 1),
                    "status": info.get('status', 'unknown'),
                    "runtime": runtime_str,
                    "exe": info.get('exe'),
                    "cmdline": cmdline[:200] if cmdline else "",
                    "connections": len(info.get('connections', []) or []),
                    "is_suspicious": is_suspicious,
                    "is_new": info['pid'] not in self.process_baseline
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        return sorted(processes, key=lambda x: x['cpu_percent'], reverse=True)
    
    def _is_suspicious_process(self, name: str, cmdline: str, exe: str) -> bool:
        """Check if a process is suspicious"""
        check_str = f"{name} {cmdline} {exe or ''}".lower()
        
        for pattern in SUSPICIOUS_PROCESS_PATTERNS:
            if re.search(pattern, check_str, re.IGNORECASE):
                return True
        
        return False
    
    def monitor_processes(self):
        """Continuous process monitoring loop"""
        while self.running:
            try:
                suspicious = self.detect_suspicious_processes()
                for proc in suspicious:
                    self._emit_alert(
                        "suspicious_process",
                        proc.get("severity", "high"),
                        proc
                    )
                    
                    if self.auto_kill_enabled and proc.get("severity") == "critical":
                        self.kill_process(proc["pid"], "Auto-kill: Critical threat")
                
            except Exception as e:
                print(f"Process monitor error: {e}")
            
            time.sleep(self.scan_interval)
    
    def detect_suspicious_processes(self) -> List[Dict]:
        """Detect suspicious processes"""
        suspicious = []
        
        for proc in psutil.process_iter(['pid', 'name', 'exe', 'cmdline', 'username', 'connections']):
            try:
                info = proc.info
                cmdline = ' '.join(info.get('cmdline', []) or [])
                check_str = f"{info['name']} {cmdline}".lower()
                
                reasons = []
                severity = "medium"
                
                # Check against patterns
                for pattern in SUSPICIOUS_PROCESS_PATTERNS:
                    if re.search(pattern, check_str, re.IGNORECASE):
                        reasons.append(f"Matches pattern: {pattern}")
                        severity = "high"
                        
                        # Critical patterns
                        if any(p in pattern for p in ["xmrig", "minerd", "mimikatz", "rm -rf /"]):
                            severity = "critical"
                
                # Check for high network activity
                connections = info.get('connections', []) or []
                if len(connections) > 50:
                    reasons.append(f"High network activity: {len(connections)} connections")
                
                # Check for suspicious ports
                suspicious_ports = {4444, 5555, 6666, 6667, 31337, 12345, 1337, 9001}
                for conn in connections:
                    if hasattr(conn, 'raddr') and conn.raddr:
                        if conn.raddr.port in suspicious_ports:
                            reasons.append(f"Connection to suspicious port: {conn.raddr.port}")
                            severity = "high"
                
                if reasons:
                    detection = {
                        "pid": info['pid'],
                        "name": info['name'],
                        "exe": info.get('exe'),
                        "cmdline": cmdline[:200],
                        "username": info.get('username'),
                        "reasons": reasons,
                        "severity": severity,
                        "timestamp": datetime.now().isoformat()
                    }
                    suspicious.append(detection)
                    self.flagged_processes.append(detection)
                    
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        return suspicious
    
    def kill_process(self, pid: int, reason: str = "Manual kill") -> Dict:
        """Kill a suspicious process"""
        try:
            proc = psutil.Process(pid)
            proc_info = {
                "pid": pid,
                "name": proc.name(),
                "exe": proc.exe() if hasattr(proc, 'exe') else None,
                "reason": reason,
                "timestamp": datetime.now().isoformat()
            }
            
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
    
    # =========================================================================
    # SERVICE MONITORING
    # =========================================================================
    
    def get_services(self) -> List[Dict]:
        """Get list of all services"""
        services = []
        system = platform.system()
        
        if system == "Linux":
            try:
                result = subprocess.run(
                    ["systemctl", "list-units", "--type=service", "--all", "--no-pager"],
                    capture_output=True, text=True, timeout=30
                )
                
                for line in result.stdout.split('\n')[1:]:
                    if '.service' in line:
                        parts = line.split()
                        if len(parts) >= 4:
                            name = parts[0].replace('.service', '')
                            is_suspicious = any(s in name.lower() for s in SUSPICIOUS_SERVICES)
                            services.append({
                                "name": name,
                                "state": parts[2] if len(parts) > 2 else "unknown",
                                "sub_state": parts[3] if len(parts) > 3 else "unknown",
                                "is_suspicious": is_suspicious
                            })
            except Exception as e:
                print(f"Service enumeration error: {e}")
        
        elif system == "Windows":
            try:
                for service in psutil.win_service_iter():
                    try:
                        svc_info = service.as_dict()
                        name = svc_info.get('name', '')
                        is_suspicious = any(s in name.lower() for s in SUSPICIOUS_SERVICES)
                        services.append({
                            "name": name,
                            "display_name": svc_info.get('display_name'),
                            "status": svc_info.get('status'),
                            "start_type": svc_info.get('start_type'),
                            "is_suspicious": is_suspicious
                        })
                    except Exception:
                        pass
            except Exception as e:
                print(f"Service enumeration error: {e}")
        
        return services
    
    def detect_suspicious_services(self) -> List[Dict]:
        """Detect suspicious services"""
        suspicious = []
        services = self.get_services()
        
        for svc in services:
            reasons = []
            
            # Check for suspicious names
            name_lower = svc['name'].lower()
            for pattern in SUSPICIOUS_SERVICES:
                if pattern in name_lower:
                    reasons.append(f"Suspicious name pattern: {pattern}")
            
            # Check for new services not in baseline
            if svc['name'] not in self.service_baseline:
                reasons.append("New service not in baseline")
            
            if reasons:
                svc['reasons'] = reasons
                svc['timestamp'] = datetime.now().isoformat()
                suspicious.append(svc)
        
        return suspicious
    
    # =========================================================================
    # PUP (POTENTIALLY UNWANTED PROGRAMS) DETECTION
    # =========================================================================
    
    def scan_for_pups(self) -> List[Dict]:
        """Scan for potentially unwanted programs"""
        pups_found = []
        
        # Check running processes
        for proc in psutil.process_iter(['pid', 'name', 'exe', 'cmdline']):
            try:
                info = proc.info
                name_lower = info['name'].lower()
                exe = info.get('exe', '') or ''
                exe_lower = exe.lower()
                
                reasons = []
                
                for signature in PUP_SIGNATURES:
                    if signature in name_lower or signature in exe_lower:
                        reasons.append(f"PUP signature match: {signature}")
                
                if reasons:
                    pup = {
                        "type": "process",
                        "pid": info['pid'],
                        "name": info['name'],
                        "exe": exe,
                        "reasons": reasons,
                        "timestamp": datetime.now().isoformat()
                    }
                    pups_found.append(pup)
                    
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        # Check installed applications (platform-specific)
        system = platform.system()
        
        if system == "Linux":
            # Check common PUP installation paths
            pup_paths = [
                Path.home() / ".local" / "share" / "applications",
                Path("/opt"),
                Path("/usr/share/applications"),
            ]
            
            for path in pup_paths:
                if path.exists():
                    for item in path.iterdir():
                        name_lower = item.name.lower()
                        for signature in PUP_SIGNATURES:
                            if signature in name_lower:
                                pups_found.append({
                                    "type": "installed_app",
                                    "path": str(item),
                                    "name": item.name,
                                    "reasons": [f"PUP signature match: {signature}"],
                                    "timestamp": datetime.now().isoformat()
                                })
        
        self.pup_detections = pups_found
        return pups_found
    
    # =========================================================================
    # PRIVILEGE ESCALATION MONITORING
    # =========================================================================
    
    def monitor_privilege_escalation(self) -> List[Dict]:
        """Monitor for privilege escalation attempts"""
        findings = []
        
        for proc in psutil.process_iter(['pid', 'name', 'username', 'uids', 'gids']):
            try:
                info = proc.info
                
                # Check for SUID/SGID processes
                uids = info.get('uids')
                gids = info.get('gids')
                
                if uids:
                    # Check if effective UID is 0 (root) but real UID is not
                    if hasattr(uids, 'effective') and hasattr(uids, 'real'):
                        if uids.effective == 0 and uids.real != 0:
                            findings.append({
                                "type": "suid_escalation",
                                "pid": info['pid'],
                                "name": info['name'],
                                "real_uid": uids.real,
                                "effective_uid": uids.effective,
                                "severity": "high",
                                "timestamp": datetime.now().isoformat()
                            })
                
                # Check for processes with admin privileges that shouldn't have them
                username = info.get('username', '')
                if username == 'root' or username == 'SYSTEM':
                    # Check if this is a known system process
                    known_root_procs = {
                        'systemd', 'init', 'kthreadd', 'kworker', 'migration',
                        'ksoftirqd', 'rcu', 'watchdog', 'sshd', 'cron', 'rsyslog'
                    }
                    
                    if info['name'] not in known_root_procs:
                        if info['pid'] not in self.process_baseline:
                            findings.append({
                                "type": "unexpected_root_process",
                                "pid": info['pid'],
                                "name": info['name'],
                                "username": username,
                                "severity": "medium",
                                "timestamp": datetime.now().isoformat()
                            })
                            
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        return findings
    
    # =========================================================================
    # HIDDEN FILE/FOLDER SCANNER
    # =========================================================================
    
    def scan_hidden_files(self, directories: List[str] = None) -> List[Dict]:
        """Scan for hidden files and folders"""
        if directories is None:
            directories = [
                str(Path.home()),
                "/tmp",
                "/var/tmp",
                "/dev/shm",
            ]
        
        hidden_items = []
        
        for directory in directories:
            dir_path = Path(directory)
            if not dir_path.exists():
                continue
            
            try:
                for item in dir_path.rglob(".*"):
                    try:
                        stat_info = item.stat()
                        
                        # Check for suspicious hidden files
                        is_suspicious = False
                        reasons = []
                        
                        # Check for executable hidden files
                        if item.is_file() and (stat_info.st_mode & stat.S_IXUSR):
                            reasons.append("Hidden executable file")
                            is_suspicious = True
                        
                        # Check for recently modified hidden files
                        mtime = datetime.fromtimestamp(stat_info.st_mtime)
                        if datetime.now() - mtime < timedelta(hours=24):
                            reasons.append("Recently modified (within 24h)")
                        
                        # Check for suspicious names
                        suspicious_names = [
                            '.backdoor', '.shell', '.hack', '.pwn', '.rootkit',
                            '.miner', '.crypto', '.keylog', '.rat', '.bot'
                        ]
                        for sname in suspicious_names:
                            if sname in item.name.lower():
                                reasons.append(f"Suspicious name pattern: {sname}")
                                is_suspicious = True
                        
                        hidden_items.append({
                            "path": str(item),
                            "name": item.name,
                            "type": "directory" if item.is_dir() else "file",
                            "size": stat_info.st_size if item.is_file() else 0,
                            "modified": mtime.isoformat(),
                            "permissions": oct(stat_info.st_mode)[-3:],
                            "is_suspicious": is_suspicious,
                            "reasons": reasons
                        })
                        
                    except (PermissionError, OSError):
                        pass
                        
            except (PermissionError, OSError):
                pass
        
        self.hidden_files = hidden_items
        return hidden_items
    
    # =========================================================================
    # ROOTKIT DETECTION & REPAIR
    # =========================================================================
    
    def detect_rootkits(self) -> Dict:
        """Comprehensive rootkit detection"""
        findings = {
            "ld_preload_hijack": [],
            "hidden_processes": [],
            "hidden_modules": [],
            "syscall_hooks": [],
            "file_integrity": [],
            "network_hiding": [],
            "overall_status": "clean",
            "timestamp": datetime.now().isoformat()
        }
        
        system = platform.system()
        
        if system != "Linux":
            findings["note"] = "Full rootkit detection only available on Linux"
            return findings
        
        # Check LD_PRELOAD hijacking
        ld_preload_path = Path("/etc/ld.so.preload")
        if ld_preload_path.exists():
            try:
                content = ld_preload_path.read_text()
                if content.strip():
                    findings["ld_preload_hijack"].append({
                        "path": str(ld_preload_path),
                        "content": content,
                        "severity": "critical"
                    })
                    findings["overall_status"] = "infected"
            except PermissionError:
                findings["ld_preload_hijack"].append({
                    "error": "Cannot read /etc/ld.so.preload - check manually"
                })
        
        # Check for hidden processes (compare /proc with ps output)
        try:
            proc_pids = set()
            for entry in Path("/proc").iterdir():
                if entry.name.isdigit():
                    proc_pids.add(int(entry.name))
            
            psutil_pids = set(psutil.pids())
            
            # Hidden processes would be in /proc but not visible to psutil
            hidden = proc_pids - psutil_pids
            for pid in hidden:
                findings["hidden_processes"].append({
                    "pid": pid,
                    "severity": "critical"
                })
                findings["overall_status"] = "infected"
                
        except Exception as e:
            findings["hidden_processes"].append({"error": str(e)})
        
        # Check for suspicious kernel modules
        try:
            result = subprocess.run(["lsmod"], capture_output=True, text=True)
            suspicious_modules = []
            for line in result.stdout.split('\n')[1:]:
                if line:
                    module_name = line.split()[0].lower()
                    for indicator in ["rootkit", "hide", "stealth", "sniff"]:
                        if indicator in module_name:
                            suspicious_modules.append({
                                "name": module_name,
                                "reason": f"Suspicious name contains: {indicator}",
                                "severity": "high"
                            })
            
            findings["hidden_modules"] = suspicious_modules
            if suspicious_modules:
                findings["overall_status"] = "suspicious"
                
        except Exception as e:
            findings["hidden_modules"].append({"error": str(e)})
        
        # Check critical file integrity
        critical_files = [
            "/bin/ls", "/bin/ps", "/bin/netstat", "/bin/ss",
            "/usr/bin/top", "/usr/bin/lsof", "/usr/bin/find"
        ]
        
        for file_path in critical_files:
            path = Path(file_path)
            if path.exists():
                try:
                    stat_info = path.stat()
                    
                    # Check for unusual permissions
                    if stat_info.st_mode & 0o002:  # World-writable
                        findings["file_integrity"].append({
                            "path": file_path,
                            "issue": "World-writable critical binary",
                            "severity": "high"
                        })
                        findings["overall_status"] = "suspicious"
                        
                except Exception as e:
                    pass
        
        self.rootkit_findings = findings
        return findings
    
    def repair_rootkit_damage(self) -> Dict:
        """Attempt to repair rootkit damage"""
        repairs = {
            "actions_taken": [],
            "success": True,
            "timestamp": datetime.now().isoformat()
        }
        
        system = platform.system()
        if system != "Linux":
            repairs["note"] = "Repair only available on Linux"
            return repairs
        
        # Clear LD_PRELOAD hijack
        ld_preload_path = Path("/etc/ld.so.preload")
        if ld_preload_path.exists():
            try:
                content = ld_preload_path.read_text()
                if content.strip():
                    # Backup before clearing
                    backup_path = Path("/tmp/ld.so.preload.backup")
                    backup_path.write_text(content)
                    
                    # Clear the file
                    ld_preload_path.write_text("")
                    repairs["actions_taken"].append({
                        "action": "cleared_ld_preload",
                        "backup": str(backup_path),
                        "original_content": content
                    })
            except PermissionError:
                repairs["success"] = False
                repairs["actions_taken"].append({
                    "action": "clear_ld_preload",
                    "status": "failed",
                    "error": "Permission denied - run as root"
                })
        
        # Kill hidden/suspicious processes
        if self.rootkit_findings.get("hidden_processes"):
            for hidden in self.rootkit_findings["hidden_processes"]:
                if isinstance(hidden, dict) and "pid" in hidden:
                    try:
                        os.kill(hidden["pid"], 9)
                        repairs["actions_taken"].append({
                            "action": "killed_hidden_process",
                            "pid": hidden["pid"]
                        })
                    except ProcessLookupError:
                        pass
                    except PermissionError:
                        repairs["success"] = False
        
        return repairs
    
    # =========================================================================
    # COMPREHENSIVE SCAN FUNCTIONS
    # =========================================================================
    
    def full_system_scan(self) -> Dict:
        """Perform a comprehensive system security scan"""
        results = {
            "scan_id": hashlib.md5(datetime.now().isoformat().encode()).hexdigest()[:16],
            "start_time": datetime.now().isoformat(),
            "system_info": self._get_system_info(),
            "suspicious_processes": [],
            "suspicious_services": [],
            "pup_detections": [],
            "privilege_issues": [],
            "hidden_files": [],
            "rootkit_findings": {},
            "risk_score": 0,
            "summary": "",
            "end_time": None
        }
        
        try:
            # Run all scans
            results["suspicious_processes"] = self.detect_suspicious_processes()
            results["suspicious_services"] = self.detect_suspicious_services()
            results["pup_detections"] = self.scan_for_pups()
            results["privilege_issues"] = self.monitor_privilege_escalation()
            results["hidden_files"] = self.scan_hidden_files()
            results["rootkit_findings"] = self.detect_rootkits()
            
            # Calculate risk score
            risk_score = 0
            risk_score += len(results["suspicious_processes"]) * 10
            risk_score += len(results["suspicious_services"]) * 5
            risk_score += len(results["pup_detections"]) * 3
            risk_score += len(results["privilege_issues"]) * 8
            risk_score += len([f for f in results["hidden_files"] if f.get("is_suspicious")]) * 5
            
            if results["rootkit_findings"].get("overall_status") == "infected":
                risk_score += 50
            elif results["rootkit_findings"].get("overall_status") == "suspicious":
                risk_score += 25
            
            results["risk_score"] = min(100, risk_score)
            
            # Generate summary
            if results["risk_score"] >= 75:
                results["summary"] = "CRITICAL: Multiple severe security issues detected. Immediate action required."
            elif results["risk_score"] >= 50:
                results["summary"] = "HIGH: Significant security concerns found. Review and remediate."
            elif results["risk_score"] >= 25:
                results["summary"] = "MEDIUM: Some potential issues detected. Further investigation recommended."
            else:
                results["summary"] = "LOW: System appears relatively clean. Continue regular monitoring."
            
        except Exception as e:
            results["error"] = str(e)
        
        results["end_time"] = datetime.now().isoformat()
        return results
    
    def quick_scan(self) -> Dict:
        """Perform a quick security check"""
        results = {
            "scan_type": "quick",
            "start_time": datetime.now().isoformat(),
            "suspicious_processes": self.detect_suspicious_processes(),
            "rootkit_status": self.detect_rootkits().get("overall_status", "unknown"),
            "end_time": datetime.now().isoformat()
        }
        return results
    
    def _get_system_info(self) -> Dict:
        """Get current system information"""
        return {
            "hostname": platform.node(),
            "os": platform.system(),
            "os_version": platform.version(),
            "architecture": platform.machine(),
            "cpu_count": psutil.cpu_count(),
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory_total": psutil.virtual_memory().total,
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage('/').percent if platform.system() != 'Windows' else psutil.disk_usage('C:\\').percent,
            "boot_time": datetime.fromtimestamp(psutil.boot_time()).isoformat()
        }
    
    # =========================================================================
    # CONTROL METHODS
    # =========================================================================
    
    def start_all(self):
        """Start all monitoring threads"""
        self.running = True
        
        # Process monitor thread
        process_thread = threading.Thread(target=self.monitor_processes, daemon=True)
        process_thread.start()
        self.threads.append(process_thread)
        
        print("[+] Advanced Security Monitor started")
        return self.threads
    
    def stop_all(self):
        """Stop all monitoring threads"""
        self.running = False
        for thread in self.threads:
            thread.join(timeout=5)
        print("[*] Advanced Security Monitor stopped")
    
    def get_status(self) -> Dict:
        """Get current monitor status"""
        return {
            "running": self.running,
            "alerts_count": len(self.alerts),
            "killed_processes": len(self.killed_processes),
            "flagged_processes": len(self.flagged_processes),
            "pup_detections": len(self.pup_detections),
            "hidden_files": len(self.hidden_files),
            "rootkit_status": self.rootkit_findings.get("overall_status", "not_scanned"),
            "auto_kill_enabled": self.auto_kill_enabled
        }


# =============================================================================
# STANDALONE USAGE
# =============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Advanced Security Monitor')
    parser.add_argument('--scan', choices=['full', 'quick', 'processes', 'services', 'hidden', 'pup', 'rootkit'], 
                       help='Run a specific scan')
    parser.add_argument('--monitor', action='store_true', help='Start continuous monitoring')
    parser.add_argument('--auto-kill', action='store_true', help='Enable auto-kill for critical threats')
    parser.add_argument('--json', action='store_true', help='Output in JSON format')
    args = parser.parse_args()
    
    monitor = AdvancedSecurityMonitor({"auto_kill_enabled": args.auto_kill})
    
    if args.scan:
        if args.scan == 'full':
            result = monitor.full_system_scan()
        elif args.scan == 'quick':
            result = monitor.quick_scan()
        elif args.scan == 'processes':
            result = monitor.detect_suspicious_processes()
        elif args.scan == 'services':
            result = monitor.detect_suspicious_services()
        elif args.scan == 'hidden':
            result = monitor.scan_hidden_files()
        elif args.scan == 'pup':
            result = monitor.scan_for_pups()
        elif args.scan == 'rootkit':
            result = monitor.detect_rootkits()
        
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(json.dumps(result, indent=2))
    
    elif args.monitor:
        print("Starting Advanced Security Monitor...")
        print("Press Ctrl+C to stop")
        try:
            monitor.start_all()
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            monitor.stop_all()
    
    else:
        # Default: run quick scan
        result = monitor.quick_scan()
        print(json.dumps(result, indent=2))
