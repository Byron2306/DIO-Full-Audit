"""
Sector boundary control pattern (VNS + MCP split responsibilities).

VNS side:
- Observe boundary crossings pre/post gate
- Score suspiciousness and tempo
- Raise sector beacon state

MCP side:
- Enforce lawful crossing (identity, token, decision context, scope)

This module is intentionally generic so the same contract can be reused
across sectors. First production wiring is Governance -> Tool Execution.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Deque, Dict, List, Optional
from collections import defaultdict, deque


SECTOR_SENSOR = "sensor"
SECTOR_COGNITION = "cognition"
SECTOR_GOVERNANCE = "governance"
SECTOR_TOOL_EXECUTION = "tool_execution"
SECTOR_DECEPTION_VALIDATION = "deception_validation"

SECTOR_RECIPES: Dict[str, Dict[str, str]] = {
    SECTOR_SENSOR: {"edge": "VNS", "gate": "MCP"},
    SECTOR_COGNITION: {"edge": "VNS", "gate": "MCP"},
    SECTOR_GOVERNANCE: {"edge": "VNS", "gate": "MCP"},
    SECTOR_TOOL_EXECUTION: {"edge": "VNS", "gate": "MCP"},
    SECTOR_DECEPTION_VALIDATION: {"edge": "VNS", "gate": "MCP"},
}

CANONICAL_BOUNDARY_OUTCOMES = {
    "allowed",
    "denied",
    "queued",
    "anomalous",
    "token-invalid",
    "decoy-hit",
}

_SECTOR_SET = set(SECTOR_RECIPES.keys())
_BEACON_ORDER = {"green": 0, "amber": 1, "red": 2}


@dataclass
class BoundaryCrossingContract:
    principal: str
    sector_from: str
    sector_to: str
    capability: str
    target: str
    decision_context: Dict[str, Any] = field(default_factory=dict)
    token: Optional[str] = None
    risk_hint: Dict[str, Any] = field(default_factory=dict)
    trace_id: Optional[str] = None


class SectorBoundaryControl:
    """Boundary controller with VNS-style observation heuristics."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._tempo: Dict[str, Deque[datetime]] = defaultdict(lambda: deque(maxlen=64))
        self._sector_beacons: Dict[str, Dict[str, Any]] = {
            sector: {
                "state": "green",
                "score": 0,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "reason": "initialized",
            }
            for sector in _SECTOR_SET
        }
        self._recent_crossings: Deque[Dict[str, Any]] = deque(maxlen=500)

    @staticmethod
    def _normalize_sector(value: str, fallback: str) -> str:
        normalized = str(value or "").strip().lower()
        if normalized in _SECTOR_SET:
            return normalized
        return fallback

    @staticmethod
    def _beacon_state(score: int) -> str:
        if score >= 70:
            return "red"
        if score >= 40:
            return "amber"
        return "green"

    @staticmethod
    def _is_decoy_target(target: str, risk_hint: Dict[str, Any]) -> bool:
        if bool((risk_hint or {}).get("decoy_interaction")):
            return True
        lowered = str(target or "").lower()
        return any(marker in lowered for marker in ("honey", "canary", "decoy", "trap"))

    def _update_sector_beacon(self, sector: str, state: str, score: int, reason: str) -> Dict[str, Any]:
        sector = self._normalize_sector(sector, SECTOR_GOVERNANCE)
        current = self._sector_beacons.get(sector) or {
            "state": "green",
            "score": 0,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "reason": "missing",
        }
        current_state = str(current.get("state") or "green")
        should_raise = _BEACON_ORDER.get(state, 0) > _BEACON_ORDER.get(current_state, 0)
        should_refresh = (state == current_state and score >= int(current.get("score") or 0))
        if should_raise or should_refresh:
            current = {
                "state": state,
                "score": int(score),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "reason": reason,
            }
            self._sector_beacons[sector] = current
        return {"sector": sector, **current}

    def _tempo_score(self, key: str) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        timeline = self._tempo[key]
        timeline.append(now)
        one_minute_ago = now - timedelta(seconds=60)
        while timeline and timeline[0] < one_minute_ago:
            timeline.popleft()
        crossings_per_minute = len(timeline)
        tempo_score = 0
        tempo_reason = "normal_tempo"
        if crossings_per_minute >= 12:
            tempo_score = 35
            tempo_reason = "high_boundary_tempo"
        elif crossings_per_minute >= 6:
            tempo_score = 20
            tempo_reason = "elevated_boundary_tempo"
        return {
            "crossings_per_minute": crossings_per_minute,
            "tempo_score": tempo_score,
            "tempo_reason": tempo_reason,
        }

    def pre_observe(self, contract: BoundaryCrossingContract) -> Dict[str, Any]:
        sector_from = self._normalize_sector(contract.sector_from, SECTOR_GOVERNANCE)
        sector_to = self._normalize_sector(contract.sector_to, SECTOR_TOOL_EXECUTION)
        decision_context = contract.decision_context or {}
        risk_hint = contract.risk_hint or {}

        reasons: List[str] = []
        score = 0

        if not decision_context.get("decision_id") and not decision_context.get("queue_id"):
            score += 18
            reasons.append("missing_decision_context")
        if not str(contract.token or "").strip():
            score += 12
            reasons.append("missing_capability_token")

        principal = str(contract.principal or "").strip()
        if not principal:
            score += 22
            reasons.append("missing_principal")
        elif not (
            principal.startswith("operator:")
            or principal.startswith("service:")
            or principal.startswith("agent:")
        ):
            score += 10
            reasons.append("unfamiliar_principal_prefix")

        capability = str(contract.capability or "").lower()
        if any(marker in capability for marker in ("kill", "block", "deploy", "quarantine", "forensics")):
            score += 8
            reasons.append("high_impact_capability")

        tempo_key = f"{principal}:{sector_from}->{sector_to}:{capability}"
        tempo = self._tempo_score(tempo_key)
        score += int(tempo["tempo_score"])
        if tempo["tempo_score"]:
            reasons.append(str(tempo["tempo_reason"]))

        decoy_hit = self._is_decoy_target(str(contract.target or ""), risk_hint)
        if decoy_hit:
            score += 45
            reasons.append("decoy_interaction_detected")

        score += int(risk_hint.get("vns_score_boost") or 0)
        score = max(0, min(int(score), 100))

        beacon_state = self._beacon_state(score)
        beacon = self._update_sector_beacon(
            sector=sector_to,
            state=beacon_state,
            score=score,
            reason="pre_observe",
        )
        observed = {
            "phase": "pre",
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "sector_from": sector_from,
            "sector_to": sector_to,
            "anomaly_score": score,
            "decoy_hit": decoy_hit,
            "beacon": beacon,
            "reasons": reasons,
            **tempo,
        }
        self._recent_crossings.append(
            {
                "trace_id": contract.trace_id,
                "principal": principal,
                "capability": contract.capability,
                "target": contract.target,
                "pre": observed,
            }
        )
        return observed

    def post_observe(
        self,
        contract: BoundaryCrossingContract,
        *,
        pre_observation: Optional[Dict[str, Any]],
        mcp_outcome: str,
        mcp_reason: Optional[str] = None,
        execution_status: Optional[str] = None,
    ) -> Dict[str, Any]:
        pre = pre_observation or {}
        score = int(pre.get("anomaly_score") or 0)
        reasons = list(pre.get("reasons") or [])
        outcome = str(mcp_outcome or "allowed").strip().lower()
        reason = str(mcp_reason or "")

        if outcome == "queued":
            score = max(score, 50)
            reasons.append("queued_for_governance")
        elif outcome in {"denied", "token-invalid"}:
            score = max(score, 65)
            reasons.append("crossing_denied")

        if str(execution_status or "").lower() in {"failed", "timeout"}:
            score = min(100, score + 12)
            reasons.append("execution_unstable")

        if str(pre.get("decoy_hit")).lower() == "true":
            score = max(score, 80)

        score = max(0, min(int(score), 100))
        beacon_state = self._beacon_state(score)
        beacon = self._update_sector_beacon(
            sector=contract.sector_to,
            state=beacon_state,
            score=score,
            reason=f"post_observe:{outcome}",
        )

        world_outcome = "allowed"
        if pre.get("decoy_hit"):
            world_outcome = "decoy-hit"
        elif outcome == "token-invalid":
            world_outcome = "token-invalid"
        elif outcome == "queued":
            world_outcome = "queued"
        elif outcome == "denied":
            world_outcome = "denied"
        elif score >= 70:
            world_outcome = "anomalous"
        if world_outcome not in CANONICAL_BOUNDARY_OUTCOMES:
            world_outcome = "allowed"

        observed = {
            "phase": "post",
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "anomaly_score": score,
            "beacon": beacon,
            "reasons": reasons,
            "mcp_outcome": outcome,
            "mcp_reason": reason,
            "execution_status": execution_status,
            "world_event_outcome": world_outcome,
        }
        self._recent_crossings.append(
            {
                "trace_id": contract.trace_id,
                "principal": contract.principal,
                "capability": contract.capability,
                "target": contract.target,
                "post": observed,
            }
        )
        return observed

    def get_boundary_status(self) -> Dict[str, Any]:
        return {
            "sectors": list(SECTOR_RECIPES.keys()),
            "recipes": SECTOR_RECIPES,
            "beacons": dict(self._sector_beacons),
            "recent_crossings": list(self._recent_crossings)[-20:],
        }


boundary_control = SectorBoundaryControl()


def build_boundary_contract(
    *,
    principal: str,
    sector_from: Optional[str],
    sector_to: Optional[str],
    capability: str,
    target: str,
    decision_context: Optional[Dict[str, Any]],
    token: Optional[str],
    risk_hint: Optional[Dict[str, Any]],
    trace_id: Optional[str],
) -> BoundaryCrossingContract:
    return BoundaryCrossingContract(
        principal=str(principal or ""),
        sector_from=str(sector_from or SECTOR_GOVERNANCE),
        sector_to=str(sector_to or SECTOR_TOOL_EXECUTION),
        capability=str(capability or ""),
        target=str(target or ""),
        decision_context=dict(decision_context or {}),
        token=str(token or ""),
        risk_hint=dict(risk_hint or {}),
        trace_id=str(trace_id or ""),
    )


def contract_to_dict(contract: BoundaryCrossingContract) -> Dict[str, Any]:
    return asdict(contract)
