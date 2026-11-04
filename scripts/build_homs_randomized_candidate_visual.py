#!/usr/bin/env python3
"""Render the HOMS randomized Grade 1–12 candidate workflow as local SVG/PNG media."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters.format_core.visual_composer import SCHEMA, write_visual_bundle


def composition() -> dict:
    return {
        "schema": SCHEMA,
        "composition_id": "HOMS-RANDOMIZED-CANDIDATES-G1-12-V1",
        "title": "One seeded CAPS assessment per grade",
        "profile_id": "site_editorial_dark",
        "canvas": {"width": 1440, "height": 920, "background": "$paper"},
        "components": [
            {
                "id": "eyebrow", "kind": "badge", "x": 72, "y": 54,
                "width": 316, "text": "HOMS · DRAFT CANDIDATE SET",
            },
            {
                "id": "headline", "kind": "text", "x": 72, "y": 158,
                "text": "A reviewable exam and memo for every grade",
                "size": 46, "weight": "900", "fill": "$ink",
                "wrap_chars": 48, "max_lines": 2, "line_gap": 56,
            },
            {
                "id": "summary", "kind": "text", "x": 74, "y": 258,
                "text": "Subject draw seed 20261101 · 12 grades · CAPS source pages bound to each question",
                "size": 20, "weight": "600", "fill": "$muted",
                "wrap_chars": 86, "max_lines": 2, "line_gap": 28,
            },
            {
                "id": "workflow", "kind": "process", "x": 72, "y": 366,
                "width": 1296, "box_width": 226, "box_height": 86,
                "size": 17, "wrap_chars": 25,
                "steps": [
                    "Seeded CAPS subject draw",
                    "Question-level source map",
                    "Exam + marking memo",
                    "PDF and mark checks",
                    "Educator moderation",
                ],
                "fill": "$surface", "stroke": "$accent", "text_fill": "$ink",
            },
            {
                "id": "evidence-cards", "kind": "cards", "x": 72, "y": 532,
                "width": 1296, "height": 220, "columns": 3,
                "items": [
                    {
                        "title": "Reproducible assignment",
                        "body": "Subjects are drawn without replacement within each CAPS phase. The seed and reconstructed draw are included.",
                        "accent": "$accent",
                    },
                    {
                        "title": "Bounded source evidence",
                        "body": "Each question maps to a CAPS topic and cited physical page with a matching page-text hash.",
                        "accent": "$success",
                    },
                    {
                        "title": "Human decision still required",
                        "body": "Mechanical and print checks pass. Educator validity and classroom release remain pending.",
                        "accent": "$warning",
                    },
                ],
            },
            {
                "id": "footnote", "kind": "text", "x": 74, "y": 824,
                "text": "Original draft assessments · not DBE examinations · no classroom release authorized",
                "size": 17, "weight": "700", "fill": "$muted",
                "wrap_chars": 95, "max_lines": 1,
            },
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", type=Path,
        default=ROOT / "deliverables/homs_randomized_exam_candidates_20261104/media",
    )
    args = parser.parse_args()
    receipt = write_visual_bundle(
        composition(), args.out, basename="homs_randomized_candidate_workflow",
        rasterize=True,
    )
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
