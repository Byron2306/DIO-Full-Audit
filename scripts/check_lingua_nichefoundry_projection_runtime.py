#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dio_secrets import load_secret_env
from lingua.product_projection import build_projection_plan
from lingua.semantic_law import build_semantic_law
from scripts.build_campaign_media import CampaignMediaError, resolve_piper_binary, resolve_piper_model
from scripts.build_campaign_media_v3 import resolve_edge_tts_binary
from scripts.build_multichannel_campaign_factory_v3 import FOUNDRY, _music_catalog


def _sample_product() -> dict[str, str]:
    return {
        "id": "HOMS_ASSESS",
        "name": "HOMS Assessment Desk",
        "short_name": "HOMS",
        "offer": "assessment_desk",
        "promise": "Prepare marking, feedback and assessment material for educator review.",
        "proof": "A controlled route produces reviewable marking while the educator remains final authority.",
        "cta": "Send one controlled assessment batch",
    }


def _teacher() -> dict[str, str]:
    return {
        "id": "teachers_lecturers",
        "name": "Teachers and lecturers",
        "pain": "Marking, feedback and paper preparation consume evenings and weekends.",
        "outcome": "Structured drafts and learner feedback ready for educator review.",
    }


def main() -> int:
    loaded = load_secret_env(overwrite=False)
    product = _sample_product()
    audience = _teacher()
    law = build_semantic_law(product, audience)
    projection = build_projection_plan(law, product, audience, {"TIKTOK_ORGANIC": {"format": "vertical_reel"}, "YOUTUBE_ORGANIC": {"format": "short_and_explainer"}})
    teacher_plan = projection["surfaces"]["vertical_short"]

    checks: dict[str, object] = {
        "nichefoundry_root": str(FOUNDRY.resolve()),
        "active_factory": "LINGUA_PROJECTION_V3",
        "semantic_law_schema": law["schema"],
        "projection_schema": projection["schema"],
        "teacher_audience_archetype": projection["audience_archetype"],
        "teacher_vertical_arc": teacher_plan["arc_family"],
        "teacher_voice_provider": teacher_plan["voice"]["provider"],
        "teacher_voice": teacher_plan["voice"]["voice"],
        "teacher_music_family": teacher_plan["music"]["family"],
        "edge_tts_binary": "",
        "piper_binary": "",
        "piper_model": "",
        "rights_recorded_music_count": 0,
        "rights_recorded_music": [],
        "loaded_media_env": sorted(key for key in loaded if key.startswith("PIPER_") or key.startswith("DIO_CAMPAIGN_MUSIC") or key == "EDGE_TTS_BIN"),
        "ready_for_teacher_projection": False,
        "errors": [],
        "warnings": [],
    }
    errors = checks["errors"]
    warnings = checks["warnings"]
    assert isinstance(errors, list)
    assert isinstance(warnings, list)

    try:
        checks["edge_tts_binary"] = str(resolve_edge_tts_binary(FOUNDRY))
    except CampaignMediaError as exc:
        errors.append(str(exc))

    try:
        checks["piper_binary"] = str(resolve_piper_binary(FOUNDRY))
        checks["piper_model"] = str(resolve_piper_model(FOUNDRY))
    except CampaignMediaError as exc:
        warnings.append("Piper fallback/profile availability: " + str(exc))

    catalog = _music_catalog()
    checks["rights_recorded_music_count"] = len(catalog)
    checks["rights_recorded_music"] = [
        {
            "title": row.get("title"),
            "artist": row.get("artist"),
            "licence": row.get("licence"),
            "path": str(row.get("path") or ""),
        }
        for row in catalog[:12]
    ]
    if not catalog:
        warnings.append("No prior rights-recorded music catalog entries were found; projections that allow silence can still render without music.")

    active_factory = ROOT / "scripts" / "build_multichannel_campaign_factory.py"
    try:
        source = active_factory.read_text(encoding="utf-8")
        if "build_multichannel_campaign_factory_v3 import *" not in source:
            errors.append("Active campaign factory is not routed through LINGUA projection v3")
    except OSError as exc:
        errors.append(f"Could not inspect active campaign factory: {exc}")

    checks["ready_for_teacher_projection"] = bool(checks["edge_tts_binary"]) and not errors
    checks["contract"] = {
        "semantic_law": "REQUIRED",
        "creative_projection": "REQUIRED",
        "vertical_short_story": "AUDIENCE_CONDITIONED",
        "landscape_explainer_story": "AUDIENCE_CONDITIONED_INDEPENDENT_PROJECTION",
        "voice_selection": "LINGUA_PROJECTION",
        "historical_teacher_voice": "en-ZA-LeahNeural",
        "music_selection": "RIGHTS_RECORDED_CATALOG_OR_INTENTIONAL_SILENCE",
        "gamma_direction": "LINGUA_PROJECTION_BOUND",
        "publication": "HELD",
        "spend": "DISABLED",
        "market_validation": False,
        "authority_created": False,
    }
    print(json.dumps(checks, indent=2, ensure_ascii=True))
    return 0 if checks["ready_for_teacher_projection"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
