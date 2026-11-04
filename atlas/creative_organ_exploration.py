"""Candidate-only ATLAS projection for Sonoris and Pictora.

The domain sets are an explicit editorial crosswalk, not a lexical match or an
execution-grade capability signature. ATLAS knowledge cannot mint authority.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from atlas.registry import AtlasRegistry


ROOT = Path(__file__).resolve().parents[1]
CREATIVE_REGISTRY = ROOT / "config/creative_organs.json"
DOMAIN_REGISTRY = ROOT / "config/atlas/dio_atlas_universal_domain_registry.csv"

# Shared work: governed sound/visual assets for publication, communication,
# learning, media and offer exploration. Subject expertise and rights remain
# separate requirements in every domain.
SHARED = frozenset({
    "D501", "D503", "D707", "D708", "D710", "D901", "D902", "D903",
    "D904", "D905", "D906", "D1308", "D1408", "D1504", "D1515",
    "D1709", "D1710",
})
SONORIS_ONLY = frozenset({"D1406"})
PICTORA_ONLY = frozenset({"D403", "D502", "D716", "D1405", "D1715"})

ORGAN_WORK = {
    "sonoris": "compose, arrange or select a source-bound musical/audio asset for a governed artifact",
    "pictora": "create or refine a source-bound visual asset for a governed artifact",
}
ORGAN_GAPS = {
    "sonoris": ["genre-specific sonic review", "instrument/sample rights", "customer brief and revision proof"],
    "pictora": ["visual and factual review", "model and source-image rights", "customer brief and revision proof"],
}
DOMAIN_TASKS = {
    "D403": "produce reviewed product or storefront visual concepts",
    "D501": "prepare audio and visual assets for a source-bound publication",
    "D502": "prepare reviewed visual explainers for a sourced media story",
    "D503": "compose soundtrack cues and visual assets for a film, audio or broadcast brief",
    "D707": "produce governed ad sound and imagery from approved claims",
    "D708": "prepare campaign sound and visual communication assets",
    "D710": "prepare audio and visual training supports",
    "D716": "produce visual design concepts with source and model provenance",
    "D901": "explore age-appropriate learning sound and visuals under educator review",
    "D902": "prepare curriculum-aligned learning sound and visuals under educator review",
    "D903": "prepare vocational demonstration sound and visuals under instructor review",
    "D904": "prepare higher-education explainer sound and visuals under subject review",
    "D905": "prepare corporate-learning media under trainer review",
    "D906": "prepare instructional media aligned to a reviewed lesson design",
    "D1308": "build source-bound communication and media-study examples",
    "D1405": "explore visual-art concepts with provenance and artist review",
    "D1406": "explore music composition and performance arrangements",
    "D1408": "prepare reviewed soundscape and visual interpretation concepts",
    "D1504": "prototype sound and imagery for a held marketing experiment",
    "D1515": "prepare reviewed internal communication sound and visuals",
    "D1709": "attach reviewed creative assets to a controlled publication artifact",
    "D1710": "test candidate creative treatments in an offer experiment without claiming demand",
    "D1715": "explore inclusive visual treatments with separate accessibility review",
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def resolve_creative_organs(root: str | Path = ROOT) -> dict[str, Any]:
    root = Path(root).resolve()
    atlas = AtlasRegistry.load(root)
    creative_path = root / "config/creative_organs.json"
    creative = json.loads(creative_path.read_text(encoding="utf-8"))
    available = {row["id"] for row in creative.get("organs") or []}
    if not set(ORGAN_WORK).issubset(available):
        raise ValueError("Sonoris and Pictora must both be present in the creative organ registry")
    if any(any(name in f"{signature.capability_id} {signature.unit_id}".casefold() for name in ORGAN_WORK)
           for signature in atlas.signatures):
        raise ValueError("creative organ execution signatures now exist; review the candidate-only projection")

    by_organ = {"sonoris": SHARED | SONORIS_ONLY, "pictora": SHARED | PICTORA_ONLY}
    union = set().union(*by_organ.values())
    if union != DOMAIN_TASKS.keys():
        raise ValueError("ATLAS candidate domain task map is incomplete")
    rows = []
    for domain_id in sorted(union):
        domain = atlas.domain(domain_id)
        if domain["domain_type"] not in {"DOMAIN", "SUBDOMAIN"}:
            raise ValueError(f"candidate {domain_id} is not an ATLAS domain")
        organs = [name for name, ids in by_organ.items() if domain_id in ids]
        rows.append({
            "domain_id": domain_id,
            "domain_name": domain["domain_name"],
            "domain_family": domain["domain_family"],
            "organs": organs,
            "domain_task_hypothesis": DOMAIN_TASKS[domain_id],
            "work_hypothesis": {name: ORGAN_WORK[name] for name in organs},
            "required_gaps": sorted({gap for name in organs for gap in ORGAN_GAPS[name]}),
            "relation_state": "ANALOGICAL_CANDIDATE",
            "execution_corroborated_for_these_organs": False,
            "market_corroborated_for_these_organs": False,
            "authority_created": False,
        })
    return {
        "schema": "dio.atlas.creative_organ_exploration.v1",
        "method": "explicit_candidate_crosswalk_over_existing_atlas_domain_ids",
        "source_hashes": {
            "atlas_domains_sha256": _sha(root / "config/atlas/dio_atlas_universal_domain_registry.csv"),
            "creative_organs_sha256": _sha(creative_path),
        },
        "atlas_domain_nodes_total": len(atlas.domains),
        "candidate_domain_counts": {"sonoris": len(by_organ["sonoris"]),
                                    "pictora": len(by_organ["pictora"]),
                                    "shared": len(SHARED), "unique_union": len(union)},
        "execution_grade_signature_count_for_these_organs": 0,
        "commercial_validation": "UNPROVED",
        "release_authorized": False,
        "domains": rows,
    }


def creative_organ_projection(organ: str, root: str | Path = ROOT) -> dict[str, Any]:
    """Return one organ's bounded ATLAS candidate domains for its local dashboard."""
    name = str(organ).strip().lower()
    if name not in ORGAN_WORK:
        raise ValueError(f"unsupported creative organ: {name}")
    projection = resolve_creative_organs(root)
    domains = [row for row in projection["domains"] if name in row["organs"]]
    unique = [row for row in domains if row["organs"] == [name]]
    shared = [row for row in domains if len(row["organs"]) > 1]
    return {
        "schema": "dio.atlas.creative_organ_dashboard_projection.v1",
        "organ": name,
        "candidate_domain_count": len(domains),
        "shared_domain_count": len(shared),
        "unique_domain_count": len(unique),
        "global_candidate_domain_union": projection["candidate_domain_counts"]["unique_union"],
        "execution_grade_signature_count": projection["execution_grade_signature_count_for_these_organs"],
        "relation_state": "ANALOGICAL_CANDIDATE",
        "authority_created": False,
        "release_authorized": False,
        "source_hashes": projection["source_hashes"],
        "domains": domains,
    }
