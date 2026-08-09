from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

try:
    from pydantic import BaseModel, Field
except Exception:
    class BaseModel:  # type: ignore
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

        def dict(self):
            return dict(self.__dict__)

        def model_dump(self, **kwargs):
            return self.dict()

    def Field(default=None, default_factory=None):  # type: ignore
        if default_factory is not None:
            return default_factory()
        return default


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class DeceptionMode(str, Enum):
    OBSERVE = "observe"
    FRICTION = "friction"
    DISINFORMATION = "disinformation"
    MIRROR_WORLD = "mirror_world"
    HONEYPOT = "honeypot"
    TRAP_SINK = "trap_sink"


class DeceptionRiskBand(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DeceptionConfidenceBand(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class DeceptionCase(BaseModel):
    deception_case_id: str
    subject_session_id: Optional[str] = None
    campaign_id: Optional[str] = None
    source_ip: Optional[str] = None
    path: Optional[str] = None
    trigger_reason: str
    triggering_signals: List[str] = Field(default_factory=list)
    deception_mode: DeceptionMode
    risk_band: DeceptionRiskBand
    confidence_band: DeceptionConfidenceBand
    safety_constraints: List[str] = Field(default_factory=list)
    allowed_output_classes: List[str] = Field(default_factory=list)
    termination_conditions: List[str] = Field(default_factory=list)
    evidence_refs: List[str] = Field(default_factory=list)
    audit_refs: List[str] = Field(default_factory=list)
    trusted_principal_blocked: bool = False
    status: str = "planned"
    created_at: str = Field(default_factory=_utc_now_iso)
    updated_at: str = Field(default_factory=_utc_now_iso)
    execution_notes: Dict[str, Any] = Field(default_factory=dict)


class DeceptionValidationResult(BaseModel):
    allowed: bool
    reasons: List[str] = Field(default_factory=list)
    collisions: List[str] = Field(default_factory=list)
    downgraded_mode: Optional[DeceptionMode] = None

