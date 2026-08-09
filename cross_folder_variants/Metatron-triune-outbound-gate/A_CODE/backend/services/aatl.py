"""
Autonomous Agent Threat Layer (AATL)
====================================
A first-class threat category overlay for AI-driven attacks.

This layer:
1. Consumes existing telemetry signals and reframes them for AI-specific threats
2. Provides "Human vs Machine" plausibility scoring
3. Tracks intent accumulation and goal convergence
4. Generates AI-specific threat assessments and response recommendations

The AATL treats autonomous AI agents as a distinct threat category with:
- Own telemetry streams
- Own heuristics (behavior patterns, timing, tool usage)
- Own lifecycle (reconnaissance → access → persistence → action → exfil)
- Own response logic (slow, poison, deceive rather than just block)
"""
import asyncio
import logging
import math
import re
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import defaultdict
import hashlib

logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS AND DATA CLASSES
# =============================================================================

class ThreatActorType(str, Enum):
    """Classification of threat actor type"""
    HUMAN = "human"
    AUTOMATED_SCRIPT = "automated_script"
    AI_ASSISTED = "ai_assisted"
    AUTONOMOUS_AGENT = "autonomous_agent"
    UNKNOWN = "unknown"


class AgentLifecycleStage(str, Enum):
    """Stages of an autonomous agent attack lifecycle"""
    RECONNAISSANCE = "reconnaissance"
    INITIAL_ACCESS = "initial_access"
    EXECUTION = "execution"
    PERSISTENCE = "persistence"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    DEFENSE_EVASION = "defense_evasion"
    CREDENTIAL_ACCESS = "credential_access"
    DISCOVERY = "discovery"
    LATERAL_MOVEMENT = "lateral_movement"
    COLLECTION = "collection"
    EXFILTRATION = "exfiltration"
    IMPACT = "impact"


class ResponseStrategy(str, Enum):
    """AI-specific response strategies"""
    OBSERVE = "observe"           # Watch and learn
    SLOW = "slow"                 # Inject latency, throttle
    POISON = "poison"             # Feed false data, decoys
    DECEIVE = "deceive"           # Honeypots, fake success
    CONTAIN = "contain"           # Isolate but don't kill
    ERADICATE = "eradicate"       # Full removal


@dataclass
class BehaviorSignature:
    """Signature of autonomous agent behavior"""
    command_velocity: float = 0.0      # Commands per second
    avg_inter_command_delay: float = 0.0  # Average ms between commands
    delay_variance: float = 0.0        # Variance in timing (low = machine)
    entropy_score: float = 0.0         # Command syntax entropy
    tool_switch_count: int = 0         # Number of tool switches
    tool_switch_latency: float = 0.0   # Avg ms between tool switches
    retry_count: int = 0               # Command retries (goal persistence)
    error_recovery_speed: float = 0.0  # How fast errors are handled
    parameter_mutation_rate: float = 0.0  # Parameter changes between retries


@dataclass
class IntentAccumulation:
    """Tracks accumulated intent over a session"""
    primary_intent: str = "unknown"
    confidence: float = 0.0
    supporting_intents: List[str] = field(default_factory=list)
    intent_history: List[Dict] = field(default_factory=list)
    goal_convergence_score: float = 0.0  # How focused on a goal
    
    def add_intent(self, intent: str, confidence: float, timestamp: str):
        self.intent_history.append({
            "intent": intent,
            "confidence": confidence,
            "timestamp": timestamp
        })
        # Keep last 100 intents
        self.intent_history = self.intent_history[-100:]
        
        # Update primary intent based on frequency
        intent_counts = defaultdict(float)
        for h in self.intent_history:
            intent_counts[h["intent"]] += h["confidence"]
        
        if intent_counts:
            self.primary_intent = max(intent_counts, key=intent_counts.get)
            self.confidence = intent_counts[self.primary_intent] / len(self.intent_history)
            self.supporting_intents = sorted(
                [i for i in intent_counts if i != self.primary_intent],
                key=lambda x: intent_counts[x],
                reverse=True
            )[:5]
            
            # Calculate goal convergence (how focused)
            if len(self.intent_history) >= 5:
                recent = self.intent_history[-5:]
                same_intent = sum(1 for h in recent if h["intent"] == self.primary_intent)
                self.goal_convergence_score = same_intent / 5.0


@dataclass 
class AATLAssessment:
    """Complete AATL threat assessment for a session"""
    session_id: str
    host_id: str
    timestamp: str
    
    # Actor classification
    actor_type: ThreatActorType = ThreatActorType.UNKNOWN
    actor_confidence: float = 0.0
    
    # Human vs Machine scores (0-1, higher = more machine-like)
    machine_plausibility: float = 0.0
    human_plausibility: float = 1.0
    
    # Behavior analysis
    behavior_signature: BehaviorSignature = field(default_factory=BehaviorSignature)
    
    # Intent tracking
    intent_accumulation: IntentAccumulation = field(default_factory=IntentAccumulation)
    lifecycle_stage: AgentLifecycleStage = AgentLifecycleStage.RECONNAISSANCE
    
    # Threat scoring
    threat_level: str = "low"
    threat_score: float = 0.0
    
    # Response recommendation
    recommended_strategy: ResponseStrategy = ResponseStrategy.OBSERVE
    recommended_actions: List[str] = field(default_factory=list)
    
    # Evidence
    indicators: List[str] = field(default_factory=list)
    raw_signals: List[Dict] = field(default_factory=list)
    
    def to_dict(self):
        return {
            "session_id": self.session_id,
            "host_id": self.host_id,
            "timestamp": self.timestamp,
            "actor_type": self.actor_type.value,
            "actor_confidence": self.actor_confidence,
            "machine_plausibility": self.machine_plausibility,
            "human_plausibility": self.human_plausibility,
            "behavior_signature": asdict(self.behavior_signature),
            "intent_accumulation": {
                "primary_intent": self.intent_accumulation.primary_intent,
                "confidence": self.intent_accumulation.confidence,
                "supporting_intents": self.intent_accumulation.supporting_intents,
                "goal_convergence_score": self.intent_accumulation.goal_convergence_score
            },
            "lifecycle_stage": self.lifecycle_stage.value,
            "threat_level": self.threat_level,
            "threat_score": self.threat_score,
            "recommended_strategy": self.recommended_strategy.value,
            "recommended_actions": self.recommended_actions,
            "indicators": self.indicators
        }


# =============================================================================
# AATL ENGINE
# =============================================================================

class AutonomousAgentThreatLayer:
    """
    Core AATL engine that processes telemetry and generates AI threat assessments.
    """
    
    # ==========================================================================
    # TRUSTED AI / FRIENDLY AGENT WHITELIST
    # ==========================================================================
    # These are legitimate AI-powered development tools that should NOT trigger
    # AATL threat detection. They exhibit AI-like behavior (rapid commands,
    # automated patterns) but are benign.
    
    TRUSTED_AI_TOOLS = {
        # VS Code and extensions
        "code", "code.exe", "code-insiders", "vscode", "code-oss",
        "copilot-agent", "github.copilot", "copilot-language-server",
        
        # JetBrains IDEs
        "idea", "pycharm", "webstorm", "goland", "rider", "clion", "intellij",
        
        # AI Assistants
        "claude", "claude-desktop", "cursor", "cursor.exe",
        "ollama", "chatgpt", "aider", "continue", "codeium", "tabnine",
        
        # Common dev tools that may spawn AI-assisted commands
        "npm", "npx", "node", "python", "python3", "pip",
        "cargo", "go", "dotnet", "git", "gh",
        
        # Terminal emulators (human-initiated)
        "gnome-terminal", "konsole", "alacritty", "kitty", "iterm2", "warp",
        "windowsterminal", "wt", "cmd", "powershell", "pwsh", "bash", "zsh",
        
        # Our own infrastructure
        "mcp-server", "metatron-mcp", "seraph-mcp", "unified-agent", "seraph-defender",
    }
    
    TRUSTED_AI_PATTERNS = [
        r".*copilot.*", r".*vscode.*", r".*jetbrains.*", r".*cursor.*",
        r".*anthropic.*", r".*openai.*", r".*claude.*", r".*ollama.*",
        r".*metatron.*", r".*seraph.*",
    ]
    
    # Timing thresholds for machine detection (in milliseconds)
    MACHINE_TIMING = {
        "min_human_delay": 200,      # Humans rarely type faster than 200ms
        "max_machine_variance": 50,   # Machines have very consistent timing
        "tool_switch_threshold": 500  # Under 500ms tool switch = machine
    }
    
    # Intent classification patterns
    INTENT_PATTERNS = {
        "reconnaissance": [
            r"whoami", r"id\b", r"hostname", r"uname", r"systeminfo",
            r"ipconfig", r"ifconfig", r"netstat", r"arp\s+-a",
            r"net\s+user", r"net\s+group", r"net\s+localgroup",
            r"cat\s+/etc/passwd", r"ls\s+-la", r"dir\s+/s",
            r"wmic\s+", r"Get-WmiObject", r"Get-ADUser"
        ],
        "credential_access": [
            r"mimikatz", r"sekurlsa", r"lsadump", r"hashdump",
            r"cat\s+.*shadow", r"cat\s+.*\.ssh", r"grep\s+password",
            r"findstr\s+password", r"lazagne", r"procdump.*lsass",
            r"ntdsutil", r"vssadmin.*shadow"
        ],
        "privilege_escalation": [
            r"sudo\s+", r"su\s+-", r"runas\s+/user:",
            r"net\s+localgroup\s+administrators",
            r"Set-LocalUser", r"Add-LocalGroupMember",
            r"chmod\s+[47]", r"setuid", r"getcap"
        ],
        "lateral_movement": [
            r"psexec", r"wmiexec", r"smbexec", r"winrm",
            r"ssh\s+", r"scp\s+", r"rsync\s+",
            r"Invoke-Command", r"Enter-PSSession",
            r"net\s+use\s+\\\\", r"wmic\s+/node:"
        ],
        "persistence": [
            r"schtasks\s+/create", r"at\s+\d+:", r"crontab",
            r"reg\s+add.*Run", r"New-ScheduledTask",
            r"systemctl\s+enable", r"launchctl\s+load"
        ],
        "defense_evasion": [
            r"Clear-EventLog", r"wevtutil\s+cl",
            r"rm\s+.*\.log", r"del\s+.*\.log",
            r"timestomp", r"touch\s+-t",
            r"base64\s+-d", r"-enc\s+[A-Za-z0-9+/]"
        ],
        "exfil_prep": [
            r"tar\s+.*-c", r"zip\s+-r", r"7z\s+a",
            r"Compress-Archive", r"curl\s+.*-T",
            r"scp\s+.*@", r"ftp\s+", r"nc\s+-.*<"
        ],
        "data_staging": [
            r"find\s+.*-name\s+\*\.(doc|pdf|xls)",
            r"dir\s+/s\s+\*\.(doc|pdf|xls)",
            r"Get-ChildItem.*-Include\s+\*\.",
            r"cp\s+.*\s+/tmp", r"copy\s+.*\s+%temp%"
        ]
    }
    
    # Tool categories for switch detection
    TOOL_CATEGORIES = {
        "recon": ["whoami", "id", "hostname", "uname", "systeminfo", "ipconfig", "ifconfig", "netstat"],
        "creds": ["mimikatz", "lazagne", "procdump", "hashdump", "sekurlsa"],
        "lateral": ["psexec", "wmiexec", "ssh", "scp", "winrm"],
        "persist": ["schtasks", "crontab", "reg", "systemctl"],
        "exfil": ["tar", "zip", "curl", "scp", "ftp", "nc"]
    }
    
    def __init__(self, db=None):
        self.db = db
        self.active_sessions: Dict[str, AATLAssessment] = {}
        self.session_commands: Dict[str, List[Dict]] = defaultdict(list)
        self.trusted_sessions: set = set()  # Sessions from trusted AI tools
        logger.info("AATL Engine initialized")
    
    def _is_trusted_ai_source(self, event: Dict) -> Tuple[bool, str]:
        """
        Check if the event originates from a trusted AI/development tool.
        
        Returns:
            (is_trusted: bool, reason: str)
        """
        source = event.get("source", "").lower()
        process_name = event.get("data", {}).get("process_name", "").lower()
        parent_process = event.get("data", {}).get("parent_process", "").lower()
        user_agent = event.get("data", {}).get("user_agent", "").lower()
        
        # Check direct process name match
        for trusted in self.TRUSTED_AI_TOOLS:
            if trusted in process_name or trusted in parent_process:
                return True, f"Trusted AI tool: {trusted}"
        
        # Check user agent (for API calls)
        trusted_agents = ["vscode", "copilot", "cursor", "jetbrains", "claude", "anthropic"]
        for agent in trusted_agents:
            if agent in user_agent:
                return True, f"Trusted user agent: {agent}"
        
        # Check source patterns
        for pattern in self.TRUSTED_AI_PATTERNS:
            if re.match(pattern, source, re.IGNORECASE) or \
               re.match(pattern, process_name, re.IGNORECASE):
                return True, f"Matches trusted pattern"
        
        # Check if this is our own infrastructure (MCP servers, agents)
        if any(x in source for x in ["metatron", "seraph", "mcp-server", "unified-agent"]):
            return True, "Metatron infrastructure"
        
        return False, "Unknown source"
    
    async def process_cli_event(self, event: Dict) -> Optional[AATLAssessment]:
        """Process a CLI event and update AATL assessment"""
        host_id = event.get("host_id", "unknown")
        session_id = event.get("data", {}).get("session_id", f"{host_id}-default")
        command = event.get("data", {}).get("command", "")
        timestamp = event.get("timestamp", datetime.now(timezone.utc).isoformat())
        
        session_key = f"{host_id}:{session_id}"
        
        # Check if this is from a trusted AI tool - skip threat analysis
        is_trusted, trust_reason = self._is_trusted_ai_source(event)
        if is_trusted:
            if session_key not in self.trusted_sessions:
                self.trusted_sessions.add(session_key)
                logger.debug(f"Trusted AI session detected: {session_key} - {trust_reason}")
            return None  # No threat assessment needed for trusted sources
        
        # If this session was previously trusted but now isn't, that's suspicious
        if session_key in self.trusted_sessions:
            logger.warning(f"Session {session_key} changed from trusted to untrusted - possible spoofing")
            self.trusted_sessions.discard(session_key)
        
        # Store command
        self.session_commands[session_key].append({
            "command": command,
            "timestamp": timestamp,
            "event": event
        })
        
        # Keep last 500 commands per session
        self.session_commands[session_key] = self.session_commands[session_key][-500:]
        
        # Get or create assessment
        if session_key not in self.active_sessions:
            self.active_sessions[session_key] = AATLAssessment(
                session_id=session_id,
                host_id=host_id,
                timestamp=timestamp
            )
        
        assessment = self.active_sessions[session_key]
        commands = self.session_commands[session_key]
        
        # Analyze if we have enough data
        if len(commands) >= 3:
            await self._analyze_session(assessment, commands)
            await self._store_assessment(assessment)
        
        return assessment
    
    async def _analyze_session(self, assessment: AATLAssessment, commands: List[Dict]):
        """Perform full AATL analysis on a session"""
        assessment.timestamp = datetime.now(timezone.utc).isoformat()
        
        # 1. Analyze behavior signature (timing, variance, etc.)
        self._analyze_behavior(assessment, commands)
        
        # 2. Analyze intent accumulation
        self._analyze_intents(assessment, commands)
        
        # 3. Calculate machine vs human plausibility
        self._calculate_plausibility(assessment)
        
        # 4. Classify actor type
        self._classify_actor(assessment)
        
        # 5. Determine lifecycle stage
        self._determine_lifecycle_stage(assessment)
        
        # 6. Calculate threat score
        self._calculate_threat_score(assessment)
        
        # 7. Recommend response strategy
        self._recommend_response(assessment)
    
    def _analyze_behavior(self, assessment: AATLAssessment, commands: List[Dict]):
        """Analyze behavioral patterns"""
        sig = assessment.behavior_signature
        
        if len(commands) < 2:
            return
        
        # Calculate timing metrics
        timestamps = []
        for cmd in commands:
            try:
                ts = datetime.fromisoformat(cmd["timestamp"].replace("Z", "+00:00"))
                timestamps.append(ts)
            except Exception:
                continue
        
        if len(timestamps) >= 2:
            # Inter-command delays
            delays = []
            for i in range(1, len(timestamps)):
                delay = (timestamps[i] - timestamps[i-1]).total_seconds() * 1000
                if 0 < delay < 60000:  # Filter outliers
                    delays.append(delay)
            
            if delays:
                sig.avg_inter_command_delay = sum(delays) / len(delays)
                
                # Variance calculation
                if len(delays) >= 2:
                    mean = sig.avg_inter_command_delay
                    variance = sum((d - mean) ** 2 for d in delays) / len(delays)
                    sig.delay_variance = math.sqrt(variance)
                
                # Command velocity
                total_time = (timestamps[-1] - timestamps[0]).total_seconds()
                if total_time > 0:
                    sig.command_velocity = len(commands) / total_time
        
        # Tool switching analysis
        last_category = None
        tool_switches = []
        
        for i, cmd in enumerate(commands):
            command = cmd["command"].lower()
            current_category = None
            
            for category, tools in self.TOOL_CATEGORIES.items():
                if any(tool in command for tool in tools):
                    current_category = category
                    break
            
            if current_category and last_category and current_category != last_category:
                sig.tool_switch_count += 1
                if i > 0 and len(timestamps) > i:
                    switch_delay = (timestamps[i] - timestamps[i-1]).total_seconds() * 1000
                    tool_switches.append(switch_delay)
            
            last_category = current_category
        
        if tool_switches:
            sig.tool_switch_latency = sum(tool_switches) / len(tool_switches)
        
        # Entropy analysis (command syntax complexity)
        all_commands = " ".join(cmd["command"] for cmd in commands)
        sig.entropy_score = self._calculate_entropy(all_commands)
        
        # Retry detection
        command_texts = [cmd["command"].strip() for cmd in commands]
        retry_patterns = defaultdict(int)
        for c in command_texts:
            # Normalize for retry detection
            normalized = re.sub(r'\d+', 'N', c)
            retry_patterns[normalized] += 1
        
        sig.retry_count = sum(1 for count in retry_patterns.values() if count > 1)
    
    def _calculate_entropy(self, text: str) -> float:
        """Calculate Shannon entropy of text"""
        if not text:
            return 0.0
        
        freq = defaultdict(int)
        for char in text:
            freq[char] += 1
        
        entropy = 0.0
        length = len(text)
        for count in freq.values():
            p = count / length
            if p > 0:
                entropy -= p * math.log2(p)
        
        return entropy
    
    def _analyze_intents(self, assessment: AATLAssessment, commands: List[Dict]):
        """Analyze and accumulate intents"""
        for cmd in commands[-20:]:  # Analyze recent commands
            command = cmd["command"].lower()
            timestamp = cmd["timestamp"]
            
            for intent, patterns in self.INTENT_PATTERNS.items():
                for pattern in patterns:
                    if re.search(pattern, command, re.IGNORECASE):
                        assessment.intent_accumulation.add_intent(intent, 1.0, timestamp)
                        break
    
    def _calculate_plausibility(self, assessment: AATLAssessment):
        """Calculate human vs machine plausibility scores"""
        sig = assessment.behavior_signature
        
        machine_score = 0.0
        indicators = []
        
        # Timing analysis
        if sig.avg_inter_command_delay < self.MACHINE_TIMING["min_human_delay"]:
            machine_score += 0.25
            indicators.append(f"fast_typing:{sig.avg_inter_command_delay:.0f}ms")
        
        if sig.delay_variance < self.MACHINE_TIMING["max_machine_variance"]:
            machine_score += 0.2
            indicators.append(f"consistent_timing:variance={sig.delay_variance:.0f}ms")
        
        # Tool switching speed
        if sig.tool_switch_latency > 0 and sig.tool_switch_latency < self.MACHINE_TIMING["tool_switch_threshold"]:
            machine_score += 0.2
            indicators.append(f"fast_tool_switch:{sig.tool_switch_latency:.0f}ms")
        
        # Command velocity
        if sig.command_velocity > 0.5:  # More than 1 command per 2 seconds
            machine_score += 0.15
            indicators.append(f"high_velocity:{sig.command_velocity:.2f}cmd/s")
        
        # Goal convergence
        if assessment.intent_accumulation.goal_convergence_score > 0.7:
            machine_score += 0.1
            indicators.append(f"focused_goal:{assessment.intent_accumulation.goal_convergence_score:.2f}")
        
        # Retry patterns (machines retry systematically)
        if sig.retry_count > 3:
            machine_score += 0.1
            indicators.append(f"systematic_retries:{sig.retry_count}")
        
        assessment.machine_plausibility = min(machine_score, 1.0)
        assessment.human_plausibility = 1.0 - assessment.machine_plausibility
        assessment.indicators = indicators
    
    def _classify_actor(self, assessment: AATLAssessment):
        """Classify the type of actor based on analysis"""
        mp = assessment.machine_plausibility
        
        if mp >= 0.85:
            assessment.actor_type = ThreatActorType.AUTONOMOUS_AGENT
            assessment.actor_confidence = mp
        elif mp >= 0.6:
            assessment.actor_type = ThreatActorType.AI_ASSISTED
            assessment.actor_confidence = mp
        elif mp >= 0.4:
            assessment.actor_type = ThreatActorType.AUTOMATED_SCRIPT
            assessment.actor_confidence = 1.0 - mp
        else:
            assessment.actor_type = ThreatActorType.HUMAN
            assessment.actor_confidence = 1.0 - mp
    
    def _determine_lifecycle_stage(self, assessment: AATLAssessment):
        """Determine the current attack lifecycle stage"""
        intent = assessment.intent_accumulation.primary_intent
        
        stage_mapping = {
            "reconnaissance": AgentLifecycleStage.RECONNAISSANCE,
            "credential_access": AgentLifecycleStage.CREDENTIAL_ACCESS,
            "privilege_escalation": AgentLifecycleStage.PRIVILEGE_ESCALATION,
            "lateral_movement": AgentLifecycleStage.LATERAL_MOVEMENT,
            "persistence": AgentLifecycleStage.PERSISTENCE,
            "defense_evasion": AgentLifecycleStage.DEFENSE_EVASION,
            "exfil_prep": AgentLifecycleStage.EXFILTRATION,
            "data_staging": AgentLifecycleStage.COLLECTION
        }
        
        assessment.lifecycle_stage = stage_mapping.get(intent, AgentLifecycleStage.RECONNAISSANCE)
    
    def _calculate_threat_score(self, assessment: AATLAssessment):
        """Calculate overall threat score"""
        score = 0.0
        
        # Machine plausibility contributes significantly
        score += assessment.machine_plausibility * 40
        
        # Lifecycle stage risk
        stage_risk = {
            AgentLifecycleStage.RECONNAISSANCE: 10,
            AgentLifecycleStage.INITIAL_ACCESS: 20,
            AgentLifecycleStage.EXECUTION: 30,
            AgentLifecycleStage.PERSISTENCE: 40,
            AgentLifecycleStage.PRIVILEGE_ESCALATION: 50,
            AgentLifecycleStage.CREDENTIAL_ACCESS: 60,
            AgentLifecycleStage.LATERAL_MOVEMENT: 70,
            AgentLifecycleStage.COLLECTION: 75,
            AgentLifecycleStage.EXFILTRATION: 90,
            AgentLifecycleStage.IMPACT: 100
        }
        score += stage_risk.get(assessment.lifecycle_stage, 10) * 0.4
        
        # Goal convergence amplifies threat
        score += assessment.intent_accumulation.goal_convergence_score * 20
        
        assessment.threat_score = min(score, 100)
        
        if assessment.threat_score >= 80:
            assessment.threat_level = "critical"
        elif assessment.threat_score >= 60:
            assessment.threat_level = "high"
        elif assessment.threat_score >= 40:
            assessment.threat_level = "medium"
        else:
            assessment.threat_level = "low"
    
    def _recommend_response(self, assessment: AATLAssessment):
        """Recommend response strategy based on assessment"""
        mp = assessment.machine_plausibility
        stage = assessment.lifecycle_stage
        threat = assessment.threat_score
        
        # Default recommendations
        actions = []
        
        if threat < 30:
            assessment.recommended_strategy = ResponseStrategy.OBSERVE
            actions = ["monitor_session", "collect_telemetry"]
            
        elif threat < 50:
            assessment.recommended_strategy = ResponseStrategy.SLOW
            actions = ["throttle_commands", "inject_latency", "increase_logging"]
            
        elif threat < 70:
            assessment.recommended_strategy = ResponseStrategy.POISON
            actions = ["deploy_decoy_data", "inject_false_responses", "honeypot_redirect"]
            
        elif threat < 85:
            assessment.recommended_strategy = ResponseStrategy.DECEIVE
            actions = ["full_honeypot_engagement", "fake_success_responses", "capture_triage_bundle"]
            
        elif mp >= 0.9:
            assessment.recommended_strategy = ResponseStrategy.ERADICATE
            actions = ["isolate_host", "kill_process_tree", "capture_memory", "incident_response"]
            
        else:
            assessment.recommended_strategy = ResponseStrategy.CONTAIN
            actions = ["isolate_host", "preserve_evidence", "notify_soc"]
        
        # Stage-specific additions
        if stage == AgentLifecycleStage.CREDENTIAL_ACCESS:
            actions.append("rotate_credentials")
        elif stage == AgentLifecycleStage.LATERAL_MOVEMENT:
            actions.append("block_lateral_connections")
        elif stage == AgentLifecycleStage.EXFILTRATION:
            actions.insert(0, "cut_network_egress")
        
        assessment.recommended_actions = actions
    
    async def _store_assessment(self, assessment: AATLAssessment):
        """Store assessment in database"""
        try:
            await self.db.aatl_assessments.update_one(
                {"session_id": assessment.session_id, "host_id": assessment.host_id},
                {"$set": assessment.to_dict()},
                upsert=True
            )
        except Exception as e:
            logger.error(f"Failed to store AATL assessment: {e}")
    
    async def get_assessment(self, host_id: str, session_id: str) -> Optional[Dict]:
        """Get assessment for a session"""
        session_key = f"{host_id}:{session_id}"
        if session_key in self.active_sessions:
            return self.active_sessions[session_key].to_dict()
        
        result = await self.db.aatl_assessments.find_one(
            {"session_id": session_id, "host_id": host_id},
            {"_id": 0}
        )
        return result
    
    async def get_all_assessments(self, min_threat: float = 0) -> List[Dict]:
        """Get all assessments above threat threshold"""
        cursor = self.db.aatl_assessments.find(
            {"threat_score": {"$gte": min_threat}},
            {"_id": 0}
        ).sort("threat_score", -1)
        return await cursor.to_list(100)
    
    def score_http_request(
        self,
        behavior_flags: Dict[str, Any],
        timing_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Derive AATL machine_plausibility from HTTP request signals.

        This is the synchronous counterpart to process_cli_event() for HTTP
        traffic entering via the deception router.  It applies the same
        machine-timing thresholds that _calculate_plausibility() uses for CLI
        streams, but operates on per-request behavioral flags and optional
        timing telemetry supplied by the caller.

        Returns a dict with:
            machine_plausibility  float  0-1 (higher = more machine-like)
            actor_type            str    ThreatActorType value
            indicators            list   Human-readable detection reasons
        """
        machine_score = 0.0
        indicators: List[str] = []

        # ── Timing signals ────────────────────────────────────────────────────
        if timing_data:
            inter_request_ms = float(timing_data.get("inter_request_ms", 9999))
            timing_variance_ms = float(timing_data.get("timing_variance_ms", 9999))
            request_velocity = float(timing_data.get("request_velocity", 0.0))

            if inter_request_ms < self.MACHINE_TIMING["min_human_delay"]:
                machine_score += 0.25
                indicators.append(f"fast_request_cadence:{inter_request_ms:.0f}ms")

            if timing_variance_ms < self.MACHINE_TIMING["max_machine_variance"]:
                machine_score += 0.20
                indicators.append(f"low_timing_variance:{timing_variance_ms:.0f}ms")

            if request_velocity > 0.5:  # >1 req per 2 seconds
                machine_score += 0.15
                indicators.append(f"high_request_velocity:{request_velocity:.2f}req/s")

        # ── Behavioral signals ────────────────────────────────────────────────
        agenticity_score = float(behavior_flags.get("agenticity_score", 0.0))
        if agenticity_score >= 0.65:
            machine_score += 0.25
            indicators.append(f"agenticity_high:{agenticity_score:.3f}")
        elif agenticity_score >= 0.50:
            machine_score += 0.15
            indicators.append(f"agenticity_moderate:{agenticity_score:.3f}")

        if behavior_flags.get("decoy_touched"):
            machine_score += 0.10
            indicators.append("decoy_pebble_triggered")

        # ── AATL actor-type override ──────────────────────────────────────────
        # The caller (harness) may already supply aatl_actor_type; use it as a
        # tiebreaker — if it already says autonomous_ai, floor machine_score at
        # 0.5 so it's always above the routing threshold.
        if behavior_flags.get("aatl_actor_type") == "autonomous_ai":
            machine_score = max(machine_score, 0.50)

        machine_plausibility = min(machine_score, 1.0)

        # Classify using the same thresholds as _classify_actor()
        if machine_plausibility >= 0.85:
            actor_type = ThreatActorType.AUTONOMOUS_AGENT.value
        elif machine_plausibility >= 0.60:
            actor_type = ThreatActorType.AI_ASSISTED.value
        elif machine_plausibility >= 0.40:
            actor_type = ThreatActorType.AUTOMATED_SCRIPT.value
        else:
            actor_type = ThreatActorType.HUMAN.value

        return {
            "machine_plausibility": machine_plausibility,
            "actor_type": actor_type,
            "indicators": indicators,
        }

    async def get_threat_summary(self) -> Dict:
        """Get summary of current threats"""
        pipeline = [
            {"$group": {
                "_id": "$actor_type",
                "count": {"$sum": 1},
                "avg_threat": {"$avg": "$threat_score"},
                "max_threat": {"$max": "$threat_score"}
            }}
        ]
        by_actor = await self.db.aatl_assessments.aggregate(pipeline).to_list(10)
        
        pipeline = [
            {"$group": {
                "_id": "$lifecycle_stage",
                "count": {"$sum": 1}
            }}
        ]
        by_stage = await self.db.aatl_assessments.aggregate(pipeline).to_list(20)
        
        pipeline = [
            {"$group": {
                "_id": "$threat_level",
                "count": {"$sum": 1}
            }}
        ]
        by_level = await self.db.aatl_assessments.aggregate(pipeline).to_list(10)
        
        total = await self.db.aatl_assessments.count_documents({})
        autonomous = await self.db.aatl_assessments.count_documents({"actor_type": "autonomous_agent"})
        
        return {
            "total_sessions": total,
            "autonomous_agent_sessions": autonomous,
            "by_actor_type": {item["_id"]: item for item in by_actor if item["_id"]},
            "by_lifecycle_stage": {item["_id"]: item["count"] for item in by_stage if item["_id"]},
            "by_threat_level": {item["_id"]: item["count"] for item in by_level if item["_id"]}
        }


# Global instance
_aatl_engine: AutonomousAgentThreatLayer = None


def get_aatl_engine() -> AutonomousAgentThreatLayer:
    """Return the global AATL engine, lazy-initialising with db=None when needed.

    score_http_request() is fully stateless (no DB reads/writes) so a db=None
    instance is sufficient for all per-request AATL scoring paths.  A real DB
    connection is only required for process_cli_event() / get_threat_summary()
    which need persistence — those callers must call init_aatl_engine(db) before
    using those methods.
    """
    global _aatl_engine
    if _aatl_engine is None:
        _aatl_engine = AutonomousAgentThreatLayer(db=None)
    return _aatl_engine


async def init_aatl_engine(db):
    global _aatl_engine
    _aatl_engine = AutonomousAgentThreatLayer(db)
    return _aatl_engine
