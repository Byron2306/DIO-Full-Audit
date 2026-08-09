#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MATRIX = ROOT / "deliverables" / "exam_source_catalogue_fet_2024_november" / "exam_source_matrix.json"
DEFAULT_OUT = ROOT / "deliverables" / "exam_source_catalogue_fet_2024_november"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def classify_contract(types: Counter[str], image_count: int) -> list[str]:
    ordered = [name for name, count in types.most_common() if count > 0]
    if image_count >= 100 and not ordered:
        ordered.append("image_rendered_or_scanned_pages")
    if image_count >= 100 and "image_rendered_or_scanned_pages" not in ordered:
        ordered.append("image_rendered_or_scanned_pages")
    return ordered


def summarize(matrix: dict[str, Any]) -> dict[str, Any]:
    subjects: dict[str, Any] = {}
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for paper in matrix.get("papers") or []:
        grouped[str(paper.get("subject") or "Unknown")].append(paper)

    for subject, papers in sorted(grouped.items()):
        type_counts: Counter[str] = Counter()
        method_counts: Counter[str] = Counter()
        examples: dict[str, list[dict[str, Any]]] = defaultdict(list)
        image_count = 0
        object_count = 0
        for paper in papers:
            type_counts.update(paper.get("unique_source_object_type_counts") or {})
            method_counts.update([paper.get("text_extraction_method") or "unknown"])
            image_count += int((paper.get("embedded_image_inventory") or {}).get("count") or 0)
            object_count += int(paper.get("unique_source_object_count") or 0)
            for item in paper.get("source_objects") or []:
                for source_type in item.get("source_types") or []:
                    if len(examples[source_type]) >= 3:
                        continue
                    examples[source_type].append(
                        {
                            "paper": paper.get("title"),
                            "page": (item.get("pages") or [None])[0],
                            "snippet": (item.get("snippets") or [""])[0],
                        }
                    )
        subjects[subject] = {
            "paper_count": len(papers),
            "papers": [
                {
                    "title": paper.get("title"),
                    "paper": paper.get("paper"),
                    "path": paper.get("path"),
                    "source_url": paper.get("source_url"),
                    "pdf_url": paper.get("pdf_url"),
                    "text_extraction_method": paper.get("text_extraction_method"),
                    "unique_source_object_count": paper.get("unique_source_object_count"),
                    "embedded_image_count": (paper.get("embedded_image_inventory") or {}).get("count"),
                    "source_types": paper.get("unique_source_object_type_counts"),
                }
                for paper in papers
            ],
            "unique_source_object_count": object_count,
            "embedded_image_count": image_count,
            "text_extraction_methods": dict(method_counts),
            "source_type_counts": dict(type_counts),
            "observed_contract": classify_contract(type_counts, image_count),
            "examples": dict(examples),
        }
    return {
        "schema": "knowedge.homs_exam_source_catalogue.v1",
        "generated_at": utc_now(),
        "matrix": matrix.get("manifest") or "",
        "paper_count": matrix.get("paper_count"),
        "subject_count": len(subjects),
        "subjects": subjects,
    }


def write_markdown(path: Path, catalogue: dict[str, Any]) -> None:
    lines = [
        "# FET Exam Source Catalogue",
        "",
        f"Generated: {catalogue['generated_at']}",
        f"Subjects: {catalogue['subject_count']}",
        f"Papers: {catalogue['paper_count']}",
        "",
        "This catalogue records what appears in actual DBE question papers. It is not a generated visual pack.",
        "",
        "## Subject Contracts",
        "",
    ]
    for subject, row in catalogue["subjects"].items():
        lines.append(f"### {subject}")
        lines.append(f"- Papers reviewed: {row['paper_count']}")
        lines.append(f"- Unique source/stimulus objects detected: {row['unique_source_object_count']}")
        lines.append(f"- Embedded image objects detected: {row['embedded_image_count']}")
        lines.append(f"- Text extraction: {', '.join(f'{k}={v}' for k, v in row['text_extraction_methods'].items())}")
        contract = ", ".join(row["observed_contract"]) or "none detected"
        lines.append(f"- Observed contract: {contract}")
        lines.append("- Source type counts: " + (", ".join(f"{k}={v}" for k, v in sorted(row["source_type_counts"].items())) or "none"))
        lines.append("- Papers:")
        for paper in row["papers"]:
            lines.append(
                f"  - {paper['title']}: objects={paper['unique_source_object_count']}, "
                f"images={paper['embedded_image_count']}, extraction={paper['text_extraction_method']}"
            )
        top_types = row["observed_contract"][:4]
        if top_types:
            lines.append("- Example hits:")
            for source_type in top_types:
                for example in (row["examples"].get(source_type) or [])[:1]:
                    snippet = " ".join(str(example.get("snippet") or "").split())[:220]
                    lines.append(f"  - {source_type}: {example.get('paper')} p.{example.get('page')} - {snippet}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a compact subject-level catalogue from an exam source matrix.")
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    matrix = json.loads(args.matrix.read_text(encoding="utf-8"))
    catalogue = summarize(matrix)
    args.out.mkdir(parents=True, exist_ok=True)
    json_path = args.out / "FET_EXAM_SOURCE_CATALOGUE.json"
    md_path = args.out / "FET_EXAM_SOURCE_CATALOGUE.md"
    json_path.write_text(json.dumps(catalogue, indent=2), encoding="utf-8")
    write_markdown(md_path, catalogue)
    print(json_path)
    print(md_path)


if __name__ == "__main__":
    main()
