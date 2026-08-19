#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from scripts import build_campaign_media as legacy

CampaignMediaError = legacy.CampaignMediaError
DEFAULT_NICHEFOUNDRY_ROOT = legacy.DEFAULT_NICHEFOUNDRY_ROOT


def _command_path(value: str | None) -> Path | None:
    if not value:
        return None
    candidate = Path(value).expanduser()
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return candidate.resolve()
    found = shutil.which(value)
    return Path(found).resolve() if found else None


def resolve_edge_tts_binary(nichefoundry_root: Path = DEFAULT_NICHEFOUNDRY_ROOT) -> Path:
    for raw in (
        os.environ.get("EDGE_TTS_BIN"),
        str(nichefoundry_root / ".venv-voicebox" / "bin" / "edge-tts"),
        str(nichefoundry_root / ".venv" / "bin" / "edge-tts"),
        "edge-tts",
    ):
        resolved = _command_path(raw)
        if resolved:
            return resolved
    raise CampaignMediaError(
        "LINGUA selected Microsoft Edge TTS, but edge-tts is not available. Install it in the original NicheFoundry voice runtime or set EDGE_TTS_BIN."
    )


def synthesize_edge_story(
    scenes: list[dict[str, Any]],
    output_dir: Path,
    *,
    voice_name: str,
    nichefoundry_root: Path = DEFAULT_NICHEFOUNDRY_ROOT,
) -> dict[str, Any]:
    edge_tts = resolve_edge_tts_binary(nichefoundry_root)
    ffprobe = legacy.require_tool("ffprobe")
    narration_dir = output_dir / "edge_tts"
    narration_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    if not voice_name:
        raise CampaignMediaError("LINGUA selected Edge TTS without a voice name.")
    for index, scene in enumerate(scenes, 1):
        text = str(scene.get("narration") or "").strip()
        if not text:
            raise CampaignMediaError(f"Story scene {index} has no narration for Edge TTS.")
        scene_id = str(scene.get("scene_id") or f"scene_{index:02d}")
        mp3 = narration_dir / f"{index:02d}_{scene_id}.mp3"
        legacy.run_checked(
            [str(edge_tts), "--voice", voice_name, "--text", text, "--write-media", str(mp3)],
            timeout=180,
        )
        if not mp3.is_file() or mp3.stat().st_size < 1000:
            raise CampaignMediaError(f"Edge TTS did not create valid audio for {scene_id}.")
        rows.append(
            {
                "scene_id": scene_id,
                "text": text,
                "audio_path": str(mp3.resolve()),
                "sha256": legacy.sha256_file(mp3),
                "size_bytes": mp3.stat().st_size,
                "duration_seconds": round(legacy.probe_duration(mp3, ffprobe), 3),
            }
        )
    receipt = {
        "schema": "dio.edge_tts.campaign_narration_receipt.v1",
        "created_at": legacy.utc_now(),
        "provider": "edge_tts",
        "voice": voice_name,
        "local_only": False,
        "remote_tts_used": True,
        "binary": str(edge_tts),
        "scene_count": len(rows),
        "scenes": rows,
        "governance": {
            "marketing_copy_only": True,
            "voice_review_required": True,
            "publication": "held_for_operator_approval",
        },
    }
    path = output_dir / "EDGE_TTS_NARRATION_RECEIPT.json"
    legacy.write_json(path, receipt)
    receipt["receipt"] = str(path.resolve())
    return receipt


def synthesize_projected_story(
    scenes: list[dict[str, Any]],
    output_dir: Path,
    voice_spec: dict[str, Any],
    *,
    nichefoundry_root: Path,
) -> dict[str, Any]:
    if voice_spec.get("required") is not True:
        raise CampaignMediaError("LINGUA projection requires narrated voice.")
    provider = str(voice_spec.get("provider") or "").strip()
    if provider == "piper_local":
        receipt = legacy.synthesize_piper_story(scenes, output_dir, nichefoundry_root=nichefoundry_root)
        receipt["receipt"] = str((output_dir / "PIPER_NARRATION_RECEIPT.json").resolve())
        return receipt
    if provider == "edge_tts":
        if voice_spec.get("remote_tts_allowed") is not True:
            raise CampaignMediaError("Edge TTS projection is blocked because remote_tts_allowed is not true.")
        return synthesize_edge_story(
            scenes,
            output_dir,
            voice_name=str(voice_spec.get("voice") or ""),
            nichefoundry_root=nichefoundry_root,
        )
    raise CampaignMediaError(f"Unsupported LINGUA voice projection provider: {provider or '<empty>'}")


def _render_projected_format(
    *,
    scene_images: list[Path],
    narration: list[dict[str, Any]],
    music: Path | None,
    music_volume: float,
    output: Path,
    width: int,
    height: int,
) -> dict[str, Any]:
    ffmpeg = legacy.require_tool("ffmpeg")
    ffprobe = legacy.require_tool("ffprobe")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="dio-lingua-media-", dir=output.parent) as temporary:
        work = Path(temporary)
        segments: list[Path] = []
        for index, (image, audio_row) in enumerate(zip(scene_images, narration, strict=True), 1):
            audio = Path(audio_row["audio_path"])
            segment = work / f"segment_{index:02d}.mp4"
            video_filter = f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},fps=30,format=yuv420p"
            legacy.run_checked(
                [
                    str(ffmpeg), "-y", "-loop", "1", "-framerate", "30", "-i", str(image), "-i", str(audio),
                    "-filter_complex", f"[0:v]{video_filter}[v];[1:a]apad=pad_dur=0.30[a]",
                    "-map", "[v]", "-map", "[a]", "-shortest", "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
                    "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(segment),
                ],
                timeout=240,
            )
            segments.append(segment)
        concat_file = work / "concat.txt"
        concat_file.write_text("".join(f"file '{segment.as_posix()}'\n" for segment in segments), encoding="utf-8")
        voiced = work / "voiced.mp4"
        legacy.run_checked([str(ffmpeg), "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file), "-c", "copy", str(voiced)], timeout=240)
        if music is None:
            legacy.run_checked([str(ffmpeg), "-y", "-i", str(voiced), "-c", "copy", "-movflags", "+faststart", str(output)], timeout=240)
        else:
            legacy.run_checked(
                [
                    str(ffmpeg), "-y", "-i", str(voiced), "-stream_loop", "-1", "-i", str(music),
                    "-filter_complex", f"[0:a]volume=1.0[voice];[1:a]volume={music_volume:.3f}[music];[voice][music]amix=inputs=2:duration=first:dropout_transition=2[a]",
                    "-map", "0:v:0", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
                    "-movflags", "+faststart", "-shortest", str(output),
                ],
                timeout=300,
            )
    if not output.is_file() or output.stat().st_size < 10000:
        raise CampaignMediaError(f"Narrated campaign render is invalid: {output}")
    return {
        "path": str(output.resolve()),
        "sha256": legacy.sha256_file(output),
        "size_bytes": output.stat().st_size,
        "duration_seconds": round(legacy.probe_duration(output, ffprobe), 3),
        "width": width,
        "height": height,
    }


def render_campaign_media_v3(
    request_path: Path,
    *,
    nichefoundry_root: Path = DEFAULT_NICHEFOUNDRY_ROOT,
) -> dict[str, Any]:
    request = legacy.read_json(request_path)
    if request.get("schema") != "nichefoundry.dio_campaign_production_request.v3":
        raise CampaignMediaError("Expected a nichefoundry.dio_campaign_production_request.v3 request.")
    variants = dict(request.get("variants") or {})
    if set(variants) != {"vertical_short", "landscape_explainer"}:
        raise CampaignMediaError("v3 request must define exactly vertical_short and landscape_explainer variants.")
    semantic = request.get("semantic_law") or {}
    projection = request.get("projection") or {}
    release = request.get("release") or {}
    if not semantic.get("semantic_law_hash") or not projection.get("projection_hash"):
        raise CampaignMediaError("v3 request must be bound to LINGUA semantic law and projection hashes.")
    if release.get("state") != "held" or release.get("spend") != "disabled":
        raise CampaignMediaError("LINGUA-projected media must keep publication held and spend disabled.")

    variant_receipts: dict[str, Any] = {}
    for surface, variant in variants.items():
        story = variant.get("story") or {}
        scenes = list(story.get("scenes") or [])
        gamma_spec = variant.get("gamma") or {}
        gamma_path = Path(str(gamma_spec.get("receipt") or "")).expanduser().resolve()
        if not gamma_path.is_file():
            raise CampaignMediaError(f"Gamma receipt is missing for {surface}: {gamma_path}")
        gamma = legacy.read_json(gamma_path)
        if gamma.get("state") != "ready" or gamma.get("request_hash") != gamma_spec.get("request_hash"):
            raise CampaignMediaError(f"Gamma receipt does not match the projected {surface} request.")
        cards = list(gamma.get("cards") or [])
        if not scenes or len(cards) != len(scenes):
            raise CampaignMediaError(f"Gamma card count must match projected story scene count for {surface}.")
        images = [Path(row["path"]).expanduser().resolve() for row in cards]
        if any(not path.is_file() for path in images):
            raise CampaignMediaError(f"One or more Gamma cards are missing for {surface}.")

        variant_dir = request_path.parent / "media" / surface
        voice_receipt = synthesize_projected_story(scenes, variant_dir, dict(variant.get("voice") or {}), nichefoundry_root=nichefoundry_root)
        music_spec = dict(variant.get("music") or {})
        music: Path | None = None
        attribution = ""
        if music_spec.get("mode") == "rights_recorded":
            music = Path(str(music_spec.get("path") or "")).expanduser().resolve()
            attribution_path = Path(str(music_spec.get("attribution") or "")).expanduser().resolve()
            if not music.is_file() or not attribution_path.is_file():
                raise CampaignMediaError(f"Rights-recorded music or attribution is missing for {surface}.")
            attribution = str(attribution_path)
        elif music_spec.get("mode") != "none":
            raise CampaignMediaError(f"Projected music mode is invalid for {surface}: {music_spec.get('mode')}")

        output_spec = variant.get("output") or {}
        output = Path(str(output_spec.get("path") or "")).expanduser().resolve()
        width = int(output_spec.get("width") or 0)
        height = int(output_spec.get("height") or 0)
        if width < 320 or height < 320:
            raise CampaignMediaError(f"Projected output dimensions are invalid for {surface}.")
        rendered = _render_projected_format(
            scene_images=images,
            narration=list(voice_receipt["scenes"]),
            music=music,
            music_volume=float(music_spec.get("volume") or 0.0),
            output=output,
            width=width,
            height=height,
        )
        variant_receipts[surface] = {
            "surface": surface,
            "story_hash": story.get("story_hash"),
            "gamma": {"generation_id": gamma.get("generation_id"), "card_count": len(cards), "receipt": str(gamma_path)},
            "voice": {
                "provider": voice_receipt["provider"],
                "voice": voice_receipt.get("voice") or voice_receipt.get("model"),
                "remote_tts_used": bool(voice_receipt.get("remote_tts_used")),
                "receipt": voice_receipt["receipt"],
            },
            "music": {**music_spec, "path": str(music) if music else "", "attribution": attribution},
            "output": rendered,
        }

    output_dir = request_path.parent / "media"
    receipt = {
        "schema": "dio.campaign_media_receipt.v2",
        "family_id": request.get("family_id"),
        "request_hash": request.get("request_hash"),
        "semantic_law_hash": semantic.get("semantic_law_hash"),
        "projection_hash": projection.get("projection_hash"),
        "creative_fingerprint": projection.get("creative_fingerprint"),
        "audience_archetype": projection.get("audience_archetype"),
        "created_at": legacy.utc_now(),
        "state": "ready",
        "variants": variant_receipts,
        "outputs": {
            "vertical_reel": variant_receipts["vertical_short"]["output"],
            "long_form_explainer": variant_receipts["landscape_explainer"]["output"],
        },
        "governance": {
            "publication": "held_for_operator_approval",
            "spend": "disabled",
            "synthetic_media_review_required": True,
            "market_validation_claimed": False,
            "authority_created": False,
            "semantic_law_preserved": True,
        },
    }
    legacy.write_json(output_dir / "CAMPAIGN_MEDIA_RECEIPT.json", receipt)
    return receipt


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Render a LINGUA-projected NicheFoundry v3 campaign request.")
    parser.add_argument("request", type=Path)
    parser.add_argument("--nichefoundry-root", type=Path, default=DEFAULT_NICHEFOUNDRY_ROOT)
    args = parser.parse_args()
    print(json.dumps(render_campaign_media_v3(args.request.resolve(), nichefoundry_root=args.nichefoundry_root.resolve()), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
