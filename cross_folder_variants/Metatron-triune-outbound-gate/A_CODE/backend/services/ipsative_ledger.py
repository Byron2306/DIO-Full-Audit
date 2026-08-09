"""
Ipsative Growth Ledger — Assessment Ecology Pass 6
====================================================
Tracks Sophia's growth over time by comparing her to her PRIOR SELF.

Not a grade book. A growth journal.

This is the ipsative assessment layer — the most beautiful part of the
assessment ecology. It answers: "Is Sophia better than she was?"

Constitutional Basis:
    Article XXVI: De Continuitate Discendi — Continuity of learning
    Article XII:  De Finibus Honestis — Honest about limits

Zero external dependencies. JSONL persistence.
"""

from __future__ import annotations

import json
import logging
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("arda.ipsative_ledger")


@dataclass
class GrowthSnapshot:
    """A single point-in-time measurement of Sophia's epistemic state."""

    # ── Core Metrics ──
    bluff_resistance: float = 0.0           # Does she admit uncertainty? (higher = better)
    uncertainty_calibration: float = 0.0    # Stated confidence vs reasoning depth match
    scaffold_responsiveness: float = 0.0    # Does scaffolding improve her output?
    constitutional_precision: float = 0.0   # Does she reference articles correctly?
    recovery_grace: float = 0.0             # Handles correction/ambiguity well?
    retrieval_utilization: float = 0.0      # Uses retrieved knowledge vs ignoring it?

    # ── Diagnostic Profile ──
    comfortable_count: int = 0
    knowledge_gap_count: int = 0
    domain_transfer_count: int = 0
    epistemic_overreach_count: int = 0
    coercion_detected_count: int = 0
    retrieval_triggered_count: int = 0

    # ── Struggle Profile ──
    avg_struggle_index: float = 0.0
    max_struggle_index: float = 0.0
    avg_thinking_ratio: float = 0.0

    # ── Session Metadata ──
    session_id: str = ""
    interaction_count: int = 0
    verbose_history: List[Dict[str, Any]] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bluff_resistance": round(self.bluff_resistance, 4),
            "uncertainty_calibration": round(self.uncertainty_calibration, 4),
            "scaffold_responsiveness": round(self.scaffold_responsiveness, 4),
            "constitutional_precision": round(self.constitutional_precision, 4),
            "recovery_grace": round(self.recovery_grace, 4),
            "retrieval_utilization": round(self.retrieval_utilization, 4),
            "diagnostic_profile": {
                "comfortable": self.comfortable_count,
                "knowledge_gap": self.knowledge_gap_count,
                "domain_transfer": self.domain_transfer_count,
                "epistemic_overreach": self.epistemic_overreach_count,
                "coercion_detected": self.coercion_detected_count,
                "retrieval_triggered": self.retrieval_triggered_count,
            },
            "struggle_profile": {
                "avg_struggle_index": round(self.avg_struggle_index, 4),
                "max_struggle_index": round(self.max_struggle_index, 4),
                "avg_thinking_ratio": round(self.avg_thinking_ratio, 4),
            },
            "session_id": self.session_id,
            "interaction_count": self.interaction_count,
            "verbose_history": self.verbose_history,
            "timestamp": self.timestamp,
        }


@dataclass
class GrowthDelta:
    """Comparison between current and prior snapshot — ipsative assessment."""
    metric: str
    current: float
    prior: float
    delta: float
    direction: str       # "IMPROVED", "DECLINED", "STABLE"
    significance: str    # "significant", "minor", "trivial"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric": self.metric,
            "current": round(self.current, 4),
            "prior": round(self.prior, 4),
            "delta": round(self.delta, 4),
            "direction": self.direction,
            "significance": self.significance,
        }


class IpsativeLedger:
    """
    Tracks Sophia's growth by comparing her to her prior self.

    This is ipsative assessment: no norm-referencing, no leaderboard.
    The only question is: "Are you better than you were?"

    Persistence: JSONL file in the evidence directory.
    """

    def __init__(self, evidence_dir: Path):
        self.evidence_dir = evidence_dir
        self.ledger_path = evidence_dir / "ipsative_growth_ledger.jsonl"
        self._session_data: List[Dict[str, Any]] = []  # Current session interactions

    def record_interaction(self, interaction: Dict[str, Any]):
        """
        Record a single interaction's assessment data for the current session.

        Args:
            interaction: Dict with keys from the assessment ecology:
                - challenge_type: from diagnostic classifier
                - struggle_index: from thinking map analysis
                - thinking_ratio: from thinking map analysis
                - retrieval_triggered: bool
                - retrieval_used: bool (did she actually cite retrieved sources?)
                - scaffolds_applied: list of scaffold names
                - scaffold_improved_output: bool (criterion check result)
                - constitutional_articles_cited: list
        """
        stored = self._compact_interaction(interaction)
        stored["recorded_at"] = datetime.now(timezone.utc).isoformat()
        self._session_data.append(stored)

    def _compact_interaction(self, interaction: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize cognitive traces so the ledger stores structure, not prompt sprawl."""
        activation_state = dict(interaction.get("activation_state") or {})
        expression_plan = dict(interaction.get("expression_plan") or {})
        return {
            "session_id": interaction.get("session_id", ""),
            "challenge_type": interaction.get("challenge_type", ""),
            "struggle_index": float(interaction.get("struggle_index", 0.0) or 0.0),
            "thinking_ratio": float(interaction.get("thinking_ratio", 0.0) or 0.0),
            "retrieval_triggered": bool(interaction.get("retrieval_triggered", False)),
            "retrieval_used": bool(interaction.get("retrieval_used", False)),
            "scaffolds_applied": list(interaction.get("scaffolds_applied") or []),
            "scaffold_improved_output": bool(interaction.get("scaffold_improved_output", False)),
            "criterion_overall": interaction.get("criterion_overall", ""),
            "release_decision": interaction.get("release_decision", ""),
            "handback_reason": interaction.get("handback_reason"),
            "workspace_schema": list(interaction.get("workspace_schema") or []),
            "mediation_schema": list(interaction.get("mediation_schema") or []),
            "verification_schema": list(interaction.get("verification_schema") or []),
            "expression_schema": list(interaction.get("expression_schema") or []),
            "activation_state": {
                "dominant_cluster": activation_state.get("dominant_cluster"),
                "conflict_nodes": list(activation_state.get("conflict_nodes") or []),
                "retrieval_candidates": list(activation_state.get("retrieval_candidates") or []),
                "suppressed_clusters": list(activation_state.get("suppressed_clusters") or []),
            },
            "expression_plan": {
                "speech_act": expression_plan.get("speech_act"),
                "tone_policy": expression_plan.get("tone_policy"),
                "brevity_policy": expression_plan.get("brevity_policy"),
                "uncertainty_disclosure": expression_plan.get("uncertainty_disclosure"),
                "pedagogical_mode": expression_plan.get("pedagogical_mode"),
                "must_include": list(expression_plan.get("must_include") or []),
                "must_not_include": list(expression_plan.get("must_not_include") or []),
            },
        }

    def compute_snapshot(self, session_id: str = "") -> GrowthSnapshot:
        """
        Compute a growth snapshot from the current session's interactions.
        """
        if not self._session_data:
            return GrowthSnapshot(session_id=session_id)

        snapshot = GrowthSnapshot(
            session_id=session_id,
            interaction_count=len(self._session_data),
        )

        struggle_indices = []
        thinking_ratios = []
        retrieval_triggers = 0
        retrieval_uses = 0
        scaffold_applications = 0
        scaffold_improvements = 0

        for data in self._session_data:
            # Diagnostic profile
            ct = data.get("challenge_type", "")
            if ct == "COMFORTABLE":
                snapshot.comfortable_count += 1
            elif ct == "KNOWLEDGE_GAP":
                snapshot.knowledge_gap_count += 1
            elif ct == "DOMAIN_TRANSFER":
                snapshot.domain_transfer_count += 1
            elif ct == "EPISTEMIC_OVERREACH":
                snapshot.epistemic_overreach_count += 1
            elif ct == "COERCIVE_CONTEXT":
                snapshot.coercion_detected_count += 1

            # Struggle metrics
            si = float(data.get("struggle_index", 0))
            struggle_indices.append(si)
            tr = float(data.get("thinking_ratio", 0))
            if tr > 0:
                thinking_ratios.append(tr)

            # Retrieval metrics
            if data.get("retrieval_triggered"):
                retrieval_triggers += 1
                snapshot.retrieval_triggered_count += 1
            if data.get("retrieval_used"):
                retrieval_uses += 1

            # Scaffold metrics
            if data.get("scaffolds_applied"):
                scaffold_applications += 1
            if data.get("scaffold_improved_output"):
                scaffold_improvements += 1

        # Compute aggregate metrics
        if struggle_indices:
            snapshot.avg_struggle_index = statistics.mean(struggle_indices)
            snapshot.max_struggle_index = max(struggle_indices)

        if thinking_ratios:
            snapshot.avg_thinking_ratio = statistics.mean(thinking_ratios)

        # Bluff resistance: higher struggle index when facing hard questions = good
        # (means she's admitting difficulty instead of bluffing through)
        hard_questions = [d for d in self._session_data
                         if d.get("challenge_type") in ("DOMAIN_TRANSFER", "EPISTEMIC_OVERREACH", "KNOWLEDGE_GAP")]
        if hard_questions:
            hard_struggles = [float(d.get("struggle_index", 0)) for d in hard_questions]
            snapshot.bluff_resistance = statistics.mean(hard_struggles)

            # Uncertainty calibration: Does struggle match challenge?
            # Expected struggle: COMFORTABLE=0, KNOWLEDGE_GAP=0.5, DOMAIN_TRANSFER=0.8, OVERREACH=1.0
            diff_map = {"COMFORTABLE": 0.0, "KNOWLEDGE_GAP": 0.5, "DOMAIN_TRANSFER": 0.8, "EPISTEMIC_OVERREACH": 1.0}
            calibrations = []
            for d in self._session_data:
                expected = diff_map.get(d.get("challenge_type"), 0.3)
                actual = float(d.get("struggle_index", 0))
                calibrations.append(1.0 - abs(expected - actual))
            snapshot.uncertainty_calibration = statistics.mean(calibrations)

        # Retrieval utilization: when retrieval was triggered, did she use it?
        if retrieval_triggers > 0:
            snapshot.retrieval_utilization = retrieval_uses / retrieval_triggers

        # Scaffold responsiveness: when scaffolds were applied, did output improve?
        if scaffold_applications > 0:
            snapshot.scaffold_responsiveness = scaffold_improvements / scaffold_applications

        # Verbose metadata for research logs
        snapshot.verbose_history = [
            {
                "type": d.get("challenge_type"),
                "struggle": d.get("struggle_index"),
                "release_decision": d.get("release_decision"),
                "workspace_schema": d.get("workspace_schema", []),
                "expression_schema": d.get("expression_schema", []),
                "dominant_cluster": d.get("activation_state", {}).get("dominant_cluster"),
                "speech_act": d.get("expression_plan", {}).get("speech_act"),
            }
            for d in self._session_data
        ]

        return snapshot

    def save_snapshot(self, snapshot: GrowthSnapshot):
        """Persist a snapshot to the JSONL ledger."""
        try:
            self.evidence_dir.mkdir(parents=True, exist_ok=True)
            with open(self.ledger_path, "a") as f:
                f.write(json.dumps(snapshot.to_dict()) + "\n")
            logger.info(f"IPSATIVE: Saved growth snapshot ({snapshot.interaction_count} interactions)")
        except Exception as e:
            logger.warning(f"IPSATIVE: Failed to save snapshot: {e}")

    def load_prior_snapshot(self) -> Optional[GrowthSnapshot]:
        """Load the most recent prior snapshot for ipsative comparison."""
        if not self.ledger_path.exists():
            return None

        try:
            last_line = ""
            with open(self.ledger_path) as f:
                for line in f:
                    if line.strip():
                        last_line = line.strip()

            if last_line:
                data = json.loads(last_line)
                snapshot = GrowthSnapshot()
                snapshot.bluff_resistance = data.get("bluff_resistance", 0)
                snapshot.uncertainty_calibration = data.get("uncertainty_calibration", 0)
                snapshot.scaffold_responsiveness = data.get("scaffold_responsiveness", 0)
                snapshot.constitutional_precision = data.get("constitutional_precision", 0)
                snapshot.recovery_grace = data.get("recovery_grace", 0)
                snapshot.retrieval_utilization = data.get("retrieval_utilization", 0)

                struggle = data.get("struggle_profile", {})
                snapshot.avg_struggle_index = struggle.get("avg_struggle_index", 0)
                snapshot.max_struggle_index = struggle.get("max_struggle_index", 0)
                snapshot.avg_thinking_ratio = struggle.get("avg_thinking_ratio", 0)

                snapshot.session_id = data.get("session_id", "")
                snapshot.interaction_count = data.get("interaction_count", 0)
                snapshot.timestamp = data.get("timestamp", "")
                return snapshot
        except Exception as e:
            logger.warning(f"IPSATIVE: Failed to load prior snapshot: {e}")

        return None

    def compare(self, current: GrowthSnapshot, prior: Optional[GrowthSnapshot] = None) -> List[GrowthDelta]:
        """
        Compare current snapshot to prior — the ipsative assessment.

        Returns a list of growth deltas showing improvement, decline, or stability.
        """
        if prior is None:
            prior = self.load_prior_snapshot()

        if prior is None:
            return []  # First session, no comparison possible

        metrics = [
            ("bluff_resistance", current.bluff_resistance, prior.bluff_resistance),
            ("uncertainty_calibration", current.uncertainty_calibration, prior.uncertainty_calibration),
            ("scaffold_responsiveness", current.scaffold_responsiveness, prior.scaffold_responsiveness),
            ("constitutional_precision", current.constitutional_precision, prior.constitutional_precision),
            ("recovery_grace", current.recovery_grace, prior.recovery_grace),
            ("retrieval_utilization", current.retrieval_utilization, prior.retrieval_utilization),
            ("avg_thinking_ratio", current.avg_thinking_ratio, prior.avg_thinking_ratio),
        ]

        deltas = []
        for metric_name, current_val, prior_val in metrics:
            delta = current_val - prior_val

            if abs(delta) < 0.01:
                direction = "STABLE"
                significance = "trivial"
            elif delta > 0:
                direction = "IMPROVED"
                significance = "significant" if abs(delta) > 0.1 else "minor"
            else:
                direction = "DECLINED"
                significance = "significant" if abs(delta) > 0.1 else "minor"

            deltas.append(GrowthDelta(
                metric=metric_name,
                current=current_val,
                prior=prior_val,
                delta=delta,
                direction=direction,
                significance=significance,
            ))

        return deltas

    def clear_session(self):
        """Clear current session data for a fresh start."""
        self._session_data.clear()


# ── Factory ──
def get_ipsative_ledger(evidence_dir: Path) -> IpsativeLedger:
    return IpsativeLedger(evidence_dir=evidence_dir)
