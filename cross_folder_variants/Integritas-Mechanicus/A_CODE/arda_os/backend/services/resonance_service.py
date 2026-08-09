from __future__ import annotations
import time
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from backend.schemas.polyphonic_models import ChorusState, ResonanceScore, VoiceProfile, PolyphonicContext
# from backend.arda.ainur.verdicts import ChoirVerdict (Removed for v2.0 Absolute Sanctuary)

logger = logging.getLogger("arda.resonance")

class ResonanceService:
    """
    The Conductor of the Great Music (Phase 26).
    Orchestrates the Micro, Meso, and Macro choirs to ensure continuous 
    polyphonic resonance across the Arda substrate and Seraph AI.
    """

    def __init__(self):
        self.micro_harmony: float = 1.0  # Substrate (BIOS/TPM)
        self.meso_harmony: float = 1.0   # OS/Memory/Logs
        self.macro_harmony: float = 1.0  # Seraph AI/Application
        self.global_resonance: float = 1.0
        
        self.voices: Dict[str, Dict[str, Any]] = {}
        self.last_update = time.time()
        self.dissonance_alerts: List[str] = []

    def sing_in_choir(self, tier: str, component_id: str, score: float, reasons: List[str] = None, witness: Optional[Any] = None):
        """
        Record a 'Voice' in one of the hierarchical choirs.
        Requirement: macro tier voices must be witnessed by the Secret Fire.
        """
        tier = tier.lower()
        reasons = reasons or []

        # ── SECRET FIRE VERIFICATION (Flame Imperishable) ──
        # Any voice in the Macro or Meso tier should ideally be witnessed by a forged packet.
        # This prevents logic-layer spoofing where a sub-service lies about its resonance.
        if tier in ("macro", "meso"):
            if witness is None:
                # No witness provided for a deep-layer check
                score = min(score, 0.4) 
                reasons.append("dissonance:missing_secret_fire_witness")
            else:
                # Verify freshness of the Secret Fire Forge
                try:
                    # In this architecture, we trust the witness provided by the orchestrator
                    # as long as it exists and isn't explicitly revoked.
                    is_fresh = witness.get("freshness_valid", True) if isinstance(witness, dict) else getattr(witness, "freshness_valid", True)
                    if not is_fresh:
                        score = min(score, 0.2)
                        reasons.append("dissonance:stale_reality_witness")
                except Exception:
                    score = min(score, 0.1)
                    reasons.append("dissonance:malformed_witness")

        self.voices[component_id] = {
            "tier": tier,
            "score": score,
            "reasons": reasons,
            "timestamp": time.time()
        }
        
        # Update specific tier harmony
        self._recalculate_tier(tier)
        self._recalculate_global()
        
        if score < 0.5:
            msg = f"DISSONANCE DETECTED: {tier.upper()} Choir - {component_id} is strained ({score})"
            logger.warning(msg)
            self.dissonance_alerts.append(msg)

    def _recalculate_tier(self, tier: str):
        tier_voices = [v["score"] for v in self.voices.values() if v["tier"] == tier]
        if not tier_voices:
            return
        
        # In a polyphonic model, the lowest resonance in a tier drags down the whole tier.
        # This prevents "logic layer squatting" where a compromised voice hides in the average.
        new_score = min(tier_voices)
        
        if tier == "micro":
            self.micro_harmony = new_score
        elif tier == "meso":
            self.meso_harmony = new_score
        elif tier == "macro":
            self.macro_harmony = new_score

    def _recalculate_global(self):
        # Choral Handoff: Macro depends on Meso, which depends on Micro.
        # Resonance cascade: Infrasound (Micro) is the baseline.
        self.global_resonance = self.micro_harmony * 0.5 + self.meso_harmony * 0.3 + self.macro_harmony * 0.2
        
        # If Micro is zero, global resonance collapses regardless of others
        if self.micro_harmony == 0:
            self.global_resonance = 0.0

    def get_resonance_spectrum(self) -> Dict[str, float]:
        """Returns the current multi-layered harmony score."""
        return {
            "global": round(self.global_resonance, 4),
            "micro": round(self.micro_harmony, 4),
            "meso": round(self.meso_harmony, 4),
            "macro": round(self.macro_harmony, 4),
            "alerts": self.dissonance_alerts[-5:] # Last 5 alerts
        }

    def reset(self):
        """Resets the choir to its initial harmonic state."""
        self.voices = {}
        self.micro_harmony = 1.0
        self.meso_harmony = 1.0
        self.macro_harmony = 1.0
        self.global_resonance = 1.0
        self.dissonance_alerts = []
        self.last_update = time.time()
        logger.info("ResonanceService: Choral state reset to harmony.")

    def sing_ai_adversary_signals(
        self,
        session_id: str,
        agenticity_score: float = 0.0,
        agenticity_classification: str = "LOW",
        cbr: float = 0.0,
        tbcr: float = 0.0,
        cognitive_pressure: float = 0.0,
        logic_budget_pressure: float = 0.0,
        witness: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Record AI adversary detection signals as macro-tier choir voices.
        High agenticity = dissonance in the macro choir (the AI/application layer).
        Inverted scoring: agenticity 1.0 → resonance 0.0 (fully adversarial).
        """
        # Invert: a fully agentic adversary collapses macro harmony to zero.
        agenticity_resonance = max(0.0, 1.0 - agenticity_score)
        compute_resonance = max(0.0, 1.0 - max(cbr / max(cbr, 1.0), tbcr / max(tbcr, 1.0)) if (cbr > 0 or tbcr > 0) else 1.0)
        pressure_resonance = max(0.0, 1.0 - logic_budget_pressure)

        reasons_agenticity = [f"agenticity_score:{agenticity_score:.3f}", f"classification:{agenticity_classification}"]
        if agenticity_score > 0.7:
            reasons_agenticity.append("dissonance:high_agenticity_adversary")
        if cognitive_pressure > 0.6:
            reasons_agenticity.append(f"dissonance:cognitive_pressure:{cognitive_pressure:.2f}")

        reasons_budget = [f"cbr:{cbr:.3f}", f"tbcr:{tbcr:.3f}", f"logic_budget_pressure:{logic_budget_pressure:.3f}"]
        if logic_budget_pressure >= 0.9:
            reasons_budget.append("dissonance:logic_budget_exhausted")

        self.sing_in_choir(
            tier="macro",
            component_id=f"ai_adversary_agenticity:{session_id}",
            score=agenticity_resonance,
            reasons=reasons_agenticity,
            witness=witness,
        )
        self.sing_in_choir(
            tier="macro",
            component_id=f"ai_adversary_compute:{session_id}",
            score=compute_resonance,
            reasons=reasons_budget,
            witness=witness,
        )

        return {
            "session_id": session_id,
            "agenticity_resonance": agenticity_resonance,
            "compute_resonance": compute_resonance,
            "pressure_resonance": pressure_resonance,
            "macro_harmony": self.macro_harmony,
            "global_resonance": self.global_resonance,
        }

_resonance_service_singleton: Optional[ResonanceService] = None

def get_resonance_service() -> ResonanceService:
    global _resonance_service_singleton
    if _resonance_service_singleton is None:
        _resonance_service_singleton = ResonanceService()
    return _resonance_service_singleton
