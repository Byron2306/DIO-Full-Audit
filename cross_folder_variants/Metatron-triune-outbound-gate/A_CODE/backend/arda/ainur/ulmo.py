import logging
import hashlib
import json
from typing import Any
from backend.arda.ainur.base import AinurInspector
from backend.arda.ainur.verdicts import AinurVerdict

logger = logging.getLogger(__name__)

class UlmoInspector(AinurInspector):
    """
    Ulmo — Lord of Depth
    Surfaces hidden anomalies below normal visibility.
    """
    name = "ulmo"

    def inspect(self, context: Any) -> AinurVerdict:
        logger.info(f"{self.name}: Assessing Deep Manifestation Evidence...")
        
        evidence_packets = getattr(context, "evidence", {}).get(self.name, [])
        if not evidence_packets:
            return AinurVerdict(ainur=self.name, state="unknown", score=0.0, reasons=["No deep signals found"])

        packet = evidence_packets[0]
        data = packet.evidence
        
        reasons = []
        state = "clear"
        score = 1.0

        # Law I: Deep Evidence Fusion
        signals = data.get("signals", [])
        anomaly_count = data.get("anomaly_count", 0)
        max_risk = data.get("max_risk_score", 0.0)

        if anomaly_count > 0:
            if max_risk > 0.8:
                state = "dark"
                score = 0.0
                reasons.append(f"Substrate VETO: {anomaly_count} high-risk anomalies detected (Max Score: {max_risk:.2f})")
            elif max_risk > 0.4:
                state = "troubled"
                score = min(score, 0.4)
                reasons.append(f"Substrate Tension: {anomaly_count} moderate-risk anomalies (Max Score: {max_risk:.2f})")
        
        for signal in signals:
            # Audit individual high-risk signals if needed
            pass

        # Law III: Memory Coherence
        mem_coherence = data.get("memory_coherence", 1.0)
        if mem_coherence < 0.8:
            state = "troubled"
            score = min(score, 0.5)
            reasons.append(f"Memory map discontinuity detected (coherence={mem_coherence})")

        # Phase IV: Secret Fire Entropy
        fire = getattr(context, "secret_fire", None)
        if fire:
            if fire.entropy_digest and fire.entropy_digest == "0000000000000000000000000000000000000000000000000000000000000000":
                state = "dark"
                score = 0.0
                reasons.append("Invalid entropy anchor in Secret Fire (Null heat)")
            
            # Law IV: Cross-contradiction vs deep state
            observed_signals_hash = hashlib.sha256(json.dumps(data.get("signals"), sort_keys=True).encode()).hexdigest()
            if fire.runtime_digest != observed_signals_hash and data.get("signals"):
                 state = "dark"
                 score = 0.0
                 logger.warning(f"{self.name}: Deep state dissonance: Secret Fire runtime digest mismatch. Fire: {fire.runtime_digest[:16]}... vs Observed: {observed_signals_hash[:16]}...")
                 reasons.append("Deep state dissonance: Secret Fire runtime digest mismatch")

        return AinurVerdict(
            ainur=self.name,
            state=state,
            score=score,
            reasons=reasons or ["The deep places are clear and serene"],
            evidence=[packet]
        )
