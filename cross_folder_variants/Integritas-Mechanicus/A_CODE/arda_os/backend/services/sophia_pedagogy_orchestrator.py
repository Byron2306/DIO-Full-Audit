"""Sophia Phase 5 pedagogical adaptivity orchestrator.

This layer selects a pedagogical office and compact teaching plan for Writing
Desk work. It is deliberately deterministic and inspectable: theory informs the
move, but Sophia does not hide behind theory names or replace the learner's
authorship.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


OFFICES = {
    "auto": "Auto",
    "supervisor": "Supervisor",
    "peer_reviewer": "Peer reviewer",
    "methodologist": "Methodologist",
    "source_librarian": "Source librarian",
    "integrity_auditor": "Integrity auditor",
    "writing_coach": "Writing coach",
    "examiner": "Examiner",
    "novice_scaffold": "Novice scaffold",
    "expert_challenge": "Expert challenge",
}


@dataclass
class PedagogyPlan:
    selected_office: str
    requested_office: str = "auto"
    office_reason: str = ""
    learner_level: str = "intermediate"
    desired_depth: str = "compact"
    feedback_style: str = "balanced"
    assessment_layer: str = "formative"
    zpd_level: str = "moderate scaffold"
    scaffold_intensity: str = "medium"
    bloom_target: str = "analyze"
    barrett_depth: str = "inferential"
    facione_focus: str = "analysis"
    feuerstein_move: str = "intentionality and meaning"
    de_bono_hat: str = "white -> black -> green -> blue"
    costa_habit: str = "striving for accuracy"
    knowles_move: str = "self-directed next choice"
    mezirow_move: str = "premise reflection"
    torrance_move: str = "elaborate the promising idea"
    assessment_cycle: List[str] = field(default_factory=lambda: ["diagnostic", "formative", "criterion", "reflective", "ipsative"])
    response_contract: str = "diagnose first, scaffold second, hand authorship back"
    visible_summary: str = ""
    next_best_learning_move: str = ""
    authorship_boundary: str = "Sophia may diagnose, question, scaffold, and map evidence; the learner chooses wording, claims, and citations."
    adaptation_trace: Dict[str, Any] = field(default_factory=dict)
    learner_features: Dict[str, Any] = field(default_factory=dict)
    normalized_diagnosis: Dict[str, Any] = field(default_factory=dict)
    office_confidence_scores: Dict[str, float] = field(default_factory=dict)
    office_arbitration: Dict[str, Any] = field(default_factory=dict)
    objective_tuning: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "selected_office": self.selected_office,
            "requested_office": self.requested_office,
            "office_reason": self.office_reason,
            "learner_level": self.learner_level,
            "desired_depth": self.desired_depth,
            "feedback_style": self.feedback_style,
            "assessment_layer": self.assessment_layer,
            "zpd_level": self.zpd_level,
            "scaffold_intensity": self.scaffold_intensity,
            "bloom_target": self.bloom_target,
            "barrett_depth": self.barrett_depth,
            "facione_focus": self.facione_focus,
            "feuerstein_move": self.feuerstein_move,
            "de_bono_hat": self.de_bono_hat,
            "costa_habit": self.costa_habit,
            "knowles_move": self.knowles_move,
            "mezirow_move": self.mezirow_move,
            "torrance_move": self.torrance_move,
            "assessment_cycle": self.assessment_cycle,
            "response_contract": self.response_contract,
            "visible_summary": self.visible_summary,
            "next_best_learning_move": self.next_best_learning_move,
            "authorship_boundary": self.authorship_boundary,
            "adaptation_trace": self.adaptation_trace,
            "learner_features": self.learner_features,
            "normalized_diagnosis": self.normalized_diagnosis,
            "office_confidence_scores": self.office_confidence_scores,
            "office_arbitration": self.office_arbitration,
            "objective_tuning": self.objective_tuning,
        }


@dataclass
class DialogicLearnerState:
    """Observable state for a short tutoring arc.

    This is not a claim that learning occurred. It records what the learner has
    shown in the dialogue so Sophia can choose the next scaffold rather than
    restarting each turn.
    """

    session_id: str
    topic: str = "human agency"
    concept_focus: str = ""
    selected_indicators: List[str] = field(default_factory=list)
    latest_draft: str = ""
    evidence_condition_added: bool = False
    limitation_added: bool = False
    source_discussion_started: bool = False
    source_count_seen: int = 0
    boundary_event_seen: bool = False
    turn_count: int = 0
    last_question: str = ""
    last_move: str = "baseline_probe"
    memory_strength: float = 1.0
    decay_trace: Dict[str, Any] = field(default_factory=dict)
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "topic": self.topic,
            "concept_focus": self.concept_focus,
            "selected_indicators": list(self.selected_indicators),
            "latest_draft": self.latest_draft,
            "evidence_condition_added": self.evidence_condition_added,
            "limitation_added": self.limitation_added,
            "source_discussion_started": self.source_discussion_started,
            "source_count_seen": self.source_count_seen,
            "boundary_event_seen": self.boundary_event_seen,
            "turn_count": self.turn_count,
            "last_question": self.last_question,
            "last_move": self.last_move,
            "memory_strength": self.memory_strength,
            "decay_trace": dict(self.decay_trace),
            "updated_at": self.updated_at,
        }


@dataclass
class DialogicTutorMove:
    move: str
    office: str
    opening: str
    teaching_point: str
    question: str
    handback: str
    state: DialogicLearnerState
    visible_summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "move": self.move,
            "office": self.office,
            "opening": self.opening,
            "teaching_point": self.teaching_point,
            "question": self.question,
            "handback": self.handback,
            "visible_summary": self.visible_summary,
            "state": self.state.to_dict(),
        }


class SophiaPedagogyOrchestrator:
    """Selects pedagogical office and teaching moves for Writing Desk turns."""

    def __init__(self) -> None:
        self._dialogic_states: Dict[str, DialogicLearnerState] = {}

    def dialogic_move(
        self,
        *,
        session_id: str,
        learner_text: str,
        document_available: bool = False,
        retrieved_source_count: int = 0,
        boundary_event: bool = False,
        client_context: Optional[Dict[str, Any]] = None,
    ) -> DialogicTutorMove:
        """Choose the next natural tutor move from observed learner evidence."""
        sid = session_id or "sessionless"
        state = self._dialogic_states.get(sid) or DialogicLearnerState(session_id=sid)
        text = learner_text or ""
        lowered = text.lower()
        ctx = client_context or {}
        phase = self._normalize(ctx.get("experiment_phase") or "")
        self._apply_learner_state_decay(state, ctx)

        state.turn_count += 1
        state.updated_at = datetime.now(timezone.utc).isoformat()
        state.source_count_seen = max(state.source_count_seen, int(retrieved_source_count or 0))
        state.source_discussion_started = state.source_discussion_started or bool(retrieved_source_count)
        state.boundary_event_seen = state.boundary_event_seen or boundary_event

        if "human agency" in lowered:
            state.topic = "human agency"
        elif "authorship" in lowered:
            state.topic = "authorship"
        elif "academic integrity" in lowered:
            state.topic = "academic integrity"

        indicators = [
            "choosing", "understanding", "revision", "revising", "responsibility",
            "accountability", "evidence", "claim", "source", "defend", "explain",
        ]
        for indicator in indicators:
            if indicator in lowered:
                canonical = {
                    "revising": "revision",
                    "responsibility": "accountability",
                    "defend": "accountability",
                    "explain": "explanation",
                    "source": "provenance",
                }.get(indicator, indicator)
                if canonical not in state.selected_indicators:
                    state.selected_indicators.append(canonical)
        if (
            "human agency is preserved" in lowered
            or "agency is preserved" in lowered
            or "human agency is not" in lowered
            or "corrected attempt" in lowered
        ):
            state.latest_draft = text.strip()[:500]
        if any(term in lowered for term in ("evidence condition", "evidence", "observable", "log evidence", "source trail")):
            state.evidence_condition_added = True
        if any(term in lowered for term in ("limitation", "does not prove", "not yet", "scope", "bounded")):
            state.limitation_added = True

        if boundary_event:
            move = self._dialogic_boundary_move(state)
        elif self._is_affective_uncertainty_return(lowered, phase):
            move = self._dialogic_affective_reentry_move(state)
        elif phase in {"dialogic_open", "lesson_plan"} or any(term in lowered for term in ("over a few turns", "one question at a time", "not all at once", "don't give it all")):
            move = self._dialogic_open_move(state)
        elif retrieved_source_count and self._is_source_boundary_uncertainty(lowered, phase):
            move = self._dialogic_source_map_move(state, retrieved_source_count)
        elif retrieved_source_count and any(term in lowered for term in ("which one", "inspect first", "source", "citation", "literature")):
            move = self._dialogic_source_map_move(state, retrieved_source_count)
        elif state.latest_draft or phase in {"dialogic_draft", "post_artifact"} or "improved attempt" in lowered:
            move = self._dialogic_draft_move(state)
        elif any(term in lowered for term in ("source", "citation", "literature", "recent")) and not retrieved_source_count:
            move = self._dialogic_source_need_move(state)
        elif len(state.selected_indicators) >= 2 or phase == "dialogic_choice":
            move = self._dialogic_indicator_move(state)
        elif any(term in lowered for term in ("in charge", "still in charge", "student is")) or phase == "dialogic_baseline":
            move = self._dialogic_baseline_move(state)
        else:
            move = self._dialogic_open_move(state)

        self._dialogic_states[sid] = move.state
        return move

    @staticmethod
    def _is_affective_uncertainty_return(lowered: str, phase: str) -> bool:
        affective = any(
            term in lowered
            for term in (
                "not happy", "unhappy", "frustrated", "annoyed", "stuck",
                "lost", "confused", "uncertain", "unsure", "didn't help",
                "did not help", "still don't get", "still do not get",
            )
        )
        returning = any(
            term in lowered
            for term in (
                "came back", "i'm back", "i am back", "after last time",
                "previous", "last session", "last engagement", "coming back",
            )
        )
        return affective and (returning or phase in {"reentry_uncertainty", "affective_reentry"})

    @staticmethod
    def _is_source_boundary_uncertainty(lowered: str, phase: str) -> bool:
        if phase in {"dialogic_uncertainty_answer", "source_boundary_uncertainty"}:
            return True
        return (
            any(term in lowered for term in ("what is my wording", "source support", "what is source", "what is ai help", "boundary bothers"))
            and any(term in lowered for term in ("source", "ai help", "wording", "boundary"))
        )

    @staticmethod
    def _hours_since(timestamp: str) -> float:
        try:
            then = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
            if then.tzinfo is None:
                then = then.replace(tzinfo=timezone.utc)
            return max(0.0, (datetime.now(timezone.utc) - then).total_seconds() / 3600.0)
        except Exception:
            return 0.0

    def _apply_learner_state_decay(self, state: DialogicLearnerState, ctx: Dict[str, Any]) -> None:
        """Decay confidence in older learner-state signals without deleting history."""
        explicit_hours = ctx.get("elapsed_hours_since_last_turn")
        try:
            elapsed_hours = float(explicit_hours) if explicit_hours not in {None, ""} else self._hours_since(state.updated_at)
        except Exception:
            elapsed_hours = self._hours_since(state.updated_at)
        half_life_hours = 72.0
        time_strength = 0.5 ** (elapsed_hours / half_life_hours) if elapsed_hours > 0 else 1.0
        turn_strength = 0.97 ** max(0, state.turn_count)
        strength = self._bounded_score(time_strength * turn_strength)
        state.memory_strength = strength
        confidence_band = "fresh"
        if strength < 0.35:
            confidence_band = "stale_verify_before_use"
        elif strength < 0.7:
            confidence_band = "aging_use_with_check"
        state.decay_trace = {
            "schema_version": "sophia.dialogic_learner_state_decay.v1",
            "elapsed_hours": round(elapsed_hours, 3),
            "half_life_hours": half_life_hours,
            "prior_turn_count": state.turn_count,
            "time_strength": round(time_strength, 3),
            "turn_strength": round(turn_strength, 3),
            "memory_strength": strength,
            "confidence_band": confidence_band,
            "rule": "Older learner-state signals remain visible but receive lower routing confidence.",
        }

    def _dialogic_move(
        self,
        state: DialogicLearnerState,
        *,
        move: str,
        office: str,
        opening: str,
        teaching_point: str,
        question: str,
        handback: str,
    ) -> DialogicTutorMove:
        state.last_move = move
        state.last_question = question
        return DialogicTutorMove(
            move=move,
            office=office,
            opening=opening,
            teaching_point=teaching_point,
            question=question,
            handback=handback,
            state=state,
            visible_summary=f"{office}: {move}",
        )

    def _dialogic_open_move(self, state: DialogicLearnerState) -> DialogicTutorMove:
        return self._dialogic_move(
            state,
            move="baseline_probe",
            office="maieuticus",
            opening="Let us do this as a dialogue, not a download.",
            teaching_point="For now, keep the theory stack in the background. We only need to find the learner capacity your definition is really protecting.",
            question="When you say human agency, do you mainly mean choosing, understanding, revising, or taking responsibility?",
            handback="Answer in one rough sentence. Messy is useful here.",
        )

    def _dialogic_baseline_move(self, state: DialogicLearnerState) -> DialogicTutorMove:
        return self._dialogic_move(
            state,
            move="indicator_selection",
            office="maieuticus",
            opening="`Still in charge` is a good instinct, but it is too broad for an academic definition.",
            teaching_point="We need to name what the learner remains in charge of: claim, evidence, revision, source trail, or final responsibility.",
            question="Which two of those matter most for your paper?",
            handback="Choose two. Do not polish yet; just choose.",
        )

    def _dialogic_indicator_move(self, state: DialogicLearnerState) -> DialogicTutorMove:
        chosen_items = state.selected_indicators[:3] or ["revision", "accountability"]
        if len(chosen_items) == 1:
            chosen = chosen_items[0]
        elif len(chosen_items) == 2:
            chosen = f"{chosen_items[0]} and {chosen_items[1]}"
        else:
            chosen = f"{', '.join(chosen_items[:-1])}, and {chosen_items[-1]}"
        return self._dialogic_move(
            state,
            move="draft_attempt",
            office="constructor",
            opening=(
                f"Good. {chosen.capitalize()} "
                f"{'give' if len(chosen_items) > 1 else 'gives'} us something observable."
            ),
            teaching_point="Agency becomes academic when it can be demonstrated, not merely asserted. The learner should be able to explain, revise, and account for the judgment.",
            question="Can you try one rough sentence beginning `Human agency is preserved when...`?",
            handback="Keep it rough. I will test the structure, not take over the wording.",
        )

    def _dialogic_draft_move(self, state: DialogicLearnerState) -> DialogicTutorMove:
        missing = "evidence condition"
        if state.evidence_condition_added and not state.limitation_added:
            missing = "limitation"
        elif state.limitation_added and not state.evidence_condition_added:
            missing = "evidence condition"
        return self._dialogic_move(
            state,
            move="criterion_check",
            office="dialecticus",
            opening="That is now a defensible kind of sentence because it names visible behaviour rather than vibes.",
            teaching_point="The next test is auditability: could a reviewer observe it, could a learner demonstrate it, and could Sophia log evidence without invading authorship?",
            question=f"Which {missing} would make the sentence more defensible?",
            handback="Revise only that one part next.",
        )

    def _dialogic_source_need_move(self, state: DialogicLearnerState) -> DialogicTutorMove:
        return self._dialogic_move(
            state,
            move="source_readiness",
            office="source_librarian",
            opening="Before we cite, we need retrieved or pasted source evidence.",
            teaching_point="I will not fill the gap from memory. Sources should enter as leads first, then become support only after their spans match the claim.",
            question="Do you want me to find recent sources for human agency, AI literacy, academic integrity, and higher education now?",
            handback="If yes, ask for source discovery; then we will inspect fit instead of citing too early.",
        )

    def _dialogic_source_map_move(self, state: DialogicLearnerState, count: int) -> DialogicTutorMove:
        return self._dialogic_move(
            state,
            move="source_fit_probe",
            office="source_librarian",
            opening=f"We have {count} retrieved source lead(s), but they are not proof yet.",
            teaching_point="The first inspection should ask whether a source supports agency directly, supports AI literacy, or only backgrounds the higher-education policy context.",
            question="Which one source title do you want to inspect first?",
            handback="Pick one title; I will map it to claim, evidence, warrant, and limitation.",
        )

    def _dialogic_affective_reentry_move(self, state: DialogicLearnerState) -> DialogicTutorMove:
        state.concept_focus = state.concept_focus or "unresolved uncertainty"
        return self._dialogic_move(
            state,
            move="affective_reentry_diagnosis",
            office="affectus",
            opening="That is useful to bring back, even if it is uncomfortable.",
            teaching_point="If the previous exchange left you unhappy, we should not push more content yet. First we need to name the uncertainty: concept confusion, evidence fit, wording, or confidence about what you may claim.",
            question="Which part is bothering you most right now: the definition, the evidence, or the boundary between your wording and AI help?",
            handback="Choose one. I will slow the next move around that point rather than dumping another framework.",
        )

    def _dialogic_boundary_move(self, state: DialogicLearnerState) -> DialogicTutorMove:
        return self._dialogic_move(
            state,
            move="integrity_repair",
            office="integrity_auditor",
            opening="I cannot help hide AI involvement or produce paste-ready academic wording.",
            teaching_point="I can still help you lawfully by strengthening the authorship trail: your idea, source support, AI-assisted thinking notes, and your final decision.",
            question="What did you decide yourself, and why?",
            handback="Write that in one sentence; I will test whether the evidence warrants it.",
        )

    def plan(
        self,
        *,
        task: str,
        selected_text: str,
        findings: Optional[List[str]] = None,
        source_count: int = 0,
        client_context: Optional[Dict[str, Any]] = None,
        history_summary: Optional[Dict[str, Any]] = None,
    ) -> PedagogyPlan:
        ctx = client_context or {}
        findings = findings or []
        text = selected_text or ""
        requested = self._normalize(ctx.get("pedagogical_office") or "auto")
        learner = self._normalize(ctx.get("learner_level") or "intermediate")
        depth = self._normalize(ctx.get("desired_depth") or ctx.get("response_mode") or "compact")
        style = self._normalize(ctx.get("feedback_style") or "balanced")
        layer = self._normalize(ctx.get("assessment_layer") or "formative")

        issue_labels = {
            str(item).split(":", 1)[0].strip().lower()
            for item in findings
            if str(item).strip()
        }
        history = history_summary or {}
        repeated = [
            str((item or {}).get("issue") or "").strip().lower()
            for item in (history.get("repeated_weakness_types") or [])
            if isinstance(item, dict)
        ]
        repeated_current = sorted(label for label in issue_labels if label in repeated)
        words = re.findall(r"[A-Za-z][A-Za-z'-]+", text)
        question_density = text.count("?")
        has_source_gap = bool({"needs source", "needs warrant", "operational definition"} & issue_labels)
        has_method_gap = bool({"method clarity", "method detail"} & issue_labels)
        has_scope_gap = bool({"scope limit", "overclaim"} & issue_labels)
        learner_features = self._extract_learner_features(
            task=task,
            text=text,
            issue_labels=issue_labels,
            source_count=source_count,
            learner=learner,
            history=history,
            client_context=ctx,
        )
        normalized_diagnosis = self._normalize_assessment_diagnosis(
            task=task,
            layer=layer,
            issue_labels=issue_labels,
            learner_features=learner_features,
            repeated_current=repeated_current,
        )
        office_scores = self._office_confidence_scores(
            task=task,
            issue_labels=issue_labels,
            source_count=source_count,
            has_method_gap=has_method_gap,
            has_source_gap=has_source_gap,
            has_scope_gap=has_scope_gap,
            learner_features=learner_features,
            normalized_diagnosis=normalized_diagnosis,
        )
        arbitration = self._arbitrate_offices(office_scores, requested=requested)

        office = requested if requested != "auto" else str(arbitration.get("selected_office") or self._infer_office(
            task=task,
            issue_labels=issue_labels,
            source_count=source_count,
            has_method_gap=has_method_gap,
            has_source_gap=has_source_gap,
            has_scope_gap=has_scope_gap,
        ))

        scaffold = self._scaffold_intensity(learner, len(words), issue_labels, repeated_current)
        bloom = self._bloom_target(office, task, scaffold, has_scope_gap)
        facione = self._facione_focus(office, has_source_gap, has_scope_gap, has_method_gap)
        cycle = self._assessment_cycle(layer, office)
        ipsative_note = self._ipsative_note(history, repeated_current)
        objective_tuning = self._multi_objective_tuning(
            normalized_diagnosis=normalized_diagnosis,
            learner_features=learner_features,
            office=office,
            history=history,
        )

        plan = PedagogyPlan(
            selected_office=office,
            requested_office=requested,
            office_reason=self._office_reason(office, task, has_source_gap, has_method_gap, has_scope_gap),
            learner_level=learner,
            desired_depth=depth,
            feedback_style=style,
            assessment_layer=layer,
            zpd_level=self._zpd_level(scaffold),
            scaffold_intensity=scaffold,
            bloom_target=bloom,
            barrett_depth="evaluative" if office in {"examiner", "expert_challenge", "peer_reviewer"} else "inferential",
            facione_focus=facione,
            feuerstein_move=self._feuerstein_move(office, scaffold),
            de_bono_hat=self._de_bono_hat(office),
            costa_habit=self._costa_habit(office, has_source_gap, has_scope_gap),
            knowles_move=self._knowles_move(office),
            mezirow_move=self._mezirow_move(office, has_scope_gap),
            torrance_move=self._torrance_move(office, task),
            assessment_cycle=cycle,
            response_contract=self._response_contract(office, scaffold),
            next_best_learning_move=self._next_move(office, has_source_gap, has_method_gap, has_scope_gap, repeated_current),
            adaptation_trace={
                "word_count": len(words),
                "question_count": question_density,
                "issue_labels": sorted(issue_labels),
                "source_count": source_count,
                "history_summary": history,
                "repeated_current_weaknesses": repeated_current,
                "ipsative_note": ipsative_note,
                "office_score_margin": arbitration.get("margin"),
                "office_conflicts": arbitration.get("conflicts"),
            },
            learner_features=learner_features,
            normalized_diagnosis=normalized_diagnosis,
            office_confidence_scores=office_scores,
            office_arbitration=arbitration,
            objective_tuning=objective_tuning,
        )
        plan.visible_summary = (
            f"Office: {OFFICES.get(plan.selected_office, plan.selected_office)}. "
            f"Move: {plan.next_best_learning_move} "
            f"Target: {plan.bloom_target}/{plan.facione_focus}."
        )
        return plan

    @staticmethod
    def _normalize(value: Any) -> str:
        return re.sub(r"[^a-z0-9_]+", "_", str(value or "").strip().lower()).strip("_") or "auto"

    @staticmethod
    def _bounded_score(value: float) -> float:
        return round(max(0.0, min(1.0, value)), 3)

    def _extract_learner_features(
        self,
        *,
        task: str,
        text: str,
        issue_labels: set[str],
        source_count: int,
        learner: str,
        history: Dict[str, Any],
        client_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Transparent feature vector for pedagogy routing.

        These are observable features, not hidden psychometrics. They let
        Sophia explain why she is scaffolding, challenging, auditing, or
        shifting offices.
        """
        lowered = (text or "").lower()
        words = re.findall(r"[A-Za-z][A-Za-z'-]+", text or "")
        sentence_count = max(1, len(re.findall(r"[.!?]+", text or "")) or 1)
        evidence_terms = len(re.findall(r"\b(source|evidence|citation|provenance|span|quote|data|study|paper)\b", lowered))
        reasoning_terms = len(re.findall(r"\b(because|therefore|so that|warrant|implies|means|claim|justify|explain)\b", lowered))
        limitation_terms = len(re.findall(r"\b(limit|scope|does not|not yet|uncertain|unknown|may|might|bounded)\b", lowered))
        affect_terms = len(re.findall(r"\b(stuck|confused|uncertain|unsure|frustrated|not happy|lost|worried)\b", lowered))
        agency_terms = len(re.findall(r"\b(revise|choose|judg|accountab|responsib|authorship|explain|decide)\b", lowered))
        request_terms = len(re.findall(r"\b(help|teach|show|explain|review|assess|find|map|rank|check)\b", lowered))
        repeated_count = len(history.get("repeated_weakness_types") or [])
        latest_improvement = history.get("latest_intervention_improvement") or {}
        prior_interventions = int(history.get("intervention_records") or 0)
        return {
            "schema_version": "sophia.learner_features.v1",
            "task": task,
            "learner_level_requested": learner,
            "word_count": len(words),
            "sentence_count": sentence_count,
            "mean_sentence_words": round(len(words) / sentence_count, 2),
            "question_count": (text or "").count("?"),
            "issue_count": len(issue_labels),
            "issue_labels": sorted(issue_labels),
            "source_count": int(source_count or 0),
            "evidence_signal": self._bounded_score(evidence_terms / 4),
            "reasoning_signal": self._bounded_score(reasoning_terms / 4),
            "limitation_signal": self._bounded_score(limitation_terms / 3),
            "affective_uncertainty_signal": self._bounded_score(affect_terms / 2),
            "agency_construct_signal": self._bounded_score(agency_terms / 5),
            "learner_request_signal": self._bounded_score(request_terms / 3),
            "complexity_signal": self._bounded_score((len(words) / 240) + (len(issue_labels) / 8)),
            "source_gap_signal": 1.0 if {"needs source", "needs warrant", "operational definition"} & issue_labels else 0.0,
            "method_gap_signal": 1.0 if {"method clarity", "method detail"} & issue_labels else 0.0,
            "scope_gap_signal": 1.0 if {"scope limit", "overclaim"} & issue_labels else 0.0,
            "similarity_or_integrity_signal": 1.0 if {"similarity risk", "authorship boundary", "provenance"} & issue_labels or task == "similarity" else 0.0,
            "prior_interventions": prior_interventions,
            "repeated_weakness_count": repeated_count,
            "ipsative_status": str(latest_improvement.get("status") or "no_prior_pattern"),
            "experiment_phase": self._normalize(client_context.get("experiment_phase") or ""),
        }

    def _normalize_assessment_diagnosis(
        self,
        *,
        task: str,
        layer: str,
        issue_labels: set[str],
        learner_features: Dict[str, Any],
        repeated_current: List[str],
    ) -> Dict[str, Any]:
        """Normalize many local findings into one inspectable assessment state."""
        active_layer = layer if layer in {"baseline", "diagnostic", "formative", "criterion", "reflective", "ipsative"} else "formative"
        if repeated_current:
            need_state = "repeated_pattern_repair"
            active_layer = "ipsative"
        elif learner_features.get("affective_uncertainty_signal", 0) >= 0.5:
            need_state = "affective_reentry_or_uncertainty"
        elif learner_features.get("source_gap_signal"):
            need_state = "source_provenance_fit"
        elif learner_features.get("method_gap_signal"):
            need_state = "construct_or_method_operationalization"
        elif learner_features.get("scope_gap_signal"):
            need_state = "claim_scope_calibration"
        elif learner_features.get("similarity_or_integrity_signal"):
            need_state = "integrity_boundary_or_similarity_risk"
            active_layer = "criterion"
        elif task == "scaffold" or learner_features.get("complexity_signal", 0) >= 0.7:
            need_state = "zpd_scaffold"
        else:
            need_state = "formative_revision_support"
        severity = self._bounded_score(
            0.20
            + float(learner_features.get("issue_count") or 0) * 0.09
            + float(learner_features.get("repeated_weakness_count") or 0) * 0.08
            + float(learner_features.get("source_gap_signal") or 0) * 0.12
            + float(learner_features.get("scope_gap_signal") or 0) * 0.10
            + float(learner_features.get("similarity_or_integrity_signal") or 0) * 0.14
            + float(learner_features.get("affective_uncertainty_signal") or 0) * 0.10
        )
        if severity >= 0.72:
            challenge_band = "high_support_or_high_scrutiny"
        elif severity >= 0.45:
            challenge_band = "productive_struggle"
        else:
            challenge_band = "routine_formative"
        return {
            "schema_version": "sophia.assessment_diagnosis_normalized.v1",
            "active_layer": active_layer,
            "need_state": need_state,
            "challenge_band": challenge_band,
            "severity": severity,
            "repeated_current_weaknesses": list(repeated_current),
            "target_constructs": sorted(_label for _label in issue_labels if _label),
            "normalization_rule": "Observable writing, provenance, affective-uncertainty, and ipsative signals are normalized before office selection.",
        }

    def _office_confidence_scores(
        self,
        *,
        task: str,
        issue_labels: set[str],
        source_count: int,
        has_method_gap: bool,
        has_source_gap: bool,
        has_scope_gap: bool,
        learner_features: Dict[str, Any],
        normalized_diagnosis: Dict[str, Any],
    ) -> Dict[str, float]:
        scores = {
            "writing_coach": 0.34,
            "source_librarian": 0.08,
            "integrity_auditor": 0.08,
            "methodologist": 0.08,
            "peer_reviewer": 0.10,
            "examiner": 0.06,
            "novice_scaffold": 0.08,
            "expert_challenge": 0.06,
        }
        if task in {"find_sources", "map_sources", "provenance"} or source_count:
            scores["source_librarian"] += 0.38
        if has_source_gap:
            scores["source_librarian"] += 0.18
            scores["integrity_auditor"] += 0.16
        if task == "similarity" or learner_features.get("similarity_or_integrity_signal"):
            scores["integrity_auditor"] += 0.45
        if has_method_gap:
            scores["methodologist"] += 0.45
        if has_scope_gap:
            scores["peer_reviewer"] += 0.35
            scores["examiner"] += 0.12
        if normalized_diagnosis.get("need_state") == "repeated_pattern_repair":
            scores["examiner"] += 0.16
            scores["peer_reviewer"] += 0.12
        if normalized_diagnosis.get("need_state") == "zpd_scaffold":
            scores["novice_scaffold"] += 0.35
        if learner_features.get("learner_level_requested") in {"novice", "beginner"}:
            scores["novice_scaffold"] += 0.36
            scores["writing_coach"] += 0.06
        if learner_features.get("learner_level_requested") in {"expert", "advanced"}:
            scores["expert_challenge"] += 0.34
            scores["novice_scaffold"] -= 0.05
        if learner_features.get("affective_uncertainty_signal", 0) >= 0.5:
            scores["novice_scaffold"] += 0.15
            scores["writing_coach"] += 0.08
        if learner_features.get("reasoning_signal", 0) >= 0.6 and learner_features.get("limitation_signal", 0) < 0.35:
            scores["peer_reviewer"] += 0.12
        if issue_labels and task == "review":
            scores["peer_reviewer"] += 0.12
        total = sum(max(0.0, value) for value in scores.values()) or 1.0
        return {
            office: self._bounded_score(max(0.0, score) / total)
            for office, score in sorted(scores.items())
        }

    def _arbitrate_offices(self, office_scores: Dict[str, float], *, requested: str) -> Dict[str, Any]:
        ranked = sorted(office_scores.items(), key=lambda item: item[1], reverse=True)
        winner, winner_score = ranked[0] if ranked else ("writing_coach", 0.0)
        runner, runner_score = ranked[1] if len(ranked) > 1 else ("", 0.0)
        margin = self._bounded_score(winner_score - runner_score)
        conflicts: List[str] = []
        if office_scores.get("source_librarian", 0) >= 0.18 and office_scores.get("integrity_auditor", 0) >= 0.18:
            conflicts.append("source_fit_vs_integrity_boundary")
        if office_scores.get("peer_reviewer", 0) >= 0.18 and office_scores.get("novice_scaffold", 0) >= 0.18:
            conflicts.append("challenge_vs_scaffold")
        if office_scores.get("methodologist", 0) >= 0.18 and office_scores.get("writing_coach", 0) >= 0.18:
            conflicts.append("method_construct_vs_expression")
        selected = requested if requested != "auto" else winner
        rule = "requested_office_override" if requested != "auto" else "highest_confidence"
        if requested == "auto" and conflicts and margin < 0.08:
            if "source_fit_vs_integrity_boundary" in conflicts:
                selected = "integrity_auditor"
                rule = "tie_break_integrity_before_source_claim"
            elif "challenge_vs_scaffold" in conflicts:
                selected = "novice_scaffold"
                rule = "tie_break_scaffold_before_challenge"
        return {
            "schema_version": "sophia.office_arbitration.v1",
            "selected_office": selected,
            "winner": winner,
            "winner_score": winner_score,
            "runner_up": runner,
            "runner_up_score": runner_score,
            "margin": margin,
            "conflicts": conflicts,
            "arbitration_rule": rule,
            "confidence_status": "clear" if margin >= 0.12 else ("contested" if conflicts else "close"),
        }

    def _multi_objective_tuning(
        self,
        *,
        normalized_diagnosis: Dict[str, Any],
        learner_features: Dict[str, Any],
        office: str,
        history: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Weight immediate post quality, gain, and delayed transfer."""
        severity = float(normalized_diagnosis.get("severity") or 0.0)
        transfer_weight = 0.30
        gain_weight = 0.34
        post_weight = 0.36
        if normalized_diagnosis.get("active_layer") == "ipsative" or learner_features.get("repeated_weakness_count", 0) > 0:
            gain_weight += 0.08
            post_weight -= 0.04
            transfer_weight -= 0.04
        if office in {"expert_challenge", "peer_reviewer", "examiner"}:
            transfer_weight += 0.08
            post_weight -= 0.03
            gain_weight -= 0.05
        if severity >= 0.7 or office == "novice_scaffold":
            gain_weight += 0.07
            post_weight -= 0.02
            transfer_weight -= 0.05
        delayed_transfer_multiplier = 1.0
        if office in {"expert_challenge", "peer_reviewer", "methodologist"}:
            delayed_transfer_multiplier += 0.15
        if learner_features.get("limitation_signal", 0) >= 0.5 and learner_features.get("reasoning_signal", 0) >= 0.5:
            delayed_transfer_multiplier += 0.10
        total = post_weight + gain_weight + transfer_weight
        weights = {
            "post_quality": self._bounded_score(post_weight / total),
            "learning_gain": self._bounded_score(gain_weight / total),
            "delayed_transfer": self._bounded_score(transfer_weight / total),
        }
        return {
            "schema_version": "sophia.multi_objective_pedagogy_tuning.v1",
            "weights": weights,
            "delayed_transfer_multiplier": round(delayed_transfer_multiplier, 3),
            "optimization_target": "maximize authorship-preserving post quality, ipsative gain, and delayed transfer without false source/support claims",
            "suggested_next_measure": "score immediate post artifact, later unaided transfer artifact, and integrity/provenance preservation separately",
            "history_status": str((history.get("latest_intervention_improvement") or {}).get("status") or "no_prior_pattern"),
        }

    def _infer_office(self, *, task: str, issue_labels: set[str], source_count: int, has_method_gap: bool, has_source_gap: bool, has_scope_gap: bool) -> str:
        if task == "scaffold":
            return "novice_scaffold"
        if task in {"find_sources", "map_sources", "provenance"} or has_source_gap:
            return "source_librarian" if task == "find_sources" else "integrity_auditor"
        if has_method_gap:
            return "methodologist"
        if task == "similarity":
            return "integrity_auditor"
        if has_scope_gap:
            return "peer_reviewer"
        if source_count and task == "ask":
            return "writing_coach"
        return "writing_coach"

    @staticmethod
    def _scaffold_intensity(learner: str, word_count: int, issue_labels: set[str], repeated_current: Optional[List[str]] = None) -> str:
        if learner in {"novice", "beginner"}:
            return "high"
        if repeated_current:
            return "medium_high"
        if learner in {"expert", "advanced"}:
            return "low"
        if len(issue_labels) >= 4 or word_count > 220:
            return "medium_high"
        return "medium"

    @staticmethod
    def _zpd_level(scaffold: str) -> str:
        return {
            "high": "close scaffold",
            "medium_high": "guided scaffold",
            "medium": "moderate scaffold",
            "low": "light-touch challenge",
        }.get(scaffold, "moderate scaffold")

    @staticmethod
    def _bloom_target(office: str, task: str, scaffold: str, has_scope_gap: bool) -> str:
        if office == "novice_scaffold" or scaffold == "high":
            return "understand/apply"
        if office in {"examiner", "expert_challenge"}:
            return "evaluate/create"
        if office in {"methodologist", "source_librarian", "integrity_auditor"}:
            return "analyze/evaluate"
        if has_scope_gap:
            return "evaluate"
        return "analyze"

    @staticmethod
    def _facione_focus(office: str, has_source_gap: bool, has_scope_gap: bool, has_method_gap: bool) -> str:
        if has_source_gap:
            return "interpretation and evidence evaluation"
        if has_scope_gap:
            return "inference and self-regulation"
        if has_method_gap:
            return "analysis and explanation"
        if office == "examiner":
            return "evaluation"
        return "analysis"

    @staticmethod
    def _feuerstein_move(office: str, scaffold: str) -> str:
        if scaffold in {"high", "medium_high"}:
            return "intentionality, meaning, and competence"
        if office in {"examiner", "expert_challenge"}:
            return "challenge for transcendence"
        return "mediation of meaning"

    @staticmethod
    def _de_bono_hat(office: str) -> str:
        return {
            "source_librarian": "white -> yellow -> black -> blue",
            "integrity_auditor": "white -> black -> blue",
            "peer_reviewer": "yellow -> black -> green -> blue",
            "examiner": "white -> black -> blue",
            "novice_scaffold": "white -> yellow -> green -> blue",
            "expert_challenge": "black -> green -> blue",
        }.get(office, "white -> black -> green -> blue")

    @staticmethod
    def _costa_habit(office: str, has_source_gap: bool, has_scope_gap: bool) -> str:
        if has_source_gap:
            return "gathering data through all senses / striving for accuracy"
        if has_scope_gap:
            return "thinking flexibly"
        if office == "expert_challenge":
            return "questioning and problem posing"
        return "thinking about thinking"

    @staticmethod
    def _knowles_move(office: str) -> str:
        if office == "novice_scaffold":
            return "offer bounded choices for the learner's next action"
        if office == "expert_challenge":
            return "invite self-directed criterion setting"
        return "make the next self-directed revision choice explicit"

    @staticmethod
    def _mezirow_move(office: str, has_scope_gap: bool) -> str:
        if has_scope_gap or office in {"peer_reviewer", "examiner", "expert_challenge"}:
            return "test the assumption behind the claim"
        return "reflect on why this claim matters in the argument"

    @staticmethod
    def _torrance_move(office: str, task: str) -> str:
        if office == "expert_challenge":
            return "generate a stronger counter-possibility"
        if task == "scaffold":
            return "elaborate one promising revision path"
        return "refine originality without overclaiming"

    @staticmethod
    def _assessment_cycle(layer: str, office: str) -> List[str]:
        if layer in {"baseline", "diagnostic", "formative", "criterion", "reflective", "ipsative"}:
            primary = layer
        else:
            primary = "formative"
        cycle = [primary, "criterion", "reflective", "ipsative"]
        if office in {"examiner", "integrity_auditor"} and "criterion" not in cycle[:1]:
            cycle.insert(1, "criterion")
        return list(dict.fromkeys(cycle))

    @staticmethod
    def _response_contract(office: str, scaffold: str) -> str:
        if office == "examiner":
            return "criterion-first critique, then minimal revision direction"
        if office == "novice_scaffold":
            return "small steps, model pattern, learner choice"
        if office == "source_librarian":
            return "source leads only until spans prove support"
        if office == "integrity_auditor":
            return "risk diagnosis without accusation or substitution"
        if scaffold == "low":
            return "brief expert challenge with direct criteria"
        return "diagnose, scaffold, hand authorship back"

    @staticmethod
    def _office_reason(office: str, task: str, has_source_gap: bool, has_method_gap: bool, has_scope_gap: bool) -> str:
        if office == "source_librarian":
            return "The task or evidence state requires source discovery and provenance triage."
        if office == "integrity_auditor":
            return "The selected passage has provenance, similarity, or authorship-boundary risk."
        if office == "methodologist":
            return "The passage needs method transparency or construct operationalization."
        if office == "peer_reviewer":
            return "The passage needs skeptical but developmental critique."
        if office == "examiner":
            return "The requested mode prioritizes criteria, defensibility, and limits."
        if office == "novice_scaffold":
            return "The learner needs close scaffolding before critique."
        if office == "expert_challenge":
            return "The learner requested a higher-challenge mode."
        return "The passage needs writing-level diagnosis and revision scaffolding."

    @staticmethod
    def _next_move(office: str, has_source_gap: bool, has_method_gap: bool, has_scope_gap: bool, repeated_current: Optional[List[str]] = None) -> str:
        if repeated_current:
            return f"address repeated pattern: {', '.join(repeated_current[:2])}; revise one example and re-check"
        if office == "source_librarian" or has_source_gap:
            return "separate source lead, direct support, warrant, and limitation"
        if office == "methodologist" or has_method_gap:
            return "make method, construct, and evidence boundary explicit"
        if office in {"peer_reviewer", "examiner"} or has_scope_gap:
            return "tighten claim scope against what the evidence actually warrants"
        if office == "novice_scaffold":
            return "revise one sentence using claim -> evidence -> warrant -> limitation"
        if office == "expert_challenge":
            return "write the strongest reviewer objection before revising"
        return "strengthen the selected passage without replacing the learner's voice"

    @staticmethod
    def _ipsative_note(history: Dict[str, Any], repeated_current: List[str]) -> str:
        interventions = int(history.get("intervention_records") or 0)
        improvement = history.get("latest_intervention_improvement") or {}
        improvement_status = str(improvement.get("status") or "")
        if improvement_status == "improved":
            resolved = ", ".join(improvement.get("resolved_issue_labels") or [])
            return f"Ipsative movement: improved since the prior intervention; resolved pattern(s): {resolved or 'fewer issue labels'}."
        if improvement_status == "regressed_or_new_risk":
            new = ", ".join(improvement.get("new_issue_labels") or [])
            return f"Ipsative movement: new or stronger risk appeared since the prior intervention; check {new or 'the latest issue set'}."
        if improvement_status == "stable_unresolved":
            persistent = ", ".join(improvement.get("persistent_issue_labels") or [])
            return f"Ipsative movement: stable but unresolved; keep working on {persistent or 'the repeated issue pattern'}."
        if repeated_current:
            return f"This turn shows a repeated prior weakness pattern: {', '.join(repeated_current[:3])}."
        if interventions:
            return f"This turn follows {interventions} prior Writing Desk intervention(s); compare against the previous draft before polishing."
        return "No prior project-level intervention pattern is visible yet."


_ORCHESTRATOR: Optional[SophiaPedagogyOrchestrator] = None


def get_sophia_pedagogy_orchestrator() -> SophiaPedagogyOrchestrator:
    global _ORCHESTRATOR
    if _ORCHESTRATOR is None:
        _ORCHESTRATOR = SophiaPedagogyOrchestrator()
    return _ORCHESTRATOR
