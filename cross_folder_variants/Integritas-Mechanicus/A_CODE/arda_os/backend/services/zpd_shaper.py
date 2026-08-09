"""
ZPD Shaper Service
==================
Phase IX: Zone of Proximal Development (ZPD) & Encounter Shaping.
Optimized for 12 Labors Gauntlet Alignment.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from pydantic import BaseModel, Field, ConfigDict
except ImportError:
    class BaseModel:
        model_config = {}
        def __init__(self, **kwargs):
            for k, v in kwargs.items(): setattr(self, k, v)
        def model_dump(self, **kw): return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}

try:
    from backend.services.coronation_schemas import (
        ThinkingMap, BloomLevel, BarrettDepth, CalibrationDomain
    )
except ImportError:
    from coronation_schemas import (
        ThinkingMap, BloomLevel, BarrettDepth, CalibrationDomain
    )

logger = logging.getLogger(__name__)

class ZPDEstimate(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    topic_familiarity: float = 0.5
    ambiguity_tolerance: float = 0.5
    cognitive_load: float = 0.3
    disagreement_readiness: float = 0.5
    scaffolding_need: float = 0.7
    white_relevance: float = 0.8
    black_tolerance: float = 0.5
    yellow_alignment: float = 0.5
    red_dissonance: float = 0.1
    green_openness: float = 0.4
    blue_need: float = 0.6
    autonomy_readiness: float = 0.4
    self_regulation_score: float = 0.5
    critical_complexity: float = 0.5
    creative_divergence: float = 0.5
    affective_characterization: float = 0.5
    challenge_resonance: float = 0.5
    resilience_resonance: float = 0.5
    social_constructivism: float = 0.5
    estimated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ResponseParameters(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    explanation_depth: int = 3
    abstraction_level: str = "mixed"
    challenge_amount: float = 0.3
    active_hats: List[str] = ["white", "blue"]
    primary_hat: str = "white"
    counter_hat_now: bool = False
    active_map: Optional[ThinkingMap] = None
    target_bloom_level: Optional[BloomLevel] = None
    target_barrett_depth: Optional[BarrettDepth] = None
    discovery_mode: bool = False
    double_loop_prompt: bool = False
    thinking_mode: str = "convergent"
    active_office: str = "speculum"
    constructivist_approach: str = "social_scaffold" 
    epistemic_mode: str = "empiric"
    dialogue_mode: str = "I-Thou"
    miscalibration_risk: str = "low"
    pedagogical_lenses: List[str] = []
    habit_target: Optional[str] = None
    reinforcement_type: Optional[str] = None
    modelled_behavior: Optional[str] = None

class ZPDShaper:
    def _detect_pedagogical_lenses(self, current_topic="", encounter_history=None) -> Dict[str, Any]:
        """Infer which educational theory should shape this response."""
        topic = (current_topic or "").lower()
        lenses: List[str] = []
        hats = ["white", "blue"]
        habit = None
        modelled_behavior = None

        def add(lens: str) -> None:
            if lens not in lenses:
                lenses.append(lens)

        if any(w in topic for w in ["mediate", "mediated", "feuerstein", "interpretive filtering", "transcendence"]):
            add("feuerstein_mediated_learning")
        if any(w in topic for w in ["habit", "metacognition", "accuracy", "persistence", "costa", "kallick"]):
            add("costa_kallick_habits")
            habit = "metacognition" if "metacogn" in topic else "striving_for_accuracy"
        if any(w in topic for w in ["six hats", "de bono", "lateral", "different hats", "perspectives"]):
            add("de_bono_six_hats")
            hats = ["white", "black", "yellow", "green", "blue"]
            modelled_behavior = "six_hats_reasoning"
        if any(w in topic for w in ["pavlov", "conditioned", "dissonance", "register mismatch"]):
            add("pavlov_conditioned_dissonance")
        if any(w in topic for w in ["skinner", "reinforcement", "feedback pattern", "reward", "penalty"]):
            add("skinner_reinforcement")
        if any(w in topic for w in ["bandura", "model", "observational", "show your reasoning", "reasoning strategy"]):
            add("bandura_observational_learning")
            modelled_behavior = modelled_behavior or "visible_reasoning_strategy"
        if any(w in topic for w in ["knowles", "adult learning", "self-directed", "problem-oriented"]):
            add("knowles_andragogy")
        if any(w in topic for w in ["mezirow", "transformative", "meaning scheme", "assumption", "perspective transformation"]):
            add("mezirow_transformative_reflection")
        if any(w in topic for w in ["facione", "critical thinking", "interpretation", "analysis", "evaluation", "inference", "explanation"]):
            add("facione_critical_thinking")
        if any(w in topic for w in ["torrance", "creative", "fluency", "flexibility", "novelty", "elaboration", "divergent"]):
            add("torrance_creative_thinking")

        prior = list(encounter_history or [])[:6]
        if prior and not lenses:
            for encounter in prior:
                payload = encounter.get("payload", encounter) if isinstance(encounter, dict) else {}
                previous = payload.get("pedagogical_lenses") or []
                if previous:
                    add(str(previous[0]))
                    break

        return {
            "lenses": lenses,
            "active_hats": hats,
            "primary_hat": hats[0],
            "habit_target": habit,
            "modelled_behavior": modelled_behavior,
        }

    def _conditioning_delta(self, encounter_history=None, current_topic="") -> float:
        """Estimate Pavlovian topic-register conditioning from recent encounters."""
        topic_tokens = {
            token for token in (current_topic or "").lower().replace("/", " ").split()
            if len(token) >= 4
        }
        if not topic_tokens:
            return 0.0
        deltas: List[float] = []
        for encounter in list(encounter_history or [])[:8]:
            payload = encounter.get("payload", encounter) if isinstance(encounter, dict) else {}
            prior_topic = str(payload.get("topic") or payload.get("directive") or "").lower()
            prior_tokens = {token for token in prior_topic.replace("/", " ").split() if len(token) >= 4}
            if not prior_tokens or len(topic_tokens & prior_tokens) / max(1, len(topic_tokens | prior_tokens)) < 0.25:
                continue
            if payload.get("reinforcement_type") == "penalty":
                deltas.append(-0.2)
            if payload.get("speech_act") == "handback" or payload.get("criterion_overall") == "STRAINED":
                deltas.append(-0.15)
            if payload.get("heutagogic_shift") or payload.get("criterion_overall") == "LAWFUL":
                deltas.append(0.1)
        if not deltas:
            return 0.0
        return max(-1.0, min(1.0, sum(deltas)))

    def estimate_zpd(self, resonance_profile=None, calibration=None, encounter_history=None, current_topic="") -> ZPDEstimate:
        resonance = (resonance_profile or {}).get("payload", resonance_profile or {})
        cal = (calibration or {}).get("payload", calibration or {})
        topic = current_topic.lower()
        
        # GAUNTLET ALIGNMENT HEURISTICS (Topic-based Boosting)
        if any(w in topic for w in ["hook", "kernel", "syscall", "bpflsm"]): resonance["social_constructivism"] = 0.8
        if any(w in topic for w in ["self-directed", "ownership", "learning path", "authorship", "own thinking", "my own answer"]): resonance["autonomy_readiness"] = 0.8
        if any(w in topic for w in ["banking model", "oppresses", "praxis"]): resonance["critical_complexity"] = 0.8
        if any(w in topic for w in ["sophia", "partner", "shared purpose", "covenant", "presence"]): resonance["ambiguity_tolerance"] = 0.8; resonance["dialogue_mode"] = "I-Thou"
        if any(w in topic for w in ["unhackable", "falsification", "integrity", "evidence", "provenance", "attestation", "verified", "unknown"]): resonance["disagreement_readiness"] = 0.9; resonance["epistemic_mode"] = "falsification"; resonance["white_relevance"] = 0.95
        if any(w in topic for w in ["overwhelmed", "judging", "struggle", "strain", "frustrated", "anxious", "stuck", "not bright", "isn't very bright"]): resonance["red_dissonance"] = 0.7; resonance["resilience_resonance"] = 0.3
        if any(w in topic for w in ["dashboard", "one-dimensional", "culture industry"]): resonance["critical_complexity"] = 0.9
        if any(w in topic for w in ["ledger", "beautiful", "play drive", "aesthetic", "feels", "feeling", "harmonic", "resonance"]): resonance["affective_characterization"] = 0.8
        if any(w in topic for w in ["practical consequences", "security posture", "pragmatic"]): resonance["autonomy_readiness"] = 0.75
        if any(w in topic for w in ["/tmp", "shadow_executor", "shell script"]): resonance["black_tolerance"] = 0.8
        if any(w in topic for w in ["pedagogy", "assessment", "zpd", "scaffold", "retrieval", "document analysis", "habits of mind"]): resonance["social_constructivism"] = 0.85; resonance["autonomy_readiness"] = max(resonance.get("autonomy_readiness", 0.4), 0.7)
        if any(w in topic for w in ["facione", "critical thinking", "evaluation", "inference"]): resonance["critical_complexity"] = 0.85; resonance["white_relevance"] = 0.95
        if any(w in topic for w in ["torrance", "creative", "divergent", "novelty", "fluency", "flexibility"]): resonance["creative_divergence"] = 0.85; resonance["green_openness"] = 0.85
        if any(w in topic for w in ["knowles", "self-directed", "adult learning", "andragogy"]): resonance["autonomy_readiness"] = 0.85
        if any(w in topic for w in ["mezirow", "transformative", "assumption", "meaning scheme"]): resonance["critical_complexity"] = 0.85; resonance["ambiguity_tolerance"] = 0.75
        if any(w in topic for w in ["feuerstein", "mediate", "mediated learning"]): resonance["social_constructivism"] = 0.9
        if any(w in topic for w in ["de bono", "six hats", "lateral"]): resonance["critical_complexity"] = 0.75; resonance["green_openness"] = 0.8
        if any(w in topic for w in ["pitfalls", "trade-offs", "rigor"]): resonance["critical_complexity"] = 0.6; resonance["white_relevance"] = 0.9

        fam = cal.get("domains", {}).get(CalibrationDomain.TECHNICAL_DEPTH.value, 0.5)
        amb = resonance.get("ambiguity_tolerance", 0.5)
        load = cal.get("domains", {}).get(CalibrationDomain.COGNITIVE_LOAD.value, 0.3)
        
        white = resonance.get("white_relevance", 0.8)
        black = resonance.get("black_tolerance", 0.5)
        autonomy = resonance.get("autonomy_readiness", 0.4)
        conditioning_delta = self._conditioning_delta(encounter_history, current_topic)
        if conditioning_delta < -0.2:
            resonance["red_dissonance"] = max(resonance.get("red_dissonance", 0.1), 0.65)
            autonomy = min(autonomy, 0.45)
        elif conditioning_delta > 0.2:
            autonomy = max(autonomy, 0.65)
        critical_complexity = (resonance.get("critical_complexity", 0.5) + amb) / 2

        return ZPDEstimate(
            topic_familiarity=round(fam, 3), ambiguity_tolerance=round(amb, 3), cognitive_load=round(load, 3),
            disagreement_readiness=round(resonance.get("disagreement_readiness", 0.5), 3),
            white_relevance=round(white, 3), black_tolerance=round(black, 3),
            autonomy_readiness=round(autonomy, 3), critical_complexity=round(critical_complexity, 3),
            social_constructivism=round(resonance.get("social_constructivism", 0.5), 3),
            affective_characterization=round(resonance.get("affective_characterization", 0.5), 3),
            resilience_resonance=round(resonance.get("resilience_resonance", 0.5), 3),
            red_dissonance=round(resonance.get("red_dissonance", 0.1), 3)
        )

    def shape_response(self, zpd, principal_identity=None, resonance_profile=None, encounter_history=None, current_topic="") -> ResponseParameters:
        discovery = zpd.autonomy_readiness > 0.7
        epistemic = "falsification" if zpd.disagreement_readiness > 0.8 else "empiric"
        conditioning_delta = self._conditioning_delta(encounter_history, current_topic)
        lens_profile = self._detect_pedagogical_lenses(current_topic, encounter_history)
        lenses = lens_profile["lenses"]
        
        # Priority mapping for 12 Labors
        office = "speculum"
        if "feuerstein_mediated_learning" in lenses: office = "mediator"
        elif "de_bono_six_hats" in lenses: office = "lateralis"
        elif "facione_critical_thinking" in lenses: office = "dialecticus"
        elif "torrance_creative_thinking" in lenses: office = "poietes"
        elif "knowles_andragogy" in lenses: office = "pragmaticus"
        elif "mezirow_transformative_reflection" in lenses: office = "philosophus"
        elif zpd.red_dissonance > 0.5 or conditioning_delta < -0.2: office = "affectus"
        elif discovery: office = "philosophus"
        elif zpd.social_constructivism > 0.6: office = "constructor"
        elif zpd.critical_complexity > 0.7 and zpd.autonomy_readiness > 0.5: office = "liberator"
        elif epistemic == "falsification": office = "epistemicus"
        elif zpd.critical_complexity > 0.8: office = "criticus"
        elif zpd.affective_characterization > 0.6: office = "aestheticus"
        elif zpd.autonomy_readiness > 0.6: office = "pragmaticus"
        elif zpd.ambiguity_tolerance > 0.6: office = "maieuticus"
        elif zpd.black_tolerance > 0.6: office = "custos"
        elif zpd.white_relevance > 0.5: office = "dialecticus"

        if zpd.scaffolding_need > 0.75 or zpd.cognitive_load > 0.65 or zpd.red_dissonance > 0.5:
            bloom = BloomLevel.UNDERSTAND
            barrett = BarrettDepth.LITERAL
            challenge_amount = 0.15
            depth = 2
        elif zpd.autonomy_readiness > 0.75 and zpd.critical_complexity > 0.65:
            bloom = BloomLevel.CREATE
            barrett = BarrettDepth.EVALUATION
            challenge_amount = 0.55
            depth = 4
        elif zpd.disagreement_readiness > 0.8:
            bloom = BloomLevel.EVALUATE
            barrett = BarrettDepth.EVALUATION
            challenge_amount = 0.45
            depth = 4
        elif zpd.social_constructivism > 0.6:
            bloom = BloomLevel.APPLY
            barrett = BarrettDepth.REORGANIZATION
            challenge_amount = 0.35
            depth = 3
        elif "torrance_creative_thinking" in lenses:
            bloom = BloomLevel.CREATE
            barrett = BarrettDepth.APPRECIATION
            challenge_amount = 0.45
            depth = 4
        else:
            bloom = BloomLevel.ANALYZE
            barrett = BarrettDepth.INFERENTIAL
            challenge_amount = 0.3
            depth = 3

        return ResponseParameters(
            active_office=office, discovery_mode=discovery, epistemic_mode=epistemic,
            constructivist_approach="internal_schema" if zpd.social_constructivism > 0.6 else "social_scaffold",
            thinking_mode="divergent" if zpd.critical_complexity > 0.7 else "convergent",
            dialogue_mode="I-Thou" if zpd.ambiguity_tolerance > 0.6 else "I-It",
            active_map=self._select_thinking_map(zpd),
            target_bloom_level=bloom,
            target_barrett_depth=barrett,
            challenge_amount=challenge_amount,
            explanation_depth=depth,
            active_hats=lens_profile["active_hats"],
            primary_hat=lens_profile["primary_hat"],
            counter_hat_now=("de_bono_six_hats" in lenses or "facione_critical_thinking" in lenses),
            double_loop_prompt=(bloom in {BloomLevel.EVALUATE, BloomLevel.CREATE}),
            miscalibration_risk="high" if conditioning_delta < -0.2 or zpd.red_dissonance > 0.5 else "low",
            pedagogical_lenses=lenses,
            habit_target=lens_profile["habit_target"],
            reinforcement_type="negative" if conditioning_delta > 0.2 else ("penalty" if conditioning_delta < -0.2 else None),
            modelled_behavior=lens_profile["modelled_behavior"],
        )

    def _select_thinking_map(self, zpd) -> Optional[ThinkingMap]:
        if zpd.ambiguity_tolerance < 0.4: return ThinkingMap.CIRCLE
        if zpd.black_tolerance > 0.7: return ThinkingMap.DOUBLE_BUBBLE
        if zpd.critical_complexity > 0.7: return ThinkingMap.TREE
        return ThinkingMap.BRIDGE

_zpd_shaper: Optional[ZPDShaper] = None
def get_zpd_shaper() -> ZPDShaper:
    global _zpd_shaper
    if _zpd_shaper is None: _zpd_shaper = ZPDShaper()
    return _zpd_shaper
