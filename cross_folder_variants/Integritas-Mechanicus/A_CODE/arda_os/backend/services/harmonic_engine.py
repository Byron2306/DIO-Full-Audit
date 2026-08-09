from __future__ import annotations

import math
import os
import statistics
from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List, Optional, Tuple


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


@dataclass
class BaselineRef:
    baseline_id: str
    scope_type: str
    actor_id: Optional[str]
    tool_name: Optional[str]
    target_domain: Optional[str]
    environment: Optional[str]
    version: str
    source: str
    baseline_band: Dict[str, float]


@dataclass
class TimingFeatures:
    sample_size: int
    timestamps_ms: Optional[List[float]]
    intervals_ms: List[float]
    last_interval_ms: Optional[float]
    median_interval_ms: Optional[float]
    mean_interval_ms: Optional[float]
    jitter_ms: float
    jitter_norm: float
    drift_norm: float
    burstiness: float
    entropy_signature: float
    sequence_class: str
    dominant_frequency: float


@dataclass
class HarmonicState:
    baseline_ref: BaselineRef
    resonance_score: float
    discord_score: float
    confidence: float
    drift_norm: float
    jitter_norm: float
    burstiness: float
    entropy_signature: float
    mode_recommendation: str
    rationale: List[str]


class HarmonicEngine:
    """
    Reconciled Arda Harmonic Engine.

    A self-contained cadence scorer shared by sovereign enforcement, Ainur,
    and higher-order runtime surfaces. It deliberately avoids schema coupling
    so the engine can operate even when broader polyphonic packages are absent.
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
        return [max(0.0, ordered[index] - ordered[index - 1]) for index in range(1, len(ordered))]

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
            (self._scope_key("actor_tool_domain_env", actor, tool, domain, env), "actor_tool_domain_env"),
            (self._scope_key("actor_tool_env", actor, tool, env), "actor_tool_env"),
            (self._scope_key("actor_env", actor, env), "actor_env"),
            (self._scope_key("tool_domain_env", tool, domain, env), "tool_domain_env"),
            (self._scope_key("domain_env", domain, env), "domain_env"),
            (self._scope_key("global_env", env), "global_env"),
            (self._scope_key("global", "all"), "global"),
        ]

    def _build_baseline_band(self, events: List[Dict[str, Any]]) -> Dict[str, float]:
        timestamps = [float(evt["timestamp_ms"]) for evt in events if evt.get("timestamp_ms") is not None]
        intervals = self.compute_intervals(timestamps)
        if not intervals:
            return dict(self._default_band)
        sorted_intervals = sorted(intervals)
        median_interval = float(statistics.median(intervals))
        p95_interval = self._percentile(sorted_intervals, 0.95)
        jitter = self.compute_jitter(intervals)
        entropy = self.compute_entropy_signature(intervals)
        burstiness = self.compute_burstiness(intervals, short_threshold_ms=30.0)
        return {
            "median_interval_ms": median_interval,
            "p95_interval_ms": p95_interval,
            "jitter_ms": max(jitter, 1.0),
            "short_threshold_ms": 30.0,
            "expected_burstiness": _clamp(burstiness),
            "entropy_target": _clamp(entropy),
            "entropy_tolerance": 0.30,
        }

    def _baseline_for_scope(
        self,
        actor_id: Optional[str],
        tool_name: Optional[str],
        target_domain: Optional[str],
        environment: Optional[str],
    ) -> BaselineRef:
        for scope_key, scope_type in self._candidate_scopes(actor_id, tool_name, target_domain, environment):
            events = list(self._events_by_scope.get(scope_key) or [])
            if len(self.compute_intervals([float(evt["timestamp_ms"]) for evt in events if evt.get("timestamp_ms") is not None])) >= 4:
                return BaselineRef(
                    baseline_id=f"baseline::{scope_key}",
                    scope_type=scope_type,
                    actor_id=actor_id,
                    tool_name=tool_name,
                    target_domain=target_domain,
                    environment=environment,
                    version="v1",
                    source="harmonic_engine.online",
                    baseline_band=self._build_baseline_band(events),
                )
        return BaselineRef(
            baseline_id=f"baseline::{self._scope_key('global', 'fallback')}",
            scope_type="global_fallback",
            actor_id=actor_id,
            tool_name=tool_name,
            target_domain=target_domain,
            environment=environment,
            version="v1",
            source="harmonic_engine.default",
            baseline_band=dict(self._default_band),
        )

    def _extract_timing_features(
        self,
        events: List[Dict[str, Any]],
        baseline: Optional[Dict[str, Any]] = None,
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
            sequence_class=sequence_tempo["sequence_class"],
            dominant_frequency=sequence_tempo["dominant_frequency"],
        )

    def _compute_harmonic_state(self, baseline_ref: BaselineRef, timing: TimingFeatures) -> HarmonicState:
        band = baseline_ref.baseline_band
        entropy_delta = abs(timing.entropy_signature - float(band.get("entropy_target", self._default_band["entropy_target"])))
        entropy_penalty = _safe_div(
            entropy_delta,
            float(band.get("entropy_tolerance", self._default_band["entropy_tolerance"])),
            default=0.0,
        )
        discord_score = _clamp(
            (timing.drift_norm * 0.35)
            + (timing.jitter_norm * 0.25)
            + (timing.burstiness * 0.20)
            + (_clamp(entropy_penalty) * 0.20)
        )
        resonance_score = _clamp(
            1.0
            - (
                (timing.drift_norm * 0.30)
                + (timing.jitter_norm * 0.25)
                + (timing.burstiness * 0.20)
                + (_clamp(entropy_penalty) * 0.10)
            )
        )
        confidence = _clamp(_sigmoid((timing.sample_size - 4.0) / 2.0))
        rationale: List[str] = []
        if timing.sample_size == 0:
            rationale.append("cold-start cadence; baseline still forming")
        if timing.drift_norm > 0.35:
            rationale.append("cadence drift from baseline pulse")
        if timing.jitter_norm > 0.50:
            rationale.append("jitter instability exceeds baseline band")
        if timing.burstiness > 0.35:
            rationale.append("burstiness above expected range")
        if entropy_penalty > 0.50:
            rationale.append("entropy signature departs from expected melody")
        if not rationale:
            rationale.append("timing resonance within expected bounds")

        if confidence < 0.40:
            mode = "observe_and_review"
        elif discord_score >= 0.85:
            mode = "sandbox_or_contain"
        elif discord_score >= 0.65:
            mode = "tighten_scrutiny"
        elif discord_score >= 0.45 or resonance_score <= 0.45 or timing.jitter_norm >= 0.80 or timing.burstiness >= 0.45:
            mode = "monitor_with_obligations"
        else:
            mode = "normal_flow"

        return HarmonicState(
            baseline_ref=baseline_ref,
            resonance_score=round(resonance_score, 6),
            discord_score=round(discord_score, 6),
            confidence=round(confidence, 6),
            drift_norm=timing.drift_norm,
            jitter_norm=timing.jitter_norm,
            burstiness=timing.burstiness,
            entropy_signature=timing.entropy_signature,
            mode_recommendation=mode,
            rationale=rationale,
        )

    def _record_observation_across_scopes(
        self,
        actor_id: Optional[str],
        tool_name: Optional[str],
        target_domain: Optional[str],
        environment: Optional[str],
        event: Dict[str, Any],
    ) -> None:
        for scope_key, _ in self._candidate_scopes(actor_id, tool_name, target_domain, environment):
            self._events_by_scope[scope_key].append(event)

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
        event = {
            "actor_id": actor_id,
            "tool_name": tool_name,
            "operation": operation or tool_name,
            "target_domain": target_domain,
            "environment": environment or "local",
            "stage": stage,
            "context": context or {},
            "timestamp_ms": float(timestamp_ms if timestamp_ms is not None else _utc_now_ms()),
        }
        self._record_observation_across_scopes(actor_id, tool_name, target_domain, environment, event)
        primary_scope = self._scope_key(
            "actor_tool_domain_env",
            actor_id or "*",
            tool_name or "*",
            target_domain or "*",
            environment or "local",
        )
        events = list(self._events_by_scope[primary_scope])
        baseline_ref = self._baseline_for_scope(actor_id, tool_name, target_domain, environment or "local")
        timing = self._extract_timing_features(events, baseline_ref.baseline_band)
        state = self._compute_harmonic_state(baseline_ref, timing)
        return {
            "event": event,
            "baseline_ref": asdict(baseline_ref),
            "timing_features": asdict(timing),
            "harmonic_state": asdict(state),
        }

    def observe(
        self,
        *,
        actor_id: str,
        tool_name: str,
        target_domain: str,
        operation: Optional[str] = None,
        environment: str = "local",
        stage: str = "gate",
        context: Optional[Dict[str, Any]] = None,
        timestamp_ms: Optional[float] = None,
    ) -> Dict[str, Any]:
        return self.score_observation(
            actor_id=actor_id,
            tool_name=tool_name,
            target_domain=target_domain,
            operation=operation,
            environment=environment,
            stage=stage,
            context=context,
            timestamp_ms=timestamp_ms,
        )


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
