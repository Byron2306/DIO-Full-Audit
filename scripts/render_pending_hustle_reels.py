#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts import build_hustle_campaign_factory as hustle


def main() -> int:
    parser = argparse.ArgumentParser(description="Render held NicheFoundry reels after LINGUA has resolved the draft strategy.")
    parser.add_argument("--output", type=Path, default=hustle.DEFAULT_OUTPUT)
    args = parser.parse_args()
    root = args.output.resolve()
    registry_path = root / "CREATIVE_FAMILY_REGISTRY.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    ready = failed = 0
    for family in registry.get("families") or []:
        request_ref = str((family.get("nichefoundry") or {}).get("request") or "")
        request_path = Path(request_ref)
        if not request_path.is_absolute():
            request_path = hustle.ROOT / request_path
        state, error = hustle._render_hustle_reel(request_path)
        family["nichefoundry"]["reel_state"] = state
        family["nichefoundry"]["reel_error"] = error
        if state == "ready":
            ready += 1
        if error:
            failed += 1
            family["validation"]["state"] = "failed"
            family["validation"].setdefault("errors", []).append(error)
        family_path = root / hustle.base.slug(family["product"]["id"]) / hustle.base.slug(family["audience"]["id"]) / "FAMILY.json"
        hustle.base.write_json(family_path, family)
    registry["summary"]["reels_ready"] = ready
    registry["summary"]["reel_failures"] = failed
    hustle.base.write_json(registry_path, registry)
    print(json.dumps({"schema":"dio.marketing.reel_render_batch.v1","reels_ready":ready,"failures":failed,"release":"held","publication":False,"spend":False}, indent=2))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
