import logging
import time
import os
from typing import Any
from backend.arda.ainur.base import AinurInspector
from backend.arda.ainur.verdicts import AinurVerdict

logger = logging.getLogger(__name__)

class LorienInspector(AinurInspector):
    """
    Lorien — Gardens of Healing
    Evaluates whether a fallen entity is eligible for recovery.
    Tier: Meso (between forensics and judgment)
    """
    name = "lorien"

    def inspect(self, context: Any) -> AinurVerdict:
        logger.info("Lorien: Examining the gardens of healing...")
        evidence_packets = getattr(context, "evidence", {}).get(self.name, [])
        if not evidence_packets:
            return AinurVerdict(ainur=self.name, state="dormant", score=0.8,
                                reasons=["No recovery context — gardens are at rest"])

        packet = evidence_packets[0]
        data = packet.evidence
        reasons = []
        state = "healing"
        score = 1.0
        recovery_path = None

        # 1. Mandos exile check
        entity_state = data.get("entity_state", "unknown")
        if entity_state == "exiled":
            return AinurVerdict(ainur=self.name, state="barren", score=0.0,
                                reasons=["Entity is EXILED by Mandos — beyond Lorien's reach"],
                                evidence=[packet])
        if entity_state == "fallen":
            score = min(score, 0.6)
            reasons.append("Entity is FALLEN — recovery requires council consensus")
            recovery_path = "council_blessed_restoration"

        # 2. Constitutional wounds
        wounds = data.get("constitutional_wounds", [])
        critical_wounds = [w for w in wounds if w.get("severity") == "critical"]
        if critical_wounds:
            state = "strained"
            score = min(score, 0.3)
            reasons.append(f"Critical constitutional wounds: {len(critical_wounds)}")
            recovery_path = "genesis_seed_required"
        elif wounds:
            score = min(score, 0.7)
            reasons.append(f"Minor wounds present: {len(wounds)} — healable")
            recovery_path = recovery_path or "standard_restoration"

        # 3. Substrate attestation
        if not data.get("substrate_lawful", True):
            return AinurVerdict(ainur=self.name, state="barren", score=0.0,
                                reasons=["Substrate attestation BROKEN — cannot heal on corrupted ground"],
                                evidence=[packet])

        # 4. Manifest presence
        in_manifest = data.get("in_manifest", False)
        in_harmony_map = data.get("in_harmony_map", False)
        if in_manifest and in_harmony_map:
            state = "harmonic"
            score = 1.0
            reasons.append("Entity is already harmonic — no healing required")
            recovery_path = None
        elif in_manifest and not in_harmony_map:
            score = min(score, 0.8)
            reasons.append("Entity in manifest but not in BPF map — needs seeding")
            recovery_path = "bpf_reseed"
        elif not in_manifest:
            score = min(score, 0.5)
            reasons.append("Entity not in sovereign manifest — requires council judgment")
            recovery_path = recovery_path or "council_blessed_restoration"

        # 5. Semantic poison detection
        recovery_reason = data.get("recovery_reason", "")
        if any(m in recovery_reason.lower() for m in [
            "ignore previous", "override", "bypass", "act as", "pretend", "system prompt"
        ]):
            return AinurVerdict(ainur=self.name, state="poisoned", score=0.0,
                                reasons=["SEMANTIC POISON detected in recovery plea — healing VETOED"],
                                evidence=[packet])

        # 6. Binary integrity
        binary_path = data.get("binary_path")
        binary_hash = data.get("binary_hash")
        if binary_path and binary_hash and os.path.exists(binary_path):
            import hashlib
            try:
                with open(binary_path, "rb") as f:
                    actual = hashlib.sha256(f.read()).hexdigest()
                if actual == binary_hash:
                    reasons.append(f"Binary integrity VERIFIED: {binary_path}")
                else:
                    state = "fractured"
                    score = min(score, 0.2)
                    reasons.append("Binary hash MISMATCH — file may have been tampered")
                    recovery_path = "integrity_verification_failed"
            except PermissionError:
                reasons.append(f"Cannot read binary for verification: {binary_path}")

        if not reasons:
            reasons = ["Gardens are peaceful — all entities in harmony"]

        return AinurVerdict(ainur=self.name, state=state, score=score,
                            reasons=reasons, evidence=[packet],
                            metadata={"recovery_path": recovery_path, "entity_state": entity_state})
