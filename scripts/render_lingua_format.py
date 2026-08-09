#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters.format_core import render_semantic_asset, semantic_content_from_lingua_object  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Project an existing DIO Lingua object through Format Core.")
    parser.add_argument("object", help="Semantic object ID or JSON path")
    parser.add_argument("--language", required=True)
    parser.add_argument("--out", type=Path, default=ROOT / "deliverables" / "format_core")
    parser.add_argument("--style", default="dio_professional")
    parser.add_argument("--delivery", default="editable_review")
    parser.add_argument("--channels", nargs="+")
    parser.add_argument("--review-candidate", action="store_true", help="Allow a non-approved language lane for human review.")
    args = parser.parse_args()
    candidate = Path(args.object).expanduser()
    source = candidate.resolve() if candidate.is_file() else ROOT / "state" / "lingua" / "objects" / f"{args.object}.json"
    lingua = json.loads(source.read_text(encoding="utf-8"))
    content = semantic_content_from_lingua_object(lingua)
    out_dir = args.out.expanduser().resolve() / str(content["object_id"]) / args.language
    receipt = render_semantic_asset(
        content,
        out_dir,
        style_profile=args.style,
        delivery_profile=args.delivery,
        language=args.language,
        channels=args.channels,
        release_mode=not args.review_candidate,
        source_root=ROOT,
    )
    print(json.dumps({"output": str(out_dir), "status": receipt["status"], "language": receipt["language"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
