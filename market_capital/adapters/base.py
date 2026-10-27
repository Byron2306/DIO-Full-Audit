from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DiscoveryObservation:
    source_id: str
    entity_type: str
    source_record_id: str
    source_reference: str
    observed_at: str
    payload: dict[str, Any]
    assertion_class: str = "OBSERVED"

    def __post_init__(self) -> None:
        if not self.source_id.strip():
            raise ValueError("source_id is required")
        if self.entity_type not in {"ORGANISATION", "PERSON", "OPPORTUNITY", "RELATIONSHIP", "ASSERTION"}:
            raise ValueError(f"Unsupported discovery entity type: {self.entity_type}")
        if not self.source_reference.strip():
            raise ValueError("source_reference is required")


@dataclass(frozen=True)
class DiscoveryBatch:
    source_id: str
    observations: tuple[DiscoveryObservation, ...]
    next_cursor: str | None
    source_state: str

    def __post_init__(self) -> None:
        if any(observation.source_id != self.source_id for observation in self.observations):
            raise ValueError("DiscoveryBatch observations must all match source_id")


class SourceAdapter(ABC):
    @abstractmethod
    def discover(self, plan_slice: dict[str, Any]) -> DiscoveryBatch:
        """Return normalized public observations without mutating the census."""
        raise NotImplementedError
