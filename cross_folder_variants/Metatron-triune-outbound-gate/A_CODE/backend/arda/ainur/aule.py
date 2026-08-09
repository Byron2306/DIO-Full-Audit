import logging
import os
from typing import Any, List
from backend.arda.ainur.base import AinurInspector
from backend.arda.ainur.verdicts import AinurVerdict

logger = logging.getLogger(__name__)

class AuleInspector(AinurInspector):
    """
    Aulë — The Final Forger
    Decides whether lawful heralding is permitted based on prior verdicts.
    """
    name = "aule"

    def inspect(self, context: Any) -> AinurVerdict:
        # Aulë is special: he consumes the verdicts of others in the context
        # In this implementation, the context is assumed to contain 'prior_verdicts'
        prior_verdicts: List[AinurVerdict] = getattr(context, 'prior_verdicts', [])
        
        by_name = {v.ainur: v for v in prior_verdicts}
        vaire = by_name.get("vaire")
        varda = by_name.get("varda")
        manwe = by_name.get("manwe")
        mandos = by_name.get("mandos")
        ulmo = by_name.get("ulmo")
        
        # 0. Fallen Check (Phase III)
        failures = getattr(context, "failure_count", 0)
        if failures >= 10:
            return AinurVerdict(
                ainur=self.name,
                state="fallen",
                score=0.0,
                reasons=[f"Constitutional state: FALLEN (Persistent dissonance detected over {failures} epochs)"]
            )

        # 1. Prerequisite Check
        essential = [vaire, varda, manwe, mandos, ulmo]
        if any(v is None for v in essential):
            missing = [name for name, v in [("vaire", vaire), ("varda", varda), ("manwe", manwe), ("mandos", mandos), ("ulmo", ulmo)] if v is None]
            return AinurVerdict(
                ainur=self.name,
                state="withheld",
                score=0.0,
                reasons=[f"Prerequisite verdicts missing: {', '.join(missing)}"]
            )
            
        # 1.1 Secret Fire Sovereignty Check (Phase IV)
        fire = getattr(context, "secret_fire", None)
        if not fire:
             return AinurVerdict(
                ainur=self.name,
                state="withheld",
                score=0.0,
                reasons=["Secret Fire is not present: Reality cannot be witnessed"]
            )
        
        if not fire.freshness_valid or fire.replay_suspected:
            return AinurVerdict(
                ainur=self.name,
                state="vetoed",
                score=0.0,
                reasons=["Secret Fire is stale or replayed: Witnessing failed"]
            )

        # 2. Accumulate Signals
        veto_reasons = []
        if vaire.state == "fractured": veto_reasons.append("Vairë: Chronology is fractured")
        if varda.state == "false": veto_reasons.append("Varda: Measured truth is false")
        if ulmo.state == "dark": veto_reasons.append("Ulmo: Deep signals are dark")

        withhold_reasons = []
        if mandos.state == "lost": withhold_reasons.append("Mandos: Expected truth is lost")
        if manwe.state == "stalled": withhold_reasons.append("Manwë: System breath is stalled")
        if varda.state == "dimmed": withhold_reasons.append("Varda: Truth is dimmed")

        # 3. Constitutional Synthesis (Phase III)
        # Weighted Fusion Logic
        weights = {"varda": 0.35, "vaire": 0.25, "ulmo": 0.20, "manwe": 0.10, "mandos": 0.10}
        
        # Phase 23: Bayesian Confidence & Liar Detection
        contradictions = []
        # 1. Liar Detection: Check for extreme outliers in scores
        scores = [v.score for v in essential]
        if max(scores) - min(scores) > 0.8:
            contradictions.append(f"Witness Dissonance: Extreme score variance detected ({min(scores)} to {max(scores)})")
        
        # 2. Confidence Variance Penalty (Bayesian-ish)
        # Penalize confidence if guardians are in disagreement
        mean_score = sum(scores) / len(scores) if scores else 0.0
        variance = sum((s - mean_score) ** 2 for s in scores) / len(scores) if scores else 0.0
        trust_factor = max(0.0, 1.0 - (variance * 2.0)) # Zero trust if variance is high
        
        weighted_score = sum(by_name[k].score * weights[k] for k in weights if k in by_name)
        weighted_score *= trust_factor

        # 3. Sovereign Mode Strictures
        mode = os.getenv("CONSTITUTIONAL_MODE", "guarded")
        if mode == "sovereign":
            # Catastrophic Choral Dissonance Rule
            if manwe.state == "stalled":
                veto_reasons.append("Catastrophic Choral Dissonance: Manwë is stalled in Sovereign Mode")
            
            if any(v.state in ("dimmed", "strained", "fading", "troubled") for v in essential if v.ainur != "manwe"):
                weighted_score *= 0.8
                contradictions.append("Sovereign Mode: Implicit trust revoked due to warning signals")

        # 1.2 Sovereign Voice Continuity Check (Phase VII)
        voice = getattr(context, "voice_of_eru", None)
        if voice:
            voice_mismatches = []
            for v in essential:
                packet = v.evidence[0] if v.evidence else None
                if not packet: continue
                # Access voice_id from the new lineage fields
                p_voice_id = getattr(packet, "voice_id", None)
                if p_voice_id != voice.voice_id:
                    voice_mismatches.append(f"{v.ainur} answered {p_voice_id or 'unknown'}, expected {voice.voice_id}")
            
            if voice_mismatches:
                contradictions.append(f"Sovereign Dissonance: Witnesses answered disparate summons ({'; '.join(voice_mismatches)})")

        # 4. Contradiction Engine (Law IV)
        if varda.state == "radiant" and vaire.state == "fractured":
            contradictions.append("Impossible State: Radiant hardware truth vs. Fractured chronology")
        if manwe.state == "flowing" and any("stale" in r.lower() for r in manwe.reasons):
            contradictions.append("Impossible State: Flowing breath vs. stale liveness evidence")
        if varda.state == "radiant" and mandos.state == "lost":
            contradictions.append("Impossible State: Radiant truth vs. critical artifact loss (Mandos remembers)")
        if voice and any(v.state == "heralded" for v in essential) and not all(getattr(v.evidence[0], "voice_id", None) == voice.voice_id for v in essential if v.evidence):
            contradictions.append("Impossible State: Heralded with voice mismatch")

        # 5. Final Decision Logic
        all_reasons = veto_reasons + withhold_reasons + contradictions
        
        if contradictions:
            # Include individual inspector reasons for deep debugging
            for v in essential:
                all_reasons.append(f"Witness {v.ainur} ({v.score:.2f}): {'; '.join(v.reasons)}")
            
            weighted_score *= 0.5 # Severe trust penalty
            state = "vetoed"
            final_substate = f"dissonant (contradiction, variance={variance:.2f})"
        elif veto_reasons:
            state = "vetoed"
            final_substate = "dissonant (veto)"
        elif withhold_reasons or weighted_score < 0.85:
            state = "withheld"
            final_substate = f"strained (weighted={weighted_score:.2f})"
            if weighted_score < 0.6:
                state = "vetoed"
                final_substate = "dissonant (low score)"
        else:
            state = "harmonic"
            final_substate = "harmonic"

        return AinurVerdict(
            ainur=self.name,
            state=state,
            score=weighted_score,
            reasons=all_reasons or [f"Constitutional Synthesis: {final_substate}"],
            evidence=[v.evidence[0] for v in essential if v.evidence]
        )
