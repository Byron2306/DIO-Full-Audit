from __future__ import annotations

import copy
from typing import Any

from twin import validate_twin

from .continuous import assess_continuous_assurance

WATCH_STATE_SCHEMA = "dio.continuous_assurance.watch_state.v1"


class ContinuousAssuranceWatcher:
    """Stateful event-driven assurance cursor over canonical Twin snapshots."""

    def __init__(self, baseline_twin: dict[str, Any]):
        validate_twin(baseline_twin)
        self._current_twin = copy.deepcopy(baseline_twin)
        self._receipts: list[dict[str, Any]] = []

    @property
    def current_twin(self) -> dict[str, Any]:
        return copy.deepcopy(self._current_twin)

    @property
    def receipts(self) -> list[dict[str, Any]]:
        return copy.deepcopy(self._receipts)

    def observe(self, next_twin: dict[str, Any]) -> dict[str, Any]:
        """Validate and assess the next snapshot, then advance only after success."""
        receipt = assess_continuous_assurance(self._current_twin, next_twin)
        self._receipts.append(copy.deepcopy(receipt))
        self._current_twin = copy.deepcopy(next_twin)
        return receipt

    def state(self) -> dict[str, Any]:
        return {
            "schema": WATCH_STATE_SCHEMA,
            "current_twin_id": self._current_twin["twin_id"],
            "current_twin_fingerprint": self._current_twin["fingerprint"],
            "assurance_receipt_ids": [row["assurance_receipt_id"] for row in self._receipts],
            "receipt_count": len(self._receipts),
            "authority": False,
            "execution": False,
        }
