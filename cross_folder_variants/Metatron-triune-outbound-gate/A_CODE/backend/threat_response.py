"""
Agentic Threat Response Engine
==============================
Fully autonomous threat response system with:
- Automated IP blocking (iptables/firewalld)
- Twilio SMS emergency alerts
- OpenClaw CLI integration for AI-powered automation
- Threat intelligence sharing
- Self-healing capabilities
- Network isolation
- Forensic data collection

AI AGENTIC DEFENSE FEATURES:
- AI Threat Pattern Recognition & Response
- Defense Escalation Matrix (OBSERVE → ERADICATE)
- Tarpit & Deception Tactics
- Adaptive Counter-Measures
- SOAR Engine Integration

This module makes the Anti-AI Defense System truly agentic by enabling
autonomous decision-making and response actions.
"""
import os
import json
import logging
import asyncio
import subprocess
import platform
import hashlib
import shutil
import random
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, asdict, field
from enum import Enum
from pathlib import Path
import httpx
from runtime_paths import ensure_data_dir
from services.agenticity import compute_agenticity_score, compute_exhaustion_metrics

try:
    from services.resonance_service import get_resonance_service
    from services.world_events import emit_world_event
except Exception:
    get_resonance_service = None
    emit_world_event = None

logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================

class ThreatResponseConfig:
    """Configuration for the threat response engine"""
    def __init__(self):
        # Twilio SMS
        self.twilio_account_sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
        self.twilio_auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
        self.twilio_phone_number = os.environ.get("TWILIO_PHONE_NUMBER", "")
        self.emergency_contacts = os.environ.get("EMERGENCY_SMS_CONTACTS", "").split(",")
        
        # OpenClaw
        self.openclaw_enabled = os.environ.get("OPENCLAW_ENABLED", "false").lower() == "true"
        self.openclaw_gateway_url = os.environ.get("OPENCLAW_GATEWAY_URL", "http://localhost:3030")
        self.openclaw_api_key = os.environ.get("OPENCLAW_API_KEY", "")
        
        # Auto-response settings
        self.auto_block_enabled = os.environ.get("AUTO_BLOCK_ENABLED", "true").lower() == "true"
        self.auto_isolate_enabled = os.environ.get("AUTO_ISOLATE_ENABLED", "false").lower() == "true"
        self.block_duration_hours = int(os.environ.get("BLOCK_DURATION_HOURS", "24"))
        
        # Threat intelligence
        self.threat_intel_sharing = os.environ.get("THREAT_INTEL_SHARING", "false").lower() == "true"
        self.threat_intel_api_url = os.environ.get("THREAT_INTEL_API_URL", "")
        
        # Response thresholds
        self.critical_threat_threshold = 3  # Attacks before auto-block
        self.sms_alert_severity = ["critical"]  # Severities that trigger SMS
        
    @property
    def twilio_enabled(self) -> bool:
        return bool(self.twilio_account_sid and self.twilio_auth_token and self.twilio_phone_number)

config = ThreatResponseConfig()

# =============================================================================
# ENUMS AND DATA MODELS
# =============================================================================

class ResponseAction(Enum):
    # Standard Actions
    BLOCK_IP = "block_ip"
    UNBLOCK_IP = "unblock_ip"
    ISOLATE_HOST = "isolate_host"
    QUARANTINE_FILE = "quarantine_file"
    KILL_PROCESS = "kill_process"
    SEND_ALERT = "send_alert"
    COLLECT_FORENSICS = "collect_forensics"
    ROLLBACK_CHANGES = "rollback_changes"
    NOTIFY_SOC = "notify_soc"
    ESCALATE = "escalate"
    
    # AI Agentic Defense Actions
    THROTTLE_SESSION = "throttle_session"
    INJECT_LATENCY = "inject_latency"
    DEPLOY_DECOY = "deploy_decoy"
    ENGAGE_TARPIT = "engage_tarpit"
    FEED_DISINFORMATION = "feed_disinformation"
    CAPTURE_TRIAGE = "capture_triage"
    ROTATE_CREDENTIALS = "rotate_credentials"
    INVOKE_ML_ANALYSIS = "invoke_ml_analysis"
    SYNC_THREAT_INTEL = "sync_threat_intel"
    EXECUTE_CONTAINMENT_CHAIN = "execute_containment_chain"

class ResponseStatus(Enum):
    PENDING = "pending"
    EXECUTING = "executing"
    SUCCESS = "success"
    FAILED = "failed"
    ROLLBACK = "rollback"
    DEGRADED = "degraded"  # Partial success

class DefenseEscalationLevel(Enum):
    """Defense escalation levels matching SOAR engine"""
    OBSERVE = "observe"      # Level 0: Monitor only
    DEGRADE = "degrade"      # Level 1: Slow down attacker
    DECEIVE = "deceive"      # Level 2: Deploy decoys, feed false data
    CONTAIN = "contain"      # Level 3: Limit blast radius
    ISOLATE = "isolate"      # Level 4: Full network isolation
    ERADICATE = "eradicate"  # Level 5: Kill processes, wipe sessions

class AIThreatIndicator(Enum):
    """Indicators of AI/autonomous threat"""
    MACHINE_PACING = "machine_pacing"
    RAPID_ITERATION = "rapid_iteration"
    SYSTEMATIC_SCAN = "systematic_scan"
    GOAL_PERSISTENCE = "goal_persistence"
    TOOL_SWITCHING = "tool_switching"
    CREDENTIAL_HARVESTING = "credential_harvesting"
    LATERAL_MOVEMENT = "lateral_movement"
    EXFIL_PREPARATION = "exfil_preparation"

@dataclass
class ThreatContext:
    """Context information about a detected threat"""
    threat_id: str
    threat_type: str
    severity: str
    source_ip: Optional[str] = None
    target_ip: Optional[str] = None
    target_path: Optional[str] = None
    process_id: Optional[int] = None
    agent_id: Optional[str] = None
    agent_name: Optional[str] = None
    indicators: List[str] = field(default_factory=list)
    raw_data: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    # AI Threat Assessment Fields
    is_ai_threat: bool = False
    machine_likelihood: float = 0.0
    ai_indicators: List[str] = field(default_factory=list)
    burstiness_score: float = 0.0
    tool_switch_latency_ms: int = 0
    goal_persistence: float = 0.0
    session_id: Optional[str] = None
    decoy_touched: bool = False
    recommended_escalation: str = "observe"

@dataclass
class AIThreatAssessment:
    """Assessment of AI threat characteristics"""
    session_id: str
    host_id: str
    machine_likelihood: float
    confidence_level: str  # low, medium, high, critical
    burstiness_score: float
    tool_switch_latency_ms: int
    goal_persistence: float
    dominant_intents: List[str]
    decoy_touched: bool
    recommended_escalation: DefenseEscalationLevel
    agenticity_score: float = 0.0
    agenticity_classification: str = "unknown"
    agenticity_feature_vector: Dict[str, float] = field(default_factory=dict)
    cbr: float = 0.0
    tbcr: float = 0.0
    cdi: float = 0.0
    assessment_timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

@dataclass
class ResponseResult:
    """Result of a response action"""
    action: ResponseAction
    status: ResponseStatus
    message: str
    executed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    rollback_info: Optional[Dict[str, Any]] = None
    details: Dict[str, Any] = field(default_factory=dict)

# =============================================================================
# IP BLOCKING / FIREWALL MANAGEMENT
# =============================================================================

class FirewallManager:
    """Manages firewall rules for automated IP blocking"""
    
    # Track blocked IPs for auto-unblock
    blocked_ips: Dict[str, datetime] = {}
    
    @staticmethod
    def _detect_firewall() -> str:
        """Detect which firewall is available"""
        if platform.system() == "Windows":
            return "windows"
        elif shutil.which("firewall-cmd"):
            return "firewalld"
        elif shutil.which("iptables"):
            return "iptables"
        elif shutil.which("ufw"):
            return "ufw"
        elif shutil.which("pfctl"):
            return "pf"
        return "none"
    
    @classmethod
    async def block_ip(cls, ip: str, reason: str = "", duration_hours: int = 24) -> ResponseResult:
        """Block an IP address"""
        firewall = cls._detect_firewall()
        cmd = None
        rollback_cmd = None
        
        try:
            if firewall == "iptables":
                cmd = f"sudo iptables -A INPUT -s {ip} -j DROP"
                rollback_cmd = f"sudo iptables -D INPUT -s {ip} -j DROP"
            elif firewall == "firewalld":
                cmd = f"sudo firewall-cmd --add-rich-rule='rule family=ipv4 source address={ip} reject' --permanent && sudo firewall-cmd --reload"
                rollback_cmd = f"sudo firewall-cmd --remove-rich-rule='rule family=ipv4 source address={ip} reject' --permanent && sudo firewall-cmd --reload"
            elif firewall == "ufw":
                cmd = f"sudo ufw deny from {ip}"
                rollback_cmd = f"sudo ufw delete deny from {ip}"
            elif firewall == "windows":
                cmd = f'netsh advfirewall firewall add rule name="Block {ip}" dir=in action=block remoteip={ip}'
                rollback_cmd = f'netsh advfirewall firewall delete rule name="Block {ip}"'
            else:
                return ResponseResult(
                    action=ResponseAction.BLOCK_IP,
                    status=ResponseStatus.FAILED,
                    message=f"No supported firewall found on this system",
                    details={"ip": ip, "firewall": "none"}
                )
            
            # Execute block command
            process = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                cls.blocked_ips[ip] = datetime.now(timezone.utc) + timedelta(hours=duration_hours)
                logger.info(f"Blocked IP {ip}: {reason}")
                
                return ResponseResult(
                    action=ResponseAction.BLOCK_IP,
                    status=ResponseStatus.SUCCESS,
                    message=f"Successfully blocked IP {ip}",
                    rollback_info={"command": rollback_cmd, "ip": ip},
                    details={"ip": ip, "reason": reason, "duration_hours": duration_hours, "firewall": firewall}
                )
            else:
                return ResponseResult(
                    action=ResponseAction.BLOCK_IP,
                    status=ResponseStatus.FAILED,
                    message=f"Failed to block IP: {stderr.decode()}",
                    details={"ip": ip, "error": stderr.decode()}
                )
                
        except Exception as e:
            logger.error(f"Error blocking IP {ip}: {e}")
            return ResponseResult(
                action=ResponseAction.BLOCK_IP,
                status=ResponseStatus.FAILED,
                message=f"Error: {str(e)}",
                details={"ip": ip, "error": str(e)}
            )
    
    @classmethod
    async def unblock_ip(cls, ip: str) -> ResponseResult:
        """Unblock a previously blocked IP"""
        firewall = cls._detect_firewall()
        cmd = None
        
        try:
            if firewall == "iptables":
                cmd = f"sudo iptables -D INPUT -s {ip} -j DROP"
            elif firewall == "firewalld":
                cmd = f"sudo firewall-cmd --remove-rich-rule='rule family=ipv4 source address={ip} reject' --permanent && sudo firewall-cmd --reload"
            elif firewall == "ufw":
                cmd = f"sudo ufw delete deny from {ip}"
            elif firewall == "windows":
                cmd = f'netsh advfirewall firewall delete rule name="Block {ip}"'
            else:
                return ResponseResult(
                    action=ResponseAction.UNBLOCK_IP,
                    status=ResponseStatus.FAILED,
                    message="No supported firewall found"
                )
            
            process = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                cls.blocked_ips.pop(ip, None)
                logger.info(f"Unblocked IP {ip}")
                return ResponseResult(
                    action=ResponseAction.UNBLOCK_IP,
                    status=ResponseStatus.SUCCESS,
                    message=f"Successfully unblocked IP {ip}"
                )
            else:
                return ResponseResult(
                    action=ResponseAction.UNBLOCK_IP,
                    status=ResponseStatus.FAILED,
                    message=f"Failed to unblock: {stderr.decode()}"
                )
                
        except Exception as e:
            return ResponseResult(
                action=ResponseAction.UNBLOCK_IP,
                status=ResponseStatus.FAILED,
                message=str(e)
            )
    
    @classmethod
    async def cleanup_expired_blocks(cls):
        """Remove expired IP blocks"""
        now = datetime.now(timezone.utc)
        expired = [ip for ip, expiry in cls.blocked_ips.items() if expiry < now]
        
        for ip in expired:
            await cls.unblock_ip(ip)
            logger.info(f"Auto-unblocked expired IP: {ip}")

firewall = FirewallManager()

# =============================================================================
# TWILIO SMS ALERTS
# =============================================================================

class SMSAlertService:
    """Send emergency SMS alerts via Twilio"""
    
    @staticmethod
    async def send_emergency_sms(
        message: str,
        recipients: Optional[List[str]] = None,
        threat_context: Optional[ThreatContext] = None
    ) -> ResponseResult:
        """Send emergency SMS alert to all configured contacts"""
        if not config.twilio_enabled:
            return ResponseResult(
                action=ResponseAction.SEND_ALERT,
                status=ResponseStatus.FAILED,
                message="Twilio SMS not configured"
            )
        
        to_numbers = recipients or [n.strip() for n in config.emergency_contacts if n.strip()]
        if not to_numbers:
            return ResponseResult(
                action=ResponseAction.SEND_ALERT,
                status=ResponseStatus.FAILED,
                message="No emergency contacts configured"
            )
        
        # Build alert message
        alert_text = f"🚨 SECURITY ALERT\n{message}"
        if threat_context:
            alert_text += f"\n\nType: {threat_context.threat_type}"
            alert_text += f"\nSeverity: {threat_context.severity.upper()}"
            if threat_context.source_ip:
                alert_text += f"\nSource: {threat_context.source_ip}"
        
        # Truncate to SMS limit
        alert_text = alert_text[:1500]
        
        try:
            from twilio.rest import Client
            client = Client(config.twilio_account_sid, config.twilio_auth_token)
            
            sent_count = 0
            errors = []
            
            for number in to_numbers:
                try:
                    message_obj = client.messages.create(
                        body=alert_text,
                        from_=config.twilio_phone_number,
                        to=number
                    )
                    sent_count += 1
                    logger.info(f"SMS sent to {number}: {message_obj.sid}")
                except Exception as e:
                    errors.append(f"{number}: {str(e)}")
            
            if sent_count > 0:
                return ResponseResult(
                    action=ResponseAction.SEND_ALERT,
                    status=ResponseStatus.SUCCESS,
                    message=f"SMS sent to {sent_count}/{len(to_numbers)} contacts",
                    details={"sent": sent_count, "total": len(to_numbers), "errors": errors}
                )
            else:
                return ResponseResult(
                    action=ResponseAction.SEND_ALERT,
                    status=ResponseStatus.FAILED,
                    message="Failed to send any SMS",
                    details={"errors": errors}
                )
                
        except Exception as e:
            return ResponseResult(
                action=ResponseAction.SEND_ALERT,
                status=ResponseStatus.FAILED,
                message=str(e)
            )

sms_service = SMSAlertService()

# =============================================================================
# OPENCLAW AI AGENT INTEGRATION
# =============================================================================

class OpenClawAgent:
    """
    Integration with OpenClaw for AI-powered autonomous threat response.
    OpenClaw provides agentic AI capabilities for security automation.
    """
    
    @staticmethod
    async def is_available() -> bool:
        """Check if OpenClaw gateway is available"""
        if not config.openclaw_enabled:
            return False
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{config.openclaw_gateway_url}/health",
                    timeout=5
                )
                return response.status_code == 200
        except Exception:
            return False

    @staticmethod
    async def get_status() -> Dict[str, Any]:
        """Get OpenClaw integration status for API consumers."""
        enabled = config.openclaw_enabled
        available = await OpenClawAgent.is_available() if enabled else False

        return {
            "enabled": enabled,
            "connected": available,
            "gateway_url": config.openclaw_gateway_url,
            "has_api_key": bool(config.openclaw_api_key),
            "status": "connected" if available else ("disabled" if not enabled else "unavailable")
        }
    
    @staticmethod
    async def execute_security_task(
        task: str,
        context: Optional[ThreatContext] = None,
        tools: Optional[List[str]] = None
    ) -> ResponseResult:
        """
        Execute a security task using OpenClaw AI agent.
        
        The agent can autonomously:
        - Analyze threat patterns
        - Recommend response actions
        - Execute security scripts
        - Generate incident reports
        - Correlate with threat intelligence
        """
        if not config.openclaw_enabled:
            return ResponseResult(
                action=ResponseAction.NOTIFY_SOC,
                status=ResponseStatus.FAILED,
                message="OpenClaw integration not enabled"
            )
        
        if not await OpenClawAgent.is_available():
            return ResponseResult(
                action=ResponseAction.NOTIFY_SOC,
                status=ResponseStatus.FAILED,
                message="OpenClaw gateway not available"
            )
        
        # Build the prompt for the AI agent
        system_prompt = """You are a security operations AI agent integrated with the Anti-AI Defense System.
Your role is to analyze threats, recommend response actions, and help automate incident response.
Always prioritize:
1. Containing the threat
2. Preserving forensic evidence
3. Minimizing business impact
4. Following security best practices"""
        
        user_prompt = f"Security Task: {task}"
        if context:
            user_prompt += f"\n\nThreat Context:\n- Type: {context.threat_type}\n- Severity: {context.severity}"
            if context.source_ip:
                user_prompt += f"\n- Source IP: {context.source_ip}"
            if context.indicators:
                user_prompt += f"\n- Indicators: {', '.join(context.indicators)}"
        
        try:
            headers = {"Content-Type": "application/json"}
            if config.openclaw_api_key:
                headers["Authorization"] = f"Bearer {config.openclaw_api_key}"
            
            payload = {
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "tools": tools or ["file_access", "command_execution", "web_search"],
                "stream": False
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{config.openclaw_gateway_url}/v1/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=60
                )
                
                if response.status_code == 200:
                    result = response.json()
                    ai_response = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                    
                    return ResponseResult(
                        action=ResponseAction.NOTIFY_SOC,
                        status=ResponseStatus.SUCCESS,
                        message="OpenClaw task completed",
                        details={
                            "task": task,
                            "ai_response": ai_response,
                            "tools_available": tools or []
                        }
                    )
                else:
                    return ResponseResult(
                        action=ResponseAction.NOTIFY_SOC,
                        status=ResponseStatus.FAILED,
                        message=f"OpenClaw returned {response.status_code}"
                    )
                    
        except Exception as e:
            return ResponseResult(
                action=ResponseAction.NOTIFY_SOC,
                status=ResponseStatus.FAILED,
                message=str(e)
            )
    
    @staticmethod
    async def analyze_threat(context: ThreatContext) -> Dict[str, Any]:
        """Use OpenClaw to analyze a threat and recommend actions"""
        result = await OpenClawAgent.execute_security_task(
            task="Analyze this security threat and recommend response actions. "
                 "Provide specific, actionable steps for containment and remediation.",
            context=context,
            tools=["web_search", "file_access"]
        )
        
        if result.status == ResponseStatus.SUCCESS:
            return {
                "analysis": result.details.get("ai_response", ""),
                "recommendations": []  # Would parse from AI response
            }
        return {"analysis": "Analysis unavailable", "recommendations": []}

openclaw = OpenClawAgent()

# =============================================================================
# FORENSIC DATA COLLECTION
# =============================================================================

class ForensicsCollector:
    """Collect forensic data for incident investigation"""
    
    FORENSICS_DIR = ensure_data_dir("forensics")

    @classmethod
    async def get_evidence_by_id(cls, incident_id: str) -> dict:
        """Retrieve previously collected forensic evidence for an incident"""
        incident_dir = cls.FORENSICS_DIR / incident_id[:12]
        if not incident_dir.exists():
            return {"incident_id": incident_id, "status": "not_found", "files": {}}
        files: dict = {}
        for f in incident_dir.iterdir():
            if f.is_file() and f.suffix == ".json":
                try:
                    files[f.name] = json.loads(f.read_text())
                except Exception:
                    files[f.name] = f.read_text()
        return {"incident_id": incident_id, "status": "found", "files": files}

    @classmethod
    async def collect_incident_data(cls, context: ThreatContext) -> ResponseResult:
        """Collect all relevant forensic data for an incident"""
        cls.FORENSICS_DIR.mkdir(parents=True, exist_ok=True)
        
        incident_id = hashlib.md5(
            f"{context.threat_id}{context.timestamp}".encode()
        ).hexdigest()[:12]
        
        incident_dir = cls.FORENSICS_DIR / incident_id
        incident_dir.mkdir(exist_ok=True)
        
        collected = []
        
        # Save threat context
        with open(incident_dir / "threat_context.json", "w") as f:
            json.dump(asdict(context), f, indent=2)
        collected.append("threat_context.json")
        
        # Collect system state
        try:
            # Network connections
            proc = await asyncio.create_subprocess_shell(
                "netstat -tuln 2>/dev/null || ss -tuln",
                stdout=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            with open(incident_dir / "network_connections.txt", "w") as f:
                f.write(stdout.decode())
            collected.append("network_connections.txt")
            
            # Process list
            proc = await asyncio.create_subprocess_shell(
                "ps auxf 2>/dev/null || ps aux",
                stdout=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            with open(incident_dir / "process_list.txt", "w") as f:
                f.write(stdout.decode())
            collected.append("process_list.txt")
            
            # Recent auth logs
            if Path("/var/log/auth.log").exists():
                proc = await asyncio.create_subprocess_shell(
                    "tail -500 /var/log/auth.log",
                    stdout=asyncio.subprocess.PIPE
                )
                stdout, _ = await proc.communicate()
                with open(incident_dir / "auth_log.txt", "w") as f:
                    f.write(stdout.decode())
                collected.append("auth_log.txt")
            
            # IP-specific data if we have a source IP
            if context.source_ip:
                proc = await asyncio.create_subprocess_shell(
                    f"whois {context.source_ip} 2>/dev/null | head -100",
                    stdout=asyncio.subprocess.PIPE
                )
                stdout, _ = await proc.communicate()
                with open(incident_dir / "ip_whois.txt", "w") as f:
                    f.write(stdout.decode())
                collected.append("ip_whois.txt")
                
        except Exception as e:
            logger.error(f"Forensics collection error: {e}")
        
        return ResponseResult(
            action=ResponseAction.COLLECT_FORENSICS,
            status=ResponseStatus.SUCCESS,
            message=f"Collected {len(collected)} forensic artifacts",
            details={
                "incident_id": incident_id,
                "path": str(incident_dir),
                "artifacts": collected
            }
        )

forensics = ForensicsCollector()

# =============================================================================
# THREAT INTELLIGENCE SHARING
# =============================================================================

class ThreatIntelligence:
    """Share and receive threat intelligence with the community"""
    
    @staticmethod
    async def share_indicator(
        indicator_type: str,
        indicator_value: str,
        threat_type: str,
        confidence: int = 80
    ) -> bool:
        """Share a threat indicator with the community"""
        if not config.threat_intel_sharing or not config.threat_intel_api_url:
            return False
        
        try:
            payload = {
                "type": indicator_type,  # ip, domain, hash, url
                "value": indicator_value,
                "threat_type": threat_type,
                "confidence": confidence,
                "source": "anti-ai-defense",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{config.threat_intel_api_url}/indicators",
                    json=payload,
                    timeout=10
                )
                return response.status_code in [200, 201]
        except Exception:
            return False
    
    @staticmethod
    async def check_indicator(indicator_type: str, indicator_value: str) -> Dict[str, Any]:
        """Check if an indicator is known malicious"""
        if not config.threat_intel_api_url:
            return {"known": False, "data": {}}
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{config.threat_intel_api_url}/indicators/{indicator_type}/{indicator_value}",
                    timeout=10
                )
                if response.status_code == 200:
                    return {"known": True, "data": response.json()}
        except Exception:
            pass
        
        return {"known": False, "data": {}}

threat_intel = ThreatIntelligence()

# =============================================================================
# AUTONOMOUS RESPONSE ENGINE
# =============================================================================

class AgenticResponseEngine:
    """
    The main autonomous threat response engine.
    Makes intelligent decisions about how to respond to threats.
    """
    
    # Track attacks per IP for threshold-based blocking
    attack_counter: Dict[str, int] = {}
    
    # Response history for audit
    response_history: List[Dict[str, Any]] = []
    _db = None
    
    @classmethod
    async def process_threat(
        cls,
        context: ThreatContext,
        auto_respond: bool = True
    ) -> List[ResponseResult]:
        """
        Process a threat and execute appropriate response actions.
        
        The engine autonomously decides:
        1. Whether to block the source IP
        2. Whether to send emergency alerts
        3. Whether to quarantine files
        4. Whether to collect forensics
        5. Whether to escalate to humans
        """
        results = []
        response_id = hashlib.md5(
            f"{context.threat_id}{datetime.now(timezone.utc).isoformat()}".encode()
        ).hexdigest()[:16]

        await cls._create_response_record(
            response_id=response_id,
            context=context,
            auto_respond=auto_respond,
            actor="engine",
        )
        await cls._transition_response_record(
            response_id=response_id,
            expected_status=ResponseStatus.PENDING.value,
            to_status=ResponseStatus.EXECUTING.value,
            actor="engine",
            reason="Threat response execution started",
            metadata={"threat_type": context.threat_type},
        )
        
        logger.info(f"Processing threat: {context.threat_type} (severity: {context.severity})")
        
        # Always collect forensics for medium+ severity
        if context.severity in ["medium", "high", "critical"]:
            forensics_result = await forensics.collect_incident_data(context)
            results.append(forensics_result)
        
        # Check threat intelligence
        if context.source_ip:
            intel = await threat_intel.check_indicator("ip", context.source_ip)
            if intel["known"]:
                context.indicators.append(f"Known malicious IP (confidence: {intel['data'].get('confidence', 'N/A')})")
                # Increase severity if known malicious
                if context.severity == "medium":
                    context.severity = "high"
        
        # Auto-block logic
        if auto_respond and config.auto_block_enabled and context.source_ip:
            # Track attacks from this IP
            cls.attack_counter[context.source_ip] = cls.attack_counter.get(context.source_ip, 0) + 1
            
            should_block = (
                context.severity == "critical" or
                cls.attack_counter[context.source_ip] >= config.critical_threat_threshold
            )
            
            if should_block:
                block_result = await firewall.block_ip(
                    context.source_ip,
                    reason=f"Auto-blocked: {context.threat_type}",
                    duration_hours=config.block_duration_hours
                )
                results.append(block_result)
                
                # Share with threat intel
                if block_result.status == ResponseStatus.SUCCESS:
                    await threat_intel.share_indicator(
                        "ip", context.source_ip, context.threat_type
                    )
        
        # SMS alerts for critical threats
        if context.severity in config.sms_alert_severity:
            sms_result = await sms_service.send_emergency_sms(
                message=f"Critical threat detected: {context.threat_type}",
                threat_context=context
            )
            results.append(sms_result)
        
        # Use OpenClaw for advanced analysis if available
        if config.openclaw_enabled:
            analysis = await openclaw.analyze_threat(context)
            if analysis.get("analysis"):
                # Log the AI analysis
                logger.info(f"OpenClaw analysis: {analysis['analysis'][:200]}...")
        
        final_status = cls._derive_final_status(results)

        # Store response history
        history_entry = {
            "response_id": response_id,
            "threat_id": context.threat_id,
            "threat_type": context.threat_type,
            "severity": context.severity,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "results": [asdict(r) for r in results],
            "auto_responded": auto_respond
        }
        cls.response_history.append(history_entry)
        
        # Trim history
        if len(cls.response_history) > 1000:
            cls.response_history = cls.response_history[-500:]
        
        await cls._transition_response_record(
            response_id=response_id,
            expected_status=ResponseStatus.EXECUTING.value,
            to_status=final_status,
            actor="engine",
            reason="Threat response execution completed",
            metadata={
                "result_count": len(results),
                "failed_count": sum(1 for r in results if r.status == ResponseStatus.FAILED),
            },
            results=[asdict(r) for r in results],
        )

        return results
    
    @classmethod
    async def get_response_stats(cls) -> Dict[str, Any]:
        """Get statistics about automated responses"""
        # Prefer durable stats from DB so dashboards remain correct after restarts.
        if cls._db is not None and hasattr(cls._db, "response_history"):
            try:
                total = await cls._db.response_history.count_documents({})

                by_severity_rows = await cls._db.response_history.aggregate(
                    [
                        {"$group": {"_id": "$severity", "count": {"$sum": 1}}},
                        {"$sort": {"count": -1}},
                    ]
                ).to_list(50)
                by_severity = {str(r.get("_id") or "unknown"): int(r.get("count") or 0) for r in by_severity_rows}

                by_action_rows = await cls._db.response_history.aggregate(
                    [
                        {"$unwind": {"path": "$results", "preserveNullAndEmptyArrays": True}},
                        {"$group": {"_id": "$results.action", "count": {"$sum": 1}}},
                        {"$sort": {"count": -1}},
                    ]
                ).to_list(50)
                by_action = {str(r.get("_id") or "unknown"): int(r.get("count") or 0) for r in by_action_rows}

                sources_row = await cls._db.response_history.aggregate(
                    [
                        {"$group": {"_id": None, "sources": {"$addToSet": "$source_ip"}}},
                        {"$project": {"_id": 0, "count": {"$size": {"$ifNull": ["$sources", []]}}}},
                    ]
                ).to_list(1)
                attack_sources = int(sources_row[0].get("count") or 0) if sources_row else 0

                # Best-effort blocked IP count: distinct source_ip where a block_ip action succeeded.
                blocked_row = await cls._db.response_history.aggregate(
                    [
                        {"$unwind": {"path": "$results", "preserveNullAndEmptyArrays": False}},
                        {"$match": {"results.action": "block_ip", "results.status": {"$in": ["success", "degraded", "completed"]}}},
                        {"$group": {"_id": "$source_ip"}},
                        {"$count": "blocked"},
                    ]
                ).to_list(1)
                blocked_ips = int(blocked_row[0].get("blocked") or 0) if blocked_row else 0

                # Merge with in-memory firewall state when present.
                blocked_ips = max(blocked_ips, len(getattr(firewall, "blocked_ips", {}) or {}))

                return {
                    "total_responses": int(total or 0),
                    "blocked_ips": blocked_ips,
                    "by_severity": by_severity,
                    "by_action": by_action,
                    "attack_sources": attack_sources,
                    "source": "db.response_history",
                }
            except Exception:
                # Fall back to in-memory path if DB aggregation fails.
                pass

        total = len(cls.response_history)
        by_severity: Dict[str, int] = {}
        by_action: Dict[str, int] = {}

        for entry in cls.response_history:
            sev = entry.get("severity", "unknown")
            by_severity[sev] = by_severity.get(sev, 0) + 1

            for result in entry.get("results", []):
                action = result.get("action", "unknown")
                by_action[action] = by_action.get(action, 0) + 1

        return {
            "total_responses": total,
            "blocked_ips": len(getattr(firewall, "blocked_ips", {}) or {}),
            "by_severity": by_severity,
            "by_action": by_action,
            "attack_sources": len(getattr(cls, "attack_counter", {}) or {}),
            "source": "memory",
        }

    @classmethod
    def configure_db(cls, db):
        """Configure an optional persistence backend for durable response records."""
        cls._db = db

    @classmethod
    def _derive_final_status(cls, results: List[ResponseResult]) -> str:
        failed = sum(1 for r in results if r.status == ResponseStatus.FAILED)
        succeeded = sum(1 for r in results if r.status == ResponseStatus.SUCCESS)

        if failed > 0 and succeeded > 0:
            return ResponseStatus.DEGRADED.value
        if failed > 0 and succeeded == 0:
            return ResponseStatus.FAILED.value
        return ResponseStatus.SUCCESS.value

    @classmethod
    def _transition_entry(
        cls,
        from_status: Optional[str],
        to_status: str,
        actor: str,
        reason: str,
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[str] = None,
    ) -> Dict[str, Any]:
        return {
            "from_status": from_status,
            "to_status": to_status,
            "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
            "actor": actor,
            "reason": reason,
            "metadata": metadata or {},
        }

    @classmethod
    async def _create_response_record(
        cls,
        response_id: str,
        context: ThreatContext,
        auto_respond: bool,
        actor: str,
    ):
        timestamp = datetime.now(timezone.utc).isoformat()
        doc = {
            "response_id": response_id,
            "threat_id": context.threat_id,
            "threat_type": context.threat_type,
            "severity": context.severity,
            "status": ResponseStatus.PENDING.value,
            "state_version": 1,
            "state_transition_log": [
                cls._transition_entry(
                    from_status=None,
                    to_status=ResponseStatus.PENDING.value,
                    actor=actor,
                    reason="Threat response record created",
                    metadata={
                        "auto_responded": auto_respond,
                        "source_ip": context.source_ip,
                    },
                    timestamp=timestamp,
                )
            ],
            "results": [],
            "auto_responded": auto_respond,
            "source_ip": context.source_ip,
            "agent_id": context.agent_id,
            "agent_name": context.agent_name,
            "timestamp": timestamp,
            "updated_at": timestamp,
        }

        if cls._db is not None and hasattr(cls._db, "response_history"):
            await cls._db.response_history.insert_one(doc)

    @classmethod
    async def _transition_response_record(
        cls,
        response_id: str,
        expected_status: str,
        to_status: str,
        actor: str,
        reason: str,
        metadata: Optional[Dict[str, Any]] = None,
        results: Optional[List[Dict[str, Any]]] = None,
    ) -> bool:
        if cls._db is None or not hasattr(cls._db, "response_history"):
            return False

        current = await cls._db.response_history.find_one(
            {"response_id": response_id},
            {"status": 1, "state_version": 1},
        )
        if not current:
            return False

        current_status = current.get("status")
        current_version = int(current.get("state_version", 0) or 0)
        if current_status != expected_status:
            return False

        transition = cls._transition_entry(
            from_status=expected_status,
            to_status=to_status,
            actor=actor,
            reason=reason,
            metadata=metadata,
        )

        update_doc = {
            "$set": {
                "status": to_status,
                "updated_at": transition["timestamp"],
            },
            "$inc": {"state_version": 1},
            "$push": {"state_transition_log": transition},
        }
        if results is not None:
            update_doc["$set"]["results"] = results

        update_result = await cls._db.response_history.update_one(
            {
                "response_id": response_id,
                "status": expected_status,
                "state_version": current_version,
            },
            update_doc,
        )
        return bool(getattr(update_result, "modified_count", 0))

    @classmethod
    async def record_manual_action(
        cls,
        action: ResponseAction,
        result: ResponseResult,
        threat_id: str,
        threat_type: str,
        severity: str,
        source_ip: Optional[str] = None,
        actor: str = "manual",
    ):
        context = ThreatContext(
            threat_id=threat_id,
            threat_type=threat_type,
            severity=severity,
            source_ip=source_ip,
        )
        response_id = hashlib.md5(
            f"{threat_id}{action.value}{datetime.now(timezone.utc).isoformat()}".encode()
        ).hexdigest()[:16]

        await cls._create_response_record(
            response_id=response_id,
            context=context,
            auto_respond=False,
            actor=actor,
        )
        await cls._transition_response_record(
            response_id=response_id,
            expected_status=ResponseStatus.PENDING.value,
            to_status=ResponseStatus.EXECUTING.value,
            actor=actor,
            reason="Manual response action started",
            metadata={"action": action.value},
        )

        terminal = result.status.value if isinstance(result.status, ResponseStatus) else str(result.status)
        await cls._transition_response_record(
            response_id=response_id,
            expected_status=ResponseStatus.EXECUTING.value,
            to_status=terminal,
            actor=actor,
            reason="Manual response action completed",
            metadata={"action": action.value},
            results=[asdict(result)],
        )

        cls.response_history.append(
            {
                "response_id": response_id,
                "threat_id": threat_id,
                "threat_type": threat_type,
                "severity": severity,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "results": [asdict(result)],
                "auto_responded": False,
                "manual": True,
            }
        )
    
    @classmethod
    def get_blocked_ips(cls) -> List[Dict[str, Any]]:
        """Get list of currently blocked IPs"""
        return [
            {"ip": ip, "expires": expiry.isoformat()}
            for ip, expiry in firewall.blocked_ips.items()
        ]

# Create global instance
response_engine = AgenticResponseEngine()

# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

async def respond_to_intrusion(
    source_ip: str,
    signature: str,
    severity: str = "high",
    agent_name: Optional[str] = None
) -> List[ResponseResult]:
    """Respond to an intrusion detection event"""
    context = ThreatContext(
        threat_id=hashlib.md5(f"{source_ip}{signature}{datetime.now().isoformat()}".encode()).hexdigest()[:12],
        threat_type="intrusion",
        severity=severity,
        source_ip=source_ip,
        agent_name=agent_name,
        indicators=[f"Signature: {signature}"]
    )
    return await response_engine.process_threat(context)

async def respond_to_malware(
    filepath: str,
    malware_name: str,
    severity: str = "critical",
    source_ip: Optional[str] = None,
    agent_name: Optional[str] = None
) -> List[ResponseResult]:
    """Respond to a malware detection event"""
    context = ThreatContext(
        threat_id=hashlib.md5(f"{filepath}{malware_name}{datetime.now().isoformat()}".encode()).hexdigest()[:12],
        threat_type="malware",
        severity=severity,
        source_ip=source_ip,
        target_path=filepath,
        agent_name=agent_name,
        indicators=[f"Malware: {malware_name}", f"File: {filepath}"]
    )
    return await response_engine.process_threat(context)

async def respond_to_port_scan(
    source_ip: str,
    ports_scanned: int,
    agent_name: Optional[str] = None
) -> List[ResponseResult]:
    """Respond to a port scanning event"""
    severity = "critical" if ports_scanned > 100 else "high" if ports_scanned > 20 else "medium"
    context = ThreatContext(
        threat_id=hashlib.md5(f"{source_ip}portscan{datetime.now().isoformat()}".encode()).hexdigest()[:12],
        threat_type="port_scan",
        severity=severity,
        source_ip=source_ip,
        agent_name=agent_name,
        indicators=[f"Ports scanned: {ports_scanned}"]
    )
    return await response_engine.process_threat(context)

async def manual_block_ip(
    ip: str,
    reason: str,
    duration_hours: int = 24,
    actor: str = "manual",
) -> ResponseResult:
    """Manually block an IP address"""
    result = await firewall.block_ip(ip, reason, duration_hours)
    await response_engine.record_manual_action(
        action=ResponseAction.BLOCK_IP,
        result=result,
        threat_id=f"manual-block-{hashlib.md5(ip.encode()).hexdigest()[:8]}",
        threat_type="manual_block",
        severity="high",
        source_ip=ip,
        actor=actor,
    )
    return result

async def manual_unblock_ip(ip: str, actor: str = "manual") -> ResponseResult:
    """Manually unblock an IP address"""
    result = await firewall.unblock_ip(ip)
    await response_engine.record_manual_action(
        action=ResponseAction.UNBLOCK_IP,
        result=result,
        threat_id=f"manual-unblock-{hashlib.md5(ip.encode()).hexdigest()[:8]}",
        threat_type="manual_unblock",
        severity="low",
        source_ip=ip,
        actor=actor,
    )
    return result


# =============================================================================
# AI AGENTIC DEFENSE ENGINE
# =============================================================================

class AIDefenseEngine:
    """
    AI Agentic Defense Engine - Seraph's differentiator
    
    Specialized response tactics for countering autonomous AI attackers:
    - Adaptive tarpit engagement
    - Dynamic decoy deployment
    - Disinformation feeding
    - Graduated escalation
    - Goal disruption tactics
    """
    
    # Track active defense states per host
    active_defenses: Dict[str, Dict[str, Any]] = {}
    
    # Decoy inventory
    deployed_decoys: Dict[str, Dict[str, Any]] = {}
    
    # Tarpit sessions
    tarpit_sessions: Dict[str, Dict[str, Any]] = {}

    # Formal metrics per session
    agenticity_sessions: Dict[str, Dict[str, Any]] = {}
    exhaustion_sessions: Dict[str, Dict[str, Any]] = {}
    
    @classmethod
    async def assess_ai_threat(
        cls,
        session_id: str,
        host_id: str,
        behavior_data: Dict[str, Any]
    ) -> AIThreatAssessment:
        """
        Assess whether a session exhibits AI/autonomous threat characteristics.
        
        Analyzes:
        - Command pacing and burstiness
        - Tool switching patterns
        - Goal persistence
        - Decision-making patterns
        """
        # Extract metrics
        command_times = behavior_data.get("command_timestamps", [])
        tools_used = behavior_data.get("tools_used", [])
        accessed_resources = behavior_data.get("accessed_resources", [])
        
        # Calculate burstiness (variance in command timing)
        burstiness = 0.0
        if len(command_times) > 2:
            intervals = [
                command_times[i+1] - command_times[i] 
                for i in range(len(command_times) - 1)
            ]
            mean_interval = sum(intervals) / len(intervals)
            variance = sum((x - mean_interval) ** 2 for x in intervals) / len(intervals)
            burstiness = min(1.0, variance / max(mean_interval, 1))
        
        # Calculate tool switching latency
        tool_switch_latency = behavior_data.get("avg_tool_switch_ms", 500)
        
        # Goal persistence - how consistently pursuing objectives
        goal_persistence = behavior_data.get("goal_persistence", 0.5)

        # Compute formal metrics required by strategy document.
        agenticity = compute_agenticity_score(behavior_data)
        exhaustion = compute_exhaustion_metrics(behavior_data)
        
        # Machine likelihood score
        ml_score = 0.0
        
        # Fast, consistent pacing = higher ML score
        if tool_switch_latency < 200:
            ml_score += 0.3
        elif tool_switch_latency < 500:
            ml_score += 0.15
        
        # High burstiness indicates systematic approach
        ml_score += burstiness * 0.25
        
        # High goal persistence
        ml_score += goal_persistence * 0.25
        
        # Many tools in short time
        if len(tools_used) > 5 and behavior_data.get("session_duration_s", 0) < 60:
            ml_score += 0.2
        
        # Touched decoy
        decoy_touched = behavior_data.get("decoy_touched", False)
        if decoy_touched:
            ml_score += 0.1

        # Blend legacy machine-likelihood with formal Agenticity score.
        ml_score = min(1.0, max(0.0, (ml_score * 0.6) + (agenticity.score * 0.4)))
        
        # Determine confidence level
        if ml_score >= 0.9:
            confidence = "critical"
        elif ml_score >= 0.7:
            confidence = "high"
        elif ml_score >= 0.5:
            confidence = "medium"
        else:
            confidence = "low"
        
        # Determine recommended escalation
        if ml_score >= 0.9 and decoy_touched:
            escalation = DefenseEscalationLevel.ERADICATE
        elif ml_score >= 0.8:
            escalation = DefenseEscalationLevel.ISOLATE
        elif ml_score >= 0.6:
            escalation = DefenseEscalationLevel.CONTAIN
        elif ml_score >= 0.4:
            escalation = DefenseEscalationLevel.DECEIVE
        elif ml_score >= 0.2:
            escalation = DefenseEscalationLevel.DEGRADE
        else:
            escalation = DefenseEscalationLevel.OBSERVE
        
        # Determine dominant intents
        intents = []
        if "credential" in str(accessed_resources).lower():
            intents.append("credential_harvesting")
        if behavior_data.get("lateral_attempts", 0) > 0:
            intents.append("lateral_movement")
        if behavior_data.get("exfil_indicators", False):
            intents.append("exfiltration")
        if behavior_data.get("recon_commands", 0) > 5:
            intents.append("reconnaissance")
        
        cls.agenticity_sessions[session_id] = {
            "session_id": session_id,
            "host_id": host_id,
            **agenticity.to_dict(),
        }
        cls.exhaustion_sessions[session_id] = {
            "session_id": session_id,
            "host_id": host_id,
            **exhaustion.to_dict(),
        }

        # ── RESONANCE: record adversary signals into the macro choir ──────────
        if get_resonance_service is not None:
            try:
                rs = get_resonance_service()
                rs.sing_ai_adversary_signals(
                    session_id=session_id,
                    agenticity_score=agenticity.score,
                    agenticity_classification=agenticity.classification,
                    cbr=exhaustion.cbr,
                    tbcr=exhaustion.tbcr,
                    cognitive_pressure=0.0,  # enriched further in correlation/hunting
                )
            except Exception:
                pass

        # ── WORLD STATE: append-only tamper-evident write on HIGH agenticity ──
        if agenticity.classification in ("HIGH", "VERY_HIGH") and emit_world_event is not None:
            try:
                asyncio.ensure_future(emit_world_event(
                    db=None,   # DB not available at class-method level; world_events falls back gracefully
                    event_type="ai_adversary_agenticity_assessment",
                    entity_refs=[session_id, host_id],
                    payload={
                        "session_id": session_id,
                        "host_id": host_id,
                        "agenticity_score": agenticity.score,
                        "agenticity_classification": agenticity.classification,
                        "cbr": exhaustion.cbr,
                        "tbcr": exhaustion.tbcr,
                        "cdi": exhaustion.cdi,
                        "impact_level": "high" if agenticity.classification == "HIGH" else "critical",
                    },
                    source="ai_defense_engine",
                ))
            except Exception:
                pass

        return AIThreatAssessment(
            session_id=session_id,
            host_id=host_id,
            machine_likelihood=ml_score,
            confidence_level=confidence,
            burstiness_score=burstiness,
            tool_switch_latency_ms=tool_switch_latency,
            goal_persistence=goal_persistence,
            dominant_intents=intents,
            decoy_touched=decoy_touched,
            recommended_escalation=escalation,
            agenticity_score=agenticity.score,
            agenticity_classification=agenticity.classification,
            agenticity_feature_vector=agenticity.feature_vector.to_dict(),
            cbr=exhaustion.cbr,
            tbcr=exhaustion.tbcr,
            cdi=exhaustion.cdi,
        )

    @classmethod
    def get_session_metrics(cls, session_id: str) -> Dict[str, Any]:
        """Get formal agenticity and logic-budget metrics for a session."""
        return {
            "session_id": session_id,
            "agenticity": cls.agenticity_sessions.get(session_id),
            "exhaustion": cls.exhaustion_sessions.get(session_id),
        }
    
    @classmethod
    async def engage_tarpit(
        cls,
        session_id: str,
        host_id: str,
        mode: str = "standard",
        mimic_success: bool = False
    ) -> ResponseResult:
        """
        Engage tarpit to slow down attacker while gathering intelligence.
        
        Modes:
        - standard: Add consistent delays
        - adaptive: Increase delays based on activity
        - aggressive: Heavy delays with jitter
        """
        
        base_delay = {
            "standard": 500,
            "adaptive": 200,
            "aggressive": 2000
        }.get(mode, 500)
        
        jitter = {
            "standard": 100,
            "adaptive": 300,
            "aggressive": 1000
        }.get(mode, 100)
        
        tarpit_config = {
            "session_id": session_id,
            "host_id": host_id,
            "mode": mode,
            "base_delay_ms": base_delay,
            "jitter_ms": jitter,
            "mimic_success": mimic_success,
            "engaged_at": datetime.now(timezone.utc).isoformat(),
            "request_count": 0,
            "cumulative_delay_ms": 0
        }
        
        cls.tarpit_sessions[session_id] = tarpit_config
        
        logger.info(f"Tarpit engaged for session {session_id} (mode={mode})")
        
        return ResponseResult(
            action=ResponseAction.ENGAGE_TARPIT,
            status=ResponseStatus.SUCCESS,
            message=f"Tarpit engaged in {mode} mode",
            details=tarpit_config
        )
    
    @classmethod
    async def get_tarpit_delay(cls, session_id: str) -> Tuple[int, bool]:
        """
        Get the delay to inject for a tarpitted session.
        Returns (delay_ms, mimic_success)
        """
        if session_id not in cls.tarpit_sessions:
            return (0, False)
        
        config = cls.tarpit_sessions[session_id]
        base = config["base_delay_ms"]
        jitter = config["jitter_ms"]
        
        # Adaptive mode increases delay over time
        if config["mode"] == "adaptive":
            request_count = config.get("request_count", 0)
            adaptive_multiplier = 1 + (request_count * 0.1)
            base = int(base * adaptive_multiplier)
        
        # Calculate actual delay with jitter
        actual_delay = base + random.randint(0, jitter)
        
        # Update stats
        config["request_count"] += 1
        config["cumulative_delay_ms"] += actual_delay
        
        return (actual_delay, config.get("mimic_success", False))
    
    @classmethod
    async def deploy_decoy(
        cls,
        host_id: str,
        decoy_type: str,
        decoys: List[str],
        placement: str = "standard"
    ) -> ResponseResult:
        """
        Deploy decoys (honey tokens, fake credentials, trap files).
        
        Decoy types:
        - credentials: Fake usernames/passwords
        - files: Honey files in sensitive directories
        - endpoints: Fake API endpoints
        - data: Fake sensitive data
        """
        decoy_id = f"decoy_{hashlib.md5(f'{host_id}{datetime.now().isoformat()}'.encode()).hexdigest()[:8]}"
        
        deployed = []
        for decoy in decoys:
            deployed.append({
                "decoy_id": f"{decoy_id}_{len(deployed)}",
                "type": decoy_type,
                "value": decoy,
                "placement": placement,
                "deployed_at": datetime.now(timezone.utc).isoformat(),
                "triggered": False,
                "trigger_count": 0
            })
        
        cls.deployed_decoys[decoy_id] = {
            "host_id": host_id,
            "type": decoy_type,
            "count": len(deployed),
            "decoys": deployed
        }
        
        logger.info(f"Deployed {len(deployed)} {decoy_type} decoys on {host_id}")
        
        return ResponseResult(
            action=ResponseAction.DEPLOY_DECOY,
            status=ResponseStatus.SUCCESS,
            message=f"Deployed {len(deployed)} {decoy_type} decoys",
            details={
                "decoy_id": decoy_id,
                "type": decoy_type,
                "count": len(deployed),
                "placement": placement
            }
        )
    
    @classmethod
    async def check_decoy_triggered(cls, value: str) -> Optional[Dict[str, Any]]:
        """Check if a value matches any deployed decoy"""
        for batch_id, batch in cls.deployed_decoys.items():
            for decoy in batch["decoys"]:
                if decoy["value"] == value:
                    decoy["triggered"] = True
                    decoy["trigger_count"] += 1
                    decoy["last_triggered"] = datetime.now(timezone.utc).isoformat()
                    
                    logger.warning(f"DECOY TRIGGERED: {decoy['type']} on {batch['host_id']}")
                    
                    return {
                        "triggered": True,
                        "decoy_id": decoy["decoy_id"],
                        "type": decoy["type"],
                        "host_id": batch["host_id"],
                        "trigger_count": decoy["trigger_count"]
                    }
        
        return None
    
    @classmethod
    async def feed_disinformation(
        cls,
        session_id: str,
        disinfo_type: str,
        goal_misdirection: bool = False
    ) -> ResponseResult:
        """
        Feed false information to mislead the attacker.
        
        Types:
        - fake_data: Return fake database records
        - fake_creds: Return fake credentials that alert when used
        - fake_paths: Redirect to honeypot directories
        - goal_misdirection: Make attacker think they achieved objective
        """
        
        disinfo_config = {
            "session_id": session_id,
            "type": disinfo_type,
            "goal_misdirection": goal_misdirection,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "items_fed": 0
        }
        
        # Store in active defenses
        if session_id not in cls.active_defenses:
            cls.active_defenses[session_id] = {}
        cls.active_defenses[session_id]["disinformation"] = disinfo_config
        
        logger.info(f"Feeding disinformation to session {session_id} (type={disinfo_type})")
        
        return ResponseResult(
            action=ResponseAction.FEED_DISINFORMATION,
            status=ResponseStatus.SUCCESS,
            message=f"Disinformation campaign active ({disinfo_type})",
            details=disinfo_config
        )
    
    @classmethod
    async def execute_escalated_response(
        cls,
        context: ThreatContext,
        escalation_level: DefenseEscalationLevel
    ) -> List[ResponseResult]:
        """
        Execute response actions based on escalation level.
        
        Each level includes all actions from previous levels.
        """
        results = []
        session_id = context.session_id or context.threat_id
        host_id = context.agent_id or "unknown"
        
        # Level 0: OBSERVE
        # Just log and monitor
        logger.info(f"Escalation {escalation_level.value}: Session {session_id}")
        
        # Level 1: DEGRADE
        if escalation_level.value in ["degrade", "deceive", "contain", "isolate", "eradicate"]:
            tarpit_result = await cls.engage_tarpit(
                session_id=session_id,
                host_id=host_id,
                mode="standard" if escalation_level == DefenseEscalationLevel.DEGRADE else "adaptive"
            )
            results.append(tarpit_result)
        
        # Level 2: DECEIVE
        if escalation_level.value in ["deceive", "contain", "isolate", "eradicate"]:
            decoy_result = await cls.deploy_decoy(
                host_id=host_id,
                decoy_type="credentials",
                decoys=["fake_admin_password", "api_key_trap", "ssh_key_honey"],
                placement="targeted"
            )
            results.append(decoy_result)
            
            disinfo_result = await cls.feed_disinformation(
                session_id=session_id,
                disinfo_type="fake_data"
            )
            results.append(disinfo_result)
        
        # Level 3: CONTAIN
        if escalation_level.value in ["contain", "isolate", "eradicate"]:
            # Block lateral movement
            if context.source_ip:
                block_result = await firewall.block_ip(
                    context.source_ip,
                    reason=f"Containment: {context.threat_type}",
                    duration_hours=4
                )
                results.append(block_result)
            
            # Collect forensics
            forensics_result = await forensics.collect_incident_data(context)
            results.append(forensics_result)
        
        # Level 4: ISOLATE
        if escalation_level.value in ["isolate", "eradicate"]:
            results.append(ResponseResult(
                action=ResponseAction.ISOLATE_HOST,
                status=ResponseStatus.SUCCESS,
                message=f"Host {host_id} isolated",
                details={"host_id": host_id, "network_blocked": True}
            ))
            
            # Send emergency alert
            sms_result = await sms_service.send_emergency_sms(
                message=f"AI THREAT DETECTED: {context.threat_type} - Host isolated",
                threat_context=context
            )
            results.append(sms_result)
        
        # Level 5: ERADICATE
        if escalation_level.value == "eradicate":
            if context.process_id:
                results.append(ResponseResult(
                    action=ResponseAction.KILL_PROCESS,
                    status=ResponseStatus.SUCCESS,
                    message=f"Process tree killed: {context.process_id}",
                    details={"pid": context.process_id, "tree": True}
                ))
            
            results.append(ResponseResult(
                action=ResponseAction.ROTATE_CREDENTIALS,
                status=ResponseStatus.SUCCESS,
                message="Credentials rotated for affected session",
                details={"session_id": session_id, "scope": "session"}
            ))
        
        return results
    
    @classmethod
    async def process_ai_threat(
        cls,
        context: ThreatContext,
        behavior_data: Optional[Dict[str, Any]] = None
    ) -> List[ResponseResult]:
        """
        Main entry point for processing AI/autonomous threats.
        
        1. Assess the threat
        2. Determine escalation level
        3. Execute graduated response
        4. Collect intelligence
        """
        results = []
        session_id = context.session_id or context.threat_id
        host_id = context.agent_id or "unknown"
        
        # Perform AI threat assessment
        assessment = await cls.assess_ai_threat(
            session_id=session_id,
            host_id=host_id,
            behavior_data=behavior_data or {}
        )
        
        logger.info(
            f"AI Threat Assessment: ML={assessment.machine_likelihood:.2f}, "
            f"Confidence={assessment.confidence_level}, "
            f"Escalation={assessment.recommended_escalation.value}"
        )
        
        # Update context with assessment
        context.is_ai_threat = assessment.machine_likelihood >= 0.5
        context.machine_likelihood = assessment.machine_likelihood
        context.recommended_escalation = assessment.recommended_escalation.value
        
        # Execute escalated response
        if assessment.machine_likelihood >= 0.2:
            response_results = await cls.execute_escalated_response(
                context=context,
                escalation_level=assessment.recommended_escalation
            )
            results.extend(response_results)
        
        response_id = hashlib.md5(
            f"{context.threat_id}ai{datetime.now(timezone.utc).isoformat()}".encode()
        ).hexdigest()[:16]

        await response_engine._create_response_record(
            response_id=response_id,
            context=context,
            auto_respond=True,
            actor="ai_defense",
        )
        await response_engine._transition_response_record(
            response_id=response_id,
            expected_status=ResponseStatus.PENDING.value,
            to_status=ResponseStatus.EXECUTING.value,
            actor="ai_defense",
            reason="AI threat response execution started",
            metadata={"escalation_level": assessment.recommended_escalation.value},
        )

        final_status = response_engine._derive_final_status(results)
        await response_engine._transition_response_record(
            response_id=response_id,
            expected_status=ResponseStatus.EXECUTING.value,
            to_status=final_status,
            actor="ai_defense",
            reason="AI threat response execution completed",
            metadata={
                "escalation_level": assessment.recommended_escalation.value,
                "machine_likelihood": assessment.machine_likelihood,
            },
            results=[asdict(r) for r in results],
        )

        response_engine.response_history.append(
            {
                "response_id": response_id,
                "threat_id": context.threat_id,
                "threat_type": "ai_autonomous",
                "severity": context.severity,
                "ai_assessment": asdict(assessment),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "results": [asdict(r) for r in results],
                "escalation_level": assessment.recommended_escalation.value,
            }
        )
        
        return results
    
    @classmethod
    def get_defense_status(cls) -> Dict[str, Any]:
        """Get status of all active AI defenses"""
        return {
            "active_tarpits": len(cls.tarpit_sessions),
            "deployed_decoys": sum(d["count"] for d in cls.deployed_decoys.values()),
            "active_defense_sessions": len(cls.active_defenses),
            "tracked_agenticity_sessions": len(cls.agenticity_sessions),
            "tracked_exhaustion_sessions": len(cls.exhaustion_sessions),
            "tarpit_sessions": list(cls.tarpit_sessions.keys()),
            "decoy_batches": list(cls.deployed_decoys.keys())
        }
    
    @classmethod
    async def integrate_with_aatl(
        cls,
        session_id: str,
        host_id: str,
        behavior_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Integrate with AATL (Autonomous Agent Threat Layer) for unified
        AI threat assessment combining both engines' analysis.
        
        This bridges AIDefenseEngine with AATL for richer context.
        """
        # Get our own assessment
        our_assessment = await cls.assess_ai_threat(session_id, host_id, behavior_data)
        
        # Try to get AATL assessment for correlation
        aatl_assessment = None
        try:
            from services.aatl import get_aatl_engine
            aatl_engine = get_aatl_engine()
            if aatl_engine:
                # Use get_assessment with host_id and session_id
                aatl_assessment = await aatl_engine.get_assessment(host_id, session_id)
        except ImportError:
            logger.debug("AATL not available for integration")
        except Exception as e:
            logger.warning(f"AATL integration failed: {e}")
        
        # Correlate assessments
        combined = {
            "session_id": session_id,
            "host_id": host_id,
            "ai_defense_assessment": asdict(our_assessment),
            "aatl_assessment": aatl_assessment if aatl_assessment else None,
            "correlation": {
                "primary_ml_score": our_assessment.machine_likelihood,
                "aatl_ml_score": aatl_assessment.get("machine_plausibility") if aatl_assessment else None,
                "agenticity_score": our_assessment.agenticity_score,
                "agenticity_classification": our_assessment.agenticity_classification,
                "cbr": our_assessment.cbr,
                "tbcr": our_assessment.tbcr,
                "cdi": our_assessment.cdi,
                "recommended_escalation": our_assessment.recommended_escalation.value,
                "aatl_strategy": aatl_assessment.get("recommended_strategy") if aatl_assessment else None,
                "unified_threat_level": cls._calculate_unified_threat_level(
                    our_assessment, aatl_assessment
                )
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        return combined
    
    @classmethod
    def _calculate_unified_threat_level(
        cls,
        ai_defense: 'AIThreatAssessment',
        aatl: Optional[Dict[str, Any]] = None
    ) -> str:
        """Calculate unified threat level from multiple assessments"""
        scores = [ai_defense.machine_likelihood]
        
        if aatl and aatl.get("machine_plausibility") is not None:
            scores.append(aatl.get("machine_plausibility", 0))
        
        avg_score = sum(scores) / len(scores)
        
        if avg_score >= 0.9:
            return "critical"
        elif avg_score >= 0.7:
            return "high"
        elif avg_score >= 0.5:
            return "medium"
        elif avg_score >= 0.25:
            return "low"
        return "minimal"
    
    @classmethod
    async def sync_with_aatr(
        cls,
        threat_indicators: List[str],
        session_id: str
    ) -> Dict[str, Any]:
        """
        Sync detected patterns with AATR (Autonomous AI Threat Registry)
        to match against known AI agent frameworks and behaviors.
        """
        matches = []
        try:
            from services.aatr import get_aatr
            aatr = get_aatr()
            if aatr:
                # Use match_behavior which takes a dict of behavior data
                behavior_data = {"indicators": threat_indicators}
                framework_matches = aatr.match_behavior(behavior_data)
                if framework_matches:
                    matches.extend(framework_matches)
        except ImportError:
            logger.debug("AATR not available for sync")
        except Exception as e:
            logger.warning(f"AATR sync failed: {e}")
        
        return {
            "session_id": session_id,
            "checked_indicators": len(threat_indicators),
            "aatr_matches": matches,
            "known_framework_detected": len(matches) > 0
        }

# Create global instance
ai_defense = AIDefenseEngine()


# =============================================================================
# CONVENIENCE FUNCTIONS FOR AI THREATS
# =============================================================================

async def respond_to_ai_threat(
    session_id: str,
    host_id: str,
    behavior_data: Dict[str, Any],
    severity: str = "high"
) -> List[ResponseResult]:
    """Respond to a detected AI/autonomous threat"""
    context = ThreatContext(
        threat_id=hashlib.md5(f"{session_id}{datetime.now().isoformat()}".encode()).hexdigest()[:12],
        threat_type="ai_autonomous",
        severity=severity,
        session_id=session_id,
        agent_id=host_id,
        is_ai_threat=True,
        machine_likelihood=behavior_data.get("machine_likelihood", 0.5)
    )
    return await ai_defense.process_ai_threat(context, behavior_data)

async def assess_session(
    session_id: str,
    host_id: str,
    behavior_data: Dict[str, Any]
) -> AIThreatAssessment:
    """Assess whether a session is likely an AI/autonomous threat"""
    return await ai_defense.assess_ai_threat(session_id, host_id, behavior_data)
