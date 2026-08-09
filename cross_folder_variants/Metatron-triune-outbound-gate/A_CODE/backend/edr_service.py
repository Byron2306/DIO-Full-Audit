"""
Memory Forensics & EDR Service
===============================
Advanced endpoint detection and response capabilities:

1. Memory Forensics (Volatility 3 integration)
   - Process memory analysis
   - Malware detection in memory
   - Rootkit detection
   - Credential extraction detection

2. EDR Capabilities
   - Process tree visualization
   - File Integrity Monitoring (FIM)
   - USB device control
   - Application whitelisting
   - Real-time telemetry
"""

import os
import json
import asyncio
import subprocess
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field, asdict
from pathlib import Path
from enum import Enum
import platform
from runtime_paths import ensure_data_dir

logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================

FORENSICS_DIR = ensure_data_dir("forensics")

FIM_BASELINE_FILE = FORENSICS_DIR / "fim_baseline.json"
USB_POLICY_FILE = FORENSICS_DIR / "usb_policy.json"
APP_WHITELIST_FILE = FORENSICS_DIR / "app_whitelist.json"

class EDRConfig:
    def __init__(self):
        self.fim_enabled = os.environ.get("FIM_ENABLED", "true").lower() == "true"
        self.usb_control_enabled = os.environ.get("USB_CONTROL", "false").lower() == "true"
        self.app_whitelist_enabled = os.environ.get("APP_WHITELIST", "false").lower() == "true"
        self.volatility_path = os.environ.get("VOLATILITY_PATH", "vol3")
        self.telemetry_interval = int(os.environ.get("TELEMETRY_INTERVAL", "60"))

config = EDRConfig()

# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass
class ProcessInfo:
    """Detailed process information"""
    pid: int
    ppid: int
    name: str
    cmdline: str
    exe_path: Optional[str]
    username: str
    create_time: str
    cpu_percent: float
    memory_percent: float
    status: str
    children: List[int] = field(default_factory=list)
    connections: int = 0
    open_files: int = 0
    threads: int = 0
    is_suspicious: bool = False
    suspicion_reasons: List[str] = field(default_factory=list)

@dataclass
class ProcessTreeNode:
    """Node in process tree"""
    process: ProcessInfo
    children: List['ProcessTreeNode'] = field(default_factory=list)

@dataclass
class FileIntegrityEvent:
    """File integrity monitoring event"""
    event_id: str
    timestamp: str
    event_type: str  # created, modified, deleted, permission_change
    file_path: str
    file_hash: Optional[str]
    previous_hash: Optional[str]
    file_size: int
    permissions: str
    owner: str
    severity: str

@dataclass
class USBDevice:
    """USB device information"""
    device_id: str
    vendor_id: str
    product_id: str
    vendor_name: str
    product_name: str
    serial_number: Optional[str]
    device_type: str
    connected_at: str
    status: str  # allowed, blocked, unknown

@dataclass
class MemoryAnalysisResult:
    """Result of memory forensics analysis"""
    analysis_id: str
    timestamp: str
    analysis_type: str
    status: str
    findings: List[Dict] = field(default_factory=list)
    suspicious_processes: List[Dict] = field(default_factory=list)
    injected_code: List[Dict] = field(default_factory=list)
    hidden_processes: List[Dict] = field(default_factory=list)
    network_connections: List[Dict] = field(default_factory=list)
    credentials_found: bool = False
    rootkit_indicators: List[str] = field(default_factory=list)

@dataclass
class EDRTelemetry:
    """EDR telemetry data"""
    timestamp: str
    hostname: str
    os_info: Dict[str, str]
    process_count: int
    network_connections: int
    open_files: int
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    suspicious_activity: List[Dict] = field(default_factory=list)
    fim_events: int = 0
    blocked_usb: int = 0

# =============================================================================
# PROCESS TREE BUILDER
# =============================================================================

class ProcessTreeBuilder:
    """
    Builds and analyzes process trees for threat detection.
    """
    
    def __init__(self):
        self._db = None
    
    def set_database(self, db):
        self._db = db
    
    async def build_process_tree(self) -> List[ProcessTreeNode]:
        """Build complete process tree"""
        try:
            import psutil
        except ImportError:
            logger.error("psutil not available")
            return []
        
        processes: Dict[int, ProcessInfo] = {}
        
        # Collect all process info
        for proc in psutil.process_iter([
            'pid', 'ppid', 'name', 'cmdline', 'exe', 'username',
            'create_time', 'cpu_percent', 'memory_percent', 'status',
            'num_threads'
        ]):
            try:
                info = proc.info
                
                # Check for suspicious patterns
                is_suspicious, reasons = self._check_suspicious(info)
                
                # Get connections and open files safely
                try:
                    conn_count = len(proc.connections())
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    conn_count = 0
                
                try:
                    files_count = len(proc.open_files())
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    files_count = 0
                
                processes[info['pid']] = ProcessInfo(
                    pid=info['pid'],
                    ppid=info['ppid'] or 0,
                    name=info['name'] or 'unknown',
                    cmdline=' '.join(info.get('cmdline') or [])[:200],
                    exe_path=info.get('exe'),
                    username=info.get('username') or 'unknown',
                    create_time=datetime.fromtimestamp(info.get('create_time', 0)).isoformat(),
                    cpu_percent=info.get('cpu_percent', 0) or 0,
                    memory_percent=info.get('memory_percent', 0) or 0,
                    status=info.get('status', 'unknown'),
                    threads=info.get('num_threads', 0) or 0,
                    connections=conn_count,
                    open_files=files_count,
                    is_suspicious=is_suspicious,
                    suspicion_reasons=reasons
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        # Build parent-child relationships
        for pid, proc in processes.items():
            if proc.ppid in processes:
                processes[proc.ppid].children.append(pid)
        
        # Build tree starting from root processes (ppid=0 or ppid=1)
        roots = []
        for pid, proc in processes.items():
            if proc.ppid == 0 or proc.ppid not in processes:
                roots.append(self._build_tree_node(proc, processes))
        
        return roots
    
    def _build_tree_node(self, process: ProcessInfo, all_processes: Dict[int, ProcessInfo]) -> ProcessTreeNode:
        """Recursively build tree node"""
        node = ProcessTreeNode(process=process)
        
        for child_pid in process.children:
            if child_pid in all_processes:
                child_node = self._build_tree_node(all_processes[child_pid], all_processes)
                node.children.append(child_node)
        
        return node
    
    def _check_suspicious(self, info: Dict) -> tuple:
        """Check if process is suspicious"""
        reasons = []
        
        name = (info.get('name') or '').lower()
        cmdline = ' '.join(info.get('cmdline') or []).lower()
        exe = (info.get('exe') or '').lower()
        
        # Suspicious process names
        suspicious_names = [
            'mimikatz', 'lazagne', 'procdump', 'pwdump', 'secretsdump',
            'xmrig', 'minerd', 'cgminer', 'nc', 'ncat', 'netcat'
        ]
        for sname in suspicious_names:
            if sname in name or sname in cmdline:
                reasons.append(f"Suspicious name: {sname}")
        
        # Suspicious command patterns
        suspicious_patterns = [
            'base64 -d', 'curl | bash', 'wget | sh', 'powershell -enc',
            '/dev/tcp/', 'nc -e', 'bash -i', 'reverse shell'
        ]
        for pattern in suspicious_patterns:
            if pattern in cmdline:
                reasons.append(f"Suspicious pattern: {pattern}")
        
        # Process running from suspicious location
        suspicious_paths = ['/tmp/', '/dev/shm/', '/var/tmp/', 'appdata/local/temp']
        for path in suspicious_paths:
            if exe and path in exe:
                reasons.append(f"Running from suspicious location: {path}")
        
        return len(reasons) > 0, reasons
    
    def tree_to_dict(self, node: ProcessTreeNode) -> Dict:
        """Convert tree node to dictionary"""
        return {
            "process": asdict(node.process),
            "children": [self.tree_to_dict(child) for child in node.children]
        }


# =============================================================================
# FILE INTEGRITY MONITORING
# =============================================================================

class FileIntegrityMonitor:
    """
    Monitors critical files for unauthorized changes.
    """
    
    DEFAULT_MONITORED_PATHS = [
        "/etc/passwd",
        "/etc/shadow",
        "/etc/sudoers",
        "/etc/ssh/sshd_config",
        "/etc/hosts",
        "/etc/crontab",
        "/root/.ssh/authorized_keys",
        "/etc/systemd/system/",
    ]
    
    def __init__(self):
        self.baseline: Dict[str, Dict] = {}
        self.events: List[FileIntegrityEvent] = []
        self.monitored_paths: List[str] = self.DEFAULT_MONITORED_PATHS.copy()
        self._db = None
        self._load_baseline()
    
    def set_database(self, db):
        self._db = db
    
    def _load_baseline(self):
        """Load baseline from file"""
        if FIM_BASELINE_FILE.exists():
            try:
                with open(FIM_BASELINE_FILE, 'r') as f:
                    data = json.load(f)
                    self.baseline = data.get("baseline", {})
                    self.monitored_paths = data.get("monitored_paths", self.DEFAULT_MONITORED_PATHS)
                logger.info(f"Loaded FIM baseline with {len(self.baseline)} files")
            except Exception as e:
                logger.error(f"Failed to load FIM baseline: {e}")
    
    def _save_baseline(self):
        """Save baseline to file"""
        try:
            data = {
                "baseline": self.baseline,
                "monitored_paths": self.monitored_paths,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            with open(FIM_BASELINE_FILE, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save FIM baseline: {e}")
    
    def _hash_file(self, path: str) -> Optional[str]:
        """Calculate SHA256 hash of file"""
        try:
            sha256 = hashlib.sha256()
            with open(path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    sha256.update(chunk)
            return sha256.hexdigest()
        except Exception:
            return None
    
    def _get_file_info(self, path: str) -> Optional[Dict]:
        """Get file metadata"""
        try:
            stat = os.stat(path)
            return {
                "size": stat.st_size,
                "permissions": oct(stat.st_mode)[-3:],
                "owner_uid": stat.st_uid,
                "mtime": stat.st_mtime,
                "hash": self._hash_file(path)
            }
        except Exception:
            return None
    
    async def create_baseline(self) -> Dict[str, Any]:
        """Create initial baseline of monitored files"""
        self.baseline = {}
        files_processed = 0
        
        for path in self.monitored_paths:
            path_obj = Path(path)
            
            if path_obj.is_file():
                info = self._get_file_info(path)
                if info:
                    self.baseline[path] = info
                    files_processed += 1
            elif path_obj.is_dir():
                for file_path in path_obj.rglob("*"):
                    if file_path.is_file():
                        info = self._get_file_info(str(file_path))
                        if info:
                            self.baseline[str(file_path)] = info
                            files_processed += 1
        
        self._save_baseline()
        
        return {
            "files_baselined": files_processed,
            "paths_monitored": len(self.monitored_paths),
            "created_at": datetime.now(timezone.utc).isoformat()
        }
    
    async def check_integrity(self) -> List[FileIntegrityEvent]:
        """Check files against baseline"""
        events = []
        
        for path, baseline_info in self.baseline.items():
            current_info = self._get_file_info(path)
            
            if current_info is None:
                # File was deleted
                event = FileIntegrityEvent(
                    event_id=hashlib.md5(f"{path}-deleted-{datetime.now().isoformat()}".encode()).hexdigest()[:16],
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    event_type="deleted",
                    file_path=path,
                    file_hash=None,
                    previous_hash=baseline_info.get("hash"),
                    file_size=0,
                    permissions="",
                    owner="",
                    severity="high"
                )
                events.append(event)
            elif current_info.get("hash") != baseline_info.get("hash"):
                # File was modified
                event = FileIntegrityEvent(
                    event_id=hashlib.md5(f"{path}-modified-{datetime.now().isoformat()}".encode()).hexdigest()[:16],
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    event_type="modified",
                    file_path=path,
                    file_hash=current_info.get("hash"),
                    previous_hash=baseline_info.get("hash"),
                    file_size=current_info.get("size", 0),
                    permissions=current_info.get("permissions", ""),
                    owner=str(current_info.get("owner_uid", "")),
                    severity="critical" if "/etc/" in path else "high"
                )
                events.append(event)
            elif current_info.get("permissions") != baseline_info.get("permissions"):
                # Permissions changed
                event = FileIntegrityEvent(
                    event_id=hashlib.md5(f"{path}-perms-{datetime.now().isoformat()}".encode()).hexdigest()[:16],
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    event_type="permission_change",
                    file_path=path,
                    file_hash=current_info.get("hash"),
                    previous_hash=baseline_info.get("hash"),
                    file_size=current_info.get("size", 0),
                    permissions=current_info.get("permissions", ""),
                    owner=str(current_info.get("owner_uid", "")),
                    severity="medium"
                )
                events.append(event)
        
        self.events.extend(events)
        
        # Store events in database
        if self._db is not None and events:
            await self._db.fim_events.insert_many([asdict(e) for e in events])
        
        return events
    
    def add_monitored_path(self, path: str):
        """Add a path to monitor"""
        if path not in self.monitored_paths:
            self.monitored_paths.append(path)
            self._save_baseline()
    
    def get_status(self) -> Dict[str, Any]:
        """Get FIM status"""
        return {
            "enabled": config.fim_enabled,
            "monitored_paths": len(self.monitored_paths),
            "baselined_files": len(self.baseline),
            "recent_events": len(self.events),
            "paths": self.monitored_paths[:10]
        }


# =============================================================================
# USB DEVICE CONTROL
# =============================================================================

class USBDeviceController:
    """
    Monitors and controls USB device connections.
    """
    
    def __init__(self):
        self.allowed_devices: Set[str] = set()
        self.blocked_devices: Set[str] = set()
        self.connected_devices: List[USBDevice] = []
        self.events: List[Dict] = []
        self._load_policy()
    
    def _load_policy(self):
        """Load USB policy"""
        if USB_POLICY_FILE.exists():
            try:
                with open(USB_POLICY_FILE, 'r') as f:
                    data = json.load(f)
                    self.allowed_devices = set(data.get("allowed", []))
                    self.blocked_devices = set(data.get("blocked", []))
            except Exception as e:
                logger.error(f"Failed to load USB policy: {e}")
    
    def _save_policy(self):
        """Save USB policy"""
        try:
            data = {
                "allowed": list(self.allowed_devices),
                "blocked": list(self.blocked_devices)
            }
            with open(USB_POLICY_FILE, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save USB policy: {e}")
    
    async def scan_devices(self) -> List[USBDevice]:
        """Scan for connected USB devices"""
        devices = []
        
        if platform.system() == "Linux":
            try:
                # Use lsusb
                result = await asyncio.create_subprocess_exec(
                    "lsusb",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, _ = await result.communicate()
                
                for line in stdout.decode().split('\n'):
                    if line.strip():
                        # Parse: Bus 001 Device 002: ID 8087:0024 Intel Corp.
                        parts = line.split()
                        if len(parts) >= 6:
                            device_id = f"{parts[1]}-{parts[3].rstrip(':')}"
                            id_parts = parts[5].split(':')
                            vendor_id = id_parts[0] if len(id_parts) > 0 else ""
                            product_id = id_parts[1] if len(id_parts) > 1 else ""
                            
                            # Determine status
                            full_id = f"{vendor_id}:{product_id}"
                            if full_id in self.allowed_devices:
                                status = "allowed"
                            elif full_id in self.blocked_devices:
                                status = "blocked"
                            else:
                                status = "unknown"
                            
                            devices.append(USBDevice(
                                device_id=device_id,
                                vendor_id=vendor_id,
                                product_id=product_id,
                                vendor_name=' '.join(parts[6:]) if len(parts) > 6 else "Unknown",
                                product_name="",
                                serial_number=None,
                                device_type="usb",
                                connected_at=datetime.now(timezone.utc).isoformat(),
                                status=status
                            ))
            except Exception as e:
                logger.error(f"USB scan failed: {e}")
        
        self.connected_devices = devices
        return devices
    
    def allow_device(self, vendor_id: str, product_id: str):
        """Add device to allowed list"""
        device_id = f"{vendor_id}:{product_id}"
        self.allowed_devices.add(device_id)
        self.blocked_devices.discard(device_id)
        self._save_policy()
    
    def block_device(self, vendor_id: str, product_id: str):
        """Add device to blocked list"""
        device_id = f"{vendor_id}:{product_id}"
        self.blocked_devices.add(device_id)
        self.allowed_devices.discard(device_id)
        self._save_policy()
    
    def get_status(self) -> Dict[str, Any]:
        """Get USB control status"""
        return {
            "enabled": config.usb_control_enabled,
            "allowed_devices": len(self.allowed_devices),
            "blocked_devices": len(self.blocked_devices),
            "connected_devices": len(self.connected_devices)
        }


# =============================================================================
# MEMORY FORENSICS (Volatility Integration)
# =============================================================================

class MemoryForensics:
    """
    Memory forensics analysis using Volatility 3.
    """
    
    def __init__(self):
        self.use_module_fallback = False
        self.volatility_path = self._find_volatility()
        self._db = None
    
    def set_database(self, db):
        self._db = db
    
    def _find_volatility(self) -> Optional[str]:
        """Find Volatility 3 installation"""
        import shutil
        
        # Try the 'vol' command first (installed via pip)
        paths = ["vol", "vol3", "volatility3", "vol.py", "/usr/local/bin/vol3", "/usr/local/bin/vol", "/root/.venv/bin/vol"]
        
        for path in paths:
            # Try which command first
            full_path = shutil.which(path)
            if full_path:
                try:
                    result = subprocess.run([full_path, "-h"], capture_output=True, timeout=10)
                    output = (result.stdout or b"") + (result.stderr or b"")
                    if result.returncode == 0 and b"volatility" in output.lower():
                        logger.info(f"Found Volatility 3 at: {full_path}")
                        return full_path
                except Exception as e:
                    logger.debug(f"Error checking {full_path}: {e}")
                    continue
            
            # Also try the path directly
            try:
                result = subprocess.run([path, "-h"], capture_output=True, timeout=10)
                output = (result.stdout or b"") + (result.stderr or b"")
                if result.returncode == 0 and b"volatility" in output.lower():
                    logger.info(f"Found Volatility 3 at: {path}")
                    return path
            except Exception:
                continue

        # Fallback: module invocation if command entrypoint is missing
        try:
            import importlib
            import sys
            importlib.import_module("volatility3")
            self.use_module_fallback = True
            logger.info("Using Volatility 3 via python -m volatility3")
            return sys.executable
        except Exception:
            pass
        
        logger.warning("Volatility 3 not found - install with: pip install volatility3")
        return None
    
    async def analyze_memory_dump(self, dump_path: str) -> MemoryAnalysisResult:
        """Analyze a memory dump file"""
        analysis_id = hashlib.md5(f"{dump_path}-{datetime.now().isoformat()}".encode()).hexdigest()[:16]
        
        result = MemoryAnalysisResult(
            analysis_id=analysis_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            analysis_type="full",
            status="completed" if self.volatility_path else "volatility_not_installed"
        )
        
        if not self.volatility_path:
            result.findings.append({
                "type": "error",
                "message": "Volatility 3 not installed. Install with: pip install volatility3"
            })
            return result
        
        if not Path(dump_path).exists():
            result.status = "error"
            result.findings.append({"type": "error", "message": "Memory dump file not found"})
            return result
        
        try:
            # Run various Volatility plugins
            plugins = [
                ("windows.pslist", "process_list"),
                ("windows.pstree", "process_tree"),
                ("windows.malfind", "injected_code"),
                ("windows.netscan", "network_connections"),
                ("windows.cmdline", "command_lines"),
            ]
            
            for plugin, finding_type in plugins:
                try:
                    command = [self.volatility_path]
                    if self.use_module_fallback:
                        command.extend(["-m", "volatility3"])
                    command.extend(["-f", dump_path, plugin])

                    proc = await asyncio.create_subprocess_exec(
                        *command,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)
                    
                    if stdout:
                        result.findings.append({
                            "type": finding_type,
                            "plugin": plugin,
                            "output": stdout.decode()[:5000]  # Limit output size
                        })
                except asyncio.TimeoutError:
                    result.findings.append({
                        "type": finding_type,
                        "plugin": plugin,
                        "error": "Analysis timed out"
                    })
                except Exception as e:
                    result.findings.append({
                        "type": finding_type,
                        "plugin": plugin,
                        "error": str(e)
                    })
            
        except Exception as e:
            result.status = "error"
            result.findings.append({"type": "error", "message": str(e)})
        
        # Store result
        if self._db is not None:
            await self._db.memory_analyses.insert_one(asdict(result))
        
        return result
    
    async def capture_live_memory(self) -> Dict[str, Any]:
        """Capture live memory (Linux only, requires AVML or LiME)"""
        if platform.system() != "Linux":
            return {"error": "Live memory capture only supported on Linux"}
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dump_path = FORENSICS_DIR / f"memory_dump_{timestamp}.raw"
        
        # Try AVML first
        try:
            proc = await asyncio.create_subprocess_exec(
                "avml", str(dump_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=600)
            
            if proc.returncode == 0:
                return {
                    "status": "success",
                    "dump_path": str(dump_path),
                    "size_mb": dump_path.stat().st_size / (1024 * 1024) if dump_path.exists() else 0
                }
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.error(f"AVML capture failed: {e}")
        
        return {
            "status": "error",
            "message": "Memory capture tools (AVML/LiME) not installed"
        }
    
    def get_status(self) -> Dict[str, Any]:
        """Get memory forensics status"""
        return {
            "volatility_installed": self.volatility_path is not None,
            "volatility_path": self.volatility_path,
            "volatility_mode": "module" if self.use_module_fallback else "binary",
            "supported_os": ["Windows", "Linux", "macOS"]
        }


# =============================================================================
# EDR MANAGER
# =============================================================================

class EDRManager:
    """
    Central manager for EDR capabilities.
    """
    
    _instance = None
    _db = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.process_tree = ProcessTreeBuilder()
        self.fim = FileIntegrityMonitor()
        self.usb_control = USBDeviceController()
        self.memory_forensics = MemoryForensics()
        self._initialized = True
    
    @classmethod
    def set_database(cls, db):
        cls._db = db
        if cls._instance:
            cls._instance.process_tree.set_database(db)
            cls._instance.fim.set_database(db)
            cls._instance.memory_forensics.set_database(db)
    
    async def get_process_tree(self) -> List[Dict]:
        """Get current process tree"""
        tree = await self.process_tree.build_process_tree()
        return [self.process_tree.tree_to_dict(node) for node in tree]
    
    async def check_file_integrity(self) -> List[Dict]:
        """Check file integrity"""
        events = await self.fim.check_integrity()
        return [asdict(e) for e in events]
    
    async def create_fim_baseline(self) -> Dict:
        """Create FIM baseline"""
        return await self.fim.create_baseline()
    
    async def scan_usb_devices(self) -> List[Dict]:
        """Scan USB devices"""
        devices = await self.usb_control.scan_devices()
        return [asdict(d) for d in devices]
    
    async def analyze_memory(self, dump_path: str) -> Dict:
        """Analyze memory dump"""
        result = await self.memory_forensics.analyze_memory_dump(dump_path)
        return asdict(result)
    
    async def capture_memory(self) -> Dict:
        """Capture live memory"""
        return await self.memory_forensics.capture_live_memory()
    
    async def collect_telemetry(self) -> Dict:
        """Collect EDR telemetry"""
        try:
            import psutil
            
            # Get suspicious processes
            tree = await self.process_tree.build_process_tree()
            suspicious = []
            
            def find_suspicious(node: ProcessTreeNode):
                if node.process.is_suspicious:
                    suspicious.append({
                        "pid": node.process.pid,
                        "name": node.process.name,
                        "reasons": node.process.suspicion_reasons
                    })
                for child in node.children:
                    find_suspicious(child)
            
            for root in tree:
                find_suspicious(root)
            
            # Get network connections safely (may require root)
            try:
                net_conns = len(psutil.net_connections())
            except (psutil.AccessDenied, PermissionError):
                net_conns = 0
            
            # Get open files count safely
            try:
                open_files_count = sum(len(p.open_files()) for p in psutil.process_iter(['open_files']) if p.info.get('open_files'))
            except (psutil.AccessDenied, PermissionError):
                open_files_count = 0
            
            telemetry = EDRTelemetry(
                timestamp=datetime.now(timezone.utc).isoformat(),
                hostname=platform.node(),
                os_info={
                    "system": platform.system(),
                    "release": platform.release(),
                    "version": platform.version()
                },
                process_count=len(psutil.pids()),
                network_connections=net_conns,
                open_files=open_files_count,
                cpu_usage=psutil.cpu_percent(),
                memory_usage=psutil.virtual_memory().percent,
                disk_usage=psutil.disk_usage('/').percent,
                suspicious_activity=suspicious,
                fim_events=len(self.fim.events)
            )
            
            return asdict(telemetry)
            
        except Exception as e:
            logger.error(f"Telemetry collection failed: {e}")
            return {"error": str(e)}
    
    def get_status(self) -> Dict[str, Any]:
        """Get EDR status"""
        return {
            "fim": self.fim.get_status(),
            "usb_control": self.usb_control.get_status(),
            "memory_forensics": self.memory_forensics.get_status(),
            "config": {
                "fim_enabled": config.fim_enabled,
                "usb_control_enabled": config.usb_control_enabled,
                "app_whitelist_enabled": config.app_whitelist_enabled,
                "telemetry_interval": config.telemetry_interval
            }
        }


# Global instance
edr_manager = EDRManager()
