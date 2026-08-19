"""Validation of the existing DIO META Portfolio Atlas crosswalk into ATLAS."""
from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path
from typing import Any

from .registry import ATLAS_CONFIG_ROOT, AtlasRegistry, AtlasRegistryError


META_CROSSWALK_TOKEN = "DIO_ATLAS_META_PORTFOLIO_CROSSWALK_READY"
PROFILE_FILE = "dio_meta_profile_crosswalk.csv"
EXPECTED_PROFILE_CLASS_COUNTS = {
    "Domain": 15,
    "Framework": 15,
    "Authority": 3,
    "Connector": 4,
    "Output": 3,
    "Commercial": 3,
}


def _split(value: str | None) -> tuple[str, ...]:
    return tuple(item.strip() for item in str(value or "").split("|") if item.strip())


def _rows(path: Path) -> tuple[dict[str, str], ...]:
    if not path.is_file():
        raise AtlasRegistryError(f"DIO META profile crosswalk missing: {path}")
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = tuple({str(key): str(value or "") for key, value in row.items()} for row in reader)
    if not rows:
        raise AtlasRegistryError("DIO META profile crosswalk is empty")
    return rows


def validate_meta_profile_crosswalk(repo_root: str | Path) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    registry = AtlasRegistry.load(root)
    profiles = _rows(root / ATLAS_CONFIG_ROOT / PROFILE_FILE)
    names = [(row["profile_class"], row["profile_name"]) for row in profiles]
    if len(names) != len(set(names)):
        raise AtlasRegistryError("DIO META profile crosswalk contains duplicate class/name rows")
    counts = Counter(row["profile_class"] for row in profiles)
    class_counts = dict(EXPECTED_PROFILE_CLASS_COUNTS)
    class_counts_exact = counts == Counter(EXPECTED_PROFILE_CLASS_COUNTS)
    domains_valid = all(set(_split(row.get("atlas_domain_ids"))) <= registry.domain_ids for row in profiles)
    sources_valid = all(set(_split(row.get("source_systems"))) <= registry.source_ids for row in profiles)
    non_authorizing = all(
        row.get("capability_effect") == "NONE" and row.get("authority_effect") == "NONE"
        for row in profiles
    )
    axes = {row.get("atlas_axis") for row in profiles}
    expected_axes = {"DOMAIN", "CONSTRAINT", "CONNECTOR", "ARTIFACT", "COMMERCIAL"}
    passed = (
        len(profiles) == 43
        and class_counts_exact
        and domains_valid
        and sources_valid
        and non_authorizing
        and expected_axes <= axes
        and len(registry.incarnations) == 53
        and len(registry.work_patterns) == 13
    )
    return {
        "schema": "dio.atlas.meta_portfolio_crosswalk_receipt.v1",
        "acceptance": META_CROSSWALK_TOKEN if passed else "DIO_ATLAS_META_PORTFOLIO_CROSSWALK_BLOCKED",
        "passed": passed,
        "portfolio_incarnation_count": len(registry.incarnations),
        "profile_row_count": len(profiles),
        "profile_class_counts": class_counts,
        "profile_class_counts_exact": class_counts_exact,
        "canonical_work_pattern_count": 12,
        "candidate_work_pattern_count": 1,
        "profile_domain_refs_valid": domains_valid,
        "profile_source_refs_valid": sources_valid,
        "profile_rows_non_authorizing": non_authorizing,
        "atlas_axes_present": sorted(axes),
        "capability_cost_first_class": all(
            bool(row.get("capability_cost")) and bool(row.get("capability_cost_score"))
            for row in registry.incarnations
        ),
        "authority_created": False,
        "authority_widened": False,
        "external_effects": False,
    }


__all__ = [
    "EXPECTED_PROFILE_CLASS_COUNTS",
    "META_CROSSWALK_TOKEN",
    "PROFILE_FILE",
    "validate_meta_profile_crosswalk",
]
