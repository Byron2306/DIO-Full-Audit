from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from adapters.format_core.visual_material_registry import (
    MATERIAL_SCHEMA,
    REGISTRY_SCHEMA,
    content_hash,
    validate_visual_material,
    validate_visual_material_registry,
)


PACK_SCHEMA = "dio.format_core.visual_material_pack.v1"
PACK_READINESS_SCHEMA = "dio.format_core.visual_material_pack_readiness.v1"


class VisualMaterialPackError(RuntimeError):
    pass


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _norm(values: Any) -> set[str]:
    return {_clean(value).casefold() for value in values or [] if _clean(value)}


def load_visual_material_pack(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != PACK_SCHEMA:
        raise VisualMaterialPackError(f"pack schema must be {PACK_SCHEMA}")
    if not _clean(payload.get("pack_id")):
        raise VisualMaterialPackError("pack_id is required")
    if not _clean(payload.get("surface")):
        raise VisualMaterialPackError("surface is required")
    slots = list(payload.get("slots") or [])
    if not slots:
        raise VisualMaterialPackError("pack slots must be non-empty")
    seen: set[str] = set()
    for index, slot in enumerate(slots, 1):
        slot_id = _clean(slot.get("slot_id"))
        if not slot_id:
            raise VisualMaterialPackError(f"slot {index} requires slot_id")
        if slot_id in seen:
            raise VisualMaterialPackError(f"duplicate slot_id: {slot_id}")
        seen.add(slot_id)
        if not _clean(slot.get("semantic_visual_kind")):
            raise VisualMaterialPackError(f"slot {slot_id} requires semantic_visual_kind")
        if not list(slot.get("allowed_material_kinds") or []):
            raise VisualMaterialPackError(f"slot {slot_id} requires allowed_material_kinds")
    return payload


def _slot_candidate(slot: dict[str, Any], material: dict[str, Any], *, surface: str, root: Path | None) -> bool:
    validation = validate_visual_material(material, root=root)
    if not validation["selectable"]:
        return False
    if material.get("schema") != MATERIAL_SCHEMA:
        return False
    if surface not in set(material.get("surface_suitability") or []):
        return False
    if str(slot.get("semantic_visual_kind")) not in set(material.get("semantic_visual_kinds") or []):
        return False
    if str(material.get("material_kind")) not in set(slot.get("allowed_material_kinds") or []):
        return False

    material_subjects = _norm(material.get("subjects"))
    material_activities = _norm(material.get("activities"))
    material_mood = _norm(material.get("mood"))

    subject_any = _norm(slot.get("required_subject_any"))
    activity_any = _norm(slot.get("required_activity_any"))
    mood_any = _norm(slot.get("required_mood_any"))

    if subject_any and not (subject_any & material_subjects):
        return False
    if activity_any and not (activity_any & material_activities):
        return False
    if mood_any and not (mood_any & material_mood):
        return False
    return True


def evaluate_visual_material_pack(
    pack: dict[str, Any],
    registry: dict[str, Any],
    *,
    root: Path | None = None,
) -> dict[str, Any]:
    registry_validation = validate_visual_material_registry(registry, root=root)
    if registry.get("schema") != REGISTRY_SCHEMA or not registry_validation["passed"]:
        raise VisualMaterialPackError("registry is invalid for pack evaluation")

    surface = str(pack["surface"])
    materials = [dict(row) for row in registry.get("materials") or []]
    used_primary: set[str] = set()
    slot_rows: list[dict[str, Any]] = []

    for slot in pack.get("slots") or []:
        candidates = [
            material
            for material in materials
            if _slot_candidate(dict(slot), material, surface=surface, root=root)
        ]
        candidates.sort(key=lambda row: (str(row.get("material_kind")), str(row.get("material_id"))))
        secondary = bool(slot.get("secondary_material"))
        selected = None
        for candidate in candidates:
            material_id = str(candidate.get("material_id") or "")
            if secondary or material_id not in used_primary:
                selected = candidate
                break
        if selected is not None and not secondary:
            used_primary.add(str(selected.get("material_id") or ""))

        slot_rows.append(
            {
                "slot_id": slot.get("slot_id"),
                "semantic_visual_kind": slot.get("semantic_visual_kind"),
                "required": bool(slot.get("required", True)),
                "secondary_material": secondary,
                "candidate_count": len(candidates),
                "selected_material_id": selected.get("material_id") if selected else None,
                "selected_material_kind": selected.get("material_kind") if selected else None,
                "state": "PASS" if selected else "REFUSE",
            }
        )

    required_rows = [row for row in slot_rows if row["required"]]
    missing_required = [row["slot_id"] for row in required_rows if row["state"] != "PASS"]
    selected_primary = [row for row in slot_rows if row["selected_material_id"] and not row["secondary_material"]]
    selected_all = [row for row in slot_rows if row["selected_material_id"]]
    kind_counts = Counter(str(row["selected_material_kind"]) for row in selected_all)

    primary_curated = sum(
        row["selected_material_kind"] in {"curated_photo", "curated_illustration", "generated_editorial"}
        for row in selected_primary
    )
    native_count = sum(row["selected_material_kind"] == "native_renderer" for row in selected_primary)
    native_share = native_count / max(1, len(selected_primary))

    min_kinds = int(pack.get("minimum_distinct_material_kinds") or 1)
    min_curated = int(pack.get("minimum_curated_primary_materials") or 0)
    max_native_share = float(pack.get("maximum_native_renderer_share") if pack.get("maximum_native_renderer_share") is not None else 1.0)

    checks = {
        "all_required_slots_satisfied": not missing_required,
        "distinct_material_kind_floor": len(kind_counts) >= min_kinds,
        "curated_primary_floor": primary_curated >= min_curated,
        "native_renderer_share_ceiling": native_share <= max_native_share,
        "primary_materials_nonrepeating": len({row["selected_material_id"] for row in selected_primary}) == len(selected_primary),
        "remote_runtime_fetch_refused": pack.get("remote_runtime_fetch") == "REFUSE",
        "automatic_publication_refused": pack.get("automatic_publication") == "REFUSE",
    }
    state = "READY_NEEDS_YOU" if all(checks.values()) else "REFUSE"
    core = {
        "schema": PACK_READINESS_SCHEMA,
        "pack_id": pack.get("pack_id"),
        "pack_hash": content_hash(pack),
        "surface": surface,
        "state": state,
        "slot_count": len(slot_rows),
        "required_slot_count": len(required_rows),
        "required_slots_satisfied": len(required_rows) - len(missing_required),
        "missing_required_slots": missing_required,
        "slots": slot_rows,
        "selected_material_kind_counts": dict(sorted(kind_counts.items())),
        "distinct_selected_material_kind_count": len(kind_counts),
        "curated_primary_material_count": primary_curated,
        "native_primary_material_count": native_count,
        "native_primary_material_share": round(native_share, 4),
        "checks": checks,
        "commercial_validation": "UNPROVED",
        "human_visual_release": pack.get("human_visual_release") or "NEEDS_YOU",
        "automatic_publication": "REFUSE",
        "authority_created": False,
    }
    return {**core, "readiness_hash": content_hash(core)}


__all__ = [
    "PACK_READINESS_SCHEMA",
    "PACK_SCHEMA",
    "VisualMaterialPackError",
    "evaluate_visual_material_pack",
    "load_visual_material_pack",
]
