#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PRIMARY_EXEMPLARS = ROOT / "deliverables" / "exam_source_catalogue_fet_2024_november" / "source_page_exemplars" / "SOURCE_PAGE_EXEMPLARS.json"
DEFAULT_GEOGRAPHY_EXEMPLARS = ROOT / "deliverables" / "exam_source_matrix" / "source_page_exemplars" / "SOURCE_PAGE_EXEMPLARS.json"
DEFAULT_OUT = ROOT / "deliverables" / "homs_core_source_bank"

CORE_SUBJECT_ALIASES = {
    "afrikaans_first_additional_language": "afrikaans_language",
    "afrikaans_fal": "afrikaans_language",
    "afrikaans_home_language": "afrikaans_language",
    "afrikaans_hl": "afrikaans_language",
    "afrikaans_sal": "afrikaans_language",
    "english_first_additional_language": "english_language",
    "english_home_language": "english_language",
    "physical_sciences_chemistry": "physical_sciences",
    "physical_sciences_physics": "physical_sciences",
    "life_science": "life_sciences",
}

CORE_SUBJECTS = {
    "afrikaans_language",
    "economics",
    "english_language",
    "geography",
    "history",
    "life_orientation",
    "life_sciences",
    "mathematics",
    "physical_sciences",
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

OBJECT_HINTS = {
    "cartoon": "cartoon",
    "diagram": "diagram_or_model",
    "extract": "text_extract",
    "figure": "photograph_or_image",
    "graph": "graph_or_chart",
    "image": "photograph_or_image",
    "map": "map_extract",
    "photograph": "photograph_or_image",
    "source": "text_extract",
    "table": "data_table",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").lower()).strip("_") or "item"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def paper_subject(paper: str) -> str:
    lower = paper.lower()
    if lower.startswith("afrikaans"):
        return "afrikaans_language"
    if lower.startswith("english"):
        return "english_language"
    if lower.startswith("life orientation"):
        return "life_orientation"
    cleaned = re.sub(r"\b(?:P|Paper)\s*[123]\b.*$", "", paper, flags=re.I).strip()
    cleaned = re.sub(r"\bNovember\b.*$", "", cleaned, flags=re.I).strip()
    cleaned = re.sub(r"\bMay June\b.*$", "", cleaned, flags=re.I).strip()
    subject = slug(cleaned)
    return CORE_SUBJECT_ALIASES.get(subject, subject)


def resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def source_rank(source_types: list[str]) -> tuple[int, str]:
    if not source_types:
        return (999, "unclassified_stimulus")
    primary = source_types[0]
    if primary in SOURCE_PRIORITY:
        return (SOURCE_PRIORITY.index(primary), primary)
    return (998, primary)


def is_usable_source_exemplar(item: dict[str, Any]) -> bool:
    object_id = str(item.get("object_id") or "").lower()
    snippet = str(item.get("snippet") or "").lower()
    if object_id.startswith("qpaper:"):
        return False
    instruction_false_positives = [
        "do not use graph paper",
        "write your answers",
        "answer all the questions",
        "instructions and information",
        "number the answers correctly",
    ]
    return not any(token in snippet for token in instruction_false_positives)


def source_quality_flags(item: dict[str, Any], primary_source_type: str) -> list[str]:
    flags = []
    object_id = str(item.get("object_id") or "").lower()
    hinted_types = {expected for token, expected in OBJECT_HINTS.items() if token in object_id}
    if hinted_types and primary_source_type not in hinted_types:
        flags.append("object_id_source_type_mismatch")
    snippet = str(item.get("snippet") or "").lower()
    if "draw a" in snippet and primary_source_type == "graph_or_chart":
        flags.append("question_asks_learner_to_draw_graph")
    if "not drawn to scale" in snippet and primary_source_type in {"diagram_or_model", "graph_or_chart"}:
        flags.append("not_drawn_to_scale")
    if item.get("source_types") and len(item.get("source_types") or []) > 1:
        flags.append("multi_source_page")
    return flags


def load_exemplars(paths: list[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        if not path.exists():
            continue
        manifest = load_json(path)
        for item in manifest.get("rendered") or []:
            if not is_usable_source_exemplar(item):
                continue
            subject_id = paper_subject(str(item.get("paper") or ""))
            if subject_id not in CORE_SUBJECTS:
                continue
            png = resolve_path(str(item.get("png") or ""))
            if not png.exists():
                continue
            source_types = list(item.get("source_types") or ["unclassified_stimulus"])
            _rank, primary_source_type = source_rank(source_types)
            rows.append(
                {
                    "subject_id": subject_id,
                    "source_type": primary_source_type,
                    "source_types": source_types,
                    "paper": item.get("paper"),
                    "paper_theme": item.get("paper_theme"),
                    "pdf": item.get("pdf"),
                    "page": item.get("page"),
                    "object_id": item.get("object_id"),
                    "snippet": item.get("snippet"),
                    "source_manifest": str(path.relative_to(ROOT)),
                    "source_png": str(png),
                    "quality_flags": source_quality_flags(item, primary_source_type),
                }
            )
    return rows


def build_bank(rows: list[dict[str, Any]], out_dir: Path, per_type_limit: int) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    selected: list[dict[str, Any]] = []
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(row["subject_id"], row["source_type"])].append(row)

    for (subject_id, source_type), items in sorted(grouped.items()):
        items = sorted(items, key=lambda item: (str(item.get("paper") or ""), int(item.get("page") or 0), str(item.get("object_id") or "")))
        for index, item in enumerate(items[:per_type_limit], start=1):
            subject_dir = out_dir / subject_id / source_type
            subject_dir.mkdir(parents=True, exist_ok=True)
            target = subject_dir / f"{index:02d}_{slug(item.get('paper'))}_p{int(item.get('page') or 0):02d}_{slug(item.get('object_id'))}.png"
            shutil.copy2(resolve_path(item["source_png"]), target)
            selected.append(
                {
                    **item,
                    "bank_png": str(target.relative_to(ROOT)),
                    "asset_status": "official_page_exemplar",
                    "quality_flags": item.get("quality_flags") or [],
                    "embedding_policy": "May be embedded as an official-paper source exemplar. Review copyright/licensing and crop/readability before client delivery.",
                }
            )

    by_subject = Counter(item["subject_id"] for item in selected)
    by_source_type = Counter(item["source_type"] for item in selected)
    missing_core = sorted(CORE_SUBJECTS - set(by_subject))
    return {
        "schema": "knowedge.homs_core_source_bank.v1",
        "created_at": utc_now(),
        "asset_count": len(selected),
        "subjects": dict(sorted(by_subject.items())),
        "source_types": dict(sorted(by_source_type.items())),
        "missing_core_subjects": missing_core,
        "assets": selected,
    }


def write_markdown(path: Path, bank: dict[str, Any]) -> None:
    lines = [
        "# HOMS Core Source Bank",
        "",
        "This bank normalizes extracted official-paper page exemplars for core FET subject routes.",
        "",
        f"- Assets: {bank['asset_count']}",
        "- Subjects: " + ", ".join(f"`{key}`={value}" for key, value in bank["subjects"].items()),
        "- Missing core subjects: " + (", ".join(f"`{item}`" for item in bank["missing_core_subjects"]) or "none"),
        "",
        "## Assets",
        "",
        "| Subject | Type | Paper | Page | Flags | Asset |",
        "|---|---|---|---:|---|---|",
    ]
    for asset in bank["assets"]:
        flags = ", ".join(f"`{flag}`" for flag in asset.get("quality_flags") or []) or "none"
        lines.append(
            f"| `{asset['subject_id']}` | `{asset['source_type']}` | {asset.get('paper') or ''} | {asset.get('page') or ''} | {flags} | `{asset['bank_png']}` |"
        )
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a normalized source bank for HOMS core FET subjects.")
    parser.add_argument("--primary-exemplars", default=str(DEFAULT_PRIMARY_EXEMPLARS))
    parser.add_argument("--geography-exemplars", default=str(DEFAULT_GEOGRAPHY_EXEMPLARS))
    parser.add_argument("--extra-exemplars", action="append", default=[], help="Additional SOURCE_PAGE_EXEMPLARS.json manifest to merge into the core bank.")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT))
    parser.add_argument("--per-type-limit", type=int, default=3)
    args = parser.parse_args()

    exemplar_paths = [
        Path(args.primary_exemplars).expanduser().resolve(),
        Path(args.geography_exemplars).expanduser().resolve(),
        *[Path(item).expanduser().resolve() for item in args.extra_exemplars],
    ]
    rows = load_exemplars(exemplar_paths)
    bank = build_bank(rows, Path(args.out_dir).expanduser().resolve(), args.per_type_limit)
    out_dir = Path(args.out_dir).expanduser().resolve()
    (out_dir / "HOMS_CORE_SOURCE_BANK.json").write_text(json.dumps(bank, indent=2), encoding="utf-8")
    write_markdown(out_dir / "HOMS_CORE_SOURCE_BANK.md", bank)
    print(json.dumps({"status": "completed", "out_dir": str(out_dir), "asset_count": bank["asset_count"], "subjects": bank["subjects"], "missing_core_subjects": bank["missing_core_subjects"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
