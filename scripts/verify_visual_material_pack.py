#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters.format_core.visual_material_pack import evaluate_visual_material_pack, load_visual_material_pack  # noqa: E402
from adapters.format_core.visual_material_registry import DEFAULT_REGISTRY_PATH, load_visual_material_registry  # noqa: E402


DEFAULT_PACK = ROOT / "config" / "visual_material_packs" / "research_consultancy_alpha.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate a governed Format Core customer visual material pack.")
    parser.add_argument("--pack", type=Path, default=DEFAULT_PACK)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY_PATH)
    parser.add_argument("--strict", action="store_true", help="Return non-zero unless pack state is READY_NEEDS_YOU.")
    args = parser.parse_args()

    pack = load_visual_material_pack(args.pack.expanduser().resolve())
    registry = load_visual_material_registry(args.registry.expanduser().resolve(), root=ROOT)
    readiness = evaluate_visual_material_pack(pack, registry, root=ROOT)
    print(json.dumps(readiness, indent=2, ensure_ascii=False))
    if args.strict and readiness["state"] != "READY_NEEDS_YOU":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
