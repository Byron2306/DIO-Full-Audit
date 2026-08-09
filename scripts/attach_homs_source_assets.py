#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RAW_DEFAULT_BANK = ROOT / "deliverables" / "homs_core_source_bank" / "HOMS_CORE_SOURCE_BANK.json"
CURATED_DEFAULT_BANK = ROOT / "deliverables" / "homs_core_source_bank_curated" / "HOMS_CORE_SOURCE_BANK_CURATED.json"
DEFAULT_BANK = CURATED_DEFAULT_BANK if CURATED_DEFAULT_BANK.exists() else RAW_DEFAULT_BANK

SUBJECT_ALIASES = {
    "afrikaans": "afrikaans_language",
    "afrikaans_first_additional_language": "afrikaans_language",
    "afrikaans_home_language": "afrikaans_language",
    "economics": "economics",
    "english": "english_language",
    "english_first_additional_language": "english_language",
    "english_home_language": "english_language",
    "geography": "geography",
    "history": "history",
    "life_orientation": "life_orientation",
    "life_science": "life_sciences",
    "life_sciences": "life_sciences",
    "mathematics": "mathematics",
    "physical_science": "physical_sciences",
    "physical_sciences": "physical_sciences",
}

VISUAL_KIND_TO_SOURCE_TYPES = {
    "axis_diagram": ["diagram_or_model"],
    "cartoon": ["cartoon"],
    "case_facts_and_decision_table": ["text_extract", "data_table"],
    "data_table": ["data_table"],
    "diagram": ["diagram_or_model"],
    "graph": ["graph_or_chart"],
    "graph_or_chart": ["graph_or_chart"],
    "image": ["photograph_or_image"],
    "investigation_sheet": ["data_table", "diagram_or_model"],
    "map": ["map_extract"],
    "photograph": ["photograph_or_image"],
    "source_based": ["text_extract", "photograph_or_image", "cartoon"],
    "synoptic_weather_map": ["synoptic_weather_map"],
    "text": ["text_extract"],
    "topographic_map": ["topographic_map_and_orthophoto"],
}

SUBJECT_DEFAULT_SOURCE_TYPES = {
    "economics": ["text_extract", "graph_or_chart", "data_table", "cartoon"],
    "english_language": ["text_extract", "cartoon", "data_table", "photograph_or_image"],
    "geography": ["map_extract", "synoptic_weather_map", "data_table", "graph_or_chart", "photograph_or_image"],
    "history": ["text_extract", "photograph_or_image", "cartoon", "data_table"],
    "life_sciences": ["data_table", "diagram_or_model", "graph_or_chart", "text_extract"],
    "mathematics": ["diagram_or_model", "graph_or_chart", "data_table"],
    "physical_sciences": ["diagram_or_model", "graph_or_chart", "data_table"],
}

SOURCE_PRIORITY = [
    "topographic_map_and_orthophoto",
    "synoptic_weather_map",
    "map_extract",
    "diagram_or_model",
    "graph_or_chart",
    "data_table",
    "text_extract",
    "cartoon",
    "photograph_or_image",
    "unclassified_stimulus",
    "image_rendered_or_scanned_pages",
]

QUESTION_OR_INSTRUCTION_PATTERNS = [
    r"\bsection\s+[ab]\s+consists\b",
    r"\banswer\s+(all|three|two|one)\s+questions\b",
    r"\bquestion\s+\d+\s*:",
    r"\bstudy\s+sources?\s+\d*[a-z]?",
    r"\bread\s+source\s+\d*[a-z]?",
    r"\brefer\s+to\s+source\s+\d*[a-z]?",
    r"\banswer\s+the\s+questions?\s+that\s+follow\b",
    r"\bsource\s+material\s+that\s+is\s+required\b",
    r"\(\s*1\s*x\s*\d+\s*\)\s*\(\s*\d+\s*\)",
    r"\b\d+\.\d+\.\d+\b",
]


def source_quality_warnings(asset: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    snippet = re.sub(r"\s+", " ", str(asset.get("snippet") or "")).strip().lower()
    quality_flags = {str(flag) for flag in asset.get("quality_flags") or []}
    curation = asset.get("curation") or {}
    curation_flags = {str(flag) for flag in curation.get("curation_flags") or []}
    object_flags = {str(flag) for flag in curation.get("object_candidate_flags") or []}
    all_flags = quality_flags | curation_flags | object_flags

    if str(asset.get("release_gate") or "").lower().startswith("blocked"):
        warnings.append("release_gate_blocked")
    if "release_blocked_auto_crop_needs_human_review" in all_flags:
        warnings.append("auto_crop_needs_human_review")
    if "release_blocked_object_crop_needs_human_review" in all_flags:
        warnings.append("object_crop_needs_human_review")
    if "page_level_source_not_object_crop" in all_flags:
        warnings.append("page_level_source_not_object_crop")
    if "object_id_source_type_mismatch" in all_flags:
        warnings.append("object_id_source_type_mismatch")
    if len(snippet) < 80:
        warnings.append("weak_or_missing_snippet")
    if any(re.search(pattern, snippet, flags=re.I) for pattern in QUESTION_OR_INSTRUCTION_PATTERNS):
        warnings.append("question_or_instruction_snippet")
    if len(re.findall(r"\(\s*\d+\s*\)", snippet)) >= 2:
        warnings.append("mark_allocation_snippet")
    return dedupe(warnings)


def source_asset_is_usable(asset: dict[str, Any]) -> bool:
    return not source_quality_warnings(asset)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").lower()).strip("_") or "item"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def canonical_subject(pack: dict[str, Any], explicit_subject: str | None) -> str:
    if explicit_subject:
        return SUBJECT_ALIASES.get(slug(explicit_subject), slug(explicit_subject))
    profile_id = str(pack.get("canonical_profile_id") or "")
    if profile_id.startswith("fet."):
        return SUBJECT_ALIASES.get(slug(profile_id.split(".", 1)[1]), slug(profile_id.split(".", 1)[1]))
    return SUBJECT_ALIASES.get(slug(str(pack.get("subject") or "")), slug(str(pack.get("subject") or "")))


def dedupe(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def requested_source_types(pack: dict[str, Any], subject_id: str, explicit_types: str | None) -> list[str]:
    if explicit_types:
        return dedupe([slug(item) for item in explicit_types.split(",")])

    blueprint = pack.get("visual_blueprint") or {}
    contract = blueprint.get("source_type_contract") or {}
    requested = [slug(item) for item in contract.get("observed_contract") or contract.get("source_types") or []]
    for visual in blueprint.get("required_visuals") or []:
        visual_kind = slug(str(visual.get("visual_kind") or visual.get("id") or ""))
        requested.extend(VISUAL_KIND_TO_SOURCE_TYPES.get(visual_kind, []))

    requested.extend(SUBJECT_DEFAULT_SOURCE_TYPES.get(subject_id, []))
    return dedupe([item for item in requested if item != "image_rendered_or_scanned_pages"])


def priority_key(asset: dict[str, Any], requested_types: list[str]) -> tuple[int, int, str, int]:
    source_type = str(asset.get("source_type") or "")
    requested_rank = requested_types.index(source_type) if source_type in requested_types else 999
    source_rank = SOURCE_PRIORITY.index(source_type) if source_type in SOURCE_PRIORITY else 999
    return (requested_rank, source_rank, str(asset.get("paper") or ""), int(asset.get("page") or 0))


def select_assets(bank: dict[str, Any], subject_id: str, source_types: list[str], limit: int, allow_fallback: bool) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
    rejected: list[dict[str, Any]] = []
    for asset in bank.get("assets") or []:
        if asset.get("subject_id") != subject_id or asset.get("source_type") not in source_types:
            continue
        warnings = source_quality_warnings(asset)
        if warnings:
            rejected.append(
                {
                    "source_type": asset.get("source_type"),
                    "paper": asset.get("paper"),
                    "page": asset.get("page"),
                    "object_id": asset.get("object_id"),
                    "snippet": asset.get("snippet"),
                    "rejection_reasons": warnings,
                }
            )
            continue
        by_type[str(asset.get("source_type"))].append(asset)

    selected = []
    for source_type in source_types:
        assets = sorted(by_type.get(source_type, []), key=lambda asset: priority_key(asset, source_types))
        if assets:
            selected.append(assets[0])
        if len(selected) >= limit:
            return selected, rejected

    if allow_fallback and len(selected) < limit:
        fallback = [
            asset
            for asset in bank.get("assets") or []
            if asset.get("subject_id") == subject_id and asset not in selected
            and source_asset_is_usable(asset)
        ]
        for asset in sorted(fallback, key=lambda item: priority_key(item, source_types)):
            selected.append(asset)
            if len(selected) >= limit:
                break
    return selected, rejected


def to_pack_source_asset(asset: dict[str, Any], index: int) -> dict[str, Any]:
    title = str(asset.get("source_type") or "official source").replace("_", " ").title()
    return {
        "id": f"source_{index:02d}_{slug(asset.get('source_type'))}",
        "title": f"Official-paper exemplar: {title}",
        "source_type": asset.get("source_type"),
        "source_types": asset.get("source_types"),
        "paper": asset.get("paper"),
        "page": asset.get("page"),
        "object_id": asset.get("object_id"),
        "snippet": asset.get("snippet"),
        "bank_png": asset.get("bank_png"),
        "curated_png": asset.get("curated_png"),
        "object_candidate_png": asset.get("object_candidate_png"),
        "preferred_png": asset.get("preferred_png") or asset.get("curated_png") or asset.get("bank_png"),
        "asset_status": asset.get("asset_status"),
        "quality_flags": asset.get("quality_flags") or [],
        "source_quality_level": asset.get("source_quality_level"),
        "release_gate": asset.get("release_gate"),
        "curation": asset.get("curation"),
        "embedding_policy": asset.get("embedding_policy"),
    }


def attach_sources(job_dir: Path, bank_path: Path, explicit_subject: str | None, explicit_types: str | None, limit: int, dry_run: bool) -> dict[str, Any]:
    pack_path = job_dir / "assessment_pack.json"
    if not pack_path.exists():
        raise FileNotFoundError(f"assessment_pack.json not found in {job_dir}")
    pack = load_json(pack_path)
    bank = load_json(bank_path)
    subject_id = canonical_subject(pack, explicit_subject)
    source_types = requested_source_types(pack, subject_id, explicit_types)
    selected, rejected_assets = select_assets(bank, subject_id, source_types, limit, allow_fallback=explicit_types is None)
    source_assets = [to_pack_source_asset(asset, index) for index, asset in enumerate(selected, start=1)]
    selected_types = {str(asset.get("source_type") or "") for asset in selected}
    missing_requested = [source_type for source_type in source_types[:limit] if source_type not in selected_types]

    receipt = {
        "schema": "knowedge.homs_source_attachment_receipt.v1",
        "created_at": utc_now(),
        "status": "dry_run" if dry_run else "attached",
        "job_dir": str(job_dir),
        "bank": str(bank_path),
        "subject_id": subject_id,
        "requested_source_types": source_types,
        "attached_count": len(source_assets),
        "missing_requested_source_types": missing_requested,
        "source_assets": source_assets,
        "rejected_asset_count": len(rejected_assets),
        "rejected_assets": rejected_assets[:50],
        "missing_source_bank": not bool(source_assets),
        "release_gate": "blocked_no_usable_sources" if not source_assets else "attached_usable_sources",
        "educator_approval_required": True,
    }

    if not dry_run:
        pack["source_assets"] = source_assets
        pack.setdefault("source_embedding", {})
        pack["source_embedding"].update(
            {
                "schema": "knowedge.homs_source_embedding.v1",
                "attached_at": receipt["created_at"],
                "source_bank": str(bank_path.relative_to(ROOT)) if bank_path.is_relative_to(ROOT) else str(bank_path),
                "subject_id": subject_id,
                "requested_source_types": source_types,
                "asset_count": len(source_assets),
                "policy": "Official-paper exemplars are source material only; crop/readability/copyright review and educator approval remain mandatory before client delivery.",
            }
        )
        write_json(pack_path, pack)
        write_json(job_dir / "HOMS_SOURCE_ATTACHMENT_RECEIPT.json", receipt)

    return receipt


def job_dirs_from_path(path: Path) -> list[Path]:
    if (path / "assessment_pack.json").exists():
        return [path]
    return sorted(p for p in path.iterdir() if p.is_dir() and (p / "assessment_pack.json").exists())


def main() -> int:
    parser = argparse.ArgumentParser(description="Attach official-paper source bank assets to HOMS assessment packs.")
    parser.add_argument("path", help="Assessment job folder or run folder containing assessment job folders.")
    parser.add_argument("--bank", default=str(DEFAULT_BANK))
    parser.add_argument("--subject", default=None)
    parser.add_argument("--source-types", default=None, help="Comma-separated source types, e.g. data_table,diagram_or_model,graph_or_chart")
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    bank_path = Path(args.bank).expanduser().resolve()
    jobs = job_dirs_from_path(Path(args.path).expanduser().resolve())
    receipts = [attach_sources(job, bank_path, args.subject, args.source_types, args.limit, args.dry_run) for job in jobs]
    print(json.dumps({"status": "completed", "jobs": len(receipts), "receipts": receipts}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
