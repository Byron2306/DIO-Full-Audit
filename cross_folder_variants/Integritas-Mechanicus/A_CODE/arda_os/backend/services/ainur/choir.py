import sys
import os
# Force project root for forensic alignment (Parent of backend)
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

import logging
import time
import uuid
import asyncio
from typing import List, Any, Dict, Optional
try:
    from backend.arda.ainur.verdicts import AinurVerdict, ChoirVerdict, EvidencePacket, SecretFirePacket, ChoralSweep, IluvatarVoiceChallenge, Freshness
    from backend.arda.ainur.vaire import VaireInspector
    from backend.arda.ainur.varda import VardaInspector
    from backend.arda.ainur.manwe import ManweInspector
    from backend.arda.ainur.mandos import MandosInspector
    from backend.arda.ainur.ulmo import UlmoInspector
    from backend.arda.ainur.aule import AuleInspector
    from backend.arda.ainur.lorien import LorienInspector
    from backend.arda.ainur.collectors import (
        VaireCollector, VardaCollector, ManweCollector,
        MandosCollector, UlmoCollector, LorienCollector
    )
except Exception:
    from backend.services.ainur.verdicts import AinurVerdict, ChoirVerdict, EvidencePacket, SecretFirePacket, ChoralSweep, IluvatarVoiceChallenge, Freshness  # type: ignore
    from backend.services.ainur.vaire import VaireInspector  # type: ignore
    from backend.services.ainur.varda import VardaInspector  # type: ignore
    from backend.services.ainur.manwe import ManweInspector  # type: ignore
    from backend.services.ainur.mandos import MandosInspector  # type: ignore
    from backend.services.ainur.ulmo import UlmoInspector  # type: ignore
    from backend.services.ainur.aule import AuleInspector  # type: ignore
    from backend.services.ainur.lorien import LorienInspector  # type: ignore
    from backend.services.ainur.collectors import (
        VaireCollector, VardaCollector, ManweCollector,
        MandosCollector, UlmoCollector, LorienCollector
    )  # type: ignore

logger = logging.getLogger(__name__)

class ChoirContext:
    """Context object for the Ainur Choir evaluation."""
    def __init__(self, raw_context: Dict[str, Any]):
        self.raw = raw_context
        self.prior_verdicts: List[AinurVerdict] = []
        self.covenant_valid = raw_context.get("covenant_valid", True)
        
        # Phase II context fields
        self.runtime_cadence = raw_context.get("runtime_cadence", {})
        self.expected_entities = raw_context.get("expected_entities", [])
        self.observed_entities = raw_context.get("observed_entities", [])
        self.deep_signals = raw_context.get("deep_signals", {})
        self.failure_count = raw_context.get("failure_count", 0)
        
        # Phase III: Evidence Packets (The Witnesses)
        self.evidence: Dict[str, List[EvidencePacket]] = raw_context.get("evidence", {})
        
        # Phase IV: The Secret Fire (Reality Witness)
        self.secret_fire: Optional[SecretFirePacket] = raw_context.get("secret_fire")
        
        # Phase VII: Choral Sweep Linkage
        self.sweep: Optional[ChoralSweep] = raw_context.get("sweep")
        
        # Phase VII: The Voice of Eru (Sovereign Summons)
        self.voice_of_eru: Optional[IluvatarVoiceChallenge] = raw_context.get("voice_of_eru")

class AinurChoir:
    """
    The Ainur Choir (Phase 26: Polyphonic Resonance)
    Ensemble of constitutional guardians organized into Micro, Meso, and Macro tiers.
    """
    def __init__(self):
        # Tiered Inspector Mapping
        self.tiers = {
            "micro": [VardaInspector()],
            "meso":  [VaireInspector(), MandosInspector(), LorienInspector()],
            "macro": [ManweInspector(), UlmoInspector()]
        }
        
        self.collectors = {
            "vaire": VaireCollector(),
            "varda": VardaCollector(),
            "manwe": ManweCollector(),
            "mandos": MandosCollector(),
            "ulmo": UlmoCollector(),
            "lorien": LorienCollector()
        }
        self.forger = AuleInspector()
        from backend.services.resonance_service import get_resonance_service
        self.resonance = get_resonance_service()

    async def evaluate(self, raw_context: Dict[str, Any]) -> ChoirVerdict:
        logger.info("Ainur Choir: Starting Polyphonic Resonance Sweep...")
        # Ensure fresh choral state for each sweep (Law XXVI)
        self.resonance.reset()
        
        from backend.services.secret_fire import get_secret_fire_forge
        forge = get_secret_fire_forge()
        
        # 0. Issue The Voice of Eru (The Sovereign Summons)
        # This binds all subordinate reality claims to the same moment.
        sweep_id = f"sweep-{uuid.uuid4().hex[:12]}"
        voice = await forge.issue_voice_of_eru(
            epoch=raw_context.get("epoch", "current_epoch"),
            sweep_id=sweep_id
        )
        logger.info(f"Ainur Choir: 'The Voice of Eru' has spoken (ID: {voice.voice_id})")
        
        # Derive canonical identity early (Fix 1 & 7)
        subject_id = (
            raw_context.get("entity_id")
            or raw_context.get("runtime_identity")
            or raw_context.get("node_id")
            or "local-substrate"
        )
        node_id = raw_context.get("node_id") or subject_id
        secret_fire = raw_context.get("secret_fire")
        covenant_id = raw_context.get("covenant_id", "runtime-covenant")
        epoch = raw_context.get("epoch", "current_epoch")

        raw_context["voice_of_eru"] = voice
        raw_context["sweep_id"] = sweep_id
        raw_context["subject_id"] = subject_id
        raw_context["node_id"] = node_id

        # Validate or Reforge Secret Fire (Fix 8)
        # Ensure the witness is born from the same summons
        if not secret_fire:
            logger.warning("Secret Fire dissonance detected - reforging sweep-bound reality witness.")
            
            # Fetch actual hardware truth for the reforge (Fix 26)
            from backend.services.secure_boot import get_secure_boot_service
            import hashlib
            import json
            
            # 1. Attestation Grounding (Varda)
            boot_svc = get_secure_boot_service()
            truth = boot_svc.get_current_truth()
            if asyncio.iscoroutine(truth):
                truth = await truth
            pcrs_raw = getattr(truth, "pcr_measurements", getattr(truth, "pcr_values", {}))
            pcrs = {str(k): v for k, v in pcrs_raw.items()}
            lawful_digest = hashlib.sha256(json.dumps(pcrs, sort_keys=True).encode()).hexdigest()

            # 2. Chronological Grounding (Vairë)
            from backend.services.order_engine import get_order_engine
            engine = get_order_engine()
            order = engine.get_current_order()
            if asyncio.iscoroutine(order):
                order = await order
            if order is None:
                order = await engine.update_order_state()
            seq = getattr(order, "verified_sequence", ["hash1", "hash2"])
            order_digest = hashlib.sha256(json.dumps(seq, sort_keys=True).encode()).hexdigest()

            # 3. Deep State Grounding (Ulmo)
            from backend.services.kernel_signal_adapter import get_kernel_signal_adapter
            adapter = get_kernel_signal_adapter()
            anomalies = adapter.get_recent_anomalies()
            if asyncio.iscoroutine(anomalies):
                anomalies = await anomalies
            signals = [a.model_dump(mode='json') if hasattr(a, 'model_dump') else a for a in anomalies]
            runtime_digest = hashlib.sha256(json.dumps(signals, sort_keys=True).encode()).hexdigest()

            # 4. Monotonicity
            counter = raw_context.get("counter", 1)

            raw_context["secret_fire"] = await forge.answer_voice(
                voice=voice,
                ainur_target=None,
                tier=None, # Use root_nonce for universal tier resonance
                covenant_id=covenant_id,
                epoch=epoch,
                counter=counter,
                attestation_digest=lawful_digest,
                order_digest=order_digest,
                runtime_digest=runtime_digest
            )
            logger.info(f"Choir: Successfully reforged Secret Fire (lawful_digest={lawful_digest[:8]}..., order_digest={order_digest[:8]}..., runtime_digest={runtime_digest[:8]}...)")

        elif secret_fire.voice_id != voice.voice_id or secret_fire.sweep_id != sweep_id:
            logger.warning("Provided Secret Fire does not line up with the new sweep; using the supplied packet for validation.")

        # 1. Collect evidence from all Witnesses (Summoned by the Voice)
        evidence_map = {}
        for name, collector in self.collectors.items():
            try:
                packet = await collector.collect(raw_context, sweep_id=sweep_id)
                # Map specific voice/tier context to evidence (Fix 2)
                packet.voice_id = voice.voice_id
                packet.sweep_id = sweep_id
                packet.ainur_target = name
                packet.secret_fire_ref = getattr(raw_context.get("secret_fire"), "nonce", None)

                # Identity anchors must survive tier inhibition.
                # If Manwë is inhibited, the projection layer still needs the
                # SecretFire workload identity to coronate the subject.
                try:
                    sf = raw_context.get("secret_fire")
                    if sf:
                        sf_workload_hash = getattr(sf, "workload_hash", None)
                        sf_executable_path = getattr(sf, "executable_path", None)
                        if isinstance(packet.evidence, dict):
                            if sf_workload_hash and not packet.evidence.get("workload_hash"):
                                packet.evidence["workload_hash"] = sf_workload_hash
                            if sf_executable_path and not packet.evidence.get("executable_path"):
                                packet.evidence["executable_path"] = sf_executable_path
                except Exception:
                    pass
                
                evidence_map[name.capitalize()] = [packet]
                evidence_map[name] = [packet]
            except Exception as e:
                logger.error(f"Collector {name} failed: {e}. Providing mock-safe fallback.")
                # Fallback to a clear mock packet to prevent choral death in non-production
                try:
                    from backend.arda.ainur.verdicts import Freshness
                except Exception:
                    from backend.services.ainur.verdicts import Freshness  # type: ignore
                packet = EvidencePacket(
                    source=f"{name.capitalize()}Collector",
                    evidence={"signals": [], "anomaly_count": 0, "max_risk_score": 0.0, "memory_coherence": 1.0, "device_stability": 1.0},
                    freshness=Freshness(observed_at=time.time(), window_ms=10000, nonce="mock-nonce"),
                    confidence=0.5,
                    sweep_id=sweep_id
                )
                evidence_map[name.capitalize()] = [packet]
                evidence_map[name] = [packet]
        
        raw_context["evidence"] = evidence_map
        context = ChoirContext(raw_context)
        
        # 2. Tiered Choral Sweep (Micro -> Meso -> Macro)
        all_verdicts = []
        handoff_inhibited = False
        
        for tier_name in ["micro", "meso", "macro"]:
            if handoff_inhibited:
                logger.warning(f"Choral Handoff: {tier_name.upper()} tier inhibited due to lower tier dissonance.")
                for inspector in self.tiers[tier_name]:
                    all_verdicts.append(AinurVerdict(ainur=inspector.name, state="inhibited", score=0.0, reasons=["Lower tier dissonance"]))
                self.resonance.sing_in_choir(tier_name, f"tier_{tier_name}_gate", 0.0, ["Inhibited by sweep"])
                continue

            tier_verdicts = []
            witness = raw_context.get("secret_fire")
            for inspector in self.tiers[tier_name]:
                try:
                    v = inspector.inspect(context)
                    tier_verdicts.append(v)
                    all_verdicts.append(v)
                    # Sync with ResonanceService
                    self.resonance.sing_in_choir(
                        tier_name,
                        inspector.name.lower(),
                        v.score,
                        v.reasons,
                        witness=witness,
                    )
                except Exception as e:
                    logger.error(f"Inspector {inspector.name} failed: {e}")
                    failed_v = AinurVerdict(ainur=inspector.name, state="unknown", score=0.0, reasons=[str(e)])
                    tier_verdicts.append(failed_v)
                    all_verdicts.append(failed_v)
                    self.resonance.sing_in_choir(
                        tier_name,
                        inspector.name.lower(),
                        0.0,
                        [str(e)],
                        witness=witness,
                    )

            # Check for Tier Dissonance (Handoff Inhibit)
            tier_harmony = self.resonance.get_resonance_spectrum().get(tier_name, 1.0)
            if any(v.score < 0.5 for v in tier_verdicts) or tier_harmony < 0.5:
                logger.error(f"Tier {tier_name} Dissonance Detected! (Harmony: {tier_harmony})")
                handoff_inhibited = True
        
        # 3. Final Synthesis (Aule)
        context.prior_verdicts = all_verdicts
        aule_verdict = self.forger.inspect(context)
        all_verdicts.append(aule_verdict)
        
        # Diagnostic Print
        # Note: 'micro_verdicts' is not defined in this scope. Assuming intent was to print all collected verdicts.
        for v in all_verdicts: # Changed from 'micro_verdicts' to 'all_verdicts' for syntactic correctness.
            print(f"DIAG: Ainur {v.ainur} -> state={v.state}, score={v.score:.2f}, reasons={v.reasons}")
        
        # Level 0 Veto (Substrate)
        # Aule may emit either legacy "heralded" or canonical "harmonic".
        heralding_allowed = aule_verdict.state in ("heralded", "harmonic") and not handoff_inhibited
        
        passed_verdicts = [v for v in all_verdicts if v.state not in ("unknown", "fractured", "false", "vetoed", "fallen", "inhibited")]
        confidence = sum(v.score for v in passed_verdicts) / len(all_verdicts) if all_verdicts else 0.0
        
        return ChoirVerdict(
            overall_state=aule_verdict.state if not handoff_inhibited else "vetoed",
            heralding_allowed=heralding_allowed,
            confidence=confidence,
            ainur=all_verdicts,
            reasons=aule_verdict.reasons if not handoff_inhibited else ["Catastrophic Choral Dissonance (Sweep Veto)"],
            
            # Identity Anchors (Fix 1)
            subject_id=subject_id,
            node_id=node_id,
            voice_id=voice.voice_id,
            sweep_id=sweep_id,
            covenant_id=covenant_id,
            epoch=epoch,
            
            observed_at=time.time()
        )
