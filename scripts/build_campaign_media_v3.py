#!/usr/bin/env python3
from __future__ import annotations

import json
import hashlib
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import build_campaign_media as legacy
from scripts.edge_tts_runtime import resolve_edge_tts_for_service

CampaignMediaError = legacy.CampaignMediaError
DEFAULT_NICHEFOUNDRY_ROOT = legacy.DEFAULT_NICHEFOUNDRY_ROOT


def _gilded_asset_pack() -> dict[str, Any]:
    """Verify the declared canonical visual pack before a production render."""
    profile_path = ROOT / "config" / "media" / "dio_gilded_house_style.json"
    profile = legacy.read_json(profile_path)
    manifest_path = ROOT / str(profile.get("source_manifest") or "")
    if not manifest_path.is_file():
        raise CampaignMediaError(
            "The configured DIO Gilded asset-pack manifest is unavailable: "
            f"{manifest_path}. Restore the canonical pack before rendering production media."
        )
    manifest = legacy.read_json(manifest_path)
    if manifest.get("pack_id") != profile.get("source_pack_id"):
        raise CampaignMediaError("The DIO Gilded asset-pack manifest does not match the configured pack id.")
    if manifest.get("generated_as_proof") != "REFUSE" or manifest.get("remote_runtime_fetch") != "REFUSE":
        raise CampaignMediaError("The DIO Gilded asset pack has invalid proof or retrieval authority.")
    base = manifest_path.parent.resolve()
    for asset in manifest.get("assets") or []:
        path = (base / str(asset.get("path") or "")).resolve()
        if not path.is_relative_to(base) or not path.is_file():
            raise CampaignMediaError(f"The DIO Gilded asset pack is missing declared asset {asset.get('asset_id')!r}.")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if f"sha256:{digest}" != asset.get("sha256"):
            raise CampaignMediaError(f"The DIO Gilded asset hash does not match for {asset.get('asset_id')!r}.")
        with Image.open(path) as image:
            if image.size != (asset.get("width"), asset.get("height")):
                raise CampaignMediaError(f"The DIO Gilded asset dimensions do not match for {asset.get('asset_id')!r}.")
    return {
        "profile_id": profile.get("profile_id"),
        "pack_id": manifest.get("pack_id"),
        "manifest": str(manifest_path.resolve()),
        "asset_count": len(manifest.get("assets") or []),
    }


def resolve_edge_tts_binary(nichefoundry_root: Path = DEFAULT_NICHEFOUNDRY_ROOT) -> Path:
    resolved = resolve_edge_tts_for_service(nichefoundry_root)
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


def synthesize_pocket_story(
    scenes: list[dict[str, Any]],
    output_dir: Path,
    voice_spec: dict[str, Any],
) -> dict[str, Any]:
    from presence_core.voice import build_voice_plan, synthesize_voice

    if voice_spec.get("remote_tts_allowed") is not False:
        raise CampaignMediaError("Pocket TTS projection must explicitly disable remote TTS.")
    profile_id = str(voice_spec.get("profile") or "")
    if not profile_id:
        raise CampaignMediaError("Pocket TTS projection must select an approved voice profile.")
    plan = build_voice_plan(
        root=ROOT,
        language=str(voice_spec.get("language") or "English"),
        interaction=None,
        requested_profile=profile_id,
    )
    if plan.get("state") != "ready_for_internal_render" or not plan.get("public_default_authorized"):
        raise CampaignMediaError("Pocket TTS projection selected a voice profile that is not approved for public rendering.")
    if plan.get("backend") != "pocket_tts":
        raise CampaignMediaError("Pocket TTS projection selected a profile with a different backend.")
    voice_name = str(plan.get("voice_url") or plan.get("model") or "").strip()
    if not voice_name or str(voice_spec.get("voice") or "").strip() != voice_name:
        raise CampaignMediaError("Pocket TTS projected voice does not match its approved profile.")

    ffprobe = legacy.require_tool("ffprobe")
    narration_dir = output_dir / "pocket_tts"
    narration_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for index, scene in enumerate(scenes, 1):
        text = str(scene.get("narration") or "").strip()
        if not text:
            raise CampaignMediaError(f"Story scene {index} has no narration for Pocket TTS.")
        scene_id = str(scene.get("scene_id") or f"scene_{index:02d}")
        audio_path = narration_dir / f"{index:02d}.wav"
        voice_receipt = synthesize_voice(text=text, output_path=audio_path, plan=plan)
        if not audio_path.is_file() or audio_path.stat().st_size < 44:
            raise CampaignMediaError(f"Pocket TTS did not create valid audio for {scene_id}.")
        with audio_path.open("rb") as audio_file:
            if audio_file.read(4) != b"RIFF":
                raise CampaignMediaError(f"Pocket TTS output for {scene_id} is not a WAV file.")
        rows.append(
            {
                "scene_id": scene_id,
                "text": text,
                "audio_path": str(audio_path.resolve()),
                "sha256": legacy.sha256_file(audio_path),
                "size_bytes": audio_path.stat().st_size,
                "duration_seconds": round(legacy.probe_duration(audio_path, ffprobe), 3),
                "voice_receipt": voice_receipt,
            }
        )

    receipt = {
        "schema": "dio.pocket_tts.campaign_narration_receipt.v1",
        "created_at": legacy.utc_now(),
        "provider": "pocket_tts",
        "profile_id": profile_id,
        "voice": voice_name,
        "local_only": True,
        "remote_tts_used": False,
        "scene_count": len(rows),
        "scenes": rows,
        "governance": {
            "marketing_copy_only": True,
            "publication": "held_for_operator_approval",
            "external_action_executed": False,
            "send_authorized": False,
        },
    }
    path = output_dir / "POCKET_TTS_NARRATION_RECEIPT.json"
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
        raise CampaignMediaError(
            "Piper narration is retired for production campaigns. Select the approved "
            "Pocket TTS Vera projection instead."
        )
    if provider == "edge_tts":
        if voice_spec.get("remote_tts_allowed") is not True:
            raise CampaignMediaError("Edge TTS projection is blocked because remote_tts_allowed is not true.")
        return synthesize_edge_story(
            scenes,
            output_dir,
            voice_name=str(voice_spec.get("voice") or ""),
            nichefoundry_root=nichefoundry_root,
        )
    if provider == "pocket_tts":
        return synthesize_pocket_story(scenes, output_dir, voice_spec)
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

    gilded_pack = _gilded_asset_pack()
    variant_receipts: dict[str, Any] = {}
    for surface, variant in variants.items():
        story = variant.get("story") or {}
        scenes = list(story.get("scenes") or [])
        # The factory renders bounded, local Format Core scene cards before this
        # stage.  They are the canonical visual input: no hosted Gamma generation
        # or opaque retrieval is required to create a reviewable campaign proof.
        images = [Path(str(value)).expanduser().resolve() for value in (variant.get("scene_images_fallback") or [])]
        if not scenes or len(images) != len(scenes):
            raise CampaignMediaError(f"Local visual card count must match projected story scene count for {surface}.")
        if any(not path.is_file() for path in images):
            raise CampaignMediaError(f"One or more local visual cards are missing for {surface}.")

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
            "visuals": {
                "provider": "format_core_local_compositor",
                "card_count": len(images),
                "paths": [str(path) for path in images],
                "external_generation_used": False,
                "gilded_asset_pack": gilded_pack,
            },
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
            "gamma_required": False,
            "visual_provider": "format_core_local_compositor",
            "gilded_asset_pack": gilded_pack,
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
