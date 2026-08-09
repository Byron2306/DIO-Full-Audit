#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters.format_core import render_semantic_asset  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Render one DIO semantic content object through Format Core.")
    parser.add_argument("semantic_object", type=Path)
    parser.add_argument("--out", type=Path, default=ROOT / "deliverables" / "format_core")
    parser.add_argument("--style", default="dio_professional")
    parser.add_argument("--delivery", default="editable_review")
    parser.add_argument("--language")
    parser.add_argument("--channels", nargs="+")
    parser.add_argument("--release", action="store_true")
    args = parser.parse_args()
    source = args.semantic_object.expanduser().resolve()
    content = json.loads(source.read_text(encoding="utf-8"))
    output = args.out.expanduser().resolve() / str(content["object_id"])
    receipt = render_semantic_asset(
        content,
        output,
        style_profile=args.style,
        delivery_profile=args.delivery,
        language=args.language,
        channels=args.channels,
        release_mode=args.release,
        source_root=source.parent,
    )
    print(json.dumps({"output": str(output), "status": receipt["status"], "channels": [item["channel"] for item in receipt["outputs"]]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
