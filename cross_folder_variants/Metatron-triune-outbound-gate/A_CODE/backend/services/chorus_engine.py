from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

try:
    from schemas.polyphonic_models import ChorusSpec, EdgeObservation, ChorusState
except Exception:
    from backend.schemas.polyphonic_models import ChorusSpec, EdgeObservation, ChorusState


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


def _safe_ratio(part: float, whole: float) -> float:
    if whole <= 0:
        return 1.0
    return _clamp(part / whole)


def _model_dump(model: Any) -> Dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()  # type: ignore[no-any-return]
    if hasattr(model, "dict"):
        return model.dict()  # type: ignore[no-any-return]
    if hasattr(model, "__dict__"):
        return dict(model.__dict__)  # type: ignore[no-any-return]
    return dict(model)


class ChorusEngine:
    """
    Phase 4 Chorus / Mesh Entrainment scoring engine.
    Focuses on relational local edge coherence rather than raw timing.
    """

    def __init__(self, db: Any = None):
        self.db = db
        self._specs: Dict[str, ChorusSpec] = {}
        self._bootstrap_specs()

    def set_db(self, db: Any) -> None:
        self.db = db

    def _bootstrap_specs(self) -> None:
        self._specs["agent_command_execution"] = ChorusSpec(
            edge_type="agent_command_execution",
            required_participants=[
                "dispatch",
                "outbound_gate",
                "policy_bind",
                "world_state_bind",
                "governance_authority",
                "executor",
                "audit_closure",
            ],
            optional_participants=["vns_alert", "telemetry_emit", "token_validation_refresh"],
            expected_sequence=[
                "dispatch",
                "world_state_bind",
                "policy_bind",
                "governance_authority",
                "executor_started",
                "executor_completed",
                "audit_closure",
                "edge_settled",
            ],
            timing_tolerances_ms={
                "dispatch->outbound_gate": (0, 2000),
                "governance_authority->executor_started": (0, 4000),
                "executor_started->executor_completed": (1, 120000),
                "executor_completed->audit_closure": (0, 20000),
            },
            required_audit_events=["audit_closed"],
            required_state_events=[
                "edge_opened",
                "state_bound_to_action",
                "policy_bind_completed",
                "governance_authorized",
                "executor_started",
                "executor_completed",
                "edge_settled",
            ],
            required_companions=["policy_bind", "world_state_bind", "audit_closure"],
            settlement_timeout_ms=5000,
            genre_overrides={
                "siege": {"settlement_timeout_ms": 3500},
                "pastoral": {"settlement_timeout_ms": 7000},
            },
        )
        self._specs["mcp_tool_invocation"] = ChorusSpec(
            edge_type="mcp_tool_invocation",
            required_participants=["dispatch", "outbound_gate", "policy_bind", "executor", "audit_closure"],
            expected_sequence=[
                "dispatch",
                "policy_bind",
                "governance_authority",
                "executor_started",
                "executor_completed",
                "audit_closure",
                "edge_settled",
            ],
            settlement_timeout_ms=5000,
        )
        self._specs["outbound_gated_action"] = ChorusSpec(
            edge_type="outbound_gated_action",
            required_participants=["dispatch", "outbound_gate", "governance_authority", "executor"],
            expected_sequence=[
                "dispatch",
                "outbound_gate",
                "governance_authority",
                "executor_started",
                "executor_completed",
                "edge_settled",
            ],
            settlement_timeout_ms=5000,
        )

    def load_edge_chorus_spec(self, edge_type: str, genre_mode: Optional[str] = None) -> ChorusSpec:
        key = str(edge_type or "agent_command_execution").strip().lower()
        spec = self._specs.get(key) or self._specs["agent_command_execution"]
        spec_doc = _model_dump(spec)
        genre = str(genre_mode or "").strip().lower()
        override = (spec_doc.get("genre_overrides") or {}).get(genre) if genre else None
        if isinstance(override, dict):
            merged = dict(spec_doc)
            merged.update(override)
            return ChorusSpec(**merged)
        return spec

    def collect_edge_participants(self, action_id: str, context: Dict[str, Any]) -> EdgeObservation:
        ctx = context or {}
        observed_participants = list(dict.fromkeys([str(x) for x in (ctx.get("observed_participants") or []) if x]))
        observed_sequence = [str(x) for x in (ctx.get("observed_sequence") or []) if x]
        timestamps_ms = {}
        for key, value in (ctx.get("timestamps_ms") or {}).items():
            try:
                timestamps_ms[str(key)] = float(value)
            except Exception:
                continue
        audit_events = [str(x) for x in (ctx.get("audit_events") or []) if x]
        state_events = [str(x) for x in (ctx.get("state_events") or []) if x]
        vns_events = [str(x) for x in (ctx.get("vns_events") or []) if x]
        edge_type = str(ctx.get("edge_type") or "agent_command_execution")
        return EdgeObservation(
            action_id=str(action_id),
            edge_type=edge_type,
            observed_participants=observed_participants,
            observed_sequence=observed_sequence,
            timestamps_ms=timestamps_ms,
            audit_events=audit_events,
            state_events=state_events,
            vns_events=vns_events,
            missing_participants=[],
            unexpected_participants=[],
        )

    def score_companion_presence(self, spec: ChorusSpec, observation: EdgeObservation) -> float:
        required = [str(x) for x in (spec.required_participants or []) if x]
        observed = {str(x) for x in (observation.observed_participants or []) if x}
        required_companions = [str(x) for x in (spec.required_companions or []) if x]
        required_union = list(dict.fromkeys(required + required_companions))
        present = sum(1 for participant in required_union if participant in observed)
        missing = [participant for participant in required_union if participant not in observed]
        observation.missing_participants = missing
        observation.unexpected_participants = [participant for participant in observed if participant not in set(required_union + (spec.optional_participants or []))]
        return round(_safe_ratio(float(present), float(len(required_union))), 6)

    def score_sequence_resolution(self, spec: ChorusSpec, observation: EdgeObservation) -> float:
        expected = [str(x) for x in (spec.expected_sequence or []) if x]
        observed = [str(x) for x in (observation.observed_sequence or []) if x]
        if not expected:
            return 1.0
        obs_index = {value: idx for idx, value in enumerate(observed)}
        score = 0.0
        for idx, step in enumerate(expected):
            if step not in obs_index:
                continue
            # credit presence + order.
            score += 0.5
            if idx == 0:
                score += 0.5
            else:
                prev = expected[idx - 1]
                if prev in obs_index and obs_index[prev] < obs_index[step]:
                    score += 0.5
        max_score = float(len(expected))
        return round(_safe_ratio(score, max_score), 6)

    def score_mesh_entrainment(self, spec: ChorusSpec, observation: EdgeObservation) -> float:
        tolerances = spec.timing_tolerances_ms or {}
        if not tolerances:
            return 1.0
        timestamps = observation.timestamps_ms or {}
        passed = 0
        total = 0
        for relation, band in tolerances.items():
            rel = str(relation)
            if "->" not in rel:
                continue
            left, right = rel.split("->", 1)
            if left not in timestamps or right not in timestamps:
                continue
            total += 1
            try:
                min_ms = int(band[0])
                max_ms = int(band[1])
            except Exception:
                min_ms, max_ms = (0, 99999999)
            delta = float(timestamps[right] - timestamps[left])
            if float(min_ms) <= delta <= float(max_ms):
                passed += 1
        if total == 0:
            # if no timing pairs were available, treat as partial confidence not perfect
            return 0.6
        vns_penalty = 0.0
        if any("pulse_instability" in event for event in (observation.vns_events or [])):
            vns_penalty = 0.15
        return round(_clamp(_safe_ratio(float(passed), float(total)) - vns_penalty), 6)

    def score_audit_closure(self, spec: ChorusSpec, observation: EdgeObservation) -> float:
        required = [str(x) for x in (spec.required_audit_events or []) if x]
        if not required:
            return 1.0
        observed = {str(x) for x in (observation.audit_events or []) if x}
        present = sum(1 for event in required if event in observed)
        return round(_safe_ratio(float(present), float(len(required))), 6)

    def score_settlement(self, spec: ChorusSpec, observation: EdgeObservation) -> float:
        score = 1.0
        required_state = [str(x) for x in (spec.required_state_events or []) if x]
        if required_state:
            observed_state = {str(x) for x in (observation.state_events or []) if x}
            state_present = sum(1 for event in required_state if event in observed_state)
            score *= _safe_ratio(float(state_present), float(len(required_state)))
        timeout_ms = spec.settlement_timeout_ms
        if timeout_ms:
            timestamps = observation.timestamps_ms or {}
            opened = timestamps.get("edge_opened")
            settled = timestamps.get("edge_settled")
            if opened is not None and settled is not None:
                settlement_lag = float(settled - opened)
                if settlement_lag > float(timeout_ms):
                    over = settlement_lag - float(timeout_ms)
                    penalty = _clamp(over / max(float(timeout_ms), 1.0), 0.0, 0.7)
                    score = _clamp(score - penalty)
            else:
                score = _clamp(score - 0.25)
        return round(_clamp(score), 6)

    def classify_resolution(
        self,
        spec: ChorusSpec,
        observation: EdgeObservation,
        scores: Dict[str, float],
    ) -> str:
        quality = float(scores.get("chorus_quality") or 0.0)
        presence = float(scores.get("companion_presence_score") or 0.0)
        sequence = float(scores.get("sequence_resolution_score") or 0.0)
        settlement = float(scores.get("settlement_score") or 0.0)
        if presence < 0.45 or settlement < 0.35:
            return "fractured"
        if quality < 0.5 or sequence < 0.5:
            return "dissonant"
        if quality < 0.78:
            return "strained"
        return "consonant"

    @staticmethod
    def _dissonance_class(resolution_class: str, quality: float, settlement: float) -> Optional[str]:
        if resolution_class == "consonant":
            return None
        if resolution_class == "strained":
            return "local_strain"
        if resolution_class == "dissonant":
            return "dissonance"
        if quality < 0.2 or settlement < 0.2:
            return "score_corruption"
        return "choral_fracture"

    def assemble_chorus_state(
        self,
        *,
        spec: ChorusSpec,
        observation: EdgeObservation,
    ) -> ChorusState:
        companion_presence_score = self.score_companion_presence(spec, observation)
        sequence_resolution_score = self.score_sequence_resolution(spec, observation)
        mesh_entrainment_score = self.score_mesh_entrainment(spec, observation)
        audit_closure_score = self.score_audit_closure(spec, observation)
        settlement_score = self.score_settlement(spec, observation)
        chorus_quality = _clamp(
            (0.28 * companion_presence_score)
            + (0.22 * sequence_resolution_score)
            + (0.2 * mesh_entrainment_score)
            + (0.15 * audit_closure_score)
            + (0.15 * settlement_score)
        )
        scores = {
            "chorus_quality": chorus_quality,
            "companion_presence_score": companion_presence_score,
            "sequence_resolution_score": sequence_resolution_score,
            "mesh_entrainment_score": mesh_entrainment_score,
            "audit_closure_score": audit_closure_score,
            "settlement_score": settlement_score,
        }
        resolution_class = self.classify_resolution(spec, observation, scores)
        dissonance_class = self._dissonance_class(
            resolution_class=resolution_class,
            quality=chorus_quality,
            settlement=settlement_score,
        )
        rationale: List[str] = []
        if observation.missing_participants:
            rationale.append(f"missing participants: {', '.join(observation.missing_participants)}")
        if sequence_resolution_score < 0.75:
            rationale.append("sequence resolution below expected order")
        if mesh_entrainment_score < 0.7:
            rationale.append("mesh entrainment outside timing tolerance bands")
        if audit_closure_score < 1.0:
            rationale.append("required audit closure events missing")
        if settlement_score < 0.75:
            rationale.append("edge settlement incomplete or delayed")
        if not rationale:
            rationale.append("local edge choir resolved within expected bounds")
        return ChorusState(
            chorus_quality=round(chorus_quality, 6),
            companion_presence_score=round(companion_presence_score, 6),
            sequence_resolution_score=round(sequence_resolution_score, 6),
            mesh_entrainment_score=round(mesh_entrainment_score, 6),
            audit_closure_score=round(audit_closure_score, 6),
            settlement_score=round(settlement_score, 6),
            resolution_class=resolution_class,
            dissonance_class=dissonance_class,
            rationale=rationale,
        )


_chorus_engine_singleton: Optional[ChorusEngine] = None


def get_chorus_engine(db: Any = None) -> ChorusEngine:
    global _chorus_engine_singleton
    if _chorus_engine_singleton is None:
        _chorus_engine_singleton = ChorusEngine(db=db)
    elif db is not None and _chorus_engine_singleton.db is None:
        _chorus_engine_singleton.set_db(db)
    return _chorus_engine_singleton
