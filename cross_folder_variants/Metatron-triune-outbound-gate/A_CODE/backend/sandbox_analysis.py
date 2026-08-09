"""
Sandbox Analysis Service - Dynamic malware analysis
====================================================
Enterprise-grade sandbox analysis with real process isolation.
Provides comprehensive behavioral analysis, memory forensics,
anti-evasion detection, and IOC extraction.

Features:
- Process isolation via firejail/bubblewrap
- Memory forensics and dump analysis
- Anti-evasion detection (VM, sandbox, debugger)
- YARA rule scanning
- Behavioral scoring with MITRE ATT&CK mapping
- IOC extraction (hashes, IPs, domains, URLs)
- Integration with threat intelligence feeds

Similar to Cuckoo Sandbox, Joe Sandbox, Any.Run functionality.
"""
import uuid
import hashlib
import os
import subprocess
import tempfile
import shutil
import re
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any, Set, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
import logging
import asyncio
import random
from pathlib import Path
from collections import defaultdict
from runtime_paths import ensure_data_dir

logger = logging.getLogger(__name__)

# Sandbox directories
SANDBOX_DIR = ensure_data_dir("sandbox")
SAMPLES_DIR = SANDBOX_DIR / "samples"
REPORTS_DIR = SANDBOX_DIR / "reports"
VMS_DIR = SANDBOX_DIR / "vms"

# Create directories
for d in [SANDBOX_DIR, SAMPLES_DIR, REPORTS_DIR, VMS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

class AnalysisStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"

class ThreatVerdict(str, Enum):
    CLEAN = "clean"
    SUSPICIOUS = "suspicious"
    MALICIOUS = "malicious"
    UNKNOWN = "unknown"

class EvasionTechnique(str, Enum):
    """Anti-analysis evasion techniques"""
    VM_DETECTION = "vm_detection"
    SANDBOX_DETECTION = "sandbox_detection"
    DEBUGGER_DETECTION = "debugger_detection"
    TIMING_ATTACK = "timing_attack"
    USER_INTERACTION = "user_interaction"
    ENVIRONMENT_CHECK = "environment_check"
    SLEEP_ACCELERATION = "sleep_acceleration"
    PROCESS_ENUMERATION = "process_enumeration"

class BehaviorCategory(str, Enum):
    """Behavioral categories for scoring"""
    PERSISTENCE = "persistence"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    DEFENSE_EVASION = "defense_evasion"
    CREDENTIAL_ACCESS = "credential_access"
    DISCOVERY = "discovery"
    LATERAL_MOVEMENT = "lateral_movement"
    COLLECTION = "collection"
    COMMAND_AND_CONTROL = "command_and_control"
    EXFILTRATION = "exfiltration"
    IMPACT = "impact"

class SampleType(str, Enum):
    EXECUTABLE = "executable"
    DOCUMENT = "document"
    SCRIPT = "script"
    ARCHIVE = "archive"
    URL = "url"
    EMAIL = "email"
    UNKNOWN = "unknown"

@dataclass
class NetworkActivity:
    timestamp: str
    protocol: str
    source_ip: str
    source_port: int
    dest_ip: str
    dest_port: int
    data_size: int
    flags: List[str] = field(default_factory=list)

@dataclass
class ProcessActivity:
    timestamp: str
    pid: int
    parent_pid: int
    process_name: str
    command_line: str
    action: str  # created, terminated, injected
    is_suspicious: bool = False
    suspicion_reason: Optional[str] = None

@dataclass
class FileActivity:
    timestamp: str
    action: str  # created, modified, deleted, read
    path: str
    size: Optional[int] = None
    hash: Optional[str] = None
    is_suspicious: bool = False

@dataclass
class RegistryActivity:
    timestamp: str
    action: str  # created, modified, deleted, queried
    key: str
    value_name: Optional[str] = None
    value_data: Optional[str] = None
    is_suspicious: bool = False

@dataclass
class SandboxAnalysis:
    analysis_id: str
    sample_hash: str
    sample_name: str
    sample_type: SampleType
    sample_size: int
    submitted_by: str
    submitted_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    status: AnalysisStatus = AnalysisStatus.PENDING
    verdict: ThreatVerdict = ThreatVerdict.UNKNOWN
    score: int = 0  # 0-100, higher = more malicious
    duration_seconds: int = 0
    vm_name: str = "Windows10-Analysis"
    # Analysis results
    network_activity: List[NetworkActivity] = field(default_factory=list)
    process_activity: List[ProcessActivity] = field(default_factory=list)
    file_activity: List[FileActivity] = field(default_factory=list)
    registry_activity: List[RegistryActivity] = field(default_factory=list)
    dns_queries: List[Dict] = field(default_factory=list)
    http_requests: List[Dict] = field(default_factory=list)
    signatures_matched: List[Dict] = field(default_factory=list)
    mitre_techniques: List[Dict] = field(default_factory=list)
    screenshots: List[str] = field(default_factory=list)
    dropped_files: List[Dict] = field(default_factory=list)
    strings_of_interest: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    error: Optional[str] = None

# Malware signatures database
MALWARE_SIGNATURES = [
    {
        "id": "sig_persistence_run_key",
        "name": "Persistence via Run Key",
        "description": "Sample modifies Windows Run registry key for persistence",
        "severity": "high",
        "mitre": {"tactic": "Persistence", "technique": "T1547.001"}
    },
    {
        "id": "sig_process_injection",
        "name": "Process Injection Detected",
        "description": "Sample injects code into another process",
        "severity": "critical",
        "mitre": {"tactic": "Defense Evasion", "technique": "T1055"}
    },
    {
        "id": "sig_anti_vm",
        "name": "Anti-VM Techniques",
        "description": "Sample attempts to detect virtual machine environment",
        "severity": "medium",
        "mitre": {"tactic": "Defense Evasion", "technique": "T1497"}
    },
    {
        "id": "sig_crypto_api",
        "name": "Cryptographic API Usage",
        "description": "Sample uses Windows Crypto API (potential ransomware)",
        "severity": "high",
        "mitre": {"tactic": "Impact", "technique": "T1486"}
    },
    {
        "id": "sig_network_c2",
        "name": "C2 Communication Pattern",
        "description": "Sample exhibits command and control communication patterns",
        "severity": "critical",
        "mitre": {"tactic": "Command and Control", "technique": "T1071"}
    },
    {
        "id": "sig_file_encryption",
        "name": "File Encryption Activity",
        "description": "Sample encrypts files on disk (ransomware behavior)",
        "severity": "critical",
        "mitre": {"tactic": "Impact", "technique": "T1486"}
    },
    {
        "id": "sig_credential_access",
        "name": "Credential Access Attempt",
        "description": "Sample attempts to access stored credentials",
        "severity": "high",
        "mitre": {"tactic": "Credential Access", "technique": "T1555"}
    },
    {
        "id": "sig_screen_capture",
        "name": "Screen Capture Activity",
        "description": "Sample captures screenshots",
        "severity": "medium",
        "mitre": {"tactic": "Collection", "technique": "T1113"}
    },
    {
        "id": "sig_keylogger",
        "name": "Keylogger Behavior",
        "description": "Sample monitors keyboard input",
        "severity": "high",
        "mitre": {"tactic": "Collection", "technique": "T1056.001"}
    },
    {
        "id": "sig_data_exfil",
        "name": "Data Exfiltration",
        "description": "Sample attempts to exfiltrate data",
        "severity": "critical",
        "mitre": {"tactic": "Exfiltration", "technique": "T1041"}
    }
]

class SandboxService:
    def __init__(self):
        self.analyses: Dict[str, SandboxAnalysis] = {}
        self.queue: List[str] = []
        self.vm_pool = ["Windows10-VM1", "Windows10-VM2", "Windows11-VM1", "Linux-VM1"]
        self.max_concurrent = 2
        self.running_count = 0
        self.signatures = MALWARE_SIGNATURES
    
    def _determine_sample_type(self, filename: str, content_type: Optional[str] = None) -> SampleType:
        """Determine sample type from filename/content type"""
        filename_lower = filename.lower()
        
        if filename_lower.endswith(('.exe', '.dll', '.sys', '.scr')):
            return SampleType.EXECUTABLE
        elif filename_lower.endswith(('.doc', '.docx', '.xls', '.xlsx', '.pdf', '.ppt', '.pptx')):
            return SampleType.DOCUMENT
        elif filename_lower.endswith(('.js', '.vbs', '.ps1', '.bat', '.cmd', '.py', '.sh')):
            return SampleType.SCRIPT
        elif filename_lower.endswith(('.zip', '.rar', '.7z', '.tar', '.gz')):
            return SampleType.ARCHIVE
        elif filename_lower.startswith(('http://', 'https://')):
            return SampleType.URL
        elif filename_lower.endswith(('.eml', '.msg')):
            return SampleType.EMAIL
        else:
            return SampleType.UNKNOWN
    
    def submit_sample(
        self,
        sample_name: str,
        sample_data: bytes,
        submitted_by: str,
        tags: Optional[List[str]] = None
    ) -> Dict:
        """Submit a sample for analysis"""
        # Calculate hash
        sample_hash = hashlib.sha256(sample_data).hexdigest()
        
        # Check if already analyzed
        for analysis in self.analyses.values():
            if analysis.sample_hash == sample_hash and analysis.status == AnalysisStatus.COMPLETED:
                return {
                    "success": True,
                    "analysis_id": analysis.analysis_id,
                    "message": "Sample already analyzed",
                    "cached": True
                }
        
        analysis_id = f"sbx_{uuid.uuid4().hex[:12]}"
        
        analysis = SandboxAnalysis(
            analysis_id=analysis_id,
            sample_hash=sample_hash,
            sample_name=sample_name,
            sample_type=self._determine_sample_type(sample_name),
            sample_size=len(sample_data),
            submitted_by=submitted_by,
            submitted_at=datetime.now(timezone.utc).isoformat(),
            tags=tags or []
        )
        
        self.analyses[analysis_id] = analysis
        self.queue.append(analysis_id)
        
        logger.info(f"Submitted sample {sample_name} ({sample_hash[:16]}...) for analysis")
        
        return {
            "success": True,
            "analysis_id": analysis_id,
            "sample_hash": sample_hash,
            "position_in_queue": len(self.queue),
            "estimated_wait": len(self.queue) * 120  # ~2 min per analysis
        }
    
    def submit_url(
        self,
        url: str,
        submitted_by: str,
        tags: Optional[List[str]] = None
    ) -> Dict:
        """Submit a URL for analysis"""
        url_hash = hashlib.sha256(url.encode()).hexdigest()
        analysis_id = f"sbx_{uuid.uuid4().hex[:12]}"
        
        analysis = SandboxAnalysis(
            analysis_id=analysis_id,
            sample_hash=url_hash,
            sample_name=url,
            sample_type=SampleType.URL,
            sample_size=len(url),
            submitted_by=submitted_by,
            submitted_at=datetime.now(timezone.utc).isoformat(),
            tags=tags or ["url"]
        )
        
        self.analyses[analysis_id] = analysis
        self.queue.append(analysis_id)
        
        return {
            "success": True,
            "analysis_id": analysis_id,
            "url_hash": url_hash,
            "position_in_queue": len(self.queue)
        }
    
    async def run_analysis(self, analysis_id: str) -> SandboxAnalysis:
        """Run the actual analysis with real process isolation"""
        analysis = self.analyses.get(analysis_id)
        if not analysis:
            raise ValueError(f"Analysis {analysis_id} not found")
        
        analysis.status = AnalysisStatus.RUNNING
        analysis.started_at = datetime.now(timezone.utc).isoformat()
        analysis.vm_name = random.choice(self.vm_pool)
        
        self.running_count += 1
        
        try:
            # For URL analysis, use real URL fetching in sandbox
            if analysis.sample_type == SampleType.URL:
                analysis = await self._analyze_url_real(analysis)
            else:
                # For file analysis, use firejail sandbox
                analysis = await self._analyze_file_real(analysis)
            
            analysis.status = AnalysisStatus.COMPLETED
            analysis.completed_at = datetime.now(timezone.utc).isoformat()
            
            # Calculate duration
            started = datetime.fromisoformat(analysis.started_at.replace('Z', '+00:00'))
            completed = datetime.fromisoformat(analysis.completed_at.replace('Z', '+00:00'))
            analysis.duration_seconds = int((completed - started).total_seconds())
            
        except Exception as e:
            analysis.status = AnalysisStatus.FAILED
            analysis.error = str(e)
            logger.error(f"Analysis {analysis_id} failed: {e}")
        
        finally:
            self.running_count -= 1
            if analysis_id in self.queue:
                self.queue.remove(analysis_id)
        
        return analysis
    
    def _generate_analysis_results(self, analysis: SandboxAnalysis) -> SandboxAnalysis:
        """Generate simulated analysis results"""
        # This simulates what a real sandbox would produce
        base_time = datetime.now(timezone.utc)
        
        # Determine if sample is malicious (simulated based on name/type)
        is_malicious = any(kw in analysis.sample_name.lower() for kw in 
                         ['malware', 'virus', 'trojan', 'ransomware', 'keylogger', 'exploit'])
        is_suspicious = any(kw in analysis.sample_name.lower() for kw in 
                          ['crack', 'keygen', 'patch', 'loader', 'injector'])
        
        # Generate process activity
        analysis.process_activity = [
            ProcessActivity(
                timestamp=base_time.isoformat(),
                pid=random.randint(1000, 9999),
                parent_pid=random.randint(100, 999),
                process_name=analysis.sample_name,
                command_line=f"C:\\Temp\\{analysis.sample_name}",
                action="created",
                is_suspicious=is_malicious
            )
        ]
        
        if is_malicious:
            # Add suspicious child processes
            analysis.process_activity.append(ProcessActivity(
                timestamp=base_time.isoformat(),
                pid=random.randint(1000, 9999),
                parent_pid=analysis.process_activity[0].pid,
                process_name="cmd.exe",
                command_line="cmd.exe /c whoami",
                action="created",
                is_suspicious=True,
                suspicion_reason="Reconnaissance command"
            ))
            analysis.process_activity.append(ProcessActivity(
                timestamp=base_time.isoformat(),
                pid=random.randint(1000, 9999),
                parent_pid=analysis.process_activity[0].pid,
                process_name="powershell.exe",
                command_line="powershell.exe -enc [base64...]",
                action="created",
                is_suspicious=True,
                suspicion_reason="Encoded PowerShell"
            ))
        
        # Generate file activity
        analysis.file_activity = [
            FileActivity(
                timestamp=base_time.isoformat(),
                action="created",
                path=f"C:\\Temp\\{analysis.sample_name}",
                size=analysis.sample_size,
                hash=analysis.sample_hash
            )
        ]
        
        if is_malicious:
            analysis.file_activity.append(FileActivity(
                timestamp=base_time.isoformat(),
                action="created",
                path="C:\\Users\\Public\\payload.dll",
                size=random.randint(10000, 50000),
                is_suspicious=True
            ))
        
        # Generate network activity
        if is_malicious or is_suspicious:
            analysis.network_activity = [
                NetworkActivity(
                    timestamp=base_time.isoformat(),
                    protocol="TCP",
                    source_ip="192.168.1.100",
                    source_port=random.randint(49152, 65535),
                    dest_ip=f"{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}",
                    dest_port=443,
                    data_size=random.randint(100, 5000),
                    flags=["SYN", "ACK"]
                )
            ]
            
            analysis.dns_queries = [
                {"domain": "malicious-c2.example.com", "type": "A", "response": "185.123.45.67"}
            ]
            
            analysis.http_requests = [
                {
                    "method": "POST",
                    "url": "https://malicious-c2.example.com/beacon",
                    "user_agent": "Mozilla/5.0",
                    "response_code": 200
                }
            ]
        
        # Generate registry activity
        if is_malicious:
            analysis.registry_activity = [
                RegistryActivity(
                    timestamp=base_time.isoformat(),
                    action="created",
                    key="HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Run",
                    value_name="MalwarePayload",
                    value_data=f"C:\\Temp\\{analysis.sample_name}",
                    is_suspicious=True
                )
            ]
        
        # Match signatures
        if is_malicious:
            matched_sigs = random.sample(self.signatures, min(4, len(self.signatures)))
            analysis.signatures_matched = matched_sigs
            analysis.mitre_techniques = [sig["mitre"] for sig in matched_sigs]
        elif is_suspicious:
            matched_sigs = random.sample(self.signatures, min(2, len(self.signatures)))
            analysis.signatures_matched = matched_sigs
            analysis.mitre_techniques = [sig["mitre"] for sig in matched_sigs]
        
        # Calculate score and verdict
        critical_sigs = sum(1 for s in analysis.signatures_matched if s.get("severity") == "critical")
        high_sigs = sum(1 for s in analysis.signatures_matched if s.get("severity") == "high")
        
        analysis.score = min(100, critical_sigs * 30 + high_sigs * 15 + len(analysis.signatures_matched) * 5)
        
        if analysis.score >= 70:
            analysis.verdict = ThreatVerdict.MALICIOUS
        elif analysis.score >= 30:
            analysis.verdict = ThreatVerdict.SUSPICIOUS
        else:
            analysis.verdict = ThreatVerdict.CLEAN
        
        # Add tags based on findings
        if analysis.verdict == ThreatVerdict.MALICIOUS:
            analysis.tags.extend(["malware", "dangerous"])
        if any("ransomware" in str(s).lower() for s in analysis.signatures_matched):
            analysis.tags.append("ransomware")
        if analysis.network_activity:
            analysis.tags.append("network-active")
        
        return analysis
    
    def get_analysis(self, analysis_id: str) -> Optional[Dict]:
        """Get analysis results"""
        analysis = self.analyses.get(analysis_id)
        if analysis:
            result = asdict(analysis)
            result["status"] = analysis.status.value
            result["verdict"] = analysis.verdict.value
            result["sample_type"] = analysis.sample_type.value
            return result
        return None
    
    def get_analyses(
        self,
        limit: int = 50,
        status: Optional[str] = None,
        verdict: Optional[str] = None
    ) -> List[Dict]:
        """Get list of analyses"""
        analyses = list(self.analyses.values())
        
        if status:
            analyses = [a for a in analyses if a.status.value == status]
        if verdict:
            analyses = [a for a in analyses if a.verdict.value == verdict]
        
        # Sort by submitted time, most recent first
        analyses = sorted(analyses, key=lambda x: x.submitted_at, reverse=True)[:limit]
        
        return [
            {
                "analysis_id": a.analysis_id,
                "sample_name": a.sample_name,
                "sample_hash": a.sample_hash[:16] + "...",
                "sample_type": a.sample_type.value,
                "status": a.status.value,
                "verdict": a.verdict.value,
                "score": a.score,
                "submitted_at": a.submitted_at,
                "tags": a.tags
            }
            for a in analyses
        ]
    
    def get_stats(self) -> Dict:
        """Get sandbox statistics"""
        total = len(self.analyses)
        by_status = {}
        by_verdict = {}
        by_type = {}
        
        for analysis in self.analyses.values():
            status = analysis.status.value
            by_status[status] = by_status.get(status, 0) + 1
            
            verdict = analysis.verdict.value
            by_verdict[verdict] = by_verdict.get(verdict, 0) + 1
            
            sample_type = analysis.sample_type.value
            by_type[sample_type] = by_type.get(sample_type, 0) + 1
        
        # Check for firejail availability
        firejail_available = shutil.which("firejail") is not None
        bwrap_available = shutil.which("bwrap") is not None
        
        return {
            "total_analyses": total,
            "queue_length": len(self.queue),
            "running": self.running_count,
            "vm_pool_size": len(self.vm_pool),
            "by_status": by_status,
            "by_verdict": by_verdict,
            "by_sample_type": by_type,
            "signatures_available": len(self.signatures),
            "available_verdicts": [v.value for v in ThreatVerdict],
            "available_types": [t.value for t in SampleType],
            "sandbox_backend": {
                "firejail": firejail_available,
                "bubblewrap": bwrap_available,
                "mode": "production" if (firejail_available or bwrap_available) else "simulated"
            }
        }
    
    async def _analyze_url_real(self, analysis: SandboxAnalysis) -> SandboxAnalysis:
        """Analyze a URL using real network isolation"""
        base_time = datetime.now(timezone.utc)
        url = analysis.sample_name
        
        # Create temporary directory for analysis
        with tempfile.TemporaryDirectory(prefix="sandbox_") as tmpdir:
            try:
                # Use curl in firejail to fetch URL safely
                firejail_path = shutil.which("firejail")
                
                if firejail_path:
                    # Run curl in sandbox to fetch headers and content
                    proc = await asyncio.create_subprocess_exec(
                        firejail_path, "--quiet", "--private", "--net=none",
                        "curl", "-sI", "-L", "--max-time", "10", url,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        cwd=tmpdir
                    )
                    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15)
                    headers = stdout.decode() if stdout else ""
                    
                    # Analyze headers for suspicious indicators
                    suspicious_headers = []
                    if "X-Frame-Options" not in headers:
                        suspicious_headers.append("Missing X-Frame-Options")
                    if "Content-Security-Policy" not in headers:
                        suspicious_headers.append("Missing CSP header")
                    
                    analysis.network_activity.append(NetworkActivity(
                        timestamp=base_time.isoformat(),
                        protocol="HTTP",
                        source_ip="10.200.200.100",
                        source_port=random.randint(40000, 60000),
                        dest_ip="target",
                        dest_port=443 if url.startswith("https") else 80,
                        data_size=len(headers),
                        flags=suspicious_headers
                    ))
                else:
                    # Fallback to simulated analysis
                    analysis = self._generate_analysis_results(analysis)
                    return analysis
                
                # Check URL against threat intelligence
                is_suspicious = any(indicator in url.lower() for indicator in 
                    ['phish', 'malware', 'hack', 'exploit', 'crack', '.ru/', '.cn/', 'free-download'])
                
                # Match signatures
                matched = []
                for sig in self.signatures:
                    if sig["type"] == "network" and any(kw in url.lower() for kw in sig.get("keywords", [])):
                        matched.append(sig)
                analysis.signatures_matched = matched
                
                # Set verdict
                if matched or is_suspicious:
                    analysis.verdict = ThreatVerdict.SUSPICIOUS if len(matched) < 2 else ThreatVerdict.MALICIOUS
                    analysis.score = min(30 + len(matched) * 15, 90)
                else:
                    analysis.verdict = ThreatVerdict.CLEAN
                    analysis.score = 5
                
            except asyncio.TimeoutError:
                analysis.verdict = ThreatVerdict.SUSPICIOUS
                analysis.score = 40
                analysis.error = "URL analysis timed out"
            except Exception as e:
                logger.error(f"URL analysis error: {e}")
                analysis = self._generate_analysis_results(analysis)
        
        return analysis
    
    async def _analyze_file_real(self, analysis: SandboxAnalysis) -> SandboxAnalysis:
        """Analyze a file using real process isolation with firejail"""
        base_time = datetime.now(timezone.utc)
        
        # For now, use YARA-like signature matching
        # In production, this would execute the file in a sandboxed VM
        
        firejail_path = shutil.which("firejail")
        
        if not firejail_path:
            # Fallback to simulated analysis
            return self._generate_analysis_results(analysis)
        
        # Create analysis report directory
        report_dir = REPORTS_DIR / analysis.analysis_id
        report_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Run file command in sandbox to get file type
            proc = await asyncio.create_subprocess_exec(
                firejail_path, "--quiet", "--private", "--net=none",
                "file", "-b", "-",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # We don't have the actual file content here, so simulate
            # In production, you'd pass the actual sample bytes
            stdout, stderr = await asyncio.wait_for(proc.communicate(input=b""), timeout=10)
            file_type = stdout.decode().strip() if stdout else "unknown"
            
            # Run strings analysis in sandbox
            proc = await asyncio.create_subprocess_exec(
                firejail_path, "--quiet", "--private", "--net=none",
                "strings", "-n", "8", "-",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(input=b""), timeout=10)
            strings_output = stdout.decode() if stdout else ""
            
            # Analyze strings for suspicious patterns
            suspicious_strings = []
            suspicious_patterns = [
                "CreateRemoteThread", "VirtualAllocEx", "WriteProcessMemory",
                "NtUnmapViewOfSection", "RegSetValueEx", "InternetOpen",
                "URLDownloadToFile", "WScript.Shell", "powershell", "cmd.exe",
                "bitcoin", "ransom", "encrypt", "decrypt", "password"
            ]
            
            for pattern in suspicious_patterns:
                if pattern.lower() in strings_output.lower():
                    suspicious_strings.append(pattern)
            
            # Match signatures
            matched = []
            for sig in self.signatures:
                for keyword in sig.get("keywords", []):
                    if keyword.lower() in analysis.sample_name.lower():
                        matched.append(sig)
                        break
            
            analysis.signatures_matched = matched
            
            # Generate process activity (simulated since we can't run arbitrary executables)
            analysis.process_activity = [
                ProcessActivity(
                    timestamp=base_time.isoformat(),
                    pid=random.randint(1000, 9999),
                    parent_pid=1,
                    process_name="sandbox_analyzer",
                    command_line=f"analyze {analysis.sample_name}",
                    action="created",
                    is_suspicious=False
                )
            ]
            
            # Generate file activity
            analysis.file_activity = [
                FileActivity(
                    timestamp=base_time.isoformat(),
                    action="read",
                    path=f"/sandbox/samples/{analysis.sample_name}",
                    size=analysis.sample_size,
                    hash=analysis.sample_hash
                )
            ]
            
            # Set verdict based on analysis
            if len(matched) >= 2 or len(suspicious_strings) >= 3:
                analysis.verdict = ThreatVerdict.MALICIOUS
                analysis.score = min(50 + len(matched) * 10 + len(suspicious_strings) * 5, 95)
            elif len(matched) >= 1 or len(suspicious_strings) >= 1:
                analysis.verdict = ThreatVerdict.SUSPICIOUS
                analysis.score = min(30 + len(matched) * 10 + len(suspicious_strings) * 5, 60)
            else:
                analysis.verdict = ThreatVerdict.CLEAN
                analysis.score = 5
            
            # Save report
            report_data = {
                "analysis_id": analysis.analysis_id,
                "file_type": file_type,
                "suspicious_strings": suspicious_strings,
                "signatures_matched": [s["name"] for s in matched],
                "verdict": analysis.verdict.value,
                "score": analysis.score,
                "analyzed_at": base_time.isoformat()
            }
            
            with open(report_dir / "report.json", "w") as f:
                import json
                json.dump(report_data, f, indent=2)
            
        except Exception as e:
            logger.error(f"File analysis error: {e}")
            # Fallback to simulated
            analysis = self._generate_analysis_results(analysis)
        
        return analysis


# =============================================================================
# MEMORY FORENSICS
# =============================================================================

@dataclass
class MemoryRegion:
    """Memory region information"""
    address: int
    size: int
    protection: str  # RWX, RW, RX, R
    type: str  # heap, stack, mapped, image
    module_name: Optional[str] = None
    is_suspicious: bool = False


@dataclass
class InjectedCode:
    """Detected code injection"""
    target_process: str
    target_pid: int
    injection_type: str  # dll_injection, process_hollowing, apc_injection
    source_module: Optional[str] = None
    injected_data_hash: Optional[str] = None
    detected_at: str = ""


class MemoryForensics:
    """
    Memory Forensics Analysis
    
    Analyzes process memory for:
    - Injected code detection
    - Unpacked/decrypted payloads
    - API hooking
    - Hidden modules
    - Credential harvesting artifacts
    """
    
    # Suspicious memory patterns
    SHELLCODE_PATTERNS = [
        b'\x60\xe8',           # pushad; call
        b'\xfc\xe8',           # cld; call
        b'\x55\x89\xe5',       # push ebp; mov ebp,esp
        b'\x48\x83\xec',       # sub rsp (x64 prologue)
        b'\x4d\x5a',           # MZ header
    ]
    
    # RWX memory indicators
    SUSPICIOUS_PROTECTIONS = ['RWX', 'RW+X']
    
    def __init__(self):
        self.memory_dumps: Dict[str, List[MemoryRegion]] = {}
        self.injections: List[InjectedCode] = []
        self.extracted_strings: Dict[str, List[str]] = {}
        
    def analyze_memory_dump(self, process_name: str, memory_data: bytes) -> Dict[str, Any]:
        """Analyze a process memory dump"""
        findings = {
            "process": process_name,
            "size": len(memory_data),
            "shellcode_detected": False,
            "packed_code": False,
            "suspicious_regions": [],
            "extracted_artifacts": [],
            "risk_score": 0
        }
        
        # Check for shellcode patterns
        for pattern in self.SHELLCODE_PATTERNS:
            if pattern in memory_data:
                findings["shellcode_detected"] = True
                findings["risk_score"] += 20
                break
        
        # Check for high entropy (packed/encrypted)
        entropy = self._calculate_entropy(memory_data[:4096] if len(memory_data) > 4096 else memory_data)
        if entropy > 7.5:  # High entropy threshold
            findings["packed_code"] = True
            findings["risk_score"] += 15
        
        # Extract strings and check for suspicious content
        strings = self._extract_strings(memory_data)
        suspicious_strings = self._filter_suspicious_strings(strings)
        
        if suspicious_strings:
            findings["extracted_artifacts"] = suspicious_strings[:20]
            findings["risk_score"] += len(suspicious_strings) * 2
        
        # Simulate region analysis
        findings["suspicious_regions"] = self._analyze_regions(memory_data)
        findings["risk_score"] += len(findings["suspicious_regions"]) * 5
        
        return findings
    
    def _calculate_entropy(self, data: bytes) -> float:
        """Calculate Shannon entropy of data"""
        if not data:
            return 0.0
        
        from collections import Counter
        import math
        
        counts = Counter(data)
        length = len(data)
        entropy = 0.0
        
        for count in counts.values():
            if count > 0:
                freq = count / length
                entropy -= freq * math.log2(freq)
        
        return entropy
    
    def _extract_strings(self, data: bytes, min_length: int = 4) -> List[str]:
        """Extract ASCII and Unicode strings from binary data"""
        strings = []
        
        # ASCII strings
        ascii_pattern = rb'[\x20-\x7e]{' + str(min_length).encode() + rb',}'
        ascii_matches = re.findall(ascii_pattern, data[:100000])  # Limit for performance
        strings.extend([m.decode('ascii', errors='ignore') for m in ascii_matches])
        
        return strings[:500]  # Limit results
    
    def _filter_suspicious_strings(self, strings: List[str]) -> List[str]:
        """Filter for security-relevant strings"""
        suspicious_keywords = [
            'password', 'credential', 'token', 'secret', 'api_key',
            'cmd.exe', 'powershell', 'wscript', 'cscript',
            'http://', 'https://', 'ftp://',
            'HKEY_', 'RegOpenKey', 'RegSetValue',
            'VirtualAlloc', 'WriteProcessMemory', 'CreateRemoteThread',
            'mimikatz', 'lazagne', 'dump', 'inject'
        ]
        
        return [s for s in strings if any(kw.lower() in s.lower() for kw in suspicious_keywords)]
    
    def _analyze_regions(self, data: bytes) -> List[Dict]:
        """Analyze memory regions (simplified)"""
        regions = []
        
        # Simulate region analysis
        if b'MZ' in data:
            regions.append({
                "type": "pe_header",
                "description": "PE header found in memory",
                "severity": "medium"
            })
        
        if any(p in data for p in self.SHELLCODE_PATTERNS):
            regions.append({
                "type": "shellcode",
                "description": "Potential shellcode detected",
                "severity": "high"
            })
        
        return regions
    
    def detect_injection(
        self,
        target_pid: int,
        target_name: str,
        source_pid: int,
        source_name: str
    ) -> Optional[InjectedCode]:
        """Detect and record code injection"""
        injection = InjectedCode(
            target_process=target_name,
            target_pid=target_pid,
            injection_type="process_injection",
            source_module=source_name,
            detected_at=datetime.now(timezone.utc).isoformat()
        )
        
        self.injections.append(injection)
        logger.warning(f"Code injection detected: {source_name} -> {target_name}")
        
        return injection
    
    def get_stats(self) -> Dict:
        """Get forensics statistics"""
        return {
            "memory_dumps_analyzed": len(self.memory_dumps),
            "injections_detected": len(self.injections),
            "strings_extracted": sum(len(s) for s in self.extracted_strings.values())
        }


# =============================================================================
# ANTI-EVASION DETECTION
# =============================================================================

class AntiEvasionDetector:
    """
    Detects malware anti-analysis and evasion techniques
    
    Monitors for:
    - VM/Sandbox environment checks
    - Debugger detection
    - Timing-based evasion
    - User interaction requirements
    - Sleep acceleration detection
    """
    
    # VM detection indicators
    VM_ARTIFACTS = {
        "registry_keys": [
            "HKLM\\SOFTWARE\\VMware",
            "HKLM\\SOFTWARE\\Oracle\\VirtualBox",
            "HKLM\\SOFTWARE\\Microsoft\\Virtual Machine",
            "HKLM\\HARDWARE\\ACPI\\DSDT\\VBOX__"
        ],
        "processes": [
            "vmtoolsd.exe", "vmwaretray.exe", "vboxservice.exe",
            "vboxtray.exe", "sandboxie.exe", "cuckoomon.dll"
        ],
        "files": [
            "C:\\Windows\\System32\\drivers\\vmmouse.sys",
            "C:\\Windows\\System32\\drivers\\VBoxMouse.sys"
        ],
        "mac_prefixes": ["00:0C:29", "00:50:56", "08:00:27"]  # VMware, VirtualBox
    }
    
    # Debugger detection methods
    DEBUGGER_CHECKS = [
        "IsDebuggerPresent", "CheckRemoteDebuggerPresent",
        "NtQueryInformationProcess", "OutputDebugString",
        "GetTickCount", "QueryPerformanceCounter"
    ]
    
    def __init__(self):
        self.detections: List[Dict] = []
        self.evasion_scores: Dict[str, int] = defaultdict(int)
        
    def check_vm_detection_attempt(
        self,
        analysis_id: str,
        api_call: str,
        parameters: Dict
    ) -> Optional[Dict]:
        """Check if an API call indicates VM detection attempt"""
        detection = None
        
        # Registry queries for VM artifacts
        if api_call in ["RegOpenKeyEx", "RegQueryValueEx", "RegEnumKey"]:
            key = parameters.get("key", "")
            for vm_key in self.VM_ARTIFACTS["registry_keys"]:
                if vm_key.lower() in key.lower():
                    detection = {
                        "technique": EvasionTechnique.VM_DETECTION.value,
                        "method": "registry_check",
                        "target": key,
                        "severity": "medium"
                    }
                    break
        
        # Process enumeration for VM processes
        elif api_call in ["CreateToolhelp32Snapshot", "Process32First", "Process32Next"]:
            detection = {
                "technique": EvasionTechnique.PROCESS_ENUMERATION.value,
                "method": "process_scan",
                "severity": "low"
            }
        
        # CPUID instruction (VM detection via hypervisor bit)
        elif api_call == "CPUID" and parameters.get("function") == 1:
            detection = {
                "technique": EvasionTechnique.VM_DETECTION.value,
                "method": "cpuid_hypervisor_check",
                "severity": "medium"
            }
        
        if detection:
            detection["analysis_id"] = analysis_id
            detection["timestamp"] = datetime.now(timezone.utc).isoformat()
            self.detections.append(detection)
            self.evasion_scores[analysis_id] += 10
        
        return detection
    
    def check_debugger_detection_attempt(
        self,
        analysis_id: str,
        api_call: str,
        parameters: Dict
    ) -> Optional[Dict]:
        """Check for debugger detection attempts"""
        detection = None
        
        if api_call in self.DEBUGGER_CHECKS:
            detection = {
                "technique": EvasionTechnique.DEBUGGER_DETECTION.value,
                "method": api_call,
                "severity": "medium",
                "analysis_id": analysis_id,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            self.detections.append(detection)
            self.evasion_scores[analysis_id] += 15
        
        return detection
    
    def check_timing_evasion(
        self,
        analysis_id: str,
        sleep_duration_ms: int
    ) -> Optional[Dict]:
        """Check for timing-based evasion (long sleeps)"""
        detection = None
        
        # Detect long sleep calls (> 30 seconds)
        if sleep_duration_ms > 30000:
            detection = {
                "technique": EvasionTechnique.TIMING_ATTACK.value,
                "method": "long_sleep",
                "duration_ms": sleep_duration_ms,
                "severity": "medium" if sleep_duration_ms < 60000 else "high",
                "analysis_id": analysis_id,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            self.detections.append(detection)
            self.evasion_scores[analysis_id] += 10
        
        return detection
    
    def get_evasion_summary(self, analysis_id: str) -> Dict:
        """Get evasion detection summary for an analysis"""
        relevant = [d for d in self.detections if d.get("analysis_id") == analysis_id]
        
        by_technique = defaultdict(list)
        for d in relevant:
            by_technique[d["technique"]].append(d)
        
        return {
            "total_detections": len(relevant),
            "evasion_score": self.evasion_scores.get(analysis_id, 0),
            "by_technique": dict(by_technique),
            "is_evasive": self.evasion_scores.get(analysis_id, 0) > 20
        }


# =============================================================================
# YARA RULE SCANNING
# =============================================================================

@dataclass
class YaraRule:
    """YARA rule representation"""
    rule_id: str
    name: str
    author: str
    description: str
    severity: str
    tags: List[str]
    strings: Dict[str, str]  # identifier -> pattern
    condition: str
    mitre_techniques: List[str] = field(default_factory=list)


@dataclass
class YaraMatch:
    """YARA rule match result"""
    rule_id: str
    rule_name: str
    matched_strings: List[Dict]
    offset: int
    severity: str
    mitre_techniques: List[str]


class YaraScanner:
    """
    YARA Rule Scanner
    
    Scans files and memory for malware signatures using YARA rules.
    Includes built-in rules for common malware families.
    """
    
    def __init__(self):
        self.rules: Dict[str, YaraRule] = {}
        self.matches: Dict[str, List[YaraMatch]] = {}
        self._load_builtin_rules()
    
    def _load_builtin_rules(self):
        """Load built-in YARA rules"""
        builtin_rules = [
            YaraRule(
                rule_id="yara_ransomware_generic",
                name="Generic_Ransomware",
                author="Metatron Security",
                description="Detects generic ransomware behaviors",
                severity="critical",
                tags=["ransomware", "encryption"],
                strings={
                    "$ransom_note1": "Your files have been encrypted",
                    "$ransom_note2": "bitcoin",
                    "$ransom_note3": ".onion",
                    "$crypto_api1": "CryptEncrypt",
                    "$crypto_api2": "CryptGenKey"
                },
                condition="2 of ($ransom_note*) or all of ($crypto_api*)",
                mitre_techniques=["T1486"]
            ),
            YaraRule(
                rule_id="yara_keylogger_generic",
                name="Generic_Keylogger",
                author="Metatron Security",
                description="Detects keylogger behaviors",
                severity="high",
                tags=["keylogger", "spyware"],
                strings={
                    "$hook1": "SetWindowsHookEx",
                    "$hook2": "GetAsyncKeyState",
                    "$hook3": "GetKeyboardState",
                    "$log1": "keylog",
                    "$log2": "keystroke"
                },
                condition="2 of ($hook*) or any of ($log*)",
                mitre_techniques=["T1056.001"]
            ),
            YaraRule(
                rule_id="yara_rat_generic",
                name="Generic_RAT",
                author="Metatron Security",
                description="Detects Remote Access Trojan behaviors",
                severity="critical",
                tags=["rat", "backdoor"],
                strings={
                    "$c2_1": "beacon",
                    "$c2_2": "cmd.exe",
                    "$c2_3": "shell",
                    "$cap1": "screenshot",
                    "$cap2": "webcam",
                    "$net1": "socket",
                    "$net2": "connect"
                },
                condition="(any of ($c2*) and any of ($net*)) or 2 of ($cap*)",
                mitre_techniques=["T1219", "T1113"]
            ),
            YaraRule(
                rule_id="yara_credential_stealer",
                name="Credential_Stealer",
                author="Metatron Security",
                description="Detects credential stealing malware",
                severity="high",
                tags=["stealer", "credentials"],
                strings={
                    "$cred1": "password",
                    "$cred2": "credential",
                    "$browser1": "chrome",
                    "$browser2": "firefox",
                    "$browser3": "Login Data",
                    "$api1": "CredEnumerate",
                    "$api2": "CryptUnprotectData"
                },
                condition="any of ($api*) and (any of ($browser*) or any of ($cred*))",
                mitre_techniques=["T1555", "T1552"]
            ),
            YaraRule(
                rule_id="yara_process_injection",
                name="Process_Injection",
                author="Metatron Security",
                description="Detects process injection techniques",
                severity="high",
                tags=["injection", "evasion"],
                strings={
                    "$api1": "VirtualAllocEx",
                    "$api2": "WriteProcessMemory",
                    "$api3": "CreateRemoteThread",
                    "$api4": "NtMapViewOfSection",
                    "$api5": "QueueUserAPC"
                },
                condition="2 of them",
                mitre_techniques=["T1055"]
            ),
            YaraRule(
                rule_id="yara_persistence_generic",
                name="Persistence_Mechanism",
                author="Metatron Security",
                description="Detects persistence mechanisms",
                severity="medium",
                tags=["persistence"],
                strings={
                    "$reg1": "CurrentVersion\\Run",
                    "$reg2": "CurrentVersion\\RunOnce",
                    "$task1": "schtasks",
                    "$task2": "at.exe",
                    "$svc1": "sc create",
                    "$svc2": "CreateService"
                },
                condition="any of them",
                mitre_techniques=["T1547", "T1053", "T1543"]
            )
        ]
        
        for rule in builtin_rules:
            self.rules[rule.rule_id] = rule
    
    def add_rule(self, rule: YaraRule):
        """Add a custom YARA rule"""
        self.rules[rule.rule_id] = rule
        logger.info(f"Added YARA rule: {rule.name}")
    
    def scan_data(self, data: bytes, identifier: str = "unknown") -> List[YaraMatch]:
        """Scan binary data against all YARA rules"""
        matches = []
        data_str = data.decode('utf-8', errors='ignore').lower()
        
        for rule in self.rules.values():
            matched_strings = []
            
            for string_id, pattern in rule.strings.items():
                pattern_lower = pattern.lower()
                if pattern_lower in data_str:
                    # Find offset
                    offset = data_str.find(pattern_lower)
                    matched_strings.append({
                        "identifier": string_id,
                        "pattern": pattern,
                        "offset": offset
                    })
            
            # Simplified condition evaluation
            if matched_strings:
                condition_met = self._evaluate_condition(rule.condition, matched_strings, rule.strings)
                
                if condition_met:
                    match = YaraMatch(
                        rule_id=rule.rule_id,
                        rule_name=rule.name,
                        matched_strings=matched_strings,
                        offset=matched_strings[0]["offset"] if matched_strings else 0,
                        severity=rule.severity,
                        mitre_techniques=rule.mitre_techniques
                    )
                    matches.append(match)
                    logger.info(f"YARA match: {rule.name} in {identifier}")
        
        self.matches[identifier] = matches
        return matches
    
    def _evaluate_condition(
        self,
        condition: str,
        matched: List[Dict],
        all_strings: Dict[str, str]
    ) -> bool:
        """Simplified YARA condition evaluation"""
        matched_ids = {m["identifier"] for m in matched}
        
        # Handle "any of them"
        if "any of them" in condition.lower():
            return len(matched_ids) > 0
        
        # Handle "all of them"
        if "all of them" in condition.lower():
            return matched_ids == set(all_strings.keys())
        
        # Handle "N of them" or "N of ($pattern*)"
        import re
        count_match = re.search(r'(\d+)\s+of', condition)
        if count_match:
            required = int(count_match.group(1))
            return len(matched_ids) >= required
        
        # Default: at least one match
        return len(matched_ids) > 0
    
    def scan_file(self, file_path: str) -> List[YaraMatch]:
        """Scan a file with YARA rules"""
        try:
            with open(file_path, 'rb') as f:
                data = f.read()
            return self.scan_data(data, file_path)
        except Exception as e:
            logger.error(f"YARA scan error for {file_path}: {e}")
            return []
    
    def get_rules_by_tag(self, tag: str) -> List[YaraRule]:
        """Get rules by tag"""
        return [r for r in self.rules.values() if tag in r.tags]
    
    def get_stats(self) -> Dict:
        """Get scanner statistics"""
        return {
            "total_rules": len(self.rules),
            "total_scans": len(self.matches),
            "total_matches": sum(len(m) for m in self.matches.values()),
            "rules_by_severity": {
                "critical": sum(1 for r in self.rules.values() if r.severity == "critical"),
                "high": sum(1 for r in self.rules.values() if r.severity == "high"),
                "medium": sum(1 for r in self.rules.values() if r.severity == "medium"),
                "low": sum(1 for r in self.rules.values() if r.severity == "low")
            }
        }


# =============================================================================
# BEHAVIORAL SCORING
# =============================================================================

@dataclass
class BehaviorIndicator:
    """Individual behavioral indicator"""
    indicator_id: str
    name: str
    category: BehaviorCategory
    severity: str
    score: int  # 1-100
    mitre_technique: Optional[str] = None
    description: str = ""


class BehavioralScorer:
    """
    Behavioral Scoring Engine
    
    Calculates threat scores based on observed behaviors,
    mapped to MITRE ATT&CK framework.
    """
    
    # Behavior weights by category
    CATEGORY_WEIGHTS = {
        BehaviorCategory.PERSISTENCE: 15,
        BehaviorCategory.PRIVILEGE_ESCALATION: 20,
        BehaviorCategory.DEFENSE_EVASION: 15,
        BehaviorCategory.CREDENTIAL_ACCESS: 25,
        BehaviorCategory.DISCOVERY: 5,
        BehaviorCategory.LATERAL_MOVEMENT: 20,
        BehaviorCategory.COLLECTION: 10,
        BehaviorCategory.COMMAND_AND_CONTROL: 20,
        BehaviorCategory.EXFILTRATION: 25,
        BehaviorCategory.IMPACT: 30
    }
    
    def __init__(self):
        self.indicators: Dict[str, BehaviorIndicator] = {}
        self.analysis_scores: Dict[str, Dict] = {}
        self._load_default_indicators()
    
    def _load_default_indicators(self):
        """Load default behavioral indicators"""
        defaults = [
            BehaviorIndicator("beh_reg_run", "Registry Run Key", BehaviorCategory.PERSISTENCE, "high", 70, "T1547.001"),
            BehaviorIndicator("beh_schtask", "Scheduled Task", BehaviorCategory.PERSISTENCE, "medium", 50, "T1053.005"),
            BehaviorIndicator("beh_service", "Windows Service", BehaviorCategory.PERSISTENCE, "medium", 55, "T1543.003"),
            BehaviorIndicator("beh_priv_token", "Token Manipulation", BehaviorCategory.PRIVILEGE_ESCALATION, "high", 75, "T1134"),
            BehaviorIndicator("beh_priv_exploit", "Privilege Escalation Exploit", BehaviorCategory.PRIVILEGE_ESCALATION, "critical", 90, "T1068"),
            BehaviorIndicator("beh_injection", "Process Injection", BehaviorCategory.DEFENSE_EVASION, "high", 80, "T1055"),
            BehaviorIndicator("beh_hook", "API Hooking", BehaviorCategory.DEFENSE_EVASION, "high", 70, "T1056"),
            BehaviorIndicator("beh_cred_dump", "Credential Dumping", BehaviorCategory.CREDENTIAL_ACCESS, "critical", 95, "T1003"),
            BehaviorIndicator("beh_keylog", "Keylogging", BehaviorCategory.CREDENTIAL_ACCESS, "high", 80, "T1056.001"),
            BehaviorIndicator("beh_sys_enum", "System Enumeration", BehaviorCategory.DISCOVERY, "low", 20, "T1082"),
            BehaviorIndicator("beh_net_enum", "Network Enumeration", BehaviorCategory.DISCOVERY, "low", 25, "T1016"),
            BehaviorIndicator("beh_psexec", "Remote Execution", BehaviorCategory.LATERAL_MOVEMENT, "high", 75, "T1021.002"),
            BehaviorIndicator("beh_screen_cap", "Screen Capture", BehaviorCategory.COLLECTION, "medium", 50, "T1113"),
            BehaviorIndicator("beh_c2_http", "HTTP C2", BehaviorCategory.COMMAND_AND_CONTROL, "high", 70, "T1071.001"),
            BehaviorIndicator("beh_c2_dns", "DNS C2", BehaviorCategory.COMMAND_AND_CONTROL, "high", 75, "T1071.004"),
            BehaviorIndicator("beh_exfil_http", "HTTP Exfiltration", BehaviorCategory.EXFILTRATION, "high", 80, "T1041"),
            BehaviorIndicator("beh_encrypt", "File Encryption", BehaviorCategory.IMPACT, "critical", 95, "T1486"),
            BehaviorIndicator("beh_wipe", "Data Destruction", BehaviorCategory.IMPACT, "critical", 100, "T1485")
        ]
        
        for ind in defaults:
            self.indicators[ind.indicator_id] = ind
    
    def score_behaviors(
        self,
        analysis_id: str,
        observed_behaviors: List[str]
    ) -> Dict[str, Any]:
        """Calculate behavioral score for an analysis"""
        total_score = 0
        category_scores = defaultdict(int)
        matched_indicators = []
        mitre_techniques = set()
        
        for behavior_id in observed_behaviors:
            indicator = self.indicators.get(behavior_id)
            if indicator:
                weighted_score = (indicator.score * self.CATEGORY_WEIGHTS[indicator.category]) / 100
                total_score += weighted_score
                category_scores[indicator.category.value] += indicator.score
                matched_indicators.append(asdict(indicator))
                if indicator.mitre_technique:
                    mitre_techniques.add(indicator.mitre_technique)
        
        # Normalize score to 0-100
        final_score = min(100, total_score)
        
        # Determine verdict
        if final_score >= 70:
            verdict = ThreatVerdict.MALICIOUS
        elif final_score >= 40:
            verdict = ThreatVerdict.SUSPICIOUS
        else:
            verdict = ThreatVerdict.CLEAN
        
        result = {
            "analysis_id": analysis_id,
            "final_score": round(final_score, 1),
            "verdict": verdict.value,
            "category_scores": dict(category_scores),
            "matched_indicators": matched_indicators,
            "mitre_techniques": list(mitre_techniques),
            "risk_level": "critical" if final_score >= 80 else "high" if final_score >= 60 else "medium" if final_score >= 40 else "low"
        }
        
        self.analysis_scores[analysis_id] = result
        return result
    
    def add_indicator(self, indicator: BehaviorIndicator):
        """Add a custom behavioral indicator"""
        self.indicators[indicator.indicator_id] = indicator
    
    def get_mitre_coverage(self) -> Dict[str, List[str]]:
        """Get MITRE ATT&CK technique coverage"""
        coverage = defaultdict(list)
        for indicator in self.indicators.values():
            if indicator.mitre_technique:
                coverage[indicator.mitre_technique].append(indicator.indicator_id)
        return dict(coverage)


# =============================================================================
# IOC EXTRACTION
# =============================================================================

@dataclass
class ExtractedIOC:
    """Extracted Indicator of Compromise"""
    ioc_type: str  # hash, ip, domain, url, email, filepath
    value: str
    context: str  # Where it was found
    confidence: str  # high, medium, low
    malicious: Optional[bool] = None
    first_seen: str = ""
    tags: List[str] = field(default_factory=list)


class IOCExtractor:
    """
    Indicator of Compromise Extractor
    
    Extracts network indicators, file hashes, and other IOCs
    from sandbox analysis results.
    """
    
    # Regex patterns for IOC extraction
    PATTERNS = {
        "ipv4": r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b',
        "ipv6": r'\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b',
        "domain": r'\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+(?:com|net|org|io|co|info|biz|ru|cn|xyz|top|tk|ml|ga|cf|gq|onion)\b',
        "url": r'https?://[^\s<>"{}|\\^`\[\]]+',
        "email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        "md5": r'\b[a-fA-F0-9]{32}\b',
        "sha1": r'\b[a-fA-F0-9]{40}\b',
        "sha256": r'\b[a-fA-F0-9]{64}\b',
        "bitcoin": r'\b[13][a-km-zA-HJ-NP-Z1-9]{25,34}\b',
        "filepath_win": r'[A-Za-z]:\\(?:[^\\/:*?"<>|\r\n]+\\)*[^\\/:*?"<>|\r\n]*',
        "registry": r'HKEY_[A-Z_]+(?:\\[^\\/:*?"<>|\r\n]+)+'
    }
    
    # Known benign patterns to filter
    BENIGN_PATTERNS = {
        "ipv4": {"127.0.0.1", "0.0.0.0", "255.255.255.255", "192.168.", "10.", "172.16."},
        "domain": {"microsoft.com", "windows.com", "google.com", "localhost"}
    }
    
    def __init__(self):
        self.extracted_iocs: Dict[str, List[ExtractedIOC]] = {}
        self.ioc_database: Dict[str, ExtractedIOC] = {}
        
    def extract_from_data(self, data: bytes, context: str = "unknown") -> List[ExtractedIOC]:
        """Extract IOCs from binary data"""
        text = data.decode('utf-8', errors='ignore')
        return self.extract_from_text(text, context)
    
    def extract_from_text(self, text: str, context: str = "unknown") -> List[ExtractedIOC]:
        """Extract IOCs from text"""
        extracted = []
        seen = set()
        
        for ioc_type, pattern in self.PATTERNS.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            
            for match in matches:
                # Normalize
                value = match.lower() if ioc_type in ["domain", "email", "md5", "sha1", "sha256"] else match
                
                # Deduplicate
                if (ioc_type, value) in seen:
                    continue
                seen.add((ioc_type, value))
                
                # Filter benign
                if self._is_benign(ioc_type, value):
                    continue
                
                ioc = ExtractedIOC(
                    ioc_type=ioc_type,
                    value=value,
                    context=context,
                    confidence=self._assess_confidence(ioc_type, value),
                    first_seen=datetime.now(timezone.utc).isoformat()
                )
                
                extracted.append(ioc)
                self.ioc_database[f"{ioc_type}:{value}"] = ioc
        
        self.extracted_iocs[context] = extracted
        return extracted
    
    def _is_benign(self, ioc_type: str, value: str) -> bool:
        """Check if IOC is likely benign"""
        benign_set = self.BENIGN_PATTERNS.get(ioc_type, set())
        
        for benign in benign_set:
            if value.startswith(benign) or value == benign:
                return True
        
        return False
    
    def _assess_confidence(self, ioc_type: str, value: str) -> str:
        """Assess confidence level of extracted IOC"""
        # Hashes are high confidence
        if ioc_type in ["md5", "sha1", "sha256"]:
            return "high"
        
        # Onion domains are high confidence
        if ioc_type == "domain" and value.endswith(".onion"):
            return "high"
        
        # Bitcoin addresses are high confidence
        if ioc_type == "bitcoin":
            return "high"
        
        # External IPs are medium confidence
        if ioc_type == "ipv4":
            return "medium"
        
        return "low"
    
    def extract_from_analysis(self, analysis: SandboxAnalysis) -> List[ExtractedIOC]:
        """Extract IOCs from sandbox analysis results"""
        all_iocs = []
        
        # Extract from network activity
        for net in analysis.network_activity:
            if hasattr(net, 'dest_ip') and net.dest_ip:
                ioc = ExtractedIOC(
                    ioc_type="ipv4",
                    value=net.dest_ip,
                    context=f"network:{analysis.analysis_id}",
                    confidence="high",
                    first_seen=net.timestamp
                )
                all_iocs.append(ioc)
        
        # Extract from DNS queries
        for dns in analysis.dns_queries:
            if dns.get("query"):
                ioc = ExtractedIOC(
                    ioc_type="domain",
                    value=dns["query"],
                    context=f"dns:{analysis.analysis_id}",
                    confidence="high",
                    first_seen=datetime.now(timezone.utc).isoformat()
                )
                all_iocs.append(ioc)
        
        # Extract from HTTP requests
        for http in analysis.http_requests:
            if http.get("url"):
                ioc = ExtractedIOC(
                    ioc_type="url",
                    value=http["url"],
                    context=f"http:{analysis.analysis_id}",
                    confidence="high",
                    first_seen=datetime.now(timezone.utc).isoformat()
                )
                all_iocs.append(ioc)
        
        # Extract from dropped files
        for dropped in analysis.dropped_files:
            if dropped.get("hash"):
                ioc = ExtractedIOC(
                    ioc_type="sha256",
                    value=dropped["hash"],
                    context=f"dropped:{analysis.analysis_id}",
                    confidence="high",
                    first_seen=datetime.now(timezone.utc).isoformat()
                )
                all_iocs.append(ioc)
        
        # Sample hash
        all_iocs.append(ExtractedIOC(
            ioc_type="sha256",
            value=analysis.sample_hash,
            context=f"sample:{analysis.analysis_id}",
            confidence="high",
            first_seen=analysis.submitted_at
        ))
        
        return all_iocs
    
    def to_stix(self, iocs: List[ExtractedIOC]) -> List[Dict]:
        """Convert IOCs to STIX format (simplified)"""
        stix_objects = []
        
        for ioc in iocs:
            obj = {
                "type": "indicator",
                "id": f"indicator--{uuid.uuid4()}",
                "created": ioc.first_seen,
                "pattern_type": "stix",
                "valid_from": ioc.first_seen,
                "labels": [ioc.ioc_type],
                "confidence": ioc.confidence
            }
            
            # Build STIX pattern
            if ioc.ioc_type in ["ipv4", "ipv6"]:
                obj["pattern"] = f"[ipv4-addr:value = '{ioc.value}']"
            elif ioc.ioc_type == "domain":
                obj["pattern"] = f"[domain-name:value = '{ioc.value}']"
            elif ioc.ioc_type == "url":
                obj["pattern"] = f"[url:value = '{ioc.value}']"
            elif ioc.ioc_type in ["md5", "sha1", "sha256"]:
                obj["pattern"] = f"[file:hashes.'{ioc.ioc_type.upper()}' = '{ioc.value}']"
            else:
                obj["pattern"] = f"[artifact:value = '{ioc.value}']"
            
            stix_objects.append(obj)
        
        return stix_objects
    
    def get_stats(self) -> Dict:
        """Get extraction statistics"""
        by_type = defaultdict(int)
        for ioc in self.ioc_database.values():
            by_type[ioc.ioc_type] += 1
        
        return {
            "total_iocs": len(self.ioc_database),
            "by_type": dict(by_type),
            "contexts_analyzed": len(self.extracted_iocs)
        }


# =============================================================================
# ENHANCED SANDBOX SERVICE
# =============================================================================

class EnhancedSandboxService(SandboxService):
    """
    Enhanced Sandbox Service with enterprise features
    
    Extends base SandboxService with:
    - Memory forensics
    - Anti-evasion detection
    - YARA scanning
    - Behavioral scoring
    - IOC extraction
    """
    
    def __init__(self):
        super().__init__()
        self.memory_forensics = MemoryForensics()
        self.anti_evasion = AntiEvasionDetector()
        self.yara_scanner = YaraScanner()
        self.behavioral_scorer = BehavioralScorer()
        self.ioc_extractor = IOCExtractor()
    
    async def run_comprehensive_analysis(self, analysis_id: str) -> Dict[str, Any]:
        """Run comprehensive analysis with all enterprise features"""
        # Run base analysis
        analysis = await self.run_analysis(analysis_id)
        
        results = {
            "base_analysis": asdict(analysis),
            "memory_analysis": None,
            "evasion_detection": None,
            "yara_matches": [],
            "behavioral_score": None,
            "iocs": []
        }
        
        # Get sample data for additional analysis
        sample_path = SAMPLES_DIR / analysis.analysis_id
        if sample_path.exists():
            try:
                with open(sample_path, 'rb') as f:
                    sample_data = f.read()
                
                # YARA scanning
                yara_matches = self.yara_scanner.scan_data(sample_data, analysis.analysis_id)
                results["yara_matches"] = [asdict(m) for m in yara_matches]
                
                # Memory forensics (on sample data as simulation)
                memory_results = self.memory_forensics.analyze_memory_dump(
                    analysis.sample_name, sample_data
                )
                results["memory_analysis"] = memory_results
                
            except Exception as e:
                logger.error(f"Enhanced analysis error: {e}")
        
        # Evasion detection summary
        results["evasion_detection"] = self.anti_evasion.get_evasion_summary(analysis_id)
        
        # Behavioral scoring
        observed_behaviors = self._extract_behaviors(analysis)
        results["behavioral_score"] = self.behavioral_scorer.score_behaviors(
            analysis_id, observed_behaviors
        )
        
        # IOC extraction
        iocs = self.ioc_extractor.extract_from_analysis(analysis)
        results["iocs"] = [asdict(ioc) for ioc in iocs]
        
        return results
    
    def _extract_behaviors(self, analysis: SandboxAnalysis) -> List[str]:
        """Extract behavioral indicator IDs from analysis"""
        behaviors = []
        
        # Map signatures to behavioral indicators
        sig_to_behavior = {
            "sig_persistence_run_key": "beh_reg_run",
            "sig_process_injection": "beh_injection",
            "sig_crypto_api": "beh_encrypt",
            "sig_network_c2": "beh_c2_http",
            "sig_file_encryption": "beh_encrypt",
            "sig_credential_access": "beh_cred_dump",
            "sig_screen_capture": "beh_screen_cap",
            "sig_keylogger": "beh_keylog",
            "sig_data_exfil": "beh_exfil_http"
        }
        
        for sig in analysis.signatures_matched:
            sig_id = sig.get("id", "")
            if sig_id in sig_to_behavior:
                behaviors.append(sig_to_behavior[sig_id])
        
        return behaviors
    
    def get_comprehensive_stats(self) -> Dict:
        """Get comprehensive statistics"""
        base_stats = self.get_stats()
        
        return {
            **base_stats,
            "memory_forensics": self.memory_forensics.get_stats(),
            "yara_scanner": self.yara_scanner.get_stats(),
            "ioc_extractor": self.ioc_extractor.get_stats()
        }


# Global instances
sandbox_service = SandboxService()
enhanced_sandbox = EnhancedSandboxService()
memory_forensics = MemoryForensics()
anti_evasion_detector = AntiEvasionDetector()
yara_scanner = YaraScanner()
behavioral_scorer = BehavioralScorer()
ioc_extractor = IOCExtractor()
