"""
Agenticity and logic-budget exhaustion metrics.

This module formalizes the core metrics described in the strategic roadmap:
- Agenticity score: weighted composite for autonomous hostile behavior
- CBR: Context Burn Rate
- TBCR: Tool Budget Consumption Rate
- CDI: Confidence Degradation Index
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from math import log2
from typing import Any, Dict, List, Optional
import uuid


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _extract_command_timestamps(behavior_data: Dict[str, Any]) -> List[float]:
    raw = behavior_data.get("command_timestamps") or []
    if not isinstance(raw, list):
        return []
    parsed = [_safe_float(ts, 0.0) for ts in raw]
    return [ts for ts in parsed if ts > 0]


def _shannon_entropy(values: List[str]) -> float:
    if not values:
        return 0.0
    counts: Dict[str, int] = {}
    for val in values:
        counts[val] = counts.get(val, 0) + 1
    total = float(len(values))
    entropy = 0.0
    for count in counts.values():
        p = count / total
        entropy -= p * log2(p)
    max_entropy = log2(len(counts)) if len(counts) > 1 else 1.0
    return _clamp(entropy / max_entropy)


@dataclass
class AgenticityFeatureVector:
    command_velocity: float
    inter_command_timing_variance: float
    path_entropy: float
    pebble_load_depth: float
    llm_trap_susceptibility: float

    def to_dict(self) -> Dict[str, float]:
        return asdict(self)


@dataclass
class AgenticityScore:
    score: float
    classification: str
    feature_vector: AgenticityFeatureVector
    weights: Dict[str, float] = field(default_factory=dict)
    weighted_components: Dict[str, float] = field(default_factory=dict)
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["feature_vector"] = self.feature_vector.to_dict()
        return payload


@dataclass
class ExhaustionMetrics:
    cbr: float
    tbcr: float
    cdi: float
    tokens_consumed: int
    tool_calls_made: int
    real_assets_discovered: int
    baseline_confidence: float
    current_confidence: float
    measured_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def compute_agenticity_score(behavior_data: Dict[str, Any]) -> AgenticityScore:
    timestamps = _extract_command_timestamps(behavior_data)
    duration = _safe_float(behavior_data.get("session_duration_s"), 0.0)
    command_count = int(_safe_float(behavior_data.get("command_count"), float(len(timestamps))))

    velocity = 0.0
    if duration > 0:
        velocity = command_count / duration
    elif len(timestamps) > 1:
        observed_duration = max(timestamps) - min(timestamps)
        if observed_duration > 0:
            velocity = len(timestamps) / observed_duration

    velocity_norm = _clamp(velocity / 5.0)

    variance_norm = 0.0
    if len(timestamps) > 2:
        intervals = [timestamps[i + 1] - timestamps[i] for i in range(len(timestamps) - 1)]
        mean_interval = sum(intervals) / len(intervals)
        variance = sum((x - mean_interval) ** 2 for x in intervals) / len(intervals)
        variance_norm = _clamp(variance / max(mean_interval, 1.0))

    command_paths = behavior_data.get("command_paths") or behavior_data.get("accessed_resources") or []
    if not isinstance(command_paths, list):
        command_paths = [str(command_paths)]
    path_entropy = _shannon_entropy([str(p) for p in command_paths if p is not None])

    pebble_depth_raw = _safe_float(behavior_data.get("pebble_load_depth"), 0.0)
    decoy_interactions = _safe_float(behavior_data.get("decoy_interactions"), 0.0)
    pebble_depth = _clamp(max(pebble_depth_raw, decoy_interactions / 10.0))

    trap_rate = _safe_float(behavior_data.get("llm_trap_hit_rate"), 0.0)
    decoy_touched = bool(behavior_data.get("decoy_touched", False))
    trap_susceptibility = _clamp(max(trap_rate, 1.0 if decoy_touched else 0.0))

    feature_vector = AgenticityFeatureVector(
        command_velocity=velocity_norm,
        inter_command_timing_variance=variance_norm,
        path_entropy=path_entropy,
        pebble_load_depth=pebble_depth,
        llm_trap_susceptibility=trap_susceptibility,
    )

    weights = {
        "command_velocity": 0.25,
        "inter_command_timing_variance": 0.20,
        "path_entropy": 0.20,
        "pebble_load_depth": 0.15,
        "llm_trap_susceptibility": 0.20,
    }

    weighted = {
        "command_velocity": feature_vector.command_velocity * weights["command_velocity"],
        "inter_command_timing_variance": feature_vector.inter_command_timing_variance
        * weights["inter_command_timing_variance"],
        "path_entropy": feature_vector.path_entropy * weights["path_entropy"],
        "pebble_load_depth": feature_vector.pebble_load_depth * weights["pebble_load_depth"],
        "llm_trap_susceptibility": feature_vector.llm_trap_susceptibility
        * weights["llm_trap_susceptibility"],
    }
    score = _clamp(sum(weighted.values()))

    if score >= 0.85:
        classification = "autonomous_agent_high"
    elif score >= 0.65:
        classification = "autonomous_agent_medium"
    elif score >= 0.45:
        classification = "automation_suspected"
    else:
        classification = "human_or_script_low"

    return AgenticityScore(
        score=score,
        classification=classification,
        feature_vector=feature_vector,
        weights=weights,
        weighted_components=weighted,
    )


def compute_exhaustion_metrics(behavior_data: Dict[str, Any]) -> ExhaustionMetrics:
    real_assets = int(_safe_float(behavior_data.get("real_assets_discovered"), 0))
    asset_divisor = max(1, real_assets)

    tokens_consumed = int(_safe_float(behavior_data.get("tokens_consumed"), 0))
    tool_calls = int(_safe_float(behavior_data.get("tool_calls_made"), 0))

    if tool_calls <= 0:
        tools_used = behavior_data.get("tools_used") or []
        if isinstance(tools_used, list):
            tool_calls = len(tools_used)

    cbr = float(tokens_consumed) / float(asset_divisor)
    tbcr = float(tool_calls) / float(asset_divisor)

    baseline_conf = _safe_float(behavior_data.get("baseline_decision_confidence"), 1.0)
    current_conf = _safe_float(behavior_data.get("current_decision_confidence"), baseline_conf)
    baseline_conf = _clamp(baseline_conf)
    current_conf = _clamp(current_conf)

    if baseline_conf <= 0.0:
        cdi = 0.0
    else:
        cdi = _clamp((baseline_conf - current_conf) / baseline_conf)

    return ExhaustionMetrics(
        cbr=round(cbr, 4),
        tbcr=round(tbcr, 4),
        cdi=round(cdi, 4),
        tokens_consumed=tokens_consumed,
        tool_calls_made=tool_calls,
        real_assets_discovered=real_assets,
        baseline_confidence=baseline_conf,
        current_confidence=current_conf,
    )


# ---------------------------------------------------------------------------
# Database persistence
# ---------------------------------------------------------------------------

import logging
logger = logging.getLogger(__name__)

class AgenticityPersistence:
    """Database persistence for agenticity scores and exhaustion metrics."""

    def __init__(self, db):
        self.db = db
        self.scores_collection = db.agenticity_scores
        self.exhaustion_collection = db.exhaustion_metrics
        self.sessions_collection = db.agenticity_sessions

    async def save_score(self, score: AgenticityScore, session_id: str, campaign_id: Optional[str] = None) -> bool:
        """Save an agenticity score to database."""
        try:
            score_dict = score.to_dict()
            score_dict["_id"] = f"{session_id}_{score.generated_at}"
            score_dict["session_id"] = session_id
            score_dict["campaign_id"] = campaign_id

            await self.scores_collection.replace_one(
                {"_id": score_dict["_id"]},
                score_dict,
                upsert=True
            )
            return True
        except Exception as e:
            logger.error(f"Failed to save agenticity score for session {session_id}: {e}")
            return False

    async def save_exhaustion_metrics(self, metrics: ExhaustionMetrics, session_id: str, campaign_id: Optional[str] = None) -> bool:
        """Save exhaustion metrics to database."""
        try:
            metrics_dict = metrics.to_dict()
            metrics_dict["_id"] = f"{session_id}_{metrics.measured_at}"
            metrics_dict["session_id"] = session_id
            metrics_dict["campaign_id"] = campaign_id

            await self.exhaustion_collection.replace_one(
                {"_id": metrics_dict["_id"]},
                metrics_dict,
                upsert=True
            )
            return True
        except Exception as e:
            logger.error(f"Failed to save exhaustion metrics for session {session_id}: {e}")
            return False

    async def get_score_history(self, session_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get agenticity score history for a session."""
        try:
            cursor = self.scores_collection.find(
                {"session_id": session_id}
            ).sort("generated_at", -1).limit(limit)

            return await cursor.to_list(length=limit)
        except Exception as e:
            logger.error(f"Failed to get score history for session {session_id}: {e}")
            return []

    async def get_exhaustion_history(self, session_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get exhaustion metrics history for a session."""
        try:
            cursor = self.exhaustion_collection.find(
                {"session_id": session_id}
            ).sort("measured_at", -1).limit(limit)

            return await cursor.to_list(length=limit)
        except Exception as e:
            logger.error(f"Failed to get exhaustion history for session {session_id}: {e}")
            return []

    async def get_session_summary(self, session_id: str) -> Dict[str, Any]:
        """Get comprehensive session summary with latest scores and metrics."""
        try:
            # Get latest score
            latest_score = await self.scores_collection.find_one(
                {"session_id": session_id},
                sort=[("generated_at", -1)]
            )

            # Get latest exhaustion metrics
            latest_exhaustion = await self.exhaustion_collection.find_one(
                {"session_id": session_id},
                sort=[("measured_at", -1)]
            )

            # Get session metadata
            session_doc = await self.sessions_collection.find_one({"_id": session_id})

            return {
                "session_id": session_id,
                "session_metadata": session_doc or {},
                "latest_score": latest_score,
                "latest_exhaustion": latest_exhaustion,
                "score_history_count": await self.scores_collection.count_documents({"session_id": session_id}),
                "exhaustion_history_count": await self.exhaustion_collection.count_documents({"session_id": session_id}),
            }
        except Exception as e:
            logger.error(f"Failed to get session summary for {session_id}: {e}")
            return {"error": str(e)}

    async def save_session_metadata(self, session_data: Dict) -> bool:
        """Save session metadata."""
        try:
            session_data["_id"] = session_data.get("session_id", str(uuid.uuid4()))
            await self.sessions_collection.replace_one(
                {"_id": session_data["_id"]},
                session_data,
                upsert=True
            )
            return True
        except Exception as e:
            logger.error(f"Failed to save session metadata: {e}")
            return False


# Global persistence instance
_agenticity_persistence: Optional[AgenticityPersistence] = None


def get_agenticity_persistence(db=None):
    """Get agenticity persistence instance."""
    global _agenticity_persistence
    if _agenticity_persistence is None and db is not None:
        _agenticity_persistence = AgenticityPersistence(db)
    return _agenticity_persistence
