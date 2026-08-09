"""
Local AI Reasoning Engine
=========================
Free local AI model for threat analysis, incident triage, and decision support.
Uses lightweight models that can run on CPU without external API calls.
"""

import os
import json
import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict
import uuid

logger = logging.getLogger(__name__)


@dataclass
class ReasoningResult:
    """Result from AI reasoning"""
    result_id: str
    query: str
    reasoning_type: str
    
    # Analysis
    conclusion: str
    confidence: float
    evidence: List[str]
    recommendations: List[str]
    
    # Metadata
    model_used: str
    reasoning_time_ms: int
    timestamp: str


@dataclass
class ThreatAnalysis:
    """Threat analysis result"""
    analysis_id: str
    threat_type: str
    severity: str
    
    # Analysis
    description: str
    indicators: List[str]
    mitre_techniques: List[str]
    
    # Risk
    risk_score: int
    exploitability: str
    impact: str
    
    # Response
    recommended_actions: List[str]
    playbook_id: Optional[str]
    
    # Reasoning
    reasoning_chain: List[str]
    confidence: float


@dataclass
class ReasoningContext:
    """Snapshot context used by cognition fabric reasoning bindings."""
    entities: List[Dict[str, Any]]
    relationships: Dict[str, Any]
    evidence_set: List[Dict[str, Any]]
    trust_state: Dict[str, Any]
    timeline_window: List[Dict[str, Any]]


class LocalAIReasoningEngine:
    """
    Local AI reasoning engine for security analysis.
    
    Features:
    - Rule-based threat classification
    - Pattern matching for MITRE ATT&CK techniques
    - Risk scoring with explainable reasoning
    - Incident triage and prioritization
    - Response recommendation
    
    Note: This is a lightweight rule-based engine.
    For full LLM capabilities, integrate with local models like:
    - Ollama (llama2, mistral, codellama)
    - llama.cpp
    - GPT4All
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
        
        # Analysis history
        self.reasoning_history: List[ReasoningResult] = []
        self.threat_analyses: Dict[str, ThreatAnalysis] = {}
        
        # Load knowledge bases
        self._load_mitre_knowledge()
        self._load_threat_patterns()
        self._load_response_playbooks()
        
        # Model configuration
        self.model_name = "seraph-reasoning-v1"
        self.use_local_llm = os.environ.get('LOCAL_LLM_ENABLED', 'false').lower() == 'true'
        self.ollama_url = os.environ.get('OLLAMA_URL', 'http://localhost:11434')
        
        logger.info(f"Local AI Reasoning Engine initialized (LLM: {self.use_local_llm})")
    
    def _load_mitre_knowledge(self):
        """Load MITRE ATT&CK knowledge base"""
        self.mitre_techniques = {
            # Initial Access
            "T1566": {"name": "Phishing", "tactic": "initial-access", "severity": "high"},
            "T1190": {"name": "Exploit Public-Facing Application", "tactic": "initial-access", "severity": "critical"},
            "T1133": {"name": "External Remote Services", "tactic": "initial-access", "severity": "high"},
            
            # Execution
            "T1059": {"name": "Command and Scripting Interpreter", "tactic": "execution", "severity": "high"},
            "T1059.001": {"name": "PowerShell", "tactic": "execution", "severity": "high"},
            "T1059.003": {"name": "Windows Command Shell", "tactic": "execution", "severity": "medium"},
            "T1204": {"name": "User Execution", "tactic": "execution", "severity": "medium"},
            
            # Persistence
            "T1547": {"name": "Boot or Logon Autostart Execution", "tactic": "persistence", "severity": "high"},
            "T1053": {"name": "Scheduled Task/Job", "tactic": "persistence", "severity": "medium"},
            "T1136": {"name": "Create Account", "tactic": "persistence", "severity": "high"},
            
            # Privilege Escalation
            "T1548": {"name": "Abuse Elevation Control Mechanism", "tactic": "privilege-escalation", "severity": "high"},
            "T1068": {"name": "Exploitation for Privilege Escalation", "tactic": "privilege-escalation", "severity": "critical"},
            
            # Defense Evasion
            "T1070": {"name": "Indicator Removal", "tactic": "defense-evasion", "severity": "high"},
            "T1562": {"name": "Impair Defenses", "tactic": "defense-evasion", "severity": "critical"},
            "T1027": {"name": "Obfuscated Files or Information", "tactic": "defense-evasion", "severity": "medium"},
            
            # Credential Access
            "T1003": {"name": "OS Credential Dumping", "tactic": "credential-access", "severity": "critical"},
            "T1003.001": {"name": "LSASS Memory", "tactic": "credential-access", "severity": "critical"},
            "T1110": {"name": "Brute Force", "tactic": "credential-access", "severity": "high"},
            "T1555": {"name": "Credentials from Password Stores", "tactic": "credential-access", "severity": "high"},
            
            # Discovery
            "T1087": {"name": "Account Discovery", "tactic": "discovery", "severity": "low"},
            "T1082": {"name": "System Information Discovery", "tactic": "discovery", "severity": "low"},
            "T1046": {"name": "Network Service Discovery", "tactic": "discovery", "severity": "medium"},
            
            # Lateral Movement
            "T1021": {"name": "Remote Services", "tactic": "lateral-movement", "severity": "high"},
            "T1021.001": {"name": "Remote Desktop Protocol", "tactic": "lateral-movement", "severity": "high"},
            "T1021.002": {"name": "SMB/Windows Admin Shares", "tactic": "lateral-movement", "severity": "high"},
            "T1021.006": {"name": "Windows Remote Management", "tactic": "lateral-movement", "severity": "high"},
            
            # Collection
            "T1560": {"name": "Archive Collected Data", "tactic": "collection", "severity": "medium"},
            "T1005": {"name": "Data from Local System", "tactic": "collection", "severity": "medium"},
            
            # Command and Control
            "T1071": {"name": "Application Layer Protocol", "tactic": "command-and-control", "severity": "high"},
            "T1571": {"name": "Non-Standard Port", "tactic": "command-and-control", "severity": "medium"},
            "T1573": {"name": "Encrypted Channel", "tactic": "command-and-control", "severity": "medium"},
            "T1105": {"name": "Ingress Tool Transfer", "tactic": "command-and-control", "severity": "high"},
            
            # Exfiltration
            "T1041": {"name": "Exfiltration Over C2 Channel", "tactic": "exfiltration", "severity": "critical"},
            "T1567": {"name": "Exfiltration Over Web Service", "tactic": "exfiltration", "severity": "critical"},
            
            # Impact
            "T1486": {"name": "Data Encrypted for Impact", "tactic": "impact", "severity": "critical"},
            "T1489": {"name": "Service Stop", "tactic": "impact", "severity": "high"},
            "T1490": {"name": "Inhibit System Recovery", "tactic": "impact", "severity": "critical"},
        }
    
    def _load_threat_patterns(self):
        """Load threat detection patterns"""
        self.threat_patterns = {
            # Credential theft
            "credential_theft": {
                "patterns": ["mimikatz", "lsass", "sekurlsa", "lazagne", "procdump", "comsvcs.dll"],
                "techniques": ["T1003", "T1003.001"],
                "severity": "critical"
            },
            
            # Ransomware
            "ransomware": {
                "patterns": ["encrypt", "ransom", ".locked", ".crypt", "bitcoin", "decrypt"],
                "techniques": ["T1486", "T1490"],
                "severity": "critical"
            },
            
            # Lateral movement
            "lateral_movement": {
                "patterns": ["psexec", "wmiexec", "smbexec", "winrm", "enter-pssession"],
                "techniques": ["T1021", "T1021.002", "T1021.006"],
                "severity": "high"
            },
            
            # Command and control
            "c2_activity": {
                "patterns": ["beacon", "meterpreter", "cobalt", "empire", "callback"],
                "techniques": ["T1071", "T1573"],
                "severity": "critical"
            },
            
            # Data exfiltration
            "exfiltration": {
                "patterns": ["rclone", "megasync", "upload", "exfil", "transfer"],
                "techniques": ["T1041", "T1567"],
                "severity": "critical"
            },
            
            # Privilege escalation
            "privilege_escalation": {
                "patterns": ["getsystem", "elevate", "runas", "sudo", "uac bypass"],
                "techniques": ["T1548", "T1068"],
                "severity": "high"
            },
            
            # Defense evasion
            "defense_evasion": {
                "patterns": ["disable av", "stop defender", "clear logs", "uninstall"],
                "techniques": ["T1562", "T1070"],
                "severity": "high"
            },
            
            # Persistence
            "persistence": {
                "patterns": ["startup", "scheduled task", "registry run", "cron", "systemd"],
                "techniques": ["T1547", "T1053"],
                "severity": "medium"
            }
        }
    
    def _load_response_playbooks(self):
        """Load response playbook mappings"""
        self.playbook_mappings = {
            "credential_theft": "playbook-credential-theft-response",
            "ransomware": "playbook-ransomware-containment",
            "lateral_movement": "playbook-lateral-movement-block",
            "c2_activity": "playbook-c2-isolation",
            "exfiltration": "playbook-data-breach-response",
            "privilege_escalation": "playbook-privilege-escalation",
            "defense_evasion": "playbook-defense-evasion",
            "persistence": "playbook-persistence-removal"
        }
    
    # =========================================================================
    # THREAT ANALYSIS
    # =========================================================================
    
    def analyze_threat(self, threat_data: Dict[str, Any]) -> ThreatAnalysis:
        """
        Analyze a threat with reasoning.
        
        Args:
            threat_data: Dict containing threat information
                - title: Threat title
                - description: Threat description
                - source: Where it came from
                - indicators: List of IOCs
                - process_name: Process involved (optional)
                - command_line: Command executed (optional)
        
        Returns:
            ThreatAnalysis with reasoning chain
        """
        import time
        start_time = time.time()
        
        analysis_id = f"analysis-{uuid.uuid4().hex[:8]}"
        
        # Extract information (handle None values)
        title = (threat_data.get("title") or "").lower()
        description = (threat_data.get("description") or "").lower()
        command_line = (threat_data.get("command_line") or "").lower()
        process_name = (threat_data.get("process_name") or "").lower()
        indicators = threat_data.get("indicators") or []
        
        # Combine all text for analysis
        all_text = f"{title} {description} {command_line} {process_name}"
        
        # Reasoning chain
        reasoning_chain = []
        reasoning_chain.append(f"Analyzing threat: {threat_data.get('title', 'Unknown')}")
        
        # Identify threat type
        threat_type = "unknown"
        matched_patterns = []
        mitre_techniques = []
        
        for ttype, tdata in self.threat_patterns.items():
            for pattern in tdata["patterns"]:
                if pattern in all_text:
                    matched_patterns.append(pattern)
                    if threat_type == "unknown":
                        threat_type = ttype
                        mitre_techniques.extend(tdata["techniques"])
        
        if matched_patterns:
            reasoning_chain.append(f"Pattern matches found: {', '.join(matched_patterns[:5])}")
            reasoning_chain.append(f"Classified as: {threat_type}")
        else:
            reasoning_chain.append("No known patterns matched - treating as suspicious activity")
        
        # Determine severity
        severity = "medium"
        if threat_type in ["credential_theft", "ransomware", "c2_activity", "exfiltration"]:
            severity = "critical"
        elif threat_type in ["lateral_movement", "privilege_escalation", "defense_evasion"]:
            severity = "high"
        
        reasoning_chain.append(f"Severity assessed as: {severity}")
        
        # Calculate risk score
        risk_score = self._calculate_risk_score(threat_type, severity, indicators)
        reasoning_chain.append(f"Risk score calculated: {risk_score}/100")
        
        # Determine exploitability and impact
        exploitability = "high" if threat_type in ["credential_theft", "c2_activity"] else "medium"
        impact = "critical" if threat_type in ["ransomware", "exfiltration"] else "high"
        
        # Get MITRE technique details
        mitre_details = [
            f"{tid}: {self.mitre_techniques.get(tid, {}).get('name', 'Unknown')}"
            for tid in mitre_techniques[:5]
        ]
        
        if mitre_details:
            reasoning_chain.append(f"MITRE ATT&CK techniques: {', '.join(mitre_details)}")
        
        # Generate recommendations
        recommendations = self._generate_recommendations(threat_type, severity)
        reasoning_chain.append(f"Generated {len(recommendations)} recommendations")
        
        # Get playbook
        playbook_id = self.playbook_mappings.get(threat_type)
        if playbook_id:
            reasoning_chain.append(f"Recommended playbook: {playbook_id}")
        
        # Calculate confidence
        confidence = min(0.9, 0.3 + (len(matched_patterns) * 0.15))
        
        analysis = ThreatAnalysis(
            analysis_id=analysis_id,
            threat_type=threat_type,
            severity=severity,
            description=f"Detected {threat_type.replace('_', ' ')} activity with {len(matched_patterns)} pattern matches",
            indicators=indicators[:10],
            mitre_techniques=mitre_techniques,
            risk_score=risk_score,
            exploitability=exploitability,
            impact=impact,
            recommended_actions=recommendations,
            playbook_id=playbook_id,
            reasoning_chain=reasoning_chain,
            confidence=confidence
        )
        
        self.threat_analyses[analysis_id] = analysis
        
        # Log reasoning result
        elapsed_ms = int((time.time() - start_time) * 1000)
        result = ReasoningResult(
            result_id=f"reason-{uuid.uuid4().hex[:8]}",
            query=threat_data.get("title", "threat analysis"),
            reasoning_type="threat_analysis",
            conclusion=f"{threat_type} ({severity})",
            confidence=confidence,
            evidence=matched_patterns,
            recommendations=recommendations[:3],
            model_used=self.model_name,
            reasoning_time_ms=elapsed_ms,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        self.reasoning_history.append(result)
        
        return analysis
    
    def _calculate_risk_score(self, threat_type: str, severity: str, 
                              indicators: List[str]) -> int:
        """Calculate risk score (0-100)"""
        base_scores = {
            "credential_theft": 90,
            "ransomware": 95,
            "c2_activity": 85,
            "exfiltration": 90,
            "lateral_movement": 75,
            "privilege_escalation": 70,
            "defense_evasion": 65,
            "persistence": 50,
            "unknown": 40
        }
        
        score = base_scores.get(threat_type, 40)
        
        # Adjust for indicators
        if len(indicators) > 5:
            score += 5
        
        # Adjust for severity
        if severity == "critical":
            score = min(100, score + 10)
        elif severity == "low":
            score = max(0, score - 15)
        
        return score
    
    def _generate_recommendations(self, threat_type: str, severity: str) -> List[str]:
        """Generate response recommendations"""
        recommendations = []
        
        # Common recommendations
        recommendations.append("Collect additional forensic evidence before containment")
        
        if threat_type == "credential_theft":
            recommendations.extend([
                "Immediately isolate affected systems",
                "Reset credentials for compromised accounts",
                "Enable multi-factor authentication",
                "Review authentication logs for lateral movement",
                "Consider forcing password reset for all users"
            ])
        elif threat_type == "ransomware":
            recommendations.extend([
                "IMMEDIATELY isolate affected systems from network",
                "Do NOT pay the ransom",
                "Preserve encrypted files for potential decryption",
                "Check backup integrity and restore from clean backups",
                "Report to law enforcement (FBI, CISA)"
            ])
        elif threat_type == "lateral_movement":
            recommendations.extend([
                "Block identified lateral movement paths",
                "Segment network to contain spread",
                "Review admin credentials on compromised segments",
                "Enable enhanced logging on domain controllers"
            ])
        elif threat_type == "c2_activity":
            recommendations.extend([
                "Block C2 IPs/domains at perimeter firewall",
                "Isolate beaconing hosts",
                "Capture memory dump for malware analysis",
                "Hunt for additional compromised hosts with same patterns"
            ])
        elif threat_type == "exfiltration":
            recommendations.extend([
                "Block outbound traffic to identified destinations",
                "Preserve network logs for forensic analysis",
                "Assess scope of data exposure",
                "Prepare for breach notification if PII involved"
            ])
        else:
            recommendations.extend([
                "Investigate suspicious activity further",
                "Collect additional evidence",
                "Monitor for escalation",
                "Consider containment if risk increases"
            ])
        
        return recommendations
    
    # =========================================================================
    # INCIDENT TRIAGE
    # =========================================================================
    
    def triage_incident(self, incidents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Triage and prioritize multiple incidents.
        
        Returns incidents sorted by priority with reasoning.
        """
        prioritized = []
        
        for incident in incidents:
            # Analyze each incident
            analysis = self.analyze_threat(incident)
            
            # Calculate priority score
            priority_score = analysis.risk_score
            
            # Adjust for active attack indicators
            if "active" in incident.get("status", "").lower():
                priority_score += 10
            
            # Adjust for business criticality
            if incident.get("affects_critical_system", False):
                priority_score += 15
            
            # Adjust for data sensitivity
            if incident.get("involves_pii", False):
                priority_score += 10
            
            prioritized.append({
                "incident": incident,
                "analysis": asdict(analysis),
                "priority_score": min(100, priority_score),
                "triage_recommendation": self._get_triage_recommendation(priority_score)
            })
        
        # Sort by priority (highest first)
        prioritized.sort(key=lambda x: x["priority_score"], reverse=True)
        
        return prioritized
    
    def _get_triage_recommendation(self, priority_score: int) -> str:
        """Get triage recommendation based on priority score"""
        if priority_score >= 90:
            return "IMMEDIATE - Drop everything and respond"
        elif priority_score >= 70:
            return "HIGH - Respond within 1 hour"
        elif priority_score >= 50:
            return "MEDIUM - Respond within 4 hours"
        elif priority_score >= 30:
            return "LOW - Respond within 24 hours"
        else:
            return "INFORMATIONAL - Monitor and review"
    
    # =========================================================================
    # NATURAL LANGUAGE QUERIES
    # =========================================================================
    
    def query(self, question: str, context: Dict[str, Any] = None) -> ReasoningResult:
        """
        Answer a natural language security question.
        
        Uses rule-based reasoning or local LLM if enabled.
        """
        import time
        start_time = time.time()
        
        question_lower = question.lower()
        
        # Rule-based responses
        conclusion = ""
        evidence = []
        recommendations = []
        confidence = 0.7
        
        if "prioritize" in question_lower or "triage" in question_lower:
            conclusion = "Use the triage_incident method for systematic prioritization based on risk scores"
            recommendations = ["Submit incidents to triage_incident()", "Review priority_score for each"]
        
        elif "mitre" in question_lower or "technique" in question_lower:
            # Extract technique ID if present
            match = re.search(r'T\d{4}(?:\.\d{3})?', question)
            if match:
                tid = match.group()
                if tid in self.mitre_techniques:
                    tech = self.mitre_techniques[tid]
                    conclusion = f"{tid} is '{tech['name']}' - a {tech['tactic']} technique with {tech['severity']} severity"
                    evidence = [f"MITRE ATT&CK: {tid}"]
                else:
                    conclusion = f"Technique {tid} not found in local knowledge base"
            else:
                conclusion = f"Found {len(self.mitre_techniques)} MITRE techniques in knowledge base"
        
        elif "credential" in question_lower or "password" in question_lower:
            conclusion = "Credential theft detected - this is a CRITICAL severity event"
            recommendations = [
                "Isolate affected systems",
                "Reset compromised credentials",
                "Enable MFA",
                "Review for lateral movement"
            ]
            evidence = list(self.threat_patterns["credential_theft"]["patterns"])
        
        elif "ransomware" in question_lower:
            conclusion = "Ransomware is a CRITICAL threat requiring immediate isolation"
            recommendations = [
                "Immediately isolate infected systems",
                "Do NOT pay ransom",
                "Restore from clean backups",
                "Report to authorities"
            ]
        
        else:
            conclusion = "Query processed. For detailed threat analysis, use analyze_threat() method."
            confidence = 0.5
        
        elapsed_ms = int((time.time() - start_time) * 1000)
        
        result = ReasoningResult(
            result_id=f"query-{uuid.uuid4().hex[:8]}",
            query=question,
            reasoning_type="query",
            conclusion=conclusion,
            confidence=confidence,
            evidence=evidence,
            recommendations=recommendations,
            model_used=self.model_name,
            reasoning_time_ms=elapsed_ms,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        
        self.reasoning_history.append(result)
        
        return result

    # =========================================================================
    # SNAPSHOT REASONING BINDINGS
    # =========================================================================

    def analyze_snapshot(self, context: ReasoningContext) -> Dict[str, Any]:
        """Analyze a multi-entity security snapshot for the cognition fabric."""
        evidence = context.evidence_set or []
        entities = context.entities or []
        relationships = context.relationships or {}
        edges = relationships.get("edges") if isinstance(relationships, dict) else []
        edges = edges if isinstance(edges, list) else []

        predictions = self.predict_next_step(context)
        lateral_paths = self.predict_lateral_path(context)
        candidate_actions = self.explain_candidates(context)

        severity_weight = {
            "credential_dump": 0.3,
            "credential_theft": 0.3,
            "c2_beacon": 0.25,
            "lateral_movement": 0.2,
            "privilege_escalation": 0.18,
            "defense_evasion": 0.15,
        }
        evidence_score = sum(
            severity_weight.get(str(item.get("type") or "").lower(), 0.08)
            for item in evidence
            if isinstance(item, dict)
        )
        graph_score = min(0.2, len(edges) * 0.04)
        entity_score = min(0.15, len(entities) * 0.03)
        risk_score = round(min(1.0, evidence_score + graph_score + entity_score), 6)

        return {
            "predictions": predictions,
            "lateral_paths": lateral_paths,
            "candidate_actions": candidate_actions,
            "suggested_actions": [item["action"] for item in candidate_actions],
            "risk_score": risk_score,
            "confidence": 0.65 if evidence else 0.35,
            "mean_uncertainty": 0.35 if evidence else 0.65,
            "model_used": self.model_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def predict_next_step(self, context: ReasoningContext) -> List[Dict[str, Any]]:
        evidence_types = {
            str(item.get("type") or "").lower()
            for item in (context.evidence_set or [])
            if isinstance(item, dict)
        }
        predictions: List[Dict[str, Any]] = []
        if {"credential_dump", "credential_theft"} & evidence_types:
            predictions.append({"step": "lateral_movement", "confidence": 0.74})
        if "c2_beacon" in evidence_types:
            predictions.append({"step": "command_and_control_expansion", "confidence": 0.68})
        if not predictions:
            predictions.append({"step": "investigation", "confidence": 0.42})
        return predictions

    def predict_lateral_path(self, context: ReasoningContext) -> List[Dict[str, Any]]:
        relationships = context.relationships or {}
        edges = relationships.get("edges") if isinstance(relationships, dict) else []
        paths = []
        for edge in edges if isinstance(edges, list) else []:
            if not isinstance(edge, dict):
                continue
            source = edge.get("source")
            target = edge.get("target")
            if source and target:
                paths.append({"source": source, "target": target, "likelihood": 0.5})
        return paths

    def explain_candidates(self, context: ReasoningContext) -> List[Dict[str, Any]]:
        evidence_types = {
            str(item.get("type") or "").lower()
            for item in (context.evidence_set or [])
            if isinstance(item, dict)
        }
        candidates = [{"action": "investigate", "reason": "preserve evidence and confirm scope"}]
        if "c2_beacon" in evidence_types:
            candidates.append({"action": "block_outbound", "reason": "C2 beacon evidence is present"})
        if {"credential_dump", "credential_theft"} & evidence_types:
            candidates.append({"action": "rotate_credentials", "reason": "credential access evidence is present"})
        return candidates

    # =========================================================================
    # OLLAMA INTEGRATION
    # =========================================================================
    
    def configure_ollama(self, base_url: str = "http://localhost:11434", 
                        model: str = "mistral") -> Dict:
        """Configure Ollama for local AI reasoning"""
        self.ollama_url = base_url
        self.ollama_model = model
        os.environ['OLLAMA_URL'] = base_url
        os.environ['OLLAMA_MODEL'] = model
        
        # Test connection
        try:
            import requests
            resp = requests.get(f"{base_url}/api/tags", timeout=5)
            if resp.status_code == 200:
                self.use_local_llm = True
                os.environ['LOCAL_LLM_ENABLED'] = 'true'
                models = resp.json().get("models", [])
                return {
                    "status": "connected",
                    "base_url": base_url,
                    "model": model,
                    "available_models": [m.get("name") for m in models]
                }
        except Exception as e:
            return {
                "status": "connection_failed",
                "error": str(e),
                "note": f"Ollama not reachable at {base_url}. Ensure Ollama is running on your server at {base_url}"
            }
        
        return {"status": "configured", "note": "Using rule-based reasoning until Ollama connected"}
    
    async def ollama_generate(self, prompt: str, model: str = None,
                              system_prompt: str = None) -> Dict:
        """Generate response using Ollama"""
        import requests
        
        model = model or getattr(self, 'ollama_model', 'mistral')
        
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False
        }
        
        if system_prompt:
            payload["system"] = system_prompt
        
        try:
            resp = requests.post(
                f"{self.ollama_url}/api/generate",
                json=payload,
                timeout=120
            )
            
            if resp.status_code == 200:
                return resp.json()
            else:
                return {"error": f"Ollama returned status {resp.status_code}"}
        except requests.exceptions.ConnectionError:
            return {
                "error": f"Cannot connect to Ollama at {self.ollama_url}",
                "note": "Ensure Ollama is running on your server"
            }
        except Exception as e:
            return {"error": str(e)}
    
    async def ollama_analyze_threat(self, threat_data: Dict[str, Any]) -> Dict:
        """
        Analyze threat using Ollama LLM for enhanced reasoning.
        Falls back to rule-based analysis if Ollama unavailable.
        """
        if not self.use_local_llm:
            # Use rule-based analysis
            analysis = self.analyze_threat(threat_data)
            return {
                "analysis": analysis,
                "method": "rule_based",
                "note": "Ollama not configured. Using rule-based analysis."
            }
        
        # Build security analysis prompt
        system_prompt = """You are Seraph AI, an expert security analyst. Analyze the following threat data and provide:
1. Threat classification (credential_theft, ransomware, c2_activity, lateral_movement, exfiltration, etc.)
2. Severity assessment (critical, high, medium, low)
3. MITRE ATT&CK technique mapping
4. Risk score (0-100)
5. Recommended response actions
6. Confidence level (0-1)

Respond in JSON format with keys: threat_type, severity, mitre_techniques, risk_score, recommendations, confidence, reasoning_chain"""
        
        prompt = f"""Analyze this security threat:

Title: {threat_data.get('title', 'Unknown')}
Description: {threat_data.get('description', 'N/A')}
Process: {threat_data.get('process_name', 'N/A')}
Command Line: {threat_data.get('command_line', 'N/A')}
Indicators: {', '.join(threat_data.get('indicators', []))}

Provide a comprehensive threat analysis."""
        
        ollama_response = await self.ollama_generate(prompt, system_prompt=system_prompt)
        
        if "error" in ollama_response:
            # Fallback to rule-based
            analysis = self.analyze_threat(threat_data)
            return {
                "analysis": analysis,
                "method": "rule_based_fallback",
                "ollama_error": ollama_response.get("error")
            }
        
        return {
            "analysis": ollama_response.get("response", ""),
            "method": "ollama_llm",
            "model": getattr(self, 'ollama_model', 'mistral'),
            "eval_count": ollama_response.get("eval_count", 0)
        }
    
    def get_ollama_status(self) -> Dict:
        """Get Ollama connection status"""
        import requests
        
        try:
            resp = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                return {
                    "status": "connected",
                    "url": self.ollama_url,
                    "models": [m.get("name") for m in models],
                    "configured_model": getattr(self, 'ollama_model', 'mistral')
                }
        except:
            pass
        
        return {
            "status": "disconnected",
            "url": self.ollama_url,
            "note": "Ollama not reachable. Install with: curl -fsSL https://ollama.com/install.sh | sh"
        }
    
    # =========================================================================
    # STATUS
    # =========================================================================
    
    def get_reasoning_stats(self) -> Dict:
        """Get reasoning engine statistics"""
        ollama_status = self.get_ollama_status()
        
        return {
            "model_name": self.model_name,
            "local_llm_enabled": self.use_local_llm,
            "ollama": ollama_status,
            "mitre_techniques_loaded": len(self.mitre_techniques),
            "threat_patterns_loaded": len(self.threat_patterns),
            "playbooks_mapped": len(self.playbook_mappings),
            "analyses_performed": len(self.threat_analyses),
            "queries_processed": len(self.reasoning_history)
        }


# Global singleton
ai_reasoning = LocalAIReasoningEngine()
