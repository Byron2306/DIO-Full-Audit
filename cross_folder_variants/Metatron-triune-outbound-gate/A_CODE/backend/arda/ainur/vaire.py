import logging
import time
import hashlib
import json
from typing import Any
from backend.arda.ainur.base import AinurInspector
from backend.arda.ainur.verdicts import AinurVerdict

try:
    from services.order_engine import get_order_engine
    from schemas.phase2_models import StabilityClass
except Exception:
    from backend.services.order_engine import get_order_engine
    from backend.schemas.phase2_models import StabilityClass

logger = logging.getLogger(__name__)

class VaireInspector(AinurInspector):
    """
    Vairë — Weaver of Order
    Validates lawful chronology and sequence.
    """
    name = "vaire"

    def inspect(self, context: Any) -> AinurVerdict:
        logger.info(f"{self.name}: Assessing Tree of Order Proof...")
        
        # Pull evidence from context (injected by Choir)
        evidence_packets = getattr(context, "evidence", {}).get(self.name, [])
        if not evidence_packets:
            return AinurVerdict(ainur=self.name, state="unknown", score=0.0, reasons=["No evidence packets found"])

        packet = evidence_packets[0]
        data = packet.evidence
        
        reasons = []
        state = "lawful"
        score = 1.0

        # Law I: Corroborate against expected phase chain
        expected_phases = ["rom", "firmware", "bootloader", "initramfs", "covenant", "choir"]
        observed_phases = data.get("phase_chain", [])
        
        if not observed_phases:
            return AinurVerdict(ainur=self.name, state="fractured", score=0.0, reasons=["Empty phase chain"])

        # Detect impossible phase transitions
        for i, phase in enumerate(observed_phases):
            if i < len(expected_phases) and phase != expected_phases[i]:
                state = "fractured"
                score = 0.0
                reasons.append(f"Phase dissonance: expected {expected_phases[i]}, found {phase}")
                break

        # Law II: Freshness Check
        if time.time() - packet.freshness.observed_at > 300.0: # 300s window (adjusted for AI latency)
            state = "fractured"
            score = 0.3
            reasons.append("Chronological evidence is stale")

        if data.get("replay_suspected"):
            state = "fractured"
            score = 0.0
            reasons.append("Replay suspected in chronological sequence")

        if data.get("monotonic_counter", 0) <= 0:
            state = "fractured"
            score = 0.1
            reasons.append("Invalid monotonic counter")

        # Live Substrate: Stability Class
        stability = data.get("stability_class")
        if stability == "fractured":
            state = "fractured"
            score = 0.0
            reasons.append("SUBSTRATE FRACTURE: Order engine reported fractured stability")
        elif stability in ["strained", "dissonant"]:
            state = "strained"
            score = min(score, 0.4)
            reasons.append(f"Substrate Tension: Stability is {stability}")

        # Phase IV: Secret Fire Anchors
        fire = getattr(context, "secret_fire", None)
        if fire:
            # Corroborate binding between fire and observed truth
            # We use the transition hashes as the anchor for order truth
            observed_order_hash = hashlib.sha256(json.dumps(data.get("transition_hashes"), sort_keys=True).encode()).hexdigest()
            
            if fire.order_digest != observed_order_hash and data.get("transition_hashes"):
                 state = "fractured"
                 score = 0.0
                 reasons.append("Chronological dissonance: Secret Fire digest mismatch")
            
            # Law: The Fire must be at least as new as the observed state
            if fire.monotonic_counter < data.get("monotonic_counter", 0):
                state = "fractured"
                score = 0.0
                reasons.append(f"Monotonic counter regression: Fire({fire.monotonic_counter}) < Substrate({data.get('monotonic_counter')})")
            
            if not fire.freshness_valid:
                state = "fractured"
                score = min(score, 0.4)
                reasons.append("Secret Fire freshness is invalid")

        # Semantic Testimony
        testimony = "Vairë the Weaver confirms that the Loom of Time is steady and the sequence is lawful."
        if state == "fractured":
            testimony = "The Weaving is torn! Vairë detects a chronological fracture or a replay in the sequence."
        elif state == "strained":
            testimony = "The Loom is strained. Vairë senses tension in the substrate stability of order."

        return AinurVerdict(
            ainur=self.name,
            state=state,
            score=score,
            reasons=reasons or ["Lawful chronology confirmed"],
            testimony=testimony,
            evidence=[packet]
        )
