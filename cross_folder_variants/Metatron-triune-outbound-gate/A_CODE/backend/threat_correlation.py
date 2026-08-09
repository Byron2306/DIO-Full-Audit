"""
Automated Threat Correlation Engine
=====================================
Automatically correlates detected threats with threat intelligence feeds
and enriches threat data with:

- Attribution information
- Campaign/APT group associations
- Related indicators (IOCs)
- Recommended mitigations
- Historical context
"""

import os
import json
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field, asdict
from enum import Enum
import hashlib
import re

logger = logging.getLogger(__name__)

# =============================================================================
# DATA MODELS
# =============================================================================

class CorrelationConfidence(Enum):
    HIGH = "high"       # Multiple strong matches
    MEDIUM = "medium"   # Some matches
    LOW = "low"         # Weak correlation
    NONE = "none"       # No correlation found

@dataclass
class DiamondModel:
    """Diamond Model of Intrusion Analysis (Sergio Caltagirone, 2013)"""
    # Core vertices
    adversary: Optional[str] = None  # Threat actor / APT group
    capability: Optional[str] = None  # Malware, tools, techniques
    infrastructure: Optional[str] = None  # C2 servers, domains, IPs
    victim: Optional[str] = None  # Target organization/industry
    
    # Meta-features
    timestamp: Optional[str] = None
    phase: Optional[str] = None  # Kill chain phase
    direction: str = "adversary-to-victim"  # Direction of attack
    methodology: Optional[str] = None  # Attack methodology
    resources: List[str] = field(default_factory=list)  # Required resources
    
    # Additional analysis
    social_political_context: Optional[str] = None  # Geopolitical factors
    technology_context: Optional[str] = None  # Technical environment
    confidence: str = "low"

@dataclass
class ThreatAttribution:
    """Attribution information for a threat"""
    threat_actor: Optional[str] = None
    threat_actor_aliases: List[str] = field(default_factory=list)
    campaign: Optional[str] = None
    malware_family: Optional[str] = None
    malware_variants: List[str] = field(default_factory=list)
    ttps_observed: List[str] = field(default_factory=list)
    mitre_techniques: List[str] = field(default_factory=list)
    origin_country: Optional[str] = None
    motivation: Optional[str] = None  # espionage, financial, sabotage, hacktivism
    target_industries: List[str] = field(default_factory=list)
    confidence: str = "low"
    sources: List[str] = field(default_factory=list)
    diamond_model: Optional[DiamondModel] = None
    
@dataclass
class RelatedIndicator:
    """Related IOC found during correlation"""
    ioc_type: str
    value: str
    relationship: str  # e.g., "same_campaign", "same_actor", "infrastructure"
    source: str
    confidence: int = 50
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None
    tags: List[str] = field(default_factory=list)

@dataclass
class Mitigation:
    """Recommended mitigation action"""
    action: str
    priority: str  # critical, high, medium, low
    description: str
    automated: bool = False
    mitre_mitigation_id: Optional[str] = None
    estimated_effort: Optional[str] = None  # low, medium, high

@dataclass
class CorrelationResult:
    """Complete correlation result for a threat"""
    threat_id: str
    correlation_id: str
    timestamp: str
    confidence: str
    attribution: ThreatAttribution
    matched_indicators: List[Dict] = field(default_factory=list)
    related_indicators: List[RelatedIndicator] = field(default_factory=list)
    mitigations: List[Mitigation] = field(default_factory=list)
    historical_context: Dict[str, Any] = field(default_factory=dict)
    enrichment_data: Dict[str, Any] = field(default_factory=dict)
    auto_actions_taken: List[str] = field(default_factory=list)

# =============================================================================
# KNOWN THREAT ACTORS & CAMPAIGNS
# =============================================================================

# APT/Threat Actor signatures and indicators (Diamond Model: Adversary)
THREAT_ACTORS = {
    # === RUSSIA-BASED ACTORS ===
    "apt28": {
        "names": ["APT28", "Fancy Bear", "Sofacy", "Sednit", "STRONTIUM", "Forest Blizzard"],
        "ttps": ["spearphishing", "watering_hole", "zero_day", "credential_harvesting"],
        "malware": ["XAgent", "Seduploader", "Zebrocy", "Drovorub"],
        "industries": ["government", "military", "defense", "media", "aerospace"],
        "origin": "Russia",
        "motivation": "espionage",
        "infrastructure": ["dedicated_servers", "compromised_sites", "tor"],
        "mitre_techniques": ["T1566", "T1189", "T1003", "T1059.001"]
    },
    "apt29": {
        "names": ["APT29", "Cozy Bear", "The Dukes", "NOBELIUM", "Midnight Blizzard"],
        "ttps": ["supply_chain", "cloud_exploitation", "spearphishing", "oauth_abuse"],
        "malware": ["SUNBURST", "TEARDROP", "WellMess", "EnvyScout", "Brute Ratel"],
        "industries": ["government", "technology", "healthcare", "think_tanks"],
        "origin": "Russia",
        "motivation": "espionage",
        "infrastructure": ["cloud_services", "compromised_domains"],
        "mitre_techniques": ["T1195.002", "T1078", "T1098", "T1550"]
    },
    "turla": {
        "names": ["Turla", "Snake", "Venomous Bear", "Waterbug", "KRYPTON"],
        "ttps": ["satellite_hijacking", "watering_hole", "rootkit", "covert_channel"],
        "malware": ["Snake", "ComRAT", "Carbon", "Kazuar", "Gazer"],
        "industries": ["government", "embassy", "military", "research"],
        "origin": "Russia",
        "motivation": "espionage",
        "infrastructure": ["hijacked_satellites", "compromised_infrastructure"],
        "mitre_techniques": ["T1071.001", "T1014", "T1205", "T1095"]
    },
    "sandworm": {
        "names": ["Sandworm", "Voodoo Bear", "IRIDIUM", "Seashell Blizzard", "TeleBots"],
        "ttps": ["ics_attacks", "wiper", "supply_chain", "destructive_attacks"],
        "malware": ["NotPetya", "Industroyer", "Olympic Destroyer", "CaddyWiper", "SwiftSlicer"],
        "industries": ["energy", "critical_infrastructure", "government", "financial"],
        "origin": "Russia",
        "motivation": "sabotage",
        "infrastructure": ["dedicated_infrastructure", "vpn_services"],
        "mitre_techniques": ["T1485", "T1495", "T1561", "T1491"]
    },
    
    # === CHINA-BASED ACTORS ===
    "apt41": {
        "names": ["APT41", "BARIUM", "Winnti", "Double Dragon", "Brass Typhoon"],
        "ttps": ["supply_chain", "ransomware", "espionage", "dual_espionage_criminal"],
        "malware": ["ShadowPad", "Winnti", "PlugX", "Cobalt Strike", "DUSTPAN"],
        "industries": ["gaming", "healthcare", "technology", "telecom", "pharmaceutical"],
        "origin": "China",
        "motivation": "espionage_and_financial",
        "infrastructure": ["compromised_servers", "cloud_providers"],
        "mitre_techniques": ["T1195", "T1587", "T1059", "T1055"]
    },
    "apt32": {
        "names": ["APT32", "OceanLotus", "SeaLotus", "Ocean Buffalo", "BISMUTH"],
        "ttps": ["spearphishing", "watering_hole", "macros", "social_engineering"],
        "malware": ["Denis", "Kerrdown", "Goopy", "METALJACK", "PhantomNet"],
        "industries": ["government", "media", "manufacturing", "human_rights", "technology"],
        "origin": "Vietnam",
        "motivation": "espionage",
        "infrastructure": ["compromised_websites", "c2_infrastructure"],
        "mitre_techniques": ["T1566.001", "T1204.002", "T1059.001", "T1027"]
    },
    "mustang_panda": {
        "names": ["Mustang Panda", "RedDelta", "Bronze President", "TA416", "Earth Preta"],
        "ttps": ["spearphishing", "usb_malware", "dll_sideloading", "geopolitical_targeting"],
        "malware": ["PlugX", "Hodur", "Korplug", "TONESHELL"],
        "industries": ["government", "ngo", "telecom", "religious_organizations"],
        "origin": "China",
        "motivation": "espionage",
        "infrastructure": ["compromised_sites", "dynamic_dns"],
        "mitre_techniques": ["T1566.001", "T1091", "T1574.002", "T1071"]
    },
    "apt40": {
        "names": ["APT40", "Leviathan", "BRONZE MOHAWK", "Kryptonite Panda", "Gingham Typhoon"],
        "ttps": ["watering_hole", "spearphishing", "supply_chain", "web_exploitation"],
        "malware": ["BADFLICK", "PHOTO", "ScanBox", "AIRBREAK"],
        "industries": ["maritime", "defense", "aviation", "chemicals", "government"],
        "origin": "China",
        "motivation": "espionage",
        "infrastructure": ["compromised_web_servers", "aws_infrastructure"],
        "mitre_techniques": ["T1190", "T1566", "T1505.003", "T1048"]
    },
    "volt_typhoon": {
        "names": ["Volt Typhoon", "BRONZE SILHOUETTE", "Vanguard Panda"],
        "ttps": ["living_off_land", "credential_theft", "network_exploitation", "zero_day"],
        "malware": ["custom_web_shells", "LOTL_tools"],
        "industries": ["critical_infrastructure", "communications", "government", "utilities"],
        "origin": "China",
        "motivation": "pre_positioning",
        "infrastructure": ["compromised_routers", "soho_devices"],
        "mitre_techniques": ["T1059.001", "T1078", "T1003", "T1071"]
    },
    
    # === NORTH KOREA-BASED ACTORS ===
    "lazarus": {
        "names": ["Lazarus Group", "Hidden Cobra", "ZINC", "APT38", "Diamond Sleet"],
        "ttps": ["cryptocurrency_theft", "ransomware", "supply_chain", "destructive_attacks"],
        "malware": ["WannaCry", "FALLCHILL", "AppleJeus", "BLINDINGCAN", "Dtrack"],
        "industries": ["financial", "cryptocurrency", "defense", "media", "entertainment"],
        "origin": "North Korea",
        "motivation": "financial_and_espionage",
        "infrastructure": ["compromised_servers", "vpn_proxy"],
        "mitre_techniques": ["T1486", "T1195.002", "T1566.001", "T1071"]
    },
    "kimsuky": {
        "names": ["Kimsuky", "Thallium", "APT43", "Velvet Chollima", "Emerald Sleet"],
        "ttps": ["spearphishing", "credential_harvesting", "web_exploitation", "social_engineering"],
        "malware": ["BabyShark", "SHARPEXT", "GoldDragon", "AppleSeed"],
        "industries": ["government", "think_tanks", "academia", "defense", "nuclear_policy"],
        "origin": "North Korea",
        "motivation": "espionage",
        "infrastructure": ["phishing_sites", "compromised_web_mail"],
        "mitre_techniques": ["T1566", "T1598", "T1539", "T1557"]
    },
    "andariel": {
        "names": ["Andariel", "Silent Chollima", "Onyx Sleet", "Plutonium"],
        "ttps": ["ransomware", "espionage", "vulnerability_exploitation", "cryptomining"],
        "malware": ["Maui", "EarlyRAT", "DTrack", "TigerRAT"],
        "industries": ["defense", "aerospace", "nuclear", "healthcare"],
        "origin": "North Korea",
        "motivation": "financial_and_espionage",
        "infrastructure": ["vpn_servers", "compromised_infrastructure"],
        "mitre_techniques": ["T1486", "T1190", "T1003", "T1496"]
    },
    
    # === IRAN-BASED ACTORS ===
    "apt33": {
        "names": ["APT33", "Elfin", "Holmium", "Refined Kitten", "Peach Sandstorm"],
        "ttps": ["spearphishing", "password_spraying", "wiper", "destructive_attacks"],
        "malware": ["Stonedrill", "Shamoon", "Dropshot", "Narilam"],
        "industries": ["aviation", "petrochemical", "energy", "defense"],
        "origin": "Iran",
        "motivation": "sabotage_and_espionage",
        "infrastructure": ["compromised_websites", "c2_servers"],
        "mitre_techniques": ["T1566", "T1110.003", "T1485", "T1561"]
    },
    "apt34": {
        "names": ["APT34", "OilRig", "Helix Kitten", "Hazel Sandstorm", "Crambus"],
        "ttps": ["dns_hijacking", "spearphishing", "credential_theft", "web_shells"],
        "malware": ["POWRUNER", "BONDUPDATER", "Glimpse", "RDAT", "SideTwist"],
        "industries": ["financial", "government", "energy", "telecom", "chemical"],
        "origin": "Iran",
        "motivation": "espionage",
        "infrastructure": ["dns_providers", "compromised_domains"],
        "mitre_techniques": ["T1071.004", "T1566", "T1003", "T1505.003"]
    },
    "apt35": {
        "names": ["APT35", "Charming Kitten", "Phosphorus", "Mint Sandstorm", "TA453"],
        "ttps": ["credential_phishing", "social_engineering", "fake_personas", "password_spraying"],
        "malware": ["HYPERSCRAPE", "DownPaper", "POWERLESS", "CharmPower"],
        "industries": ["think_tanks", "academia", "media", "human_rights", "policy"],
        "origin": "Iran",
        "motivation": "espionage",
        "infrastructure": ["phishing_domains", "lookalike_domains"],
        "mitre_techniques": ["T1566.001", "T1598.003", "T1534", "T1110.003"]
    },
    "muddywater": {
        "names": ["MuddyWater", "Static Kitten", "Mercury", "Mango Sandstorm", "TEMP.Zagros"],
        "ttps": ["spearphishing", "powershell_abuse", "legitimate_tools", "macro_enabled_docs"],
        "malware": ["POWERSTATS", "PhonyC2", "BugSleep", "MUDBLAST"],
        "industries": ["government", "telecom", "oil_gas", "defense"],
        "origin": "Iran",
        "motivation": "espionage",
        "infrastructure": ["cloud_services", "compromised_hosts"],
        "mitre_techniques": ["T1566.001", "T1059.001", "T1204.002", "T1218"]
    },
    
    # === RANSOMWARE & ECRIME GROUPS ===
    "fin7": {
        "names": ["FIN7", "Carbanak", "Carbon Spider", "Sangria Tempest"],
        "ttps": ["pos_malware", "spearphishing", "social_engineering", "supply_chain"],
        "malware": ["Carbanak", "GRIFFON", "BIRDWATCH", "Lizar", "DiceLoader"],
        "industries": ["retail", "hospitality", "financial", "food_service"],
        "origin": "Eastern Europe",
        "motivation": "financial",
        "infrastructure": ["bulletproof_hosting", "compromised_sites"],
        "mitre_techniques": ["T1566.001", "T1204", "T1059.001", "T1583"]
    },
    "lockbit": {
        "names": ["LockBit", "ABCD", "LockBit 2.0", "LockBit 3.0", "LockBit Black"],
        "ttps": ["ransomware", "raas", "double_extortion", "credential_theft"],
        "malware": ["LockBit", "StealBit", "Cobalt Strike"],
        "industries": ["all_industries", "healthcare", "education", "manufacturing"],
        "origin": "Russia/CIS",
        "motivation": "financial",
        "infrastructure": ["tor_sites", "affiliate_network"],
        "mitre_techniques": ["T1486", "T1490", "T1048", "T1003"]
    },
    "blackcat": {
        "names": ["ALPHV", "BlackCat", "Noberus", "Scatter Spider"],
        "ttps": ["ransomware", "raas", "triple_extortion", "social_engineering"],
        "malware": ["BlackCat", "ALPHV", "Rust_ransomware"],
        "industries": ["healthcare", "government", "technology", "critical_infrastructure"],
        "origin": "Russia",
        "motivation": "financial",
        "infrastructure": ["tor_infrastructure", "data_leak_sites"],
        "mitre_techniques": ["T1486", "T1491.002", "T1496", "T1567"]
    },
    "clop": {
        "names": ["Cl0p", "TA505", "Clop", "Lace Tempest", "FIN11"],
        "ttps": ["ransomware", "zero_day_exploitation", "mass_exploitation", "data_theft"],
        "malware": ["Clop", "FlawedAmmyy", "SDBBot", "Truebot"],
        "industries": ["all_industries", "healthcare", "financial", "government"],
        "origin": "Russia",
        "motivation": "financial",
        "infrastructure": ["data_leak_sites", "file_transfer_exploits"],
        "mitre_techniques": ["T1190", "T1486", "T1567", "T1537"]
    },
    "conti": {
        "names": ["Conti", "Wizard Spider", "TrickBot", "Gold Ulrick"],
        "ttps": ["ransomware", "double_extortion", "credential_theft", "cobalt_strike"],
        "malware": ["Conti", "TrickBot", "BazarLoader", "Ryuk", "Diavol"],
        "industries": ["healthcare", "education", "government", "manufacturing"],
        "origin": "Russia",
        "motivation": "financial",
        "infrastructure": ["bulletproof_hosting", "botnet_infrastructure"],
        "mitre_techniques": ["T1486", "T1003", "T1021.001", "T1047"]
    },
    "blackbasta": {
        "names": ["Black Basta", "Storm-0506", "Tropical Scorpius"],
        "ttps": ["ransomware", "double_extortion", "qakbot", "social_engineering"],
        "malware": ["Black Basta", "QakBot", "Cobalt Strike", "SystemBC"],
        "industries": ["manufacturing", "construction", "professional_services"],
        "origin": "Russia/CIS",
        "motivation": "financial",
        "infrastructure": ["tor_sites", "affiliate_programs"],
        "mitre_techniques": ["T1486", "T1566", "T1059", "T1218"]
    },
    "play": {
        "names": ["Play", "PlayCrypt", "Balloonfly"],
        "ttps": ["ransomware", "living_off_land", "credential_theft", "double_extortion"],
        "malware": ["Play Ransomware", "SystemBC", "Grixba"],
        "industries": ["local_government", "legal", "healthcare", "technology"],
        "origin": "Russia/CIS",
        "motivation": "financial",
        "infrastructure": ["tor_sites", "data_leak_sites"],
        "mitre_techniques": ["T1486", "T1059.001", "T1003", "T1490"]
    }
}

# Campaign patterns (Diamond Model: Capability)
CAMPAIGN_PATTERNS = {
    "ransomware": {
        "indicators": ["encrypted", "ransom", "bitcoin", "decrypt", "locked", ".onion", "recover"],
        "file_extensions": [".encrypted", ".locked", ".crypt", ".wcry", ".wnry", ".locky", ".zepto", ".cerber"],
        "malware_families": ["lockbit", "conti", "revil", "blackcat", "ryuk", "maze", "clop"],
        "severity": "critical",
        "mitre_tactics": ["TA0040"],
        "response_priority": 1
    },
    "cryptomining": {
        "indicators": ["xmrig", "monero", "stratum", "pool", "miner", "hashrate", "coinhive", "cryptonight"],
        "ports": [3333, 4444, 5555, 14444, 45700, 14433],
        "process_indicators": ["xmr", "miner", "minerd", "cgminer", "bfgminer"],
        "severity": "high",
        "mitre_tactics": ["TA0040"],
        "response_priority": 3
    },
    "botnet": {
        "indicators": ["c2", "beacon", "callback", "bot", "zombie", "dga", "heartbeat"],
        "behaviors": ["periodic_connection", "encrypted_traffic", "dga_domains", "fast_flux"],
        "common_ports": [6667, 6697, 443, 80, 8080],
        "severity": "critical",
        "mitre_tactics": ["TA0011"],
        "response_priority": 2
    },
    "data_exfiltration": {
        "indicators": ["exfil", "upload", "transfer", "staging", "compress", "archive", "encrypt_files"],
        "behaviors": ["large_outbound", "dns_tunneling", "steganography", "cloud_upload"],
        "protocols": ["https", "dns", "ftp", "sftp", "smb"],
        "severity": "critical",
        "mitre_tactics": ["TA0010"],
        "response_priority": 1
    },
    "supply_chain": {
        "indicators": ["update", "package", "dependency", "npm", "pypi", "nuget", "maven", "cargo"],
        "attack_vectors": ["trojanized_update", "compromised_library", "build_server", "ci_cd"],
        "target_systems": ["build_servers", "package_managers", "update_mechanisms"],
        "severity": "critical",
        "mitre_tactics": ["TA0001", "TA0042"],
        "response_priority": 1
    },
    "credential_harvesting": {
        "indicators": ["mimikatz", "lsass", "sam", "ntds", "credential", "password", "kerberos", "ticket"],
        "techniques": ["pass_the_hash", "pass_the_ticket", "kerberoasting", "dcsync", "credential_dump"],
        "target_files": ["lsass.exe", "sam", "ntds.dit", "security", "system"],
        "severity": "critical",
        "mitre_tactics": ["TA0006"],
        "response_priority": 1
    },
    "wiper": {
        "indicators": ["wipe", "destroy", "mbr", "partition", "overwrite", "corrupt", "delete"],
        "malware_families": ["notpetya", "shamoon", "whispergate", "caddywiper", "hermetic"],
        "target_systems": ["mbr", "boot_sector", "file_systems", "backups"],
        "severity": "critical",
        "mitre_tactics": ["TA0040"],
        "response_priority": 1
    },
    "espionage": {
        "indicators": ["screenshot", "keylog", "clipboard", "microphone", "camera", "document", "collect"],
        "techniques": ["keylogging", "screen_capture", "audio_capture", "data_collection"],
        "data_targets": ["documents", "emails", "credentials", "communications"],
        "severity": "high",
        "mitre_tactics": ["TA0009"],
        "response_priority": 2
    },
    "watering_hole": {
        "indicators": ["iframe", "exploit_kit", "drive_by", "redirect", "compromised_site"],
        "attack_vectors": ["compromised_website", "malicious_ads", "exploit_kits"],
        "delivery_methods": ["javascript", "flash", "java", "browser_exploit"],
        "severity": "high",
        "mitre_tactics": ["TA0001"],
        "response_priority": 2
    },
    "living_off_land": {
        "indicators": ["powershell", "wmic", "certutil", "mshta", "regsvr32", "rundll32", "bitsadmin"],
        "techniques": ["lolbins", "fileless", "memory_only", "legitimate_tools"],
        "common_tools": ["powershell", "cmd", "wmic", "certutil", "mshta"],
        "severity": "high",
        "mitre_tactics": ["TA0002", "TA0005"],
        "response_priority": 2
    },
    "lateral_movement": {
        "indicators": ["psexec", "wmiexec", "smbexec", "dcom", "rdp", "winrm", "ssh"],
        "techniques": ["remote_execution", "pass_the_hash", "token_impersonation", "exploitation"],
        "protocols": ["smb", "wmi", "rdp", "ssh", "winrm"],
        "severity": "critical",
        "mitre_tactics": ["TA0008"],
        "response_priority": 1
    },
    "persistence": {
        "indicators": ["startup", "services", "registry", "scheduled_task", "boot", "autorun"],
        "techniques": ["registry_run_key", "scheduled_task", "service_creation", "dll_hijacking"],
        "locations": ["run_keys", "services", "scheduled_tasks", "startup_folder"],
        "severity": "high",
        "mitre_tactics": ["TA0003"],
        "response_priority": 2
    },
    "initial_access_exploit": {
        "indicators": ["exploit", "cve", "vulnerability", "rce", "injection", "overflow"],
        "attack_vectors": ["zero_day", "n_day", "web_exploit", "network_exploit"],
        "common_services": ["exchange", "sharepoint", "citrix", "vpn", "firewall"],
        "severity": "critical",
        "mitre_tactics": ["TA0001"],
        "response_priority": 1
    }
}

# =============================================================================
# MITIGATION LIBRARY
# =============================================================================

MITIGATION_LIBRARY = {
    "malware": [
        Mitigation("isolate_host", "critical", "Immediately isolate the affected host from the network", True),
        Mitigation("kill_process", "critical", "Terminate the malicious process", True),
        Mitigation("quarantine_file", "high", "Move malicious file to quarantine", True),
        Mitigation("scan_related_hosts", "high", "Scan hosts that communicated with infected system", False),
        Mitigation("reset_credentials", "medium", "Reset credentials for affected users", False),
    ],
    "ransomware": [
        Mitigation("isolate_host", "critical", "Immediately isolate to prevent spread", True),
        Mitigation("disable_smb", "critical", "Disable SMB on network segment", True),
        Mitigation("backup_verify", "high", "Verify backup integrity before restoration", False),
        Mitigation("incident_response", "high", "Engage incident response team", False),
        Mitigation("law_enforcement", "medium", "Consider reporting to law enforcement", False),
    ],
    "botnet": [
        Mitigation("block_c2", "critical", "Block communication to C2 server", True),
        Mitigation("sinkhole_dns", "high", "Sinkhole malicious DNS queries", True),
        Mitigation("network_forensics", "high", "Capture network traffic for analysis", False),
        Mitigation("identify_scope", "medium", "Identify all infected hosts in network", False),
    ],
    "ai_agent": [
        Mitigation("rate_limit", "critical", "Apply aggressive rate limiting", True),
        Mitigation("block_ip", "critical", "Block source IP address", True),
        Mitigation("captcha_challenge", "high", "Require CAPTCHA for suspicious requests", False),
        Mitigation("behavioral_analysis", "medium", "Deep behavioral analysis of traffic", False),
    ],
    "phishing": [
        Mitigation("block_sender", "high", "Block sender domain/address", True),
        Mitigation("user_notification", "high", "Notify targeted users", False),
        Mitigation("credential_reset", "medium", "Reset credentials if clicked", False),
        Mitigation("awareness_training", "low", "Schedule security awareness training", False),
    ],
    "default": [
        Mitigation("investigate", "high", "Investigate threat indicators", False),
        Mitigation("monitor", "medium", "Increase monitoring on affected systems", False),
        Mitigation("document", "low", "Document findings for future reference", False),
    ]
}

# =============================================================================
# THREAT CORRELATION ENGINE
# =============================================================================

class ThreatCorrelationEngine:
    """
    Automated threat correlation and enrichment engine.
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
        
        self.threat_intel = None  # Will be set from threat_intel module
        self.correlation_cache: Dict[str, CorrelationResult] = {}
        self.auto_correlate_enabled = True
        self._initialized = True
    
    @classmethod
    def set_database(cls, db):
        cls._db = db
    
    def set_threat_intel(self, threat_intel):
        """Set threat intelligence manager reference"""
        self.threat_intel = threat_intel
    
    async def correlate_threat(self, threat: Dict) -> CorrelationResult:
        """
        Perform comprehensive correlation analysis on a threat.
        """
        threat_id = threat.get("id", "unknown")
        correlation_id = hashlib.md5(f"{threat_id}-{datetime.now().isoformat()}".encode()).hexdigest()[:16]
        
        logger.info(f"Starting correlation for threat {threat_id}")
        
        # Initialize result
        result = CorrelationResult(
            threat_id=threat_id,
            correlation_id=correlation_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            confidence=CorrelationConfidence.NONE.value,
            attribution=ThreatAttribution()
        )
        
        try:
            signal_context = await self._collect_signal_context(threat)

            # Step 1: Check threat intel feeds for IOC matches
            matched_indicators = await self._check_threat_intel(threat)
            result.matched_indicators = matched_indicators
            
            # Step 2: Identify threat actor/campaign
            attribution = self._identify_attribution(threat, matched_indicators)
            result.attribution = attribution
            
            # Step 3: Find related indicators
            related = self._find_related_indicators(threat, matched_indicators)
            result.related_indicators = related
            
            # Step 4: Generate mitigations
            mitigations = self._generate_mitigations(threat, attribution)
            result.mitigations = mitigations
            
            # Step 5: Historical context
            historical = await self._get_historical_context(threat)
            result.historical_context = historical
            
            # Step 6: Enrichment data
            enrichment = self._generate_enrichment(threat, attribution, matched_indicators, signal_context)
            result.enrichment_data = enrichment
            
            # Step 7: Calculate confidence
            result.confidence = self._calculate_confidence(result)
            
            # Step 8: Execute auto-actions if enabled
            if self.auto_correlate_enabled:
                actions = await self._execute_auto_actions(threat, result)
                result.auto_actions_taken = actions
            
            # Cache result
            self.correlation_cache[threat_id] = result
            
            # Store in database
            if self._db is not None:
                await self._db.threat_correlations.insert_one(asdict(result))
            
            logger.info(f"Correlation complete for {threat_id}: confidence={result.confidence}")
            
        except Exception as e:
            logger.error(f"Correlation error for {threat_id}: {e}")
            result.enrichment_data["error"] = str(e)
        
        return result
    
    async def _check_threat_intel(self, threat: Dict) -> List[Dict]:
        """Check threat against threat intelligence feeds"""
        matched = []
        
        if not self.threat_intel:
            return matched
        
        # Extract IOCs from threat
        iocs_to_check = []
        
        # Source IP
        if threat.get("source_ip"):
            iocs_to_check.append(("ip", threat["source_ip"]))
        
        # Indicators field
        for indicator in threat.get("indicators", []):
            # Try to detect type
            iocs_to_check.append((None, indicator))
        
        # Check description for IPs, domains, hashes
        description = threat.get("description", "")
        
        # IP pattern
        ip_pattern = r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
        for ip in re.findall(ip_pattern, description):
            iocs_to_check.append(("ip", ip))
        
        # Hash patterns
        md5_pattern = r'\b[a-fA-F0-9]{32}\b'
        sha256_pattern = r'\b[a-fA-F0-9]{64}\b'
        for h in re.findall(md5_pattern, description):
            iocs_to_check.append(("md5", h))
        for h in re.findall(sha256_pattern, description):
            iocs_to_check.append(("sha256", h))
        
        # Check each IOC
        for ioc_type, value in iocs_to_check:
            try:
                match = self.threat_intel.check_indicator(value, ioc_type)
                if match.matched and match.indicator:
                    matched.append({
                        "value": value,
                        "type": match.query_type,
                        "source": match.indicator.source,
                        "threat_level": match.indicator.threat_level,
                        "description": match.indicator.description,
                        "confidence": match.indicator.confidence
                    })
            except Exception as e:
                logger.debug(f"IOC check failed for {value}: {e}")
        
        return matched
    
    def _identify_attribution(self, threat: Dict, matched_indicators: List[Dict]) -> ThreatAttribution:
        """Identify threat actor and campaign attribution using enhanced correlation"""
        attribution = ThreatAttribution()
        
        threat_type = threat.get("type", "").lower()
        threat_name = threat.get("name", "").lower()
        description = threat.get("description", "").lower()
        indicators = threat.get("indicators", [])
        mitre_techniques = threat.get("mitre_techniques", [])
        target_industry = threat.get("target_industry", "").lower()
        source_country = threat.get("source_country", "").lower()
        
        combined_text = f"{threat_name} {description} {' '.join(str(i).lower() for i in indicators)}"
        
        # Check for known threat actors with enhanced scoring
        actor_scores = {}
        
        for actor_id, actor_info in THREAT_ACTORS.items():
            score = 0
            match_reasons = []
            
            # Check name matches (high weight)
            for name in actor_info["names"]:
                if name.lower() in combined_text:
                    score += 35
                    match_reasons.append(f"name:{name}")
            
            # Check malware matches (high weight)
            for malware in actor_info.get("malware", []):
                if malware.lower() in combined_text:
                    score += 25
                    match_reasons.append(f"malware:{malware}")
            
            # Check TTP matches (medium weight)
            for ttp in actor_info.get("ttps", []):
                if ttp in combined_text:
                    score += 12
                    match_reasons.append(f"ttp:{ttp}")
            
            # Check MITRE technique matches (high weight)
            actor_techniques = actor_info.get("mitre_techniques", [])
            for technique in mitre_techniques:
                if technique in actor_techniques:
                    score += 20
                    match_reasons.append(f"mitre:{technique}")
            
            # Check industry targeting alignment (medium weight)
            actor_industries = actor_info.get("industries", [])
            for industry in actor_industries:
                if industry in target_industry or industry in combined_text:
                    score += 10
                    match_reasons.append(f"industry:{industry}")
            
            # Check origin/country correlation (medium weight)
            actor_origin = actor_info.get("origin", "").lower()
            if actor_origin and source_country and (actor_origin in source_country or source_country in actor_origin):
                score += 8
                match_reasons.append(f"origin:{actor_origin}")
            
            # Check infrastructure patterns (medium weight)
            for infra in actor_info.get("infrastructure", []):
                if infra in combined_text:
                    score += 8
                    match_reasons.append(f"infra:{infra}")
            
            if score > 0:
                actor_scores[actor_id] = {"score": score, "reasons": match_reasons}
        
        # Find best matching actor
        if actor_scores:
            best_match = max(actor_scores.items(), key=lambda x: x[1]["score"])
            actor_id = best_match[0]
            score_data = best_match[1]
            
            if score_data["score"] >= 15:  # Minimum threshold
                actor_info = THREAT_ACTORS[actor_id]
                attribution.threat_actor = actor_info["names"][0]
                attribution.threat_actor_aliases = actor_info["names"][1:] if len(actor_info["names"]) > 1 else []
                attribution.ttps_observed = actor_info.get("ttps", [])
                attribution.mitre_techniques = actor_info.get("mitre_techniques", [])
                attribution.origin_country = actor_info.get("origin")
                attribution.motivation = actor_info.get("motivation")
                attribution.target_industries = actor_info.get("industries", [])
                attribution.malware_variants = actor_info.get("malware", [])
                
                # Determine confidence based on score
                if score_data["score"] >= 60:
                    attribution.confidence = "high"
                elif score_data["score"] >= 35:
                    attribution.confidence = "medium"
                else:
                    attribution.confidence = "low"
                
                attribution.sources = ["internal_correlation", "mitre_att&ck", "threat_actor_database"]
                
                # Build Diamond Model
                attribution.diamond_model = DiamondModel(
                    adversary=attribution.threat_actor,
                    capability=", ".join(actor_info.get("malware", [])[:3]),
                    infrastructure=", ".join(actor_info.get("infrastructure", [])[:2]),
                    victim=target_industry or "unknown",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    phase=self._determine_kill_chain_phase(threat),
                    methodology=actor_info.get("motivation"),
                    resources=actor_info.get("ttps", [])[:5],
                    social_political_context=f"Attribution to {actor_info.get('origin', 'unknown')} state-sponsored or criminal group",
                    technology_context=description[:200] if description else None,
                    confidence=attribution.confidence
                )
        
        # Check for campaign patterns with enhanced matching
        campaign_matches = []
        for campaign_id, campaign_info in CAMPAIGN_PATTERNS.items():
            campaign_score = 0
            for indicator in campaign_info.get("indicators", []):
                if indicator in combined_text:
                    campaign_score += 10
            for malware in campaign_info.get("malware_families", []):
                if malware in combined_text:
                    campaign_score += 15
            if campaign_score > 0:
                campaign_matches.append((campaign_id, campaign_score))
        
        if campaign_matches:
            best_campaign = max(campaign_matches, key=lambda x: x[1])
            attribution.campaign = best_campaign[0].replace("_", " ").title()
        
        # Check matched indicators for additional context
        for match in matched_indicators:
            if match.get("source"):
                if match["source"] not in attribution.sources:
                    attribution.sources.append(match["source"])
        
        # Try to identify malware family from threat name/description
        if not attribution.malware_family:
            malware_keywords = ["ransomware", "trojan", "worm", "backdoor", "rootkit", "keylogger", "spyware", "rat", "infostealer", "loader", "downloader"]
            for keyword in malware_keywords:
                if keyword in combined_text:
                    attribution.malware_family = keyword.title()
                    break
        
        return attribution
    
    def _determine_kill_chain_phase(self, threat: Dict) -> str:
        """Determine approximate kill chain phase based on threat indicators"""
        combined = f"{threat.get('name', '')} {threat.get('description', '')} {threat.get('type', '')}".lower()
        
        if any(k in combined for k in ["recon", "scan", "enumeration", "discovery"]):
            return "reconnaissance"
        elif any(k in combined for k in ["phishing", "exploit", "payload", "dropper"]):
            return "delivery"
        elif any(k in combined for k in ["execute", "run", "spawn", "shellcode"]):
            return "exploitation"
        elif any(k in combined for k in ["persistence", "service", "registry", "scheduled"]):
            return "installation"
        elif any(k in combined for k in ["c2", "beacon", "callback", "command"]):
            return "command_and_control"
        elif any(k in combined for k in ["lateral", "pivot", "spread", "wmi", "psexec"]):
            return "lateral_movement"
        elif any(k in combined for k in ["exfil", "upload", "steal", "collect", "archive"]):
            return "actions_on_objectives"
        else:
            return "unknown"
    
    def _find_related_indicators(self, threat: Dict, matched_indicators: List[Dict]) -> List[RelatedIndicator]:
        """Find related indicators based on correlation"""
        related = []
        
        # If we matched against threat feeds, check for related IOCs
        for match in matched_indicators:
            # Add the matched indicator as related
            related.append(RelatedIndicator(
                ioc_type=match.get("type", "unknown"),
                value=match.get("value", ""),
                relationship="direct_match",
                source=match.get("source", "threat_intel"),
                confidence=match.get("confidence", 50)
            ))
        
        # Check if source IP is related to other threats
        source_ip = threat.get("source_ip")
        if source_ip and self._db is not None:
            # Would query DB for other threats from same IP
            related.append(RelatedIndicator(
                ioc_type="ip",
                value=source_ip,
                relationship="source_infrastructure",
                source="internal_correlation",
                confidence=70
            ))
        
        return related[:20]  # Limit to 20 related indicators
    
    def _generate_mitigations(self, threat: Dict, attribution: ThreatAttribution) -> List[Mitigation]:
        """Generate recommended mitigations based on threat type"""
        mitigations = []
        
        threat_type = threat.get("type", "").lower()
        severity = threat.get("severity", "medium").lower()
        
        # Get type-specific mitigations
        if "ransomware" in threat_type or attribution.campaign == "Ransomware":
            mitigations.extend(MITIGATION_LIBRARY["ransomware"])
        elif "malware" in threat_type:
            mitigations.extend(MITIGATION_LIBRARY["malware"])
        elif "botnet" in threat_type or attribution.campaign == "Botnet":
            mitigations.extend(MITIGATION_LIBRARY["botnet"])
        elif "ai" in threat_type or "agent" in threat_type:
            mitigations.extend(MITIGATION_LIBRARY["ai_agent"])
        elif "phishing" in threat_type:
            mitigations.extend(MITIGATION_LIBRARY["phishing"])
        else:
            mitigations.extend(MITIGATION_LIBRARY["default"])
        
        # Prioritize based on severity
        if severity == "critical":
            for m in mitigations:
                if m.priority in ["high", "medium"]:
                    m.priority = "critical"
        
        return mitigations
    
    async def _get_historical_context(self, threat: Dict) -> Dict[str, Any]:
        """Get historical context for the threat"""
        context = {
            "first_seen": threat.get("created_at"),
            "related_threats_count": 0,
            "previous_occurrences": 0,
            "trend": "unknown"
        }
        
        if self._db is not None:
            try:
                # Count related threats by type
                threat_type = threat.get("type")
                if threat_type:
                    count = await self._db.threats.count_documents({"type": threat_type})
                    context["related_threats_count"] = count
                
                # Check for previous occurrences from same source
                source_ip = threat.get("source_ip")
                if source_ip:
                    prev_count = await self._db.threats.count_documents({"source_ip": source_ip})
                    context["previous_occurrences"] = prev_count
                    
                    if prev_count > 5:
                        context["trend"] = "increasing"
                    elif prev_count > 1:
                        context["trend"] = "recurring"
                    else:
                        context["trend"] = "new"
                        
            except Exception as e:
                logger.debug(f"Historical context error: {e}")
        
        return context

    async def _collect_signal_context(self, threat: Dict) -> Dict[str, Any]:
        """Collect AI-agenticity and CCE session signals for scoring and prioritization."""
        context: Dict[str, Any] = {
            "session_id": None,
            "machine_likelihood": 0.0,
            "tool_switch_latency_ms": 0,
            "goal_persistence": 0.0,
            "agenticity_score": 0.0,
            "command_velocity": 0.0,
            "cbr": 0.0,
            "tbcr": 0.0,
            "cdi": 0.0,
            "autonomous_confidence": 0.0,
            "cognitive_pressure": 0.0,
            "ml_threat_score": 0.0,
            "ml_confidence": 0.0,
            "ml_category": None,
            "triune_policy_tier": None,
            "triune_recommended_actions": [],
        }

        metadata = threat.get("metadata") if isinstance(threat.get("metadata"), dict) else {}
        session_id = threat.get("session_id") or metadata.get("session_id")
        context["session_id"] = session_id

        # Explicit threat payload values take precedence when present.
        for key in [
            "machine_likelihood",
            "tool_switch_latency_ms",
            "goal_persistence",
            "agenticity_score",
            "command_velocity",
            "cbr",
            "tbcr",
            "cdi",
            "autonomous_confidence",
            "cognitive_pressure",
        ]:
            value = threat.get(key, metadata.get(key))
            if value is not None:
                try:
                    context[key] = float(value)
                except (TypeError, ValueError):
                    pass

        if session_id:
            try:
                from threat_response import AIDefenseEngine

                metrics = AIDefenseEngine.get_session_metrics(str(session_id))
                agenticity = metrics.get("agenticity") or {}
                exhaustion = metrics.get("exhaustion") or {}

                context["agenticity_score"] = max(context["agenticity_score"], float(agenticity.get("score") or 0.0))
                feature_vector = agenticity.get("feature_vector") or {}
                context["command_velocity"] = max(context["command_velocity"], float(feature_vector.get("command_velocity") or 0.0))
                context["autonomous_confidence"] = max(context["autonomous_confidence"], float(agenticity.get("score") or 0.0))
                context["cbr"] = max(context["cbr"], float(exhaustion.get("cbr") or 0.0))
                context["tbcr"] = max(context["tbcr"], float(exhaustion.get("tbcr") or 0.0))
                context["cdi"] = max(context["cdi"], float(exhaustion.get("cdi") or 0.0))
            except Exception:
                pass

            if self._db is not None:
                try:
                    summary = await self._db.cli_session_summaries.find_one(
                        {"session_id": str(session_id)},
                        sort=[("window_end", -1)]
                    )
                    if summary:
                        context["machine_likelihood"] = max(context["machine_likelihood"], float(summary.get("machine_likelihood") or 0.0))
                        context["tool_switch_latency_ms"] = float(summary.get("tool_switch_latency_ms") or context["tool_switch_latency_ms"])
                        context["goal_persistence"] = max(context["goal_persistence"], float(summary.get("goal_persistence") or 0.0))
                except Exception:
                    pass

        # ML predictor enrichment (best effort).
        try:
            from ml_threat_prediction import ml_predictor

            ml_payload = {
                "source_ip": threat.get("source_ip") or metadata.get("source_ip") or "unknown",
                "bytes_in": int(threat.get("bytes_in") or metadata.get("bytes_in") or 0),
                "bytes_out": int(threat.get("bytes_out") or metadata.get("bytes_out") or 0),
                "packets_in": int(threat.get("packets_in") or metadata.get("packets_in") or 0),
                "packets_out": int(threat.get("packets_out") or metadata.get("packets_out") or 0),
                "unique_destinations": int(threat.get("unique_destinations") or metadata.get("unique_destinations") or 0),
                "unique_ports": int(threat.get("unique_ports") or metadata.get("unique_ports") or 0),
                "dns_queries": int(threat.get("dns_queries") or metadata.get("dns_queries") or 0),
                "failed_connections": int(threat.get("failed_connections") or metadata.get("failed_connections") or 0),
                "encrypted_ratio": float(threat.get("encrypted_ratio") or metadata.get("encrypted_ratio") or 0.0),
                "avg_packet_size": float(threat.get("avg_packet_size") or metadata.get("avg_packet_size") or 0.0),
                "connection_duration": float(threat.get("connection_duration") or metadata.get("connection_duration") or 0.0),
                "port_scan_score": float(threat.get("port_scan_score") or metadata.get("port_scan_score") or 0.0),
            }
            ml_prediction = await ml_predictor.predict_network_threat(ml_payload)
            context["ml_threat_score"] = max(context["ml_threat_score"], float(getattr(ml_prediction, "threat_score", 0.0)) / 100.0)
            context["ml_confidence"] = max(context["ml_confidence"], float(getattr(ml_prediction, "confidence", 0.0)))
            context["ml_category"] = str(getattr(ml_prediction, "predicted_category", None))
        except Exception:
            pass

        # Triune/Cognition Fabric fused signal enrichment (best effort).
        if self._db is not None:
            try:
                from services.cognition_fabric import CognitionFabricService

                fabric = CognitionFabricService(self._db)
                world_snapshot = {
                    "entities": [{"id": str(threat.get("source_ip") or "unknown"), "type": "host"}],
                    "attack_path_graph": {"nodes": [], "edges": []},
                    "trust_state": {},
                    "recent_world_events": [],
                }
                cognition = await fabric.build_cognition_snapshot(
                    world_snapshot=world_snapshot,
                    event_type="threat_correlation",
                    entity_ids=[str(threat.get("source_ip") or "unknown")],
                    context={
                        "behavior": {
                            "command_velocity": context.get("command_velocity", 0.0),
                            "tool_switch_latency": context.get("tool_switch_latency_ms", 0.0),
                        }
                    },
                )
                fused = (cognition or {}).get("fused_signal") or {}
                context["cognitive_pressure"] = max(context["cognitive_pressure"], float(fused.get("cognitive_pressure") or 0.0))
                context["autonomous_confidence"] = max(context["autonomous_confidence"], float(fused.get("autonomous_confidence") or 0.0))
                context["triune_policy_tier"] = fused.get("recommended_policy_tier")
                context["triune_recommended_actions"] = fused.get("recommended_actions") or []
            except Exception:
                pass

        context["cognitive_pressure"] = max(
            context["cognitive_pressure"],
            (context["cbr"] * 0.4) + (context["tbcr"] * 0.35) + (context["cdi"] * 0.25)
        )
        return context
    
    def _generate_enrichment(
        self,
        threat: Dict,
        attribution: ThreatAttribution,
        matched: List[Dict],
        signal_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate enriched threat data"""
        enrichment = {
            "threat_score": self._calculate_threat_score(threat, attribution, matched, signal_context),
            "kill_chain_phase": self._identify_kill_chain_phase(threat),
            "mitre_tactics": self._map_to_mitre(threat),
            "recommended_actions": [],
            "ioc_summary": {
                "total_matched": len(matched),
                "sources": list(set(m.get("source", "") for m in matched)),
                "types": list(set(m.get("type", "") for m in matched))
            },
            "ai_pressure": signal_context or {},
        }
        
        # Add recommended actions based on threat score
        if enrichment["threat_score"] >= 80:
            enrichment["recommended_actions"] = ["immediate_isolation", "incident_response", "forensic_analysis"]
        elif enrichment["threat_score"] >= 60:
            enrichment["recommended_actions"] = ["enhanced_monitoring", "containment", "investigation"]
        else:
            enrichment["recommended_actions"] = ["monitoring", "documentation"]
        
        return enrichment
    
    def _calculate_threat_score(
        self,
        threat: Dict,
        attribution: ThreatAttribution,
        matched: List[Dict],
        signal_context: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Calculate overall threat score (0-100)"""
        score = 0
        
        # Base score from severity
        severity_scores = {"critical": 40, "high": 30, "medium": 20, "low": 10}
        score += severity_scores.get(threat.get("severity", "medium").lower(), 20)
        
        # Attribution confidence bonus
        if attribution.confidence == "high":
            score += 20
        elif attribution.confidence == "medium":
            score += 10
        
        # Known threat actor bonus
        if attribution.threat_actor:
            score += 15
        
        # Matched indicators bonus
        score += min(len(matched) * 5, 25)

        # Agenticity + logic-budget pressure bonuses
        signal_context = signal_context or {}
        if float(signal_context.get("agenticity_score") or 0.0) >= 0.70:
            score += 12
        if float(signal_context.get("cdi") or 0.0) >= 0.60:
            score += 10
        if float(signal_context.get("machine_likelihood") or 0.0) >= 0.70:
            score += 8
        if float(signal_context.get("cognitive_pressure") or 0.0) >= 0.70:
            score += 8
        if float(signal_context.get("ml_threat_score") or 0.0) >= 0.70:
            score += 8
        if float(signal_context.get("ml_confidence") or 0.0) >= 0.70:
            score += 6
        
        return min(100, score)
    
    def _identify_kill_chain_phase(self, threat: Dict) -> str:
        """Identify Cyber Kill Chain phase"""
        threat_type = threat.get("type", "").lower()
        description = threat.get("description", "").lower()
        
        if any(k in description for k in ["reconnaissance", "scanning", "enumeration"]):
            return "Reconnaissance"
        elif any(k in description for k in ["exploit", "vulnerability", "cve"]):
            return "Weaponization/Exploitation"
        elif any(k in description for k in ["download", "dropper", "payload"]):
            return "Delivery"
        elif any(k in description for k in ["install", "persistence", "registry"]):
            return "Installation"
        elif any(k in description for k in ["c2", "beacon", "callback", "command"]):
            return "Command & Control"
        elif any(k in description for k in ["exfil", "steal", "extract", "encrypt"]):
            return "Actions on Objectives"
        else:
            return "Unknown"
    
    def _map_to_mitre(self, threat: Dict) -> List[str]:
        """Map threat to MITRE ATT&CK tactics"""
        tactics = []
        threat_type = threat.get("type", "").lower()
        description = threat.get("description", "").lower()
        
        mitre_mapping = {
            "Initial Access": ["phishing", "exploit", "drive-by"],
            "Execution": ["script", "command", "powershell", "payload"],
            "Persistence": ["registry", "startup", "scheduled", "service"],
            "Privilege Escalation": ["escalat", "root", "admin", "sudo"],
            "Defense Evasion": ["obfuscat", "encrypt", "pack", "hide"],
            "Credential Access": ["credential", "password", "hash", "mimikatz"],
            "Discovery": ["scan", "enumerat", "discover", "recon"],
            "Lateral Movement": ["lateral", "spread", "pivot", "smb"],
            "Collection": ["collect", "keylog", "screen", "clipboard"],
            "Exfiltration": ["exfil", "upload", "transfer", "steal"],
            "Impact": ["ransomware", "encrypt", "destroy", "wipe"]
        }
        
        for tactic, keywords in mitre_mapping.items():
            for keyword in keywords:
                if keyword in description or keyword in threat_type:
                    if tactic not in tactics:
                        tactics.append(tactic)
                    break
        
        return tactics if tactics else ["Unknown"]
    
    def _calculate_confidence(self, result: CorrelationResult) -> str:
        """Calculate overall correlation confidence"""
        score = 0
        
        # Matched indicators
        score += len(result.matched_indicators) * 10
        
        # Attribution confidence
        if result.attribution.confidence == "high":
            score += 30
        elif result.attribution.confidence == "medium":
            score += 20
        elif result.attribution.confidence == "low":
            score += 10
        
        # Related indicators
        score += len(result.related_indicators) * 5
        
        # Historical context
        if result.historical_context.get("previous_occurrences", 0) > 0:
            score += 10

        # Confidence lift from autonomous campaign pressure signals.
        ai_pressure = result.enrichment_data.get("ai_pressure") if isinstance(result.enrichment_data, dict) else {}
        if isinstance(ai_pressure, dict):
            if float(ai_pressure.get("agenticity_score") or 0.0) >= 0.70:
                score += 8
            if float(ai_pressure.get("cdi") or 0.0) >= 0.60:
                score += 8
            if float(ai_pressure.get("machine_likelihood") or 0.0) >= 0.70:
                score += 6
            if float(ai_pressure.get("ml_threat_score") or 0.0) >= 0.70:
                score += 6
            if float(ai_pressure.get("ml_confidence") or 0.0) >= 0.70:
                score += 4
        
        if score >= 50:
            return CorrelationConfidence.HIGH.value
        elif score >= 30:
            return CorrelationConfidence.MEDIUM.value
        elif score >= 10:
            return CorrelationConfidence.LOW.value
        else:
            return CorrelationConfidence.NONE.value
    
    async def _execute_auto_actions(self, threat: Dict, result: CorrelationResult) -> List[str]:
        """Execute automated response actions"""
        actions_taken = []
        
        # Only execute for high-confidence, critical threats
        if result.confidence not in ["high", "medium"]:
            return actions_taken
        
        severity = threat.get("severity", "").lower()
        if severity not in ["critical", "high"]:
            return actions_taken
        
        # Auto-block source IP if matched in threat feeds
        source_ip = threat.get("source_ip")
        if source_ip and any(m.get("type") == "ip" for m in result.matched_indicators):
            # Would call threat_response.block_ip here
            actions_taken.append(f"auto_block_ip:{source_ip}")
            logger.info(f"Auto-action: Would block IP {source_ip}")
        
        # Log the correlation
        if self._db is not None:
            await self._db.auto_actions.insert_one({
                "threat_id": threat.get("id"),
                "correlation_id": result.correlation_id,
                "actions": actions_taken,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        
        return actions_taken
    
    async def correlate_all_active_threats(self) -> List[CorrelationResult]:
        """Correlate all active threats"""
        results = []
        
        if self._db is None:
            return results
        
        threats = await self._db.threats.find(
            {"status": "active"},
            {"_id": 0}
        ).to_list(100)
        
        for threat in threats:
            result = await self.correlate_threat(threat)
            results.append(result)
        
        return results
    
    def get_correlation(self, threat_id: str) -> Optional[CorrelationResult]:
        """Get cached correlation result"""
        return self.correlation_cache.get(threat_id)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get correlation engine statistics"""
        return {
            "cached_correlations": len(self.correlation_cache),
            "auto_correlate_enabled": self.auto_correlate_enabled,
            "known_threat_actors": len(THREAT_ACTORS),
            "campaign_patterns": len(CAMPAIGN_PATTERNS)
        }


# Global instance
correlation_engine = ThreatCorrelationEngine()
