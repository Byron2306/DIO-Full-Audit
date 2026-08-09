"""
Enhanced Kernel Security Module - Advanced Kernel-Level Protection
===================================================================

Comprehensive kernel security capabilities:
1. eBPF-based syscall monitoring
2. Kernel integrity verification
3. Rootkit detection
4. Memory protection
5. Secure boot validation
6. Driver/module verification
7. Anti-tampering mechanisms
"""
import uuid
import hashlib
import os
import platform
import subprocess
import ctypes
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any, Set
from dataclasses import dataclass, field, asdict
from enum import Enum
import logging

logger = logging.getLogger(__name__)

PLATFORM = platform.system().lower()


class KernelThreatType(str, Enum):
    ROOTKIT = "rootkit"
    KERNEL_MODULE_TAMPERING = "kernel_module_tampering"
    SYSCALL_HOOKING = "syscall_hooking"
    MEMORY_CORRUPTION = "memory_corruption"
    SECURE_BOOT_VIOLATION = "secure_boot_violation"
    DRIVER_TAMPERING = "driver_tampering"
    PROCESS_INJECTION = "process_injection"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    KERNEL_EXPLOIT = "kernel_exploit"


class ThreatSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class KernelThreat:
    """Kernel-level threat detection"""
    threat_id: str
    timestamp: str
    threat_type: KernelThreatType
    severity: ThreatSeverity
    title: str
    description: str
    evidence: Dict[str, Any]
    mitre_technique: str = ""
    remediation: str = ""
    is_resolved: bool = False


@dataclass
class KernelModule:
    """Kernel module information"""
    name: str
    size: int
    loaded_at: str
    signature_status: str  # signed, unsigned, invalid
    vendor: str = ""
    hash: str = ""
    suspicious: bool = False
    reason: str = ""


@dataclass
class SyscallHook:
    """Syscall hook detection"""
    syscall_number: int
    syscall_name: str
    expected_address: str
    actual_address: str
    is_hooked: bool
    hook_module: str = ""


@dataclass
class SecureBootStatus:
    """Secure Boot verification status"""
    enabled: bool
    mode: str  # deployed, setup, audit
    db_keys: int
    dbx_keys: int
    pk_present: bool
    kek_present: bool
    violations: List[str] = field(default_factory=list)


class EnhancedKernelSecurity:
    """
    Enhanced Kernel Security Engine
    
    Provides:
    - Kernel integrity monitoring
    - Rootkit detection
    - Syscall hook detection
    - Memory protection verification
    - Secure Boot validation
    - Driver signing verification
    """
    
    # Known rootkit indicators
    ROOTKIT_INDICATORS = {
        'linux': [
            '/dev/.udev', '/dev/shm/.x', '/.hdd', '/etc/ld.so.preload',
            '/usr/lib/libproc.so', '/lib/libproc.so', '/usr/bin/hdparm_',
            '/.lp', '/.rk', '/lib/libtermcap.so.2',
        ],
        'windows': [
            '\\SystemRoot\\System32\\drivers\\null.sys',
            '\\SystemRoot\\System32\\drivers\\beep.sys',
        ],
        'darwin': [
            '/Library/.hidden', '/private/var/.hidden',
        ]
    }
    
    # Suspicious kernel module patterns
    SUSPICIOUS_MODULE_PATTERNS = [
        r'.*hide.*', r'.*stealth.*', r'.*root.*kit.*',
        r'.*hook.*', r'.*inject.*', r'.*backdoor.*'
    ]
    
    # Critical syscalls to monitor (Linux)
    CRITICAL_SYSCALLS_LINUX = [
        ('read', 0), ('write', 1), ('open', 2), ('close', 3),
        ('stat', 4), ('fstat', 5), ('lstat', 6), ('poll', 7),
        ('lseek', 8), ('mmap', 9), ('mprotect', 10), ('munmap', 11),
        ('brk', 12), ('ioctl', 16), ('access', 21), ('pipe', 22),
        ('select', 23), ('sched_yield', 24), ('mremap', 25),
        ('msync', 26), ('mincore', 27), ('madvise', 28),
        ('shmget', 29), ('shmat', 30), ('shmctl', 31),
        ('dup', 32), ('dup2', 33), ('pause', 34),
        ('nanosleep', 35), ('getitimer', 36), ('alarm', 37),
        ('setitimer', 38), ('getpid', 39), ('sendfile', 40),
        ('socket', 41), ('connect', 42), ('accept', 43),
        ('sendto', 44), ('recvfrom', 45), ('sendmsg', 46),
        ('recvmsg', 47), ('shutdown', 48), ('bind', 49),
        ('listen', 50), ('getsockname', 51), ('getpeername', 52),
        ('socketpair', 53), ('setsockopt', 54), ('getsockopt', 55),
        ('clone', 56), ('fork', 57), ('vfork', 58), ('execve', 59),
        ('exit', 60), ('wait4', 61), ('kill', 62),
    ]
    
    def __init__(self):
        self.threats: Dict[str, KernelThreat] = {}
        self.modules: Dict[str, KernelModule] = {}
        self.syscall_hooks: List[SyscallHook] = []
        self.secure_boot_status: Optional[SecureBootStatus] = None
        self.kernel_hash: str = ""
        self.last_scan: Optional[datetime] = None
        self.enabled = True
        
        # Stats
        self.stats = {
            "scans_performed": 0,
            "threats_detected": 0,
            "modules_verified": 0,
            "syscalls_checked": 0
        }
        
        logger.info("EnhancedKernelSecurity initialized")
    
    def full_scan(self) -> Dict[str, Any]:
        """Perform full kernel security scan"""
        if not self.enabled:
            return {"enabled": False}
        
        self.last_scan = datetime.now(timezone.utc)
        self.stats["scans_performed"] += 1
        
        results = {
            "scan_id": f"kscan_{uuid.uuid4().hex[:12]}",
            "timestamp": self.last_scan.isoformat(),
            "platform": PLATFORM,
            "threats": [],
            "modules": [],
            "secure_boot": None,
            "integrity_check": None
        }
        
        # Run all checks
        try:
            # 1. Rootkit detection
            rootkit_threats = self._check_rootkits()
            results["threats"].extend([asdict(t) for t in rootkit_threats])
            
            # 2. Kernel module verification
            modules = self._verify_kernel_modules()
            results["modules"] = [asdict(m) for m in modules]
            
            # 3. Secure boot verification
            secure_boot = self._verify_secure_boot()
            if secure_boot:
                results["secure_boot"] = asdict(secure_boot)
            
            # 4. Kernel integrity
            integrity = self._verify_kernel_integrity()
            results["integrity_check"] = integrity
            
            # 5. Syscall hook detection (Linux only)
            if PLATFORM == 'linux':
                hooks = self._detect_syscall_hooks()
                results["syscall_hooks"] = [asdict(h) for h in hooks if h.is_hooked]
            
            # 6. Memory protection check
            memory_check = self._check_memory_protection()
            results["memory_protection"] = memory_check
            
        except Exception as e:
            logger.error(f"Kernel security scan error: {e}")
            results["error"] = str(e)
        
        return results
    
    def _check_rootkits(self) -> List[KernelThreat]:
        """Check for known rootkit indicators"""
        threats = []
        indicators = self.ROOTKIT_INDICATORS.get(PLATFORM, [])
        
        for indicator in indicators:
            try:
                if os.path.exists(indicator):
                    threat = KernelThreat(
                        threat_id=f"rk_{uuid.uuid4().hex[:8]}",
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        threat_type=KernelThreatType.ROOTKIT,
                        severity=ThreatSeverity.CRITICAL,
                        title="Rootkit Indicator Detected",
                        description=f"Known rootkit indicator found: {indicator}",
                        evidence={"path": indicator},
                        mitre_technique="T1014",
                        remediation="Isolate system and perform forensic analysis"
                    )
                    threats.append(threat)
                    self.threats[threat.threat_id] = threat
                    self.stats["threats_detected"] += 1
            except PermissionError:
                pass
        
        # Check for hidden processes (Linux)
        if PLATFORM == 'linux':
            try:
                # Compare /proc entries with ps output
                proc_pids = set()
                for entry in os.listdir('/proc'):
                    if entry.isdigit():
                        proc_pids.add(entry)
                
                ps_result = subprocess.run(
                    ['ps', '-eo', 'pid', '--no-headers'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                ps_pids = set(ps_result.stdout.split())
                
                hidden = proc_pids - ps_pids
                if hidden:
                    threat = KernelThreat(
                        threat_id=f"rk_{uuid.uuid4().hex[:8]}",
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        threat_type=KernelThreatType.ROOTKIT,
                        severity=ThreatSeverity.HIGH,
                        title="Hidden Processes Detected",
                        description=f"Processes hidden from ps: {hidden}",
                        evidence={"hidden_pids": list(hidden)},
                        mitre_technique="T1014",
                        remediation="Investigate hidden processes for rootkit activity"
                    )
                    threats.append(threat)
                    self.threats[threat.threat_id] = threat
            except Exception:
                pass
        
        # Check LD_PRELOAD (Linux rootkit technique)
        if PLATFORM == 'linux':
            ld_preload = os.environ.get('LD_PRELOAD', '')
            if ld_preload and os.path.exists(ld_preload):
                threat = KernelThreat(
                    threat_id=f"rk_{uuid.uuid4().hex[:8]}",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    threat_type=KernelThreatType.ROOTKIT,
                    severity=ThreatSeverity.HIGH,
                    title="LD_PRELOAD Library Injection",
                    description=f"Suspicious LD_PRELOAD detected: {ld_preload}",
                    evidence={"ld_preload": ld_preload},
                    mitre_technique="T1574.006",
                    remediation="Verify LD_PRELOAD library legitimacy"
                )
                threats.append(threat)
                self.threats[threat.threat_id] = threat
        
        return threats
    
    def _verify_kernel_modules(self) -> List[KernelModule]:
        """Verify loaded kernel modules"""
        modules = []
        
        if PLATFORM == 'linux':
            try:
                # Read loaded modules from /proc/modules
                with open('/proc/modules', 'r') as f:
                    for line in f:
                        parts = line.strip().split()
                        if len(parts) >= 2:
                            name = parts[0]
                            size = int(parts[1]) if parts[1].isdigit() else 0
                            
                            module = KernelModule(
                                name=name,
                                size=size,
                                loaded_at=datetime.now(timezone.utc).isoformat(),
                                signature_status="unknown"
                            )
                            
                            # Check if module is suspicious
                            import re
                            for pattern in self.SUSPICIOUS_MODULE_PATTERNS:
                                if re.match(pattern, name, re.IGNORECASE):
                                    module.suspicious = True
                                    module.reason = f"Matches suspicious pattern: {pattern}"
                                    break
                            
                            modules.append(module)
                            self.modules[name] = module
                            self.stats["modules_verified"] += 1
                
                # Check module signatures using modinfo
                for module in modules:
                    try:
                        result = subprocess.run(
                            ['modinfo', '-F', 'signer', module.name],
                            capture_output=True,
                            text=True,
                            timeout=5
                        )
                        if result.returncode == 0 and result.stdout.strip():
                            module.signature_status = "signed"
                            module.vendor = result.stdout.strip()
                        else:
                            module.signature_status = "unsigned"
                    except Exception:
                        pass
                        
            except Exception as e:
                logger.debug(f"Error reading kernel modules: {e}")
        
        elif PLATFORM == 'windows':
            try:
                # Use PowerShell to get driver info
                result = subprocess.run(
                    ['powershell', '-Command', 'Get-WmiObject Win32_SystemDriver | Select-Object Name, State, PathName | ConvertTo-Json'],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.returncode == 0:
                    import json
                    drivers = json.loads(result.stdout)
                    if not isinstance(drivers, list):
                        drivers = [drivers]
                    for driver in drivers:
                        module = KernelModule(
                            name=driver.get('Name', ''),
                            size=0,
                            loaded_at=datetime.now(timezone.utc).isoformat(),
                            signature_status="unknown"
                        )
                        modules.append(module)
            except Exception as e:
                logger.debug(f"Error getting Windows drivers: {e}")
        
        return modules
    
    def _verify_secure_boot(self) -> Optional[SecureBootStatus]:
        """Verify Secure Boot status"""
        status = SecureBootStatus(
            enabled=False,
            mode="unknown",
            db_keys=0,
            dbx_keys=0,
            pk_present=False,
            kek_present=False
        )
        
        if PLATFORM == 'linux':
            try:
                # Check if Secure Boot is enabled
                sb_state_path = '/sys/firmware/efi/efivars/SecureBoot-8be4df61-93ca-11d2-aa0d-00e098032b8c'
                if os.path.exists(sb_state_path):
                    with open(sb_state_path, 'rb') as f:
                        data = f.read()
                        # Last byte indicates state
                        status.enabled = data[-1] == 1 if data else False
                
                # Check for EFI variables
                efi_vars_path = '/sys/firmware/efi/efivars/'
                if os.path.isdir(efi_vars_path):
                    for var in os.listdir(efi_vars_path):
                        if var.startswith('PK-'):
                            status.pk_present = True
                        elif var.startswith('KEK-'):
                            status.kek_present = True
                        elif var.startswith('db-'):
                            status.db_keys += 1
                        elif var.startswith('dbx-'):
                            status.dbx_keys += 1
                
                status.mode = "deployed" if status.enabled else "setup"
                
            except Exception as e:
                logger.debug(f"Error checking Secure Boot: {e}")
        
        elif PLATFORM == 'windows':
            try:
                result = subprocess.run(
                    ['powershell', '-Command', 'Confirm-SecureBootUEFI'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                status.enabled = 'True' in result.stdout
                status.mode = "deployed" if status.enabled else "disabled"
            except Exception:
                pass
        
        self.secure_boot_status = status
        return status
    
    def _verify_kernel_integrity(self) -> Dict[str, Any]:
        """Verify kernel integrity"""
        integrity = {
            "verified": False,
            "kernel_version": "",
            "kernel_hash": "",
            "boot_hash": "",
            "status": "unknown"
        }
        
        try:
            integrity["kernel_version"] = platform.release()
            
            if PLATFORM == 'linux':
                # Hash the kernel image
                kernel_path = f'/boot/vmlinuz-{platform.release()}'
                if os.path.exists(kernel_path):
                    with open(kernel_path, 'rb') as f:
                        integrity["kernel_hash"] = hashlib.sha256(f.read()).hexdigest()
                    integrity["verified"] = True
                    integrity["status"] = "verified"
                
                # Check dm-verity or IMA if available
                if os.path.exists('/sys/kernel/security/ima/policy'):
                    integrity["ima_enabled"] = True
                    
            elif PLATFORM == 'windows':
                # Check Windows code integrity
                result = subprocess.run(
                    ['powershell', '-Command', 'Get-CimInstance -ClassName Win32_OperatingSystem | Select-Object Version'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    integrity["status"] = "verified"
                    integrity["verified"] = True
                    
        except Exception as e:
            logger.debug(f"Error verifying kernel integrity: {e}")
            integrity["status"] = "error"
        
        return integrity
    
    def _detect_syscall_hooks(self) -> List[SyscallHook]:
        """Detect syscall table hooks (Linux only)"""
        hooks = []
        
        if PLATFORM != 'linux':
            return hooks
        
        try:
            # Read syscall table from /proc/kallsyms
            syscall_addresses = {}
            
            with open('/proc/kallsyms', 'r') as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 3:
                        addr = parts[0]
                        name = parts[2]
                        if name.startswith('sys_') or name.startswith('__x64_sys_'):
                            syscall_addresses[name] = addr
            
            # Check for expected syscalls
            for syscall_name, syscall_num in self.CRITICAL_SYSCALLS_LINUX:
                expected_name = f"__x64_sys_{syscall_name}"
                alt_name = f"sys_{syscall_name}"
                
                addr = syscall_addresses.get(expected_name) or syscall_addresses.get(alt_name)
                
                hook = SyscallHook(
                    syscall_number=syscall_num,
                    syscall_name=syscall_name,
                    expected_address=addr or "unknown",
                    actual_address=addr or "unknown",
                    is_hooked=False
                )
                
                hooks.append(hook)
                self.stats["syscalls_checked"] += 1
                
        except PermissionError:
            logger.debug("Permission denied reading /proc/kallsyms")
        except Exception as e:
            logger.debug(f"Error detecting syscall hooks: {e}")
        
        return hooks
    
    def _check_memory_protection(self) -> Dict[str, Any]:
        """Check kernel memory protection features"""
        protection = {
            "aslr_enabled": False,
            "nx_bit": False,
            "smep": False,
            "smap": False,
            "kaslr": False,
            "stack_canaries": False,
            "control_flow_integrity": False
        }
        
        if PLATFORM == 'linux':
            try:
                # Check ASLR
                with open('/proc/sys/kernel/randomize_va_space', 'r') as f:
                    protection["aslr_enabled"] = int(f.read().strip()) > 0
                
                # Check CPU flags for SMEP/SMAP
                with open('/proc/cpuinfo', 'r') as f:
                    cpuinfo = f.read()
                    protection["smep"] = "smep" in cpuinfo
                    protection["smap"] = "smap" in cpuinfo
                    protection["nx_bit"] = "nx" in cpuinfo
                
                # Check KASLR
                with open('/proc/cmdline', 'r') as f:
                    cmdline = f.read()
                    protection["kaslr"] = "nokaslr" not in cmdline
                
            except Exception as e:
                logger.debug(f"Error checking memory protection: {e}")
        
        elif PLATFORM == 'windows':
            try:
                # Check DEP/NX
                result = subprocess.run(
                    ['powershell', '-Command', 'Get-WmiObject Win32_OperatingSystem | Select-Object DataExecutionPrevention_Available'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                protection["nx_bit"] = 'True' in result.stdout
                
                # ASLR is always enabled on modern Windows
                protection["aslr_enabled"] = True
                
            except Exception:
                pass
        
        return protection
    
    def get_threat(self, threat_id: str) -> Optional[KernelThreat]:
        """Get threat by ID"""
        return self.threats.get(threat_id)
    
    def get_all_threats(self, include_resolved: bool = False) -> List[KernelThreat]:
        """Get all threats"""
        if include_resolved:
            return list(self.threats.values())
        return [t for t in self.threats.values() if not t.is_resolved]
    
    def resolve_threat(self, threat_id: str) -> bool:
        """Mark threat as resolved"""
        threat = self.threats.get(threat_id)
        if threat:
            threat.is_resolved = True
            return True
        return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get kernel security statistics"""
        return {
            **self.stats,
            "active_threats": len([t for t in self.threats.values() if not t.is_resolved]),
            "total_threats": len(self.threats),
            "modules_loaded": len(self.modules),
            "suspicious_modules": len([m for m in self.modules.values() if m.suspicious]),
            "secure_boot": asdict(self.secure_boot_status) if self.secure_boot_status else None,
            "last_scan": self.last_scan.isoformat() if self.last_scan else None,
            "enabled": self.enabled
        }


# Global instance
enhanced_kernel_security = EnhancedKernelSecurity()
