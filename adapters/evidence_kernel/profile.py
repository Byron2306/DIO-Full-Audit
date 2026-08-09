from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jsonschema


ROOT = Path(__file__).resolve().parents[2]
PROFILE_SCHEMA = ROOT / "schemas" / "performance_profile.schema.json"


@dataclass(frozen=True)
class EvidenceConfidence:
    retrieval: float
    relevance: float
    provenance: float
    sufficiency: float

    @property
    def overall(self) -> float:
        """Use the weakest link; confidence must not hide a material weakness."""
        return round(min(self.retrieval, self.relevance, self.provenance, self.sufficiency), 3)

    def to_dict(self) -> dict[str, float]:
        return {
            "retrieval": round(self.retrieval, 3),
            "relevance": round(self.relevance, 3),
            "provenance": round(self.provenance, 3),
            "sufficiency": round(self.sufficiency, 3),
            "overall": self.overall,
        }


@dataclass(frozen=True)
class InstitutionalProfile:
    path: Path
    data: dict[str, Any]

    @property
    def profile_id(self) -> str:
        return str(self.data["profile_id"])

    @property
    def domain_map(self) -> dict[str, dict[str, Any]]:
        return {str(item["code"]): item for item in self.data["domains"]}

    @property
    def thresholds(self) -> dict[str, float]:
        return {
            key: float(value)
            for key, value in self.data["confidence_policy"]["acceptance_thresholds"].items()
        }

    @property
    def strong_cues(self) -> tuple[str, ...]:
        return tuple(str(value).lower() for value in self.data["evidence_policy"]["strong_source_cues"])

    @property
    def weak_cues(self) -> tuple[str, ...]:
        return tuple(str(value).lower() for value in self.data["evidence_policy"]["weak_source_cues"])

    @property
    def stopwords(self) -> set[str]:
        return {str(value).lower() for value in self.data["mapping_policy"]["stopwords"]}


def load_profile(path: Path) -> InstitutionalProfile:
    resolved = path.expanduser().resolve()
    data = json.loads(resolved.read_text(encoding="utf-8"))
    schema = json.loads(PROFILE_SCHEMA.read_text(encoding="utf-8"))
    jsonschema.validate(data, schema)
    return InstitutionalProfile(path=resolved, data=data)
