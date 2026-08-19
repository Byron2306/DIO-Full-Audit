#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_NICHEFOUNDRY_ROOT = Path("/home/byron/Downloads/NicheFoundry_Phase11")


class CampaignMediaError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _command_path(value: str | None) -> Path | None:
    if not value:
        return None
    candidate = Path(value).expanduser()
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return candidate.resolve()
    found = shutil.which(value)
    return Path(found).resolve() if found else None


def resolve_piper_binary(nichefoundry_root: Path = DEFAULT_NICHEFOUNDRY_ROOT) -> Path:
    candidates = [
        os.environ.get("PIPER_BIN"),
        str(nichefoundry_root / ".venv-piper" / "bin" / "piper"),
        "piper",
    ]
    for raw in candidates:
        resolved = _command_path(raw)
        if resolved:
            return resolved
    raise CampaignMediaError(
        "Local Piper is required for campaign narration. Set PIPER_BIN, install the NicheFoundry .venv-piper runtime, or place piper on PATH."
    )


def resolve_piper_model(nichefoundry_root: Path = DEFAULT_NICHEFOUNDRY_ROOT) -> Path:
    explicit = str(os.environ.get("PIPER_MODEL") or "").strip()
    if explicit:
        path = Path(explicit).expanduser().resolve()
        if not path.is_file() or path.suffix.lower() != ".onnx":
            raise CampaignMediaError(f"PIPER_MODEL does not point to a Piper .onnx model: {path}")
        if not Path(str(path) + ".json").is_file():
            raise CampaignMediaError(f"Piper model config is missing: {path}.json")
        return path

    voice_hint = str(os.environ.get("PIPER_VOICE") or "").strip().lower()
    roots = [
        nichefoundry_root / "assets" / "piper",
        ROOT / "assets" / "piper",
    ]
    models = sorted({path.resolve() for root in roots if root.is_dir() for path in root.rglob("*.onnx")})
    if voice_hint:
        hinted = [path for path in models if voice_hint in path.stem.lower() or voice_hint in str(path).lower()]
        if hinted:
            models = hinted
    valid = [path for path in models if Path(str(path) + ".json").is_file()]
    if not valid:
        location_text = ", ".join(str(root) for root in roots)
        raise CampaignMediaError(
            f"Local Piper voice model is required. Set PIPER_MODEL or install an .onnx + .onnx.json voice under: {location_text}"
        )
    return valid[0]


def require_tool(name: str) -> Path:
    found = shutil.which(name)
    if not found:
        raise CampaignMediaError(f"{name} is required to render narrated campaign media.")
    return Path(found).resolve()


def run_checked(command: list[str], *, input_text: str | None = None, timeout: int = 240) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        input=input_text,
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "command failed").strip()[-3000:]
        raise CampaignMediaError(f"Command failed ({Path(command[0]).name}): {detail}")
    return completed


def probe_duration(path: Path, ffprobe: Path) -> float:
    completed = run_checked(
        [str(ffprobe), "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        timeout=60,
    )
    try:
        return float(completed.stdout.strip())
    except ValueError as exc:
        raise CampaignMediaError(f"Could not read media duration for {path}") from exc


def synthesize_piper_story(
    scenes: list[dict[str, Any]],
    output_dir: Path,
    *,
    nichefoundry_root: Path = DEFAULT_NICHEFOUNDRY_ROOT,
) -> dict[str, Any]:
    piper = resolve_piper_binary(nichefoundry_root)
    model = resolve_piper_model(nichefoundry_root)
    ffprobe = require_tool("ffprobe")
    narration_dir = output_dir / "piper"
    narration_dir.mkdir(parents=True, exist_ok=True)
    scene_receipts: list[dict[str, Any]] = []

    for index, scene in enumerate(scenes, 1):
        text = str(scene.get("narration") or "").strip()
        if not text:
            raise CampaignMediaError(f"Story scene {index} has no narration for Piper.")
        scene_id = str(scene.get("scene_id") or f"scene_{index:02d}")
        wav = narration_dir / f"{index:02d}_{scene_id}.wav"
        run_checked(
            [str(piper), "--model", str(model), "--output_file", str(wav)],
            input_text=text + "\n",
            timeout=180,
        )
        if not wav.is_file() or wav.stat().st_size < 1000:
            raise CampaignMediaError(f"Piper did not create a valid WAV for {scene_id}.")
        scene_receipts.append(
            {
                "scene_id": scene_id,
                "text": text,
                "audio_path": str(wav.resolve()),
                "sha256": sha256_file(wav),
                "size_bytes": wav.stat().st_size,
                "duration_seconds": round(probe_duration(wav, ffprobe), 3),
            }
        )

    receipt = {
        "schema": "dio.piper.campaign_narration_receipt.v1",
        "created_at": utc_now(),
        "provider": "piper_local",
        "local_only": True,
        "fallback_provider": None,
        "binary": str(piper),
        "model": str(model),
        "model_sha256": sha256_file(model),
        "scene_count": len(scene_receipts),
        "scenes": scene_receipts,
        "governance": {
            "remote_tts_used": False,
            "voice_review_required": True,
            "publication": "held_for_operator_approval",
        },
    }
    write_json(output_dir / "PIPER_NARRATION_RECEIPT.json", receipt)
    return receipt


def _render_format(
    *,
    scene_images: list[Path],
    narration: list[dict[str, Any]],
    music: Path,
    output: Path,
    width: int,
    height: int,
    ffmpeg: Path,
    ffprobe: Path,
) -> dict[str, Any]:
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="dio-campaign-media-", dir=output.parent) as temporary:
        work = Path(temporary)
        segments: list[Path] = []
        for index, (image, audio_row) in enumerate(zip(scene_images, narration, strict=True), 1):
            audio = Path(audio_row["audio_path"])
            segment = work / f"segment_{index:02d}.mp4"
            video_filter = (
                f"scale={width}:{height}:force_original_aspect_ratio=increase,"
                f"crop={width}:{height},fps=30,format=yuv420p"
            )
            run_checked(
                [
                    str(ffmpeg), "-y",
                    "-loop", "1", "-framerate", "30", "-i", str(image),
                    "-i", str(audio),
                    "-filter_complex", f"[0:v]{video_filter}[v];[1:a]apad=pad_dur=0.30[a]",
                    "-map", "[v]", "-map", "[a]",
                    "-shortest",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
                    "-c:a", "aac", "-b:a", "160k",
                    "-movflags", "+faststart",
                    str(segment),
                ],
                timeout=240,
            )
            segments.append(segment)

        concat_file = work / "concat.txt"
        concat_file.write_text("".join(f"file '{segment.as_posix()}'\n" for segment in segments), encoding="utf-8")
        voiced = work / "voiced.mp4"
        run_checked(
            [str(ffmpeg), "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file), "-c", "copy", str(voiced)],
            timeout=240,
        )
        run_checked(
            [
                str(ffmpeg), "-y", "-i", str(voiced), "-stream_loop", "-1", "-i", str(music),
                "-filter_complex", "[0:a]volume=1.0[voice];[1:a]volume=0.10[music];[voice][music]amix=inputs=2:duration=first:dropout_transition=2[a]",
                "-map", "0:v:0", "-map", "[a]",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
                "-movflags", "+faststart", "-shortest", str(output),
            ],
            timeout=300,
        )

    if not output.is_file() or output.stat().st_size < 10000:
        raise CampaignMediaError(f"Narrated campaign render is invalid: {output}")
    return {
        "path": str(output.resolve()),
        "sha256": sha256_file(output),
        "size_bytes": output.stat().st_size,
        "duration_seconds": round(probe_duration(output, ffprobe), 3),
        "width": width,
        "height": height,
    }


def render_campaign_media(
    request_path: Path,
    gamma_receipt_path: Path,
    *,
    nichefoundry_root: Path = DEFAULT_NICHEFOUNDRY_ROOT,
) -> dict[str, Any]:
    request = read_json(request_path)
    gamma = read_json(gamma_receipt_path)
    if request.get("schema") != "nichefoundry.dio_campaign_production_request.v2":
        raise CampaignMediaError("Expected a nichefoundry.dio_campaign_production_request.v2 request.")
    if request.get("voice", {}).get("provider") != "piper_local" or request.get("voice", {}).get("required") is not True:
        raise CampaignMediaError("Campaign media contract requires voice.provider=piper_local and required=true.")
    if gamma.get("state") != "ready" or gamma.get("request_hash") != request.get("gamma_request_hash"):
        raise CampaignMediaError("Current Gamma story receipt does not match this campaign request.")

    scenes = list((request.get("story") or {}).get("scenes") or [])
    cards = list(gamma.get("cards") or [])
    if not scenes or len(cards) != len(scenes):
        raise CampaignMediaError("Gamma card count must exactly match the campaign story scene count.")
    scene_images = [Path(row["path"]).expanduser().resolve() for row in cards]
    if any(not path.is_file() for path in scene_images):
        raise CampaignMediaError("One or more Gamma campaign cards are missing.")

    music = Path(str((request.get("music") or {}).get("path") or "")).expanduser().resolve()
    attribution = Path(str((request.get("music") or {}).get("attribution") or "")).expanduser().resolve()
    if not music.is_file() or not attribution.is_file():
        raise CampaignMediaError("A rights-recorded music bed and attribution file are required.")

    output_dir = request_path.parent / "media"
    output_dir.mkdir(parents=True, exist_ok=True)
    piper_receipt = synthesize_piper_story(scenes, output_dir, nichefoundry_root=nichefoundry_root)
    ffmpeg = require_tool("ffmpeg")
    ffprobe = require_tool("ffprobe")
    narration = list(piper_receipt["scenes"])

    outputs = request.get("outputs") or {}
    vertical_path = Path(str(outputs.get("vertical_reel") or "")).expanduser().resolve()
    landscape_path = Path(str(outputs.get("long_form_explainer") or "")).expanduser().resolve()
    if not str(vertical_path) or not str(landscape_path):
        raise CampaignMediaError("Campaign request must define both vertical_reel and long_form_explainer output paths.")

    vertical = _render_format(
        scene_images=scene_images,
        narration=narration,
        music=music,
        output=vertical_path,
        width=1080,
        height=1920,
        ffmpeg=ffmpeg,
        ffprobe=ffprobe,
    )
    landscape = _render_format(
        scene_images=scene_images,
        narration=narration,
        music=music,
        output=landscape_path,
        width=1920,
        height=1080,
        ffmpeg=ffmpeg,
        ffprobe=ffprobe,
    )

    receipt = {
        "schema": "dio.campaign_media_receipt.v1",
        "family_id": request.get("family_id"),
        "request_hash": request.get("request_hash"),
        "gamma_request_hash": request.get("gamma_request_hash"),
        "created_at": utc_now(),
        "state": "ready",
        "story_scene_count": len(scenes),
        "gamma": {
            "generation_id": gamma.get("generation_id"),
            "card_count": len(cards),
            "receipt": str(gamma_receipt_path.resolve()),
            "visual_review_required": True,
        },
        "voice": {
            "provider": "piper_local",
            "local_only": True,
            "model": piper_receipt["model"],
            "model_sha256": piper_receipt["model_sha256"],
            "receipt": str((output_dir / "PIPER_NARRATION_RECEIPT.json").resolve()),
        },
        "music": {
            "path": str(music),
            "attribution": str(attribution),
        },
        "outputs": {
            "vertical_reel": vertical,
            "long_form_explainer": landscape,
        },
        "governance": {
            "publication": "held_for_operator_approval",
            "spend": "disabled",
            "synthetic_media_review_required": True,
            "market_validation_claimed": False,
        },
    }
    write_json(output_dir / "CAMPAIGN_MEDIA_RECEIPT.json", receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a Gamma campaign story with mandatory local Piper narration.")
    parser.add_argument("request", type=Path, help="NICHEFOUNDRY_PRODUCTION_REQUEST.json")
    parser.add_argument("gamma_receipt", type=Path, help="GAMMA_STORY_RECEIPT.json")
    parser.add_argument("--nichefoundry-root", type=Path, default=DEFAULT_NICHEFOUNDRY_ROOT)
    args = parser.parse_args()
    receipt = render_campaign_media(args.request.resolve(), args.gamma_receipt.resolve(), nichefoundry_root=args.nichefoundry_root.resolve())
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
