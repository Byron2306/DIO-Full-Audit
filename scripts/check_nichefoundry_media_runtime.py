#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dio_secrets import load_secret_env
from scripts.build_campaign_media import CampaignMediaError, resolve_piper_binary, resolve_piper_model
from scripts.build_multichannel_campaign_factory import FOUNDRY, MUSIC, MUSIC_ATTRIBUTION


def main() -> int:
    loaded = load_secret_env(overwrite=False)
    checks: dict[str, object] = {
        "nichefoundry_root": str(FOUNDRY.resolve()),
        "loaded_media_env": sorted(key for key in loaded if key.startswith("PIPER_") or key.startswith("DIO_CAMPAIGN_MUSIC")),
        "ffmpeg": shutil.which("ffmpeg") or "",
        "ffprobe": shutil.which("ffprobe") or "",
        "music_bed": str(MUSIC.resolve()),
        "music_bed_exists": MUSIC.is_file(),
        "music_attribution": str(MUSIC_ATTRIBUTION.resolve()),
        "music_attribution_exists": MUSIC_ATTRIBUTION.is_file(),
        "piper_binary": "",
        "piper_model": "",
        "piper_model_config_exists": False,
        "ready": False,
        "errors": [],
        "remediation": [],
    }
    errors = checks["errors"]
    remediation = checks["remediation"]
    assert isinstance(errors, list)
    assert isinstance(remediation, list)

    try:
        binary = resolve_piper_binary(FOUNDRY)
        checks["piper_binary"] = str(binary)
    except CampaignMediaError as exc:
        errors.append(str(exc))

    try:
        model = resolve_piper_model(FOUNDRY)
        checks["piper_model"] = str(model)
        checks["piper_model_config_exists"] = Path(str(model) + ".json").is_file()
    except CampaignMediaError as exc:
        errors.append(str(exc))
        configured_config = FOUNDRY / "assets" / "piper" / "en_US-lessac-high" / "en_US-lessac-high.onnx.json"
        configured_model = FOUNDRY / "assets" / "piper" / "en_US-lessac-high" / "en_US-lessac-high.onnx"
        if configured_config.is_file() and not configured_model.is_file():
            remediation.append(
                "Configured Lessac-high voice metadata exists but the ONNX model bytes are missing. "
                "Run: PYTHONNOUSERSITE=1 /home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 "
                "scripts/install_nichefoundry_piper_voice.py"
            )

    if not checks["ffmpeg"]:
        errors.append("ffmpeg is not on PATH")
    if not checks["ffprobe"]:
        errors.append("ffprobe is not on PATH")
    if not checks["music_bed_exists"]:
        errors.append("configured rights-recorded music bed is missing")
    if not checks["music_attribution_exists"]:
        errors.append("configured music attribution record is missing")

    checks["ready"] = not errors
    checks["contract"] = {
        "gamma_cards": "REQUIRED",
        "voice_provider": "piper_local",
        "remote_tts_fallback": False,
        "rights_recorded_music": "REQUIRED",
        "vertical_reel_mp4": "REQUIRED",
        "landscape_explainer_mp4": "REQUIRED",
        "publication": "HELD",
        "spend": "DISABLED",
    }
    print(json.dumps(checks, indent=2, ensure_ascii=True))
    return 0 if checks["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
