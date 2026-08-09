import os
import asyncio
import json
import logging
from typing import List, Dict, Any

logger = logging.getLogger("ARDA_AINUR")

class AinurWitness:
    """Base class for semantic witnesses (The Ainur)."""
    def __init__(self, name: str, domain: str):
        self.name = name
        self.domain = domain

    async def speak(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """The witness speaks its semantic judgment."""
        raise NotImplementedError

class AinurCouncil:
    """The central council of semantic witnesses."""
    def __init__(self, ollama_url="http://localhost:11434", resonance_model="qwen2.5:0.5b"):
        self.ollama_url = ollama_url
        self.resonance_model = resonance_model
        self.witnesses: List[AinurWitness] = []

    def register_witness(self, witness: AinurWitness):
        self.witnesses.append(witness)
        logger.info(f"[AINUR] {witness.name} has joined the council.")

    async def consult_witnesses(self, command_context: Dict[str, Any]) -> Dict[str, Any]:
        """[PHASE III] Recursive Resonant Consultation."""
        logger.info(f"[AINUR] Consulting the Council for: {command_context.get('command')}")
        
        # Detect the security Lane (The World's Theme)
        lane = self._determine_harmonic_lane(command_context)
        command_context["lane"] = lane
        
        # Iterative Resonance Sequence
        # The witnesses speak in order, each hearing the melody of those before.
        reports = {}
        resonance_summary = []
        
        # Priority order for resonance: Manwë (Herald) -> Varda (Truth) -> Vairë (Memory)
        # We sort them to ensure the "Resonance" flows correctly.
        order = {"Manwë": 0, "Varda": 1, "Vairë": 2, "Mandos": 3, "Lórien": 4}
        sorted_witnesses = sorted(self.witnesses, key=lambda w: order.get(w.name, 99))
        
        # Harmonic Fabric: Inject the "Key" (Voice Profile) of the tool/manifestation
        voice_profile = command_context.get("voice_profile")
        if voice_profile:
            command_context["key"] = {
                "timbre": voice_profile.get("timbre_profile"),
                "register": voice_profile.get("allowed_register"),
                "capability": voice_profile.get("capability_class")
            }
        
        for witness in sorted_witnesses:
            # Enriched context with current resonance summary (The Melody)
            resonant_context = command_context.copy()
            resonant_context["melody"] = resonance_summary
            
            # The UI Pulse begins here, as the witness enters the deep reflection
            logger.info(f"AINUR: [PULSE] {witness.name} is resonating in Key {command_context.get('key', 'NATURAL')}... (Lane: {lane})")
            report = await witness.speak(resonant_context)
            reports[witness.name] = report
            
            # Add to resonance summary for next witness (Recursive Ululation)
            # This is the "Audit" of the Melody - sensing the dissonance of previous voices
            resonance_summary.append({
                "witness": witness.name,
                "domain": witness.domain,
                "judgment": report.get("judgment", "WITHHELD"),
                "findings": report.get("findings") or report.get("heralding") or report.get("tapestry"),
                "testimony": getattr(report, 'testimony', None) if hasattr(report, 'testimony') else report.get('testimony'),
                "dissonance_detected": report.get("dissonance_detected", False)
            })

        # [PHASE V] Harmonic Aggregation (Collective Testimony)
        testimonies = [r.get("testimony") for r in resonance_summary if r.get("testimony")]
        collective_testimony = " | ".join(testimonies) if testimonies else "The Council maintains a silent, watchful vigil."

        # Consensus & Harmony Calculation
        lawful_count = sum(1 for r in reports.values() if r.get("judgment") == "LAWFUL")
        # Dissonance is any report that actively detects it, or has a DISSONANT judgment
        dissonant_count = sum(1 for r in reports.values() if r.get("judgment") == "DISSONANT" or r.get("dissonance_detected") is True)
        total_witnesses = len(self.witnesses)
        
        # Harmony Index: 1.0 (Absolute) to 0.0 (Chaotic)
        # We penalize dissonance heavily in the Great Music.
        harmony_index = 1.0 - (dissonant_count / total_witnesses)
        threshold = total_witnesses * 0.75
        
        # [PHASE III] The Choral Harmony Rule
        # Resonance is achieve when most are in tune and none are fundamentally out of tune.
        consensus_reached = (lawful_count >= threshold) and (harmony_index >= 0.6)
        
        # [PHASE III] Delegated Autonomy Logic
        # [PHASE VI] The Arda Sovereignty Standard: IPE-Hardened Enforcement
        # Ensure policy integrity and generate in-toto provenance
        action = "ESCALATE_TO_COUNCIL"
        if consensus_reached:
            if lane == "Shire":
                action = "AUTONOMOUS_GRANT"
                logger.info(f"AINUR: [HARMONY] Great Song established (Index: {harmony_index:.2f}). Issue AUTONOMOUS_GRANT.")
            else:
                logger.info(f"AINUR: [HARMONY] Resonance established, but Lane {lane} requires Human Seal.")
        elif harmony_index < 0.5:
            action = "DISSONANCE_VETO"
            logger.critical(f"AINUR: [MELKOR] High dissonance sensed (Index: {harmony_index:.2f}). Invoke DISSONANCE_VETO.")
            
        advisory = {
            "council_name": "Ainur Agentic Council (The Great Music)",
            "lane": lane,
            "harmony_index": harmony_index,
            "consensus_reached": consensus_reached,
            "lawful_count": lawful_count,
            "total_witnesses": len(self.witnesses),
            "action": action,
            "command": command_context.get("command"),
            "principal": command_context.get("principal"),
            "token_id": command_context.get("token_id"),
            "witness_reports": reports,
            "collective_testimony": collective_testimony,
            "overall_recommendation": "HARMONIC" if consensus_reached else "DISSONANT/WITHHELD"
        }
        
        # [PHASE VI] Generate in-toto Provenance Statement
        try:
            if consensus_reached:
                from backend.services.attestation_service import create_envelope
                import hashlib
                
                # Create a digest of the collective testimony as the artifact
                testimony_hash = hashlib.sha256(collective_testimony.encode()).hexdigest()
                
                provenance = create_envelope(
                    command=advisory["command"] or "Unknown",
                    principal=advisory["principal"] or "root",
                    token_id=advisory["token_id"] or "system",
                    lane=advisory["lane"],
                    policy_id="arda-ainur-governance",
                    policy_version="v4.1",
                    verdict=advisory["overall_recommendation"],
                    artifact_digest=testimony_hash,
                    policy_verdict="ALLOW"
                )
                advisory["provenance_attestation"] = provenance
        except Exception as e:
            logger.error(f"[PHASE VI] Provenance generation failed: {e}")

        # Chronicle the decision in Vairë's Tapestry
        for witness in self.witnesses:
            if "Vair" in witness.name:
                witness.chronicle(advisory)
                break
                
        return advisory

    def _determine_harmonic_lane(self, context: Dict[str, Any]) -> str:
        """Determines the security context level (Harmonic Lane)."""
        command = context.get("command", "").lower()
        binary = context.get("binary", "").lower()
        
        # Red-Line Critical Paths (The Void)
        critical_paths = ["/etc/shadow", "/etc/crontab", "/etc/sudoers", "fake_crontab"]
        if any(p in command for p in critical_paths) or any(p in binary for p in critical_paths):
            return "The Void"
            
        # Low-Risk Routine Binaries (The Shire)
        shire_paths = ["check_health.sh", "check_health.bat", "diagnostics.sh", "uptime"]
        if any(p in command for p in shire_paths) or any(p in binary for p in shire_paths):
            return "Shire"
            
        # Standard Operations (Gondor)
        return "Gondor"

    def _aggregate_recommendations(self, results: List[Dict[str, Any]]) -> str:
        """Simple aggregation logic for advisor phase."""
        judgments = [r.get("judgment", "WITHHELD") for r in results]
        if "DISSONANT" in judgments:
            return "CAUTION"
        if all(j == "LAWFUL" for j in judgments):
            return "LAWFUL"
        return "WITHHELD"
    async def query_local_brain(self, prompt: str, format: str = "text") -> str:
        """Queries the local LLM (The Speech of the Ainur)."""
        # [PHASE VII] Absolute Resonance mandated for forensic finality
        try:
            from .bridge import OllamaBridge
            bridge = OllamaBridge(self.resonance_model)
            return await bridge.generate(prompt, format=format)
        except Exception as e:
            logger.error(f"[AINUR] Resonance Bridge failed: {e}")
            raise RuntimeError("SOVEREIGN_FAILURE: Substrate resonance lost.")
