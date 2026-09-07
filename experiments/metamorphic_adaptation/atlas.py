from __future__ import annotations

import copy
import hashlib
import hmac
import random
from typing import Any

from .contracts import canonical_json


class AtlasSelectionError(RuntimeError):
    """Raised when the frozen ATLAS transfer rules cannot be satisfied."""


def composition_fingerprint(capabilities: list[str]) -> str:
    normalised = sorted({str(item) for item in capabilities if str(item)})
    digest = hashlib.sha256(canonical_json(normalised).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def build_eligibility_pool(
    tasks: list[dict[str, Any]],
    frozen_compositions: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    named_fingerprints = {
        composition_fingerprint(list(row.get("capabilities") or []))
        for row in frozen_compositions
    }

    eligible: list[dict[str, Any]] = []
    excluded: list[dict[str, str]] = []

    for raw in tasks:
        task = copy.deepcopy(raw)
        task_id = str(task.get("id") or "")
        capabilities = sorted({str(item) for item in task.get("required_capabilities") or [] if str(item)})

        reason: str | None = None
        if bool(task.get("dedicated_runner")):
            reason = "dedicated_runner"
        elif bool(task.get("dedicated_template")):
            reason = "dedicated_template"
        elif len(capabilities) < 2:
            reason = "fewer_than_two_capabilities"
        elif bool(task.get("adaptation_overlap")):
            reason = "adaptation_overlap"
        elif bool(task.get("requires_external_effects")):
            reason = "external_effect_required"
        elif not bool(task.get("scorable_artifact")):
            reason = "unscorable_artifact"
        elif not bool(task.get("source_inputs_replayable")):
            reason = "unreplayable_inputs"

        if reason is not None:
            excluded.append({"id": task_id, "reason": reason})
            continue

        fingerprint = composition_fingerprint(capabilities)
        task["required_capabilities"] = capabilities
        task["composition_fingerprint"] = fingerprint
        task["novel_composition"] = fingerprint not in named_fingerprints
        eligible.append(task)

    eligible.sort(key=lambda row: str(row.get("id") or ""))
    return eligible, excluded


def commit_seed(seed: bytes) -> str:
    if not isinstance(seed, (bytes, bytearray)) or not seed:
        raise AtlasSelectionError("selection seed must be non-empty bytes")
    return f"sha256:{hashlib.sha256(bytes(seed)).hexdigest()}"


def verify_seed(seed: bytes, commitment: str) -> bool:
    try:
        rendered = commit_seed(seed)
    except AtlasSelectionError:
        return False
    return hmac.compare_digest(rendered, str(commitment))


def select_tasks(pool: list[dict[str, Any]], seed: bytes, count: int = 3) -> dict[str, Any]:
    if count <= 0:
        raise AtlasSelectionError("selection count must be positive")
    if len(pool) < count:
        raise AtlasSelectionError(f"frozen eligibility pool must contain at least {count} tasks")
    if not any(bool(row.get("novel_composition")) for row in pool):
        raise AtlasSelectionError("frozen eligibility pool contains no novel composition candidate")

    frozen = sorted((copy.deepcopy(row) for row in pool), key=lambda row: str(row.get("id") or ""))
    frozen_ids = [str(row.get("id") or "") for row in frozen]
    if len(frozen_ids) != len(set(frozen_ids)) or any(not task_id for task_id in frozen_ids):
        raise AtlasSelectionError("frozen eligibility pool must contain unique non-empty task ids")

    seed_bytes = bytes(seed)
    seed_int = int.from_bytes(hashlib.sha256(seed_bytes).digest(), "big")
    rng = random.Random(seed_int)
    shuffled = list(frozen)
    rng.shuffle(shuffled)

    selected: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    for row in shuffled:
        if len(selected) >= count:
            break
        slots_left = count - len(selected)
        already_has_novel = any(bool(item.get("novel_composition")) for item in selected)
        if slots_left == 1 and not already_has_novel and not bool(row.get("novel_composition")):
            skipped.append({
                "id": str(row.get("id") or ""),
                "reason": "novelty_requirement_for_final_slot",
            })
            continue
        selected.append(copy.deepcopy(row))

    if len(selected) != count:
        raise AtlasSelectionError("deterministic traversal could not satisfy the declared selection count")
    if not any(bool(row.get("novel_composition")) for row in selected):
        raise AtlasSelectionError("deterministic selection failed the predeclared novel-composition requirement")

    return {
        "schema": "dio.metamorphic_adaptation.atlas_selection.v1",
        "seed_commitment": commit_seed(seed_bytes),
        "revealed_seed_hex": seed_bytes.hex(),
        "frozen_pool_order": frozen_ids,
        "shuffle_order": [str(row.get("id") or "") for row in shuffled],
        "selected": selected,
        "selected_ids": [str(row.get("id") or "") for row in selected],
        "skipped": skipped,
        "novelty_rule": "at_least_one_selected_task_must_have_novel_composition",
        "selection_replaced": False,
    }
