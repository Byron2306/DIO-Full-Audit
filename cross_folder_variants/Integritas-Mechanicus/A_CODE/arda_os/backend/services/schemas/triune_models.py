from typing import Any, Dict, List, Optional
from datetime import datetime
try:
    # pydantic v1/v2 compatibility: tests use BaseModel elsewhere
    from pydantic import BaseModel
except Exception:
    # fallback minimal dataclass-like model if pydantic missing in lightweight envs
    class BaseModel:  # type: ignore
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)


class AIComponent(BaseModel):
    explanation: Optional[str] = None
    score_delta: Optional[float] = None
    details: Optional[Dict[str, Any]] = None


class RankedCandidate(BaseModel):
    candidate: str
    score: float
    components: Optional[Dict[str, Any]] = None


class TriuneAnalysis(BaseModel):
    id: str
    created: Optional[datetime] = None
    entities: Optional[List[str]] = []
    candidates: Optional[List[str]] = []
    ranked: Optional[List[RankedCandidate]] = []


class MetatronState(BaseModel):
    header: Dict[str, Any]
    narrative: Dict[str, Any]
    attack_path: Dict[str, Any]
    trust: Dict[str, Any]
    hotspots: List[Dict[str, Any]]
    actions: List[Dict[str, Any]]
    hypotheses: List[Dict[str, Any]]
    triune_analyses: Optional[List[TriuneAnalysis]] = []
    timeline: List[Dict[str, Any]]
