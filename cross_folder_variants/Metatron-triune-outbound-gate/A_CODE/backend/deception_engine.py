"""
Seraph Deception Engine
========================
Advanced deception and misdirection system integrating:

1. Pebbles (Campaign Tracking) - Correlate attacks across sessions/IPs via behavioral fingerprints
2. Mystique (Adaptive Deception) - Self-tuning deception parameters based on attacker behavior
3. Stonewall (Progressive Escalation) - Automated escalation for persistent attackers
4. Risk Scoring - Behavioral fingerprinting and weighted threat scoring

Inspired by CAS Shield Sentinel defensive architecture.
Integrates with: honey_tokens.py, ransomware_protection.py, threat_response.py, soar_engine.py

This is Seraph's DIFFERENTIATOR - the ability to deceive, misdirect, and outwit both
human attackers and rogue AI agents.
"""

import os
import json
import time
import hashlib
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple, Set, Callable
from dataclasses import dataclass, field, asdict
from collections import defaultdict
from enum import Enum
from pathlib import Path
from runtime_paths import ensure_data_dir

logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================

DATA_DIR = ensure_data_dir("deception")


class DeceptionConfig:
    """Configuration for the deception engine"""
    
    def __init__(self):
        # Pebbles (Campaign Tracking)
        self.correlation_enabled = os.environ.get("CORRELATION_ENABLED", "true").lower() == "true"
        self.campaign_window_minutes = int(os.environ.get("DECEPTION_CAMPAIGN_WINDOW", "120"))
        self.campaign_salt = os.environ.get("DECEPTION_CAMPAIGN_SALT", "SERAPH_DECEPTION_SALT")
        self.fingerprint_fields = ["user_agent", "accept", "accept_language", "accept_encoding"]
        
        # Mystique (Adaptive Deception)
        self.mystique_enabled = os.environ.get("MYSTIQUE_ENABLED", "true").lower() == "true"
        self.adapt_every_n_events = int(os.environ.get("MYSTIQUE_ADAPT_N", "25"))
        self.campaign_promote_threshold = int(os.environ.get("MYSTIQUE_PROMOTE_THRESHOLD", "30"))
        self.max_friction_multiplier = float(os.environ.get("MYSTIQUE_MAX_FRICTION", "2.5"))
        self.max_tarpit_multiplier = float(os.environ.get("MYSTIQUE_MAX_TARPIT", "2.0"))
        self.min_sink_score_floor = int(os.environ.get("MYSTIQUE_SINK_FLOOR", "60"))
        
        # Stonewall (Progressive Escalation)
        self.stonewall_enabled = os.environ.get("STONEWALL_ENABLED", "true").lower() == "true"
        self.repeat_threshold = int(os.environ.get("STONEWALL_REPEAT_THRESHOLD", "20"))
        self.ban_seconds_first = int(os.environ.get("STONEWALL_BAN_FIRST", "1800"))
        self.ban_seconds_repeat = int(os.environ.get("STONEWALL_BAN_REPEAT", "21600"))
        self.trap_hits_to_blocklist = int(os.environ.get("STONEWALL_TRAP_BLOCKLIST", "50"))
        
        # Risk Scoring
        self.scoring_weights = {
            "missing_headers": 15,
            "bad_user_agent": 20,
            "rate_pressure": 10,
            "suspicious_path": 25,
            "trap_interaction": 30,
            "decoy_touched": 35,
            "ai_behavior": 25,
            "known_bad_fingerprint": 40,
            "repeated_failures": 15,
        }
        
        # Friction
        self.friction_enabled = os.environ.get("FRICTION_ENABLED", "true").lower() == "true"
        self.friction_base_delay_ms = int(os.environ.get("FRICTION_BASE_DELAY", "500"))
        self.friction_max_delay_ms = int(os.environ.get("FRICTION_MAX_DELAY", "5000"))
        self.friction_challenge_score = int(os.environ.get("FRICTION_CHALLENGE_SCORE", "40"))
        
        # Trap Sink
        self.trap_sink_enabled = os.environ.get("TRAP_SINK_ENABLED", "true").lower() == "true"
        self.trap_sink_min_score = int(os.environ.get("TRAP_SINK_MIN_SCORE", "70"))
        self.trap_tarpit_delay_ms = int(os.environ.get("TRAP_TARPIT_DELAY", "3000"))

        # Disinformation (DISINFORMATION route)
        self.disinformation_enabled = os.environ.get("DISINFORMATION_ENABLED", "true").lower() == "true"
        self.disinformation_min_score = int(os.environ.get("DISINFORMATION_MIN_SCORE", "50"))
        
        # Trap paths that indicate malicious behavior
        self.trap_paths_prefix = [
            "/.env", "/.git", "/wp-admin", "/wp-login", "/phpmyadmin",
            "/admin", "/.aws", "/.ssh", "/config", "/backup",
            "/etc/passwd", "/etc/shadow", "/.htaccess", "/web.config"
        ]

        # Logic-budget exhaustion controller (CBR/TBCR/CDI + agenticity signals)
        self.logic_budget_controller_enabled = (
            os.environ.get("LOGIC_BUDGET_CONTROLLER_ENABLED", "true").lower() == "true"
        )
        self.logic_budget_target_cbr = float(os.environ.get("LOGIC_BUDGET_TARGET_CBR", "800.0"))
        self.logic_budget_target_tbcr = float(os.environ.get("LOGIC_BUDGET_TARGET_TBCR", "12.0"))
        self.logic_budget_target_cdi = float(os.environ.get("LOGIC_BUDGET_TARGET_CDI", "0.35"))
        self.logic_budget_force_trap_threshold = float(
            os.environ.get("LOGIC_BUDGET_FORCE_TRAP_THRESHOLD", "0.92")
        )
        self.logic_budget_weights = {
            "cbr": float(os.environ.get("LOGIC_BUDGET_WEIGHT_CBR", "0.30")),
            "tbcr": float(os.environ.get("LOGIC_BUDGET_WEIGHT_TBCR", "0.25")),
            "cdi": float(os.environ.get("LOGIC_BUDGET_WEIGHT_CDI", "0.25")),
            "agenticity": float(os.environ.get("LOGIC_BUDGET_WEIGHT_AGENTICITY", "0.20")),
        }


config = DeceptionConfig()


# =============================================================================
# DATA MODELS
# =============================================================================

class RouteDecision(str, Enum):
    """Routing decisions for incoming requests/sessions"""
    PASS_THROUGH = "pass_through"       # Allow normally
    FRICTION = "friction"               # Delay then allow
    TRAP_SINK = "trap_sink"             # Tarpit and deny
    HONEYPOT = "honeypot"               # Route to full honeypot
    DISINFORMATION = "disinformation"   # Feed false data


class EscalationLevel(str, Enum):
    """Stonewall escalation levels"""
    NONE = "none"
    WARNED = "warned"
    THROTTLED = "throttled"
    SOFT_BANNED = "soft_banned"
    HARD_BANNED = "hard_banned"
    BLOCKLISTED = "blocklisted"


@dataclass
class BehavioralFingerprint:
    """Fingerprint of attacker behavior for correlation"""
    fingerprint_id: str
    header_hash: str
    timing_signature: str
    tool_patterns: List[str] = field(default_factory=list)
    command_velocity: float = 0.0
    first_seen: str = ""
    last_seen: str = ""
    total_events: int = 0
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class AttackCampaign:
    """Correlated attack campaign (Pebbles)"""
    campaign_id: str
    fingerprint_ids: Set[str] = field(default_factory=set)
    source_ips: Set[str] = field(default_factory=set)
    session_ids: Set[str] = field(default_factory=set)
    first_seen: str = ""
    last_seen: str = ""
    
    # Event counters
    total_events: int = 0
    trap_events: int = 0
    friction_events: int = 0
    pass_events: int = 0
    decoy_interactions: int = 0
    disinfo_events: int = 0        # times this campaign was served disinformation
    
    # Mystique adaptive parameters
    friction_multiplier: float = 1.0
    tarpit_multiplier: float = 1.0
    sink_score_override: Optional[int] = None
    
    # Escalation state
    escalation_level: EscalationLevel = EscalationLevel.NONE
    ban_until: Optional[float] = None
    
    def to_dict(self) -> Dict:
        d = asdict(self)
        d["fingerprint_ids"] = list(self.fingerprint_ids)
        d["source_ips"] = list(self.source_ips)
        d["session_ids"] = list(self.session_ids)
        d["escalation_level"] = self.escalation_level.value
        return d


@dataclass
class DeceptionEvent:
    """Record of a deception system event"""
    event_id: str
    timestamp: str
    event_type: str  # trap_triggered, decoy_accessed, friction_applied, etc.
    campaign_id: Optional[str]
    fingerprint_id: Optional[str]
    source_ip: str
    session_id: Optional[str]
    route_decision: RouteDecision
    risk_score: int
    risk_reasons: List[str]
    delay_applied_ms: int = 0
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        d = asdict(self)
        d["route_decision"] = self.route_decision.value
        return d


@dataclass
class RiskAssessment:
    """Risk assessment result"""
    score: int
    reasons: List[str]
    route: RouteDecision
    delay_ms: int = 0
    campaign_id: Optional[str] = None
    fingerprint_id: Optional[str] = None
    escalation_level: EscalationLevel = EscalationLevel.NONE


# =============================================================================
# TOKEN BUCKET RATE LIMITER
# =============================================================================

class TokenBucket:
    """Token bucket for rate limiting"""
    
    def __init__(self, rate_per_sec: float, burst: int):
        self.rate = float(rate_per_sec)
        self.capacity = int(burst)
        self.tokens = float(burst)
        self.last_time = time.time()
    
    def take(self, n: float = 1.0) -> bool:
        """Try to take n tokens. Returns True if successful."""
        now = time.time()
        elapsed = now - self.last_time
        self.last_time = now
        
        # Refill tokens
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        
        if self.tokens >= n:
            self.tokens -= n
            return True
        return False


class RateLimiter:
    """Rate limiter with per-IP and per-IP+path buckets"""
    
    def __init__(self, per_ip_rps: float = 10.0, per_ip_burst: int = 50,
                 per_ip_path_rps: float = 2.0, per_ip_path_burst: int = 10):
        self.per_ip: Dict[str, TokenBucket] = {}
        self.per_ip_path: Dict[str, TokenBucket] = {}
        self.per_ip_rps = per_ip_rps
        self.per_ip_burst = per_ip_burst
        self.per_ip_path_rps = per_ip_path_rps
        self.per_ip_path_burst = per_ip_path_burst
    
    def _get_bucket(self, store: Dict[str, TokenBucket], key: str, 
                    rps: float, burst: int) -> TokenBucket:
        if key not in store:
            store[key] = TokenBucket(rps, burst)
        return store[key]
    
    def check(self, ip: str, path: str = "/") -> Tuple[bool, bool]:
        """
        Check rate limits. Returns (rate_ok, under_pressure).
        under_pressure indicates approaching limits.
        """
        ip_bucket = self._get_bucket(self.per_ip, ip, self.per_ip_rps, self.per_ip_burst)
        path_bucket = self._get_bucket(
            self.per_ip_path, f"{ip}|{path}", 
            self.per_ip_path_rps, self.per_ip_path_burst
        )
        
        ip_ok = ip_bucket.take(1.0)
        path_ok = path_bucket.take(1.0)
        
        # Under pressure if tokens are low
        under_pressure = (
            ip_bucket.tokens < self.per_ip_burst * 0.3 or
            path_bucket.tokens < self.per_ip_path_burst * 0.3
        )
        
        return (ip_ok and path_ok, under_pressure)
    
    def cleanup(self, max_age_seconds: int = 3600):
        """Clean up old buckets"""
        now = time.time()
        cutoff = now - max_age_seconds
        
        self.per_ip = {k: v for k, v in self.per_ip.items() if v.last_time > cutoff}
        self.per_ip_path = {k: v for k, v in self.per_ip_path.items() if v.last_time > cutoff}


# =============================================================================
# SERAPH DECEPTION ENGINE
# =============================================================================

class DeceptionEngine:
    """
    Core deception engine implementing Pebbles, Mystique, and Stonewall.
    
    This is Seraph's key differentiator - intelligent deception that adapts
    to attacker behavior and correlates attacks across sessions.
    """
    
    def __init__(self):
        self.db = None
        self.config = config
        
        # Campaign tracking (Pebbles)
        self.campaigns: Dict[str, AttackCampaign] = {}
        self.fingerprints: Dict[str, BehavioralFingerprint] = {}
        self.campaign_counts: Dict[str, int] = defaultdict(int)
        self.trap_hits: Dict[str, int] = defaultdict(int)
        
        # Rate limiting
        self.rate_limiter = RateLimiter()
        
        # Blocklists
        self.allowlist: Set[str] = set()
        self.blocklist: Set[str] = set()
        self.soft_bans: Dict[str, float] = {}  # IP -> ban_until timestamp
        
        # Event log
        self.events: List[DeceptionEvent] = []
        
        # Integration callbacks
        self._alert_callback: Optional[Callable] = None
        self._honey_token_manager = None
        self._ransomware_detector = None
        
        # Load persistent state
        self._load_state()
    
    def set_database(self, db):
        self.db = db
    
    def set_alert_callback(self, callback: Callable):
        self._alert_callback = callback
    
    def set_honey_token_manager(self, manager):
        self._honey_token_manager = manager
    
    def set_ransomware_detector(self, detector):
        self._ransomware_detector = detector
    
    # =========================================================================
    # PEBBLES - CAMPAIGN TRACKING
    # =========================================================================
    
    def _hash(self, s: str) -> str:
        """SHA256 hash, truncated"""
        return hashlib.sha256(s.encode("utf-8")).hexdigest()
    
    def compute_fingerprint(self, headers: Dict[str, str], 
                           timing_data: Optional[Dict] = None) -> BehavioralFingerprint:
        """
        Compute behavioral fingerprint from headers and timing data.
        Used to correlate attacks from the same tool/actor.
        """
        # Header-based fingerprint
        fields = self.config.fingerprint_fields
        header_str = "|".join([f"{k}:{headers.get(k, '')}" for k in fields])
        header_hash = self._hash(header_str)[:16]
        
        # Timing signature (if available)
        timing_sig = ""
        velocity = 0.0
        if timing_data:
            intervals = timing_data.get("command_intervals", [])
            if intervals:
                avg_interval = sum(intervals) / len(intervals)
                variance = sum((x - avg_interval) ** 2 for x in intervals) / len(intervals)
                timing_sig = f"{avg_interval:.2f}:{variance:.2f}"
                velocity = 1000.0 / max(avg_interval, 1)  # commands/sec
        
        fingerprint_id = self._hash(f"{header_hash}|{timing_sig}")[:16]
        
        # Get or create fingerprint
        if fingerprint_id in self.fingerprints:
            fp = self.fingerprints[fingerprint_id]
            fp.last_seen = datetime.now(timezone.utc).isoformat()
            fp.total_events += 1
        else:
            fp = BehavioralFingerprint(
                fingerprint_id=fingerprint_id,
                header_hash=header_hash,
                timing_signature=timing_sig,
                command_velocity=velocity,
                first_seen=datetime.now(timezone.utc).isoformat(),
                last_seen=datetime.now(timezone.utc).isoformat(),
                total_events=1
            )
            self.fingerprints[fingerprint_id] = fp
        
        return fp
    
    def compute_campaign_id(self, ip: str, fingerprint_id: str, path: str = "") -> str:
        """
        Compute campaign ID for correlating related attacks.
        Time-windowed to group attacks within campaign_window_minutes.
        """
        if not self.config.correlation_enabled:
            return self._hash(f"nocorr|{time.time_ns()}|{ip}|{fingerprint_id}|{path}")[:16]
        window_min = self.config.campaign_window_minutes
        time_bucket = int(time.time() // (window_min * 60))
        salt = self.config.campaign_salt
        
        campaign_str = f"{salt}|{time_bucket}|{ip}|{fingerprint_id}|{path[:24]}"
        return self._hash(campaign_str)[:16]
    
    def get_or_create_campaign(self, campaign_id: str, ip: Optional[str] = None,
                               fingerprint_id: Optional[str] = None, 
                               session_id: Optional[str] = None) -> AttackCampaign:
        """Get existing campaign or create new one"""
        if campaign_id not in self.campaigns:
            self.campaigns[campaign_id] = AttackCampaign(
                campaign_id=campaign_id,
                first_seen=datetime.now(timezone.utc).isoformat(),
                last_seen=datetime.now(timezone.utc).isoformat()
            )
        
        campaign = self.campaigns[campaign_id]
        campaign.last_seen = datetime.now(timezone.utc).isoformat()
        
        if ip:
            campaign.source_ips.add(ip)
        if fingerprint_id:
            campaign.fingerprint_ids.add(fingerprint_id)
        if session_id:
            campaign.session_ids.add(session_id)
        
        return campaign
    
    # =========================================================================
    # RISK SCORING
    # =========================================================================
    
    def assess_risk(self, 
                    ip: str,
                    path: str = "/",
                    headers: Optional[Dict[str, str]] = None,
                    session_id: Optional[str] = None,
                    timing_data: Optional[Dict] = None,
                    behavior_flags: Optional[Dict[str, Any]] = None) -> RiskAssessment:
        """
        Comprehensive risk assessment combining multiple signals.
        Returns routing decision with delay if applicable.
        """
        headers = headers or {}
        behavior_flags = behavior_flags or {}
        weights = self.config.scoring_weights
        
        score = 0
        reasons: List[str] = []
        
        # Check allowlist/blocklist first
        if ip in self.allowlist:
            return RiskAssessment(
                score=0, reasons=["allowlisted"], route=RouteDecision.PASS_THROUGH
            )
        
        if ip in self.blocklist:
            return RiskAssessment(
                score=100, reasons=["blocklisted"], route=RouteDecision.TRAP_SINK,
                delay_ms=self.config.trap_tarpit_delay_ms
            )
        
        # Check soft ban
        if ip in self.soft_bans:
            if time.time() < self.soft_bans[ip]:
                return RiskAssessment(
                    score=100, reasons=["soft_banned"], route=RouteDecision.TRAP_SINK,
                    delay_ms=self.config.trap_tarpit_delay_ms
                )
            else:
                del self.soft_bans[ip]
        
        # Compute fingerprint and campaign
        fingerprint = self.compute_fingerprint(headers, timing_data)
        campaign_id = self.compute_campaign_id(ip, fingerprint.fingerprint_id, path)
        campaign = self.get_or_create_campaign(campaign_id, ip, fingerprint.fingerprint_id, session_id)
        
        # Rate limiting check
        rate_ok, under_pressure = self.rate_limiter.check(ip, path)
        if not rate_ok:
            return RiskAssessment(
                score=100, reasons=["rate_limited"], route=RouteDecision.TRAP_SINK,
                delay_ms=self.config.trap_tarpit_delay_ms,
                campaign_id=campaign_id,
                fingerprint_id=fingerprint.fingerprint_id
            )
        
        if under_pressure:
            score += weights["rate_pressure"]
            reasons.append("rate_pressure")
        
        # User-Agent analysis
        ua = headers.get("user-agent", "").strip()
        if len(ua) < 8:
            score += weights["bad_user_agent"]
            reasons.append("suspicious_user_agent")
        
        # Missing headers
        needed = ["accept", "accept-language"]
        missing = [h for h in needed if not headers.get(h)]
        if missing:
            score += weights["missing_headers"]
            reasons.append(f"missing_headers:{','.join(missing)}")
        
        # Suspicious path
        if any(path.startswith(p) for p in self.config.trap_paths_prefix):
            score += weights["suspicious_path"]
            reasons.append("suspicious_path")
        
        # Behavior flags
        if behavior_flags.get("decoy_touched"):
            score += weights["decoy_touched"]
            reasons.append("decoy_touched")
            campaign.decoy_interactions += 1
        
        if behavior_flags.get("ai_behavior"):
            score += weights["ai_behavior"]
            reasons.append("ai_behavior_detected")
        
        if behavior_flags.get("repeated_failures"):
            score += weights["repeated_failures"]
            reasons.append("repeated_auth_failures")
        
        # Known bad fingerprint (high recidivism)
        if fingerprint.total_events > 50 and campaign.trap_events > 10:
            score += weights["known_bad_fingerprint"]
            reasons.append("known_bad_fingerprint")

        logic_budget = self._logic_budget_control(behavior_flags, campaign)
        if logic_budget["enabled"] and logic_budget["pressure"] > 0:
            score += logic_budget["score_boost"]
            reasons.append(f"logic_budget_pressure:{logic_budget['pressure']:.2f}")
            if logic_budget["high_pressure"]:
                reasons.append("logic_budget_high_pressure")
        
        # Apply Mystique campaign overrides
        if self.config.mystique_enabled and campaign.sink_score_override is not None:
            if score >= campaign.sink_score_override:
                score = max(score, campaign.sink_score_override)
        
        # Clamp score
        score = max(0, min(100, score))
        
        # Determine route
        route = RouteDecision.PASS_THROUGH
        delay_ms = 0

        if logic_budget["force_trap"] and self.config.trap_sink_enabled:
            route = RouteDecision.TRAP_SINK
            delay_ms = self._calculate_tarpit_delay(campaign)
        elif self.config.trap_sink_enabled and score >= self.config.trap_sink_min_score:
            route = RouteDecision.TRAP_SINK
            delay_ms = self._calculate_tarpit_delay(campaign)
        elif self.config.disinformation_enabled and score >= self.config.disinformation_min_score and (
            "suspicious_path" in reasons
            or "ai_behavior_detected" in reasons
            or "decoy_touched" in reasons
            or logic_budget.get("high_pressure", False)
        ):
            # DISINFORMATION: medium-confidence probe — feed plausible-but-wrong data
            route = RouteDecision.DISINFORMATION
        elif self.config.friction_enabled and score >= self.config.friction_challenge_score:
            route = RouteDecision.FRICTION
            delay_ms = self._calculate_friction_delay(score, campaign)
        
        return RiskAssessment(
            score=score,
            reasons=reasons,
            route=route,
            delay_ms=delay_ms,
            campaign_id=campaign_id,
            fingerprint_id=fingerprint.fingerprint_id,
            escalation_level=campaign.escalation_level
        )

    def _logic_budget_control(self, behavior_flags: Dict[str, Any], campaign: AttackCampaign) -> Dict[str, Any]:
        """Apply logic-budget exhaustion signals to routing pressure."""
        if not self.config.logic_budget_controller_enabled:
            return {
                "enabled": False,
                "pressure": 0.0,
                "score_boost": 0,
                "high_pressure": False,
                "force_trap": False,
            }

        cbr = float(behavior_flags.get("cbr") or 0.0)
        tbcr = float(behavior_flags.get("tbcr") or 0.0)
        cdi = float(behavior_flags.get("cdi") or 0.0)
        agenticity = float(behavior_flags.get("agenticity_score") or 0.0)
        autonomous_confidence = float(behavior_flags.get("autonomous_confidence") or 0.0)
        cognitive_pressure = float(behavior_flags.get("cognitive_pressure") or 0.0)

        # Normalize primary metrics into 0..1 pressure components.
        cbr_norm = min(1.0, cbr / max(1.0, self.config.logic_budget_target_cbr))
        tbcr_norm = min(1.0, tbcr / max(1.0, self.config.logic_budget_target_tbcr))
        cdi_norm = min(1.0, cdi / max(0.01, self.config.logic_budget_target_cdi))
        agenticity_norm = min(1.0, max(agenticity, autonomous_confidence, cognitive_pressure))

        w = self.config.logic_budget_weights
        pressure = (
            cbr_norm * w["cbr"]
            + tbcr_norm * w["tbcr"]
            + cdi_norm * w["cdi"]
            + agenticity_norm * w["agenticity"]
        )
        pressure = max(0.0, min(1.0, pressure))

        # Directly bias campaign dynamics when pressure remains elevated.
        if pressure >= 0.75:
            campaign.friction_multiplier = min(
                self.config.max_friction_multiplier,
                campaign.friction_multiplier + 0.10,
            )
            campaign.tarpit_multiplier = min(
                self.config.max_tarpit_multiplier,
                campaign.tarpit_multiplier + 0.05,
            )

        score_boost = int(min(30, round(pressure * 30)))
        high_pressure = pressure >= 0.7
        force_trap = pressure >= self.config.logic_budget_force_trap_threshold

        return {
            "enabled": True,
            "pressure": pressure,
            "score_boost": score_boost,
            "high_pressure": high_pressure,
            "force_trap": force_trap,
        }
    
    def _calculate_friction_delay(self, score: int, campaign: AttackCampaign) -> int:
        """Calculate friction delay based on score and Mystique multiplier"""
        base = self.config.friction_base_delay_ms
        max_delay = self.config.friction_max_delay_ms
        
        # Score-based delay
        delay = base + int((score / 100) * (max_delay - base))
        
        # Apply Mystique multiplier
        if self.config.mystique_enabled:
            delay = int(delay * campaign.friction_multiplier)
        
        # Cap at max * max_multiplier
        max_allowed = int(max_delay * self.config.max_friction_multiplier)
        return max(base, min(max_allowed, delay))
    
    def _calculate_tarpit_delay(self, campaign: AttackCampaign) -> int:
        """Calculate tarpit delay with Mystique multiplier"""
        base = self.config.trap_tarpit_delay_ms
        
        # Apply Mystique multiplier
        if self.config.mystique_enabled:
            delay = int(base * campaign.tarpit_multiplier)
        else:
            delay = base
        
        max_allowed = int(base * self.config.max_tarpit_multiplier)
        return max(base, min(max_allowed, delay))
    
    # =========================================================================
    # MYSTIQUE - ADAPTIVE DECEPTION
    # =========================================================================
    
    def mystique_adapt(self, campaign_id: str) -> bool:
        """
        Adapt deception parameters based on campaign behavior.
        Called periodically after events. Returns True if adapted.
        """
        if not self.config.mystique_enabled or campaign_id not in self.campaigns:
            return False
        
        campaign = self.campaigns[campaign_id]
        n = self.config.adapt_every_n_events
        promote = self.config.campaign_promote_threshold
        
        # Only adapt for promoted campaigns
        if campaign.total_events < promote:
            return False
        
        # Adapt every n events
        if campaign.total_events % n != 0:
            return False
        
        # Calculate trap ratio
        trap_ratio = campaign.trap_events / max(1, campaign.total_events)
        
        # High trap ratio = increase friction
        if trap_ratio >= 0.4:
            campaign.friction_multiplier = min(
                self.config.max_friction_multiplier,
                campaign.friction_multiplier + 0.25
            )
            campaign.tarpit_multiplier = min(
                self.config.max_tarpit_multiplier,
                campaign.tarpit_multiplier + 0.10
            )
            
            # Lower sink threshold
            floor = self.config.min_sink_score_floor
            if campaign.sink_score_override is None:
                campaign.sink_score_override = 75
            campaign.sink_score_override = max(floor, min(90, campaign.sink_score_override - 5))
            
            logger.info(
                f"Mystique adapted campaign {campaign_id}: "
                f"friction={campaign.friction_multiplier:.2f}, "
                f"tarpit={campaign.tarpit_multiplier:.2f}, "
                f"sink_threshold={campaign.sink_score_override}"
            )
            return True
        
        return False
    
    # =========================================================================
    # STONEWALL - PROGRESSIVE ESCALATION
    # =========================================================================
    
    def stonewall_check(self, campaign_id: str, ip: str, route: RouteDecision) -> EscalationLevel:
        """
        Check and apply Stonewall escalation rules.
        Automatically escalates persistent attackers.
        """
        if not self.config.stonewall_enabled or campaign_id not in self.campaigns:
            return EscalationLevel.NONE
        
        campaign = self.campaigns[campaign_id]
        
        # Update counters
        self.campaign_counts[campaign_id] += 1
        if route == RouteDecision.TRAP_SINK:
            self.trap_hits[campaign_id] += 1
            campaign.trap_events += 1
        elif route == RouteDecision.FRICTION:
            campaign.friction_events += 1
        elif route == RouteDecision.DISINFORMATION:
            campaign.disinfo_events += 1
        else:
            campaign.pass_events += 1
        
        campaign.total_events += 1
        
        count = self.campaign_counts[campaign_id]
        traps = self.trap_hits[campaign_id]
        
        # Progressive escalation
        new_level = campaign.escalation_level
        
        # First threshold - soft ban
        if count == self.config.repeat_threshold:
            self.soft_bans[ip] = time.time() + self.config.ban_seconds_first
            new_level = EscalationLevel.SOFT_BANNED
            logger.warning(f"Stonewall: {ip} soft banned for {self.config.ban_seconds_first}s (campaign {campaign_id})")
        
        # Repeat offender - longer ban
        if count > self.config.repeat_threshold and count % self.config.repeat_threshold == 0:
            self.soft_bans[ip] = time.time() + self.config.ban_seconds_repeat
            new_level = EscalationLevel.HARD_BANNED
            logger.warning(f"Stonewall: {ip} hard banned for {self.config.ban_seconds_repeat}s (campaign {campaign_id})")
        
        # High trap hits - blocklist
        if traps >= self.config.trap_hits_to_blocklist:
            self.blocklist.add(ip)
            new_level = EscalationLevel.BLOCKLISTED
            logger.critical(f"Stonewall: {ip} BLOCKLISTED after {traps} trap hits (campaign {campaign_id})")
        
        campaign.escalation_level = new_level

        # Gap B: Fire alert callback on meaningful escalation so SOAR gets notified
        # (soft-ban is routine; hard-ban and blocklist warrant SOAR playbook activation)
        if new_level in (EscalationLevel.HARD_BANNED, EscalationLevel.BLOCKLISTED) and self._alert_callback:
            stonewall_event = {
                "event_id": hashlib.md5(f"stonewall{ip}{time.time()}".encode()).hexdigest()[:16],
                "event_type": "stonewall.escalation",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "campaign_id": campaign_id,
                "source_ip": ip,
                "session_id": None,
                "route_decision": RouteDecision.TRAP_SINK.value,
                "risk_score": 100,
                "escalation_level": new_level.value,
                "details": {
                    "decoy_type": "stonewall",
                    "decoy_id": f"stonewall_{campaign_id}",
                    "campaign_events": count,
                    "trap_hits": traps,
                },
            }
            self._alert_callback(stonewall_event)

        return new_level
    
    # =========================================================================
    # EVENT PROCESSING
    # =========================================================================
    
    async def process_request(self,
                              ip: str,
                              path: str,
                              headers: Dict[str, str],
                              session_id: Optional[str] = None,
                              timing_data: Optional[Dict] = None,
                              behavior_flags: Optional[Dict[str, bool]] = None) -> RiskAssessment:
        """
        Main entry point for processing incoming requests.
        Returns risk assessment with routing decision.
        """
        # Assess risk
        assessment = self.assess_risk(
            ip=ip,
            path=path,
            headers=headers,
            session_id=session_id,
            timing_data=timing_data,
            behavior_flags=behavior_flags
        )
        
        # Apply Stonewall escalation
        if assessment.campaign_id:
            assessment.escalation_level = self.stonewall_check(
                assessment.campaign_id, ip, assessment.route
            )
            
            # Apply Mystique adaptation
            self.mystique_adapt(assessment.campaign_id)
        
        # Record event
        event = DeceptionEvent(
            event_id=hashlib.md5(f"{ip}{time.time()}".encode()).hexdigest()[:16],
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type=f"request_{assessment.route.value}",
            campaign_id=assessment.campaign_id,
            fingerprint_id=assessment.fingerprint_id,
            source_ip=ip,
            session_id=session_id,
            route_decision=assessment.route,
            risk_score=assessment.score,
            risk_reasons=assessment.reasons,
            delay_applied_ms=assessment.delay_ms,
            details={"path": path, "escalation": assessment.escalation_level.value}
        )
        
        self.events.append(event)
        
        # Keep only last 10000 events
        if len(self.events) > 10000:
            self.events = self.events[-10000:]
        
        # Emit alert for significant events
        if assessment.route in (RouteDecision.TRAP_SINK, RouteDecision.HONEYPOT):
            if self._alert_callback:
                self._alert_callback(event.to_dict())

        # Emit a DISINFORMATION persistence alert when a campaign crosses the
        # threshold — signals that someone is probing systematically through
        # the poisoned-data layer and SOAR should escalate.
        if (assessment.route == RouteDecision.DISINFORMATION
                and assessment.campaign_id
                and self._alert_callback):
            camp = self.campaigns.get(assessment.campaign_id)
            _DISINFO_PERSIST_THRESHOLD = int(
                os.environ.get("DISINFO_PERSIST_THRESHOLD", "5")
            )
            if camp and camp.disinfo_events >= _DISINFO_PERSIST_THRESHOLD:
                disinfo_alert = {
                    "event_id": hashlib.md5(
                        f"disinfo_persist{assessment.campaign_id}{camp.disinfo_events}".encode()
                    ).hexdigest()[:16],
                    "event_type": "deception.disinfo",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "campaign_id": assessment.campaign_id,
                    "source_ip": ip,
                    "session_id": session_id,
                    "route_decision": RouteDecision.DISINFORMATION.value,
                    "risk_score": assessment.score,
                    "disinfo_events": camp.disinfo_events,
                    "details": {
                        "path": path,
                        "disinfo_events": camp.disinfo_events,
                        "total_events": camp.total_events,
                    },
                }
                self._alert_callback(disinfo_alert)

        return assessment
    
    async def record_decoy_interaction(self,
                                        ip: str,
                                        decoy_type: str,
                                        decoy_id: str,
                                        session_id: Optional[str] = None,
                                        headers: Optional[Dict[str, str]] = None) -> RiskAssessment:
        """
        Record when an attacker interacts with a decoy/honey token.
        Immediately escalates campaign risk.
        """
        headers = headers or {}
        
        # Compute fingerprint and campaign
        fingerprint = self.compute_fingerprint(headers)
        campaign_id = self.compute_campaign_id(ip, fingerprint.fingerprint_id)
        campaign = self.get_or_create_campaign(campaign_id, ip, fingerprint.fingerprint_id, session_id)
        
        # Record interaction
        campaign.decoy_interactions += 1
        
        # Record event
        event = DeceptionEvent(
            event_id=hashlib.md5(f"{ip}{decoy_id}{time.time()}".encode()).hexdigest()[:16],
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type="decoy_interaction",
            campaign_id=campaign_id,
            fingerprint_id=fingerprint.fingerprint_id,
            source_ip=ip,
            session_id=session_id,
            route_decision=RouteDecision.TRAP_SINK,
            risk_score=100,
            risk_reasons=["decoy_touched", f"decoy_type:{decoy_type}"],
            details={"decoy_id": decoy_id, "decoy_type": decoy_type}
        )
        
        self.events.append(event)
        
        # Aggressive Stonewall escalation for decoy touches
        self.trap_hits[campaign_id] += 5  # Decoy touch counts as 5 trap hits
        self.stonewall_check(campaign_id, ip, RouteDecision.TRAP_SINK)
        
        # Alert
        if self._alert_callback:
            self._alert_callback(event.to_dict())
        
        logger.critical(f"DECOY TOUCHED: {decoy_type} ({decoy_id}) from {ip} - Campaign {campaign_id}")
        
        return RiskAssessment(
            score=100,
            reasons=["decoy_touched"],
            route=RouteDecision.TRAP_SINK,
            delay_ms=self._calculate_tarpit_delay(campaign),
            campaign_id=campaign_id,
            fingerprint_id=fingerprint.fingerprint_id,
            escalation_level=campaign.escalation_level
        )
    
    # =========================================================================
    # API / STATUS
    # =========================================================================
    
    def get_status(self) -> Dict[str, Any]:
        """Get deception engine status"""
        active_campaigns = len([c for c in self.campaigns.values() 
                               if c.total_events > 0])
        
        return {
            "config": {
                "mystique_enabled": self.config.mystique_enabled,
                "stonewall_enabled": self.config.stonewall_enabled,
                "friction_enabled": self.config.friction_enabled,
                "trap_sink_enabled": self.config.trap_sink_enabled,
            },
            "campaigns": {
                "total": len(self.campaigns),
                "active": active_campaigns,
            },
            "fingerprints": len(self.fingerprints),
            "blocklist_size": len(self.blocklist),
            "soft_bans": len(self.soft_bans),
            "recent_events": len(self.events),
            "trap_hits_total": sum(self.trap_hits.values()),
        }
    
    def get_campaigns(self, min_events: int = 5, limit: int = 50) -> List[Dict]:
        """Get active campaigns"""
        campaigns = [
            c.to_dict() for c in self.campaigns.values()
            if c.total_events >= min_events
        ]
        
        # Sort by total events descending
        campaigns.sort(key=lambda x: x["total_events"], reverse=True)
        return campaigns[:limit]
    
    def get_campaign(self, campaign_id: str) -> Optional[Dict]:
        """Get specific campaign"""
        if campaign_id in self.campaigns:
            return self.campaigns[campaign_id].to_dict()
        return None
    
    def get_events(self, 
                   limit: int = 100,
                   route_filter: Optional[str] = None,
                   campaign_id: Optional[str] = None) -> List[Dict]:
        """Get recent events with optional filtering"""
        events = self.events
        
        if route_filter:
            events = [e for e in events if e.route_decision.value == route_filter]
        
        if campaign_id:
            events = [e for e in events if e.campaign_id == campaign_id]
        
        events = sorted(events, key=lambda x: x.timestamp, reverse=True)[:limit]
        return [e.to_dict() for e in events]
    
    def add_to_allowlist(self, ip: str) -> bool:
        """Add IP to allowlist"""
        self.allowlist.add(ip)
        self.blocklist.discard(ip)
        self.soft_bans.pop(ip, None)
        return True
    
    def add_to_blocklist(self, ip: str) -> bool:
        """Add IP to blocklist"""
        self.blocklist.add(ip)
        self.allowlist.discard(ip)
        return True
    
    def remove_from_blocklist(self, ip: str) -> bool:
        """Remove IP from blocklist"""
        self.blocklist.discard(ip)
        return True
    
    # =========================================================================
    # PERSISTENCE
    # =========================================================================
    
    def _load_state(self):
        """Load persistent state from disk"""
        state_file = DATA_DIR / "deception_state.json"
        if state_file.exists():
            try:
                with open(state_file, 'r') as f:
                    data = json.load(f)
                    self.blocklist = set(data.get("blocklist", []))
                    self.allowlist = set(data.get("allowlist", []))
                    logger.info(f"Loaded deception state: {len(self.blocklist)} blocklisted IPs")
            except Exception as e:
                logger.error(f"Failed to load deception state: {e}")
    
    def _save_state(self):
        """Save persistent state to disk"""
        state_file = DATA_DIR / "deception_state.json"
        try:
            data = {
                "blocklist": list(self.blocklist),
                "allowlist": list(self.allowlist),
                "saved_at": datetime.now(timezone.utc).isoformat()
            }
            with open(state_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save deception state: {e}")
    
    async def periodic_maintenance(self):
        """Periodic maintenance tasks"""
        while True:
            try:
                # Clean up rate limiter
                self.rate_limiter.cleanup()
                
                # Clean up expired soft bans
                now = time.time()
                self.soft_bans = {k: v for k, v in self.soft_bans.items() if v > now}
                
                # Save state
                self._save_state()
                
                # Prune old campaigns (older than 24 hours with no activity)
                cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
                cutoff_str = cutoff.isoformat()
                old_campaigns = [
                    cid for cid, c in self.campaigns.items()
                    if c.last_seen < cutoff_str and c.total_events < 10
                ]
                for cid in old_campaigns:
                    del self.campaigns[cid]
                
            except Exception as e:
                logger.error(f"Deception maintenance error: {e}")
            
            await asyncio.sleep(300)  # Every 5 minutes


# =============================================================================
# GLOBAL INSTANCE
# =============================================================================

deception_engine = DeceptionEngine()


# =============================================================================
# INTEGRATION HELPERS
# =============================================================================

def integrate_with_honey_tokens(honey_token_manager):
    """Connect deception engine with honey token manager"""
    deception_engine.set_honey_token_manager(honey_token_manager)
    
    # Wrap honey token access recording to also notify deception engine
    original_record_access = honey_token_manager.record_access
    
    def wrapped_record_access(token_id, source_ip, **kwargs):
        result = original_record_access(token_id, source_ip, **kwargs)

        if os.environ.get("HONEY_TOKENS_ENABLED", "true").lower() != "true":
            return result
        
        # Notify deception engine
        asyncio.create_task(
            deception_engine.record_decoy_interaction(
                ip=source_ip,
                decoy_type="honey_token",
                decoy_id=token_id,
                headers=kwargs.get("headers", {})
            )
        )
        
        return result
    
    honey_token_manager.record_access = wrapped_record_access
    logger.info("Integrated deception engine with honey token manager")


def integrate_with_ransomware_protection(ransomware_detector):
    """Connect deception engine with ransomware detector"""
    deception_engine.set_ransomware_detector(ransomware_detector)
    logger.info("Integrated deception engine with ransomware protection")
