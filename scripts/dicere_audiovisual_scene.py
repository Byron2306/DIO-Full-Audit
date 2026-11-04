"""Dicere audiovisual scene adapter for DIO's NicheFoundry media compiler.

Local preview rendering only.
No publication, spending, authority creation, or external transmission.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


class DicereSceneError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def probe(path: Path) -> dict:
    result = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-show_streams",
            "-show_format",
            "-of", "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    return json.loads(result.stdout)


def render_dicere_scene(
    *,
    source: Path,
    output: Path,
    width: int,
    height: int,
    expected_sha256: str,
) -> dict:

    source = Path(source).resolve()
    output = Path(output).resolve()

    if not source.is_file():
        raise DicereSceneError("DICERE_SOURCE_MISSING")

    if sha256(source) != expected_sha256:
        raise DicereSceneError("DICERE_SOURCE_HASH_MISMATCH")

    if source == output:
        raise DicereSceneError("SOURCE_OVERWRITE_REFUSED")

    if width < 320 or height < 320:
        raise DicereSceneError("INVALID_OUTPUT_DIMENSIONS")

    source_info = probe(source)

    streams = source_info["streams"]

    video = next(
        (s for s in streams if s["codec_type"] == "video"),
        None,
    )

    audio = next(
        (s for s in streams if s["codec_type"] == "audio"),
        None,
    )

    if video is None:
        raise DicereSceneError("SOURCE_VIDEO_MISSING")

    if audio is None:
        raise DicereSceneError("SOURCE_AUDIO_MISSING")

    if video["codec_name"] != "h264":
        raise DicereSceneError("UNSUPPORTED_SOURCE_VIDEO_CODEC")

    if audio["codec_name"] != "aac":
        raise DicereSceneError("UNSUPPORTED_SOURCE_AUDIO_CODEC")

    output.parent.mkdir(parents=True, exist_ok=True)

    if output.exists():
        raise DicereSceneError("OUTPUT_ALREADY_EXISTS")

    filter_chain = (
        f"scale={width}:{height}:"
        "force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:"
        "color=0x060606,"
        "setsar=1,"
        "format=yuv420p"
    )

    temporary = output.with_name(
        output.stem + ".partial.mp4"
    )

    if temporary.exists():
        raise DicereSceneError("PARTIAL_OUTPUT_ALREADY_EXISTS")

    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "error",
        "-nostdin",
        "-n",
        "-i", str(source),
        "-map", "0:v:0",
        "-map", "0:a:0",
        "-vf", filter_chain,
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "19",
        "-c:a", "copy",
        "-movflags", "+faststart",
        str(temporary),
    ]

    try:
        subprocess.run(
            command,
            check=True,
            timeout=300,
        )

        if not temporary.is_file():
            raise DicereSceneError("RENDER_NOT_CREATED")

        output_info = probe(temporary)

        output_video = next(
            s for s in output_info["streams"]
            if s["codec_type"] == "video"
        )

        output_audio = next(
            s for s in output_info["streams"]
            if s["codec_type"] == "audio"
        )

        if (
            output_video["width"] != width
            or output_video["height"] != height
        ):
            raise DicereSceneError("OUTPUT_DIMENSION_MISMATCH")

        if output_audio["codec_name"] != "aac":
            raise DicereSceneError("OUTPUT_AUDIO_CODEC_MISMATCH")

        source_duration = float(
            source_info["format"]["duration"]
        )

        output_duration = float(
            output_info["format"]["duration"]
        )

        if abs(source_duration - output_duration) > 0.12:
            raise DicereSceneError("AUDIO_VIDEO_DURATION_DRIFT")

        temporary.rename(output)

    finally:
        if temporary.exists():
            temporary.unlink()

    receipt = {
        "schema": "dio.dicere.audiovisual_scene_receipt.v1",
        "organ_id": "dicere",
        "production_role": "presenter_performance",
        "source": {
            "path": str(source),
            "sha256": expected_sha256,
        },
        "output": {
            "path": str(output),
            "sha256": sha256(output),
            "bytes": output.stat().st_size,
            "width": width,
            "height": height,
        },
        "audio_policy": "preserve_embedded_aac",
        "publication": "held",
        "advertising_spend": "disabled",
        "human_review_required": True,
        "authority_created": False,
        "execution_authority_claimed": False,
        "validation_scope": "local_media_structure_only",
    }

    receipt_path = output.with_suffix(".receipt.json")

    if receipt_path.exists():
        raise DicereSceneError("RECEIPT_ALREADY_EXISTS")

    receipt_path.write_text(
        json.dumps(receipt, indent=2) + "\n",
        encoding="utf-8",
    )

    return receipt
