from __future__ import annotations

import math
import tempfile
from pathlib import Path
from typing import Any

from scripts import build_campaign_media as legacy


def _motion_filter(*, index: int, width: int, height: int, frames: int) -> str:
    frames = max(frames, 2)
    if index % 4 == 1:
        zoom = "min(zoom+0.00075,1.085)"
        x = "iw/2-(iw/zoom/2)"
        y = "ih/2-(ih/zoom/2)"
    elif index % 4 == 2:
        zoom = "1.065"
        x = f"(iw-iw/zoom)*on/{frames}"
        y = "ih/2-(ih/zoom/2)"
    elif index % 4 == 3:
        zoom = "1.065"
        x = f"(iw-iw/zoom)*(1-on/{frames})"
        y = "ih/2-(ih/zoom/2)"
    else:
        zoom = "1.055"
        x = "iw/2-(iw/zoom/2)"
        y = f"(ih-ih/zoom)*on/{frames}"
    return (
        f"scale={math.ceil(width * 1.16)}:{math.ceil(height * 1.16)}:force_original_aspect_ratio=increase,"
        f"crop={math.ceil(width * 1.14)}:{math.ceil(height * 1.14)},"
        f"zoompan=z='{zoom}':x='{x}':y='{y}':d=1:s={width}x{height}:fps=30,"
        "format=yuv420p"
    )


def render_cinematic_format(
    *,
    scene_images: list[Path],
    narration: list[dict[str, Any]],
    music: Path | None,
    music_volume: float,
    output: Path,
    width: int,
    height: int,
) -> dict[str, Any]:
    """Render projected stills as moving editorial frames, never static slides."""
    ffmpeg = legacy.require_tool("ffmpeg")
    ffprobe = legacy.require_tool("ffprobe")
    output.parent.mkdir(parents=True, exist_ok=True)
    if len(scene_images) != len(narration):
        raise legacy.CampaignMediaError("Cinematic renderer requires one narration row per scene image.")

    motion_receipts: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="dio-lingua-cinematic-", dir=output.parent) as temporary:
        work = Path(temporary)
        segments: list[Path] = []
        for index, (image, audio_row) in enumerate(zip(scene_images, narration, strict=True), 1):
            audio = Path(str(audio_row["audio_path"]))
            audio_duration = float(audio_row.get("duration_seconds") or legacy.probe_duration(audio, ffprobe))
            duration = max(1.0, audio_duration + 0.30)
            frames = max(2, math.ceil(duration * 30))
            motion_filter = _motion_filter(index=index, width=width, height=height, frames=frames)
            segment = work / f"segment_{index:02d}.mp4"
            legacy.run_checked(
                [
                    str(ffmpeg), "-y",
                    "-loop", "1", "-framerate", "30", "-i", str(image),
                    "-i", str(audio),
                    "-filter_complex", f"[0:v]{motion_filter}[v];[1:a]apad=pad_dur=0.30[a]",
                    "-map", "[v]", "-map", "[a]",
                    "-t", f"{duration:.3f}",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
                    "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
                    str(segment),
                ],
                timeout=300,
            )
            if not segment.is_file() or segment.stat().st_size < 10000:
                raise legacy.CampaignMediaError(f"Cinematic segment render is invalid: {segment}")
            segments.append(segment)
            motion_receipts.append({
                "scene_index": index,
                "motion_family": ["slow_push", "drift_right", "drift_left", "vertical_drift"][(index - 1) % 4],
                "duration_seconds": round(duration, 3),
                "frames": frames,
            })

        concat_file = work / "concat.txt"
        concat_file.write_text("".join(f"file '{segment.as_posix()}'\n" for segment in segments), encoding="utf-8")
        voiced = work / "voiced.mp4"
        legacy.run_checked(
            [str(ffmpeg), "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file), "-c", "copy", str(voiced)],
            timeout=300,
        )
        if music is None:
            legacy.run_checked(
                [str(ffmpeg), "-y", "-i", str(voiced), "-c", "copy", "-movflags", "+faststart", str(output)],
                timeout=300,
            )
        else:
            legacy.run_checked(
                [
                    str(ffmpeg), "-y", "-i", str(voiced), "-stream_loop", "-1", "-i", str(music),
                    "-filter_complex",
                    f"[0:a]volume=1.0[voice];[1:a]volume={music_volume:.3f}[music];[voice][music]amix=inputs=2:duration=first:dropout_transition=2[a]",
                    "-map", "0:v:0", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
                    "-movflags", "+faststart", "-shortest", str(output),
                ],
                timeout=360,
            )

    if not output.is_file() or output.stat().st_size < 10000:
        raise legacy.CampaignMediaError(f"Cinematic campaign render is invalid: {output}")
    return {
        "path": str(output.resolve()),
        "sha256": legacy.sha256_file(output),
        "size_bytes": output.stat().st_size,
        "duration_seconds": round(legacy.probe_duration(output, ffprobe), 3),
        "width": width,
        "height": height,
        "motion_state": "executed",
        "static_slide_deck": False,
        "motion_receipts": motion_receipts,
    }
