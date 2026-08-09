import logging
from typing import Any
from backend.arda.ainur.base import AinurInspector
from backend.arda.ainur.verdicts import AinurVerdict

logger = logging.getLogger(__name__)

class MandosInspector(AinurInspector):
    """
    Mandos — Keeper of the Dead
    Detects absence of expected truth (missing processes/services).
    """
    name = "mandos"

    def inspect(self, context: Any) -> AinurVerdict:
        logger.info(f"{self.name}: Assessing Absence Memory (Dead Ledger)...")
        
        evidence_packets = getattr(context, "evidence", {}).get(self.name, [])
        if not evidence_packets:
            return AinurVerdict(ainur=self.name, state="unknown", score=0.0, reasons=["No absence evidence found"])

        packet = evidence_packets[0]
        data = packet.evidence
        
        reasons = []
        state = "remembered"
        score = 1.0

        # Law I: Compare expected vs observed through memory
        expected = set(data.get("expected_entities", []))
        observed_count = data.get("protected_manifestations_count", 0)
        
        # If no protected processes are running but we expect the herald/quorum, it's a gap
        if expected and observed_count < len(expected):
            state = "fading"
            score = 0.4
            reasons.append(f"Substrate Gap: Only {observed_count} protected manifestations active (Expected: {len(expected)})")
        elif observed_count > len(expected) + 5:
             # Spontaneous manifestation of too many processes is also suspicious
             state = "lost"
             score = 0.2
             reasons.append(f"Spontaneous Creation: {observed_count} manifestations exceeds expected baseline")

        # Law III: Memory of vanishing
        vanished = data.get("vanished_since_last_epoch", [])
        if vanished:
            state = "lost"
            score = 0.2
            reasons.append(f"Entities vanished since last epoch: {', '.join(vanished)}")

        if data.get("erasure_suspected"):
            state = "lost"
            score = 0.0
            reasons.append("Evidence of artifact erasure detected (Mandos remembers)")

        # Phase 21: Shadow Memory Forensics
        flicker = data.get("flicker_events", [])
        if len(flicker) > 2:
            state = "fading"
            score = min(score, 0.4)
            reasons.append(f"Anti-stealth: Transient entity flicker detected ({len(flicker)} events)")
        
        log_meta = data.get("log_metadata", {})
        if log_meta.get("sequence_gap", 0) > 0:
            state = "lost"
            score = 0.0
            reasons.append(f"Log Forensics: Journal sequence gap detected ({log_meta['sequence_gap']})")
        
        if log_meta.get("timestamp_discontinuity", 0.0) > 1.0:
            state = "fading"
            score = min(score, 0.5)
            reasons.append("Log Forensics: Temporal discontinuity in system logs")

        return AinurVerdict(
            ainur=self.name,
            state=state,
            score=score,
            reasons=reasons or ["No unauthorized absence detected"],
            evidence=[packet]
        )
