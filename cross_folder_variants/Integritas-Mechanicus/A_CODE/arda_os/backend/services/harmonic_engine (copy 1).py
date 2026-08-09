from __future__ import annotations

import math
import os
import statistics
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List, Optional, Tuple

try:
    from schemas.polyphonic_models import BaselineRef, HarmonicState, TimingFeatures
except Exception:
    from backend.schemas.polyphonic_models import BaselineRef, HarmonicState, TimingFeatures


def _utc_now_ms() -> float:
    return datetime.now(timezone.utc).timestamp() * 1000.0


def _safe_div(numerator: float, denominator: float, default: float = 0.0) -> float:
    if denominator == 0:
        return default
    return numerator / denominator


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


def _sigmoid(x: float) -> float:
    try:
        return 1.0 / (1.0 + math.exp(-x))
    except OverflowError:
        return 0.0 if x < 0 else 1.0


def _model_dump(model: Any) -> Dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()  # type: ignore[no-any-return]
    if hasattr(model, "dict"):
        return model.dict()  # type: ignore[no-any-return]
    if hasattr(model, "__dict__"):
        return dict(model.__dict__)  # type: ignore[no-any-return]
    return dict(model)


class HarmonicEngine:
    """
    Phase 3 Harmonic Governance Layer (HGL) online scoring engine.
    Tracks timing cadence windows and computes resonance/discord/confidence.
    """

    def __init__(self, db: Any = None, *, window_size: int = 64):
        self.db = db
        self.window_size = max(16, int(window_size))
        self._events_by_scope: Dict[str, Deque[Dict[str, Any]]] = defaultdict(
            lambda: deque(maxlen=self.window_size)
        )
        self._default_band = {
            "median_interval_ms": 200.0,
            "p95_interval_ms": 900.0,
            "jitter_ms": 120.0,
            "short_threshold_ms": 80.0,
            "expected_burstiness": 0.15,
            "entropy_target": 0.72,
            "entropy_tolerance": 0.28,
        }

    def set_db(self, db: Any) -> None:
        self.db = db

    @staticmethod
    def _scope_key(scope_type: str, *parts: Optional[str]) -> str:
        normalized = [str(scope_type).strip().lower()]
        for part in parts:
            normalized.append(str(part or "*").strip().lower())
        return "::".join(normalized)

    @staticmethod
    def _percentile(sorted_values: List[float], q: float) -> float:
        if not sorted_values:
            return 0.0
        if q <= 0:
            return sorted_values[0]
        if q >= 1:
            return sorted_values[-1]
        pos = (len(sorted_values) - 1) * q
        lower = int(math.floor(pos))
        upper = int(math.ceil(pos))
        if lower == upper:
            return sorted_values[lower]
        ratio = pos - lower
        return sorted_values[lower] * (1.0 - ratio) + sorted_values[upper] * ratio

    def compute_intervals(self, timestamps: List[float]) -> List[float]:
        ordered = [float(ts) for ts in timestamps if ts is not None]
        if len(ordered) < 2:
            return []
        return [max(0.0, ordered[i] - ordered[i - 1]) for i in range(1, len(ordered))]

    def compute_jitter(self, intervals: List[float], window: Optional[int] = None) -> float:
        if not intervals:
            return 0.0
        series = intervals[-int(window):] if window else intervals
        if len(series) <= 1:
            return 0.0
        return float(statistics.pstdev(series))

    def compute_drift(self, intervals: List[float], baseline_band: Optional[Dict[str, Any]]) -> float:
        if not intervals:
            return 0.0
        band = baseline_band or self._default_band
        baseline_median = float(band.get("median_interval_ms") or self._default_band["median_interval_ms"])
        observed_median = float(statistics.median(intervals))
        return abs(observed_median - baseline_median) / max(baseline_median, 1.0)

    def compute_burstiness(
        self,
        intervals: List[float],
        short_threshold_ms: float,
        baseline_expectation: Optional[float] = None,
    ) -> float:
        if not intervals:
            return 0.0
        threshold = max(1.0, float(short_threshold_ms))
        short_ratio = _safe_div(sum(1 for value in intervals if value <= threshold), len(intervals))
        if baseline_expectation is None:
            return short_ratio
        return max(0.0, short_ratio - float(baseline_expectation))

    def compute_entropy_signature(
        self,
        intervals: List[float],
        bucket_scheme: Optional[List[float]] = None,
    ) -> float:
        if not intervals:
            return 0.0
        buckets = sorted(bucket_scheme or [50.0, 150.0, 400.0, 1000.0])
        counts = [0] * (len(buckets) + 1)
        for value in intervals:
            placed = False
            for index, limit in enumerate(buckets):
                if value <= limit:
                    counts[index] += 1
                    placed = True
                    break
            if not placed:
                counts[-1] += 1
        total = float(sum(counts))
        if total <= 0:
            return 0.0
        entropy = 0.0
        for count in counts:
            if count <= 0:
                continue
            probability = count / total
            entropy -= probability * math.log(probability, 2)
        max_entropy = math.log(len(counts), 2) if len(counts) > 1 else 1.0
        return _clamp(_safe_div(entropy, max_entropy, default=0.0))

    def compute_sequence_tempo(self, tool_sequence: List[str], timestamps: List[float]) -> Dict[str, Any]:
        intervals = self.compute_intervals(timestamps)
        if not intervals:
            return {"sequence_class": "cold_start", "dominant_frequency": 0.0}
        median_interval = float(statistics.median(intervals))
        mean_interval = float(statistics.mean(intervals))
        jitter = self.compute_jitter(intervals)
        cv = _safe_div(jitter, mean_interval)
        if median_interval <= 80 and cv < 0.35:
            sequence_class = "rapid_regular"
        elif cv < 0.25:
            sequence_class = "regular"
        elif cv > 0.9:
            sequence_class = "chaotic"
        else:
            sequence_class = "adaptive"
        dominant_frequency = _safe_div(1000.0, max(median_interval, 1.0))
        return {
            "sequence_class": sequence_class,
            "dominant_frequency": round(dominant_frequency, 6),
            "tool_sequence_size": len(tool_sequence or []),
        }

    def extract_timing_features(
        self,
        events: List[Dict[str, Any]],
        baseline: Optional[Dict[str, Any]] = None,
        scope: Optional[str] = None,
    ) -> TimingFeatures:
        timestamps = [float(evt.get("timestamp_ms")) for evt in events if evt.get("timestamp_ms") is not None]
        intervals = self.compute_intervals(timestamps)
        last_interval = intervals[-1] if intervals else None
        median_interval = float(statistics.median(intervals)) if intervals else None
        mean_interval = float(statistics.mean(intervals)) if intervals else None
        jitter = self.compute_jitter(intervals)
        band = baseline or self._default_band
        drift_norm = self.compute_drift(intervals, band)
        jitter_norm = _safe_div(jitter, float(band.get("jitter_ms") or self._default_band["jitter_ms"]), default=0.0)
        burstiness = self.compute_burstiness(
            intervals,
            short_threshold_ms=float(band.get("short_threshold_ms") or self._default_band["short_threshold_ms"]),
            baseline_expectation=float(band.get("expected_burstiness") or self._default_band["expected_burstiness"]),
        )
        entropy_signature = self.compute_entropy_signature(intervals)
        sequence_tempo = self.compute_sequence_tempo(
            tool_sequence=[str(evt.get("tool_name") or evt.get("operation") or "") for evt in events],
            timestamps=timestamps,
        )
        return TimingFeatures(
            sample_size=len(intervals),
            timestamps_ms=timestamps if timestamps else None,
            intervals_ms=[round(value, 6) for value in intervals],
            last_interval_ms=round(last_interval, 6) if last_interval is not None else None,
            median_interval_ms=round(median_interval, 6) if median_interval is not None else None,
            mean_interval_ms=round(mean_interval, 6) if mean_interval is not None else None,
            jitter_ms=round(jitter, 6),
            jitter_norm=round(_clamp(jitter_norm), 6),
            drift_norm=round(_clamp(drift_norm), 6),
            burstiness=round(_clamp(burstiness), 6),
            entropy_signature=round(_clamp(entropy_signature), 6),
            sequence_class=sequence_tempo.get("sequence_class"),
            dominant_frequency=sequence_tempo.get("dominant_frequency"),
        )

    def _build_baseline_band(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        timestamps = [float(evt.get("timestamp_ms")) for evt in events if evt.get("timestamp_ms") is not None]
        intervals = self.compute_intervals(timestamps)
        if len(intervals) < 4:
            return dict(self._default_band)
        ordered = sorted(intervals)
        median_interval = float(statistics.median(ordered))
        p95_interval = self._percentile(ordered, 0.95)
        jitter = self.compute_jitter(intervals)
        burstiness = self.compute_burstiness(intervals, short_threshold_ms=80.0, baseline_expectation=None)
        entropy = self.compute_entropy_signature(intervals)
        return {
            "median_interval_ms": median_interval,
            "p95_interval_ms": p95_interval,
            "jitter_ms": max(jitter, 1.0),
            "short_threshold_ms": min(150.0, max(30.0, median_interval * 0.45)),
            "expected_burstiness": _clamp(burstiness),
            "entropy_target": _clamp(entropy),
            "entropy_tolerance": 0.30,
        }

    def _candidate_scopes(
        self,
        actor_id: Optional[str],
        tool_name: Optional[str],
        target_domain: Optional[str],
        environment: Optional[str],
    ) -> List[Tuple[str, str]]:
        env = str(environment or "unknown").lower()
        actor = str(actor_id or "*").lower()
        tool = str(tool_name or "*").lower()
        domain = str(target_domain or "*").lower()
        return [
            (
                self._scope_key("actor_tool_domain_env", actor, tool, domain, env),
                "actor_tool_domain_env",
            ),
            (
                self._scope_key("actor_tool_env", actor, tool, env),
                "actor_tool_env",
            ),
            (
                self._scope_key("actor_env", actor, env),
                "actor_env",
            ),
            (
                self._scope_key("tool_domain_env", tool, domain, env),
                "tool_domain_env",
            ),
            (
                self._scope_key("domain_env", domain, env),
                "domain_env",
            ),
            (
                self._scope_key("global_env", env),
                "global_env",
            ),
            (
                self._scope_key("global", "all"),
                "global",
            ),
        ]

    def select_baseline_scope(
        self,
        actor_id: Optional[str],
        tool_name: Optional[str],
        target_domain: Optional[str],
        env: Optional[str],
    ) -> BaselineRef:
        for key, scope_type in self._candidate_scopes(actor_id, tool_name, target_domain, env):
            events = list(self._events_by_scope.get(key) or [])
            intervals = self.compute_intervals([float(evt.get("timestamp_ms")) for evt in events if evt.get("timestamp_ms") is not None])
            if len(intervals) >= 4:
                band = self._build_baseline_band(events)
                return BaselineRef(
                    baseline_id=f"baseline::{key}",
                    scope_type=scope_type,
                    actor_id=actor_id,
                    tool_name=tool_name,
                    target_domain=target_domain,
                    environment=env,
                    version="v1",
                    source="harmonic_engine.online",
                    baseline_band=band,
                )
        # cold-start fallback
        return BaselineRef(
            baseline_id=f"baseline::{self._scope_key('global', 'fallback')}",
            scope_type="global_fallback",
            actor_id=actor_id,
            tool_name=tool_name,
            target_domain=target_domain,
            environment=env,
            version="v1",
            source="harmonic_engine.default",
            baseline_band=dict(self._default_band),
        )

    def compute_resonance_score(self, features: TimingFeatures, baseline_ref: BaselineRef) -> float:
        drift = float(features.drift_norm or 0.0)
        jitter = float(features.jitter_norm or 0.0)
        burst = float(features.burstiness or 0.0)
        entropy = float(features.entropy_signature or 0.0)
        band = baseline_ref.baseline_band or self._default_band
        entropy_target = float(band.get("entropy_target") or self._default_band["entropy_target"])
        entropy_tolerance = float(band.get("entropy_tolerance") or self._default_band["entropy_tolerance"])
        entropy_fit = 1.0 - _clamp(abs(entropy - entropy_target) / max(entropy_tolerance, 0.01))
        raw = (
            +1.4 * (1.0 - _clamp(jitter))
            +1.6 * (1.0 - _clamp(drift))
            +1.2 * (1.0 - _clamp(burst))
            +0.8 * entropy_fit
            -2.0
        )
        return round(_clamp(_sigmoid(raw)), 6)

    def compute_discord_score(self, features: TimingFeatures, baseline_ref: BaselineRef) -> float:
        drift = float(features.drift_norm or 0.0)
        jitter = float(features.jitter_norm or 0.0)
        burst = float(features.burstiness or 0.0)
        entropy = float(features.entropy_signature or 0.0)
        band = baseline_ref.baseline_band or self._default_band
        entropy_target = float(band.get("entropy_target") or self._default_band["entropy_target"])
        entropy_tolerance = float(band.get("entropy_tolerance") or self._default_band["entropy_tolerance"])
        entropy_delta = _clamp(abs(entropy - entropy_target) / max(entropy_tolerance, 0.01))
        perfect_tempo_penalty = 0.0
        if features.sample_size >= 5 and (features.jitter_ms or 0.0) < 5.0:
            perfect_tempo_penalty = 0.20
        raw = (
            +1.5 * _clamp(drift)
            +1.2 * _clamp(jitter)
            +1.4 * _clamp(burst)
            +0.9 * entropy_delta
            +perfect_tempo_penalty
            -1.6
        )
        return round(_clamp(_sigmoid(raw)), 6)

    def compute_confidence(
        self,
        features: TimingFeatures,
        sample_size: int,
        env_conditions: Optional[Dict[str, Any]] = None,
    ) -> float:
        sample_factor = _clamp(_safe_div(float(sample_size), 16.0))
        env_conditions = env_conditions or {}
        baseline_quality = _clamp(float(env_conditions.get("baseline_quality", 0.75)))
        degradation_penalty = 0.2 if str(env_conditions.get("environment_state") or "").lower() in {"degraded", "incident"} else 0.0
        confidence = (0.65 * sample_factor) + (0.35 * baseline_quality) - degradation_penalty
        return round(_clamp(confidence), 6)

    def _mode_recommendation(self, resonance: float, discord: float, confidence: float) -> Tuple[str, List[str]]:
        rationale: List[str] = []
        if confidence < 0.4:
            rationale.append("low confidence due to limited cadence evidence")
            return "observe_and_review", rationale
        if discord >= 0.85:
            rationale.append("extreme discord score")
            return "sandbox_or_contain", rationale
        if discord >= 0.65:
            rationale.append("high discord score")
            return "tighten_scrutiny", rationale
        if discord >= 0.45 or resonance <= 0.45:
            rationale.append("moderate timing strain")
            return "monitor_with_obligations", rationale
        rationale.append("timing resonance within expected bounds")
        return "normal_flow", rationale

    def _record_event(self, scope_key: str, event: Dict[str, Any]) -> None:
        self._events_by_scope[scope_key].append(event)

    def _record_observation_across_scopes(
        self,
        actor_id: Optional[str],
        tool_name: Optional[str],
        target_domain: Optional[str],
        environment: Optional[str],
        event: Dict[str, Any],
    ) -> None:
        for scope_key, _ in self._candidate_scopes(actor_id, tool_name, target_domain, environment):
            self._record_event(scope_key, event)

    def score_observation(
        self,
        *,
        actor_id: Optional[str],
        tool_name: Optional[str],
        target_domain: Optional[str],
        environment: Optional[str],
        stage: str,
        timestamp_ms: Optional[float] = None,
        operation: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        ts_ms = float(timestamp_ms if timestamp_ms is not None else _utc_now_ms())
        event = {
            "timestamp_ms": ts_ms,
            "stage": str(stage),
            "actor_id": actor_id,
            "tool_name": tool_name,
            "operation": operation or tool_name,
            "target_domain": target_domain,
            "environment": environment,
            "context": context or {},
        }
        resolved_context = context or {}
        threat_state = str(resolved_context.get("threat_state") or "").strip().lower()
        learn_baseline = bool(resolved_context.get("learn_baseline", True))
        if threat_state in {"active", "elevated", "incident", "siege"}:
            learn_baseline = False
        if learn_baseline:
            self._record_observation_across_scopes(
                actor_id=actor_id,
                tool_name=tool_name,
                target_domain=target_domain,
                environment=environment,
                event=event,
            )
        primary_scope_key = self._scope_key(
            "actor_tool_domain_env",
            actor_id or "*",
            tool_name or "*",
            target_domain or "*",
            environment or "unknown",
        )
        primary_events = list(self._events_by_scope.get(primary_scope_key) or [])
        if not learn_baseline:
            primary_events = primary_events + [event]
        baseline_ref = self.select_baseline_scope(actor_id, tool_name, target_domain, environment)
        features = self.extract_timing_features(
            primary_events,
            baseline=baseline_ref.baseline_band or self._default_band,
            scope=primary_scope_key,
        )
        # 1. Calculate base discord and resonance using full sigmoid logic
        raw_discord = self.compute_discord_score(features, baseline_ref)
        raw_resonance = self.compute_resonance_score(features, baseline_ref)
        
        # 2. Phase 26: Polyphonic Resonance Integration
        from .resonance_service import get_resonance_service
        res_svc = get_resonance_service()
        spectrum = res_svc.get_resonance_spectrum()
        
        # Adjust resonance and discord based on choral spectrum
        micro_fact = float(spectrum.get("micro", 1.0))
        meso_fact = float(spectrum.get("meso", 1.0))
        macro_fact = float(spectrum.get("macro", 1.0))
        
        # Spectral Multiplication
        # Micro (Infrasound) is the absolute foundation.
        resonance_score = _clamp(raw_resonance * (0.4 * micro_fact + 0.3 * meso_fact + 0.3 * macro_fact))
        if micro_fact < 0.1:
            resonance_score = 0.0
            
        # Discord is boosted by choral dissonance
        discord_score = _clamp(raw_discord + (1.0 - micro_fact) * 0.5 + (1.0 - meso_fact) * 0.3)

        confidence = self.compute_confidence(
            features,
            sample_size=features.sample_size,
            env_conditions={
                "baseline_quality": (0.85 if baseline_ref.scope_type != "global_fallback" else 0.45) * micro_fact,
                "environment_state": "degraded"
                if str(environment or "").lower() in {"incident", "degraded"} or micro_fact < 0.5
                else "normal",
            },
        )
        mode_recommendation, rationale = self._mode_recommendation(resonance_score, discord_score, confidence)
        
        # Add spectral rationale
        if micro_fact < 0.8:
            rationale.append(f"Infrasound (Micro) dissonance: {micro_fact}")
        if meso_fact < 0.8:
            rationale.append(f"Mid-range (Meso) rhythm drift: {meso_fact}")
        # enrich rationale with top contributors
        if float(features.burstiness or 0.0) > 0.35:
            rationale.append("burstiness above expected range")
        if float(features.drift_norm or 0.0) > 0.35:
            rationale.append("cadence drift from baseline pulse")
        if float(features.jitter_norm or 0.0) > 0.5:
            rationale.append("jitter instability exceeds baseline band")
        
        harmonic_state = HarmonicState(
            resonance_score=resonance_score,
            discord_score=discord_score,
            confidence=confidence,
            baseline_ref=baseline_ref,
            mode_recommendation=mode_recommendation,
            drift_norm=features.drift_norm,
            jitter_norm=features.jitter_norm,
            burstiness=features.burstiness,
            entropy_signature=features.entropy_signature,
            rationale=rationale,
            baseline_ref_id=baseline_ref.baseline_id
        )
        return {
            "event": event,
            "timing_features": _model_dump(features),
            "baseline_ref": _model_dump(baseline_ref),
            "harmonic_state": _model_dump(harmonic_state),
        }


_harmonic_engine_singleton: Optional[HarmonicEngine] = None


def get_harmonic_engine(db: Any = None) -> HarmonicEngine:
    global _harmonic_engine_singleton
    if _harmonic_engine_singleton is None:
        _harmonic_engine_singleton = HarmonicEngine(
            db=db,
            window_size=int(os.environ.get("HGL_WINDOW_SIZE", "64")),
        )
    elif db is not None and _harmonic_engine_singleton.db is None:
        _harmonic_engine_singleton.set_db(db)
    return _harmonic_engine_singleton
