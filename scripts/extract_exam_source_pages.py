#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MATRIX = ROOT / "deliverables" / "exam_source_matrix" / "exam_source_matrix.json"
DEFAULT_OUT = ROOT / "deliverables" / "exam_source_matrix" / "source_page_exemplars"


PRIORITY_TYPES = {
    "topographic_map_and_orthophoto",
    "synoptic_weather_map",
    "map_extract",
    "graph_or_chart",
    "data_table",
    "photograph_or_image",
    "diagram_or_model",
    "text_extract",
    "cartoon",
}


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").lower()).strip("_") or "source"


def render_page(pdf_path: Path, page: int, out_prefix: Path, dpi: int) -> Path:
    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["pdftoppm", "-f", str(page), "-l", str(page), "-r", str(dpi), "-png", str(pdf_path), str(out_prefix)],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"pdftoppm failed for {pdf_path} page {page}")
    rendered = out_prefix.parent / f"{out_prefix.name}-{page}.png"
    if not rendered.exists():
        candidates = sorted(out_prefix.parent.glob(f"{out_prefix.name}-*.png"))
        if candidates:
            rendered = candidates[-1]
    return rendered


def select_objects(paper: dict[str, Any], per_type_limit: int) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    for item in paper.get("source_objects") or []:
        types = [source_type for source_type in item.get("source_types") or [] if source_type in PRIORITY_TYPES]
        if not types:
            continue
        primary = types[0]
        if counts.get(primary, 0) >= per_type_limit:
            continue
        selected.append({**item, "primary_source_type": primary})
        counts[primary] = counts.get(primary, 0) + 1
    return selected


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render actual old-paper pages containing detected source/stimulus objects.")
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--per-type-limit", type=int, default=1)
    parser.add_argument("--paper-limit", type=int, default=0)
    parser.add_argument("--dpi", type=int, default=140)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    matrix = json.loads(args.matrix.read_text(encoding="utf-8"))
    rendered: list[dict[str, Any]] = []
    papers = matrix.get("papers") or []
    if args.paper_limit:
        papers = papers[: args.paper_limit]
    for paper in papers:
        pdf_path = Path(paper["path"])
        paper_dir = args.out / slug(paper["title"])
        for item in select_objects(paper, args.per_type_limit):
            page = int((item.get("pages") or [1])[0])
            out_prefix = paper_dir / f"p{page:02d}_{slug(item['primary_source_type'])}_{slug(item['object_id'])}"
            png_path = render_page(pdf_path, page, out_prefix, args.dpi)
            rendered.append(
                {
                    "paper": paper["title"],
                    "paper_theme": paper["paper_theme"],
                    "pdf": paper["path"],
                    "page": page,
                    "source_types": item.get("source_types") or [],
                    "object_id": item.get("object_id"),
                    "snippet": item.get("snippets", [""])[0],
                    "png": str(png_path),
                }
            )
    args.out.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema": "knowedge.homs_exam_source_page_exemplars.v1",
        "matrix": str(args.matrix),
        "rendered_count": len(rendered),
        "rendered": rendered,
    }
    args.out.joinpath("SOURCE_PAGE_EXEMPLARS.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    lines = ["# Source Page Exemplars", "", f"Rendered pages: {len(rendered)}", ""]
    for item in rendered:
        lines.append(f"- {item['paper']} p.{item['page']} {', '.join(item['source_types'])}: {item['png']}")
    args.out.joinpath("SOURCE_PAGE_EXEMPLARS.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Rendered {len(rendered)} source page exemplar(s)")
    print(args.out / "SOURCE_PAGE_EXEMPLARS.json")


if __name__ == "__main__":
    main()
