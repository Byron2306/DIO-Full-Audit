from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from products.premium_media_federation import ACCEPTANCE_TOKEN
from products.premium_media_gauntlet import run_gauntlet


def _load_optional_json(path: Path | None) -> dict | None:
    if path is None:
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("state/media_incarnation/phase16_1_1"))
    parser.add_argument("--nichefoundry-root", type=Path)
    parser.add_argument(
        "--provider",
        default="auto",
        choices=["auto", "imported", "voicebox", "kokoro", "piper", "elevenlabs", "openvoice"],
    )
    parser.add_argument("--script-package", type=Path)
    parser.add_argument("--production-request", type=Path)
    args = parser.parse_args()
    result = run_gauntlet(
        output_dir=args.output,
        nichefoundry_root=args.nichefoundry_root,
        provider=args.provider,
        script_package=_load_optional_json(args.script_package),
        production_request=_load_optional_json(args.production_request),
    )
    keys = (
        "explainer_contract_binding",
        "nichefoundry_repository_execution",
        "premium_or_approved_voice",
        "robotic_production_fallback",
        "music_asset_present",
        "music_rights_evidence",
        "narration_music_mix",
        "sample_rate_48khz_stereo",
        "loudness_qa",
        "procedural_music_fallback",
        "music_hiss_detection",
        "native_gamma_execution",
        "gamma_scene_coverage",
        "gamma_final_video_binding",
        "native_nichefoundry_render_execution",
        "gamma_composition_preserved",
        "document_studio_control_surface_binding",
        "document_studio_native_render_execution",
        "destructive_media_recomposition",
        "automated_perceptual_release",
        "human_visual_release",
        "premium_video_rendering",
        "corpus_execution_census",
        "full_corpus_native_execution",
        "canonical_output_integrity",
        "tamper_detection",
        "provider_set",
        "external_publication",
        "external_send",
        "media_spend",
        "human_gate",
    )
    print(json.dumps({key: result[key] for key in keys}, indent=2, sort_keys=True))
    print(result["acceptance_token"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
