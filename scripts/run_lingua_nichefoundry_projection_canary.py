#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_multichannel_campaign_factory import build_family

MATRIX = ROOT / "config" / "marketing_audience_matrix.json"
DEFAULT_OUTPUT = Path("/tmp/dio-lingua-nichefoundry-canary")
TOKEN = "DIO_LINGUA_NICHEFOUNDRY_PROJECTION_CANARY_READY"


def _pick(matrix: dict, product_id: str, audience_id: str) -> tuple[dict, dict]:
    product = next((row for row in matrix.get("products") or [] if row.get("id") == product_id), None)
    if not product:
        raise RuntimeError(f"Missing configured product: {product_id}")
    audience = next((row for row in product.get("audiences") or [] if row.get("id") == audience_id), None)
    if not audience:
        raise RuntimeError(f"Missing configured audience {audience_id} for {product_id}")
    return product, audience


def _summary(family: dict) -> dict:
    variants = (family.get("story") or {}).get("variants") or {}
    request_path = ROOT / family["nichefoundry"]["request"]
    request = json.loads(request_path.read_text(encoding="utf-8"))
    return {
        "family_id": family["family_id"],
        "audience": family["audience"]["name"],
        "semantic_law_hash": family["semantic_law"]["semantic_law_hash"],
        "projection_hash": family["creative_projection"]["projection_hash"],
        "creative_fingerprint": family["creative_projection"]["creative_fingerprint"],
        "audience_archetype": family["creative_projection"]["audience_archetype"],
        "vertical": {
            "arc_family": variants["vertical_short"]["arc_family"],
            "scene_count": variants["vertical_short"]["scene_count"],
            "voice": request["variants"]["vertical_short"]["voice"],
            "music": request["variants"]["vertical_short"]["music"],
        },
        "landscape": {
            "arc_family": variants["landscape_explainer"]["arc_family"],
            "scene_count": variants["landscape_explainer"]["scene_count"],
            "voice": request["variants"]["landscape_explainer"]["voice"],
            "music": request["variants"]["landscape_explainer"]["music"],
        },
        "governance": family["governance"],
        "validation": family["validation"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Prove LINGUA creates distinct lawful NicheFoundry projections before invoking Gamma/media rendering.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--keep", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() and not args.keep:
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)

    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    homs_product, teachers = _pick(matrix, "HOMS_ASSESS", "teachers_lecturers")
    evidex_product, auditors = _pick(matrix, "EVIDEX_PACK", "compliance_audit")

    homs = build_family(homs_product, teachers, matrix["channels"], output / "homs", False)
    evidex = build_family(evidex_product, auditors, matrix["channels"], output / "evidex", False)
    homs_summary = _summary(homs)
    evidex_summary = _summary(evidex)

    checks = {
        "homs_semantic_law_ready": homs["semantic_law"]["state"] == "ready",
        "evidex_semantic_law_ready": evidex["semantic_law"]["state"] == "ready",
        "homs_projection_ready": homs["creative_projection"]["state"] == "ready",
        "evidex_projection_ready": evidex["creative_projection"]["state"] == "ready",
        "teacher_archetype": homs_summary["audience_archetype"] == "education_practitioner",
        "auditor_archetype": evidex_summary["audience_archetype"] == "assurance",
        "creative_fingerprints_distinct": homs_summary["creative_fingerprint"] != evidex_summary["creative_fingerprint"],
        "vertical_arcs_distinct": homs_summary["vertical"]["arc_family"] != evidex_summary["vertical"]["arc_family"],
        "teacher_voice_is_historical_leah": homs_summary["vertical"]["voice"].get("voice") == "en-ZA-LeahNeural",
        "auditor_voice_is_distinct_luke": evidex_summary["vertical"]["voice"].get("voice") == "en-ZA-LukeNeural",
        "short_and_long_homs_are_distinct": homs_summary["vertical"]["arc_family"] != homs_summary["landscape"]["arc_family"] and homs_summary["vertical"]["scene_count"] != homs_summary["landscape"]["scene_count"],
        "short_and_long_evidex_are_distinct": evidex_summary["vertical"]["arc_family"] != evidex_summary["landscape"]["arc_family"] and evidex_summary["vertical"]["scene_count"] != evidex_summary["landscape"]["scene_count"],
        "publication_held": homs_summary["governance"].get("publication") == "held" and evidex_summary["governance"].get("publication") == "held",
        "spend_disabled": homs_summary["governance"].get("spend") == "disabled" and evidex_summary["governance"].get("spend") == "disabled",
    }
    passed = all(checks.values())
    report = {
        "schema": "dio.lingua.nichefoundry_projection_canary.v1",
        "state": "PASS" if passed else "FAIL",
        "acceptance_token": TOKEN if passed else None,
        "checks": checks,
        "homs_teachers": homs_summary,
        "evidex_auditors": evidex_summary,
        "output": str(output),
        "truth": {
            "semantic_projection_proved": passed,
            "gamma_render_proved": False,
            "voice_execution_proved": False,
            "mp4_render_proved": False,
            "market_validation_claimed": False,
            "authority_created": False,
        },
    }
    report_path = output / "LINGUA_NICHEFOUNDRY_PROJECTION_CANARY.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=True))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
