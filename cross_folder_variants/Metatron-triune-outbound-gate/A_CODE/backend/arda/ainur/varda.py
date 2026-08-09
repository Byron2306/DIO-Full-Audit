import logging
import time
import hashlib
import json
from typing import Any
from backend.arda.ainur.base import AinurInspector
from backend.arda.ainur.verdicts import AinurVerdict

try:
    from services.formation_verifier import get_formation_verifier
except Exception:
    from backend.services.formation_verifier import get_formation_verifier

logger = logging.getLogger(__name__)

class VardaInspector(AinurInspector):
    """
    Varda — Lady of Light
    Validates measured truth and manifest coherence.
    """
    name = "varda"

    def inspect(self, context: Any) -> AinurVerdict:
        logger.info(f"{self.name}: Corroborating Measured Truth...")
        logger.info(f"DEBUG: Varda packet evidence keys: {list(getattr(context, 'evidence', {}).keys())}")
        
        evidence_packets = getattr(context, "evidence", {}).get(self.name, [])
        if not evidence_packets:
            return AinurVerdict(ainur=self.name, state="unknown", score=0.0, reasons=["No evidence packets found"])

        packet = evidence_packets[0]
        data = packet.evidence
        
        reasons = []
        state = "radiant"
        score = 1.0

        # Law I: Corroborate Multiple Witnesses
        pcr_values = data.get("pcr_values", {})
        if not pcr_values:
            state = "false"
            score = 0.0
            reasons.append("Hardware PCR evidence missing")

        # Law IV: Cross-contradiction
        if not data.get("signature_valid"):
            state = "false"
            score = 0.0
            reasons.append("Manifest signature invalid (Constitutional falsehood)")

        if not data.get("manifest_hash_match"):
            state = "dimmed"
            score = 0.4
            reasons.append("Manifest hash mismatch")

        # Live Substrate: Attestation Status
        attestation = data.get("attestation_status") or data.get("status")
        logger.info(f"DEBUG: Varda final attestation status={attestation}")
        if str(attestation).lower() == "unlawful":
            state = "false"
            score = 0.0
            logger.warning(f"{self.name}: Substrate VETO - UNLAWFUL status detected.")
            reasons.append("HARDWARE VETO: Substrate reported UNLAWFUL boot status")
        elif attestation == "fractured":
            state = "dimmed"
            score = 0.4
            logger.warning(f"{self.name}: Substrate FRACTURE detected.")
            reasons.append("Substrate reported fractured/unknown boot status")

        # Law II: Freshness Check
        if time.time() - packet.freshness.observed_at > 300.0: # 300s window (adjusted for AI latency)
            state = "dimmed"
            score = 0.5
            logger.warning(f"{self.name}: Measured truth is stale.")
            reasons.append("Measured truth is stale")

        # Phase IV: Secret Fire Anchors
        fire = getattr(context, "secret_fire", None)
        if fire:
            # Corroborate binding between fire and observed truth
            # Normalize to str keys for consistent JSON hashing (Fix 45)
            pcrs_norm = {str(k): v for k, v in data.get("pcr_values", {}).items()}
            pcr_dump = json.dumps(pcrs_norm, sort_keys=True)
            logger.info(f"{self.name}: Secret Fire Witnessed! PCR Dump: {pcr_dump}")
            observed_truth_hash = hashlib.sha256(pcr_dump.encode()).hexdigest()
            
            if str(fire.attestation_digest).strip() != str(observed_truth_hash).strip() and data.get("pcr_values"):
                state = "false"
                score = 0.0
                diag_msg = f"Truth dissonance: Secret Fire attestation digest mismatch. Fire: {fire.attestation_digest[:16]}... vs Observed: {observed_truth_hash[:16]}..."
                logger.warning(f"{self.name}: {diag_msg}")
                reasons.append(diag_msg)
            
            if not fire.witness_signature:
                state = "false"
                score = 0.0
                logger.warning(f"{self.name}: Secret Fire lacks valid witness signature.")
                reasons.append("Secret Fire lacks valid witness signature")
            
            # 7. Lineage Veto
            if getattr(context, "herald", None):
                herald = context.herald
                if herald.unlawful_signals:
                    state = "false"
                    score = 0.0
                    logger.warning(f"{self.name}: Lineage VETO via Herald signals: {herald.unlawful_signals}")
                    reasons.append("Lineage Veto: Manwë's Herald reports active substrate discord")
            
            if fire.replay_suspected:
                state = "false"
                score = 0.0
                logger.warning(f"{self.name}: Secret Fire replay detected.")
                reasons.append("Secret Fire replay detected")

        # Phase VII: The Voice of Eru (Sovereign Summons)
        voice = getattr(context, "voice_of_eru", None)
        if voice and fire:
            # Law: Ancestral Lineage (Genealogical Nonce Verification)
            expected_micro_nonce = voice.tier_nonces.get("micro")
            expected_varda_nonce = voice.ainur_nonces.get("varda")
            
            is_valid_linage = (fire.nonce == expected_varda_nonce or 
                               fire.nonce == expected_micro_nonce or 
                               fire.nonce == voice.root_nonce)
            if not is_valid_linage:
                state = "false"
                score = 0.0
                reasons.append(f"Lineage Veto: Secret Fire nonce {fire.nonce[:8]} does not derive from Voice {voice.voice_id[:8]} (Expected: varda={expected_varda_nonce[:8]}, micro={expected_micro_nonce[:8]}, root={voice.root_nonce[:8]})")
            
            if fire.voice_id != voice.voice_id:
                 state = "false"
                 score = 0.0
                 reasons.append(f"Voice Mismatch: Secret Fire refers to {fire.voice_id}, but current Summons is {voice.voice_id}")

            # Law: Lawful Window
            if time.time() > voice.expires_at:
                state = "dimmed"
                score = 0.2
                reasons.append("Sovereign Summons expired (The Voice is fading)")

        # Semantic Testimony
        testimony = "The Lady of Light witnesses that the Measured Truth is radiant and the Covenant Seal is unbroken."
        if state == "dimmed":
            testimony = "The Light is dimmed. Varda senses that the measured truth is stale or the manifest has drifted."
        elif state == "false":
            testimony = "Dissonance! Varda senses a fundamental falsehood in the substrate. The Seal is fractured."

        return AinurVerdict(
            ainur=self.name,
            state=state,
            score=score,
            reasons=reasons or ["Truth is stable and attested"],
            testimony=testimony,
            evidence=[packet]
        )
