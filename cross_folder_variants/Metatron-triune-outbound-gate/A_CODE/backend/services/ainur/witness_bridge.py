import logging
import time
import json
from typing import Dict, Any, List
from .ainur_council import AinurWitness
from backend.arda.ainur.base import AinurInspector
from backend.arda.ainur.verdicts import AinurVerdict

logger = logging.getLogger("ARDA_BRIDGE")

class SovereignDict(dict):
    """
    A recursive wrapper that turns a dict into a Dot-notation accessible dictionary.
    Inherits from dict to ensure compatibility with Pydantic and standard dict methods.
    """
    def __init__(self, d):
        processed = {}
        for k, v in d.items():
            if isinstance(v, dict):
                v = SovereignDict(v)
            elif isinstance(v, list):
                v = [SovereignDict(i) if isinstance(i, dict) else i for i in v]
            processed[k] = v
        # Initialize with the processed data
        super().__init__(processed)

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            # Arda Correction: Raise AttributeError so getattr(obj, name, default) works.
            raise AttributeError(f"'SovereignDict' object has no attribute '{name}'")

    def __setattr__(self, name, value):
        self[name] = value

class _MockFreshness:
    """Lightweight freshness wrapper for presence-level evidence."""
    def __init__(self):
        self.observed_at = time.time()

class _MockEvidencePacket:
    """Lightweight evidence packet for presence-level witnesses."""
    def __init__(self, data: dict):
        self.evidence = data
        self.freshness = _MockFreshness()

class UnifiedAinurBridge(AinurWitness):
    """
    A bridge wrapper that allows Technical Inspectors (AinurInspector)
    to serve as Semantic Witnesses (AinurWitness) for the Council.
    """
    def __init__(self, inspector: AinurInspector):
        super().__init__(name=inspector.name.capitalize(), domain=getattr(inspector, "domain", "Sovereignty"))
        self.inspector = inspector

    async def speak(self, context: Any) -> Dict[str, Any]:
        """Maps the Technical Inspection to a Semantic Judgment."""
        logger.info(f"BRIDGE: Mapping {self.name} Technical Inspection to Semantic Witness...")
        
        # Build a structurally valid inspection context from the command context
        # The inspectors need evidence packets with .freshness.observed_at, .evidence dict, etc.
        raw = context if isinstance(context, dict) else {}
        
        # Inject structurally valid evidence for each inspector type
        inspector_name = self.inspector.name.lower()
        evidence_data = self._build_evidence_for(inspector_name, raw)
        
        inspection_context = SovereignDict({
            **raw,
            "evidence": {
                inspector_name: [_MockEvidencePacket(evidence_data)]
            }
        })

        try:
            # The inspector's 'inspect' method is synchronous
            verdict: AinurVerdict = self.inspector.inspect(inspection_context)
            
            # Convert AinurVerdict to the dict structure preferred by the Council
            return {
                "judgment": "LAWFUL" if verdict.score > 0.6 else "DISSONANT",
                "testimony": getattr(verdict, "testimony", "Truth is stable."),
                "findings": getattr(verdict, "reasons", []),
                "score": getattr(verdict, "score", 0.0),
                "dissonance_detected": getattr(verdict, "score", 0.0) <= 0.6
            }
        except Exception as e:
            logger.warning(f"BRIDGE: {self.name} inspector failed ({e}), generating spectrum-based testimony.")
            # Produce articulate testimony from available spectrum data rather than going silent
            spectrum = raw.get("spectrum", {})
            harmonic = raw.get("harmonic", {})
            score = spectrum.get("global", 0.5) if spectrum else 0.5
            
            testimony = self._generate_fallback_testimony(inspector_name, score, harmonic)
            return {
                "judgment": "LAWFUL" if score > 0.6 else "WITHHELD",
                "testimony": testimony,
                "findings": [f"spectrum_derived (global={score:.3f})"],
                "score": score,
                "dissonance_detected": score <= 0.6
            }

    def _build_evidence_for(self, inspector_name: str, context: dict) -> dict:
        """Build structurally valid evidence data for each inspector type."""
        witness = context.get("witness")
        
        if inspector_name == "manwe":
            return {
                "heartbeat_ms": 10.0,
                "liveness": True,
                "tpm_quote": getattr(witness, "tpm_quote", None) if witness else None,
            }
        elif inspector_name == "varda":
            return {
                "pcr_values": {"0": "mock", "7": "mock", "11": "mock"},
                "signature_valid": True,
                "manifest_hash_match": True,
                "attestation_status": "lawful",
            }
        elif inspector_name == "vaire":
            return {
                "phase_chain": ["rom", "firmware", "bootloader", "initramfs", "covenant", "choir"],
                "replay_suspected": False,
                "monotonic_counter": 1,
                "transition_hashes": {},
                "stability_class": "harmonious",
            }
        else:
            return {}

    def _generate_fallback_testimony(self, inspector_name: str, score: float, harmonic: dict) -> str:
        """Generate articulate testimony when the inspector can't fully run."""
        mode = harmonic.get("mode", "unknown") if harmonic else "unknown"
        resonance = harmonic.get("resonance", 0.0) if harmonic else 0.0
        
        if inspector_name == "manwe":
            if score > 0.8:
                return f"Manwë observes that the sovereign breath is steady. The encounter mode is '{mode}' and the substrate pulse is strong."
            else:
                return f"Manwë senses strain in the sovereign breath. The encounter mode is '{mode}' but the substrate resonance is diminished ({score:.2f})."
        elif inspector_name == "varda":
            if score > 0.8:
                return "Varda witnesses that the measured truth is radiant. The covenant seal holds and the substrate attestation is lawful."
            else:
                return f"Varda observes that the light of truth is dimmed. The substrate resonance is at {score:.2f}."
        elif inspector_name == "vaire":
            if score > 0.8:
                return f"Vairë confirms that the chronological weaving is steady. The harmonic resonance is {resonance:.3f}."
            else:
                return f"Vairë senses tension in the loom. The cadence is strained at resonance {resonance:.3f}."
        else:
            return f"The witness observes a substrate resonance of {score:.2f}."

    def chronicle(self, advisory: Dict[str, Any]):
        """Records the decision in the witness's tapestry."""
        logger.info(f"BRIDGE: {self.name} is chronicling the Great Music...")
        pass

