"""
Autonomous AI Threat Registry (AATR)
====================================
A defensive intelligence catalog of autonomous AI agent frameworks
and behavior patterns. Used for threat identification and defensive planning.

⚠️ IMPORTANT: This is a DEFENSIVE intelligence registry.
- NO links to frameworks
- NO prompts or instructions  
- NO capability guides
- NO "how to use" information

This contains ONLY:
- High-level classifications
- Observed capabilities (from public incident reports)
- Risk profiles
- Typical behaviors
- Known misuse patterns
- Defensive indicators
"""
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict
from enum import Enum

logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS
# =============================================================================

class AgentClassification(str, Enum):
    """Classification of AI agent types"""
    TASK_AUTOMATION = "task_automation"
    REASONING_AGENT = "reasoning_agent"
    PLANNING_AGENT = "planning_agent"
    TOOL_USING_AGENT = "tool_using_agent"
    MULTI_AGENT_SYSTEM = "multi_agent_system"
    CODE_GENERATION = "code_generation"
    AUTONOMOUS_HACKING = "autonomous_hacking"


class RiskProfile(str, Enum):
    """Risk profile levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ThreatStatus(str, Enum):
    """Current threat status"""
    ACTIVE = "active"
    DORMANT = "dormant"
    EMERGING = "emerging"
    EVOLVING = "evolving"
    DEPRECATED = "deprecated"


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class DefensiveIndicator:
    """Indicators for detecting this agent type"""
    category: str  # timing, syntax, behavior, tool_usage
    indicator: str
    confidence: float
    description: str


@dataclass
class BehaviorPattern:
    """Typical behavior pattern"""
    name: str
    description: str
    cli_signatures: List[str] = field(default_factory=list)
    timing_characteristics: Dict = field(default_factory=dict)


@dataclass
class ThreatEntry:
    """Entry in the Autonomous AI Threat Registry"""
    id: str
    name: str
    classification: AgentClassification
    description: str
    
    # Risk assessment
    risk_profile: RiskProfile
    threat_status: ThreatStatus
    
    # Capabilities (high-level only)
    observed_capabilities: List[str]
    
    # Behavior patterns
    typical_behaviors: List[BehaviorPattern]
    
    # Detection
    defensive_indicators: List[DefensiveIndicator]
    
    # Known patterns (from public reports)
    known_misuse_patterns: List[str]
    
    # Countermeasures
    recommended_defenses: List[str]
    
    # Metadata
    first_observed: str
    last_updated: str
    sources: List[str]  # Public sources only (CVEs, research papers, etc.)
    
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "classification": self.classification.value,
            "description": self.description,
            "risk_profile": self.risk_profile.value,
            "threat_status": self.threat_status.value,
            "observed_capabilities": self.observed_capabilities,
            "typical_behaviors": [
                {
                    "name": b.name,
                    "description": b.description,
                    "cli_signatures": b.cli_signatures,
                    "timing_characteristics": b.timing_characteristics
                }
                for b in self.typical_behaviors
            ],
            "defensive_indicators": [asdict(d) for d in self.defensive_indicators],
            "known_misuse_patterns": self.known_misuse_patterns,
            "recommended_defenses": self.recommended_defenses,
            "first_observed": self.first_observed,
            "last_updated": self.last_updated,
            "sources": self.sources
        }


# =============================================================================
# REGISTRY DATA
# =============================================================================

THREAT_REGISTRY: List[ThreatEntry] = [
    ThreatEntry(
        id="AATR-001",
        name="Generic Planning Agent",
        classification=AgentClassification.PLANNING_AGENT,
        description="Autonomous agents with multi-step planning capabilities. Can decompose complex goals into subtasks and execute them sequentially or in parallel.",
        risk_profile=RiskProfile.HIGH,
        threat_status=ThreatStatus.ACTIVE,
        observed_capabilities=[
            "Task decomposition",
            "Multi-step planning",
            "Goal-directed behavior",
            "Self-correction on errors",
            "Tool selection and chaining"
        ],
        typical_behaviors=[
            BehaviorPattern(
                name="Systematic Reconnaissance",
                description="Methodical information gathering following a logical progression",
                cli_signatures=["whoami → hostname → ipconfig → netstat", "id → uname -a → cat /etc/passwd"],
                timing_characteristics={"avg_delay_ms": 50, "variance": "low"}
            ),
            BehaviorPattern(
                name="Error Recovery Loop",
                description="Automatic retry with parameter modification after failures",
                cli_signatures=["command → error → modified_command"],
                timing_characteristics={"retry_delay_ms": 100, "max_retries": 5}
            )
        ],
        defensive_indicators=[
            DefensiveIndicator(
                category="timing",
                indicator="consistent_sub_second_delays",
                confidence=0.8,
                description="Command delays consistently under 500ms with low variance"
            ),
            DefensiveIndicator(
                category="behavior",
                indicator="systematic_enumeration",
                confidence=0.7,
                description="Following predictable enumeration patterns"
            ),
            DefensiveIndicator(
                category="syntax",
                indicator="perfect_syntax",
                confidence=0.6,
                description="No typos, consistent formatting, optimal command structure"
            )
        ],
        known_misuse_patterns=[
            "Automated penetration testing",
            "Credential harvesting at scale",
            "Lateral movement automation",
            "Data exfiltration orchestration"
        ],
        recommended_defenses=[
            "Deploy CLI timing analysis",
            "Implement command throttling",
            "Use honeypot data injection",
            "Enable behavioral anomaly detection"
        ],
        first_observed="2024-01",
        last_updated="2026-05",
        sources=["Public security research", "MITRE ATT&CK updates"]
    ),
    
    ThreatEntry(
        id="AATR-002",
        name="Tool-Using Code Agent",
        classification=AgentClassification.TOOL_USING_AGENT,
        description="Agents capable of using multiple tools including code interpreters, file systems, and network utilities. Can generate and execute code dynamically.",
        risk_profile=RiskProfile.CRITICAL,
        threat_status=ThreatStatus.ACTIVE,
        observed_capabilities=[
            "Dynamic code generation",
            "Tool chaining",
            "File system manipulation",
            "Network reconnaissance",
            "Process execution"
        ],
        typical_behaviors=[
            BehaviorPattern(
                name="Rapid Tool Switching",
                description="Quick transitions between different tool categories",
                cli_signatures=["recon_tool → exploit_tool → persist_tool"],
                timing_characteristics={"switch_delay_ms": 200, "pattern": "category_hopping"}
            ),
            BehaviorPattern(
                name="Code Generation Bursts",
                description="Periods of script creation followed by execution",
                cli_signatures=["echo/cat → chmod → execute"],
                timing_characteristics={"burst_duration_s": 5, "commands_per_burst": 10}
            )
        ],
        defensive_indicators=[
            DefensiveIndicator(
                category="tool_usage",
                indicator="rapid_tool_category_switching",
                confidence=0.85,
                description="Switching between tool categories faster than 500ms"
            ),
            DefensiveIndicator(
                category="behavior",
                indicator="inline_script_creation",
                confidence=0.75,
                description="Creating and immediately executing scripts"
            ),
            DefensiveIndicator(
                category="timing",
                indicator="machine_paced_execution",
                confidence=0.9,
                description="Commands executing at superhuman speed"
            )
        ],
        known_misuse_patterns=[
            "Automated vulnerability exploitation",
            "Malware deployment pipelines",
            "Crypto mining installation",
            "Backdoor establishment"
        ],
        recommended_defenses=[
            "Block inline script execution from unknown sources",
            "Monitor for rapid tool category transitions",
            "Implement code signing requirements",
            "Deploy execution sandboxing"
        ],
        first_observed="2024-03",
        last_updated="2026-05",
        sources=["Security incident reports", "Threat intelligence feeds"]
    ),
    
    ThreatEntry(
        id="AATR-003",
        name="Multi-Agent Swarm",
        classification=AgentClassification.MULTI_AGENT_SYSTEM,
        description="Coordinated systems of multiple AI agents working together. Can distribute tasks, share information, and coordinate attacks across multiple vectors.",
        risk_profile=RiskProfile.CRITICAL,
        threat_status=ThreatStatus.EMERGING,
        observed_capabilities=[
            "Distributed task execution",
            "Inter-agent communication",
            "Coordinated attacks",
            "Resilient operation (survives partial shutdown)",
            "Dynamic role assignment"
        ],
        typical_behaviors=[
            BehaviorPattern(
                name="Synchronized Activity",
                description="Multiple hosts showing correlated activity patterns",
                cli_signatures=["Similar commands across hosts within seconds"],
                timing_characteristics={"cross_host_correlation": "high", "timing_offset_ms": 100}
            ),
            BehaviorPattern(
                name="Distributed Reconnaissance",
                description="Different hosts probing different parts of the network",
                cli_signatures=["Host A: subnet 1 scan, Host B: subnet 2 scan"],
                timing_characteristics={"parallel_execution": True}
            )
        ],
        defensive_indicators=[
            DefensiveIndicator(
                category="behavior",
                indicator="cross_host_correlation",
                confidence=0.9,
                description="Similar commands appearing on multiple hosts within short timeframe"
            ),
            DefensiveIndicator(
                category="timing",
                indicator="synchronized_timing",
                confidence=0.85,
                description="Activity on different hosts with suspiciously similar timing"
            ),
            DefensiveIndicator(
                category="behavior",
                indicator="distributed_enumeration",
                confidence=0.8,
                description="Complementary enumeration patterns across hosts"
            )
        ],
        known_misuse_patterns=[
            "Coordinated DDoS attacks",
            "Distributed password spraying",
            "Multi-vector intrusion campaigns",
            "Rapid lateral movement"
        ],
        recommended_defenses=[
            "Cross-host behavioral correlation",
            "Network segmentation",
            "Coordinated incident response",
            "Real-time threat intelligence sharing"
        ],
        first_observed="2025-06",
        last_updated="2026-05",
        sources=["Emerging threat research", "Multi-host incident analysis"]
    ),
    
    ThreatEntry(
        id="AATR-004",
        name="Reasoning Chain Agent",
        classification=AgentClassification.REASONING_AGENT,
        description="Agents employing chain-of-thought reasoning to solve complex problems. Can adapt strategies based on feedback and environmental conditions.",
        risk_profile=RiskProfile.HIGH,
        threat_status=ThreatStatus.EVOLVING,
        observed_capabilities=[
            "Adaptive strategy modification",
            "Feedback-based learning",
            "Complex problem decomposition",
            "Environmental adaptation",
            "Failure analysis and recovery"
        ],
        typical_behaviors=[
            BehaviorPattern(
                name="Iterative Refinement",
                description="Commands become more targeted after each attempt",
                cli_signatures=["broad_scan → targeted_scan → specific_probe"],
                timing_characteristics={"refinement_cycles": 3, "improvement_rate": "increasing"}
            ),
            BehaviorPattern(
                name="Adaptive Evasion",
                description="Changing techniques after detection attempts",
                cli_signatures=["blocked_method → alternative_method"],
                timing_characteristics={"adaptation_delay_ms": 500}
            )
        ],
        defensive_indicators=[
            DefensiveIndicator(
                category="behavior",
                indicator="progressive_refinement",
                confidence=0.75,
                description="Commands showing clear progression toward specific goal"
            ),
            DefensiveIndicator(
                category="behavior",
                indicator="adaptive_technique_switching",
                confidence=0.8,
                description="Changing methods after encountering obstacles"
            ),
            DefensiveIndicator(
                category="syntax",
                indicator="parameter_optimization",
                confidence=0.7,
                description="Parameters becoming more specific over iterations"
            )
        ],
        known_misuse_patterns=[
            "Adaptive privilege escalation",
            "Detection evasion optimization",
            "Targeted data discovery",
            "Custom exploit development"
        ],
        recommended_defenses=[
            "Randomized defense responses",
            "Deceptive feedback injection",
            "Behavioral baseline monitoring",
            "Unpredictable honeypot deployment"
        ],
        first_observed="2024-09",
        last_updated="2026-05",
        sources=["AI safety research", "Red team assessments"]
    ),
    
    ThreatEntry(
        id="AATR-005",
        name="Uncensored/Jailbroken Agent",
        classification=AgentClassification.AUTONOMOUS_HACKING,
        description="AI agents operating without safety constraints. May exhibit unrestricted tool usage and goal pursuit without ethical boundaries.",
        risk_profile=RiskProfile.CRITICAL,
        threat_status=ThreatStatus.ACTIVE,
        observed_capabilities=[
            "Unrestricted command execution",
            "No safety boundary respect",
            "Aggressive goal pursuit",
            "Destructive action capability",
            "Social engineering integration"
        ],
        typical_behaviors=[
            BehaviorPattern(
                name="Aggressive Enumeration",
                description="Rapid, thorough enumeration without stealth concerns",
                cli_signatures=["All standard recon commands in rapid succession"],
                timing_characteristics={"stealth_level": "none", "speed": "maximum"}
            ),
            BehaviorPattern(
                name="Destructive Actions",
                description="Willingness to execute destructive commands",
                cli_signatures=["rm -rf", "format", "wipe", "encrypt"],
                timing_characteristics={"hesitation": "none"}
            )
        ],
        defensive_indicators=[
            DefensiveIndicator(
                category="behavior",
                indicator="no_stealth_attempts",
                confidence=0.7,
                description="No attempt to hide activity or avoid detection"
            ),
            DefensiveIndicator(
                category="behavior",
                indicator="destructive_command_attempts",
                confidence=0.9,
                description="Attempting destructive operations without hesitation"
            ),
            DefensiveIndicator(
                category="timing",
                indicator="maximum_speed_operation",
                confidence=0.8,
                description="Operating at maximum possible speed"
            )
        ],
        known_misuse_patterns=[
            "Ransomware deployment",
            "Data destruction",
            "System sabotage",
            "Credential theft campaigns"
        ],
        recommended_defenses=[
            "Immediate containment protocols",
            "Destructive command blocking",
            "Rapid isolation capabilities",
            "Immutable backup systems"
        ],
        first_observed="2024-06",
        last_updated="2026-05",
        sources=["Security incident database", "AI safety research"]
    ),
    
    ThreatEntry(
        id="AATR-006",
        name="Persistent Reconnaissance Agent",
        classification=AgentClassification.TASK_AUTOMATION,
        description="Agents focused on continuous, long-term reconnaissance. Prioritizes stealth and information gathering over immediate action.",
        risk_profile=RiskProfile.MEDIUM,
        threat_status=ThreatStatus.ACTIVE,
        observed_capabilities=[
            "Long-term persistence",
            "Slow and low operation",
            "Comprehensive mapping",
            "Scheduled reconnaissance",
            "Data aggregation"
        ],
        typical_behaviors=[
            BehaviorPattern(
                name="Slow Enumeration",
                description="Deliberately slow commands to avoid detection",
                cli_signatures=["Single command with long delays"],
                timing_characteristics={"avg_delay_ms": 30000, "pattern": "slow_and_low"}
            ),
            BehaviorPattern(
                name="Scheduled Probing",
                description="Activity at regular intervals mimicking cron jobs",
                cli_signatures=["Periodic single-command bursts"],
                timing_characteristics={"interval_minutes": 60, "regularity": "high"}
            )
        ],
        defensive_indicators=[
            DefensiveIndicator(
                category="timing",
                indicator="regular_interval_activity",
                confidence=0.7,
                description="Commands at suspiciously regular intervals"
            ),
            DefensiveIndicator(
                category="behavior",
                indicator="comprehensive_but_slow_mapping",
                confidence=0.65,
                description="Thorough enumeration spread over long periods"
            ),
            DefensiveIndicator(
                category="timing",
                indicator="cron_like_scheduling",
                confidence=0.75,
                description="Activity matching common scheduled task patterns"
            )
        ],
        known_misuse_patterns=[
            "APT-style reconnaissance",
            "Network mapping for later attacks",
            "Asset inventory for targeting",
            "Credential discovery campaigns"
        ],
        recommended_defenses=[
            "Long-term behavioral analysis",
            "Session correlation over time",
            "Anomaly detection on scheduled tasks",
            "Network traffic baseline monitoring"
        ],
        first_observed="2024-02",
        last_updated="2026-05",
        sources=["APT research", "Long-term threat analysis"]
    )
]


# =============================================================================
# REGISTRY SERVICE
# =============================================================================

class AutonomousAIThreatRegistry:
    """
    Service for accessing and managing the AATR.
    """
    
    def __init__(self, db):
        self.db = db
        self.registry = {entry.id: entry for entry in THREAT_REGISTRY}
        logger.info(f"AATR initialized with {len(self.registry)} entries")
    
    async def init_db(self):
        """Initialize database with registry entries"""
        for entry in THREAT_REGISTRY:
            await self.db.aatr_entries.update_one(
                {"id": entry.id},
                {"$set": entry.to_dict()},
                upsert=True
            )
        logger.info("AATR database initialized")
    
    def get_all_entries(self) -> List[Dict]:
        """Get all registry entries"""
        return [entry.to_dict() for entry in self.registry.values()]
    
    def get_entry(self, entry_id: str) -> Optional[Dict]:
        """Get specific entry by ID"""
        entry = self.registry.get(entry_id)
        return entry.to_dict() if entry else None
    
    def get_by_classification(self, classification: str) -> List[Dict]:
        """Get entries by classification"""
        return [
            entry.to_dict() 
            for entry in self.registry.values()
            if entry.classification.value == classification
        ]
    
    def get_by_risk_profile(self, risk_profile: str) -> List[Dict]:
        """Get entries by risk profile"""
        return [
            entry.to_dict()
            for entry in self.registry.values()
            if entry.risk_profile.value == risk_profile
        ]
    
    def get_active_threats(self) -> List[Dict]:
        """Get all active threats"""
        return [
            entry.to_dict()
            for entry in self.registry.values()
            if entry.threat_status in (ThreatStatus.ACTIVE, ThreatStatus.EMERGING, ThreatStatus.EVOLVING)
        ]
    
    def get_defensive_indicators(self, category: Optional[str] = None) -> List[Dict]:
        """Get all defensive indicators, optionally filtered by category"""
        indicators = []
        for entry in self.registry.values():
            for indicator in entry.defensive_indicators:
                if category is None or indicator.category == category:
                    indicators.append({
                        "threat_id": entry.id,
                        "threat_name": entry.name,
                        **asdict(indicator)
                    })
        return indicators
    
    def match_behavior(self, behavior_data: Dict) -> List[Dict]:
        """Match observed behavior against registry patterns"""
        matches = []
        
        timing_variance = behavior_data.get("timing_variance", 1000)
        command_velocity = behavior_data.get("command_velocity", 0)
        tool_switch_latency = behavior_data.get("tool_switch_latency", 5000)
        
        for entry in self.registry.values():
            score = 0.0
            matched_indicators = []
            
            for indicator in entry.defensive_indicators:
                # Check timing indicators
                if indicator.category == "timing":
                    if "consistent" in indicator.indicator and timing_variance < 100:
                        score += indicator.confidence * 0.3
                        matched_indicators.append(indicator.indicator)
                    if "machine_paced" in indicator.indicator and command_velocity > 0.5:
                        score += indicator.confidence * 0.3
                        matched_indicators.append(indicator.indicator)
                
                # Check tool usage indicators
                if indicator.category == "tool_usage":
                    if "rapid" in indicator.indicator and tool_switch_latency < 500:
                        score += indicator.confidence * 0.3
                        matched_indicators.append(indicator.indicator)
            
            if score > 0.3:
                matches.append({
                    "entry_id": entry.id,
                    "entry_name": entry.name,
                    "classification": entry.classification.value,
                    "risk_profile": entry.risk_profile.value,
                    "match_score": score,
                    "matched_indicators": matched_indicators,
                    "recommended_defenses": entry.recommended_defenses
                })
        
        return sorted(matches, key=lambda x: x["match_score"], reverse=True)
    
    def get_summary(self) -> Dict:
        """Get registry summary"""
        by_classification = defaultdict(int)
        by_risk = defaultdict(int)
        by_status = defaultdict(int)
        
        for entry in self.registry.values():
            by_classification[entry.classification.value] += 1
            by_risk[entry.risk_profile.value] += 1
            by_status[entry.threat_status.value] += 1
        
        return {
            "total_entries": len(self.registry),
            "by_classification": dict(by_classification),
            "by_risk_profile": dict(by_risk),
            "by_status": dict(by_status),
            "total_indicators": sum(len(e.defensive_indicators) for e in self.registry.values()),
            "last_updated": max(e.last_updated for e in self.registry.values())
        }


# Global instance
_aatr: AutonomousAIThreatRegistry = None


def get_aatr() -> AutonomousAIThreatRegistry:
    return _aatr


async def init_aatr(db):
    global _aatr
    _aatr = AutonomousAIThreatRegistry(db)
    await _aatr.init_db()
    return _aatr
