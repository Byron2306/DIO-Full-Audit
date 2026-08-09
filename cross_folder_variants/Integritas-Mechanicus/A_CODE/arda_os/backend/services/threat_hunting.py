"""
MITRE ATT&CK Threat Hunting Rules
=================================
Automated threat hunting based on MITRE ATT&CK framework.
Proactively scans for indicators of compromise (IOCs) and
tactics, techniques, and procedures (TTPs).
"""

import re
import os
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict

logger = logging.getLogger('seraph.threat_hunting')


@dataclass
class HuntingRule:
    """MITRE ATT&CK-based hunting rule"""
    rule_id: str
    name: str
    description: str
    mitre_technique: str
    mitre_tactic: str
    severity: str = "medium"
    data_sources: List[str] = field(default_factory=list)
    detection_logic: str = ""
    indicators: List[str] = field(default_factory=list)
    regex_patterns: List[str] = field(default_factory=list)
    process_names: List[str] = field(default_factory=list)
    command_patterns: List[str] = field(default_factory=list)
    network_indicators: Dict = field(default_factory=dict)
    file_indicators: List[str] = field(default_factory=list)
    registry_indicators: List[str] = field(default_factory=list)
    parent_process_patterns: Dict = field(default_factory=dict)
    behavioral_indicators: Dict = field(default_factory=dict)
    enabled: bool = True
    false_positive_notes: str = ""
    response_actions: List[str] = field(default_factory=list)


@dataclass
class HuntingMatch:
    """A match from threat hunting"""
    rule_id: str
    rule_name: str
    mitre_technique: str
    mitre_tactic: str
    severity: str
    matched_data: Dict
    matched_indicators: List[str]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    confidence: float = 0.0
    context: Dict = field(default_factory=dict)


class ThreatHuntingEngine:
    """
    MITRE ATT&CK-based threat hunting engine.
    
    Provides automated threat hunting across:
    - Process execution
    - Network traffic
    - File system
    - Registry (Windows)
    - Command line arguments
    """
    
    def __init__(self):
        self.rules: Dict[str, HuntingRule] = {}
        self.matches: List[HuntingMatch] = []
        self.stats = {
            "rules_loaded": 0,
            "hunts_executed": 0,
            "matches_found": 0,
            "false_positives": 0
        }
        
        # Load default rules
        self._load_default_rules()
        
        logger.info(f"Threat Hunting Engine initialized with {len(self.rules)} rules")
    
    def _load_default_rules(self):
        """Load MITRE ATT&CK-based hunting rules"""
        
        # ============================================================
        # CREDENTIAL ACCESS (TA0006)
        # ============================================================
        
        self.add_rule(HuntingRule(
            rule_id="hunt-T1003.001",
            name="LSASS Memory Credential Dumping",
            description="Detects attempts to dump credentials from LSASS memory",
            mitre_technique="T1003.001",
            mitre_tactic="TA0006",
            severity="critical",
            data_sources=["process", "command_line"],
            process_names=["mimikatz", "procdump", "lsass", "comsvcs"],
            command_patterns=[
                r"sekurlsa::logonpasswords",
                r"lsass\.dmp",
                r"lsass\.exe.*MiniDump",
                r"comsvcs\.dll.*MiniDump",
                r"procdump.*lsass",
                r"rundll32.*comsvcs.*MiniDump"
            ],
            response_actions=["terminate_process", "alert_critical", "isolate_host"],
            false_positive_notes="Legitimate memory dumps for debugging may trigger this"
        ))
        
        self.add_rule(HuntingRule(
            rule_id="hunt-T1003.002",
            name="SAM Database Credential Access",
            description="Detects attempts to extract credentials from SAM database",
            mitre_technique="T1003.002",
            mitre_tactic="TA0006",
            severity="critical",
            data_sources=["process", "file", "registry"],
            command_patterns=[
                r"reg\s+save\s+.*\\sam",
                r"reg\s+save\s+.*\\system",
                r"secretsdump",
                r"hashdump",
                r"pwdump"
            ],
            file_indicators=[
                r"\\Windows\\System32\\config\\SAM",
                r"\\Windows\\System32\\config\\SYSTEM"
            ],
            response_actions=["terminate_process", "alert_critical"],
            false_positive_notes="System backup tools may access these files"
        ))
        
        self.add_rule(HuntingRule(
            rule_id="hunt-T1558.003",
            name="Kerberoasting",
            description="Detects Kerberoasting attacks for service account credential theft",
            mitre_technique="T1558.003",
            mitre_tactic="TA0006",
            severity="high",
            data_sources=["process", "command_line", "network"],
            process_names=["rubeus", "invoke-kerberoast"],
            command_patterns=[
                r"kerberoast",
                r"GetUserSPNs",
                r"asreproast",
                r"rubeus.*kerberoast"
            ],
            response_actions=["alert_high", "investigate_user"]
        ))
        
        # ============================================================
        # EXECUTION (TA0002)
        # ============================================================
        
        self.add_rule(HuntingRule(
            rule_id="hunt-T1059.001",
            name="Malicious PowerShell Execution",
            description="Detects suspicious PowerShell command execution",
            mitre_technique="T1059.001",
            mitre_tactic="TA0002",
            severity="high",
            data_sources=["process", "command_line"],
            process_names=["powershell", "pwsh"],
            command_patterns=[
                r"-enc\s+[A-Za-z0-9+/=]{50,}",
                r"-encodedcommand",
                r"invoke-expression",
                r"iex\s*\(",
                r"downloadstring",
                r"webclient",
                r"bypass",
                r"-ep\s+bypass",
                r"-exec\s+bypass",
                r"hidden",
                r"-w\s+hidden",
                r"invoke-mimikatz",
                r"invoke-shellcode",
                r"powersploit"
            ],
            response_actions=["alert_high", "log_command"],
            false_positive_notes="Some legitimate admin scripts use encoded commands"
        ))
        
        self.add_rule(HuntingRule(
            rule_id="hunt-T1059.003",
            name="Suspicious Windows Command Shell",
            description="Detects suspicious cmd.exe usage patterns",
            mitre_technique="T1059.003",
            mitre_tactic="TA0002",
            severity="medium",
            data_sources=["process", "command_line"],
            process_names=["cmd"],
            command_patterns=[
                r"cmd.*\/c.*powershell",
                r"cmd.*\/c.*certutil",
                r"cmd.*\/c.*bitsadmin",
                r"cmd.*\/c.*mshta",
                r"cmd.*\/c.*regsvr32",
                r"whoami\s*/all",
                r"net\s+user\s+/add",
                r"net\s+localgroup\s+administrators"
            ],
            response_actions=["alert_medium", "log_command"]
        ))
        
        self.add_rule(HuntingRule(
            rule_id="hunt-T1047",
            name="WMI Execution",
            description="Detects suspicious WMI command execution",
            mitre_technique="T1047",
            mitre_tactic="TA0002",
            severity="medium",
            data_sources=["process", "command_line", "network"],
            process_names=["wmic", "wmiprvse"],
            command_patterns=[
                r"wmic.*process\s+call\s+create",
                r"wmic.*\/node:",
                r"invoke-wmimethod",
                r"get-wmiobject"
            ],
            network_indicators={"ports": [135, 445]},
            response_actions=["alert_medium", "log_command"]
        ))
        
        # ============================================================
        # PERSISTENCE (TA0003)
        # ============================================================
        
        self.add_rule(HuntingRule(
            rule_id="hunt-T1547.001",
            name="Registry Run Key Persistence",
            description="Detects modifications to Run/RunOnce registry keys",
            mitre_technique="T1547.001",
            mitre_tactic="TA0003",
            severity="high",
            data_sources=["registry", "command_line"],
            command_patterns=[
                r"reg\s+add.*\\Run",
                r"reg\s+add.*\\RunOnce",
                r"set-itemproperty.*\\Run",
                r"new-itemproperty.*\\Run"
            ],
            response_actions=["alert_high", "investigate_registry"]
        ))
        
        self.add_rule(HuntingRule(
            rule_id="hunt-T1053.005",
            name="Scheduled Task Persistence",
            description="Detects suspicious scheduled task creation",
            mitre_technique="T1053.005",
            mitre_tactic="TA0003",
            severity="high",
            data_sources=["process", "command_line"],
            process_names=["schtasks"],
            command_patterns=[
                r"schtasks.*\/create",
                r"schtasks.*\/run",
                r"register-scheduledjob",
                r"new-scheduledtask"
            ],
            response_actions=["alert_high", "investigate_task"]
        ))
        
        # ============================================================
        # DEFENSE EVASION (TA0005)
        # ============================================================
        
        self.add_rule(HuntingRule(
            rule_id="hunt-T1562.001",
            name="Security Tool Tampering",
            description="Detects attempts to disable security tools",
            mitre_technique="T1562.001",
            mitre_tactic="TA0005",
            severity="critical",
            data_sources=["process", "command_line", "service"],
            command_patterns=[
                r"sc\s+stop\s+.*defender",
                r"sc\s+stop\s+.*av",
                r"sc\s+stop\s+.*endpoint",
                r"set-mppreference.*disablerealtimemonitoring",
                r"taskkill.*msmpeng",
                r"net\s+stop\s+.*security"
            ],
            response_actions=["alert_critical", "restore_service"],
            false_positive_notes="Some software installers may stop AV temporarily"
        ))
        
        self.add_rule(HuntingRule(
            rule_id="hunt-T1070.001",
            name="Windows Event Log Clearing",
            description="Detects clearing of Windows event logs",
            mitre_technique="T1070.001",
            mitre_tactic="TA0005",
            severity="high",
            data_sources=["process", "command_line"],
            command_patterns=[
                r"wevtutil\s+cl",
                r"clear-eventlog",
                r"remove-eventlog"
            ],
            response_actions=["alert_high", "backup_logs"]
        ))
        
        self.add_rule(HuntingRule(
            rule_id="hunt-T1218.010",
            name="Regsvr32 Proxy Execution",
            description="Detects regsvr32 being used to proxy execution",
            mitre_technique="T1218.010",
            mitre_tactic="TA0005",
            severity="high",
            data_sources=["process", "command_line", "network"],
            process_names=["regsvr32"],
            command_patterns=[
                r"regsvr32.*\/s.*\/n.*\/u.*\/i:",
                r"regsvr32.*scrobj\.dll",
                r"regsvr32.*http"
            ],
            response_actions=["alert_high", "terminate_process"]
        ))
        
        # ============================================================
        # LATERAL MOVEMENT (TA0008)
        # ============================================================
        
        self.add_rule(HuntingRule(
            rule_id="hunt-T1021.002",
            name="SMB/Windows Admin Shares",
            description="Detects access to administrative shares for lateral movement",
            mitre_technique="T1021.002",
            mitre_tactic="TA0008",
            severity="high",
            data_sources=["network", "command_line"],
            command_patterns=[
                r"net\s+use.*\$",
                r"\\\\.*\\c\$",
                r"\\\\.*\\admin\$",
                r"\\\\.*\\ipc\$"
            ],
            network_indicators={"ports": [445, 139]},
            response_actions=["alert_high", "investigate_lateral"]
        ))
        
        self.add_rule(HuntingRule(
            rule_id="hunt-T1021.001",
            name="Remote Desktop Protocol",
            description="Detects suspicious RDP connections",
            mitre_technique="T1021.001",
            mitre_tactic="TA0008",
            severity="medium",
            data_sources=["network", "process"],
            process_names=["mstsc"],
            network_indicators={"ports": [3389]},
            response_actions=["alert_medium", "log_rdp"]
        ))
        
        self.add_rule(HuntingRule(
            rule_id="hunt-T1570",
            name="Lateral Tool Transfer",
            description="Detects tools being transferred laterally",
            mitre_technique="T1570",
            mitre_tactic="TA0008",
            severity="high",
            data_sources=["network", "file", "command_line"],
            command_patterns=[
                r"psexec.*-c",
                r"copy.*\\\\",
                r"xcopy.*\\\\",
                r"robocopy.*\\\\",
                r"scp.*@"
            ],
            file_indicators=[r"\.exe$", r"\.dll$", r"\.ps1$"],
            response_actions=["alert_high", "block_transfer"]
        ))
        
        # ============================================================
        # COMMAND AND CONTROL (TA0011)
        # ============================================================
        
        self.add_rule(HuntingRule(
            rule_id="hunt-T1071.001",
            name="Web-based C2 Communication",
            description="Detects potential C2 communication over HTTP/HTTPS",
            mitre_technique="T1071.001",
            mitre_tactic="TA0011",
            severity="high",
            data_sources=["network", "process"],
            command_patterns=[
                r"curl.*-d",
                r"wget.*--post",
                r"invoke-webrequest.*-method\s+post",
                r"webclient.*uploaddata"
            ],
            network_indicators={
                "ports": [80, 443, 8080, 8443],
                "suspicious_user_agents": ["python-requests", "curl", "wget"]
            },
            response_actions=["alert_high", "inspect_traffic"]
        ))
        
        self.add_rule(HuntingRule(
            rule_id="hunt-T1095",
            name="Non-Standard Port Communication",
            description="Detects communication on non-standard ports",
            mitre_technique="T1095",
            mitre_tactic="TA0011",
            severity="medium",
            data_sources=["network"],
            network_indicators={
                "suspicious_ports": [4444, 5555, 6666, 7777, 8888, 9999, 1337, 31337, 12345]
            },
            response_actions=["alert_medium", "block_connection"]
        ))
        
        # ============================================================
        # EXFILTRATION (TA0010)
        # ============================================================
        
        self.add_rule(HuntingRule(
            rule_id="hunt-T1567",
            name="Exfiltration to Cloud Storage",
            description="Detects potential data exfiltration to cloud services",
            mitre_technique="T1567",
            mitre_tactic="TA0010",
            severity="high",
            data_sources=["network", "process", "command_line"],
            command_patterns=[
                r"rclone.*copy",
                r"rclone.*sync",
                r"aws\s+s3\s+cp",
                r"gsutil\s+cp",
                r"azcopy"
            ],
            network_indicators={
                "domains": ["*.s3.amazonaws.com", "*.blob.core.windows.net", "*.storage.googleapis.com"]
            },
            response_actions=["alert_high", "block_exfil"]
        ))
        
        self.add_rule(HuntingRule(
            rule_id="hunt-T1048",
            name="Data Exfiltration Over Alternative Protocol",
            description="Detects data exfiltration over DNS, ICMP, etc.",
            mitre_technique="T1048",
            mitre_tactic="TA0010",
            severity="high",
            data_sources=["network"],
            command_patterns=[
                r"nslookup.*txt",
                r"dnscat",
                r"iodine"
            ],
            network_indicators={
                "protocols": ["DNS", "ICMP"],
                "large_dns_queries": True
            },
            response_actions=["alert_high", "block_dns_tunnel"]
        ))
        
        # ============================================================
        # DISCOVERY (TA0007)
        # ============================================================
        
        self.add_rule(HuntingRule(
            rule_id="hunt-T1087",
            name="Account Discovery",
            description="Detects enumeration of user accounts",
            mitre_technique="T1087",
            mitre_tactic="TA0007",
            severity="medium",
            data_sources=["process", "command_line"],
            command_patterns=[
                r"net\s+user",
                r"net\s+localgroup",
                r"net\s+group",
                r"get-localuser",
                r"get-aduser",
                r"dsquery\s+user",
                r"wmic\s+useraccount"
            ],
            response_actions=["log_recon"]
        ))
        
        self.add_rule(HuntingRule(
            rule_id="hunt-T1083",
            name="File and Directory Discovery",
            description="Detects suspicious file/directory enumeration",
            mitre_technique="T1083",
            mitre_tactic="TA0007",
            severity="low",
            data_sources=["process", "command_line"],
            command_patterns=[
                r"dir\s+\/s\s+.*\.doc",
                r"dir\s+\/s\s+.*\.pdf",
                r"dir\s+\/s\s+.*\.xls",
                r"findstr\s+\/s\s+password",
                r"find\s+-name.*password"
            ],
            response_actions=["log_recon"]
        ))
        
        self.add_rule(HuntingRule(
            rule_id="hunt-T1082",
            name="System Information Discovery",
            description="Detects enumeration of system information",
            mitre_technique="T1082",
            mitre_tactic="TA0007",
            severity="low",
            data_sources=["process", "command_line"],
            command_patterns=[
                r"systeminfo",
                r"hostname",
                r"ver\s*$",
                r"uname\s+-a",
                r"cat\s+/etc/os-release",
                r"wmic\s+os\s+get",
                r"get-computerinfo"
            ],
            response_actions=["log_recon"]
        ))
        
        self.add_rule(HuntingRule(
            rule_id="hunt-T1057",
            name="Process Discovery",
            description="Detects enumeration of running processes",
            mitre_technique="T1057",
            mitre_tactic="TA0007",
            severity="low",
            data_sources=["process", "command_line"],
            command_patterns=[
                r"tasklist",
                r"get-process",
                r"ps\s+aux",
                r"ps\s+-ef",
                r"wmic\s+process\s+list",
                r"query\s+process"
            ],
            response_actions=["log_recon"]
        ))
        
        self.add_rule(HuntingRule(
            rule_id="hunt-T1018",
            name="Remote System Discovery",
            description="Detects enumeration of remote systems",
            mitre_technique="T1018",
            mitre_tactic="TA0007",
            severity="medium",
            data_sources=["process", "command_line", "network"],
            command_patterns=[
                r"net\s+view",
                r"net\s+group.*domain",
                r"nltest\s+\/dclist",
                r"ping\s+-n\s+1\s+\d",
                r"arp\s+-a",
                r"nbtstat\s+-n",
                r"get-adcomputer",
                r"dsquery\s+computer"
            ],
            response_actions=["log_recon", "alert_medium"]
        ))
        
        # ============================================================
        # INITIAL ACCESS (TA0001)
        # ============================================================
        
        self.add_rule(HuntingRule(
            rule_id="hunt-T1566.001",
            name="Spearphishing Attachment Execution",
            description="Detects execution of files from common phishing locations",
            mitre_technique="T1566.001",
            mitre_tactic="TA0001",
            severity="high",
            data_sources=["process", "file", "command_line"],
            command_patterns=[
                r"\\AppData\\Local\\Temp\\.*\.(exe|scr|hta|js|vbs)",
                r"\\Downloads\\.*\.(exe|scr|hta|js|vbs)",
                r"\\INetCache\\.*\.(exe|scr|hta)",
                r"cmd.*\/c.*\.lnk",
                r"wscript.*\\temp\\",
                r"mshta.*http"
            ],
            file_indicators=[r".*\\Outlook.*\\.*\.(exe|scr)$", r".*\\Downloads\\.*\.(hta|js|vbs)$"],
            response_actions=["alert_high", "quarantine_file"]
        ))
        
        self.add_rule(HuntingRule(
            rule_id="hunt-T1190",
            name="Exploit Public-Facing Application",
            description="Detects potential exploitation of web applications",
            mitre_technique="T1190",
            mitre_tactic="TA0001",
            severity="critical",
            data_sources=["process", "network", "command_line"],
            command_patterns=[
                r"w3wp.*cmd.*\/c",
                r"httpd.*\/bin\/sh",
                r"java.*runtime.*exec",
                r"php.*system\(",
                r"node.*child_process",
                r"python.*subprocess"
            ],
            process_names=["w3wp", "httpd", "nginx", "apache", "tomcat"],
            network_indicators={"suspicious_response_codes": [500, 502, 503]},
            response_actions=["alert_critical", "isolate_system"]
        ))
        
        self.add_rule(HuntingRule(
            rule_id="hunt-T1133",
            name="External Remote Services Abuse",
            description="Detects suspicious remote service connections",
            mitre_technique="T1133",
            mitre_tactic="TA0001",
            severity="medium",
            data_sources=["network", "authentication"],
            network_indicators={
                "ports": [3389, 22, 5900, 5901, 5985, 5986],
                "suspicious_geolocations": True
            },
            response_actions=["alert_medium", "log_authentication"]
        ))
        
        self.add_rule(HuntingRule(
            rule_id="hunt-T1078",
            name="Valid Accounts - Suspicious Use",
            description="Detects suspicious use of valid credentials",
            mitre_technique="T1078",
            mitre_tactic="TA0001",
            severity="high",
            data_sources=["authentication", "process"],
            command_patterns=[
                r"runas\s+\/user",
                r"psexec.*-u\s+",
                r"net\s+use.*\/user",
                r"su\s+-\s+",
                r"sudo\s+-u"
            ],
            response_actions=["alert_high", "log_authentication"]
        ))
        
        # ============================================================
        # PRIVILEGE ESCALATION (TA0004)
        # ============================================================
        
        self.add_rule(HuntingRule(
            rule_id="hunt-T1134",
            name="Access Token Manipulation",
            description="Detects token manipulation for privilege escalation",
            mitre_technique="T1134",
            mitre_tactic="TA0004",
            severity="critical",
            data_sources=["process", "command_line"],
            command_patterns=[
                r"incognito.*list_tokens",
                r"incognito.*impersonate",
                r"invoke-tokenmanipulation",
                r"getsystem",
                r"tokenvator",
                r"maketoken"
            ],
            response_actions=["alert_critical", "terminate_process"]
        ))
        
        self.add_rule(HuntingRule(
            rule_id="hunt-T1055",
            name="Process Injection",
            description="Detects process injection techniques",
            mitre_technique="T1055",
            mitre_tactic="TA0004",
            severity="critical",
            data_sources=["process", "memory"],
            command_patterns=[
                r"invoke-reflectivepeinjection",
                r"invoke-shellcode",
                r"meterpreter.*migrate",
                r"inject.*pid",
                r"hollowing"
            ],
            process_names=["notepad", "explorer", "svchost", "rundll32"],
            response_actions=["alert_critical", "memory_dump", "terminate_process"]
        ))
        
        self.add_rule(HuntingRule(
            rule_id="hunt-T1068",
            name="Exploitation for Privilege Escalation",
            description="Detects local privilege escalation exploits",
            mitre_technique="T1068",
            mitre_tactic="TA0004",
            severity="critical",
            data_sources=["process", "command_line"],
            command_patterns=[
                r"juicypotato",
                r"rottenpotato",
                r"sweetpotato",
                r"printspoofer",
                r"godpotato",
                r"localpotato",
                r"pspy",
                r"linpeas",
                r"winpeas"
            ],
            response_actions=["alert_critical", "isolate_system"]
        ))
        
        self.add_rule(HuntingRule(
            rule_id="hunt-T1548.002",
            name="UAC Bypass",
            description="Detects User Account Control bypass attempts",
            mitre_technique="T1548.002",
            mitre_tactic="TA0004",
            severity="high",
            data_sources=["process", "command_line", "registry"],
            command_patterns=[
                r"fodhelper",
                r"eventvwr.*mmc",
                r"sdclt.*\/kickoffelev",
                r"computerdefaults",
                r"cmstp.*\/s",
                r"uacme"
            ],
            registry_indicators=[r"HKCU\\Software\\Classes\\ms-settings\\shell"],
            response_actions=["alert_high", "block_execution"]
        ))
        
        # ============================================================
        # COLLECTION (TA0009)
        # ============================================================
        
        self.add_rule(HuntingRule(
            rule_id="hunt-T1560",
            name="Archive Collected Data",
            description="Detects data compression for exfiltration staging",
            mitre_technique="T1560",
            mitre_tactic="TA0009",
            severity="medium",
            data_sources=["process", "file", "command_line"],
            command_patterns=[
                r"7z\s+a.*-p",
                r"rar\s+a.*-hp",
                r"zip.*-e",
                r"tar.*czf",
                r"compress-archive",
                r"makecab"
            ],
            file_indicators=[r"\.7z$", r"\.rar$", r"\.zip$", r"\.tar\.gz$"],
            response_actions=["alert_medium", "log_file_activity"]
        ))
        
        self.add_rule(HuntingRule(
            rule_id="hunt-T1113",
            name="Screen Capture",
            description="Detects screen capture activities",
            mitre_technique="T1113",
            mitre_tactic="TA0009",
            severity="medium",
            data_sources=["process", "command_line"],
            command_patterns=[
                r"screenshot",
                r"nircmd.*savescreenshot",
                r"import\s+-window\s+root",
                r"scrot",
                r"gnome-screenshot",
                r"psr\.exe"
            ],
            response_actions=["alert_medium", "log_collection"]
        ))
        
        self.add_rule(HuntingRule(
            rule_id="hunt-T1123",
            name="Audio Capture",
            description="Detects audio recording activities",
            mitre_technique="T1123",
            mitre_tactic="TA0009",
            severity="high",
            data_sources=["process", "command_line"],
            command_patterns=[
                r"ffmpeg.*-f\s+alsa",
                r"ffmpeg.*-f\s+dshow",
                r"sox.*-d",
                r"arecord",
                r"soundrecorder"
            ],
            response_actions=["alert_high", "terminate_process"]
        ))
        
        self.add_rule(HuntingRule(
            rule_id="hunt-T1125",
            name="Video Capture",
            description="Detects webcam/video capture activities",
            mitre_technique="T1125",
            mitre_tactic="TA0009",
            severity="high",
            data_sources=["process", "command_line"],
            command_patterns=[
                r"ffmpeg.*-f\s+v4l2",
                r"ffmpeg.*-f\s+video4linux",
                r"ffmpeg.*webcam",
                r"cheese",
                r"cameracapture"
            ],
            response_actions=["alert_high", "terminate_process"]
        ))
        
        self.add_rule(HuntingRule(
            rule_id="hunt-T1115",
            name="Clipboard Data Collection",
            description="Detects clipboard monitoring/theft",
            mitre_technique="T1115",
            mitre_tactic="TA0009",
            severity="medium",
            data_sources=["process", "command_line"],
            command_patterns=[
                r"get-clipboard",
                r"xclip",
                r"xsel",
                r"pbpaste",
                r"powershell.*clipboard"
            ],
            response_actions=["alert_medium", "log_collection"]
        ))
        
        self.add_rule(HuntingRule(
            rule_id="hunt-T1074",
            name="Data Staging",
            description="Detects data staging for exfiltration",
            mitre_technique="T1074",
            mitre_tactic="TA0009",
            severity="high",
            data_sources=["file", "process", "command_line"],
            command_patterns=[
                r"copy.*\\staging",
                r"xcopy.*\\temp\\data",
                r"move.*\\public\\",
                r"cp.*\/tmp\/exfil"
            ],
            file_indicators=[r"\\staging\\", r"\\exfil\\", r"\\collect\\"],
            response_actions=["alert_high", "monitor_network"]
        ))
        
        # ============================================================
        # IMPACT (TA0040)
        # ============================================================
        
        self.add_rule(HuntingRule(
            rule_id="hunt-T1486",
            name="Data Encrypted for Impact (Ransomware)",
            description="Detects ransomware encryption behavior",
            mitre_technique="T1486",
            mitre_tactic="TA0040",
            severity="critical",
            data_sources=["process", "file", "command_line"],
            command_patterns=[
                r"vssadmin.*delete\s+shadows",
                r"wmic.*shadowcopy.*delete",
                r"bcdedit.*recoveryenabled.*no",
                r"bcdedit.*bootstatuspolicy.*ignoreallfailures",
                r"wbadmin\s+delete",
                r"cipher\s+\/w"
            ],
            file_indicators=[r"\.encrypted$", r"\.locked$", r"\.crypt$", r"readme.*ransom", r"how.*decrypt"],
            response_actions=["alert_critical", "isolate_system", "kill_encryption_process"]
        ))
        
        self.add_rule(HuntingRule(
            rule_id="hunt-T1485",
            name="Data Destruction",
            description="Detects data destruction/wiper behavior",
            mitre_technique="T1485",
            mitre_tactic="TA0040",
            severity="critical",
            data_sources=["process", "file", "command_line"],
            command_patterns=[
                r"format\s+c:",
                r"dd\s+if=\/dev\/zero",
                r"dd\s+if=\/dev\/urandom",
                r"shred\s+-",
                r"secure-delete",
                r"sdelete",
                r"eraser"
            ],
            response_actions=["alert_critical", "isolate_system", "terminate_process"]
        ))
        
        self.add_rule(HuntingRule(
            rule_id="hunt-T1490",
            name="Inhibit System Recovery",
            description="Detects attempts to disable system recovery",
            mitre_technique="T1490",
            mitre_tactic="TA0040",
            severity="critical",
            data_sources=["process", "command_line"],
            command_patterns=[
                r"vssadmin.*delete",
                r"wmic.*shadowcopy.*delete",
                r"bcdedit.*recoveryenabled.*no",
                r"bcdedit.*safeboot",
                r"reagentc.*\/disable",
                r"wbadmin.*delete.*catalog",
                r"del.*\\windows\\system32\\config"
            ],
            response_actions=["alert_critical", "block_command", "isolate_system"]
        ))
        
        self.add_rule(HuntingRule(
            rule_id="hunt-T1489",
            name="Service Stop",
            description="Detects stopping of critical services",
            mitre_technique="T1489",
            mitre_tactic="TA0040",
            severity="high",
            data_sources=["process", "command_line"],
            command_patterns=[
                r"net\s+stop.*sql",
                r"net\s+stop.*backup",
                r"net\s+stop.*exchange",
                r"net\s+stop.*vss",
                r"sc\s+stop.*sql",
                r"taskkill.*sql",
                r"systemctl\s+stop"
            ],
            response_actions=["alert_high", "restore_service"]
        ))
        
        self.add_rule(HuntingRule(
            rule_id="hunt-T1561",
            name="Disk Wipe",
            description="Detects disk wiping activities",
            mitre_technique="T1561",
            mitre_tactic="TA0040",
            severity="critical",
            data_sources=["process", "command_line"],
            command_patterns=[
                r"dd\s+if=.*of=\/dev\/sd",
                r"dd\s+if=.*of=\\\\\.\\Physical",
                r"diskpart.*clean.*all",
                r"wipefs",
                r"bootkit"
            ],
            response_actions=["alert_critical", "isolate_system", "emergency_shutdown"]
        ))
        
        self.add_rule(HuntingRule(
            rule_id="hunt-T1496",
            name="Resource Hijacking (Cryptomining)",
            description="Detects unauthorized cryptocurrency mining",
            mitre_technique="T1496",
            mitre_tactic="TA0040",
            severity="high",
            data_sources=["process", "network", "command_line"],
            command_patterns=[
                r"xmrig",
                r"minerd",
                r"cgminer",
                r"bfgminer",
                r"cpuminer",
                r"stratum\+tcp",
                r"nicehash"
            ],
            network_indicators={
                "ports": [3333, 4444, 5555, 14444, 45700],
                "pool_domains": ["pool.minergate.com", "xmrpool.net"]
            },
            response_actions=["alert_high", "terminate_process", "block_mining_pools"]
        ))
        
        # ============================================================
        # BEHAVIORAL HUNTING PATTERNS
        # ============================================================
        
        self.add_rule(HuntingRule(
            rule_id="hunt-BEHAV-001",
            name="Suspicious Parent-Child Process",
            description="Detects unusual parent-child process relationships",
            mitre_technique="T1059",
            mitre_tactic="TA0002",
            severity="high",
            data_sources=["process"],
            process_names=["cmd", "powershell", "wscript", "cscript", "mshta"],
            parent_process_patterns={
                "suspicious_parents": ["winword", "excel", "outlook", "powerpnt", "msaccess", "onenote"],
                "suspicious_children": ["cmd", "powershell", "mshta", "wscript", "cscript", "certutil"]
            },
            response_actions=["alert_high", "terminate_process"]
        ))
        
        self.add_rule(HuntingRule(
            rule_id="hunt-BEHAV-002",
            name="Rapid File Encryption Pattern",
            description="Detects rapid file modification indicative of ransomware",
            mitre_technique="T1486",
            mitre_tactic="TA0040",
            severity="critical",
            data_sources=["file"],
            behavioral_indicators={
                "file_operations_per_minute": 100,
                "extension_changes": True,
                "entropy_increase": True
            },
            response_actions=["alert_critical", "isolate_system", "terminate_suspicious_process"]
        ))
        
        self.add_rule(HuntingRule(
            rule_id="hunt-BEHAV-003",
            name="Beaconing Behavior",
            description="Detects periodic C2 communication patterns",
            mitre_technique="T1071",
            mitre_tactic="TA0011",
            severity="high",
            data_sources=["network"],
            behavioral_indicators={
                "periodic_connections": True,
                "jitter_threshold": 0.2,
                "min_beacon_count": 10
            },
            response_actions=["alert_high", "capture_traffic", "block_destination"]
        ))
        
        self.add_rule(HuntingRule(
            rule_id="hunt-BEHAV-004",
            name="Large Data Transfer to External",
            description="Detects large outbound data transfers",
            mitre_technique="T1041",
            mitre_tactic="TA0010",
            severity="high",
            data_sources=["network"],
            behavioral_indicators={
                "data_threshold_mb": 100,
                "external_destination": True,
                "unusual_protocol": True
            },
            response_actions=["alert_high", "throttle_connection", "capture_traffic"]
        ))
        
        self.add_rule(HuntingRule(
            rule_id="hunt-BEHAV-005",
            name="Credential Access Sequence",
            description="Detects sequence of credential access activities",
            mitre_technique="T1003",
            mitre_tactic="TA0006",
            severity="critical",
            data_sources=["process", "file", "memory"],
            behavioral_indicators={
                "lsass_access": True,
                "sam_access": True,
                "ntds_access": True,
                "sequence_window_seconds": 300
            },
            response_actions=["alert_critical", "isolate_system", "credential_rotation"]
        ))
        
        self.add_rule(HuntingRule(
            rule_id="hunt-BEHAV-006",
            name="Living Off The Land Attack Pattern",
            description="Detects LOTL techniques using multiple native tools",
            mitre_technique="T1218",
            mitre_tactic="TA0005",
            severity="high",
            data_sources=["process", "command_line"],
            behavioral_indicators={
                "lolbin_sequence": ["certutil", "mshta", "regsvr32", "rundll32", "bitsadmin"],
                "sequence_window_seconds": 60
            },
            command_patterns=[
                r"certutil.*-urlcache",
                r"mshta.*vbscript",
                r"regsvr32.*\/s.*\/u.*scrobj",
                r"rundll32.*javascript",
                r"bitsadmin.*\/transfer"
            ],
            response_actions=["alert_high", "terminate_chain", "isolate_system"]
        ))
        
        self.stats["rules_loaded"] = len(self.rules)
    
    def add_rule(self, rule: HuntingRule):
        """Add a hunting rule"""
        self.rules[rule.rule_id] = rule

    def _context_confidence_boost(self, behavior_context: Optional[Dict[str, Any]]) -> float:
        """Return confidence boost based on autonomous pressure context."""
        if not behavior_context:
            return 0.0

        try:
            agenticity = float(behavior_context.get("agenticity_score") or 0.0)
            cdi = float(behavior_context.get("cdi") or 0.0)
            machine_likelihood = float(behavior_context.get("machine_likelihood") or 0.0)
            cognitive_pressure = float(behavior_context.get("cognitive_pressure") or 0.0)
            ml_threat_score = float(behavior_context.get("ml_threat_score") or 0.0)
            ml_confidence = float(behavior_context.get("ml_confidence") or 0.0)
            triune_policy = str(behavior_context.get("triune_policy_tier") or "").strip().lower()
        except (TypeError, ValueError):
            return 0.0

        boost = 0.0
        if agenticity >= 0.70:
            boost += 0.15
        if cdi >= 0.60:
            boost += 0.12
        if machine_likelihood >= 0.70:
            boost += 0.10
        if cognitive_pressure >= 0.70:
            boost += 0.10
        if ml_threat_score >= 0.70:
            boost += 0.10
        if ml_confidence >= 0.70:
            boost += 0.08
        if triune_policy == "critical":
            boost += 0.08
        elif triune_policy == "high":
            boost += 0.05
        return min(0.30, boost)
    
    def hunt_process(self, process_data: Dict, behavior_context: Optional[Dict[str, Any]] = None) -> List[HuntingMatch]:
        """Hunt through process data"""
        matches = []
        
        name = (process_data.get('name') or '').lower()
        cmdline = (process_data.get('cmdline') or process_data.get('command_line') or '').lower()
        
        for rule in self.rules.values():
            if not rule.enabled:
                continue
            
            if 'process' not in rule.data_sources and 'command_line' not in rule.data_sources:
                continue
            
            matched_indicators = []
            confidence = 0.0
            
            # Check process names
            for proc_name in rule.process_names:
                if proc_name.lower() in name:
                    matched_indicators.append(f"process_name:{proc_name}")
                    confidence += 0.3
            
            # Check command patterns
            for pattern in rule.command_patterns:
                try:
                    if re.search(pattern, cmdline, re.IGNORECASE):
                        matched_indicators.append(f"command_pattern:{pattern[:30]}")
                        confidence += 0.4
                except re.error:
                    pass
            
            # Create match if indicators found
            if matched_indicators:
                confidence = min(1.0, confidence + self._context_confidence_boost(behavior_context))
                match = HuntingMatch(
                    rule_id=rule.rule_id,
                    rule_name=rule.name,
                    mitre_technique=rule.mitre_technique,
                    mitre_tactic=rule.mitre_tactic,
                    severity=rule.severity,
                    matched_data={
                        "pid": process_data.get('pid'),
                        "name": process_data.get('name'),
                        "cmdline": cmdline[:500]
                    },
                    matched_indicators=matched_indicators,
                    confidence=confidence,
                    context={
                        "data_source": "process",
                        "behavior_context": behavior_context or {},
                    }
                )
                matches.append(match)
                self.matches.append(match)
        
        return matches
    
    def hunt_network(self, connection_data: Dict, behavior_context: Optional[Dict[str, Any]] = None) -> List[HuntingMatch]:
        """Hunt through network connection data"""
        matches = []
        
        remote_port = connection_data.get('remote_port', 0)
        remote_ip = connection_data.get('remote_ip', '')
        
        for rule in self.rules.values():
            if not rule.enabled:
                continue
            
            if 'network' not in rule.data_sources:
                continue
            
            matched_indicators = []
            confidence = 0.0
            
            # Check suspicious ports
            network_ind = rule.network_indicators
            if 'suspicious_ports' in network_ind:
                if remote_port in network_ind['suspicious_ports']:
                    matched_indicators.append(f"suspicious_port:{remote_port}")
                    confidence += 0.5
            
            if 'ports' in network_ind:
                if remote_port in network_ind['ports']:
                    matched_indicators.append(f"indicator_port:{remote_port}")
                    confidence += 0.3
            
            # Create match if indicators found
            if matched_indicators:
                confidence = min(1.0, confidence + self._context_confidence_boost(behavior_context))
                match = HuntingMatch(
                    rule_id=rule.rule_id,
                    rule_name=rule.name,
                    mitre_technique=rule.mitre_technique,
                    mitre_tactic=rule.mitre_tactic,
                    severity=rule.severity,
                    matched_data={
                        "remote_ip": remote_ip,
                        "remote_port": remote_port,
                        "local_port": connection_data.get('local_port')
                    },
                    matched_indicators=matched_indicators,
                    confidence=confidence,
                    context={
                        "data_source": "network",
                        "behavior_context": behavior_context or {},
                    }
                )
                matches.append(match)
                self.matches.append(match)
        
        return matches
    
    def hunt_all(self, telemetry: Dict) -> List[HuntingMatch]:
        """Hunt through all telemetry data"""
        self.stats["hunts_executed"] += 1
        all_matches = []
        behavior_context = telemetry.get("behavior_context") if isinstance(telemetry, dict) else None
        
        # Hunt processes
        for process in telemetry.get('processes', []):
            matches = self.hunt_process(process, behavior_context)
            all_matches.extend(matches)
        
        # Hunt network connections
        for connection in telemetry.get('connections', []):
            matches = self.hunt_network(connection, behavior_context)
            all_matches.extend(matches)
        
        self.stats["matches_found"] += len(all_matches)
        
        return all_matches
    
    def get_rules_by_tactic(self, tactic: str) -> List[HuntingRule]:
        """Get rules for a specific MITRE tactic"""
        return [r for r in self.rules.values() if r.mitre_tactic == tactic]
    
    def get_rules_by_technique(self, technique: str) -> List[HuntingRule]:
        """Get rules for a specific MITRE technique"""
        return [r for r in self.rules.values() if r.mitre_technique == technique]
    
    def get_high_severity_matches(self) -> List[HuntingMatch]:
        """Get critical and high severity matches"""
        return [m for m in self.matches if m.severity in ['critical', 'high']]
    
    def get_stats(self) -> Dict:
        """Get hunting engine statistics"""
        return {
            **self.stats,
            "recent_matches": len([m for m in self.matches[-100:]]),
            "critical_matches": len([m for m in self.matches if m.severity == 'critical']),
            "high_matches": len([m for m in self.matches if m.severity == 'high']),
            "tactics_covered": len(set(r.mitre_tactic for r in self.rules.values())),
            "techniques_covered": len(set(r.mitre_technique for r in self.rules.values()))
        }
    
    def export_rules(self, path: str):
        """Export rules to JSON file"""
        with open(path, 'w') as f:
            json.dump({rid: asdict(rule) for rid, rule in self.rules.items()}, f, indent=2)
    
    def import_rules(self, path: str):
        """Import rules from JSON file"""
        with open(path, 'r') as f:
            rules_data = json.load(f)
        
        for rid, rdata in rules_data.items():
            self.rules[rid] = HuntingRule(**rdata)
        
        self.stats["rules_loaded"] = len(self.rules)


# Global singleton
threat_hunting_engine = ThreatHuntingEngine()
