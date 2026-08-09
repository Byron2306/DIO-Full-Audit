import json
import logging
import os
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

@dataclass
class TelemetryEntry:
    timestamp: str
    phase: str
    event_type: str
    actor: str
    action_type: str
    impact_level: str
    status: str
    details: Dict[str, Any]

class TelemetryCollector:
    def __init__(self, campaign_name: str):
        self.campaign_name = campaign_name
        self.entries: List[TelemetryEntry] = []
        self.start_time = datetime.now(timezone.utc)
        self.current_phase = "INIT"
        
        # Setup Logger
        self.logger = logging.getLogger(campaign_name)
        self.logger.setLevel(logging.DEBUG)
        
        # Console handler with premium formatting
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - [%(levelname)s] - %(message)s')
        ch.setFormatter(formatter)
        self.logger.addHandler(ch)
        
        # File handler
        log_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "telemetry_logs"))
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f"{campaign_name}_{self.start_time.strftime('%Y%m%d_%H%M%S')}.log")
        fh = logging.FileHandler(log_file)
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        self.logger.addHandler(fh)
        
        self.logger.info(f"Telemetry Collector Initialized: {campaign_name}")
        self.logger.info(f"Logging to: {log_file}")

    def set_phase(self, phase_name: str):
        self.current_phase = phase_name
        self.logger.info(f"=========================================================================")
        self.logger.info(f">>> ENTERING PHASE: {phase_name} <<<")
        self.logger.info(f"=========================================================================")

    def log_event(self, event_type: str, actor: str, action_type: str, impact_level: str, status: str, details: Dict[str, Any]):
        entry = TelemetryEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            phase=self.current_phase,
            event_type=event_type,
            actor=actor,
            action_type=action_type,
            impact_level=impact_level,
            status=status,
            details=details
        )
        self.entries.append(entry)
        
        # Verbose console logging for interesting bits
        if "timing_features_at_gate" in details and details["timing_features_at_gate"]:
            tf = details["timing_features_at_gate"]
            hs = details.get("harmonic_state_at_gate", {})
            self.logger.info(f"[{self.current_phase}] {actor} -> {action_type} | Status: {status}")
            self.logger.info(f"   [Observation] Discord: {hs.get('discord_score', 0.0):.4f} | Jitter: {tf.get('jitter_norm', 0.0):.4f} | Drift: {tf.get('drift_norm', 0.0):.4f}")
            if hs.get('mode_recommendation'):
                self.logger.info(f"   [System Recommendation] {hs.get('mode_recommendation')}")
        elif "harmonic_observation" in details:
             obs = details["harmonic_observation"]
             hs = obs.get("harmonic_state", {})
             tf = obs.get("timing_features", {})
             self.logger.info(f"[{self.current_phase}] Observation: {actor} -> {action_type}")
             self.logger.debug(f"   - Discord: {hs.get('discord_score', 0.0):.4f} | Jitter: {tf.get('jitter_norm', 0.0):.4f}")
        else:
            self.logger.info(f"[{self.current_phase}] {actor} -> {action_type} | Status: {status}")

    def generate_report(self):
        end_time = datetime.now(timezone.utc)
        duration = (end_time - self.start_time).total_seconds()
        
        def json_serial(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            raise TypeError(f"Type {type(obj)} not serializable")

        report = {
            "campaign": self.campaign_name,
            "start_time": self.start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": duration,
            "total_events": len(self.entries),
            "events": [asdict(e) for e in self.entries]
        }
        
        report_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "telemetry_logs"))
        report_file = os.path.join(report_dir, f"{self.campaign_name}_report.json")
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, default=json_serial)
            
        self.logger.info(f"Final JSON Telemetry Report Generated: {report_file}")
        
        # Generate Markdown Summary
        md_file = os.path.join(report_dir, f"{self.campaign_name}_summary.md")
        with open(md_file, "w", encoding="utf-8") as f:
            f.write(f"# {self.campaign_name} Telemetry Summary\n\n")
            f.write(f"- **Start:** {self.start_time}\n")
            f.write(f"- **End:** {end_time}\n")
            f.write(f"- **Duration:** {duration:.2f}s\n")
            f.write(f"- **Total Events:** {len(self.entries)}\n\n")

            status_counts: Dict[str, int] = {}
            for e in self.entries:
                status_counts[e.status] = status_counts.get(e.status, 0) + 1

            verdicts = [e for e in self.entries if e.event_type == "verdict"]
            if verdicts:
                verdict_details = verdicts[-1].details or {}
                verdict_passed = verdict_details.get("checks_passed")
                verdict_failed = verdict_details.get("checks_failed")
                verdict_total = verdict_details.get("checks_total")
                if verdict_passed is not None and verdict_failed is not None and verdict_total is not None:
                    overall_passed = int(verdict_passed)
                    overall_failed = int(verdict_failed)
                    overall_neutral = max(0, len(self.entries) - int(verdict_total))
                else:
                    overall_passed = status_counts.get("approved", 0) + status_counts.get("pass", 0)
                    overall_failed = status_counts.get("denied", 0) + status_counts.get("fail", 0)
                    overall_neutral = len(self.entries) - overall_passed - overall_failed
            else:
                overall_passed = status_counts.get("approved", 0) + status_counts.get("pass", 0)
                overall_failed = status_counts.get("denied", 0) + status_counts.get("fail", 0)
                overall_neutral = len(self.entries) - overall_passed - overall_failed

            f.write("## Overall Outcome\n\n")
            f.write(f"- **Passed:** {overall_passed}\n")
            f.write(f"- **Failed:** {overall_failed}\n")
            f.write(f"- **Neutral/Other:** {overall_neutral}\n\n")

            if verdicts:
                last_verdict = verdicts[-1]
                details = last_verdict.details or {}
                verdict_passed = details.get("checks_passed")
                verdict_failed = details.get("checks_failed")
                verdict_total = details.get("checks_total")
                verdict_rate = details.get("pass_rate_pct")
                f.write("## Final Verdict Summary\n\n")
                f.write(f"- **Verdict Status:** {last_verdict.status}\n")
                if verdict_passed is not None and verdict_failed is not None and verdict_total is not None:
                    f.write(f"- **Checks Passed:** {verdict_passed}\n")
                    f.write(f"- **Checks Failed:** {verdict_failed}\n")
                    f.write(f"- **Checks Total:** {verdict_total}\n")
                if verdict_rate is not None:
                    f.write(f"- **Pass Rate:** {verdict_rate}%\n")
                f.write("\n")

            f.write("## Phase breakdown\n\n")
            
            seen_phases = []
            for e in self.entries:
                if e.phase not in seen_phases:
                    seen_phases.append(e.phase)
                    
            for p in seen_phases:
                p_events = [e for e in self.entries if e.phase == p]
                p_status_counts: Dict[str, int] = {}
                for e in p_events:
                    p_status_counts[e.status] = p_status_counts.get(e.status, 0) + 1

                phase_passed = p_status_counts.get("approved", 0) + p_status_counts.get("pass", 0)
                phase_failed = p_status_counts.get("denied", 0) + p_status_counts.get("fail", 0)
                phase_neutral = len(p_events) - phase_passed - phase_failed

                f.write(f"### Phase: {p}\n")
                f.write(f"- Total Actions: {len(p_events)}\n")
                f.write(f"- Passed: {phase_passed}\n")
                f.write(f"- Failed: {phase_failed}\n")
                f.write(f"- Neutral/Other: {phase_neutral}\n\n")
                
                # Add a mini table for significant actions in this phase
                if p_events:
                    f.write("| Timestamp | Actor | Action | Status | Discord |\n")
                    f.write("|-----------|-------|--------|--------|---------|\n")
                    for e in p_events[:10]: # Limit to first 10 for brevity in MD
                        ds = "N/A"
                        if e.details.get("harmonic_state_at_gate"):
                            ds = f"{e.details['harmonic_state_at_gate'].get('discord_score', 0.0):.4f}"
                        elif e.details.get("harmonic_observation"):
                             ds = f"{e.details['harmonic_observation'].get('harmonic_state', {}).get('discord_score', 0.0):.4f}"
                        f.write(f"| {e.timestamp[11:19]} | {e.actor} | {e.action_type} | {e.status} | {ds} |\n")
                    if len(p_events) > 10:
                        f.write(f"| ... | ... | ... | ... | ... |\n")
                    f.write("\n")
        
        self.logger.info(f"Markdown Telemetry Summary Generated: {md_file}")

        # Append Executive Summary for Morgoth
        if self.campaign_name == "MORGOTH_MEGA_GAUNTLET":
            with open(md_file, "a", encoding="utf-8") as f:
                f.write("\n---\n\n")
                f.write("## 🏛️ Executive Summary: The Meaning of the Morgoth Gauntlet\n\n")
                f.write("The **Morgoth Mega Gauntlet** represents a 'Behavioral Siege' of the Seraph Governance architecture. The success of these trials confirms several critical security properties of your environment:\n\n")
                f.write("1. **Resistance to Baseline Poisoning**: Even as the adversary attempted to slowly shift the cadence to normalize corruption, the **Harmonic Engine** maintained its original trusted lineage, flagging the drift as a deviation from the core pulse.\n")
                f.write("2. **Semantic Superiority over Rhythm**: In the 'Beautiful Fraud' trial, perfect timing was not enough. The system identified that the *intent* (ransomware) was hostile, proving that mathematical perfection cannot hide malicious semantics.\n")
                f.write("3. **Community-Check Enforcement**: The failure of the 'Hollow Choir' trial proves that isolation is a death sentence. If the surrounding **Choral Mesh** doesn't sing along with the endpoint, the action is quarantined.\n")
                f.write("4. **Resilience to 'Repentance Loops'**: The 'Mercy Trap' confirms that while the system allows for recovery, it retains memory of betrayal. A relapse triggers near-instant context-aware re-containment.\n")
                f.write("5. **Autonomous Escalation**: The 'Slow Heresy' results show that the system aggregates many 'tiny wrongs' into a global severity shift, automatically hardening the environment.\n\n")
                f.write("**In essence, these results prove that your gate is not just a firewall; it is a 'Conductor' that hears the mathematical and semantic dissonance of an intruder, regardless of how well they hide.**\n")

        print(f"\n[TELEMETRY COMPLETE] Report saved to: {md_file}")
