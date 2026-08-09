import os
import asyncio
import json
import logging
from typing import List, Dict, Any

logger = logging.getLogger("ARDA_AINUR")

try:
    from services.ainur.witness_bridge import UnifiedAinurBridge
except Exception:
    try:
        from backend.services.ainur.witness_bridge import UnifiedAinurBridge  # type: ignore
    except Exception:
        UnifiedAinurBridge = None  # type: ignore

try:
    from services.harmonic_engine import HarmonicEngine
except Exception:
    try:
        from backend.services.harmonic_engine import HarmonicEngine  # type: ignore
    except Exception:
        HarmonicEngine = None  # type: ignore

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
        self._harmonic_engine = HarmonicEngine() if HarmonicEngine is not None else None

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
        witness_sequence = []
        
        # Priority order for resonance: Manwë (Herald) -> Varda (Truth) -> Vairë (Memory)
        # We sort them to ensure the "Resonance" flows correctly.
        order = {"Manwë": 0, "Varda": 1, "Vairë": 2, "Mandos": 3, "Lórien": 4, "Ulmo": 5, "Aulë": 99}
        sorted_witnesses = sorted(self.witnesses, key=lambda w: order.get(w.name, 99))
        synthesis_witnesses = [w for w in sorted_witnesses if w.name == "Aulë"]
        primary_witnesses = [w for w in sorted_witnesses if w.name != "Aulë"]
        
        # Harmonic Fabric: Inject the "Key" (Voice Profile) of the tool/manifestation
        voice_profile = command_context.get("voice_profile")
        if voice_profile:
            command_context["key"] = {
                "timbre": voice_profile.get("timbre_profile"),
                "register": voice_profile.get("allowed_register"),
                "capability": voice_profile.get("capability_class")
            }
        
        for witness in primary_witnesses:
            # Enriched context with current resonance summary (The Melody)
            resonant_context = command_context.copy()
            resonant_context["melody"] = resonance_summary
            
            # The UI Pulse begins here, as the witness enters the deep reflection
            logger.info(f"AINUR: [PULSE] {witness.name} is resonating in Key {command_context.get('key', 'NATURAL')}... (Lane: {lane})")
            report = await witness.speak(resonant_context)
            reports[witness.name] = report
            witness_sequence.append(witness.name)
            
            # Add to resonance summary for next witness (Recursive Ululation)
            # This is the "Audit" of the Melody - sensing the dissonance of previous voices
            resonance_summary.append({
                "witness": witness.name,
                "domain": witness.domain,
                "judgment": report.get("judgment", "WITHHELD"),
                "findings": report.get("findings") or report.get("heralding") or report.get("tapestry"),
                "testimony": report.get("testimony"),
                "dissonance_detected": report.get("dissonance_detected", False),
                "state": report.get("state"),
                "score": report.get("score"),
                "reasons": report.get("reasons"),
                "evidence": report.get("evidence"),
                "inspector": report.get("inspector"),
            })

        for witness in synthesis_witnesses:
            resonant_context = command_context.copy()
            resonant_context["melody"] = resonance_summary
            logger.info(f"AINUR: [FORGE] {witness.name} is binding the prior song into constitutional synthesis...")
            report = await witness.speak(resonant_context)
            reports[witness.name] = report
            witness_sequence.append(witness.name)
            resonance_summary.append({
                "witness": witness.name,
                "domain": witness.domain,
                "judgment": report.get("judgment", "WITHHELD"),
                "findings": report.get("findings") or report.get("heralding") or report.get("tapestry"),
                "testimony": report.get("testimony"),
                "dissonance_detected": report.get("dissonance_detected", False),
                "state": report.get("state"),
                "score": report.get("score"),
                "reasons": report.get("reasons"),
                "evidence": report.get("evidence"),
                "inspector": report.get("inspector"),
            })

        # Consensus & Harmony Calculation
        lawful_count = sum(1 for r in reports.values() if r.get("judgment") == "LAWFUL")
        # Dissonance is any report that actively detects it, or has a DISSONANT judgment
        dissonant_count = sum(1 for r in reports.values() if r.get("judgment") == "DISSONANT" or r.get("dissonance_detected") is True)
        total_witnesses = len(self.witnesses)
        if total_witnesses == 0:
            logger.warning("[AINUR] Council consulted without witnesses; withholding by constitutional default.")
            return {
                "council_name": "Ainur Agentic Council (The Great Music)",
                "lane": lane,
                "harmony_index": 0.0,
                "consensus_reached": False,
                "lawful_count": 0,
                "total_witnesses": 0,
                "action": "WITHHOLD_EMPTY_COUNCIL",
                "command": command_context.get("command"),
                "principal": command_context.get("principal"),
                "token_id": command_context.get("token_id"),
                "witness_reports": {},
                "resonance_summary": [],
                "collective_testimony": "The Council is unsummoned; no witness has spoken.",
                "overall_recommendation": "DISSONANT/WITHHELD",
                "compat_recommendation": "WITHHELD",
                "canonical_runtime_state": "muted",
                "harmonic_observation": None,
            }
        
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
            "resonance_summary": resonance_summary,
            "witness_sequence": witness_sequence,
            "collective_testimony": self._collective_testimony(resonance_summary),
            "overall_recommendation": "HARMONIC" if consensus_reached else "DISSONANT/WITHHELD"
        }
        advisory["compat_recommendation"] = self._compat_recommendation(advisory["overall_recommendation"])
        advisory["canonical_runtime_state"] = self._canonical_runtime_state(
            overall_recommendation=advisory["overall_recommendation"],
            action=action,
            lane=lane,
        )
        advisory["harmonic_observation"] = self._build_harmonic_observation(
            command_context=command_context,
            lane=lane,
            witness_sequence=witness_sequence,
            resonance_summary=resonance_summary,
            harmony_index=harmony_index,
        )
        
        # [PHASE VI] Generate in-toto Provenance Statement
        try:
            from backend.services.attestation_service import create_envelope
            import hashlib

            testimony_hash = hashlib.sha256(
                advisory["collective_testimony"].encode("utf-8")
            ).hexdigest()
            provenance = create_envelope(
                command=advisory["command"] or "Unknown",
                principal=advisory["principal"] or command_context.get("actor") or "root",
                token_id=advisory["token_id"] or "system",
                lane=advisory["lane"],
                policy_id="arda-ainur-governance",
                policy_version="v4.2",
                verdict=advisory["overall_recommendation"],
                artifact_digest=testimony_hash,
                policy_verdict="ALLOW",
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

    @staticmethod
    def _collective_testimony(resonance_summary: List[Dict[str, Any]]) -> str:
        testimonies = [str(item.get("testimony")).strip() for item in resonance_summary if item.get("testimony")]
        if testimonies:
            return " | ".join(testimonies)
        findings = [str(item.get("findings")).strip() for item in resonance_summary if item.get("findings")]
        if findings:
            return " | ".join(findings)
        return "The Council maintains a silent, watchful vigil."

    @staticmethod
    def _compat_recommendation(overall_recommendation: str) -> str:
        if overall_recommendation == "HARMONIC":
            return "LAWFUL"
        if overall_recommendation == "DISSONANT/WITHHELD":
            return "WITHHELD"
        return overall_recommendation

    @staticmethod
    def _canonical_runtime_state(*, overall_recommendation: str, action: str, lane: str) -> str:
        if action == "DISSONANCE_VETO":
            return "fallen"
        if overall_recommendation == "HARMONIC" and lane == "Shire":
            return "harmonic"
        if overall_recommendation == "HARMONIC":
            return "strained"
        return "muted"

    def _build_harmonic_observation(
        self,
        *,
        command_context: Dict[str, Any],
        lane: str,
        witness_sequence: List[str],
        resonance_summary: List[Dict[str, Any]],
        harmony_index: float,
    ) -> Dict[str, Any] | None:
        if self._harmonic_engine is None:
            return None
        command = str(command_context.get("command") or "unknown")
        principal = str(
            command_context.get("principal")
            or command_context.get("actor")
            or command_context.get("user")
            or "unknown"
        )
        target_domain = str(command_context.get("binary") or command_context.get("target_domain") or command)
        dissonance_count = sum(1 for item in resonance_summary if item.get("dissonance_detected"))
        observation = self._harmonic_engine.observe(
            actor_id=principal,
            tool_name="ainur_council",
            target_domain=target_domain,
            operation=command,
            environment="council",
            stage=lane.lower(),
            context={
                "lane": lane,
                "harmony_index": harmony_index,
                "witness_count": len(witness_sequence),
                "dissonance_count": dissonance_count,
                "voice_profile": bool(command_context.get("voice_profile")),
            },
        )
        return {
            "event": observation["event"],
            "baseline_ref": observation["baseline_ref"],
            "timing_features": observation["timing_features"],
            "harmonic_state": observation["harmonic_state"],
        }

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
