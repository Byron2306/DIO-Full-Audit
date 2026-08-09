import logging
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger("arda.lawful_defense")

class AttackCategory(Enum):
    KERBEROS = "kerberos"
    LDAP = "ldap"
    IDENTITY_THEFT = "identity_theft"
    PRIVILEGE_ESCALATION = "privilege_escalation"

class ThreatSeverity(Enum):
     CRITICAL = "critical"
     HIGH = "high"
     MEDIUM = "medium"
     LOW = "low"

@dataclass
class IdentityThreatEvent:
    event_id: str
    timestamp: datetime
    category: AttackCategory
    attack_type: str
    severity: ThreatSeverity
    source_ip: str
    target_principal: str
    description: str
    mitre_techniques: List[str]
    confidence: float

class IdentitySentry:
    """
    The Active Identity Sentry (Ported from Metatron v2.0.0).
    Monitors protocol-level identity attacks.
    """
    def __init__(self):
        self.config = {
            "kerberoast_tgs_threshold": 5,      # TGS requests per minute
            "ticket_lifetime_max_hours": 10,    # Normal TGT lifetime
        }
        self.tgs_history: Dict[str, List[datetime]] = {} # user -> [timestamps]

    def analyze_kerberos_requests(self, user: str, source_ip: str, tgs_count: int) -> Optional[IdentityThreatEvent]:
        """Detects Kerberoasting behavior."""
        if tgs_count >= self.config["kerberoast_tgs_threshold"]:
            return IdentityThreatEvent(
                event_id=f"IDS-{secrets.token_hex(4)}",
                timestamp=datetime.now(timezone.utc),
                category=AttackCategory.KERBEROS,
                attack_type="kerberoasting",
                severity=ThreatSeverity.HIGH,
                source_ip=source_ip,
                target_principal=user,
                description=f"High TGS request volume ({tgs_count}) from {source_ip}. Potential Kerberoasting.",
                mitre_techniques=["T1558.003"],
                confidence=0.85
            )
        return None

    def detect_golden_ticket(self, user: str, lifetime_hours: float) -> Optional[IdentityThreatEvent]:
        """Detects Golden Ticket indicators (abnormal lifetime)."""
        if lifetime_hours > self.config["ticket_lifetime_max_hours"]:
             return IdentityThreatEvent(
                event_id=f"IDS-{secrets.token_hex(4)}",
                timestamp=datetime.now(timezone.utc),
                category=AttackCategory.KERBEROS,
                attack_type="golden_ticket",
                severity=ThreatSeverity.CRITICAL,
                source_ip="internal",
                target_principal=user,
                description=f"Abnormal TGT lifetime: {lifetime_hours} hours. Arda Policy is {self.config['ticket_lifetime_max_hours']}h.",
                mitre_techniques=["T1558.001"],
                confidence=0.9
            )
        return None

_sentry = IdentitySentry()
def get_identity_sentry(): return _sentry
