#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters.format_core.visual_composer import SCHEMA, write_visual_bundle


DEFAULT_OUT = ROOT / "deliverables" / "format_core_visual_composer" / "DIO-VISUAL-COMPOSER-GOLDEN-001"


def composition() -> dict:
    return {
        "schema": SCHEMA,
        "composition_id": "DIO-VISUAL-COMPOSER-GOLDEN-001",
        "title": "DIO Visual Composition",
        "profile_id": "site_editorial_dark",
        "canvas": {"width": 1280, "height": 720, "background": "$paper"},
        "components": [
            {"id": "label", "kind": "badge", "x": 74, "y": 62, "width": 236, "text": "FORMAT CORE / VISUAL"},
            {
                "id": "title",
                "kind": "text",
                "x": 74,
                "y": 172,
                "text": "DIO owns the composition.",
                "size": 58,
                "weight": "900",
                "fill": "$ink",
                "wrap_chars": 28,
                "max_lines": 2,
                "line_gap": 66
            },
            {
                "id": "subtitle",
                "kind": "text",
                "x": 76,
                "y": 286,
                "text": "HOMS visual discipline, promoted into Format Core for every product surface.",
                "size": 21,
                "weight": "600",
                "fill": "$muted",
                "wrap_chars": 68,
                "max_lines": 2,
                "line_gap": 28
            },
            {
                "id": "flow",
                "kind": "process",
                "x": 76,
                "y": 366,
                "width": 1128,
                "steps": ["Semantic object", "Visual profile", "Composition", "SVG / PNG", "Product surface"],
                "box_width": 164,
                "box_height": 64,
                "size": 15
            },
            {
                "id": "capabilities",
                "kind": "cards",
                "x": 76,
                "y": 500,
                "width": 1128,
                "height": 150,
                "columns": 3,
                "items": [
                    {"title": "Deterministic", "body": "Canonical scene plus profile equals stable SVG bytes."},
                    {"title": "Composable", "body": "Panels, cards, tables, flows, badges, paths and text share one law."},
                    {"title": "Fail-closed", "body": "Invalid scenes refuse rendering and publication remains external."}
                ]
            }
        ]
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the Format Core visual-composition golden proof.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--no-png", action="store_true")
    args = parser.parse_args()
    receipt = write_visual_bundle(composition(), args.out, basename="visual_composer_golden", rasterize=not args.no_png)
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
