"""
Identity Protection Module
==========================
Enterprise-grade Active Directory, Kerberos, and LDAP attack detection.

This module provides comprehensive protection against identity-based attacks:
- Active Directory attack detection (DCSync, DCShadow, AdminSDHolder abuse)
- Kerberos attack detection (Kerberoasting, AS-REP Roasting, Golden/Silver/Diamond/Sapphire Tickets)
- LDAP attack detection (Reconnaissance, Injection, Relay, Shadow Credentials)
- Credential threat analysis (Pass-the-Hash, Pass-the-Ticket, Overpass-the-Hash, DPAPI abuse)

MITRE ATT&CK Coverage:
- T1003: OS Credential Dumping
- T1003.001: LSASS Memory
- T1003.002: Security Account Manager
- T1003.003: NTDS
- T1003.004: LSA Secrets
- T1003.005: Cached Domain Credentials
- T1003.006: DCSync
- T1078.002: Domain Accounts
- T1110: Brute Force
- T1110.001: Password Guessing
- T1110.003: Password Spraying
- T1134.005: SID-History Injection
- T1187: Forced Authentication
- T1207: Rogue Domain Controller (DCShadow)
- T1550: Use Alternate Authentication Material
- T1550.002: Pass the Hash
- T1550.003: Pass the Ticket
- T1556.001: Directory Services (Skeleton Key)
- T1557: Adversary-in-the-Middle
- T1557.001: LLMNR/NBT-NS Poisoning (NTLM Relay)
- T1558: Steal or Forge Kerberos Tickets
- T1558.001: Golden Ticket
- T1558.002: Silver Ticket
- T1558.003: Kerberoasting
- T1558.004: AS-REP Roasting

Detection Techniques:
- Behavioral baseline deviation analysis
- Encryption type downgrade detection
- Ticket lifetime anomaly detection
- Cross-realm trust abuse detection
- Delegation abuse detection (constrained/unconstrained/RBCD)
- Shadow Credentials attack detection
- Certificate-based attack detection (AD CS abuse)
- DPAPI backup key extraction detection
- AdminSDHolder modification detection
- SID History injection detection

References:
- Microsoft ATA/Azure ATP detection patterns
- CrowdStrike Falcon Identity Protection
- Semperis Directory Services Protector
- SpecterOps BloodHound research
- Mandiant/FireEye AD attack research

Author: Metatron Security Team
Version: 2.0.0
Date: March 2026
"""

import os
import re
import json
import hashlib
import hmac
import logging
import ipaddress
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Tuple, Set, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum, auto
from collections import defaultdict
from functools import lru_cache
import statistics
import math
import secrets
import struct
import base64

logger = logging.getLogger(__name__)


# =============================================================================
# WINDOWS SECURITY EVENT IDS
# =============================================================================

class WindowsSecurityEventID:
    """Windows Security Event IDs for identity attack correlation"""
    
    # Kerberos Events
    KERBEROS_TGT_REQUEST = 4768           # TGT requested (AS-REQ)
    KERBEROS_SERVICE_TICKET = 4769        # Service ticket requested (TGS-REQ)
    KERBEROS_RENEWAL = 4770               # TGT renewed
    KERBEROS_PREAUTH_FAILED = 4771        # Kerberos pre-authentication failed
    KERBEROS_SERVICE_TICKET_FAILED = 4773  # Service ticket request failed
    
    # Logon Events
    SUCCESSFUL_LOGON = 4624
    FAILED_LOGON = 4625
    ACCOUNT_LOGOFF = 4634
    ACCOUNT_LOCKOUT = 4740
    EXPLICIT_CREDENTIAL_LOGON = 4648
    SPECIAL_PRIVILEGES_ASSIGNED = 4672
    
    # Credential Events
    CREDENTIAL_VALIDATION_NTLM = 4776     # NTLM credential validation
    SENSITIVE_PRIVILEGE_USE = 4673
    CREDENTIAL_MANAGER_READ = 5379
    
    # Directory Service Events
    DIRECTORY_SERVICE_ACCESS = 4662
    DIRECTORY_SERVICE_CHANGE = 5136
    DIRECTORY_SERVICE_REPLICATION = 4929
    DIRECTORY_SERVICE_OBJECT_MODIFIED = 5137
    
    # Account Management
    USER_ACCOUNT_CREATED = 4720
    USER_ACCOUNT_ENABLED = 4722
    USER_PASSWORD_CHANGED = 4723
    USER_PASSWORD_RESET = 4724
    USER_ACCOUNT_DISABLED = 4725
    USER_ACCOUNT_DELETED = 4726
    SECURITY_GROUP_MEMBER_ADDED = 4728
    DOMAIN_LOCAL_GROUP_MEMBER_ADDED = 4732
    UNIVERSAL_GROUP_MEMBER_ADDED = 4756
    
    # Certificate Services
    CERTIFICATE_REQUESTED = 4886
    CERTIFICATE_ISSUED = 4887
    CERTIFICATE_PENDING = 4888
    
    # Trust Events
    FOREST_TRUST_INFO_CHANGED = 4865
    KERBEROS_POLICY_CHANGED = 4713
    TRUSTED_DOMAIN_MODIFIED = 4716


class LogonType:
    """Windows logon types for authentication analysis"""
    INTERACTIVE = 2           # Console logon
    NETWORK = 3               # Network logon (SMB, etc.)
    BATCH = 4                 # Batch job
    SERVICE = 5               # Service account
    UNLOCK = 7                # Workstation unlock
    NETWORK_CLEARTEXT = 8     # Clear text network logon
    NEW_CREDENTIALS = 9       # RunAs /netonly
    REMOTE_INTERACTIVE = 10   # RDP
    CACHED_INTERACTIVE = 11   # Cached credentials
    CACHED_REMOTE = 12        # Cached RDP
    CACHED_UNLOCK = 13        # Cached unlock


class KerberosErrorCode:
    """Kerberos error codes for attack detection"""
    KDC_ERR_NONE = 0
    KDC_ERR_NAME_EXP = 1              # Client's entry expired
    KDC_ERR_SERVICE_EXP = 2           # Server's entry expired
    KDC_ERR_BAD_PVNO = 3              # Bad protocol version
    KDC_ERR_C_OLD_MAST_KVNO = 4       # Old master key version
    KDC_ERR_S_OLD_MAST_KVNO = 5       # Server's key version old
    KDC_ERR_C_PRINCIPAL_UNKNOWN = 6   # Client not found (user enum)
    KDC_ERR_S_PRINCIPAL_UNKNOWN = 7   # Server not found
    KDC_ERR_PRINCIPAL_NOT_UNIQUE = 8
    KDC_ERR_NULL_KEY = 9
    KDC_ERR_CANNOT_POSTDATE = 10
    KDC_ERR_NEVER_VALID = 11
    KDC_ERR_POLICY = 12
    KDC_ERR_BADOPTION = 13
    KDC_ERR_ETYPE_NOSUPP = 14         # Encryption type not supported
    KDC_ERR_PREAUTH_REQUIRED = 25     # Pre-auth required (AS-REP roast indicator)
    KDC_ERR_PREAUTH_FAILED = 24       # Pre-auth failed
    KDC_ERR_CLIENT_REVOKED = 18
    KDC_ERR_SERVICE_REVOKED = 19
    KDC_ERR_TGT_REVOKED = 20
    KDC_ERR_KEY_EXPIRED = 23


# =============================================================================
# ENUMS AND DATA CLASSES
# =============================================================================

class AttackCategory(Enum):
    """Categories of identity-based attacks"""
    KERBEROS = "kerberos"
    LDAP = "ldap"
    AD_REPLICATION = "ad_replication"
    CREDENTIAL_THEFT = "credential_theft"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    PERSISTENCE = "persistence"
    LATERAL_MOVEMENT = "lateral_movement"
    RECONNAISSANCE = "reconnaissance"
    CERTIFICATE_ABUSE = "certificate_abuse"
    DELEGATION_ABUSE = "delegation_abuse"
    TRUST_ABUSE = "trust_abuse"


class ThreatSeverity(Enum):
    """Threat severity levels aligned with MITRE"""
    CRITICAL = "critical"  # Immediate compromise (DCSync, Golden Ticket)
    HIGH = "high"          # Active attack (Kerberoasting, PtH)
    MEDIUM = "medium"      # Suspicious activity (LDAP recon)
    LOW = "low"            # Anomaly requiring investigation
    INFO = "info"          # Informational event


class KerberosMessageType(Enum):
    """Kerberos protocol message types"""
    AS_REQ = 10   # Authentication Service Request
    AS_REP = 11   # Authentication Service Response
    TGS_REQ = 12  # Ticket Granting Service Request
    TGS_REP = 13  # Ticket Granting Service Response
    AP_REQ = 14   # Application Request
    AP_REP = 15   # Application Response
    KRB_ERROR = 30  # Kerberos Error


class EncryptionType(Enum):
    """Kerberos encryption types (etype)"""
    DES_CBC_CRC = 1
    DES_CBC_MD4 = 2
    DES_CBC_MD5 = 3
    RC4_HMAC = 23          # Vulnerable to Kerberoasting
    RC4_HMAC_EXP = 24
    AES128_CTS_HMAC_SHA1 = 17
    AES256_CTS_HMAC_SHA1 = 18
    AES128_CTS_HMAC_SHA256 = 19
    AES256_CTS_HMAC_SHA384 = 20


class LDAPOperation(Enum):
    """LDAP operation types"""
    BIND = "bind"
    SEARCH = "search"
    MODIFY = "modify"
    ADD = "add"
    DELETE = "delete"
    MODIFY_DN = "modify_dn"
    COMPARE = "compare"
    ABANDON = "abandon"
    EXTENDED = "extended"


@dataclass
class KerberosTicketInfo:
    """Information about a Kerberos ticket"""
    ticket_id: str
    client_principal: str
    server_principal: str
    encryption_type: int
    ticket_flags: int
    auth_time: datetime
    start_time: datetime
    end_time: datetime
    renew_until: Optional[datetime]
    client_addresses: List[str]
    realm: str
    
    # Anomaly indicators
    is_renewable: bool = False
    is_forwardable: bool = False
    is_proxiable: bool = False
    lifetime_hours: float = 0.0
    
    def __post_init__(self):
        self.lifetime_hours = (self.end_time - self.start_time).total_seconds() / 3600
        self.is_renewable = bool(self.ticket_flags & 0x00800000)
        self.is_forwardable = bool(self.ticket_flags & 0x40000000)
        self.is_proxiable = bool(self.ticket_flags & 0x10000000)


@dataclass
class LDAPQueryInfo:
    """Information about an LDAP query"""
    query_id: str
    timestamp: datetime
    source_ip: str
    bind_dn: str
    operation: LDAPOperation
    base_dn: str
    scope: int  # 0=base, 1=one-level, 2=subtree
    filter_str: str
    attributes: List[str]
    result_count: int
    response_time_ms: float
    
    # Parsed filter components
    filter_objects: List[str] = field(default_factory=list)
    filter_attributes: List[str] = field(default_factory=list)


@dataclass
class ADReplicationEvent:
    """Active Directory replication event"""
    event_id: str
    timestamp: datetime
    source_dc: str
    destination_dc: str
    replication_type: str  # "inbound", "outbound", "rogue"
    naming_context: str
    object_count: int
    attributes_replicated: List[str]
    source_ip: str
    is_legitimate_dc: bool = True


@dataclass 
class IdentityThreatEvent:
    """A detected identity threat event"""
    event_id: str
    timestamp: datetime
    category: AttackCategory
    attack_type: str
    severity: ThreatSeverity
    source_ip: str
    target_principal: str
    description: str
    evidence: Dict[str, Any]
    mitre_techniques: List[str]
    recommendations: List[str]
    confidence: float  # 0.0 - 1.0
    raw_event: Optional[Dict[str, Any]] = None


# =============================================================================
# KERBEROS ATTACK DETECTOR
# =============================================================================

class KerberosAttackDetector:
    """
    Detects Kerberos-based attacks including:
    - Kerberoasting (T1558.003)
    - AS-REP Roasting (T1558.004)
    - Golden Ticket (T1558.001)
    - Silver Ticket (T1558.002)
    - Overpass-the-Hash / Pass-the-Key (T1550.002)
    - Skeleton Key (T1556.001)
    - Diamond Ticket
    - Sapphire Ticket
    """
    
    def __init__(self):
        # Configuration
        self.config = {
            # Kerberoasting detection
            "kerberoast_tgs_threshold": 5,      # TGS requests per minute per user
            "kerberoast_spn_threshold": 10,     # Unique SPNs requested per hour
            "kerberoast_rc4_ratio_alert": 0.5,  # Alert if >50% requests use RC4
            
            # AS-REP Roasting detection  
            "asrep_threshold": 10,              # AS-REP without preauth per hour
            "asrep_unique_users_threshold": 5,  # Different users targeted
            
            # Golden/Silver Ticket detection
            "ticket_lifetime_max_hours": 10,    # Normal TGT lifetime
            "ticket_forwardable_alert": True,   # Alert on forwardable tickets
            "known_dcs": set(),                 # Legitimate Domain Controllers
            
            # Timing analysis
            "time_window_seconds": 300,         # 5-minute sliding window
            "baseline_period_hours": 24,        # Baseline calculation period
        }
        
        # State tracking
        self.tgs_request_history: Dict[str, List[Tuple[datetime, str]]] = defaultdict(list)  # user -> [(time, spn)]
        self.asrep_history: Dict[str, List[datetime]] = defaultdict(list)  # ip -> [timestamps]
        self.ticket_cache: Dict[str, KerberosTicketInfo] = {}  # ticket_id -> info
        self.encryption_stats: Dict[str, Dict[int, int]] = defaultdict(lambda: defaultdict(int))  # user -> {etype: count}
        self.spn_access_patterns: Dict[str, Set[str]] = defaultdict(set)  # user -> {spns}
        
        # Known attack patterns
        self.kerberoasting_tools = {
            "rubeus", "getuserspns.py", "invoke-kerberoast", "kerberoast",
            "hashcat", "john", "tgsrepcrack", "impacket"
        }
        
        # Sensitive SPNs that shouldn't be mass-requested
        self.sensitive_spn_patterns = [
            r"krbtgt/.*",           # Key Distribution Center
            r"ldap/.*",             # LDAP services
            r"cifs/.*",             # File shares
            r"http/.*",             # Web services  
            r"mssqlsvc/.*",         # SQL Server
            r"exchange.*/.*",       # Exchange services
            r"termserv/.*",         # Terminal Services
            r"wsman/.*",            # WS-Management
            r"host/.*",             # Computer accounts
        ]
        
        logger.info("KerberosAttackDetector initialized")
    
    def analyze_tgs_request(self, event: Dict[str, Any]) -> Optional[IdentityThreatEvent]:
        """
        Analyze a TGS-REQ event for Kerberoasting indicators.
        
        Kerberoasting detection based on:
        1. High volume of TGS requests for different SPNs
        2. Preference for RC4 encryption (weaker, easier to crack)
        3. Requests for service accounts (not computer accounts)
        4. Unusual timing patterns (bursts of requests)
        5. Known tool signatures
        """
        timestamp = datetime.fromisoformat(event.get("timestamp", datetime.now(timezone.utc).isoformat()))
        user = event.get("client_principal", "unknown")
        spn = event.get("server_principal", "unknown")
        etype = event.get("encryption_type", 0)
        source_ip = event.get("source_ip", "unknown")
        
        # Track request
        self.tgs_request_history[user].append((timestamp, spn))
        self.spn_access_patterns[user].add(spn)
        self.encryption_stats[user][etype] += 1
        
        # Clean old entries (sliding window)
        cutoff = timestamp - timedelta(seconds=self.config["time_window_seconds"])
        self.tgs_request_history[user] = [
            (t, s) for t, s in self.tgs_request_history[user] if t > cutoff
        ]
        
        # Check for Kerberoasting indicators
        threats = []
        confidence = 0.0
        evidence = {
            "user": user,
            "source_ip": source_ip,
            "current_spn": spn,
            "encryption_type": etype,
            "timestamp": timestamp.isoformat()
        }
        
        # Indicator 1: High volume of TGS requests
        recent_requests = len(self.tgs_request_history[user])
        if recent_requests >= self.config["kerberoast_tgs_threshold"]:
            threats.append(f"High TGS request volume: {recent_requests} in {self.config['time_window_seconds']}s")
            confidence += 0.3
            evidence["request_count"] = recent_requests
        
        # Indicator 2: Many unique SPNs
        unique_spns = len(self.spn_access_patterns[user])
        if unique_spns >= self.config["kerberoast_spn_threshold"]:
            threats.append(f"Many unique SPNs requested: {unique_spns}")
            confidence += 0.25
            evidence["unique_spns"] = unique_spns
        
        # Indicator 3: RC4 encryption preference
        total_requests = sum(self.encryption_stats[user].values())
        rc4_requests = self.encryption_stats[user].get(EncryptionType.RC4_HMAC.value, 0)
        if total_requests > 0:
            rc4_ratio = rc4_requests / total_requests
            if rc4_ratio >= self.config["kerberoast_rc4_ratio_alert"]:
                threats.append(f"High RC4 usage: {rc4_ratio:.1%}")
                confidence += 0.25
                evidence["rc4_ratio"] = rc4_ratio
        
        # Indicator 4: Service account targeting (not computer accounts)
        if not spn.endswith("$") and any(re.match(p, spn, re.IGNORECASE) for p in self.sensitive_spn_patterns):
            threats.append(f"Sensitive SPN targeted: {spn}")
            confidence += 0.15
            evidence["sensitive_spn"] = True
        
        # Indicator 5: Burst pattern detection
        if len(self.tgs_request_history[user]) >= 3:
            times = [t for t, _ in self.tgs_request_history[user]]
            intervals = [(times[i+1] - times[i]).total_seconds() for i in range(len(times)-1)]
            avg_interval = statistics.mean(intervals) if intervals else 60
            if avg_interval < 2:  # Less than 2 seconds between requests
                threats.append(f"Automated burst pattern detected: {avg_interval:.2f}s intervals")
                confidence += 0.2
                evidence["avg_interval_seconds"] = avg_interval
        
        # Generate threat event if confidence exceeds threshold
        if confidence >= 0.5:
            return IdentityThreatEvent(
                event_id=f"kerb_{secrets.token_hex(8)}",
                timestamp=timestamp,
                category=AttackCategory.KERBEROS,
                attack_type="kerberoasting",
                severity=ThreatSeverity.HIGH if confidence >= 0.7 else ThreatSeverity.MEDIUM,
                source_ip=source_ip,
                target_principal=user,
                description=f"Potential Kerberoasting attack detected: {'; '.join(threats)}",
                evidence=evidence,
                mitre_techniques=["T1558.003"],
                recommendations=[
                    "Review service account permissions",
                    "Rotate service account passwords",
                    "Enable AES-only encryption for service accounts",
                    "Use Group Managed Service Accounts (gMSAs)",
                    "Monitor for offline password cracking attempts"
                ],
                confidence=min(1.0, confidence),
                raw_event=event
            )
        
        return None
    
    def analyze_as_rep(self, event: Dict[str, Any]) -> Optional[IdentityThreatEvent]:
        """
        Analyze AS-REP events for AS-REP Roasting indicators.
        
        AS-REP Roasting targets accounts with "Do not require Kerberos preauthentication"
        enabled, allowing offline password cracking.
        """
        timestamp = datetime.fromisoformat(event.get("timestamp", datetime.now(timezone.utc).isoformat()))
        source_ip = event.get("source_ip", "unknown")
        target_user = event.get("client_principal", "unknown")
        preauth_required = event.get("preauth_required", True)
        error_code = event.get("error_code", 0)
        
        # Track AS-REP without preauth
        if not preauth_required or error_code == 0x18:  # KDC_ERR_PREAUTH_FAILED indicates enumeration
            self.asrep_history[source_ip].append(timestamp)
        
        # Clean old entries
        cutoff = timestamp - timedelta(hours=1)
        self.asrep_history[source_ip] = [t for t in self.asrep_history[source_ip] if t > cutoff]
        
        # Check threshold
        asrep_count = len(self.asrep_history[source_ip])
        
        if asrep_count >= self.config["asrep_threshold"]:
            # Track unique users targeted (would need additional state)
            return IdentityThreatEvent(
                event_id=f"asrep_{secrets.token_hex(8)}",
                timestamp=timestamp,
                category=AttackCategory.KERBEROS,
                attack_type="asrep_roasting",
                severity=ThreatSeverity.HIGH,
                source_ip=source_ip,
                target_principal=target_user,
                description=f"AS-REP Roasting attack detected: {asrep_count} AS-REP requests without preauth from {source_ip}",
                evidence={
                    "asrep_count": asrep_count,
                    "source_ip": source_ip,
                    "target_user": target_user,
                    "preauth_required": preauth_required,
                    "window_hours": 1
                },
                mitre_techniques=["T1558.004"],
                recommendations=[
                    "Enable Kerberos pre-authentication for all accounts",
                    "Audit accounts with 'Do not require Kerberos preauthentication'",
                    "Block source IP if confirmed malicious",
                    "Review affected account passwords"
                ],
                confidence=0.85,
                raw_event=event
            )
        
        return None
    
    def analyze_ticket(self, ticket: KerberosTicketInfo) -> Optional[IdentityThreatEvent]:
        """
        Analyze a Kerberos ticket for Golden/Silver Ticket indicators.
        
        Detection based on:
        1. Abnormal ticket lifetime (Golden tickets often have long lifetimes)
        2. Encryption type anomalies
        3. Unknown or suspicious issuing KDC
        4. forwardable/renewable flags without matching policy
        5. SID history anomalies
        6. Timestamp inconsistencies
        """
        threats = []
        confidence = 0.0
        evidence = {
            "ticket_id": ticket.ticket_id,
            "client": ticket.client_principal,
            "server": ticket.server_principal,
            "encryption_type": ticket.encryption_type,
            "lifetime_hours": ticket.lifetime_hours
        }
        
        # Indicator 1: Abnormal lifetime
        if ticket.lifetime_hours > self.config["ticket_lifetime_max_hours"]:
            threats.append(f"Abnormal ticket lifetime: {ticket.lifetime_hours:.1f} hours (max: {self.config['ticket_lifetime_max_hours']})")
            confidence += 0.35
            evidence["lifetime_anomaly"] = True
        
        # Indicator 2: Weak encryption on privileged ticket
        if ticket.encryption_type == EncryptionType.RC4_HMAC.value:
            if "krbtgt" in ticket.server_principal.lower():
                threats.append("TGT using RC4 encryption (potential Golden Ticket)")
                confidence += 0.3
                evidence["weak_encryption_tgt"] = True
        
        # Indicator 3: Check if issued by legitimate DC
        # For Golden Tickets, the KDC might not be a real DC
        if self.config["known_dcs"] and ticket.realm not in self.config["known_dcs"]:
            threats.append(f"Ticket from unknown KDC realm: {ticket.realm}")
            confidence += 0.25
            evidence["unknown_kdc"] = True
        
        # Indicator 4: Suspicious flags
        if ticket.is_forwardable and ticket.is_renewable:
            # Check if this matches policy (simplified - would need policy lookup)
            threats.append("Ticket has forwardable AND renewable flags")
            confidence += 0.1
            evidence["suspicious_flags"] = True
        
        # Indicator 5: Krbtgt ticket analysis
        if "krbtgt" in ticket.server_principal.lower():
            # TGT-specific checks
            if ticket.renew_until:
                renew_lifetime = (ticket.renew_until - ticket.start_time).total_seconds() / 3600
                if renew_lifetime > 168:  # More than 7 days
                    threats.append(f"TGT has excessive renewal period: {renew_lifetime:.1f} hours")
                    confidence += 0.25
                    evidence["excessive_renewal"] = renew_lifetime
        
        # Determine attack type based on target
        attack_type = "golden_ticket" if "krbtgt" in ticket.server_principal.lower() else "silver_ticket"
        mitre_tech = "T1558.001" if attack_type == "golden_ticket" else "T1558.002"
        
        if confidence >= 0.5:
            return IdentityThreatEvent(
                event_id=f"ticket_{secrets.token_hex(8)}",
                timestamp=datetime.now(timezone.utc),
                category=AttackCategory.KERBEROS,
                attack_type=attack_type,
                severity=ThreatSeverity.CRITICAL,
                source_ip="unknown",
                target_principal=ticket.client_principal,
                description=f"Potential {attack_type.replace('_', ' ').title()} detected: {'; '.join(threats)}",
                evidence=evidence,
                mitre_techniques=[mitre_tech],
                recommendations=[
                    "Reset the KRBTGT password twice (for Golden Ticket)" if attack_type == "golden_ticket" else "Reset service account password",
                    "Investigate compromised service account",
                    "Review recent authentications from affected principal",
                    "Enable Advanced Audit Policy for Kerberos",
                    "Consider implementing Protected Users security group"
                ],
                confidence=min(1.0, confidence)
            )
        
        return None
    
    def detect_skeleton_key(self, event: Dict[str, Any]) -> Optional[IdentityThreatEvent]:
        """
        Detect Skeleton Key attack indicators.
        
        Skeleton Key modifies LSASS on domain controllers to allow
        authentication with a master password.
        """
        event_type = event.get("event_type", "")
        source_dc = event.get("source_dc", "")
        
        indicators = []
        confidence = 0.0
        
        # Indicator 1: LSASS memory modification
        if event.get("lsass_modified"):
            indicators.append("LSASS memory modification detected on DC")
            confidence += 0.4
        
        # Indicator 2: Suspicious DLL loaded into LSASS
        loaded_dlls = event.get("loaded_dlls", [])
        suspicious_dlls = ["msv1_0", "kerberos", "negoexts", "pku2u", "schannel"]
        for dll in loaded_dlls:
            if any(s in dll.lower() for s in suspicious_dlls) and "unsigned" in event.get("dll_signature", "unsigned"):
                indicators.append(f"Unsigned security DLL: {dll}")
                confidence += 0.3
        
        # Indicator 3: Authentication anomaly (same password works for multiple accounts)
        if event.get("multi_account_same_ntlm"):
            indicators.append("Same NTLM hash authenticated multiple accounts")
            confidence += 0.4
        
        if confidence >= 0.5:
            return IdentityThreatEvent(
                event_id=f"skeleton_{secrets.token_hex(8)}",
                timestamp=datetime.now(timezone.utc),
                category=AttackCategory.PERSISTENCE,
                attack_type="skeleton_key",
                severity=ThreatSeverity.CRITICAL,
                source_ip=event.get("source_ip", "unknown"),
                target_principal=source_dc,
                description=f"Potential Skeleton Key attack on DC {source_dc}: {'; '.join(indicators)}",
                evidence={
                    "indicators": indicators,
                    "affected_dc": source_dc,
                    "raw_event": event
                },
                mitre_techniques=["T1556.001"],
                recommendations=[
                    "Restart affected Domain Controller immediately",
                    "Perform memory forensics on DC",
                    "Reset KRBTGT password twice",
                    "Investigate all DC authentications since compromise",
                    "Enable Credential Guard on DCs"
                ],
                confidence=min(1.0, confidence)
            )
        
        return None
    
    def detect_diamond_ticket(self, event: Dict[str, Any]) -> Optional[IdentityThreatEvent]:
        """
        Detect Diamond Ticket attacks.
        
        Diamond Ticket is an advanced variant of Golden Ticket that:
        1. Uses a legitimately issued TGT
        2. Modifies the PAC to add privileges
        3. Re-signs with KRBTGT key
        
        Detection based on:
        - PAC checksum anomalies
        - Privilege modifications without corresponding events
        - Server checksum verification failures
        """
        ticket_data = event.get("ticket_data", {})
        pac_data = event.get("pac_data", {})
        
        indicators = []
        confidence = 0.0
        evidence = {
            "client_principal": event.get("client_principal", "unknown"),
            "source_ip": event.get("source_ip", "unknown"),
            "timestamp": event.get("timestamp", datetime.now(timezone.utc).isoformat())
        }
        
        # Indicator 1: PAC checksum mismatch
        if pac_data.get("server_checksum_valid") is False:
            indicators.append("PAC server checksum validation failed")
            confidence += 0.4
            evidence["pac_checksum_failed"] = True
        
        # Indicator 2: Privileged group SIDs without corresponding group membership events
        extra_sids = pac_data.get("extra_sids", [])
        privileged_sids = {
            "S-1-5-21-*-512": "Domain Admins",
            "S-1-5-21-*-519": "Enterprise Admins",
            "S-1-5-21-*-518": "Schema Admins",
            "S-1-5-32-544": "Administrators"
        }
        for sid in extra_sids:
            for pattern, group in privileged_sids.items():
                if re.match(pattern.replace("*", "\\d+"), sid):
                    if not event.get("group_membership_verified"):
                        indicators.append(f"Privileged SID {group} without verified membership")
                        confidence += 0.3
                        evidence["unverified_privileged_sid"] = sid
        
        # Indicator 3: PAC modification timestamp anomaly
        pac_auth_time = pac_data.get("auth_time")
        ticket_auth_time = ticket_data.get("auth_time")
        if pac_auth_time and ticket_auth_time:
            try:
                pac_ts = datetime.fromisoformat(pac_auth_time.replace('Z', '+00:00'))
                ticket_ts = datetime.fromisoformat(ticket_auth_time.replace('Z', '+00:00'))
                if abs((pac_ts - ticket_ts).total_seconds()) > 5:
                    indicators.append("PAC auth time doesn't match ticket auth time")
                    confidence += 0.3
                    evidence["auth_time_mismatch"] = True
            except (ValueError, TypeError):
                pass
        
        # Indicator 4: Resource SIDs in TGT (should only be in service tickets)
        if ticket_data.get("is_tgt") and pac_data.get("resource_group_sids"):
            indicators.append("Resource group SIDs present in TGT (Diamond Ticket signature)")
            confidence += 0.35
            evidence["resource_sids_in_tgt"] = True
        
        if confidence >= 0.5:
            return IdentityThreatEvent(
                event_id=f"diamond_{secrets.token_hex(8)}",
                timestamp=datetime.now(timezone.utc),
                category=AttackCategory.KERBEROS,
                attack_type="diamond_ticket",
                severity=ThreatSeverity.CRITICAL,
                source_ip=event.get("source_ip", "unknown"),
                target_principal=event.get("client_principal", "unknown"),
                description=f"Diamond Ticket attack detected: {'; '.join(indicators)}",
                evidence=evidence,
                mitre_techniques=["T1558.001"],  # Golden Ticket variant
                recommendations=[
                    "Reset KRBTGT password twice (24+ hours apart)",
                    "Invalidate all Kerberos tickets domain-wide",
                    "Review PAC validation settings on domain controllers",
                    "Enable PAC validation for all services",
                    "Investigate source of KRBTGT key compromise",
                    "Audit all privileged group memberships"
                ],
                confidence=min(1.0, confidence)
            )
        
        return None
    
    def detect_sapphire_ticket(self, event: Dict[str, Any]) -> Optional[IdentityThreatEvent]:
        """
        Detect Sapphire Ticket attacks.
        
        Sapphire Ticket:
        1. Requests a TGT for a target user using S4U2Self
        2. Uses the PAC from that ticket to forge new tickets
        3. Bypasses PAC validation by using legitimately issued PAC
        
        Detection based on:
        - S4U2Self requests from non-service accounts
        - S4U2Self for privileged accounts
        - Ticket usage pattern anomalies
        """
        s4u_data = event.get("s4u_data", {})
        
        indicators = []
        confidence = 0.0
        evidence = {
            "requesting_principal": event.get("requesting_principal", "unknown"),
            "target_principal": event.get("target_principal", "unknown"),
            "source_ip": event.get("source_ip", "unknown")
        }
        
        # Indicator 1: S4U2Self from non-trusted-for-delegation account
        if s4u_data.get("s4u2self") and not s4u_data.get("trusted_for_delegation"):
            indicators.append("S4U2Self from account not trusted for delegation")
            confidence += 0.4
            evidence["unauthorized_s4u2self"] = True
        
        # Indicator 2: S4U2Self targeting privileged account
        target = event.get("target_principal", "").lower()
        privileged_patterns = ["admin", "domain admins", "enterprise admins", "krbtgt"]
        if any(p in target for p in privileged_patterns):
            indicators.append(f"S4U2Self targeting privileged account: {target}")
            confidence += 0.35
            evidence["privileged_target"] = True
        
        # Indicator 3: Unusual S4U chain (S4U2Self -> S4U2Proxy sequence)
        if s4u_data.get("s4u_chain_length", 0) > 2:
            indicators.append(f"Unusual S4U chain length: {s4u_data.get('s4u_chain_length')}")
            confidence += 0.25
            evidence["unusual_s4u_chain"] = True
        
        # Indicator 4: S4U without corresponding application request
        if s4u_data.get("s4u2self") and not s4u_data.get("subsequent_ap_req"):
            indicators.append("S4U2Self without subsequent application authentication")
            confidence += 0.2
            evidence["orphan_s4u"] = True
        
        if confidence >= 0.5:
            return IdentityThreatEvent(
                event_id=f"sapphire_{secrets.token_hex(8)}",
                timestamp=datetime.now(timezone.utc),
                category=AttackCategory.DELEGATION_ABUSE,
                attack_type="sapphire_ticket",
                severity=ThreatSeverity.CRITICAL,
                source_ip=event.get("source_ip", "unknown"),
                target_principal=event.get("target_principal", "unknown"),
                description=f"Sapphire Ticket attack detected: {'; '.join(indicators)}",
                evidence=evidence,
                mitre_techniques=["T1558.001", "T1550.003"],
                recommendations=[
                    "Review constrained delegation configurations",
                    "Audit accounts trusted for delegation",
                    "Enable Protected Users for privileged accounts",
                    "Implement resource-based constrained delegation",
                    "Reset password for compromised service account",
                    "Monitor for S4U2Self activity"
                ],
                confidence=min(1.0, confidence)
            )
        
        return None
    
    def detect_overpass_the_hash(self, event: Dict[str, Any]) -> Optional[IdentityThreatEvent]:
        """
        Detect Overpass-the-Hash (Pass-the-Key) attacks.
        
        Overpass-the-Hash uses NTLM hash to request Kerberos tickets,
        combining PtH with Kerberos authentication.
        
        Detection based on:
        - AS-REQ from unusual source
        - RC4 encryption requested when AES available
        - Missing expected pre-authentication data
        - Timing correlation with NTLM events
        """
        as_req_data = event.get("as_req_data", {})
        
        indicators = []
        confidence = 0.0
        evidence = {
            "client_principal": event.get("client_principal", "unknown"),
            "source_ip": event.get("source_ip", "unknown"),
            "source_workstation": event.get("source_workstation", "unknown")
        }
        
        # Indicator 1: RC4 encryption requested when AES is account's default
        requested_etypes = as_req_data.get("requested_etypes", [])
        account_etypes = as_req_data.get("account_supported_etypes", [])
        
        if EncryptionType.RC4_HMAC.value in requested_etypes:
            if EncryptionType.AES256_CTS_HMAC_SHA1.value in account_etypes:
                indicators.append("RC4 requested when AES available (Overpass-the-Hash signature)")
                confidence += 0.4
                evidence["etype_downgrade"] = True
        
        # Indicator 2: AS-REQ from IP not associated with user
        user_known_ips = as_req_data.get("user_known_ips", set())
        source_ip = event.get("source_ip", "")
        if user_known_ips and source_ip not in user_known_ips:
            indicators.append(f"AS-REQ from unusual IP: {source_ip}")
            confidence += 0.3
            evidence["unusual_source_ip"] = source_ip
            evidence["known_ips"] = list(user_known_ips)[:5]
        
        # Indicator 3: Certificate-less authentication for smart-card user
        if as_req_data.get("user_requires_smartcard") and not as_req_data.get("certificate_used"):
            indicators.append("Password authentication for smart card required user")
            confidence += 0.35
            evidence["smartcard_bypass"] = True
        
        # Indicator 4: Pre-auth using RC4 timestamp encryption
        preauth_etype = as_req_data.get("preauth_etype")
        if preauth_etype == EncryptionType.RC4_HMAC.value:
            indicators.append("Pre-authentication using RC4 (NTLM hash used)")
            confidence += 0.25
            evidence["rc4_preauth"] = True
        
        # Indicator 5: Rapid progression from NTLM to Kerberos
        if as_req_data.get("ntlm_event_correlation"):
            indicators.append("AS-REQ correlated with recent NTLM authentication attempt")
            confidence += 0.2
            evidence["ntlm_kerberos_correlation"] = True
        
        if confidence >= 0.5:
            return IdentityThreatEvent(
                event_id=f"opth_{secrets.token_hex(8)}",
                timestamp=datetime.now(timezone.utc),
                category=AttackCategory.CREDENTIAL_THEFT,
                attack_type="overpass_the_hash",
                severity=ThreatSeverity.HIGH,
                source_ip=event.get("source_ip", "unknown"),
                target_principal=event.get("client_principal", "unknown"),
                description=f"Overpass-the-Hash attack detected: {'; '.join(indicators)}",
                evidence=evidence,
                mitre_techniques=["T1550.002"],
                recommendations=[
                    "Reset password for affected account immediately",
                    "Investigate source system for credential theft tools",
                    "Enable Credential Guard on source system",
                    "Enforce AES-only Kerberos encryption",
                    "Add account to Protected Users group",
                    "Review NTLM usage and restrict where possible"
                ],
                confidence=min(1.0, confidence)
            )
        
        return None
    
    def detect_delegation_abuse(self, event: Dict[str, Any]) -> Optional[IdentityThreatEvent]:
        """
        Detect Kerberos delegation abuse attacks.
        
        Covers:
        - Unconstrained Delegation abuse
        - Constrained Delegation abuse
        - Resource-Based Constrained Delegation (RBCD) abuse
        - Protocol Transition abuse
        
        Detection based on:
        - TGT forwarding to non-DC services
        - S4U2Proxy to sensitive services
        - RBCD configuration changes
        - Protocol transition anomalies
        """
        delegation_data = event.get("delegation_data", {})
        
        indicators = []
        confidence = 0.0
        attack_subtype = "delegation_abuse"
        evidence = {
            "delegating_principal": event.get("delegating_principal", "unknown"),
            "target_service": event.get("target_service", "unknown"),
            "source_ip": event.get("source_ip", "unknown")
        }
        
        # Check 1: Unconstrained delegation TGT capture
        if delegation_data.get("delegation_type") == "unconstrained":
            if delegation_data.get("tgt_received"):
                indicators.append("TGT received by unconstrained delegation service")
                confidence += 0.3
                attack_subtype = "unconstrained_delegation_abuse"
                
                # High value target TGT
                forwarded_user = delegation_data.get("forwarded_user", "")
                if any(priv in forwarded_user.lower() for priv in ["admin", "service", "sql"]):
                    indicators.append(f"Privileged TGT captured: {forwarded_user}")
                    confidence += 0.3
                    evidence["privileged_tgt_captured"] = forwarded_user
        
        # Check 2: Constrained delegation to sensitive service
        if delegation_data.get("delegation_type") == "constrained":
            target_spn = delegation_data.get("target_spn", "")
            sensitive_spns = ["ldap/", "cifs/", "http/", "host/", "krbtgt/"]
            
            for spn in sensitive_spns:
                if target_spn.lower().startswith(spn):
                    indicators.append(f"Constrained delegation to sensitive SPN: {target_spn}")
                    confidence += 0.25
                    attack_subtype = "constrained_delegation_abuse"
                    evidence["sensitive_target_spn"] = target_spn
        
        # Check 3: RBCD modification
        if delegation_data.get("rbcd_modified"):
            indicators.append("Resource-based constrained delegation modified")
            confidence += 0.4
            attack_subtype = "rbcd_abuse"
            evidence["rbcd_modified"] = True
            
            # Computer account added to RBCD
            if delegation_data.get("computer_account_added"):
                indicators.append("Computer account added to RBCD (potential machine account attack)")
                confidence += 0.3
                evidence["computer_account_rbcd"] = delegation_data.get("added_account")
        
        # Check 4: Protocol transition without expected client cert
        if delegation_data.get("protocol_transition"):
            if not delegation_data.get("client_certificate_present"):
                indicators.append("Protocol transition used without client certificate")
                confidence += 0.2
                evidence["protocol_transition_no_cert"] = True
        
        # Check 5: S4U2Proxy without prior S4U2Self (indicates ticket injection)
        if delegation_data.get("s4u2proxy") and not delegation_data.get("prior_s4u2self"):
            indicators.append("S4U2Proxy without prior S4U2Self (possible ticket injection)")
            confidence += 0.3
            evidence["s4u_anomaly"] = True
        
        if confidence >= 0.4:
            return IdentityThreatEvent(
                event_id=f"delegation_{secrets.token_hex(8)}",
                timestamp=datetime.now(timezone.utc),
                category=AttackCategory.DELEGATION_ABUSE,
                attack_type=attack_subtype,
                severity=ThreatSeverity.HIGH if confidence >= 0.6 else ThreatSeverity.MEDIUM,
                source_ip=event.get("source_ip", "unknown"),
                target_principal=event.get("target_service", "unknown"),
                description=f"Delegation abuse detected: {'; '.join(indicators)}",
                evidence=evidence,
                mitre_techniques=["T1558", "T1550.003"],
                recommendations=[
                    "Review and minimize delegation configurations",
                    "Use constrained delegation with protocol transition disabled where possible",
                    "Monitor msDS-AllowedToActOnBehalfOfOtherIdentity changes",
                    "Enable Protected Users for sensitive accounts",
                    "Consider eliminating unconstrained delegation",
                    "Audit all delegation-enabled service accounts"
                ],
                confidence=min(1.0, confidence)
            )
        
        return None
    
    def detect_cross_realm_abuse(self, event: Dict[str, Any]) -> Optional[IdentityThreatEvent]:
        """
        Detect cross-realm/inter-forest trust abuse attacks.
        
        Detection based on:
        - SID history injection across trusts
        - Inter-realm TGT manipulation
        - Trust ticket forging
        - Selective authentication bypass
        """
        trust_data = event.get("trust_data", {})
        
        indicators = []
        confidence = 0.0
        evidence = {
            "source_realm": event.get("source_realm", "unknown"),
            "target_realm": event.get("target_realm", "unknown"),
            "source_ip": event.get("source_ip", "unknown")
        }
        
        # Indicator 1: SID filtering bypass
        extra_sids = trust_data.get("extra_sids_in_referral", [])
        if extra_sids:
            # Enterprise Admins SID from trusting domain
            for sid in extra_sids:
                if re.match(r"S-1-5-21-\d+-\d+-\d+-519", sid):
                    indicators.append(f"Enterprise Admins SID in cross-realm referral: {sid}")
                    confidence += 0.5
                    evidence["enterprise_admin_sid_injection"] = sid
        
        # Indicator 2: Trust ticket with unexpected encryption type
        trust_etype = trust_data.get("trust_ticket_etype")
        if trust_etype == EncryptionType.RC4_HMAC.value:
            indicators.append("Cross-realm TGT using RC4 (trust key extraction indicator)")
            confidence += 0.3
            evidence["weak_trust_encryption"] = True
        
        # Indicator 3: Inter-realm TGT with anomalous lifetime
        referral_lifetime = trust_data.get("referral_ticket_lifetime_hours", 0)
        if referral_lifetime > 10:
            indicators.append(f"Inter-realm referral with extended lifetime: {referral_lifetime}h")
            confidence += 0.25
            evidence["extended_referral_lifetime"] = referral_lifetime
        
        # Indicator 4: Selective authentication bypass
        if trust_data.get("selective_auth_enabled"):
            if not trust_data.get("allowed_to_authenticate"):
                indicators.append("Authentication attempt blocked by selective authentication was bypassed")
                confidence += 0.4
                evidence["selective_auth_bypass"] = True
        
        # Indicator 5: Trust direction abuse (outbound trust used for inbound)
        if trust_data.get("trust_direction") == "outbound":
            if trust_data.get("inbound_auth_attempted"):
                indicators.append("Inbound authentication through outbound-only trust")
                confidence += 0.35
                evidence["trust_direction_abuse"] = True
        
        if confidence >= 0.4:
            return IdentityThreatEvent(
                event_id=f"trust_{secrets.token_hex(8)}",
                timestamp=datetime.now(timezone.utc),
                category=AttackCategory.TRUST_ABUSE,
                attack_type="cross_realm_abuse",
                severity=ThreatSeverity.CRITICAL,
                source_ip=event.get("source_ip", "unknown"),
                target_principal=event.get("target_realm", "unknown"),
                description=f"Cross-realm trust abuse detected: {'; '.join(indicators)}",
                evidence=evidence,
                mitre_techniques=["T1134.005", "T1558.001"],
                recommendations=[
                    "Enable SID filtering on all trusts",
                    "Review trust configurations",
                    "Rotate inter-realm trust keys",
                    "Enable selective authentication",
                    "Monitor cross-realm authentication events",
                    "Consider quarantine-based trust for untrusted forests"
                ],
                confidence=min(1.0, confidence)
            )
        
        return None
    
    def analyze_windows_event(self, event_id: int, event_data: Dict[str, Any]) -> Optional[IdentityThreatEvent]:
        """
        Analyze Windows Security Event Log events for Kerberos attacks.
        
        Supports:
        - Event 4768 (TGT Request)
        - Event 4769 (Service Ticket Request)
        - Event 4771 (Pre-authentication Failed)
        - Event 4770 (TGT Renewed)
        """
        if event_id == WindowsSecurityEventID.KERBEROS_TGT_REQUEST:
            return self._analyze_4768(event_data)
        elif event_id == WindowsSecurityEventID.KERBEROS_SERVICE_TICKET:
            return self._analyze_4769(event_data)
        elif event_id == WindowsSecurityEventID.KERBEROS_PREAUTH_FAILED:
            return self._analyze_4771(event_data)
        elif event_id == WindowsSecurityEventID.KERBEROS_RENEWAL:
            return self._analyze_4770(event_data)
        
        return None
    
    def _analyze_4768(self, event_data: Dict[str, Any]) -> Optional[IdentityThreatEvent]:
        """Analyze Event 4768 - TGT Request"""
        # Convert to internal format and analyze
        converted_event = {
            "client_principal": event_data.get("TargetUserName", ""),
            "realm": event_data.get("TargetDomainName", ""),
            "source_ip": event_data.get("IpAddress", "").strip("::ffff:"),
            "encryption_type": int(event_data.get("TicketEncryptionType", "0x0"), 16),
            "result_code": int(event_data.get("Status", "0x0"), 16),
            "preauth_type": event_data.get("PreAuthType", ""),
            "timestamp": event_data.get("TimeCreated", datetime.now(timezone.utc).isoformat())
        }
        
        # Check for AS-REP Roasting (result code 0 with no pre-auth)
        if converted_event["result_code"] == 0:
            preauth = converted_event.get("preauth_type", "")
            if preauth == "-" or preauth == "0":
                return self.analyze_as_rep({
                    **converted_event,
                    "preauth_required": False,
                    "error_code": 0
                })
        
        # Check for Overpass-the-Hash
        return self.detect_overpass_the_hash({
            **converted_event,
            "as_req_data": {
                "requested_etypes": [converted_event["encryption_type"]],
                "preauth_etype": converted_event["encryption_type"]
            }
        })
    
    def _analyze_4769(self, event_data: Dict[str, Any]) -> Optional[IdentityThreatEvent]:
        """Analyze Event 4769 - Service Ticket Request"""
        converted_event = {
            "client_principal": event_data.get("TargetUserName", ""),
            "server_principal": event_data.get("ServiceName", ""),
            "source_ip": event_data.get("IpAddress", "").strip("::ffff:"),
            "encryption_type": int(event_data.get("TicketEncryptionType", "0x0"), 16),
            "timestamp": event_data.get("TimeCreated", datetime.now(timezone.utc).isoformat())
        }
        
        # Analyze for Kerberoasting
        return self.analyze_tgs_request(converted_event)
    
    def _analyze_4771(self, event_data: Dict[str, Any]) -> Optional[IdentityThreatEvent]:
        """Analyze Event 4771 - Pre-authentication Failed"""
        failure_code = int(event_data.get("FailureCode", "0x0"), 16)
        source_ip = event_data.get("IpAddress", "").strip("::ffff:")
        target_user = event_data.get("TargetUserName", "")
        
        # Track for password spray detection
        self.asrep_history[source_ip].append(datetime.now(timezone.utc))
        
        # Check if failure indicates user enumeration
        if failure_code == KerberosErrorCode.KDC_ERR_C_PRINCIPAL_UNKNOWN:
            return IdentityThreatEvent(
                event_id=f"userenum_{secrets.token_hex(8)}",
                timestamp=datetime.now(timezone.utc),
                category=AttackCategory.RECONNAISSANCE,
                attack_type="user_enumeration",
                severity=ThreatSeverity.MEDIUM,
                source_ip=source_ip,
                target_principal=target_user,
                description=f"User enumeration via Kerberos: {target_user} does not exist",
                evidence={
                    "failure_code": hex(failure_code),
                    "attempted_user": target_user,
                    "source_ip": source_ip
                },
                mitre_techniques=["T1087.002"],
                recommendations=[
                    "Enable account enumeration protection",
                    "Monitor for bulk enumeration attempts",
                    "Consider blocking source IP"
                ],
                confidence=0.7
            )
        
        return None
    
    def _analyze_4770(self, event_data: Dict[str, Any]) -> Optional[IdentityThreatEvent]:
        """Analyze Event 4770 - TGT Renewal"""
        # TGT renewal from unexpected source could indicate ticket theft
        source_ip = event_data.get("IpAddress", "").strip("::ffff:")
        client = event_data.get("TargetUserName", "")
        
        # Would compare against baseline of known user IPs
        # For now, just track
        return None
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get detector statistics"""
        return {
            "tgs_requests_tracked": sum(len(v) for v in self.tgs_request_history.values()),
            "asrep_requests_tracked": sum(len(v) for v in self.asrep_history.values()),
            "tickets_cached": len(self.ticket_cache),
            "unique_users_tracked": len(self.encryption_stats),
            "config": self.config
        }
    
    def clear_state(self):
        """Clear detector state"""
        self.tgs_request_history.clear()
        self.asrep_history.clear()
        self.ticket_cache.clear()
        self.encryption_stats.clear()
        self.spn_access_patterns.clear()
        logger.info("KerberosAttackDetector state cleared")


# =============================================================================
# LDAP ATTACK DETECTOR
# =============================================================================

class LDAPAttackDetector:
    """
    Detects LDAP-based attacks including:
    - LDAP Reconnaissance (T1087)
    - LDAP Injection
    - LDAP Pass-back attacks
    - BloodHound/SharpHound collection
    - Privileged attribute queries
    - Shadow Credentials attack
    - Coerced authentication (PetitPotam-style)
    """
    
    def __init__(self):
        # Configuration
        self.config = {
            # Query thresholds
            "query_rate_threshold": 100,         # Queries per minute
            "unique_objects_threshold": 50,      # Unique objects queried per minute
            "subtree_search_threshold": 10,      # Subtree searches per minute
            
            # Sensitive attribute monitoring
            "sensitive_attribute_alert": True,
            
            # BloodHound detection
            "bloodhound_detection_enabled": True,
            
            # Baseline
            "baseline_window_hours": 24,
        }
        
        # State tracking
        self.query_history: Dict[str, List[LDAPQueryInfo]] = defaultdict(list)  # ip -> queries
        self.attribute_access: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))  # ip -> {attr: count}
        self.object_access: Dict[str, Set[str]] = defaultdict(set)  # ip -> {object_dns}
        
        # Sensitive LDAP attributes (credential-related, privilege-related)
        self.sensitive_attributes = {
            # Credential attributes
            "unicodepwd", "userpassword", "ntpwdhistory", "lmpwdhistory",
            "supplementalcredentials", "serviceprincipalname", "msds-managedpassword",
            "msds-groupmsamembership", "ms-mcs-admpwd", "ms-mcs-admpwdexpirationtime",
            
            # Privilege attributes
            "admincount", "memberof", "primarygroupid", "sidhistory", "objectsid",
            "dscorepropagationdata", "msds-allowedtodelegateto", 
            "msds-allowedtoactonbehalfofotheridentity",
            
            # Group Policy
            "gplink", "gpoptions", "gpcfilesyspath",
            
            # Replication (DCSync)
            "ms-ds-replicationepoch", "repluptodatevector", "replpropertymetadata",
            
            # Trust
            "trustpartner", "trustdirection", "trusttype", "trustattributes",
            "msds-trusteddomainobject",
        }
        
        # BloodHound/SharpHound LDAP filter patterns
        self.bloodhound_patterns = [
            # User enumeration
            r"\(objectClass=user\)",
            r"\(objectCategory=person\)",
            r"\(samAccountType=805306368\)",  # Normal user account
            
            # Computer enumeration
            r"\(objectClass=computer\)",
            r"\(samAccountType=805306369\)",  # Computer account
            
            # Group enumeration
            r"\(objectClass=group\)",
            r"\(groupType:1.2.840.113556.1.4.803:=2147483648\)",  # Security groups
            
            # GPO enumeration
            r"\(objectClass=groupPolicyContainer\)",
            
            # OU enumeration
            r"\(objectClass=organizationalUnit\)",
            
            # Trust enumeration
            r"\(objectClass=trustedDomain\)",
            
            # AdminCount enumeration (privileged accounts)
            r"\(adminCount=1\)",
            
            # Delegation enumeration
            r"\(userAccountControl:1.2.840.113556.1.4.803:=524288\)",  # TRUSTED_FOR_DELEGATION
            r"\(msds-allowedtodelegateto=\*\)",
            
            # SPN enumeration (Kerberoasting prep)
            r"\(servicePrincipalName=\*\)",
            r"\(&\(servicePrincipalName=\*\)\(!\(samAccountType=805306369\)\)\)",
            
            # AS-REP roasting prep
            r"\(userAccountControl:1.2.840.113556.1.4.803:=4194304\)",  # DONT_REQ_PREAUTH
        ]
        
        # LDAP injection patterns
        self.injection_patterns = [
            r"\*\)\(\|",           # Boolean injection
            r"\)\(\|(.*?)=\*\)",   # OR injection
            r"\*\)\(!\(",          # NOT injection
            r"%00",                # Null byte injection
            r"\\00",               # Escaped null
            r"\)\)\(\(",           # Nested filter escape
            r"\*\)\)\(cn=",        # Filter bypass
        ]
        
        logger.info("LDAPAttackDetector initialized")
    
    def analyze_query(self, query: LDAPQueryInfo) -> Optional[IdentityThreatEvent]:
        """
        Analyze an LDAP query for reconnaissance or attack indicators.
        """
        # Track query
        self.query_history[query.source_ip].append(query)
        self.object_access[query.source_ip].add(query.base_dn)
        for attr in query.attributes:
            self.attribute_access[query.source_ip][attr.lower()] += 1
        
        # Clean old entries (sliding window)
        cutoff = query.timestamp - timedelta(minutes=1)
        self.query_history[query.source_ip] = [
            q for q in self.query_history[query.source_ip] if q.timestamp > cutoff
        ]
        
        threats = []
        confidence = 0.0
        evidence = {
            "source_ip": query.source_ip,
            "bind_dn": query.bind_dn,
            "base_dn": query.base_dn,
            "filter": query.filter_str,
            "attributes": query.attributes,
            "timestamp": query.timestamp.isoformat()
        }
        
        # Check 1: Query rate
        query_count = len(self.query_history[query.source_ip])
        if query_count >= self.config["query_rate_threshold"]:
            threats.append(f"High LDAP query rate: {query_count}/min")
            confidence += 0.25
            evidence["query_rate"] = query_count
        
        # Check 2: Sensitive attribute access
        accessed_sensitive = [
            attr for attr in query.attributes 
            if attr.lower() in self.sensitive_attributes
        ]
        if accessed_sensitive:
            threats.append(f"Sensitive attributes queried: {', '.join(accessed_sensitive)}")
            confidence += 0.3
            evidence["sensitive_attributes"] = accessed_sensitive
        
        # Check 3: BloodHound patterns
        matched_bloodhound = []
        for pattern in self.bloodhound_patterns:
            if re.search(pattern, query.filter_str, re.IGNORECASE):
                matched_bloodhound.append(pattern)
        
        if len(matched_bloodhound) >= 2:  # Multiple BloodHound-like patterns
            threats.append(f"BloodHound/SharpHound enumeration patterns detected")
            confidence += 0.35
            evidence["bloodhound_patterns"] = matched_bloodhound
        
        # Check 4: LDAP injection
        for pattern in self.injection_patterns:
            if re.search(pattern, query.filter_str):
                threats.append(f"Potential LDAP injection: pattern '{pattern}'")
                confidence += 0.4
                evidence["injection_pattern"] = pattern
                break
        
        # Check 5: Subtree searches (scope=2) on sensitive containers
        sensitive_containers = ["cn=users", "cn=computers", "ou=domain controllers", "cn=admins"]
        if query.scope == 2:  # Subtree
            if any(sc in query.base_dn.lower() for sc in sensitive_containers):
                threats.append(f"Subtree search on sensitive container: {query.base_dn}")
                confidence += 0.2
                evidence["subtree_sensitive"] = True
        
        # Check 6: Schema/configuration enumeration
        if any(x in query.base_dn.lower() for x in ["cn=schema", "cn=configuration"]):
            threats.append("Schema/Configuration partition enumeration")
            confidence += 0.15
            evidence["config_enumeration"] = True
        
        # Determine attack type
        attack_type = "ldap_reconnaissance"
        if matched_bloodhound:
            attack_type = "bloodhound_collection"
        elif any("injection" in t for t in threats):
            attack_type = "ldap_injection"
        
        if confidence >= 0.4:
            return IdentityThreatEvent(
                event_id=f"ldap_{secrets.token_hex(8)}",
                timestamp=query.timestamp,
                category=AttackCategory.RECONNAISSANCE if "reconnaissance" in attack_type else AttackCategory.LDAP,
                attack_type=attack_type,
                severity=ThreatSeverity.HIGH if confidence >= 0.6 else ThreatSeverity.MEDIUM,
                source_ip=query.source_ip,
                target_principal=query.bind_dn,
                description=f"LDAP attack detected: {'; '.join(threats)}",
                evidence=evidence,
                mitre_techniques=["T1087.002", "T1069.002"],  # Account/Group Discovery
                recommendations=[
                    "Review LDAP query permissions for source account",
                    "Enable LDAP signing and channel binding",
                    "Implement LDAP query logging",
                    "Block excessive LDAP queries from source IP",
                    "Review AD permissions for sensitive attributes"
                ],
                confidence=min(1.0, confidence)
            )
        
        return None
    
    def detect_ldap_relay(self, event: Dict[str, Any]) -> Optional[IdentityThreatEvent]:
        """
        Detect LDAP relay attacks.
        
        LDAP relay involves capturing NTLM authentication and
        relaying it to LDAP for privilege escalation.
        """
        source_ip = event.get("source_ip", "")
        target_dn = event.get("target_dn", "")
        operation = event.get("operation", "")
        bind_type = event.get("bind_type", "simple")
        
        indicators = []
        confidence = 0.0
        
        # Indicator 1: NTLM bind followed by sensitive modification
        if bind_type == "ntlm" and operation in ["modify", "add"]:
            indicators.append("NTLM bind followed by modification")
            confidence += 0.3
        
        # Indicator 2: Modification of msDS-AllowedToActOnBehalfOfOtherIdentity
        if "msds-allowedtoactonbehalfofotheridentity" in event.get("modified_attrs", []):
            indicators.append("Resource-based constrained delegation modification")
            confidence += 0.4
        
        # Indicator 3: ACL modification on sensitive object
        if event.get("acl_modified") and event.get("target_sensitive"):
            indicators.append("ACL modification on sensitive object")
            confidence += 0.35
        
        # Indicator 4: Computer account creation
        if operation == "add" and "computer" in target_dn.lower():
            indicators.append("Computer account creation via LDAP")
            confidence += 0.2
        
        if confidence >= 0.5:
            return IdentityThreatEvent(
                event_id=f"ldap_relay_{secrets.token_hex(8)}",
                timestamp=datetime.now(timezone.utc),
                category=AttackCategory.LATERAL_MOVEMENT,
                attack_type="ldap_relay",
                severity=ThreatSeverity.CRITICAL,
                source_ip=source_ip,
                target_principal=target_dn,
                description=f"Potential LDAP relay attack: {'; '.join(indicators)}",
                evidence={
                    "indicators": indicators,
                    "target_dn": target_dn,
                    "operation": operation,
                    "bind_type": bind_type,
                    "raw_event": event
                },
                mitre_techniques=["T1557.001"],  # LLMNR/NBT-NS Poisoning
                recommendations=[
                    "Enable LDAP signing requirement",
                    "Enable LDAP channel binding",
                    "Disable NTLM where possible",
                    "Investigate source IP for relay tools",
                    "Review modified objects for malicious changes"
                ],
                confidence=min(1.0, confidence)
            )
        
        return None
    
    def detect_shadow_credentials(self, event: Dict[str, Any]) -> Optional[IdentityThreatEvent]:
        """
        Detect Shadow Credentials attack.
        
        Shadow Credentials abuse msDS-KeyCredentialLink to add attacker-controlled
        certificates for Kerberos PKINIT authentication.
        
        Detection based on:
        - Unauthorized msDS-KeyCredentialLink modifications
        - KeyCredential additions by non-privileged accounts
        - Subsequent PKINIT authentication using new credentials
        """
        modification_data = event.get("modification_data", {})
        
        indicators = []
        confidence = 0.0
        evidence = {
            "source_ip": event.get("source_ip", "unknown"),
            "modifying_principal": event.get("modifying_principal", "unknown"),
            "target_object": event.get("target_object", "unknown"),
            "timestamp": event.get("timestamp", datetime.now(timezone.utc).isoformat())
        }
        
        # Check 1: msDS-KeyCredentialLink modification
        modified_attrs = modification_data.get("modified_attributes", [])
        if "msds-keycredentiallink" in [a.lower() for a in modified_attrs]:
            indicators.append("msDS-KeyCredentialLink attribute modified")
            confidence += 0.4
            evidence["key_credential_modified"] = True
            
            # Check modifier permissions
            if not modification_data.get("modifier_has_permission"):
                indicators.append("Modifier lacks explicit permission for Key Credential modification")
                confidence += 0.3
                evidence["unauthorized_modifier"] = True
            
            # Check for DeviceID change (shadow credentials signature)
            if modification_data.get("device_id_changed"):
                indicators.append("New DeviceID added to KeyCredentialLink")
                confidence += 0.2
                evidence["new_device_id"] = modification_data.get("device_id")
        
        # Check 2: Self-modification of KeyCredentialLink
        modifying_principal = event.get("modifying_principal", "")
        target_object = event.get("target_object", "")
        if modifying_principal and target_object:
            if modifying_principal.lower() != target_object.lower():
                if "cn=computers" not in target_object.lower():  # Expect computer to modify own
                    indicators.append(f"User modifying another account's KeyCredentialLink")
                    confidence += 0.25
        
        # Check 3: Modification followed by PKINIT
        if event.get("subsequent_pkinit"):
            indicators.append("PKINIT authentication shortly after KeyCredentialLink change")
            confidence += 0.3
            evidence["pkinit_correlation"] = True
        
        # Check 4: Certificate with unusual issuer
        cert_data = event.get("certificate_data", {})
        if cert_data.get("issuer") == cert_data.get("subject"):
            if "self-signed" not in str(cert_data.get("issuer", "")).lower():
                indicators.append("Self-signed certificate added to KeyCredentialLink")
                confidence += 0.2
                evidence["self_signed_cert"] = True
        
        if confidence >= 0.5:
            return IdentityThreatEvent(
                event_id=f"shadow_cred_{secrets.token_hex(8)}",
                timestamp=datetime.now(timezone.utc),
                category=AttackCategory.CREDENTIAL_THEFT,
                attack_type="shadow_credentials",
                severity=ThreatSeverity.CRITICAL,
                source_ip=event.get("source_ip", "unknown"),
                target_principal=target_object,
                description=f"Shadow Credentials attack detected: {'; '.join(indicators)}",
                evidence=evidence,
                mitre_techniques=["T1556.001", "T1556.006"],  # Credential modification
                recommendations=[
                    "Remove unauthorized KeyCredentialLink entries",
                    "Restrict write access to msDS-KeyCredentialLink",
                    "Monitor Active Directory Certificate Services",
                    "Enable Protected Users for sensitive accounts",
                    "Audit KeyCredentialLink changes in AD",
                    "Review ADCS certificate issuance logs"
                ],
                confidence=min(1.0, confidence)
            )
        
        return None
    
    def detect_coerced_authentication(self, event: Dict[str, Any]) -> Optional[IdentityThreatEvent]:
        """
        Detect coerced authentication attacks.
        
        Covers:
        - PetitPotam (EFS coercion)
        - PrinterBug/SpoolSample
        - DFSCoerce
        - ShadowCoerce
        - RemotePotato
        
        Detection based on:
        - RPC calls to coercible interfaces
        - Outbound NTLM authentication from protected systems
        - Authentication to non-standard targets
        """
        rpc_data = event.get("rpc_data", {})
        auth_data = event.get("auth_data", {})
        
        indicators = []
        confidence = 0.0
        coercion_type = "unknown"
        evidence = {
            "source_ip": event.get("source_ip", "unknown"),
            "target_ip": event.get("target_ip", "unknown"),
            "protocol": event.get("protocol", "unknown")
        }
        
        # PetitPotam detection - EFS RPC calls
        if rpc_data.get("interface") in ["c681d488-d850-11d0-8c52-00c04fd90f7e",  # EFS
                                          "df1941c5-fe89-4e79-bf10-463657acf44d"]: # EFSRPC
            if rpc_data.get("method") in ["EfsRpcOpenFileRaw", "EfsRpcEncryptFileSrv"]:
                indicators.append(f"PetitPotam EFS coercion: {rpc_data.get('method')}")
                confidence += 0.5
                coercion_type = "petitpotam"
                evidence["efs_method"] = rpc_data.get("method")
        
        # PrinterBug/SpoolSample detection
        if rpc_data.get("interface") == "12345678-1234-abcd-ef00-0123456789ab":  # Spooler
            if rpc_data.get("method") in ["RpcRemoteFindFirstPrinterChangeNotificationEx",
                                          "RpcRemoteFindFirstPrinterChangeNotification"]:
                indicators.append(f"PrinterBug/SpoolSample coercion: {rpc_data.get('method')}")
                confidence += 0.45
                coercion_type = "printerbug"
                evidence["spooler_method"] = rpc_data.get("method")
        
        # DFSCoerce detection
        if rpc_data.get("interface") == "4fc742e0-4a10-11cf-8273-00aa004ae673":  # DFS
            if rpc_data.get("method") in ["NetrDfsAddStdRoot", "NetrDfsRemoveStdRoot"]:
                indicators.append(f"DFSCoerce coercion: {rpc_data.get('method')}")
                confidence += 0.45
                coercion_type = "dfscoerce"
                evidence["dfs_method"] = rpc_data.get("method")
        
        # ShadowCoerce detection - File Server VSS Agent
        if rpc_data.get("interface") == "a8e0653c-2744-4389-a61d-7373df8b2292":
            indicators.append("ShadowCoerce: VSS Agent RPC invoked")
            confidence += 0.4
            coercion_type = "shadowcoerce"
        
        # Check for outbound machine account authentication to non-DC
        if auth_data.get("auth_type") == "machine":
            target = event.get("target_ip", "")
            source = event.get("source_ip", "")
            
            # Machine authenticating outbound to non-DC = suspicious
            if not auth_data.get("target_is_dc"):
                if auth_data.get("source_is_dc"):
                    indicators.append("DC machine account authenticating to non-DC target")
                    confidence += 0.35
                    evidence["dc_outbound_auth"] = True
                elif auth_data.get("is_high_value"):
                    indicators.append("High-value server authenticating outbound")
                    confidence += 0.3
                    evidence["high_value_coercion"] = True
        
        # Check for NTLM authentication following RPC coercion trigger
        if rpc_data.get("triggering_ip") and auth_data.get("ntlm_auth_target"):
            if rpc_data.get("triggering_ip") == auth_data.get("ntlm_auth_target"):
                indicators.append("NTLM authentication to coercion trigger source")
                confidence += 0.3
                evidence["coercion_correlation"] = True
        
        if confidence >= 0.4:
            return IdentityThreatEvent(
                event_id=f"coerce_{secrets.token_hex(8)}",
                timestamp=datetime.now(timezone.utc),
                category=AttackCategory.LATERAL_MOVEMENT,
                attack_type=f"coerced_auth_{coercion_type}",
                severity=ThreatSeverity.CRITICAL if auth_data.get("source_is_dc") else ThreatSeverity.HIGH,
                source_ip=event.get("source_ip", "unknown"),
                target_principal=event.get("target_ip", "unknown"),
                description=f"Coerced authentication detected ({coercion_type}): {'; '.join(indicators)}",
                evidence=evidence,
                mitre_techniques=["T1557.001", "T1187"],
                recommendations=[
                    f"Disable {coercion_type} attack vector if possible",
                    "Enable Extended Protection for Authentication",
                    "Disable NTLM where feasible",
                    "Apply relevant security patches",
                    "Configure Windows Firewall to block outbound NTLM" if auth_data.get("source_is_dc") else "",
                    "Monitor for relay attacks to LDAP/SMB",
                    "Enable LDAP signing and channel binding"
                ],
                confidence=min(1.0, confidence)
            )
        
        return None
    
    def detect_password_spray_ldap(self, event: Dict[str, Any]) -> Optional[IdentityThreatEvent]:
        """
        Detect password spraying via LDAP bind failures.
        
        Detection based on:
        - Many failed binds to different users from same source
        - Slow spray (1-2 attempts per account per timeframe)
        - User enumeration via bind response timing
        """
        source_ip = event.get("source_ip", "")
        target_user = event.get("target_user", "")
        result = event.get("result", "")
        
        # Track failed bind
        if result in ["invalid_credentials", "49"]:  # LDAP error code 49
            if source_ip not in self.query_history:
                self.query_history[source_ip] = []
            
            self.query_history[source_ip].append(LDAPQueryInfo(
                timestamp=datetime.now(timezone.utc),
                source_ip=source_ip,
                bind_dn=target_user,
                base_dn="",
                scope=0,
                filter_str="(bind_failed)",
                attributes=[]
            ))
        
        # Analyze for spray pattern
        recent_failures = [
            q for q in self.query_history.get(source_ip, [])
            if (datetime.now(timezone.utc) - q.timestamp).total_seconds() < 600  # 10 min window
            and q.filter_str == "(bind_failed)"
        ]
        
        unique_users = set(q.bind_dn for q in recent_failures)
        
        indicators = []
        confidence = 0.0
        evidence = {
            "source_ip": source_ip,
            "failed_attempts": len(recent_failures),
            "unique_users": len(unique_users),
            "users_attempted": list(unique_users)[:10]  # Limit for evidence
        }
        
        # Low and slow spray detection
        if len(unique_users) >= 5:
            avg_attempts_per_user = len(recent_failures) / len(unique_users)
            
            if avg_attempts_per_user <= 2:  # Spray pattern: 1-2 attempt per user
                indicators.append(f"Password spray pattern: {len(unique_users)} users, {avg_attempts_per_user:.1f} attempts each")
                confidence += 0.5
                evidence["spray_pattern"] = True
            elif len(unique_users) >= 20:
                indicators.append(f"Bulk authentication failures: {len(unique_users)} unique users")
                confidence += 0.4
        
        # Check for privileged account targeting
        privileged_patterns = ["admin", "service", "sql", "backup", "svc"]
        privileged_targeted = [u for u in unique_users if any(p in u.lower() for p in privileged_patterns)]
        if len(privileged_targeted) >= 3:
            indicators.append(f"Privileged accounts targeted: {', '.join(privileged_targeted[:3])}")
            confidence += 0.2
            evidence["privileged_targets"] = privileged_targeted[:5]
        
        # Timing analysis (if available)
        if len(recent_failures) >= 10:
            timestamps = sorted([q.timestamp for q in recent_failures])
            intervals = [(timestamps[i+1] - timestamps[i]).total_seconds() for i in range(len(timestamps)-1)]
            avg_interval = sum(intervals) / len(intervals) if intervals else 0
            
            # Very consistent timing = automated spray
            if intervals:
                variance = sum((i - avg_interval)**2 for i in intervals) / len(intervals)
                if variance < 1.0:  # Less than 1 second variance
                    indicators.append(f"Automated spray detected: consistent {avg_interval:.1f}s intervals")
                    confidence += 0.2
                    evidence["automated"] = True
        
        if confidence >= 0.5:
            return IdentityThreatEvent(
                event_id=f"spray_{secrets.token_hex(8)}",
                timestamp=datetime.now(timezone.utc),
                category=AttackCategory.CREDENTIAL_THEFT,
                attack_type="password_spray_ldap",
                severity=ThreatSeverity.HIGH,
                source_ip=source_ip,
                target_principal=f"{len(unique_users)} accounts",
                description=f"Password spray attack via LDAP: {'; '.join(indicators)}",
                evidence=evidence,
                mitre_techniques=["T1110.003"],  # Password Spraying
                recommendations=[
                    "Block source IP temporarily",
                    "Enable smart lockout for affected accounts",
                    "Implement LDAP rate limiting",
                    "Review targeted accounts for compromise",
                    "Enforce MFA for all affected accounts",
                    "Consider blocking LDAP simple binds"
                ],
                confidence=min(1.0, confidence)
            )
        
        return None
    
    def track_windows_event(self, event_id: int, event_data: Dict[str, Any]) -> Optional[IdentityThreatEvent]:
        """
        Track LDAP-related Windows Security events.
        
        Supports:
        - Event 2889 (Unsigned LDAP bind)
        - Event 3039 (LDAP bind rejected)
        """
        if event_id == WindowsSecurityEventID.LDAP_UNSIGNED_BIND:
            # Track unsigned binds - potential relay vulnerability
            source_ip = event_data.get("ClientIPAddress", "")
            bind_dn = event_data.get("BindingDN", "")
            
            # Log for pattern analysis but don't alert on single event
            self.query_history[source_ip].append(LDAPQueryInfo(
                timestamp=datetime.now(timezone.utc),
                source_ip=source_ip,
                bind_dn=bind_dn,
                base_dn="",
                scope=0,
                filter_str="(unsigned_bind)",
                attributes=[]
            ))
            
            # Alert if many unsigned binds from same source
            unsigned_count = sum(
                1 for q in self.query_history.get(source_ip, [])
                if q.filter_str == "(unsigned_bind)" 
                and (datetime.now(timezone.utc) - q.timestamp).total_seconds() < 300
            )
            
            if unsigned_count >= 10:
                return IdentityThreatEvent(
                    event_id=f"unsigned_ldap_{secrets.token_hex(8)}",
                    timestamp=datetime.now(timezone.utc),
                    category=AttackCategory.LDAP,
                    attack_type="unsigned_ldap_binds",
                    severity=ThreatSeverity.MEDIUM,
                    source_ip=source_ip,
                    target_principal=bind_dn,
                    description=f"Multiple unsigned LDAP binds from {source_ip} ({unsigned_count} in 5 minutes)",
                    evidence={
                        "source_ip": source_ip,
                        "unsigned_bind_count": unsigned_count,
                        "sample_bind_dn": bind_dn
                    },
                    mitre_techniques=["T1040"],
                    recommendations=[
                        "Enable LDAP signing requirement",
                        "Investigate source for LDAP relay tools",
                        "Update clients to use signed LDAP binds"
                    ],
                    confidence=0.6
                )
        
        return None
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get detector statistics"""
        return {
            "queries_tracked": sum(len(v) for v in self.query_history.values()),
            "unique_sources": len(self.query_history),
            "objects_accessed": sum(len(v) for v in self.object_access.values()),
            "attribute_accesses": sum(
                sum(v.values()) for v in self.attribute_access.values()
            ),
            "config": self.config
        }
    
    def clear_state(self):
        """Clear detector state"""
        self.query_history.clear()
        self.attribute_access.clear()
        self.object_access.clear()
        logger.info("LDAPAttackDetector state cleared")


# =============================================================================
# AD REPLICATION MONITOR (DCSYNC DETECTION)
# =============================================================================

class ADReplicationMonitor:
    """
    Monitors Active Directory replication for malicious activity.
    
    Detects:
    - DCSync attacks (T1003.006)
    - DCShadow attacks (T1207)
    - Rogue Domain Controller registration
    - Unauthorized replication requests
    """
    
    def __init__(self):
        # Configuration
        self.config = {
            "known_domain_controllers": set(),   # Legitimate DC hostnames/IPs
            "replication_threshold": 5,          # Replication requests per minute from non-DC
            "sensitive_attributes_threshold": 3, # Sensitive attrs in single replication
        }
        
        # State tracking
        self.replication_history: Dict[str, List[ADReplicationEvent]] = defaultdict(list)
        self.dc_registration_events: List[Dict[str, Any]] = []
        
        # Sensitive attributes that shouldn't be replicated to non-DCs
        self.sensitive_replication_attrs = {
            "unicodepwd", "ntpwdhistory", "lmpwdhistory", "supplementalcredentials",
            "currentvalue", "priorvalue", "dbbsecret", "trust*", 
            "initialauthincoming", "initialautoutgoing"
        }
        
        # DRSUAPI operations
        self.dcsync_operations = {
            "DsGetNCChanges",
            "DsReplicaSync", 
            "DsReplicaGetInfo",
            "DsGetDomainControllerInfo"
        }
        
        logger.info("ADReplicationMonitor initialized")
    
    def add_known_dc(self, dc_hostname: str, dc_ip: str):
        """Register a legitimate Domain Controller"""
        self.config["known_domain_controllers"].add(dc_hostname.lower())
        self.config["known_domain_controllers"].add(dc_ip)
    
    def analyze_replication_event(self, event: ADReplicationEvent) -> Optional[IdentityThreatEvent]:
        """
        Analyze an AD replication event for DCSync indicators.
        """
        # Track event
        self.replication_history[event.source_ip].append(event)
        
        # Clean old entries
        cutoff = event.timestamp - timedelta(minutes=1)
        self.replication_history[event.source_ip] = [
            e for e in self.replication_history[event.source_ip] if e.timestamp > cutoff
        ]
        
        threats = []
        confidence = 0.0
        evidence = {
            "source_dc": event.source_dc,
            "destination_dc": event.destination_dc,
            "source_ip": event.source_ip,
            "naming_context": event.naming_context,
            "replicated_attrs": event.attributes_replicated,
            "timestamp": event.timestamp.isoformat()
        }
        
        # Check 1: Non-DC requesting replication
        if not event.is_legitimate_dc:
            threats.append(f"Replication request from non-DC: {event.source_ip}")
            confidence += 0.5
            evidence["non_dc_replication"] = True
        
        # Check 2: Unknown source
        if event.source_ip not in self.config["known_domain_controllers"]:
            if event.source_dc.lower() not in self.config["known_domain_controllers"]:
                threats.append(f"Replication from unknown source: {event.source_dc}")
                confidence += 0.3
                evidence["unknown_source"] = True
        
        # Check 3: Sensitive attributes being replicated
        sensitive_attrs = [
            attr for attr in event.attributes_replicated
            if any(s in attr.lower() for s in self.sensitive_replication_attrs)
        ]
        if len(sensitive_attrs) >= self.config["sensitive_attributes_threshold"]:
            threats.append(f"Sensitive attributes replicated: {', '.join(sensitive_attrs)}")
            confidence += 0.35
            evidence["sensitive_attrs"] = sensitive_attrs
        
        # Check 4: High replication rate from single source
        repl_count = len(self.replication_history[event.source_ip])
        if repl_count >= self.config["replication_threshold"]:
            threats.append(f"High replication rate: {repl_count}/min")
            confidence += 0.2
            evidence["replication_rate"] = repl_count
        
        # Check 5: Password-related replication
        password_attrs = ["unicodepwd", "ntpwdhistory", "supplementalcredentials"]
        if any(pa in attr.lower() for attr in event.attributes_replicated for pa in password_attrs):
            threats.append("Password attributes in replication (DCSync signature)")
            confidence += 0.4
            evidence["password_replication"] = True
        
        if confidence >= 0.5:
            return IdentityThreatEvent(
                event_id=f"dcsync_{secrets.token_hex(8)}",
                timestamp=event.timestamp,
                category=AttackCategory.AD_REPLICATION,
                attack_type="dcsync",
                severity=ThreatSeverity.CRITICAL,
                source_ip=event.source_ip,
                target_principal=event.destination_dc,
                description=f"DCSync attack detected: {'; '.join(threats)}",
                evidence=evidence,
                mitre_techniques=["T1003.006"],
                recommendations=[
                    "Immediately isolate source system",
                    "Review AD permissions for 'Replicating Directory Changes'",
                    "Reset KRBTGT password twice",
                    "Audit all accounts with DCSync rights",
                    "Enable Advanced Audit for Directory Service Access",
                    "Consider resetting all domain passwords"
                ],
                confidence=min(1.0, confidence)
            )
        
        return None
    
    def detect_dcshadow(self, event: Dict[str, Any]) -> Optional[IdentityThreatEvent]:
        """
        Detect DCShadow attacks.
        
        DCShadow uses the replication mechanism to inject changes
        into AD by registering a rogue DC temporarily.
        """
        event_type = event.get("event_type", "")
        
        indicators = []
        confidence = 0.0
        
        # Indicator 1: New DC registration
        if event_type == "dc_registration":
            dc_name = event.get("dc_name", "")
            if dc_name.lower() not in self.config["known_domain_controllers"]:
                indicators.append(f"Unknown DC registration: {dc_name}")
                confidence += 0.4
                self.dc_registration_events.append(event)
        
        # Indicator 2: Temporary SPN registration
        spn_changes = event.get("spn_changes", [])
        dc_spns = ["E3514235-4B06-11D1-AB04-00C04FC2DCD2", "GC/", "ldap/"]
        for spn in spn_changes:
            if any(ds in spn for ds in dc_spns):
                indicators.append(f"DC-related SPN added: {spn}")
                confidence += 0.3
        
        # Indicator 3: Schema modification through replication
        if event.get("schema_via_replication"):
            indicators.append("Schema modification via replication")
            confidence += 0.4
        
        # Indicator 4: Short-lived DC existence
        if event.get("dc_lifetime_seconds", 9999) < 60:
            indicators.append("Ephemeral DC registration (DCShadow signature)")
            confidence += 0.35
        
        if confidence >= 0.5:
            return IdentityThreatEvent(
                event_id=f"dcshadow_{secrets.token_hex(8)}",
                timestamp=datetime.now(timezone.utc),
                category=AttackCategory.AD_REPLICATION,
                attack_type="dcshadow",
                severity=ThreatSeverity.CRITICAL,
                source_ip=event.get("source_ip", "unknown"),
                target_principal=event.get("dc_name", "unknown"),
                description=f"Potential DCShadow attack: {'; '.join(indicators)}",
                evidence={
                    "indicators": indicators,
                    "raw_event": event
                },
                mitre_techniques=["T1207"],
                recommendations=[
                    "Investigate source system immediately",
                    "Review AD for unauthorized changes",
                    "Audit Enterprise Admins and Domain Admins groups",
                    "Enable Advanced Audit for directory service changes",
                    "Consider AD restoration from known-good backup"
                ],
                confidence=min(1.0, confidence)
            )
        
        return None
    
    def detect_admin_sdholder_abuse(self, event: Dict[str, Any]) -> Optional[IdentityThreatEvent]:
        """
        Detect AdminSDHolder persistence attacks.
        
        AdminSDHolder is a protected AD object whose ACL is applied to 
        all protected accounts every 60 minutes by SDProp.
        
        Attackers modify AdminSDHolder to gain persistent backdoor access.
        """
        modification_data = event.get("modification_data", {})
        
        indicators = []
        confidence = 0.0
        evidence = {
            "source_ip": event.get("source_ip", "unknown"),
            "modifying_principal": event.get("modifying_principal", "unknown"),
            "timestamp": event.get("timestamp", datetime.now(timezone.utc).isoformat())
        }
        
        target_dn = event.get("target_dn", "").lower()
        
        # Check if AdminSDHolder is being modified
        if "adminsdholder" in target_dn or "cn=adminsdholder,cn=system" in target_dn:
            indicators.append("AdminSDHolder object modification")
            confidence += 0.5
            evidence["adminsdholder_modified"] = True
            
            # Check what was modified
            if modification_data.get("acl_modified"):
                indicators.append("AdminSDHolder ACL modified (persistence backdoor)")
                confidence += 0.35
                evidence["acl_modified"] = True
                
                # Check for added permissions
                added_aces = modification_data.get("added_aces", [])
                for ace in added_aces:
                    if ace.get("rights") in ["GenericAll", "WriteDacl", "WriteOwner"]:
                        indicators.append(f"Dangerous permission added: {ace.get('rights')} for {ace.get('trustee')}")
                        confidence += 0.25
                        evidence["dangerous_permission"] = ace
        
        # Check for SDProp manipulation
        if event.get("sdprop_interval_changed"):
            indicators.append("SDProp interval modified (delay persistence)")
            confidence += 0.3
            evidence["sdprop_modified"] = True
        
        # Check protected user's AdminCount manipulation
        if modification_data.get("admincount_changed"):
            if modification_data.get("admincount_value") == 0:
                indicators.append("AdminCount cleared (removing protection)")
                confidence += 0.25
                evidence["admincount_cleared"] = True
        
        if confidence >= 0.5:
            return IdentityThreatEvent(
                event_id=f"adminsdholder_{secrets.token_hex(8)}",
                timestamp=datetime.now(timezone.utc),
                category=AttackCategory.PERSISTENCE,
                attack_type="adminsdholder_abuse",
                severity=ThreatSeverity.CRITICAL,
                source_ip=event.get("source_ip", "unknown"),
                target_principal="CN=AdminSDHolder,CN=System",
                description=f"AdminSDHolder persistence attack: {'; '.join(indicators)}",
                evidence=evidence,
                mitre_techniques=["T1078.002", "T1222.001"],
                recommendations=[
                    "Immediately audit AdminSDHolder ACL",
                    "Force SDProp to run and verify protected accounts",
                    "Review all privileged account permissions",
                    "Check for unauthorized ACE additions",
                    "Review recent privileged group changes",
                    "Consider restoring AdminSDHolder from backup"
                ],
                confidence=min(1.0, confidence)
            )
        
        return None
    
    def detect_sid_history_abuse(self, event: Dict[str, Any]) -> Optional[IdentityThreatEvent]:
        """
        Detect SID History injection attacks.
        
        SID History is used during domain migration but can be abused
        to inject privileged SIDs into non-privileged accounts.
        """
        modification_data = event.get("modification_data", {})
        
        indicators = []
        confidence = 0.0
        evidence = {
            "source_ip": event.get("source_ip", "unknown"),
            "modified_account": event.get("target_dn", "unknown"),
            "timestamp": event.get("timestamp", datetime.now(timezone.utc).isoformat())
        }
        
        # Check for SID History modification
        if modification_data.get("sid_history_modified"):
            added_sids = modification_data.get("added_sids", [])
            
            indicators.append(f"SID History modified: {len(added_sids)} SIDs added")
            confidence += 0.4
            evidence["added_sids"] = added_sids
            
            # Check for privileged SIDs
            privileged_rids = {
                "500": "Administrator",
                "512": "Domain Admins",
                "518": "Schema Admins",
                "519": "Enterprise Admins",
                "521": "Read-only Domain Controllers"
            }
            
            for sid in added_sids:
                parts = sid.split("-")
                if parts:
                    rid = parts[-1]
                    if rid in privileged_rids:
                        indicators.append(f"Privileged SID injected: {privileged_rids[rid]} ({sid})")
                        confidence += 0.4
                        evidence["privileged_sid_injection"] = True
            
            # Check if added during non-migration period
            if not event.get("migration_in_progress"):
                indicators.append("SID History modification outside migration")
                confidence += 0.2
                evidence["non_migration_modification"] = True
            
            # Check for cross-forest SID History (more suspicious)
            source_domain_sid = modification_data.get("source_domain_sid")
            target_domain_sid = modification_data.get("target_domain_sid")
            for sid in added_sids:
                if source_domain_sid and not sid.startswith(source_domain_sid):
                    if target_domain_sid and not sid.startswith(target_domain_sid):
                        indicators.append(f"Unknown domain SID in history: {sid}")
                        confidence += 0.25
                        evidence["unknown_domain_sid"] = sid
        
        if confidence >= 0.5:
            return IdentityThreatEvent(
                event_id=f"sidhistory_{secrets.token_hex(8)}",
                timestamp=datetime.now(timezone.utc),
                category=AttackCategory.PRIVILEGE_ESCALATION,
                attack_type="sid_history_injection",
                severity=ThreatSeverity.CRITICAL,
                source_ip=event.get("source_ip", "unknown"),
                target_principal=event.get("target_dn", "unknown"),
                description=f"SID History injection attack: {'; '.join(indicators)}",
                evidence=evidence,
                mitre_techniques=["T1134.005"],
                recommendations=[
                    "Enable SID filtering on all trusts",
                    "Remove unauthorized SID History entries",
                    "Audit SID History on all accounts",
                    "Review trust configurations",
                    "Enable SID History auditing",
                    "Consider quarantining affected account"
                ],
                confidence=min(1.0, confidence)
            )
        
        return None
    
    def detect_dpapi_key_extraction(self, event: Dict[str, Any]) -> Optional[IdentityThreatEvent]:
        """
        Detect DPAPI Domain Backup Key extraction.
        
        The domain DPAPI backup key can decrypt any DPAPI-protected
        secrets in the domain. Extraction enables mass credential theft.
        """
        replication_data = event.get("replication_data", {})
        
        indicators = []
        confidence = 0.0
        evidence = {
            "source_ip": event.get("source_ip", "unknown"),
            "requesting_principal": event.get("requesting_principal", "unknown"),
            "timestamp": event.get("timestamp", datetime.now(timezone.utc).isoformat())
        }
        
        # Check for BCKUPKEY secret replication
        replicated_attrs = replication_data.get("attributes", [])
        secrets_requested = replication_data.get("secrets", [])
        
        # DPAPI backup key object patterns
        dpapi_patterns = [
            "bckupkey",
            "g$bckupkey",
            "dpapi",
            "backup key",
            "cn=secrets,cn=system"
        ]
        
        for attr in replicated_attrs + secrets_requested:
            for pattern in dpapi_patterns:
                if pattern in attr.lower():
                    indicators.append(f"DPAPI-related secret accessed: {attr}")
                    confidence += 0.4
                    evidence["dpapi_secret_accessed"] = attr
        
        # Check for LSA secret replication
        lsa_secrets = ["currentvalue", "priorvalue", "g$", "_sc_"]
        for attr in replicated_attrs:
            if any(ls in attr.lower() for ls in lsa_secrets):
                indicators.append(f"LSA secret replicated: {attr}")
                confidence += 0.3
                evidence["lsa_secret_replicated"] = attr
        
        # Check if request came from non-DC
        if not event.get("source_is_dc"):
            indicators.append("DPAPI key accessed from non-Domain Controller")
            confidence += 0.3
            evidence["non_dc_access"] = True
        
        # Check for specific DRSUAPI calls for secrets
        if replication_data.get("operation") == "DsGetNCChanges":
            if replication_data.get("nc") == "CN=Configuration":
                indicators.append("Configuration NC replication (secret access)")
                confidence += 0.15
        
        if confidence >= 0.5:
            return IdentityThreatEvent(
                event_id=f"dpapi_{secrets.token_hex(8)}",
                timestamp=datetime.now(timezone.utc),
                category=AttackCategory.CREDENTIAL_THEFT,
                attack_type="dpapi_key_extraction",
                severity=ThreatSeverity.CRITICAL,
                source_ip=event.get("source_ip", "unknown"),
                target_principal="DPAPI Domain Backup Key",
                description=f"DPAPI backup key extraction: {'; '.join(indicators)}",
                evidence=evidence,
                mitre_techniques=["T1003.004", "T1555.003"],
                recommendations=[
                    "Immediately investigate source system",
                    "Consider rotating DPAPI backup keys",
                    "Audit all DCSync-capable accounts",
                    "Review directory replication permissions",
                    "Assume widespread credential compromise",
                    "Plan for enterprise-wide secret rotation"
                ],
                confidence=min(1.0, confidence)
            )
        
        return None
    
    def detect_gpo_replication_abuse(self, event: Dict[str, Any]) -> Optional[IdentityThreatEvent]:
        """
        Detect malicious Group Policy replication.
        
        Attackers may use replication to inject malicious GPO settings
        or modify existing policies for persistence/lateral movement.
        """
        replication_data = event.get("replication_data", {})
        
        indicators = []
        confidence = 0.0
        evidence = {
            "source_ip": event.get("source_ip", "unknown"),
            "timestamp": event.get("timestamp", datetime.now(timezone.utc).isoformat())
        }
        
        # Check for GPO modifications via replication
        modified_objects = replication_data.get("modified_objects", [])
        for obj in modified_objects:
            obj_class = obj.get("object_class", "").lower()
            obj_dn = obj.get("dn", "").lower()
            
            if obj_class == "grouppolicycontainer" or "policies" in obj_dn:
                indicators.append(f"GPO modified via replication: {obj.get('dn')}")
                confidence += 0.3
                evidence["modified_gpo"] = obj.get("dn")
                
                # Check for dangerous attributes
                dangerous_attrs = obj.get("modified_attributes", [])
                for attr in dangerous_attrs:
                    if attr.lower() in ["gpcfilesyspath", "gplink", "versionNumber"]:
                        indicators.append(f"GPO {attr} modified")
                        confidence += 0.2
        
        # Check for new GPO linked at high level
        gpo_link = replication_data.get("new_gpo_link", {})
        if gpo_link:
            link_location = gpo_link.get("link_location", "").lower()
            if any(x in link_location for x in ["dc=", "domain controllers"]):
                indicators.append(f"GPO linked at domain/DC level: {link_location}")
                confidence += 0.35
                evidence["high_level_link"] = link_location
        
        # Check for scheduled task/script installation via GPO
        gpo_content = replication_data.get("gpo_content", {})
        if gpo_content.get("scheduled_tasks") or gpo_content.get("startup_scripts"):
            indicators.append("GPO contains scheduled tasks or startup scripts")
            confidence += 0.25
            evidence["code_execution"] = True
        
        # Check for service installation via GPO
        if gpo_content.get("service_install"):
            indicators.append("GPO contains service installation")
            confidence += 0.25
            evidence["service_install"] = True
        
        if confidence >= 0.5:
            return IdentityThreatEvent(
                event_id=f"gpo_abuse_{secrets.token_hex(8)}",
                timestamp=datetime.now(timezone.utc),
                category=AttackCategory.PERSISTENCE,
                attack_type="gpo_replication_abuse",
                severity=ThreatSeverity.HIGH,
                source_ip=event.get("source_ip", "unknown"),
                target_principal=evidence.get("modified_gpo", "unknown"),
                description=f"Malicious GPO replication: {'; '.join(indicators)}",
                evidence=evidence,
                mitre_techniques=["T1484.001", "T1053.005"],
                recommendations=[
                    "Review GPO changes immediately",
                    "Check GPO file system content",
                    "Audit GPO link changes",
                    "Review scheduled tasks and startup scripts",
                    "Consider reverting GPO to previous version",
                    "Enable advanced GPO auditing"
                ],
                confidence=min(1.0, confidence)
            )
        
        return None
    
    def analyze_windows_event(self, event_id: int, event_data: Dict[str, Any]) -> Optional[IdentityThreatEvent]:
        """
        Analyze Windows Security Event Log events for replication attacks.
        
        Supports:
        - Event 4662 (Directory object operation)
        - Event 5136 (Directory object modified)
        - Event 4929 (Directory replication)
        """
        if event_id == WindowsSecurityEventID.DIRECTORY_SERVICE_ACCESS:
            return self._analyze_4662(event_data)
        elif event_id == WindowsSecurityEventID.DIRECTORY_OBJECT_MODIFIED:
            return self._analyze_5136(event_data)
        
        return None
    
    def _analyze_4662(self, event_data: Dict[str, Any]) -> Optional[IdentityThreatEvent]:
        """Analyze Event 4662 - Directory Service Access"""
        # Look for DCSync operations
        object_type = event_data.get("ObjectType", "")
        operation = event_data.get("OperationType", "")
        properties = event_data.get("Properties", "")
        subject_user = event_data.get("SubjectUserName", "")
        
        # DCSync GUID: Replicating Directory Changes (1131f6aa-9c07-11d1-f79f-00c04fc2dcd2)
        dcsync_guids = [
            "1131f6aa-9c07-11d1-f79f-00c04fc2dcd2",  # Replicating Directory Changes
            "1131f6ad-9c07-11d1-f79f-00c04fc2dcd2",  # Replicating Directory Changes All
            "89e95b76-444d-4c62-991a-0facbeda640c",  # Replicating Directory Changes in Filtered Set
        ]
        
        for guid in dcsync_guids:
            if guid.lower() in properties.lower():
                return self.analyze_replication_event(ADReplicationEvent(
                    timestamp=datetime.now(timezone.utc),
                    source_dc=subject_user,
                    destination_dc=event_data.get("ObjectServer", ""),
                    source_ip=event_data.get("ClientAddress", ""),
                    naming_context=event_data.get("ObjectDN", ""),
                    attributes_replicated=[properties],
                    is_legitimate_dc=subject_user.endswith("$") and 
                                    subject_user[:-1].lower() in self.config["known_domain_controllers"]
                ))
        
        return None
    
    def _analyze_5136(self, event_data: Dict[str, Any]) -> Optional[IdentityThreatEvent]:
        """Analyze Event 5136 - Directory Object Modified"""
        object_dn = event_data.get("ObjectDN", "")
        attribute = event_data.get("AttributeLDAPDisplayName", "")
        
        # Check for AdminSDHolder modifications
        if "adminsdholder" in object_dn.lower():
            return self.detect_admin_sdholder_abuse({
                "target_dn": object_dn,
                "modification_data": {
                    "acl_modified": attribute.lower() in ["ntsecuritydescriptor", "dacl"]
                },
                "modifying_principal": event_data.get("SubjectUserName", ""),
                "source_ip": event_data.get("ClientAddress", "")
            })
        
        # Check for SID History modifications
        if attribute.lower() == "sidhistory":
            return self.detect_sid_history_abuse({
                "target_dn": object_dn,
                "modification_data": {
                    "sid_history_modified": True,
                    "added_sids": [event_data.get("AttributeValue", "")]
                },
                "source_ip": event_data.get("ClientAddress", "")
            })
        
        return None
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get monitor statistics"""
        return {
            "replication_events_tracked": sum(len(v) for v in self.replication_history.values()),
            "unique_sources": len(self.replication_history),
            "dc_registration_events": len(self.dc_registration_events),
            "known_dcs": len(self.config["known_domain_controllers"]),
            "config": self.config
        }
    
    def clear_state(self):
        """Clear monitor state"""
        self.replication_history.clear()
        self.dc_registration_events.clear()
        logger.info("ADReplicationMonitor state cleared")


# =============================================================================
# CREDENTIAL THREAT ANALYZER
# =============================================================================

class CredentialThreatAnalyzer:
    """
    Analyzes credential-based attacks including:
    - Pass-the-Hash (T1550.002)
    - Pass-the-Ticket (T1550.003)
    - Credential Dumping (T1003)
    - NTLM Relay (T1557.001)
    """
    
    def __init__(self):
        # Configuration
        self.config = {
            "pth_same_hash_threshold": 3,      # Same hash from different IPs
            "ptt_unusual_source_alert": True,
            "ntlm_downgrade_alert": True,
        }
        
        # State tracking
        self.ntlm_hash_sources: Dict[str, Set[str]] = defaultdict(set)  # hash -> {source_ips}
        self.ticket_sources: Dict[str, Set[str]] = defaultdict(set)     # ticket_hash -> {source_ips}
        self.authentication_patterns: Dict[str, List[Dict]] = defaultdict(list)  # user -> auth events
        
        logger.info("CredentialThreatAnalyzer initialized")
    
    def analyze_ntlm_auth(self, event: Dict[str, Any]) -> Optional[IdentityThreatEvent]:
        """
        Analyze NTLM authentication for Pass-the-Hash indicators.
        """
        username = event.get("username", "")
        source_ip = event.get("source_ip", "")
        ntlm_hash = event.get("ntlm_hash", "")  # Would come from advanced logging
        auth_type = event.get("auth_type", "interactive")
        workstation = event.get("workstation", "")
        
        if not ntlm_hash:
            # Calculate a pseudo-hash for tracking (in real scenario, use actual NTLM response)
            ntlm_hash = hashlib.sha256(f"{username}:{source_ip}:{event.get('timestamp')}".encode()).hexdigest()[:16]
        
        # Track source IPs for this hash
        self.ntlm_hash_sources[ntlm_hash].add(source_ip)
        
        # Track authentication pattern
        self.authentication_patterns[username].append({
            "timestamp": event.get("timestamp"),
            "source_ip": source_ip,
            "auth_type": auth_type,
            "workstation": workstation
        })
        
        threats = []
        confidence = 0.0
        evidence = {
            "username": username,
            "source_ip": source_ip,
            "auth_type": auth_type,
            "workstation": workstation
        }
        
        # Check 1: Same hash from multiple sources (Pass-the-Hash indicator)
        if len(self.ntlm_hash_sources[ntlm_hash]) >= self.config["pth_same_hash_threshold"]:
            threats.append(f"NTLM hash used from {len(self.ntlm_hash_sources[ntlm_hash])} different IPs")
            confidence += 0.5
            evidence["source_ips"] = list(self.ntlm_hash_sources[ntlm_hash])
        
        # Check 2: Network logon to multiple systems
        recent_auths = [
            a for a in self.authentication_patterns[username]
            if (datetime.fromisoformat(a["timestamp"]) > 
                datetime.fromisoformat(event.get("timestamp")) - timedelta(minutes=5))
        ]
        unique_targets = {a["workstation"] for a in recent_auths if a["workstation"]}
        if len(unique_targets) >= 5:
            threats.append(f"Rapid lateral movement: {len(unique_targets)} systems in 5 minutes")
            confidence += 0.35
            evidence["lateral_movement"] = list(unique_targets)
        
        # Check 3: NTLM when Kerberos expected
        if event.get("expected_kerberos") and auth_type == "ntlm":
            threats.append("NTLM used when Kerberos expected (potential downgrade)")
            confidence += 0.25
            evidence["ntlm_downgrade"] = True
        
        # Check 4: Auth to sensitive resource
        if event.get("target_sensitive"):
            sensitive_resource = event.get("target_resource", "")
            threats.append(f"NTLM auth to sensitive resource: {sensitive_resource}")
            confidence += 0.2
            evidence["sensitive_target"] = sensitive_resource
        
        if confidence >= 0.5:
            return IdentityThreatEvent(
                event_id=f"pth_{secrets.token_hex(8)}",
                timestamp=datetime.now(timezone.utc),
                category=AttackCategory.CREDENTIAL_THEFT,
                attack_type="pass_the_hash",
                severity=ThreatSeverity.HIGH,
                source_ip=source_ip,
                target_principal=username,
                description=f"Potential Pass-the-Hash attack: {'; '.join(threats)}",
                evidence=evidence,
                mitre_techniques=["T1550.002"],
                recommendations=[
                    "Reset password for affected account",
                    "Investigate source systems for credential theft tools",
                    "Enable Protected Users group membership",
                    "Implement Credential Guard",
                    "Restrict NTLM usage via Group Policy"
                ],
                confidence=min(1.0, confidence)
            )
        
        return None
    
    def analyze_ticket_reuse(self, event: Dict[str, Any]) -> Optional[IdentityThreatEvent]:
        """
        Analyze Kerberos ticket reuse for Pass-the-Ticket indicators.
        """
        ticket_hash = event.get("ticket_hash", "")
        source_ip = event.get("source_ip", "")
        username = event.get("username", "")
        
        if not ticket_hash:
            return None
        
        # Track source IPs for this ticket
        old_sources = self.ticket_sources[ticket_hash].copy()
        self.ticket_sources[ticket_hash].add(source_ip)
        
        threats = []
        confidence = 0.0
        evidence = {
            "username": username,
            "source_ip": source_ip,
            "ticket_hash": ticket_hash[:16] + "..."
        }
        
        # Check: Same ticket from different source
        if old_sources and source_ip not in old_sources:
            threats.append(f"Ticket reused from new IP (previously: {list(old_sources)})")
            confidence += 0.6
            evidence["previous_sources"] = list(old_sources)
        
        # Check: Ticket used after expected expiry
        if event.get("ticket_expired"):
            threats.append("Ticket used after expiration (forged ticket indicator)")
            confidence += 0.4
        
        if confidence >= 0.5:
            return IdentityThreatEvent(
                event_id=f"ptt_{secrets.token_hex(8)}",
                timestamp=datetime.now(timezone.utc),
                category=AttackCategory.CREDENTIAL_THEFT,
                attack_type="pass_the_ticket",
                severity=ThreatSeverity.HIGH,
                source_ip=source_ip,
                target_principal=username,
                description=f"Potential Pass-the-Ticket attack: {'; '.join(threats)}",
                evidence=evidence,
                mitre_techniques=["T1550.003"],
                recommendations=[
                    "Purge Kerberos tickets on affected systems",
                    "Reset password for affected account",
                    "Investigate source systems for credential theft",
                    "Review ticket granting policies",
                    "Enable Kerberos armoring (FAST)"
                ],
                confidence=min(1.0, confidence)
            )
        
        return None
    
    def detect_credential_dumping(self, event: Dict[str, Any]) -> Optional[IdentityThreatEvent]:
        """
        Detect credential dumping attempts (LSASS access, SAM dump, etc.)
        """
        process_name = event.get("process_name", "").lower()
        target_process = event.get("target_process", "").lower()
        access_mask = event.get("access_mask", 0)
        
        threats = []
        confidence = 0.0
        evidence = {
            "process_name": process_name,
            "target_process": target_process,
            "access_mask": hex(access_mask) if access_mask else "N/A"
        }
        
        # Known credential dumping tools
        malicious_tools = {
            "mimikatz", "procdump", "sqldumper", "comsvcs",
            "secretsdump", "pypykatz", "lazagne", "gsecdump",
            "pwdump", "fgdump", "wce", "ntdsutil"
        }
        
        # Check 1: Known tool
        if any(tool in process_name for tool in malicious_tools):
            threats.append(f"Known credential dumping tool: {process_name}")
            confidence += 0.7
            evidence["known_tool"] = True
        
        # Check 2: LSASS access
        if "lsass" in target_process:
            if access_mask & 0x1010:  # PROCESS_VM_READ | PROCESS_QUERY_INFORMATION
                threats.append("Suspicious LSASS memory access")
                confidence += 0.5
                evidence["lsass_access"] = True
        
        # Check 3: SAM/SECURITY hive access
        registry_targets = event.get("registry_targets", [])
        sensitive_hives = ["sam", "security", "system"]
        for hive in sensitive_hives:
            if any(hive in rt.lower() for rt in registry_targets):
                threats.append(f"Access to {hive.upper()} registry hive")
                confidence += 0.4
                evidence[f"{hive}_access"] = True
        
        # Check 4: NTDS.dit access
        file_access = event.get("file_access", [])
        if any("ntds.dit" in f.lower() for f in file_access):
            threats.append("NTDS.dit database access")
            confidence += 0.6
            evidence["ntds_access"] = True
        
        if confidence >= 0.5:
            return IdentityThreatEvent(
                event_id=f"cred_dump_{secrets.token_hex(8)}",
                timestamp=datetime.now(timezone.utc),
                category=AttackCategory.CREDENTIAL_THEFT,
                attack_type="credential_dumping",
                severity=ThreatSeverity.CRITICAL,
                source_ip=event.get("source_ip", "localhost"),
                target_principal=event.get("username", "SYSTEM"),
                description=f"Credential dumping detected: {'; '.join(threats)}",
                evidence=evidence,
                mitre_techniques=["T1003.001", "T1003.002", "T1003.003"],
                recommendations=[
                    "Isolate affected system immediately",
                    "Capture memory dump for forensics",
                    "Assume all cached credentials compromised",
                    "Reset passwords for accounts that accessed the system",
                    "Enable Credential Guard",
                    "Deploy LSA protection"
                ],
                confidence=min(1.0, confidence)
            )
        
        return None
    
    def detect_lsass_injection(self, event: Dict[str, Any]) -> Optional[IdentityThreatEvent]:
        """
        Detect LSASS process injection for credential theft.
        
        Advanced credential dumping may use process injection
        rather than direct memory access.
        """
        process_data = event.get("process_data", {})
        
        indicators = []
        confidence = 0.0
        evidence = {
            "source_process": event.get("source_process", "unknown"),
            "target_process": event.get("target_process", "unknown"),
            "source_ip": event.get("source_ip", "localhost")
        }
        
        # Check 1: Code injection into LSASS
        if "lsass" in event.get("target_process", "").lower():
            injection_type = process_data.get("injection_technique", "")
            
            if injection_type:
                indicators.append(f"Code injection into LSASS: {injection_type}")
                confidence += 0.7
                evidence["injection_type"] = injection_type
            else:
                # Generic LSASS access with write permissions
                access_flags = process_data.get("access_flags", 0)
                if access_flags & 0x20:  # PROCESS_VM_WRITE
                    indicators.append("Write access to LSASS process memory")
                    confidence += 0.5
        
        # Check 2: DLL injection patterns
        if process_data.get("dll_injected"):
            dll_name = process_data.get("injected_dll", "")
            indicators.append(f"DLL injected into credential process: {dll_name}")
            confidence += 0.4
            evidence["injected_dll"] = dll_name
        
        # Check 3: CreateRemoteThread to LSASS
        if process_data.get("remote_thread_created"):
            indicators.append("Remote thread created in LSASS")
            confidence += 0.5
            evidence["remote_thread"] = True
        
        # Check 4: Suspicious source process
        suspicious_sources = ["powershell", "cmd", "wscript", "cscript", "mshta", "rundll32"]
        source = event.get("source_process", "").lower()
        if any(s in source for s in suspicious_sources):
            indicators.append(f"Injection from suspicious process: {source}")
            confidence += 0.2
        
        # Check 5: SSP installation (Security Support Provider)
        if process_data.get("ssp_installed"):
            indicators.append("Security Support Provider installed (credential interception)")
            confidence += 0.6
            evidence["ssp_installed"] = True
        
        if confidence >= 0.5:
            return IdentityThreatEvent(
                event_id=f"lsass_inject_{secrets.token_hex(8)}",
                timestamp=datetime.now(timezone.utc),
                category=AttackCategory.CREDENTIAL_THEFT,
                attack_type="lsass_injection",
                severity=ThreatSeverity.CRITICAL,
                source_ip=event.get("source_ip", "localhost"),
                target_principal="LSASS.exe",
                description=f"LSASS injection attack: {'; '.join(indicators)}",
                evidence=evidence,
                mitre_techniques=["T1003.001", "T1055"],
                recommendations=[
                    "Isolate system immediately",
                    "Enable LSA protection (RunAsPPL)",
                    "Deploy Credential Guard",
                    "Capture memory for forensic analysis",
                    "Reset all credentials from the system",
                    "Review Security Support Providers"
                ],
                confidence=min(1.0, confidence)
            )
        
        return None
    
    def detect_ntlm_relay(self, event: Dict[str, Any]) -> Optional[IdentityThreatEvent]:
        """
        Detect NTLM relay attacks.
        
        NTLM relay forwards authentication to access resources
        as the victim user.
        """
        auth_data = event.get("auth_data", {})
        
        indicators = []
        confidence = 0.0
        evidence = {
            "source_ip": event.get("source_ip", "unknown"),
            "target_ip": event.get("target_ip", "unknown"),
            "relay_target": event.get("relay_target", "unknown"),
            "username": event.get("username", "unknown")
        }
        
        # Check 1: Authentication source differs from relay source
        auth_source = auth_data.get("ntlm_source_ip")
        relay_source = event.get("source_ip")
        
        if auth_source and relay_source:
            if auth_source != relay_source:
                indicators.append(f"NTLM auth relayed: origin {auth_source} -> relay {relay_source}")
                confidence += 0.6
                evidence["relay_detected"] = True
                evidence["original_source"] = auth_source
        
        # Check 2: Type 2/Type 3 timing anomaly
        if auth_data.get("type3_timing_anomaly"):
            indicators.append("NTLM Type 3 response timing indicates relay")
            confidence += 0.3
        
        # Check 3: Relay to sensitive service
        relay_target = event.get("relay_target", "").lower()
        sensitive_targets = ["ldap", "smb", "http", "mssql", "exchange"]
        
        for target in sensitive_targets:
            if target in relay_target:
                indicators.append(f"NTLM relay to sensitive service: {target}")
                confidence += 0.2
                evidence["sensitive_relay_target"] = target
        
        # Check 4: Machine account relay (common in RBCD attacks)
        username = event.get("username", "")
        if username.endswith("$"):  # Machine account
            indicators.append(f"Machine account relayed: {username}")
            confidence += 0.25
            evidence["machine_relay"] = True
        
        # Check 5: Relay from coerced authentication
        if auth_data.get("coerced_auth"):
            indicators.append("Authentication appears coerced (PetitPotam/PrinterBug)")
            confidence += 0.3
            evidence["coerced"] = True
        
        # Check 6: Channel binding failure
        if auth_data.get("channel_binding_failed"):
            indicators.append("Channel binding failed (relay indicator)")
            confidence += 0.25
        
        if confidence >= 0.5:
            return IdentityThreatEvent(
                event_id=f"ntlm_relay_{secrets.token_hex(8)}",
                timestamp=datetime.now(timezone.utc),
                category=AttackCategory.LATERAL_MOVEMENT,
                attack_type="ntlm_relay",
                severity=ThreatSeverity.CRITICAL,
                source_ip=relay_source or "unknown",
                target_principal=event.get("username", "unknown"),
                description=f"NTLM relay attack detected: {'; '.join(indicators)}",
                evidence=evidence,
                mitre_techniques=["T1557.001"],
                recommendations=[
                    "Enable EPA (Extended Protection for Authentication)",
                    "Enable LDAP signing and channel binding",
                    "Disable NTLM where possible",
                    "Block source IP",
                    "Investigate relay target for malicious changes",
                    "Review RBCD configurations if machine account relayed"
                ],
                confidence=min(1.0, confidence)
            )
        
        return None
    
    def detect_dpapi_abuse(self, event: Dict[str, Any]) -> Optional[IdentityThreatEvent]:
        """
        Detect DPAPI credential theft.
        
        Attackers may access DPAPI master keys or use CryptUnprotectData
        to steal protected credentials.
        """
        dpapi_data = event.get("dpapi_data", {})
        
        indicators = []
        confidence = 0.0
        evidence = {
            "source_ip": event.get("source_ip", "localhost"),
            "process": event.get("process_name", "unknown")
        }
        
        # Check 1: Master key file access
        if dpapi_data.get("master_key_accessed"):
            indicators.append("DPAPI master key file accessed")
            confidence += 0.4
            evidence["master_key_access"] = True
            
            # Access to other user's master keys
            if dpapi_data.get("cross_user_access"):
                indicators.append("Cross-user DPAPI master key access")
                confidence += 0.3
                evidence["cross_user"] = True
        
        # Check 2: CryptUnprotectData calls
        if dpapi_data.get("crypt_unprotect_calls", 0) > 10:
            indicators.append(f"Mass CryptUnprotectData calls: {dpapi_data.get('crypt_unprotect_calls')}")
            confidence += 0.3
            evidence["mass_decrypt"] = dpapi_data.get("crypt_unprotect_calls")
        
        # Check 3: Browser credential files
        browser_paths = dpapi_data.get("accessed_paths", [])
        browser_cred_patterns = ["login data", "cookies", "web data", "credential", "vault"]
        
        for path in browser_paths:
            if any(p in path.lower() for p in browser_cred_patterns):
                indicators.append(f"Browser credential file accessed: {path}")
                confidence += 0.25
                evidence["browser_creds"] = True
        
        # Check 4: Credential Manager vault access
        if dpapi_data.get("credential_vault_accessed"):
            indicators.append("Windows Credential Manager vault accessed")
            confidence += 0.35
            evidence["vault_access"] = True
        
        # Check 5: Domain backup key usage
        if dpapi_data.get("domain_backup_key_used"):
            indicators.append("Domain DPAPI backup key used (mass decryption)")
            confidence += 0.5
            evidence["domain_key"] = True
        
        # Check 6: SharpDPAPI-like tool behavior
        if dpapi_data.get("tool_pattern_detected"):
            indicators.append(f"DPAPI tool pattern detected: {dpapi_data.get('tool_name', 'unknown')}")
            confidence += 0.4
            evidence["tool_detected"] = dpapi_data.get("tool_name")
        
        if confidence >= 0.5:
            return IdentityThreatEvent(
                event_id=f"dpapi_{secrets.token_hex(8)}",
                timestamp=datetime.now(timezone.utc),
                category=AttackCategory.CREDENTIAL_THEFT,
                attack_type="dpapi_abuse",
                severity=ThreatSeverity.HIGH,
                source_ip=event.get("source_ip", "localhost"),
                target_principal=event.get("user", "unknown"),
                description=f"DPAPI credential theft: {'; '.join(indicators)}",
                evidence=evidence,
                mitre_techniques=["T1555.003", "T1555.004"],
                recommendations=[
                    "Investigate source process and system",
                    "Reset affected user's passwords",
                    "Rotate domain DPAPI backup key if accessed",
                    "Clear browser saved credentials",
                    "Enable Credential Guard",
                    "Review file access permissions on credential stores"
                ],
                confidence=min(1.0, confidence)
            )
        
        return None
    
    def detect_kerberos_fast_bypass(self, event: Dict[str, Any]) -> Optional[IdentityThreatEvent]:
        """
        Detect Kerberos FAST (Flexible Authentication Secure Tunneling) bypass.
        
        FAST/Kerberos Armoring provides additional protection. Attackers
        may attempt to downgrade or bypass this protection.
        """
        kerberos_data = event.get("kerberos_data", {})
        
        indicators = []
        confidence = 0.0
        evidence = {
            "source_ip": event.get("source_ip", "unknown"),
            "client_principal": event.get("client_principal", "unknown")
        }
        
        # Check 1: FAST-required account without FAST
        if kerberos_data.get("fast_required") and not kerberos_data.get("fast_used"):
            indicators.append("FAST-required account authenticated without FAST")
            confidence += 0.5
            evidence["fast_bypass"] = True
        
        # Check 2: Armor ticket anomaly
        armor_ticket = kerberos_data.get("armor_ticket", {})
        if armor_ticket.get("missing"):
            indicators.append("Missing Kerberos armor ticket")
            confidence += 0.3
        elif armor_ticket.get("invalid_signature"):
            indicators.append("Invalid Kerberos armor ticket signature")
            confidence += 0.4
            evidence["invalid_armor"] = True
        
        # Check 3: Pre-authentication type downgrade
        expected_pa_type = kerberos_data.get("expected_pa_type", [])
        actual_pa_type = kerberos_data.get("actual_pa_type", [])
        
        if expected_pa_type and actual_pa_type:
            # FAST = PA-FX-FAST (136), If expected but not present
            if 136 in expected_pa_type and 136 not in actual_pa_type:
                indicators.append("PA-FX-FAST type not used when expected")
                confidence += 0.35
        
        # Check 4: Anonymous PKINIT when certificate required
        if kerberos_data.get("anonymous_pkinit"):
            if kerberos_data.get("certificate_required"):
                indicators.append("Anonymous PKINIT used when certificate required")
                confidence += 0.4
                evidence["anonymous_pkinit_bypass"] = True
        
        # Check 5: Unclaimed TGT in armored realm
        if kerberos_data.get("unarmored_tgt_in_armored_realm"):
            indicators.append("Unarmored TGT accepted in armored realm")
            confidence += 0.3
        
        if confidence >= 0.5:
            return IdentityThreatEvent(
                event_id=f"fast_bypass_{secrets.token_hex(8)}",
                timestamp=datetime.now(timezone.utc),
                category=AttackCategory.KERBEROS,
                attack_type="kerberos_fast_bypass",
                severity=ThreatSeverity.HIGH,
                source_ip=event.get("source_ip", "unknown"),
                target_principal=event.get("client_principal", "unknown"),
                description=f"Kerberos armoring bypass: {'; '.join(indicators)}",
                evidence=evidence,
                mitre_techniques=["T1558"],
                recommendations=[
                    "Review FAST/Kerberos armoring configuration",
                    "Ensure all DCs enforce armoring consistently",
                    "Check for rogues DCs that may accept unarmored requests",
                    "Review client-side armoring support",
                    "Enable claims support for Protected Users"
                ],
                confidence=min(1.0, confidence)
            )
        
        return None
    
    def analyze_windows_event(self, event_id: int, event_data: Dict[str, Any]) -> Optional[IdentityThreatEvent]:
        """
        Analyze Windows Security Event Log events for credential attacks.
        
        Supports:
        - Event 4624 (Successful logon)
        - Event 4625 (Failed logon)
        - Event 4648 (Explicit credentials logon)
        - Event 4776 (NTLM authentication)
        """
        if event_id == WindowsSecurityEventID.LOGON_SUCCESS:
            return self._analyze_4624(event_data)
        elif event_id == WindowsSecurityEventID.LOGON_FAILED:
            return self._analyze_4625(event_data)
        elif event_id == WindowsSecurityEventID.EXPLICIT_CREDENTIALS:
            return self._analyze_4648(event_data)
        elif event_id == WindowsSecurityEventID.NTLM_AUTHENTICATION:
            return self._analyze_4776(event_data)
        
        return None
    
    def _analyze_4624(self, event_data: Dict[str, Any]) -> Optional[IdentityThreatEvent]:
        """Analyze Event 4624 - Successful Logon"""
        logon_type = int(event_data.get("LogonType", "0"))
        source_ip = event_data.get("IpAddress", "").strip("::ffff:").strip("-")
        username = event_data.get("TargetUserName", "")
        auth_package = event_data.get("AuthenticationPackageName", "")
        
        # Convert to internal format and analyze
        return self.analyze_ntlm_auth({
            "username": username,
            "source_ip": source_ip,
            "auth_type": "ntlm" if "NTLM" in auth_package.upper() else "kerberos",
            "workstation": event_data.get("WorkstationName", ""),
            "timestamp": event_data.get("TimeCreated", datetime.now(timezone.utc).isoformat()),
            "expected_kerberos": logon_type in [LogonType.NETWORK, LogonType.REMOTE_INTERACTIVE],
            "target_sensitive": event_data.get("TargetDomainName", "").upper() == event_data.get("SubjectDomainName", "").upper()
        })
    
    def _analyze_4625(self, event_data: Dict[str, Any]) -> Optional[IdentityThreatEvent]:
        """Analyze Event 4625 - Failed Logon"""
        # Track for spray detection (handled by LDAPAttackDetector for now)
        return None
    
    def _analyze_4648(self, event_data: Dict[str, Any]) -> Optional[IdentityThreatEvent]:
        """Analyze Event 4648 - Explicit Credentials Logon"""
        source_process = event_data.get("ProcessName", "")
        target_user = event_data.get("TargetUserName", "")
        target_server = event_data.get("TargetServerName", "")
        source_ip = event_data.get("IpAddress", "").strip("::ffff:")
        
        # Suspicious RunAs patterns
        suspicious_processes = ["sekurlsa", "mimikatz", "powershell", "cmd"]
        
        if any(s in source_process.lower() for s in suspicious_processes):
            return IdentityThreatEvent(
                event_id=f"explicit_cred_{secrets.token_hex(8)}",
                timestamp=datetime.now(timezone.utc),
                category=AttackCategory.CREDENTIAL_THEFT,
                attack_type="explicit_credentials",
                severity=ThreatSeverity.MEDIUM,
                source_ip=source_ip,
                target_principal=target_user,
                description=f"Suspicious explicit credential use from {source_process} to {target_server}",
                evidence={
                    "process": source_process,
                    "target_user": target_user,
                    "target_server": target_server,
                    "source_ip": source_ip
                },
                mitre_techniques=["T1078"],
                recommendations=[
                    "Investigate source process",
                    "Verify legitimate use of credentials",
                    "Review user's credential usage patterns"
                ],
                confidence=0.6
            )
        
        return None
    
    def _analyze_4776(self, event_data: Dict[str, Any]) -> Optional[IdentityThreatEvent]:
        """Analyze Event 4776 - NTLM Authentication"""
        username = event_data.get("TargetUserName", "")
        workstation = event_data.get("Workstation", "")
        status = event_data.get("Status", "0x0")
        
        # Track authentication pattern
        return self.analyze_ntlm_auth({
            "username": username,
            "workstation": workstation,
            "auth_type": "ntlm",
            "source_ip": event_data.get("ClientAddress", ""),
            "timestamp": event_data.get("TimeCreated", datetime.now(timezone.utc).isoformat())
        })
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get analyzer statistics"""
        return {
            "ntlm_hashes_tracked": len(self.ntlm_hash_sources),
            "tickets_tracked": len(self.ticket_sources),
            "users_tracked": len(self.authentication_patterns),
            "total_auth_events": sum(len(v) for v in self.authentication_patterns.values()),
            "config": self.config
        }
    
    def clear_state(self):
        """Clear analyzer state"""
        self.ntlm_hash_sources.clear()
        self.ticket_sources.clear()
        self.authentication_patterns.clear()
        logger.info("CredentialThreatAnalyzer state cleared")


# =============================================================================
# UNIFIED IDENTITY PROTECTION ENGINE
# =============================================================================

class IdentityProtectionEngine:
    """
    Unified engine for identity threat detection and response.
    
    Integrates all identity protection detectors:
    - Kerberos attack detection
    - LDAP attack detection  
    - AD replication monitoring
    - Credential threat analysis
    
    Provides:
    - Correlated threat detection
    - Risk scoring
    - Automated response recommendations
    - Integration with SOAR
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        
        # Initialize all detectors
        self.kerberos_detector = KerberosAttackDetector()
        self.ldap_detector = LDAPAttackDetector()
        self.ad_replication_monitor = ADReplicationMonitor()
        self.credential_analyzer = CredentialThreatAnalyzer()
        
        # Threat storage
        self.active_threats: Dict[str, IdentityThreatEvent] = {}
        self.threat_history: List[IdentityThreatEvent] = []
        
        # Correlation state
        self.entity_threat_scores: Dict[str, float] = defaultdict(float)  # principal -> cumulative risk
        self.ip_threat_scores: Dict[str, float] = defaultdict(float)      # ip -> cumulative risk
        
        # Configuration
        self.config = {
            "correlation_window_minutes": 30,
            "risk_score_decay_hours": 24,
            "auto_response_threshold": 0.8,
            "alert_threshold": 0.5,
        }
        
        # Metrics
        self.metrics = {
            "events_analyzed": 0,
            "threats_detected": 0,
            "critical_threats": 0,
            "auto_responses_triggered": 0
        }
        
        logger.info("IdentityProtectionEngine initialized with all detectors")
    
    def process_event(self, event_type: str, event_data: Dict[str, Any]) -> Optional[IdentityThreatEvent]:
        """
        Process an incoming security event through appropriate detectors.
        
        Event types:
        - kerberos_tgs_req: TGS request
        - kerberos_as_rep: AS-REP response  
        - kerberos_ticket: Ticket creation/use
        - ldap_query: LDAP search/modify
        - ad_replication: Replication event
        - ntlm_auth: NTLM authentication
        - process_access: Process memory access
        """
        self.metrics["events_analyzed"] += 1
        
        threat = None
        
        try:
            if event_type == "kerberos_tgs_req":
                threat = self.kerberos_detector.analyze_tgs_request(event_data)
            
            elif event_type == "kerberos_as_rep":
                threat = self.kerberos_detector.analyze_as_rep(event_data)
            
            elif event_type == "kerberos_ticket":
                ticket = self._parse_ticket(event_data)
                if ticket:
                    threat = self.kerberos_detector.analyze_ticket(ticket)
            
            elif event_type == "ldap_query":
                query = self._parse_ldap_query(event_data)
                if query:
                    threat = self.ldap_detector.analyze_query(query)
            
            elif event_type == "ad_replication":
                repl_event = self._parse_replication_event(event_data)
                if repl_event:
                    threat = self.ad_replication_monitor.analyze_replication_event(repl_event)
            
            elif event_type == "ntlm_auth":
                threat = self.credential_analyzer.analyze_ntlm_auth(event_data)
            
            elif event_type == "process_access":
                threat = self.credential_analyzer.detect_credential_dumping(event_data)
            
            elif event_type == "dc_registration":
                threat = self.ad_replication_monitor.detect_dcshadow(event_data)
            
            elif event_type == "skeleton_key_indicator":
                threat = self.kerberos_detector.detect_skeleton_key(event_data)
            
            elif event_type == "ldap_modification":
                threat = self.ldap_detector.detect_ldap_relay(event_data)
            
            elif event_type == "ticket_reuse":
                threat = self.credential_analyzer.analyze_ticket_reuse(event_data)
        
        except Exception as e:
            logger.error(f"Error processing {event_type} event: {e}")
            return None
        
        if threat:
            self._handle_threat(threat)
        
        return threat
    
    def _handle_threat(self, threat: IdentityThreatEvent):
        """Handle a detected threat"""
        # Store threat
        self.active_threats[threat.event_id] = threat
        self.threat_history.append(threat)
        self.metrics["threats_detected"] += 1
        
        if threat.severity == ThreatSeverity.CRITICAL:
            self.metrics["critical_threats"] += 1
        
        # Update risk scores
        self._update_risk_scores(threat)
        
        # Log threat
        logger.warning(
            f"IDENTITY THREAT: {threat.attack_type} | "
            f"Severity: {threat.severity.value} | "
            f"Confidence: {threat.confidence:.1%} | "
            f"Target: {threat.target_principal} | "
            f"Source: {threat.source_ip}"
        )
        
        # Check for auto-response
        if threat.confidence >= self.config["auto_response_threshold"]:
            self._trigger_auto_response(threat)
    
    def _update_risk_scores(self, threat: IdentityThreatEvent):
        """Update cumulative risk scores"""
        severity_weights = {
            ThreatSeverity.CRITICAL: 1.0,
            ThreatSeverity.HIGH: 0.7,
            ThreatSeverity.MEDIUM: 0.4,
            ThreatSeverity.LOW: 0.2,
            ThreatSeverity.INFO: 0.05
        }
        
        weight = severity_weights.get(threat.severity, 0.1)
        score_increment = weight * threat.confidence
        
        self.entity_threat_scores[threat.target_principal] += score_increment
        self.ip_threat_scores[threat.source_ip] += score_increment
    
    def _trigger_auto_response(self, threat: IdentityThreatEvent):
        """Trigger automated response for high-confidence threats"""
        self.metrics["auto_responses_triggered"] += 1
        
        logger.critical(
            f"AUTO-RESPONSE TRIGGERED for {threat.attack_type}: "
            f"Recommendations: {threat.recommendations}"
        )
        
        # In production, this would integrate with SOAR
        # For now, log the recommended actions
        
    def _parse_ticket(self, event_data: Dict[str, Any]) -> Optional[KerberosTicketInfo]:
        """Parse event data into KerberosTicketInfo"""
        try:
            return KerberosTicketInfo(
                ticket_id=event_data.get("ticket_id", secrets.token_hex(8)),
                client_principal=event_data.get("client_principal", "unknown"),
                server_principal=event_data.get("server_principal", "unknown"),
                encryption_type=event_data.get("encryption_type", 0),
                ticket_flags=event_data.get("ticket_flags", 0),
                auth_time=datetime.fromisoformat(event_data.get("auth_time", datetime.now(timezone.utc).isoformat())),
                start_time=datetime.fromisoformat(event_data.get("start_time", datetime.now(timezone.utc).isoformat())),
                end_time=datetime.fromisoformat(event_data.get("end_time", (datetime.now(timezone.utc) + timedelta(hours=10)).isoformat())),
                renew_until=datetime.fromisoformat(event_data["renew_until"]) if event_data.get("renew_until") else None,
                client_addresses=event_data.get("client_addresses", []),
                realm=event_data.get("realm", "UNKNOWN")
            )
        except Exception as e:
            logger.error(f"Failed to parse ticket: {e}")
            return None
    
    def _parse_ldap_query(self, event_data: Dict[str, Any]) -> Optional[LDAPQueryInfo]:
        """Parse event data into LDAPQueryInfo"""
        try:
            return LDAPQueryInfo(
                query_id=event_data.get("query_id", secrets.token_hex(8)),
                timestamp=datetime.fromisoformat(event_data.get("timestamp", datetime.now(timezone.utc).isoformat())),
                source_ip=event_data.get("source_ip", "unknown"),
                bind_dn=event_data.get("bind_dn", "anonymous"),
                operation=LDAPOperation(event_data.get("operation", "search")),
                base_dn=event_data.get("base_dn", ""),
                scope=event_data.get("scope", 2),
                filter_str=event_data.get("filter", ""),
                attributes=event_data.get("attributes", []),
                result_count=event_data.get("result_count", 0),
                response_time_ms=event_data.get("response_time_ms", 0.0)
            )
        except Exception as e:
            logger.error(f"Failed to parse LDAP query: {e}")
            return None
    
    def _parse_replication_event(self, event_data: Dict[str, Any]) -> Optional[ADReplicationEvent]:
        """Parse event data into ADReplicationEvent"""
        try:
            source_ip = event_data.get("source_ip", "unknown")
            is_legitimate = (
                source_ip in self.ad_replication_monitor.config["known_domain_controllers"] or
                event_data.get("source_dc", "").lower() in self.ad_replication_monitor.config["known_domain_controllers"]
            )
            
            return ADReplicationEvent(
                event_id=event_data.get("event_id", secrets.token_hex(8)),
                timestamp=datetime.fromisoformat(event_data.get("timestamp", datetime.now(timezone.utc).isoformat())),
                source_dc=event_data.get("source_dc", "unknown"),
                destination_dc=event_data.get("destination_dc", "unknown"),
                replication_type=event_data.get("replication_type", "inbound"),
                naming_context=event_data.get("naming_context", ""),
                object_count=event_data.get("object_count", 0),
                attributes_replicated=event_data.get("attributes_replicated", []),
                source_ip=source_ip,
                is_legitimate_dc=is_legitimate
            )
        except Exception as e:
            logger.error(f"Failed to parse replication event: {e}")
            return None
    
    def get_entity_risk(self, principal: str) -> Dict[str, Any]:
        """Get risk assessment for an entity"""
        risk_score = self.entity_threat_scores.get(principal, 0.0)
        
        # Get recent threats for this entity
        recent_threats = [
            t for t in self.threat_history
            if t.target_principal == principal
            and (datetime.now(timezone.utc) - t.timestamp).total_seconds() < 3600
        ]
        
        return {
            "principal": principal,
            "risk_score": min(1.0, risk_score),
            "risk_level": self._score_to_level(risk_score),
            "recent_threats": len(recent_threats),
            "threat_types": list({t.attack_type for t in recent_threats})
        }
    
    def get_ip_risk(self, ip: str) -> Dict[str, Any]:
        """Get risk assessment for an IP"""
        risk_score = self.ip_threat_scores.get(ip, 0.0)
        
        recent_threats = [
            t for t in self.threat_history
            if t.source_ip == ip
            and (datetime.now(timezone.utc) - t.timestamp).total_seconds() < 3600
        ]
        
        return {
            "ip": ip,
            "risk_score": min(1.0, risk_score),
            "risk_level": self._score_to_level(risk_score),
            "recent_threats": len(recent_threats),
            "threat_types": list({t.attack_type for t in recent_threats})
        }
    
    def _score_to_level(self, score: float) -> str:
        """Convert numeric score to risk level"""
        if score >= 0.8:
            return "critical"
        elif score >= 0.6:
            return "high"
        elif score >= 0.4:
            return "medium"
        elif score >= 0.2:
            return "low"
        return "minimal"
    
    def get_active_threats(self, severity: Optional[ThreatSeverity] = None) -> List[Dict[str, Any]]:
        """Get active threats, optionally filtered by severity"""
        threats = list(self.active_threats.values())
        
        if severity:
            threats = [t for t in threats if t.severity == severity]
        
        return [asdict(t) for t in threats]
    
    def get_threat_summary(self) -> Dict[str, Any]:
        """Get summary of identity threat landscape"""
        now = datetime.now(timezone.utc)
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(days=1)
        
        threats_last_hour = [t for t in self.threat_history if t.timestamp > hour_ago]
        threats_last_day = [t for t in self.threat_history if t.timestamp > day_ago]
        
        return {
            "metrics": self.metrics,
            "active_threats": len(self.active_threats),
            "threats_last_hour": len(threats_last_hour),
            "threats_last_day": len(threats_last_day),
            "severity_distribution": {
                s.value: len([t for t in threats_last_day if t.severity == s])
                for s in ThreatSeverity
            },
            "attack_type_distribution": {
                attack_type: len([t for t in threats_last_day if t.attack_type == attack_type])
                for attack_type in {t.attack_type for t in threats_last_day}
            },
            "top_targeted_entities": sorted(
                self.entity_threat_scores.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10],
            "top_source_ips": sorted(
                self.ip_threat_scores.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]
        }
    
    def register_known_dc(self, dc_info: Dict[str, str]):
        """Register a known Domain Controller"""
        hostname = dc_info.get("hostname", "")
        ip = dc_info.get("ip", "")
        
        if hostname:
            self.ad_replication_monitor.add_known_dc(hostname, ip)
            self.kerberos_detector.config["known_dcs"].add(hostname.lower())
        if ip:
            self.kerberos_detector.config["known_dcs"].add(ip)
        
        logger.info(f"Registered known DC: {hostname} ({ip})")
    
    def clear_threat(self, event_id: str) -> bool:
        """Clear a threat from active list"""
        if event_id in self.active_threats:
            del self.active_threats[event_id]
            return True
        return False
    
    def process_windows_event(self, event_id: int, event_data: Dict[str, Any]) -> List[IdentityThreatEvent]:
        """
        Process a Windows Security Event through all applicable detectors.
        
        Dispatches to:
        - KerberosAttackDetector for Kerberos events (4768, 4769, 4771, 4770)
        - LDAPAttackDetector for LDAP events (2889, 3039)
        - ADReplicationMonitor for replication events (4662, 5136)
        - CredentialThreatAnalyzer for auth events (4624, 4625, 4648, 4776)
        
        Returns list of all threats detected from the event.
        """
        threats = []
        
        # Kerberos events
        kerberos_events = [
            WindowsSecurityEventID.KERBEROS_TGT_REQUEST,
            WindowsSecurityEventID.KERBEROS_SERVICE_TICKET,
            WindowsSecurityEventID.KERBEROS_PREAUTH_FAILED,
            WindowsSecurityEventID.KERBEROS_RENEWAL
        ]
        
        if event_id in kerberos_events:
            threat = self.kerberos_detector.analyze_windows_event(event_id, event_data)
            if threat:
                threats.append(threat)
        
        # LDAP events
        ldap_events = [
            WindowsSecurityEventID.LDAP_UNSIGNED_BIND
        ]
        
        if event_id in ldap_events:
            threat = self.ldap_detector.track_windows_event(event_id, event_data)
            if threat:
                threats.append(threat)
        
        # AD Replication events
        replication_events = [
            WindowsSecurityEventID.DIRECTORY_SERVICE_ACCESS,
            WindowsSecurityEventID.DIRECTORY_OBJECT_MODIFIED
        ]
        
        if event_id in replication_events:
            threat = self.ad_replication_monitor.analyze_windows_event(event_id, event_data)
            if threat:
                threats.append(threat)
        
        # Authentication events
        auth_events = [
            WindowsSecurityEventID.LOGON_SUCCESS,
            WindowsSecurityEventID.LOGON_FAILED,
            WindowsSecurityEventID.EXPLICIT_CREDENTIALS,
            WindowsSecurityEventID.NTLM_AUTHENTICATION
        ]
        
        if event_id in auth_events:
            threat = self.credential_analyzer.analyze_windows_event(event_id, event_data)
            if threat:
                threats.append(threat)
        
        # Handle all detected threats
        for threat in threats:
            self._handle_threat(threat)
        
        return threats
    
    def correlate_threats(self, time_window_minutes: int = 15) -> List[Dict[str, Any]]:
        """
        Correlate threats to identify attack chains.
        
        Looks for related threats across detectors that may indicate
        a coordinated attack campaign.
        """
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(minutes=time_window_minutes)
        
        recent_threats = [
            t for t in self.threat_history
            if t.timestamp > window_start
        ]
        
        # Group by source IP
        by_source: Dict[str, List[IdentityThreatEvent]] = defaultdict(list)
        for t in recent_threats:
            by_source[t.source_ip].append(t)
        
        # Group by target
        by_target: Dict[str, List[IdentityThreatEvent]] = defaultdict(list)
        for t in recent_threats:
            by_target[t.target_principal].append(t)
        
        correlations = []
        
        # Detect attack chains from same source
        for source_ip, threats in by_source.items():
            if len(threats) >= 2:
                attack_types = list({t.attack_type for t in threats})
                
                # Known attack chains
                attack_chains = [
                    {"chain": ["ldap_reconnaissance", "kerberoasting"], "name": "Pre-Kerberoasting Recon"},
                    {"chain": ["password_spray_ldap", "kerberoasting"], "name": "Spray-then-Kerberoast"},
                    {"chain": ["asrep_roasting", "kerberoasting"], "name": "Roasting Campaign"},
                    {"chain": ["dcsync", "golden_ticket"], "name": "DCSync-to-Golden"},
                    {"chain": ["coerced_auth_petitpotam", "ntlm_relay"], "name": "PetitPotam Attack Chain"},
                    {"chain": ["shadow_credentials", "pass_the_ticket"], "name": "Shadow Credentials Attack"},
                    {"chain": ["rbcd_abuse", "pass_the_ticket"], "name": "RBCD Privilege Escalation"},
                ]
                
                for chain_def in attack_chains:
                    if all(at in attack_types for at in chain_def["chain"]):
                        correlations.append({
                            "correlation_id": f"chain_{secrets.token_hex(4)}",
                            "name": chain_def["name"],
                            "source_ip": source_ip,
                            "attack_types": attack_types,
                            "threat_count": len(threats),
                            "severity": "critical",
                            "threats": [t.event_id for t in threats],
                            "first_seen": min(t.timestamp for t in threats).isoformat(),
                            "last_seen": max(t.timestamp for t in threats).isoformat()
                        })
        
        # Detect coordinated attacks on same target from multiple sources
        for target, threats in by_target.items():
            unique_sources = {t.source_ip for t in threats}
            if len(unique_sources) >= 3 and len(threats) >= 5:
                correlations.append({
                    "correlation_id": f"coord_{secrets.token_hex(4)}",
                    "name": "Coordinated Attack Campaign",
                    "target": target,
                    "source_ips": list(unique_sources),
                    "attack_types": list({t.attack_type for t in threats}),
                    "threat_count": len(threats),
                    "severity": "critical",
                    "threats": [t.event_id for t in threats],
                    "first_seen": min(t.timestamp for t in threats).isoformat(),
                    "last_seen": max(t.timestamp for t in threats).isoformat()
                })
        
        return correlations
    
    def get_mitre_coverage(self) -> Dict[str, Any]:
        """
        Get MITRE ATT&CK technique coverage report.
        
        Shows which techniques have been detected and their frequency.
        """
        technique_counts: Dict[str, int] = defaultdict(int)
        technique_severities: Dict[str, List[str]] = defaultdict(list)
        
        for threat in self.threat_history:
            for technique in threat.mitre_techniques:
                technique_counts[technique] += 1
                technique_severities[technique].append(threat.severity.value)
        
        coverage = {
            "total_techniques_seen": len(technique_counts),
            "techniques": [
                {
                    "technique_id": tid,
                    "detection_count": count,
                    "max_severity": max(technique_severities[tid]) if technique_severities[tid] else "unknown"
                }
                for tid, count in sorted(technique_counts.items(), key=lambda x: x[1], reverse=True)
            ],
            "coverage_summary": {
                "credential_access": len([t for t in technique_counts if "T1003" in t or "T1558" in t or "T1555" in t]),
                "persistence": len([t for t in technique_counts if "T1078" in t or "T1556" in t]),
                "lateral_movement": len([t for t in technique_counts if "T1550" in t or "T1557" in t]),
                "discovery": len([t for t in technique_counts if "T1087" in t or "T1069" in t]),
            }
        }
        
        return coverage
    
    def export_threats(self, 
                       format: str = "json",
                       since: Optional[datetime] = None,
                       severity_filter: Optional[List[str]] = None) -> str:
        """
        Export threat data for reporting or SIEM integration.
        
        Formats: json, csv, cef (Common Event Format)
        """
        threats = self.threat_history
        
        if since:
            threats = [t for t in threats if t.timestamp > since]
        
        if severity_filter:
            threats = [t for t in threats if t.severity.value in severity_filter]
        
        if format == "json":
            import json
            return json.dumps([asdict(t) for t in threats], default=str, indent=2)
        
        elif format == "csv":
            lines = ["event_id,timestamp,attack_type,severity,confidence,source_ip,target_principal,description"]
            for t in threats:
                lines.append(
                    f'"{t.event_id}","{t.timestamp.isoformat()}","{t.attack_type}",'
                    f'"{t.severity.value}",{t.confidence:.2f},"{t.source_ip}",'
                    f'"{t.target_principal}","{t.description.replace(",", ";")}"'
                )
            return "\n".join(lines)
        
        elif format == "cef":
            # Common Event Format for SIEM integration
            cef_lines = []
            for t in threats:
                severity_map = {"critical": 10, "high": 7, "medium": 4, "low": 2, "info": 1}
                cef_severity = severity_map.get(t.severity.value, 5)
                
                cef_line = (
                    f"CEF:0|Seraph|IdentityProtection|2.0|{t.attack_type}|"
                    f"{t.description}|{cef_severity}|"
                    f"src={t.source_ip} duser={t.target_principal} "
                    f"cs1={','.join(t.mitre_techniques)} cs1Label=MITRETechniques "
                    f"cfp1={t.confidence:.2f} cfp1Label=Confidence "
                    f"rt={t.timestamp.strftime('%b %d %Y %H:%M:%S')}"
                )
                cef_lines.append(cef_line)
            return "\n".join(cef_lines)
        
        else:
            raise ValueError(f"Unknown export format: {format}")
    
    def get_detector_health(self) -> Dict[str, Any]:
        """
        Get health status of all detectors.
        """
        return {
            "engine_status": "healthy",
            "uptime_seconds": (datetime.now(timezone.utc) - self.threat_history[0].timestamp).total_seconds() 
                             if self.threat_history else 0,
            "detectors": {
                "kerberos": {
                    "status": "healthy",
                    "stats": self.kerberos_detector.get_statistics()
                },
                "ldap": {
                    "status": "healthy",
                    "stats": self.ldap_detector.get_statistics()
                },
                "ad_replication": {
                    "status": "healthy",
                    "stats": self.ad_replication_monitor.get_statistics()
                },
                "credential": {
                    "status": "healthy",
                    "stats": self.credential_analyzer.get_statistics()
                }
            },
            "global_metrics": self.metrics,
            "memory_usage": {
                "active_threats": len(self.active_threats),
                "threat_history": len(self.threat_history),
                "entity_scores": len(self.entity_threat_scores),
                "ip_scores": len(self.ip_threat_scores)
            }
        }
    
    def configure(self, config: Dict[str, Any]):
        """
        Update engine configuration.
        """
        # Update engine config
        for key, value in config.items():
            if key in self.config:
                self.config[key] = value
                logger.info(f"Updated config: {key} = {value}")
        
        # Propagate to detectors if applicable
        detector_configs = {
            "kerberos": self.kerberos_detector.config,
            "ldap": self.ldap_detector.config,
            "ad_replication": self.ad_replication_monitor.config,
            "credential": self.credential_analyzer.config
        }
        
        for detector_name, detector_config in detector_configs.items():
            detector_prefix = f"{detector_name}_"
            for key, value in config.items():
                if key.startswith(detector_prefix):
                    config_key = key[len(detector_prefix):]
                    if config_key in detector_config:
                        detector_config[config_key] = value
                        logger.info(f"Updated {detector_name} config: {config_key} = {value}")
    
    def clear_all_state(self):
        """
        Clear all state from engine and detectors.
        Use with caution - clears threat history!
        """
        self.active_threats.clear()
        self.threat_history.clear()
        self.entity_threat_scores.clear()
        self.ip_threat_scores.clear()
        
        self.kerberos_detector.clear_state()
        self.ldap_detector.clear_state()
        self.ad_replication_monitor.clear_state()
        self.credential_analyzer.clear_state()
        
        # Reset metrics
        self.metrics = {
            "events_analyzed": 0,
            "threats_detected": 0,
            "critical_threats": 0,
            "auto_responses_triggered": 0
        }
        
        logger.warning("All identity protection state cleared")
    
    def decay_risk_scores(self):
        """
        Apply time-based decay to risk scores.
        Should be called periodically (e.g., hourly).
        """
        decay_factor = 0.9  # 10% decay per call
        
        for principal in list(self.entity_threat_scores.keys()):
            self.entity_threat_scores[principal] *= decay_factor
            if self.entity_threat_scores[principal] < 0.01:
                del self.entity_threat_scores[principal]
        
        for ip in list(self.ip_threat_scores.keys()):
            self.ip_threat_scores[ip] *= decay_factor
            if self.ip_threat_scores[ip] < 0.01:
                del self.ip_threat_scores[ip]
        
        logger.debug("Applied risk score decay")


# Global singleton
identity_protection_engine = IdentityProtectionEngine()


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def get_identity_protection_engine() -> IdentityProtectionEngine:
    """Get the global identity protection engine instance"""
    return identity_protection_engine


def analyze_security_event(event_type: str, event_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Convenience function to analyze a security event.
    
    Returns threat details as dict if threat detected, else None.
    """
    engine = get_identity_protection_engine()
    threat = engine.process_event(event_type, event_data)
    return asdict(threat) if threat else None
