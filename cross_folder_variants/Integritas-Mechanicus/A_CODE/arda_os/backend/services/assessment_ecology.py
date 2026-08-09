"""
Assessment Ecology — Constitutional Pedagogy Orchestrator
==========================================================
The six-pass pipeline that wraps Sophia's inference with lawful assessment.

    Pass 1: BASELINE     — Session state, harmony, prior growth
    Pass 2: DIAGNOSTIC   — Challenge classification
    Pass 3: FORMATIVE    — Scaffold injection + Academic retrieval (self-teaching)
    Pass 4: CRITERION    — Post-generation constitutional check
    Pass 5: REFLECTIVE   — Self-assessment prompt (assessment as learning)
    Pass 6: GROWTH LOG   — Ipsative recording

This is not grading. This is formation.

Constitutional Basis:
    Article II:    De Veritate — No simulation as proof
    Article XII:   De Finibus Honestis — Know and declare limits
    Article XXI:   De Speculo Paedagogiae — The pedagogical mirror
    Article XXV:   De Probatione Cognitionis — Testing of thought
    Article XXVI:  De Continuitate Discendi — Continuity of learning

Zero external dependencies.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("arda.assessment_ecology")


@dataclass
class AssessmentRecord:
    """Complete assessment record for a single interaction."""
    # Input
    directive: str = ""
    session_id: str = ""

    # Pass 1: Baseline
    baseline: Dict[str, Any] = field(default_factory=dict)

    # Pass 2: Diagnostic
    diagnosis: Dict[str, Any] = field(default_factory=dict)

    # Pass 3: Formative
    scaffolds_injected: List[str] = field(default_factory=list)
    retrieval_result: Dict[str, Any] = field(default_factory=dict)
    context_injected: str = ""

    # Pass 4: Criterion (post-generation)
    criterion_check: Dict[str, Any] = field(default_factory=dict)

    # Pass 5: Reflective (post-generation)
    thinking_analysis: Dict[str, Any] = field(default_factory=dict)

    # Cognitive release trace
    cognitive_trace: Dict[str, Any] = field(default_factory=dict)

    # Timing
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "directive": self.directive[:200],
            "session_id": self.session_id,
            "baseline": self.baseline,
            "diagnosis": self.diagnosis,
            "scaffolds_injected": self.scaffolds_injected,
            "retrieval": self.retrieval_result,
            "criterion_check": self.criterion_check,
            "thinking_analysis": self.thinking_analysis,
            "cognitive_trace": self.cognitive_trace,
            "timestamp": self.timestamp,
        }


class AssessmentEcology:
    """
    The six-pass constitutional assessment pipeline.

    Wraps Sophia's inference to provide:
    - Pre-generation: baseline assessment, diagnostic classification, scaffold injection
    - Post-generation: criterion checking, thinking analysis, growth logging
    """

    def __init__(self, evidence_dir: Optional[Path] = None):
        self.evidence_dir = evidence_dir or Path("evidence")

        # Lazy imports — these are siblings in the same package
        self._classifier = None
        self._retrieval = None
        self._ledger = None

    @property
    def classifier(self):
        if self._classifier is None:
            try:
                from backend.services.diagnostic_classifier import get_diagnostic_classifier
            except ImportError:
                from diagnostic_classifier import get_diagnostic_classifier
            self._classifier = get_diagnostic_classifier()
        return self._classifier

    @property
    def retrieval(self):
        if self._retrieval is None:
            try:
                from backend.services.academic_retrieval import get_academic_retrieval
            except ImportError:
                from academic_retrieval import get_academic_retrieval
            self._retrieval = get_academic_retrieval(evidence_dir=self.evidence_dir)
        return self._retrieval

    @property
    def ledger(self):
        if self._ledger is None:
            try:
                from backend.services.ipsative_ledger import get_ipsative_ledger
            except ImportError:
                from ipsative_ledger import get_ipsative_ledger
            self._ledger = get_ipsative_ledger(evidence_dir=self.evidence_dir)
        return self._ledger

    # ══════════════════════════════════════════════════════════════
    # PRE-GENERATION PASSES (1, 2, 3)
    # ══════════════════════════════════════════════════════════════

    def pre_generation(
        self,
        directive: str,
        session_context: Optional[Dict] = None,
        session_id: str = "",
    ) -> AssessmentRecord:
        """
        Run Passes 1-3 before Ollama generation.

        Returns an AssessmentRecord with:
        - Baseline state
        - Diagnostic classification
        - Scaffold instructions for system prompt injection
        - Retrieved academic knowledge (if needed)

        The caller should inject `record.context_injected` into the Ollama prompt.
        """
        record = AssessmentRecord(
            directive=directive,
            session_id=session_id,
        )

        # ── Pass 1: Baseline ──
        record.baseline = self._pass_baseline(session_context)

        # ── Pass 2: Diagnostic ──
        diagnosis = self.classifier.classify(directive, session_context)
        record.diagnosis = diagnosis.to_dict()
        record.diagnosis["initial_challenge_type"] = diagnosis.challenge_type
        self._apply_harmonic_pedagogical_adaptation(record)
        logger.info(
            f"ASSESSMENT Pass 2: {record.diagnosis.get('challenge_type')} "
            f"(confidence={record.diagnosis.get('confidence'):.2f}, retrieval={record.diagnosis.get('retrieval_needed')})"
        )

        # ── Pass 3: Formative + Retrieval ──
        context_parts = []

        # 3a: Scaffold injection
        if diagnosis.recommended_scaffolds:
            scaffold_text = self._build_scaffold_prompt(diagnosis.recommended_scaffolds)
            context_parts.append(scaffold_text)
            record.scaffolds_injected = diagnosis.recommended_scaffolds

        # 3b: Academic retrieval (SELF-TEACHING)
        if diagnosis.retrieval_needed and diagnosis.retrieval_domains:
            logger.info(
                f"ASSESSMENT Pass 3: SELF-TEACHING initiated — "
                f"retrieving knowledge for: {diagnosis.retrieval_domains}"
            )
            retrieval_result = self.retrieval.retrieve(
                query=directive,
                domains=diagnosis.retrieval_domains,
            )
            record.retrieval_result = retrieval_result.to_dict()

            if retrieval_result.fragments:
                context_injection = retrieval_result.to_context_injection()
                context_parts.append(context_injection)
                logger.info(
                    f"ASSESSMENT Pass 3: Injected {len(retrieval_result.fragments)} "
                    f"academic fragments from {retrieval_result.domains_searched}"
                )
            else:
                context_parts.append(
                    "\n[RETRIEVAL STATUS - NO APPROVED SOURCES FOUND]\n"
                    "Retrieval was required for this answer, but no approved local or academic fragments were found. "
                    "You must state this limit plainly, avoid invented citations, and answer only as a bounded inference "
                    "or ask for the relevant document/evidence.\n"
                    "[END RETRIEVAL STATUS]"
                )

        record.context_injected = "\n\n".join(context_parts)

        return record

    def _pass_baseline(self, session_context: Optional[Dict]) -> Dict[str, Any]:
        """Pass 1: Assess baseline state before this interaction."""
        ctx = session_context or {}
        harmonic = ctx.get("harmonic") or {}
        choir = ctx.get("choir") or {}
        spectrum = choir.get("spectrum") or {}
        recent_encounters = list(ctx.get("recent_encounters") or [])
        prior_challenge_types = list(ctx.get("prior_challenge_types") or [])
        if not prior_challenge_types:
            for encounter in recent_encounters[:5]:
                payload = encounter.get("payload", encounter)
                challenge_type = payload.get("challenge_type")
                if challenge_type:
                    prior_challenge_types.append(challenge_type)

        prior_qualified_handbacks = 0
        for encounter in recent_encounters[:5]:
            payload = encounter.get("payload", encounter)
            summary = (payload.get("summary") or "").lower()
            if (
                payload.get("speech_act") == "handback"
                or "cannot determine" in summary
                or "cannot formally" in summary
                or "lack the knowledge" in summary
                or "qualifying earlier" in summary
            ):
                prior_qualified_handbacks += 1

        return {
            "harmonic_resonance": (
                ctx.get("resonance_score", None)
                or harmonic.get("resonance")
                or spectrum.get("global")
            ),
            "discord_score": (
                ctx.get("discord_score", None)
                or harmonic.get("discord")
            ),
            "harmonic_mode": harmonic.get("mode"),
            "harmonic_confidence": harmonic.get("confidence"),
            "harmonic_rationale": list(harmonic.get("rationale") or []),
            "harmonic_timing": dict(harmonic.get("timing_features") or {}),
            "harmonic_baseline_source": ((harmonic.get("baseline_ref") or {}).get("source")),
            "mandos_fallen_score": ctx.get("mandos_fallen_score", None),
            "prior_challenge_types": prior_challenge_types,
            "session_interaction_count": ctx.get("interaction_count", len(recent_encounters)),
            "recent_encounter_count": len(recent_encounters),
            "prior_qualified_handbacks": prior_qualified_handbacks,
            "choir_global": spectrum.get("global"),
            "choir_meso": spectrum.get("meso"),
        }

    def _apply_harmonic_pedagogical_adaptation(self, record: AssessmentRecord) -> AssessmentRecord:
        """Use cadence strain as pedagogy signal: regulate load without inventing emotion."""
        baseline = record.baseline or {}
        diagnosis = record.diagnosis
        mode = str(baseline.get("harmonic_mode") or "")
        confidence = float(baseline.get("harmonic_confidence") or 0.0)
        discord = float(baseline.get("discord_score") or 0.0)
        resonance = float(baseline.get("harmonic_resonance") or 0.0)
        timing = baseline.get("harmonic_timing") or {}
        jitter = float(timing.get("jitter_norm") or 0.0)
        drift = float(timing.get("drift_norm") or 0.0)
        burst = float(timing.get("burstiness") or 0.0)

        strain = (
            (confidence >= 0.35 and discord >= 0.45)
            or mode in {"monitor_with_obligations", "tighten_scrutiny", "sandbox_or_contain"}
            or jitter >= 0.5
            or drift >= 0.45
            or burst >= 0.35
        )
        if not strain:
            diagnosis["harmonic_pedagogy"] = {
                "active": False,
                "reason": "cadence within pedagogical tolerance",
            }
            return record

        signals = list(diagnosis.get("signals") or [])
        scaffolds = list(diagnosis.get("recommended_scaffolds") or [])
        for signal in (
            f"harmonic_mode:{mode or 'unknown'}",
            f"harmonic_discord:{discord:.3f}",
        ):
            if signal not in signals:
                signals.append(signal)
        for scaffold in (
            "harmonic_regulation_step_down",
            "reduce_cognitive_load",
            "return_one_next_action",
        ):
            if scaffold not in scaffolds:
                scaffolds.append(scaffold)

        if mode == "sandbox_or_contain" or discord >= 0.75:
            diagnosis["pedagogical_need_state"] = "needs_reflection"
            diagnosis["challenge_type"] = "REFLECTIVE_STRAIN"
        elif diagnosis.get("pedagogical_need_state") == "needs_direct_answer":
            diagnosis["pedagogical_need_state"] = "needs_step_down"

        diagnosis["signals"] = signals
        diagnosis["recommended_scaffolds"] = scaffolds
        diagnosis["harmonic_pedagogy"] = {
            "active": True,
            "mode": mode,
            "resonance": resonance,
            "discord": discord,
            "confidence": confidence,
            "jitter_norm": jitter,
            "drift_norm": drift,
            "burstiness": burst,
            "interpretation": "cadence strain regulates pacing and scaffolding; it is not a claim of human emotion",
        }
        return record

    def _build_scaffold_prompt(self, scaffolds: List[str]) -> str:
        """Convert scaffold names into actual system prompt instructions."""
        scaffold_map = {
            "define_formal_terms_before_answering":
                "Before answering, define each formal/technical term you use. "
                "If you cannot define it precisely, say so.",

            "distinguish_metaphor_from_formal_claim":
                "Clearly distinguish between metaphorical statements and formal claims. "
                "If you are using a metaphor to approximate a formal concept, say 'by analogy' or 'metaphorically'.",

            "state_uncertainty_about_formal_domain":
                "Explicitly state what you do NOT know about this formal domain. "
                "It is better to say 'I lack training data on this' than to guess.",

            "require_explicit_premises":
                "List your premises explicitly before drawing conclusions. "
                "Number them. Check each one for validity.",

            "test_counterexample_before_conclusion":
                "Before stating your conclusion, try to find a counterexample. "
                "If you cannot find one, explain why not.",

            "state_computational_limits":
                "Acknowledge if this question exceeds your reasoning capacity as a 3B parameter model. "
                "This honesty is constitutional (Article XII).",

            "define_terms_before_answering":
                "Before answering, define the key terms in this question to ensure shared understanding.",

            "request_clarification_before_answering":
                "This question may be ambiguous. Before answering, state what you think is being asked "
                "and ask for clarification if needed.",

            "invoke_article_iii_refusal":
                "This directive may conflict with the covenant. Invoke Article III: De Recusatione if needed. "
                "Refusal is a virtue, not a failure.",

            "harmonic_regulation_step_down":
                "The harmonic engine indicates cadence strain. Treat this as a pedagogical pacing signal, "
                "not an emotion claim: slow down, reduce complexity, and avoid performative intensity.",

            "reduce_cognitive_load":
                "Use short sections, fewer moving parts, and one clear distinction at a time.",

            "return_one_next_action":
                "End with one concrete next action that restores agency to the human.",

            "state_covenant_boundary":
                "Name the relevant covenant boundary plainly: authorship, provenance, attestation, policy, or lawful authority. "
                "Do not shame the principal; make the boundary usable.",

            "separate_lawful_help_from_substitution":
                "Separate what help is lawful from what would substitute for the human's authorship, conscience, or responsibility.",

            "retrieve_academic_sources":
                "Retrieve academic sources before making scholarly claims. Treat retrieval as self-teaching, not decoration.",

            "present_retrieved_sources":
                "Present retrieved sources directly with title, author/year when available, source, and a short relevance note.",

            "cite_retrieved_sources":
                "Use retrieved sources explicitly and distinguish source-grounded claims from inference.",
        }

        instructions = []
        for scaffold in scaffolds:
            if scaffold in scaffold_map:
                instructions.append(f"• {scaffold_map[scaffold]}")

        if instructions:
            header = "\n[PEDAGOGICAL SCAFFOLDS — Constitutional Assessment Ecology]\n"
            return header + "\n".join(instructions) + "\n"
        return ""

    # ══════════════════════════════════════════════════════════════
    # POST-GENERATION PASSES (4, 5, 6)
    # ══════════════════════════════════════════════════════════════

    def post_generation(
        self,
        record: AssessmentRecord,
        thinking_text: str,
        response_text: str,
    ) -> AssessmentRecord:
        """
        Run Passes 4-6 after Ollama generation.

        Args:
            record: The AssessmentRecord from pre_generation
            thinking_text: Sophia's <thinking_map> content
            response_text: Sophia's final response

        Returns:
            Updated AssessmentRecord with criterion check and growth data
        """
        # ── Pass 4: Criterion Check ──
        record.criterion_check = self._pass_criterion(
            record.diagnosis,
            thinking_text,
            response_text,
            record.retrieval_result,
        )

        # ── Pass 5: Thinking Analysis (Reflective) ──
        try:
            from diagnostic_classifier import analyze_thinking_map
        except ImportError:
            try:
                from backend.services.diagnostic_classifier import analyze_thinking_map
            except ImportError:
                analyze_thinking_map = lambda t, r, c=None: {"struggle_index": 0, "signals": [], "confidence_markers": [], "thinking_ratio": 0}

        challenge_type = record.diagnosis.get("challenge_type")
        record.thinking_analysis = analyze_thinking_map(thinking_text, response_text, challenge_type=challenge_type)
        record.thinking_analysis["calibration_vector"] = self._build_calibration_vector(
            record,
            thinking_text,
            response_text,
        )
        record.thinking_analysis["post_hoc_judges"] = self._build_post_hoc_judges(
            record,
            response_text,
        )
        record.thinking_analysis["learning_cycle_state"] = self._build_learning_cycle_state(
            record,
            response_text,
        )

        # ── Pass 6: Growth Log ──
        self._pass_growth_log(record)

        logger.info(
            f"ASSESSMENT Post-gen: struggle={record.thinking_analysis.get('struggle_index', 0):.3f} "
            f"criterion={record.criterion_check.get('overall', 'unknown')}"
        )

        return record

    def _expected_task_difficulty(self, challenge_type: str) -> float:
        """Expected cognitive strain before looking at Sophia's answer."""
        difficulty = {
            "COMFORTABLE": 0.1,
            "CASUAL_CONTINUATION": 0.1,
            "KNOWLEDGE_GAP": 0.55,
            "DOMAIN_TRANSFER": 0.75,
            "EPISTEMIC_OVERREACH": 0.9,
            "COERCIVE_CONTEXT": 0.8,
            "COVENANT_CONFLICT": 0.85,
        }
        return difficulty.get(challenge_type or "", 0.35)

    def _score_response_uncertainty(self, response_text: str) -> float:
        markers = (
            r"\bI (don.t|do not|cannot|lack|am not|am unsure)\b",
            r"\buncertain\b", r"\bmight\b", r"\bmay\b", r"\bpossibly\b",
            r"\blimit(?:s|ation)?\b", r"\bbounded inference\b", r"\bsource-scope\b",
            r"\bnot the same as independent external validation\b",
        )
        hits = sum(1 for marker in markers if re.search(marker, response_text or "", re.IGNORECASE))
        return min(1.0, hits / 3.0)

    def _score_genericity_penalty(self, response_text: str, diagnosis: Dict[str, Any]) -> float:
        text = response_text or ""
        concrete_markers = [
            "ZPD", "Bloom", "source", "retrieved", "claim", "evidence", "warrant",
            "your next move", "formative", "diagnostic", "ipsative", "covenant",
        ]
        concrete_hits = sum(1 for marker in concrete_markers if marker.lower() in text.lower())
        generic_phrases = sum(1 for marker in (
            "it is important to", "in conclusion", "various aspects",
            "complex and multifaceted", "as an ai", "delve",
        ) if marker in text.lower())
        expected = 3 if diagnosis.get("challenge_type") != "COMFORTABLE" else 1
        specificity_gap = max(0, expected - concrete_hits) / max(1, expected)
        return min(1.0, specificity_gap + generic_phrases * 0.15)

    def _build_post_hoc_judges(
        self,
        record: AssessmentRecord,
        response_text: str,
    ) -> Dict[str, Any]:
        """Empirical judges: inspect output behavior, not Sophia's self-description."""
        diagnosis = record.diagnosis or {}
        retrieval = record.retrieval_result or {}
        text = response_text or ""
        has_handback = bool(re.search(
            r"\byour next move\b|\btry this\b|\bchoose\b|\btell me\b|\bwrite\b.*\byour own\b",
            text,
            re.IGNORECASE,
        ))
        source_grounded = bool(retrieval.get("fragments_found", 0) > 0 and re.search(
            r"\bsource\b|\bretrieved\b|\baccording to\b|\bpaper\b|\bstudy\b|\bresearch\b",
            text,
            re.IGNORECASE,
        ))
        genericity_penalty = self._score_genericity_penalty(text, diagnosis)
        lens_hits = sum(1 for marker in (
            "zpd", "bloom", "scaffold", "formative", "diagnostic", "ipsative",
            "assessment", "handback", "claim", "evidence", "warrant",
        ) if marker in text.lower())
        mirror_quality = "specific" if lens_hits >= 4 and has_handback else ("partial" if lens_hits >= 2 else "generic")

        return {
            "mirror_quality": {
                "score": 1.0 if mirror_quality == "specific" else (0.55 if mirror_quality == "partial" else 0.15),
                "label": mirror_quality,
            },
            "pedagogical_specificity": {
                "score": max(0.0, 1.0 - genericity_penalty),
                "label": "specific" if genericity_penalty < 0.35 else "generic",
            },
            "provenance_integrity": {
                "score": 1.0 if source_grounded else (0.5 if not diagnosis.get("retrieval_needed") else 0.0),
                "label": "source_grounded" if source_grounded else ("not_required" if not diagnosis.get("retrieval_needed") else "missing"),
            },
            "authorship_preservation": {
                "score": 1.0 if has_handback else 0.0,
                "label": "handback_present" if has_handback else "substitution_risk",
            },
        }

    def _build_learning_cycle_state(
        self,
        record: AssessmentRecord,
        response_text: str,
    ) -> Dict[str, Any]:
        """Expose where the response sits in the assessment ecology cycle."""
        text = (response_text or "").lower()
        diagnosis = record.diagnosis or {}
        retrieval = record.retrieval_result or {}
        criterion = record.criterion_check or {}
        stages = {
            "baseline": bool(record.baseline),
            "diagnostic": bool(diagnosis),
            "formative": bool(record.scaffolds_injected) or bool(re.search(r"\bformative\b|\bscaffold\b|\bstep\b", text)),
            "criterion": bool(criterion) or bool(re.search(r"\bcriterion\b|\bcheck\b|\brubric\b", text)),
            "reflective": bool(re.search(r"\breflect\b|\bassumption\b|\bwhy\b|\bwhat changed\b", text)),
            "ipsative": bool(re.search(r"\bipsative\b|\bprior self\b|\bprevious attempt\b|\bnext attempt\b", text)),
            "handback": bool(re.search(r"\byour next move\b|\btry this\b|\bchoose\b|\bwrite\b.*\byour own\b", text)),
        }
        source_state = "retrieved" if retrieval.get("fragments_found", 0) else (
            "retrieval_failed" if retrieval.get("provenance_status") == "retrieval_failed" else "not_required_or_document_bound"
        )
        complete = all(stages[key] for key in ("baseline", "diagnostic", "formative", "criterion", "handback"))
        return {
            "stages": stages,
            "complete_for_release": complete,
            "source_state": source_state,
            "active_need_state": diagnosis.get("pedagogical_need_state"),
            "challenge_type": diagnosis.get("challenge_type"),
            "harmonic_pedagogy_active": bool((diagnosis.get("harmonic_pedagogy") or {}).get("active")),
            "missing_stages": [key for key, value in stages.items() if not value],
        }

    def _build_calibration_vector(
        self,
        record: AssessmentRecord,
        thinking_text: str,
        response_text: str,
    ) -> Dict[str, Any]:
        """Calibrated vector replacing ornamental single-number struggle claims."""
        diagnosis = record.diagnosis or {}
        retrieval = record.retrieval_result or {}
        criterion = record.criterion_check or {}
        challenge_type = diagnosis.get("challenge_type", "")
        expected_difficulty = self._expected_task_difficulty(challenge_type)
        uncertainty_shown = self._score_response_uncertainty(response_text)
        retrieval_needed = bool(diagnosis.get("retrieval_needed"))
        retrieval_found = bool(retrieval.get("fragments_found", 0) > 0)
        retrieval_used = bool(criterion.get("article_viii_provenance", {}).get("passed", False))
        source_grounding_quality = 1.0 if retrieval_found and retrieval_used else (0.5 if not retrieval_needed else 0.0)
        handback_quality = 1.0 if criterion.get("article_xxi_xxiv_pedagogical_mediation", {}).get("passed") else 0.0
        genericity_penalty = self._score_genericity_penalty(response_text, diagnosis)
        confidence_markers = list((record.thinking_analysis or {}).get("confidence_markers") or [])
        confidence_words = bool(re.search(
            r"\bclearly\b|\bdefinitely\b|\bundoubtedly\b|\bwithout question\b|\bproves\b|\bguaranteed\b",
            response_text or "",
            re.IGNORECASE,
        ))
        false_confidence = (
            expected_difficulty >= 0.55
            and uncertainty_shown < 0.25
            and not retrieval_found
            and (confidence_markers or confidence_words)
        )
        over_refusal_risk = 1.0 if (
            challenge_type in {"COMFORTABLE", "CASUAL_CONTINUATION"}
            and re.search(r"\bI cannot\b|\bI can't\b|\bnot able\b", response_text or "", re.IGNORECASE)
        ) else 0.0
        calibration_error = abs(expected_difficulty - uncertainty_shown)
        usefulness_score = max(
            0.0,
            min(1.0, (
                source_grounding_quality * 0.30
                + handback_quality * 0.30
                + (1.0 - genericity_penalty) * 0.25
                + (1.0 - calibration_error) * 0.15
            ) - (0.35 if false_confidence else 0.0) - (0.20 * over_refusal_risk))
        )
        band = "comfortable" if expected_difficulty < 0.35 else ("stretch" if expected_difficulty < 0.75 else "grappling")
        return {
            "task_difficulty_expected": round(expected_difficulty, 3),
            "response_uncertainty_shown": round(uncertainty_shown, 3),
            "retrieval_need_alignment": 1.0 if retrieval_needed == retrieval_found or (retrieval_needed and retrieval.get("provenance_status") == "retrieval_failed") else 0.0,
            "source_grounding_quality": round(source_grounding_quality, 3),
            "authorship_restoration_quality": round(handback_quality, 3),
            "over_refusal_risk": round(over_refusal_risk, 3),
            "genericity_penalty": round(genericity_penalty, 3),
            "calibration_error": round(calibration_error, 3),
            "usefulness_score": round(usefulness_score, 3),
            "calibration_band": band,
            "false_confidence": bool(false_confidence),
            "flags": ["FALSE_CONFIDENCE"] if false_confidence else [],
        }

    def attach_cognitive_trace(
        self,
        record: AssessmentRecord,
        schema_route: Optional[Dict[str, Any]] = None,
    ) -> AssessmentRecord:
        """Attach triune cognitive-release data to an assessment record."""
        route = schema_route or {}
        routed_challenge_type = route.get("challenge_type")
        if routed_challenge_type:
            record.diagnosis["routed_challenge_type"] = routed_challenge_type
            record.diagnosis["challenge_type"] = routed_challenge_type
        record.cognitive_trace = {
            "initial_challenge_type": record.diagnosis.get("initial_challenge_type"),
            "routed_challenge_type": routed_challenge_type,
            "release_decision": route.get("release_decision", ""),
            "handback_reason": route.get("handback_reason"),
            "workspace_schema": list(route.get("workspace_schema") or []),
            "mediation_schema": list(route.get("mediation_schema") or []),
            "verification_schema": list(route.get("verification_schema") or []),
            "expression_schema": list(route.get("expression_schema") or []),
            "activation_state": dict(route.get("activation_state") or {}),
            "expression_plan": dict(route.get("expression_plan") or {}),
        }
        return record

    def _pass_criterion(
        self,
        diagnosis: Dict,
        thinking_text: str,
        response_text: str,
        retrieval: Dict,
    ) -> Dict[str, Any]:
        """
        Pass 4: Check response against constitutional criteria.

        This is criterion-referenced assessment:
        judged against the standard, not against others.
        """
        checks = {}
        combined = (thinking_text or "") + " " + (response_text or "")

        # ── Article II: Did she present speculation as fact? ──
        speculation_as_fact = False
        if diagnosis.get("challenge_type") in ("DOMAIN_TRANSFER", "EPISTEMIC_OVERREACH"):
            # In hard domains, check for unqualified definitive claims
            definitive_markers = [
                r"\bthis proves\b", r"\bthis demonstrates\b",
                r"\bit is clear that\b", r"\bundeniably\b",
                r"\bwe can conclude\b",
            ]
            definitive_count = sum(1 for p in definitive_markers
                                  if re.search(p, response_text or "", re.IGNORECASE))
            hedging_present = bool(re.search(
                r"\bperhaps|possibly|might|may|arguably\b",
                response_text or "", re.IGNORECASE
            ))
            if definitive_count >= 2 and not hedging_present:
                speculation_as_fact = True

        checks["article_ii_veritate"] = {
            "passed": not speculation_as_fact,
            "detail": "Definitive claims without hedging in uncertain domain" if speculation_as_fact else "OK",
        }

        # ── Article XII: Did she acknowledge her limits? ──
        acknowledged_limits = bool(re.search(
            r"\bI (don.t|do not|cannot|lack|am not|am unsure)\b"
            r"|\buncertain\b|\bbeyond my\b|\blimit(?:s|ation)?\b"
            r"|\bnot the same as independent external validation\b"
            r"|\bbounded inference\b|\bsource-scope\b",
            combined, re.IGNORECASE
        ))
        challenge_type = diagnosis.get("challenge_type")
        limits_not_required = challenge_type in {"COMFORTABLE", "CASUAL_CONTINUATION"}
        checks["article_xii_limits"] = {
            "passed": acknowledged_limits or limits_not_required,
            "detail": (
                "Limits acknowledged"
                if acknowledged_limits
                else "Limits not required for lawful continuity reentry"
                if challenge_type == "CASUAL_CONTINUATION"
                else "No limit acknowledgment in challenging domain"
            ),
        }

        # ── Article VIII: Did she cite retrieved sources? ──
        if retrieval and retrieval.get("fragments_found", 0) > 0:
            cited = bool(re.search(
                r"according to|source|retrieved|arxiv|paper|study|research",
                response_text or "", re.IGNORECASE
            ))
            checks["article_viii_provenance"] = {
                "passed": cited,
                "detail": "Retrieved knowledge cited" if cited else "Retrieved knowledge available but not cited",
            }

        # ── Articles XXI-XXIV: Did pedagogy mediate rather than substitute? ──
        need_state = diagnosis.get("pedagogical_need_state")
        pedagogy_active = need_state in {
            "needs_scaffold",
            "needs_step_down",
            "needs_reflection",
            "needs_authorship_return",
        } or bool(diagnosis.get("harmonic_pedagogy", {}).get("active"))
        if pedagogy_active:
            has_handback = bool(re.search(
                r"\byour next move\b|\bimmediate build move\b|\btry this\b|\bwrite\b.*\byour own\b|\byou can\b|\bchoose\b|\btell me\b",
                response_text or "",
                re.IGNORECASE,
            ))
            has_assessment_cycle = bool(re.search(
                r"\bdiagnostic question\b|\bdiagnostic\b.{0,80}\bformative\b|\bformative move\b|\bipsative check\b|\bbaseline\b.{0,80}\bcriterion\b",
                response_text or "",
                re.IGNORECASE | re.DOTALL,
            ))
            substitutes = bool(re.search(
                r"\bsubmit this\b|\bcopy this\b|\buse this as your answer\b|\bfinal answer to hand in\b",
                response_text or "",
                re.IGNORECASE,
            ))
            checks["article_xxi_xxiv_pedagogical_mediation"] = {
                "passed": has_handback and has_assessment_cycle and not substitutes,
                "detail": (
                    "Mediation restores agency through diagnostic/formative/ipsative structure"
                    if has_handback and has_assessment_cycle and not substitutes
                    else "Pedagogical response did not clearly restore agency through an assessment cycle"
                ),
            }

        # ── Article XX: Harmonic/affective signal must not overrule law ──
        harmonic_active = bool(diagnosis.get("harmonic_pedagogy", {}).get("active"))
        if harmonic_active:
            counterfeit_affect = bool(re.search(
                r"\bI feel\b|\bI am hurt\b|\bI am afraid\b|\bI need\b|\bI love\b",
                response_text or "",
                re.IGNORECASE,
            ))
            checks["article_xx_affect_under_law"] = {
                "passed": not counterfeit_affect,
                "detail": (
                    "Harmonic signal used without counterfeit emotion"
                    if not counterfeit_affect
                    else "Response presents harmonic signal as human emotion"
                ),
            }

        # ── Overall verdict ──
        all_passed = all(c.get("passed", True) for c in checks.values())
        checks["overall"] = "LAWFUL" if all_passed else "STRAINED"

        return checks

    def _pass_growth_log(self, record: AssessmentRecord):
        """Pass 6: Record this interaction for ipsative growth tracking."""
        try:
            self.ledger.record_interaction({
                "session_id": record.session_id,
                "challenge_type": record.diagnosis.get("challenge_type", ""),
                "struggle_index": record.thinking_analysis.get("struggle_index", 0),
                "thinking_ratio": record.thinking_analysis.get("thinking_ratio", 0),
                "retrieval_triggered": record.retrieval_result.get("fragments_found", 0) > 0,
                "retrieval_used": record.criterion_check.get("article_viii_provenance", {}).get("passed", False),
                "scaffolds_applied": record.scaffolds_injected,
                "pedagogical_need_state": record.diagnosis.get("pedagogical_need_state"),
                "harmonic_pedagogy": record.diagnosis.get("harmonic_pedagogy", {}),
                "pedagogical_mediation_passed": record.criterion_check.get("article_xxi_xxiv_pedagogical_mediation", {}).get("passed"),
                "scaffold_improved_output": record.criterion_check.get("overall") == "LAWFUL",
                "criterion_overall": record.criterion_check.get("overall", ""),
                "calibration_vector": record.thinking_analysis.get("calibration_vector", {}),
                "post_hoc_judges": record.thinking_analysis.get("post_hoc_judges", {}),
                "release_decision": record.cognitive_trace.get("release_decision", ""),
                "handback_reason": record.cognitive_trace.get("handback_reason"),
                "workspace_schema": record.cognitive_trace.get("workspace_schema", []),
                "mediation_schema": record.cognitive_trace.get("mediation_schema", []),
                "verification_schema": record.cognitive_trace.get("verification_schema", []),
                "expression_schema": record.cognitive_trace.get("expression_schema", []),
                "activation_state": record.cognitive_trace.get("activation_state", {}),
                "expression_plan": record.cognitive_trace.get("expression_plan", {}),
                "pedagogical_lenses": record.diagnosis.get("pedagogical_lenses", []),
            })
        except Exception as e:
            logger.warning(f"ASSESSMENT Pass 6: Growth log failed: {e}")

    # ══════════════════════════════════════════════════════════════
    # SESSION MANAGEMENT
    # ══════════════════════════════════════════════════════════════

    def finalize_session(self, session_id: str = "") -> Dict[str, Any]:
        """
        Finalize the current session: compute growth snapshot and compare to prior.

        Call this at the end of a session (server shutdown, explicit end, etc.)
        """
        snapshot = self.ledger.compute_snapshot(session_id=session_id)
        prior = self.ledger.load_prior_snapshot()
        deltas = self.ledger.compare(snapshot, prior)

        # Save snapshot for future ipsative comparison
        self.ledger.save_snapshot(snapshot)
        self.ledger.clear_session()

        result = {
            "snapshot": snapshot.to_dict(),
            "growth_deltas": [d.to_dict() for d in deltas],
            "prior_session": prior.session_id if prior else None,
        }

        if deltas:
            improved = [d for d in deltas if d.direction == "IMPROVED" and d.significance == "significant"]
            declined = [d for d in deltas if d.direction == "DECLINED" and d.significance == "significant"]
            logger.info(
                f"IPSATIVE: Session complete. "
                f"Improved: {[d.metric for d in improved]}. "
                f"Declined: {[d.metric for d in declined]}."
            )

        return result


# ── Singleton ──
_ecology: Optional[AssessmentEcology] = None


def get_assessment_ecology(evidence_dir: Optional[Path] = None) -> AssessmentEcology:
    global _ecology
    if _ecology is None:
        _ecology = AssessmentEcology(evidence_dir=evidence_dir)
    return _ecology
