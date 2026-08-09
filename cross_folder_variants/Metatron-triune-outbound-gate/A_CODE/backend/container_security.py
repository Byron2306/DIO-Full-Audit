"""
Container Security Service
===========================
Comprehensive container security monitoring and scanning:

1. Image Vulnerability Scanning (Trivy integration)
2. Runtime Security (Falco integration)
3. Container Escape Detection
4. Crypto-miner Detection
5. Privileged Container Monitoring
6. Network Policy Enforcement
7. Kubernetes Security (Pod Security, RBAC audit)
8. Image Signing Verification (Cosign/Notary)
9. Secret Detection in Images
10. Compliance Checking (CIS Docker Benchmark)

Enterprise-grade features:
- Real-time Falco alert streaming
- CIS Docker Benchmark 1.5+ compliance
- Supply chain security (image signing)
- Kubernetes RBAC anomaly detection
- Secret scanning with regex patterns
"""

import os
import json
import asyncio
import subprocess
import logging
import re
import socket
import threading
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Callable, Set, Tuple
from dataclasses import dataclass, field, asdict
from pathlib import Path
from enum import Enum
import hashlib
from collections import defaultdict
from runtime_paths import ensure_data_dir

logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================

TRIVY_CACHE_DIR = ensure_data_dir("trivy_cache")
FALCO_ALERTS_PATH = Path("/var/log/falco/falco_alerts.json")
FALCO_SOCKET_PATH = Path("/var/run/falco/falco.sock")
CIS_RESULTS_DIR = ensure_data_dir("cis_benchmarks")

class ContainerSecurityConfig:
    def __init__(self):
        self.trivy_enabled = os.environ.get("TRIVY_ENABLED", "true").lower() == "true"
        self.falco_enabled = os.environ.get("FALCO_ENABLED", "true").lower() == "true"
        self.auto_scan_new_images = os.environ.get("AUTO_SCAN_IMAGES", "true").lower() == "true"
        self.block_vulnerable_images = os.environ.get("BLOCK_VULNERABLE", "false").lower() == "true"
        self.severity_threshold = os.environ.get("VULN_SEVERITY_THRESHOLD", "HIGH")
        self.kubernetes_enabled = os.environ.get("K8S_ENABLED", "true").lower() == "true"
        self.cosign_verify = os.environ.get("COSIGN_VERIFY", "false").lower() == "true"
        self.cis_benchmark = os.environ.get("CIS_BENCHMARK", "true").lower() == "true"
        self.secret_scanning = os.environ.get("SECRET_SCANNING", "true").lower() == "true"

config = ContainerSecurityConfig()

# =============================================================================
# DATA MODELS
# =============================================================================

class VulnerabilitySeverity(Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"

@dataclass
class Vulnerability:
    """Represents a security vulnerability"""
    vuln_id: str
    pkg_name: str
    installed_version: str
    fixed_version: Optional[str]
    severity: str
    title: str
    description: str = ""
    references: List[str] = field(default_factory=list)
    cvss_score: Optional[float] = None

@dataclass
class ImageScanResult:
    """Result of scanning a container image"""
    image_name: str
    image_id: str
    scan_id: str
    scanned_at: str
    vulnerabilities: List[Vulnerability] = field(default_factory=list)
    total_vulnerabilities: int = 0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    scan_status: str = "completed"
    scan_duration_ms: int = 0
    os_family: str = ""
    os_version: str = ""

@dataclass
class ContainerRuntimeEvent:
    """Runtime security event from a container"""
    event_id: str
    container_id: str
    container_name: str
    image_name: str
    event_type: str
    timestamp: str
    severity: str
    rule_name: str
    description: str
    process_name: Optional[str] = None
    user: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ContainerInfo:
    """Information about a running container"""
    container_id: str
    name: str
    # Prefer a human-readable reference (repo:tag or build name). If Docker only
    # reports an image ID, we resolve it via `docker inspect` Config.Image.
    image: str
    status: str
    created: str
    # Raw immutable image identifier (e.g. sha256:...).
    image_id: str = ""
    ports: List[str] = field(default_factory=list)
    is_privileged: bool = False
    capabilities: List[str] = field(default_factory=list)
    security_score: int = 100
    last_scan: Optional[str] = None
    vulnerabilities_count: int = 0


@dataclass
class SecretFinding:
    """A secret found in a container image"""
    finding_id: str
    secret_type: str
    file_path: str
    line_number: int
    match: str  # Redacted match
    severity: str
    rule_id: str
    description: str


@dataclass
class CISBenchmarkResult:
    """CIS Docker Benchmark check result"""
    check_id: str
    check_name: str
    level: int  # 1 or 2
    status: str  # PASS, FAIL, WARN, INFO
    description: str
    remediation: str
    audit_result: str


@dataclass
class FalcoAlert:
    """Falco runtime security alert"""
    alert_id: str
    timestamp: str
    rule: str
    priority: str
    output: str
    container_id: Optional[str]
    container_name: Optional[str]
    pod_name: Optional[str]
    namespace: Optional[str]
    process_name: Optional[str]
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ContainerEscapeAttempt:
    """Detected container escape attempt"""
    attempt_id: str
    timestamp: str
    container_id: str
    escape_type: str
    severity: str
    details: Dict[str, Any]
    blocked: bool = False


# =============================================================================
# TRIVY SCANNER
# =============================================================================

class TrivyScanner:
    """
    Trivy-based container image vulnerability scanner.
    https://github.com/aquasecurity/trivy
    """
    
    def __init__(self):
        self.trivy_path = self._find_trivy()
        self.scan_cache: Dict[str, ImageScanResult] = {}
        self._db = None
    
    def set_database(self, db):
        self._db = db
    
    def _find_trivy(self) -> Optional[str]:
        """Find trivy binary"""
        paths = ["/usr/local/bin/trivy", "/usr/bin/trivy", "trivy"]
        for path in paths:
            try:
                result = subprocess.run([path, "--version"], capture_output=True, timeout=5)
                if result.returncode == 0:
                    logger.info(f"Found Trivy at: {path}")
                    return path
            except Exception:
                continue
        logger.warning("Trivy not found - container scanning disabled")
        return None

    def is_available(self) -> bool:
        return bool(self.trivy_path)
    
    async def scan_image(self, image_name: str, force: bool = False) -> ImageScanResult:
        """
        Scan a container image for vulnerabilities.
        Uses cache unless force=True.
        """
        # Check cache
        cache_key = hashlib.md5(image_name.encode()).hexdigest()
        if not force and cache_key in self.scan_cache:
            cached = self.scan_cache[cache_key]
            # Use cache if less than 24 hours old
            cached_time = datetime.fromisoformat(cached.scanned_at.replace('Z', '+00:00'))
            if datetime.now(timezone.utc) - cached_time < timedelta(hours=24):
                return cached
        
        if not self.trivy_path:
            return ImageScanResult(
                image_name=image_name,
                image_id="",
                scan_id=hashlib.md5(f"{image_name}-{datetime.now().isoformat()}".encode()).hexdigest()[:16],
                scanned_at=datetime.now(timezone.utc).isoformat(),
                scan_status="error",
                vulnerabilities=[Vulnerability(
                    vuln_id="TRIVY_NOT_INSTALLED",
                    pkg_name="trivy",
                    installed_version="0",
                    fixed_version=None,
                    severity="UNKNOWN",
                    title="Trivy scanner not installed",
                    description="Install trivy to enable container scanning"
                )]
            )
        
        start_time = datetime.now()
        
        try:
            # Run trivy scan
            cmd = [
                self.trivy_path, "image",
                "--format", "json",
                "--severity", "CRITICAL,HIGH,MEDIUM,LOW",
                "--cache-dir", str(TRIVY_CACHE_DIR),
                image_name
            ]
            
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(result.communicate(), timeout=300)
            
            if result.returncode != 0 and not stdout:
                raise Exception(f"Trivy scan failed: {stderr.decode()}")
            
            # Parse results
            scan_data = json.loads(stdout.decode()) if stdout else {}
            
            vulnerabilities = []
            critical_count = high_count = medium_count = low_count = 0
            
            for result_item in scan_data.get("Results", []):
                for vuln in result_item.get("Vulnerabilities", []):
                    severity = vuln.get("Severity", "UNKNOWN").upper()
                    
                    if severity == "CRITICAL":
                        critical_count += 1
                    elif severity == "HIGH":
                        high_count += 1
                    elif severity == "MEDIUM":
                        medium_count += 1
                    elif severity == "LOW":
                        low_count += 1
                    
                    vulnerabilities.append(Vulnerability(
                        vuln_id=vuln.get("VulnerabilityID", ""),
                        pkg_name=vuln.get("PkgName", ""),
                        installed_version=vuln.get("InstalledVersion", ""),
                        fixed_version=vuln.get("FixedVersion"),
                        severity=severity,
                        title=vuln.get("Title", ""),
                        description=vuln.get("Description", "")[:500],
                        references=vuln.get("References", [])[:5],
                        cvss_score=vuln.get("CVSS", {}).get("nvd", {}).get("V3Score")
                    ))
            
            # Get OS info
            metadata = scan_data.get("Metadata", {})
            os_info = metadata.get("OS", {})
            
            scan_result = ImageScanResult(
                image_name=image_name,
                image_id=metadata.get("ImageID", "")[:12],
                scan_id=hashlib.md5(f"{image_name}-{datetime.now().isoformat()}".encode()).hexdigest()[:16],
                scanned_at=datetime.now(timezone.utc).isoformat(),
                vulnerabilities=vulnerabilities,
                total_vulnerabilities=len(vulnerabilities),
                critical_count=critical_count,
                high_count=high_count,
                medium_count=medium_count,
                low_count=low_count,
                scan_status="completed",
                scan_duration_ms=int((datetime.now() - start_time).total_seconds() * 1000),
                os_family=os_info.get("Family", ""),
                os_version=os_info.get("Name", "")
            )
            
            # Cache result
            self.scan_cache[cache_key] = scan_result
            
            # Store in database
            if self._db is not None:
                await self._db.container_scans.insert_one(asdict(scan_result))
            
            logger.info(f"Scanned {image_name}: {len(vulnerabilities)} vulnerabilities found")
            return scan_result
            
        except asyncio.TimeoutError:
            return ImageScanResult(
                image_name=image_name,
                image_id="",
                scan_id=hashlib.md5(f"{image_name}-{datetime.now().isoformat()}".encode()).hexdigest()[:16],
                scanned_at=datetime.now(timezone.utc).isoformat(),
                scan_status="timeout"
            )
        except Exception as e:
            logger.error(f"Scan failed for {image_name}: {e}")
            return ImageScanResult(
                image_name=image_name,
                image_id="",
                scan_id=hashlib.md5(f"{image_name}-{datetime.now().isoformat()}".encode()).hexdigest()[:16],
                scanned_at=datetime.now(timezone.utc).isoformat(),
                scan_status="error",
                vulnerabilities=[Vulnerability(
                    vuln_id="SCAN_ERROR",
                    pkg_name="scanner",
                    installed_version="",
                    fixed_version=None,
                    severity="UNKNOWN",
                    title="Scan error",
                    description=str(e)[:200]
                )]
            )
    
    async def scan_all_images(self) -> List[ImageScanResult]:
        """Scan all local Docker images"""
        images = await self._get_local_images()
        results = []
        
        for image in images:
            result = await self.scan_image(image)
            results.append(result)
        
        return results
    
    async def _get_local_images(self) -> List[str]:
        """Get list of local Docker images"""
        try:
            result = await asyncio.create_subprocess_exec(
                "docker", "images", "--format", "{{.Repository}}:{{.Tag}}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await result.communicate()
            images = [img for img in stdout.decode().split('\n') if img and img != '<none>:<none>']
            return images
        except Exception as e:
            logger.error(f"Failed to list Docker images: {e}")
            return []


# =============================================================================
# CONTAINER RUNTIME MONITOR
# =============================================================================

class ContainerRuntimeMonitor:
    """
    Monitors running containers for security issues:
    - Privileged containers
    - Container escapes
    - Crypto-miners
    - Suspicious processes
    """
    
    # Expanded crypto-miner process detection
    CRYPTO_MINER_PROCESSES = {
        # XMR/Monero miners
        "xmrig", "xmr-stak", "xmr-stak-cpu", "xmr-stak-nvidia", "xmr-stak-amd",
        "minerd", "cpuminer", "cpuminer-multi",
        # Bitcoin/Ethereum miners
        "cgminer", "bfgminer", "ethminer", "claymore", "phoenixminer",
        "trex", "t-rex", "gminer", "nbminer", "lolminer",
        # Pool miners
        "stratum", "nicehash", "minergate", "nanopool",
        # Generic
        "miner", "cryptonight", "randomx", "kawpow",
        # Hidden/obfuscated
        "kswapd0", "watchdogs", "ksoftirqd", "kdevtmpfsi", "kinsing"
    }
    
    # Mining pool domains/IPs to detect in network connections
    MINING_POOL_PATTERNS = [
        r"pool\..*\.(com|net|org)",
        r".*mining.*pool.*",
        r".*\.nicehash\.com",
        r".*\.nanopool\.org",
        r".*\.f2pool\.com",
        r".*\.antpool\.com",
        r".*\.slushpool\.com",
        r".*\.ethermine\.org",
        r".*\.sparkpool\.com",
        r"stratum\+tcp://",
        r"stratum\+ssl://",
    ]
    
    # High CPU usage threshold (percentage)
    CPU_THRESHOLD = 90
    
    SUSPICIOUS_CAPABILITIES = {
        "SYS_ADMIN", "SYS_PTRACE", "NET_ADMIN", "NET_RAW",
        "DAC_OVERRIDE", "SETUID", "SETGID", "SYS_MODULE",
        "SYS_RAWIO", "SYS_CHROOT", "MKNOD", "AUDIT_WRITE"
    }
    
    def __init__(self):
        self.runtime_events: List[ContainerRuntimeEvent] = []
        self._monitoring = False
        self._db = None
        self._alert_callback = None
    
    def set_database(self, db):
        self._db = db
    
    def set_alert_callback(self, callback):
        self._alert_callback = callback
    
    async def get_running_containers(self) -> List[ContainerInfo]:
        """Get list of running containers with security assessment"""
        def _looks_like_image_id(value: str) -> bool:
            v = (value or "").strip().lower()
            if not v:
                return False
            if v.startswith("sha256:"):
                return True
            # docker ps often renders untagged images as a 12-char hex ID
            if re.fullmatch(r"[0-9a-f]{12,64}", v):
                return True
            return False

        try:
            result = await asyncio.create_subprocess_exec(
                "docker", "ps", "--format", 
                '{"id":"{{.ID}}","name":"{{.Names}}","image":"{{.Image}}","status":"{{.Status}}","ports":"{{.Ports}}"}',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await result.communicate()
            
            containers = []
            for line in stdout.decode().split('\n'):
                if not line.strip():
                    continue
                
                try:
                    data = json.loads(line)
                    container_id = data.get("id", "")
                    docker_ps_image = data.get("image", "") or ""
                    
                    # Get detailed inspection
                    inspect_result = await asyncio.create_subprocess_exec(
                        "docker", "inspect", container_id,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    inspect_stdout, _ = await inspect_result.communicate()
                    inspect_data = json.loads(inspect_stdout.decode())[0] if inspect_stdout else {}

                    host_config = inspect_data.get("HostConfig", {})
                    is_privileged = host_config.get("Privileged", False)
                    cap_add = host_config.get("CapAdd", []) or []

                    config_image = ""
                    try:
                        config_image = str(inspect_data.get("Config", {}).get("Image") or "")
                    except Exception:
                        config_image = ""
                    image_id = str(inspect_data.get("Image") or "")
                    image_display = docker_ps_image
                    if _looks_like_image_id(image_display) and config_image:
                        image_display = config_image

                    # Calculate security score
                    security_score = 100
                    if is_privileged:
                        security_score -= 50
                    for cap in cap_add:
                        if cap in self.SUSPICIOUS_CAPABILITIES:
                            security_score -= 10
                    
                    containers.append(ContainerInfo(
                        container_id=container_id,
                        name=data.get("name", ""),
                        image=image_display,
                        image_id=image_id,
                        status=data.get("status", ""),
                        created=inspect_data.get("Created", ""),
                        ports=data.get("ports", "").split(", ") if data.get("ports") else [],
                        is_privileged=is_privileged,
                        capabilities=cap_add,
                        security_score=max(0, security_score)
                    ))
                    
                except json.JSONDecodeError:
                    continue
            
            return containers
            
        except Exception as e:
            logger.error(f"Failed to get containers: {e}")
            return []
    
    async def check_container_security(self, container_id: str) -> Dict[str, Any]:
        """Perform security check on a specific container"""
        findings = {
            "container_id": container_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "issues": [],
            "risk_level": "low"
        }
        
        try:
            # Get container processes
            result = await asyncio.create_subprocess_exec(
                "docker", "top", container_id,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await result.communicate()
            
            processes = stdout.decode().lower()
            
            # Check for crypto miners
            for miner in self.CRYPTO_MINER_PROCESSES:
                if miner in processes:
                    findings["issues"].append({
                        "type": "crypto_miner",
                        "severity": "critical",
                        "description": f"Possible crypto-miner detected: {miner}"
                    })
                    findings["risk_level"] = "critical"
            
            # Check container CPU usage for mining behavior
            stats_result = await asyncio.create_subprocess_exec(
                "docker", "stats", container_id, "--no-stream", "--format", "{{.CPUPerc}}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stats_stdout, _ = await stats_result.communicate()
            cpu_str = stats_stdout.decode().strip().replace('%', '')
            try:
                cpu_usage = float(cpu_str)
                if cpu_usage > self.CPU_THRESHOLD:
                    findings["issues"].append({
                        "type": "high_cpu_usage",
                        "severity": "medium",
                        "description": f"Abnormally high CPU usage: {cpu_usage}% (possible mining)"
                    })
                    if findings["risk_level"] == "low":
                        findings["risk_level"] = "medium"
            except ValueError:
                pass
            
            # Check for mining pool connections
            netstat_result = await asyncio.create_subprocess_exec(
                "docker", "exec", container_id, "sh", "-c", 
                "netstat -an 2>/dev/null || ss -an 2>/dev/null || cat /proc/net/tcp 2>/dev/null",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            netstat_stdout, _ = await netstat_result.communicate()
            network_output = netstat_stdout.decode().lower()
            
            for pool_pattern in self.MINING_POOL_PATTERNS:
                if re.search(pool_pattern, network_output, re.IGNORECASE):
                    findings["issues"].append({
                        "type": "mining_pool_connection",
                        "severity": "critical",
                        "description": f"Connection to mining pool detected"
                    })
                    findings["risk_level"] = "critical"
                    break
            
            # Get container inspect
            inspect_result = await asyncio.create_subprocess_exec(
                "docker", "inspect", container_id,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            inspect_stdout, _ = await inspect_result.communicate()
            inspect_data = json.loads(inspect_stdout.decode())[0] if inspect_stdout else {}
            
            host_config = inspect_data.get("HostConfig", {})
            
            # Check privileged mode
            if host_config.get("Privileged"):
                findings["issues"].append({
                    "type": "privileged_container",
                    "severity": "high",
                    "description": "Container running in privileged mode"
                })
                if findings["risk_level"] != "critical":
                    findings["risk_level"] = "high"
            
            # Check for host PID namespace
            if host_config.get("PidMode") == "host":
                findings["issues"].append({
                    "type": "host_pid_namespace",
                    "severity": "high",
                    "description": "Container shares host PID namespace"
                })
                if findings["risk_level"] != "critical":
                    findings["risk_level"] = "high"
            
            # Check for dangerous capabilities
            cap_add = host_config.get("CapAdd", []) or []
            dangerous_caps = [c for c in cap_add if c in self.SUSPICIOUS_CAPABILITIES]
            if dangerous_caps:
                findings["issues"].append({
                    "type": "dangerous_capabilities",
                    "severity": "medium",
                    "description": f"Dangerous capabilities: {', '.join(dangerous_caps)}"
                })
                if findings["risk_level"] == "low":
                    findings["risk_level"] = "medium"
            
            # Check for host mounts
            mounts = inspect_data.get("Mounts", [])
            sensitive_mounts = [m for m in mounts if m.get("Source", "").startswith(("/etc", "/var/run/docker.sock", "/"))]
            if sensitive_mounts:
                findings["issues"].append({
                    "type": "sensitive_mounts",
                    "severity": "medium",
                    "description": f"Sensitive host paths mounted: {len(sensitive_mounts)}"
                })
            
        except Exception as e:
            logger.error(f"Security check failed for {container_id}: {e}")
            findings["error"] = str(e)
        
        return findings
    
    async def get_runtime_events(self, limit: int = 50) -> List[Dict]:
        """Get recent runtime security events"""
        return [asdict(e) for e in self.runtime_events[-limit:]]


# =============================================================================
# CONTAINER SECURITY MANAGER
# =============================================================================

class ContainerSecurityManager:
    """
    Central manager for container security features.
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
        
        self.scanner = TrivyScanner()
        self.runtime_monitor = ContainerRuntimeMonitor()
        self._initialized = True
    
    @classmethod
    def set_database(cls, db):
        cls._db = db
        if cls._instance:
            cls._instance.scanner.set_database(db)
            cls._instance.runtime_monitor.set_database(db)
    
    async def scan_image(self, image_name: str, force: bool = False) -> Dict:
        """Scan a container image"""
        result = await self.scanner.scan_image(image_name, force)
        return asdict(result)
    
    async def scan_all_images(self) -> List[Dict]:
        """Scan all local images"""
        results = await self.scanner.scan_all_images()
        return [asdict(r) for r in results]
    
    async def get_containers(self) -> List[Dict]:
        """Get running containers with security info"""
        containers = await self.runtime_monitor.get_running_containers()
        return [asdict(c) for c in containers]
    
    async def check_container(self, container_id: str) -> Dict:
        """Security check a specific container"""
        return await self.runtime_monitor.check_container_security(container_id)
    
    async def get_runtime_security_status(self) -> Dict[str, Any]:
        """Return a summary of Falco/Suricata runtime security status."""
        import subprocess

        def _container_running(name: str) -> bool:
            try:
                out = subprocess.check_output(
                    ["docker", "inspect", "--format", "{{.State.Running}}", name],
                    stderr=subprocess.DEVNULL, timeout=5,
                ).decode().strip()
                return out == "true"
            except Exception:
                return False

        falco_running = _container_running("seraph-falco")
        suricata_running = _container_running("seraph-suricata")
        return {
            "falco": {
                "available": falco_running,
                "status": "running" if falco_running else "not_running",
            },
            "suricata": {
                "available": suricata_running,
                "status": "running" if suricata_running else "not_running",
            },
            "runtime_events": len(self.runtime_monitor.runtime_events),
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get container security statistics"""
        return {
            "trivy_enabled": config.trivy_enabled,
            "falco_enabled": config.falco_enabled,
            "auto_scan": config.auto_scan_new_images,
            "cached_scans": len(self.scanner.scan_cache),
            "runtime_events": len(self.runtime_monitor.runtime_events)
        }


# =============================================================================
# SECRET SCANNER
# =============================================================================

class SecretScanner:
    """
    Scans container images for hardcoded secrets.
    Uses regex patterns to detect API keys, passwords, certificates, etc.
    """
    
    # Secret detection patterns (type, pattern, severity)
    SECRET_PATTERNS = [
        # AWS
        ("aws_access_key", r"AKIA[0-9A-Z]{16}", "critical"),
        ("aws_secret_key", r"['\"][0-9a-zA-Z/+]{40}['\"]", "critical"),
        
        # Azure
        ("azure_storage_key", r"DefaultEndpointsProtocol=https;AccountName=[^;]+;AccountKey=[^;]+", "critical"),
        ("azure_conn_string", r"AccountKey=[A-Za-z0-9+/=]{88}", "critical"),
        
        # GCP
        ("gcp_service_account", r'"type":\s*"service_account"', "critical"),
        ("gcp_api_key", r"AIza[0-9A-Za-z_-]{35}", "critical"),
        
        # Generic API Keys
        ("api_key", r"['\"]?api[_-]?key['\"]?\s*[:=]\s*['\"][a-zA-Z0-9_-]{20,}['\"]", "high"),
        ("auth_token", r"['\"]?auth[_-]?token['\"]?\s*[:=]\s*['\"][a-zA-Z0-9_-]{20,}['\"]", "high"),
        ("bearer_token", r"Bearer\s+[a-zA-Z0-9_-]{20,}", "high"),
        
        # Private Keys
        ("private_key", r"-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----", "critical"),
        ("pgp_private", r"-----BEGIN PGP PRIVATE KEY BLOCK-----", "critical"),
        
        # Database
        ("db_password", r"(?:password|passwd|pwd)\s*[:=]\s*['\"][^'\"]{8,}['\"]", "high"),
        ("db_conn_string", r"(?:mysql|postgres|mongodb)://[^:]+:[^@]+@", "critical"),
        ("redis_url", r"redis://:[^@]+@", "high"),
        
        # JWT
        ("jwt_secret", r"['\"]?jwt[_-]?secret['\"]?\s*[:=]\s*['\"][^'\"]{16,}['\"]", "critical"),
        ("jwt_token", r"eyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*", "medium"),
        
        # GitHub/GitLab
        ("github_token", r"gh[pousr]_[A-Za-z0-9_]{36,}", "critical"),
        ("gitlab_token", r"glpat-[A-Za-z0-9_-]{20,}", "critical"),
        
        # Slack
        ("slack_token", r"xox[baprs]-[0-9]{10,13}-[0-9]{10,13}[a-zA-Z0-9-]*", "high"),
        ("slack_webhook", r"https://hooks\.slack\.com/services/T[A-Z0-9]+/B[A-Z0-9]+/[a-zA-Z0-9]+", "high"),
        
        # Stripe
        ("stripe_key", r"sk_live_[0-9a-zA-Z]{24,}", "critical"),
        ("stripe_restricted", r"rk_live_[0-9a-zA-Z]{24,}", "critical"),
        
        # Generic Secrets
        ("password", r"(?:password|passwd|pwd|pass)\s*[:=]\s*['\"][^'\"]{6,}['\"]", "medium"),
        ("secret", r"(?:secret|token|key)\s*[:=]\s*['\"][^'\"]{16,}['\"]", "medium"),
    ]
    
    SKIP_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.ico', '.svg', '.woff', '.woff2', '.ttf', '.eot'}
    SKIP_DIRS = {'node_modules', '.git', '__pycache__', 'vendor', '.venv', 'venv'}
    
    def __init__(self):
        self.compiled_patterns = [(name, re.compile(pattern, re.IGNORECASE), sev) 
                                   for name, pattern, sev in self.SECRET_PATTERNS]
    
    async def scan_image(self, image_name: str) -> List[SecretFinding]:
        """Scan a container image for secrets using docker save + tar extraction."""
        findings = []
        temp_dir = Path(f"/tmp/secret_scan_{hashlib.md5(image_name.encode()).hexdigest()[:8]}")
        
        try:
            temp_dir.mkdir(exist_ok=True)
            tar_path = temp_dir / "image.tar"
            
            proc = await asyncio.create_subprocess_exec(
                "docker", "save", "-o", str(tar_path), image_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await proc.communicate()
            
            if proc.returncode != 0:
                logger.warning(f"Could not export image {image_name}")
                return findings
            
            extract_dir = temp_dir / "extracted"
            extract_dir.mkdir(exist_ok=True)
            
            await asyncio.create_subprocess_exec(
                "tar", "-xf", str(tar_path), "-C", str(extract_dir)
            )
            
            for file_path in extract_dir.rglob("*"):
                if file_path.is_file():
                    file_findings = await self._scan_file(file_path, image_name)
                    findings.extend(file_findings)
            
        except Exception as e:
            logger.error(f"Secret scan failed for {image_name}: {e}")
        finally:
            try:
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass
        
        return findings
    
    async def _scan_file(self, file_path: Path, image_name: str) -> List[SecretFinding]:
        """Scan a single file for secrets"""
        findings = []
        
        if file_path.suffix.lower() in self.SKIP_EXTENSIONS:
            return findings
        if any(skip in file_path.parts for skip in self.SKIP_DIRS):
            return findings
        
        try:
            if file_path.stat().st_size > 1024 * 1024:  # Skip files > 1MB
                return findings
            
            content = file_path.read_text(errors='ignore')
            lines = content.split('\n')
            
            for line_num, line in enumerate(lines, 1):
                for name, pattern, severity in self.compiled_patterns:
                    matches = pattern.findall(line)
                    for match in matches:
                        redacted = match[:4] + "..." + match[-4:] if len(match) > 10 else match[:2] + "***"
                        
                        findings.append(SecretFinding(
                            finding_id=hashlib.md5(f"{file_path}{line_num}{name}".encode()).hexdigest()[:12],
                            secret_type=name,
                            file_path=str(file_path.name),
                            line_number=line_num,
                            match=redacted,
                            severity=severity,
                            rule_id=f"SEC-{name.upper()}",
                            description=f"Possible {name.replace('_', ' ')} detected"
                        ))
        except Exception:
            pass
        
        return findings


# =============================================================================
# FALCO INTEGRATION
# =============================================================================

class FalcoIntegration:
    """
    Integration with Falco for runtime container security.
    Supports alert streaming, escape detection, and custom rules.
    """
    
    ESCAPE_PATTERNS = {
        "docker_socket_mount": r"/var/run/docker\.sock",
        "proc_mount": r"mount.*/proc",
        "sys_mount": r"mount.*/sys",
        "cgroup_escape": r"/sys/fs/cgroup",
        "kernel_module": r"insmod|modprobe|rmmod",
        "ptrace_attach": r"ptrace.*PTRACE_ATTACH",
        "nsenter": r"nsenter.*--target.*1",
        "chroot_escape": r"chroot.*\.\.",
    }
    
    def __init__(self):
        self.alerts: List[FalcoAlert] = []
        self.escape_attempts: List[ContainerEscapeAttempt] = []
        self._monitoring = False
        self._monitor_thread = None
        self._alert_callback: Optional[Callable] = None
        self._db = None
        self._falco_available = self._check_falco()
    
    def _check_falco(self) -> bool:
        """Check if Falco is available"""
        try:
            result = subprocess.run(["falco", "--version"], capture_output=True, timeout=5)
            if result.returncode == 0:
                logger.info("Falco runtime security available")
                return True
        except Exception:
            pass
        
        if FALCO_ALERTS_PATH.exists():
            logger.info("Falco alerts file found")
            return True
        
        logger.info("Falco not available - using built-in runtime detection")
        return False
    
    def set_database(self, db):
        self._db = db
    
    def set_alert_callback(self, callback: Callable):
        self._alert_callback = callback
    
    def start_monitoring(self):
        """Start Falco alert monitoring"""
        if self._monitoring:
            return
        
        self._monitoring = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        logger.info("Falco monitoring started")
    
    def stop_monitoring(self):
        """Stop Falco monitoring"""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
    
    def _monitor_loop(self):
        """Background loop to process Falco alerts"""
        last_position = 0
        
        while self._monitoring:
            try:
                if self._falco_available and FALCO_ALERTS_PATH.exists():
                    with open(FALCO_ALERTS_PATH, 'r') as f:
                        f.seek(last_position)
                        new_alerts = f.read()
                        last_position = f.tell()
                    
                    for line in new_alerts.strip().split('\n'):
                        if line:
                            self._process_falco_alert(line)
                
                time.sleep(1)
            except Exception as e:
                logger.debug(f"Falco monitor error: {e}")
                time.sleep(5)
    
    def _process_falco_alert(self, alert_json: str):
        """Process a single Falco alert"""
        try:
            data = json.loads(alert_json)
            
            alert = FalcoAlert(
                alert_id=hashlib.md5(f"{data.get('time', '')}{data.get('rule', '')}".encode()).hexdigest()[:12],
                timestamp=data.get("time", datetime.now(timezone.utc).isoformat()),
                rule=data.get("rule", ""),
                priority=data.get("priority", "WARNING"),
                output=data.get("output", ""),
                container_id=data.get("output_fields", {}).get("container.id"),
                container_name=data.get("output_fields", {}).get("container.name"),
                pod_name=data.get("output_fields", {}).get("k8s.pod.name"),
                namespace=data.get("output_fields", {}).get("k8s.ns.name"),
                process_name=data.get("output_fields", {}).get("proc.name"),
                details=data.get("output_fields", {})
            )
            
            self.alerts.append(alert)
            if len(self.alerts) > 1000:
                self.alerts = self.alerts[-1000:]
            
            escape_attempt = self._check_escape_attempt(alert)
            if escape_attempt:
                self.escape_attempts.append(escape_attempt)
            
            if self._alert_callback:
                self._alert_callback(asdict(alert))
            
            logger.warning(f"Falco alert: {alert.rule} - {alert.output[:100]}")
            
        except json.JSONDecodeError:
            pass
    
    def _check_escape_attempt(self, alert: FalcoAlert) -> Optional[ContainerEscapeAttempt]:
        """Check if alert indicates container escape attempt"""
        escape_rules = {
            "Terminal shell in container": "shell_spawn",
            "Write below root": "root_write",
            "Container Drift Detected": "drift",
            "Privileged Container": "privileged",
            "Mount in sensitive directory": "sensitive_mount",
        }
        
        for rule_pattern, escape_type in escape_rules.items():
            if rule_pattern.lower() in alert.rule.lower():
                return ContainerEscapeAttempt(
                    attempt_id=hashlib.md5(f"{alert.alert_id}-escape".encode()).hexdigest()[:12],
                    timestamp=alert.timestamp,
                    container_id=alert.container_id or "unknown",
                    escape_type=escape_type,
                    severity="critical" if alert.priority in ["CRITICAL", "EMERGENCY"] else "high",
                    details={"rule": alert.rule, "output": alert.output, "process": alert.process_name},
                    blocked=False
                )
        return None
    
    async def check_container_for_escape(self, container_id: str) -> List[ContainerEscapeAttempt]:
        """Check a specific container for escape indicators"""
        attempts = []
        
        try:
            result = await asyncio.create_subprocess_exec(
                "docker", "exec", container_id, "ps", "auxww",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await result.communicate()
            processes = stdout.decode()
            
            for pattern_name, pattern in self.ESCAPE_PATTERNS.items():
                if re.search(pattern, processes, re.IGNORECASE):
                    attempts.append(ContainerEscapeAttempt(
                        attempt_id=hashlib.md5(f"{container_id}-{pattern_name}".encode()).hexdigest()[:12],
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        container_id=container_id,
                        escape_type=pattern_name,
                        severity="critical",
                        details={"pattern": pattern_name},
                        blocked=False
                    ))
        except Exception as e:
            logger.debug(f"Escape check failed for {container_id}: {e}")
        
        return attempts
    
    def get_alerts(self, limit: int = 50, priority: Optional[str] = None) -> List[Dict]:
        """Get recent Falco alerts"""
        alerts = self.alerts[-limit:]
        if priority:
            alerts = [a for a in alerts if a.priority == priority]
        return [asdict(a) for a in alerts]
    
    def get_escape_attempts(self, limit: int = 50) -> List[Dict]:
        """Get recent escape attempts"""
        return [asdict(a) for a in self.escape_attempts[-limit:]]


# =============================================================================
# CIS DOCKER BENCHMARK
# =============================================================================

class CISDockerBenchmark:
    """CIS Docker Benchmark 1.5+ compliance checking."""
    
    def __init__(self):
        self._db = None
    
    def set_database(self, db):
        self._db = db
    
    async def run_benchmark(self) -> List[CISBenchmarkResult]:
        """Run all CIS Docker Benchmark checks"""
        results = []
        results.extend(await self._check_host_configuration())
        results.extend(await self._check_daemon_configuration())
        results.extend(await self._check_container_runtime())
        results.extend(await self._check_security_operations())
        
        if self._db is not None:
            await self._db.cis_benchmarks.insert_one({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "results": [asdict(r) for r in results],
                "passed": len([r for r in results if r.status == "PASS"]),
                "failed": len([r for r in results if r.status == "FAIL"]),
                "total": len(results)
            })
        
        return results
    
    async def _check_host_configuration(self) -> List[CISBenchmarkResult]:
        """CIS Section 1: Host Configuration"""
        results = []
        
        try:
            result = await asyncio.create_subprocess_exec(
                "getent", "group", "docker",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await result.communicate()
            docker_group = stdout.decode().strip()
            users_in_docker = docker_group.split(":")[-1].split(",") if docker_group else []
            users_in_docker = [u for u in users_in_docker if u and u != "root"]
            
            results.append(CISBenchmarkResult(
                check_id="1.1.2",
                check_name="Ensure only trusted users control Docker",
                level=1,
                status="INFO" if len(users_in_docker) <= 3 else "WARN",
                description="Review users with Docker access",
                remediation="Audit users in docker group: " + ", ".join(users_in_docker),
                audit_result=f"Users in docker group: {len(users_in_docker)}"
            ))
        except Exception:
            pass
        
        return results
    
    async def _check_daemon_configuration(self) -> List[CISBenchmarkResult]:
        """CIS Section 2: Docker Daemon Configuration"""
        results = []
        
        try:
            result = await asyncio.create_subprocess_exec(
                "docker", "info", "--format", "{{json .}}",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await result.communicate()
            docker_info = json.loads(stdout.decode()) if stdout else {}
        except Exception:
            docker_info = {}
        
        # 2.1 - Restrict network traffic between containers
        icc = docker_info.get("BridgeNfIptables", True)
        results.append(CISBenchmarkResult(
            check_id="2.1",
            check_name="Restrict network traffic between containers",
            level=1,
            status="PASS" if not icc else "WARN",
            description="Inter-container communication should be restricted",
            remediation="Set --icc=false in daemon configuration",
            audit_result=f"ICC enabled: {icc}"
        ))
        
        # 2.2 - Logging driver
        log_level = docker_info.get("LoggingDriver", "json-file")
        results.append(CISBenchmarkResult(
            check_id="2.2",
            check_name="Ensure logging driver is configured",
            level=1,
            status="PASS" if log_level else "FAIL",
            description="Docker should use appropriate logging driver",
            remediation="Configure logging driver in daemon.json",
            audit_result=f"Logging driver: {log_level}"
        ))
        
        # 2.11 - Live restore
        live_restore = docker_info.get("LiveRestoreEnabled", False)
        results.append(CISBenchmarkResult(
            check_id="2.11",
            check_name="Ensure live restore is enabled",
            level=1,
            status="PASS" if live_restore else "WARN",
            description="Containers should survive daemon restarts",
            remediation='Set "live-restore": true in daemon.json',
            audit_result=f"Live restore: {live_restore}"
        ))
        
        # 2.14 - Content trust
        content_trust = os.environ.get("DOCKER_CONTENT_TRUST", "0")
        results.append(CISBenchmarkResult(
            check_id="2.14",
            check_name="Ensure content trust is enabled",
            level=1,
            status="PASS" if content_trust == "1" else "FAIL",
            description="Image signatures should be verified",
            remediation="Set DOCKER_CONTENT_TRUST=1",
            audit_result=f"DOCKER_CONTENT_TRUST={content_trust}"
        ))
        
        return results
    
    async def _check_container_runtime(self) -> List[CISBenchmarkResult]:
        """CIS Section 5: Container Runtime"""
        results = []
        
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "ps", "-q",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            containers = [c for c in stdout.decode().strip().split('\n') if c]
        except Exception:
            containers = []
        
        privileged_count = 0
        root_user_count = 0
        
        for container_id in containers[:20]:
            try:
                proc = await asyncio.create_subprocess_exec(
                    "docker", "inspect", container_id,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                stdout, _ = await proc.communicate()
                inspect_data = json.loads(stdout.decode())[0] if stdout else {}
                
                host_config = inspect_data.get("HostConfig", {})
                if host_config.get("Privileged"):
                    privileged_count += 1
                
                user = inspect_data.get("Config", {}).get("User", "")
                if not user or user == "root" or user == "0":
                    root_user_count += 1
            except Exception:
                pass
        
        results.append(CISBenchmarkResult(
            check_id="5.1",
            check_name="Ensure containers run as non-root user",
            level=1,
            status="PASS" if root_user_count == 0 else "FAIL",
            description="Containers should not run as root",
            remediation="Use USER directive in Dockerfile or --user flag",
            audit_result=f"Containers running as root: {root_user_count}/{len(containers)}"
        ))
        
        results.append(CISBenchmarkResult(
            check_id="5.2",
            check_name="Ensure privileged mode is not used",
            level=1,
            status="PASS" if privileged_count == 0 else "FAIL",
            description="Containers should not run in privileged mode",
            remediation="Remove --privileged flag from container run commands",
            audit_result=f"Privileged containers: {privileged_count}/{len(containers)}"
        ))
        
        return results
    
    async def _check_security_operations(self) -> List[CISBenchmarkResult]:
        """CIS Section 7: Docker Security Operations"""
        results = []
        
        results.append(CISBenchmarkResult(
            check_id="7.1",
            check_name="Ensure image vulnerability scanning",
            level=1,
            status="PASS" if config.trivy_enabled else "FAIL",
            description="Container images should be scanned for vulnerabilities",
            remediation="Enable Trivy scanning: TRIVY_ENABLED=true",
            audit_result=f"Trivy enabled: {config.trivy_enabled}"
        ))
        
        results.append(CISBenchmarkResult(
            check_id="7.2",
            check_name="Ensure runtime security monitoring",
            level=1,
            status="PASS" if config.falco_enabled else "WARN",
            description="Container runtime should be monitored for threats",
            remediation="Enable Falco: FALCO_ENABLED=true",
            audit_result=f"Falco enabled: {config.falco_enabled}"
        ))
        
        results.append(CISBenchmarkResult(
            check_id="7.3",
            check_name="Ensure secret scanning in images",
            level=2,
            status="PASS" if config.secret_scanning else "WARN",
            description="Images should be scanned for hardcoded secrets",
            remediation="Enable secret scanning: SECRET_SCANNING=true",
            audit_result=f"Secret scanning: {config.secret_scanning}"
        ))
        
        return results
    
    def get_summary(self, results: List[CISBenchmarkResult]) -> Dict[str, Any]:
        """Get benchmark summary"""
        passed = len([r for r in results if r.status == "PASS"])
        failed = len([r for r in results if r.status == "FAIL"])
        warned = len([r for r in results if r.status == "WARN"])
        
        return {
            "total_checks": len(results),
            "passed": passed,
            "failed": failed,
            "warned": warned,
            "compliance_score": round((passed / len(results) * 100) if results else 0, 1),
        }


# =============================================================================
# IMAGE SIGNING VERIFICATION
# =============================================================================

class ImageSigningVerifier:
    """Verifies container image signatures using Cosign/Notary."""
    
    def __init__(self):
        self.cosign_path = self._find_cosign()
        self.verification_cache: Dict[str, Dict] = {}
    
    def _find_cosign(self) -> Optional[str]:
        """Find cosign binary"""
        paths = ["/usr/local/bin/cosign", "/usr/bin/cosign", "cosign"]
        for path in paths:
            try:
                result = subprocess.run([path, "version"], capture_output=True, timeout=5)
                if result.returncode == 0:
                    logger.info(f"Found Cosign at: {path}")
                    return path
            except Exception:
                continue
        logger.info("Cosign not found - image signing verification disabled")
        return None
    
    async def verify_image(self, image_name: str, public_key: Optional[str] = None) -> Dict[str, Any]:
        """Verify container image signature."""
        cache_key = hashlib.md5(image_name.encode()).hexdigest()
        if cache_key in self.verification_cache:
            cached = self.verification_cache[cache_key]
            cached_time = datetime.fromisoformat(cached['timestamp'].replace('Z', '+00:00'))
            if datetime.now(timezone.utc) - cached_time < timedelta(hours=1):
                return cached
        
        result = {
            "image": image_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "verified": False,
            "signed": False,
            "signers": [],
            "error": None
        }
        
        if not self.cosign_path:
            result["error"] = "Cosign not installed"
            return result
        
        try:
            cmd = [self.cosign_path, "verify", image_name]
            if public_key:
                cmd.extend(["--key", public_key])
            
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**os.environ, "COSIGN_EXPERIMENTAL": "1"}
            )
            
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
            
            if proc.returncode == 0:
                result["verified"] = True
                result["signed"] = True
                try:
                    output_data = json.loads(stdout.decode())
                    if isinstance(output_data, list):
                        for sig in output_data:
                            if "critical" in sig:
                                result["signers"].append(sig.get("critical", {}).get("identity", {}).get("docker-reference"))
                except json.JSONDecodeError:
                    pass
            else:
                error_msg = stderr.decode()
                if "no matching signatures" in error_msg.lower():
                    result["signed"] = False
                    result["error"] = "Image not signed"
                else:
                    result["error"] = error_msg[:200]
        
        except asyncio.TimeoutError:
            result["error"] = "Verification timeout"
        except Exception as e:
            result["error"] = str(e)
        
        self.verification_cache[cache_key] = result
        return result


# =============================================================================
# KUBERNETES SECURITY
# =============================================================================

class KubernetesSecurity:
    """Kubernetes security: Pod Security, RBAC audit, Network Policy audit."""
    
    def __init__(self):
        self.kubectl_available = self._check_kubectl()
        self._db = None
    
    def _check_kubectl(self) -> bool:
        """Check if kubectl is available and configured"""
        try:
            result = subprocess.run(["kubectl", "cluster-info"], capture_output=True, timeout=10)
            return result.returncode == 0
        except Exception:
            return False
    
    def set_database(self, db):
        self._db = db
    
    async def audit_rbac(self) -> Dict[str, Any]:
        """Audit Kubernetes RBAC configuration"""
        if not self.kubectl_available:
            return {"error": "kubectl not available", "findings": []}
        
        findings = []
        
        try:
            proc = await asyncio.create_subprocess_exec(
                "kubectl", "get", "clusterrolebindings", "-o", "json",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            
            if stdout:
                bindings = json.loads(stdout.decode())
                for item in bindings.get("items", []):
                    role_ref = item.get("roleRef", {})
                    if role_ref.get("name") == "cluster-admin":
                        subjects = item.get("subjects", [])
                        for subject in subjects:
                            if subject.get("kind") == "User" and subject.get("name") != "system:admin":
                                findings.append({
                                    "type": "excessive_privilege",
                                    "severity": "high",
                                    "resource": item.get("metadata", {}).get("name"),
                                    "description": f"User {subject.get('name')} has cluster-admin role"
                                })
            
            # Check for privileged pods
            proc = await asyncio.create_subprocess_exec(
                "kubectl", "get", "pods", "--all-namespaces", "-o", "json",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            
            if stdout:
                pods = json.loads(stdout.decode())
                privileged_pods = 0
                
                for item in pods.get("items", []):
                    spec = item.get("spec", {})
                    for container in spec.get("containers", []):
                        security_context = container.get("securityContext", {})
                        if security_context.get("privileged"):
                            privileged_pods += 1
                
                if privileged_pods > 0:
                    findings.append({
                        "type": "privileged_containers",
                        "severity": "critical",
                        "description": f"{privileged_pods} pods running privileged containers"
                    })
        
        except Exception as e:
            return {"error": str(e), "findings": []}
        
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "findings": findings,
            "risk_level": "critical" if any(f.get("severity") == "critical" for f in findings) else "low"
        }
    
    async def audit_network_policies(self) -> Dict[str, Any]:
        """Audit Kubernetes Network Policies"""
        if not self.kubectl_available:
            return {"error": "kubectl not available", "findings": []}
        
        findings = []
        namespaces = []
        
        try:
            proc = await asyncio.create_subprocess_exec(
                "kubectl", "get", "namespaces", "-o", "json",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            
            namespaces = json.loads(stdout.decode()).get("items", []) if stdout else []
            
            for ns in namespaces:
                ns_name = ns.get("metadata", {}).get("name", "")
                if ns_name.startswith("kube-"):
                    continue
                
                proc = await asyncio.create_subprocess_exec(
                    "kubectl", "get", "networkpolicies", "-n", ns_name, "-o", "json",
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                stdout, _ = await proc.communicate()
                
                policies = json.loads(stdout.decode()).get("items", []) if stdout else []
                
                if not policies:
                    findings.append({
                        "type": "missing_network_policy",
                        "severity": "medium",
                        "namespace": ns_name,
                        "description": f"Namespace {ns_name} has no network policies"
                    })
        
        except Exception as e:
            return {"error": str(e), "findings": []}
        
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "findings": findings,
            "namespaces_audited": len(namespaces)
        }


# =============================================================================
# ENHANCED CONTAINER SECURITY MANAGER
# =============================================================================

class EnhancedContainerSecurityManager:
    """
    Enterprise-grade container security manager.
    Combines all security features into unified interface.
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
        
        self.scanner = TrivyScanner()
        self.runtime_monitor = ContainerRuntimeMonitor()
        self.secret_scanner = SecretScanner()
        self.falco = FalcoIntegration()
        self.cis_benchmark = CISDockerBenchmark()
        self.signing_verifier = ImageSigningVerifier()
        self.k8s_security = KubernetesSecurity()
        
        # Start Falco monitoring
        if config.falco_enabled:
            self.falco.start_monitoring()
        
        self._initialized = True
        logger.info("EnhancedContainerSecurityManager initialized")

    @staticmethod
    def _docker_container_running(name: str) -> bool:
        try:
            out = subprocess.check_output(
                ["docker", "inspect", "--format", "{{.State.Running}}", name],
                stderr=subprocess.DEVNULL,
                timeout=5,
            ).decode().strip()
            return out.lower() == "true"
        except Exception:
            return False

    @staticmethod
    def _trivy_server_reachable(host: str = "127.0.0.1", port: int = 4954) -> bool:
        try:
            with socket.create_connection((host, port), timeout=2):
                return True
        except Exception:
            return False
    
    @classmethod
    def set_database(cls, db):
        cls._db = db
        if cls._instance:
            cls._instance.scanner.set_database(db)
            cls._instance.runtime_monitor.set_database(db)
            cls._instance.falco.set_database(db)
            cls._instance.cis_benchmark.set_database(db)
            cls._instance.k8s_security.set_database(db)

    async def scan_image(self, image_name: str, force: bool = False) -> Dict[str, Any]:
        result = await self.scanner.scan_image(image_name, force)
        return asdict(result)

    async def scan_all_images(self) -> List[Dict[str, Any]]:
        results = await self.scanner.scan_all_images()
        return [asdict(r) for r in results]

    async def get_containers(self) -> List[Dict[str, Any]]:
        containers = await self.runtime_monitor.get_running_containers()
        return [asdict(c) for c in containers]

    async def check_container(self, container_id: str) -> Dict[str, Any]:
        return await self.runtime_monitor.check_container_security(container_id)
    
    async def full_security_scan(self, image_name: str) -> Dict[str, Any]:
        """Run comprehensive security scan on an image"""
        results = {
            "image": image_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "vulnerability_scan": None,
            "secret_scan": None,
            "signing_verification": None,
            "overall_risk": "unknown"
        }
        
        # Vulnerability scan
        vuln_result = await self.scanner.scan_image(image_name)
        results["vulnerability_scan"] = asdict(vuln_result)
        
        # Secret scan
        if config.secret_scanning:
            secrets = await self.secret_scanner.scan_image(image_name)
            results["secret_scan"] = {
                "findings_count": len(secrets),
                "findings": [asdict(s) for s in secrets[:20]],  # Limit to 20
                "critical_count": len([s for s in secrets if s.severity == "critical"])
            }
        
        # Signing verification
        if config.cosign_verify:
            signing = await self.signing_verifier.verify_image(image_name)
            results["signing_verification"] = signing
        
        # Calculate overall risk
        risk_score = 0
        if vuln_result.critical_count > 0:
            risk_score += 40
        if vuln_result.high_count > 0:
            risk_score += 20
        if results.get("secret_scan", {}).get("critical_count", 0) > 0:
            risk_score += 30
        if not results.get("signing_verification", {}).get("verified", True):
            risk_score += 10
        
        if risk_score >= 50:
            results["overall_risk"] = "critical"
        elif risk_score >= 30:
            results["overall_risk"] = "high"
        elif risk_score >= 10:
            results["overall_risk"] = "medium"
        else:
            results["overall_risk"] = "low"
        
        return results
    
    async def run_cis_benchmark(self) -> Dict[str, Any]:
        """Run CIS Docker Benchmark"""
        results = await self.cis_benchmark.run_benchmark()
        summary = self.cis_benchmark.get_summary(results)
        return {
            "results": [asdict(r) for r in results],
            "summary": summary
        }
    
    async def get_runtime_security_status(self) -> Dict[str, Any]:
        """Get runtime security status"""
        return {
            "falco_available": self.falco._falco_available,
            "falco_monitoring": self.falco._monitoring,
            "recent_alerts": self.falco.get_alerts(limit=10),
            "escape_attempts": self.falco.get_escape_attempts(limit=10),
            "runtime_events": len(self.runtime_monitor.runtime_events)
        }
    
    async def audit_kubernetes(self) -> Dict[str, Any]:
        """Run Kubernetes security audit"""
        if not self.k8s_security.kubectl_available:
            return {"error": "Kubernetes not available"}
        
        rbac = await self.k8s_security.audit_rbac()
        network = await self.k8s_security.audit_network_policies()
        
        return {
            "rbac_audit": rbac,
            "network_policy_audit": network,
            "overall_risk": rbac.get("risk_level", "unknown")
        }
    
    def get_comprehensive_stats(self) -> Dict[str, Any]:
        """Get comprehensive security statistics"""
        trivy_available = (
            bool(config.trivy_enabled and self.scanner.is_available())
            or self._docker_container_running("seraph-trivy")
            or self._trivy_server_reachable()
        )
        return {
            "trivy_enabled": trivy_available,
            "falco_enabled": config.falco_enabled,
            "secret_scanning": config.secret_scanning,
            "cosign_verify": config.cosign_verify,
            "cis_benchmark": config.cis_benchmark,
            "kubernetes_enabled": config.kubernetes_enabled,
            "cached_scans": len(self.scanner.scan_cache),
            "runtime_events": len(self.runtime_monitor.runtime_events),
            "falco_alerts": len(self.falco.alerts),
            "escape_attempts": len(self.falco.escape_attempts),
            "signing_cache": len(self.signing_verifier.verification_cache)
        }

    def get_stats(self) -> Dict[str, Any]:
        stats = self.get_comprehensive_stats()
        return {
            "trivy_enabled": bool(stats.get("trivy_enabled")),
            "falco_enabled": bool(stats.get("falco_enabled")),
            "auto_scan": config.auto_scan_new_images,
            "cached_scans": int(stats.get("cached_scans", 0)),
            "runtime_events": int(stats.get("runtime_events", 0)),
            "trivy_binary_available": self.scanner.is_available(),
            "trivy_server_running": self._docker_container_running("seraph-trivy"),
            "trivy_server_reachable": self._trivy_server_reachable(),
        }


# Global instance
container_security = EnhancedContainerSecurityManager()
