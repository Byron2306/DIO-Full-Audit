#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def run(args: list[str], *, cwd: Path | None = None, timeout: int = 240) -> None:
    result = subprocess.run(args, cwd=str(cwd) if cwd else None, text=True, capture_output=True, timeout=timeout)
    if result.returncode != 0:
        detail = "\n".join(part for part in [result.stdout.strip(), result.stderr.strip()] if part)
        raise RuntimeError(f"Command failed: {' '.join(args)}\n{detail}")


def which(command: str) -> str | None:
    return shutil.which(command)


def ffprobe_duration(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        text=True,
        capture_output=True,
        check=True,
    )
    return float(result.stdout.strip() or 0)


def safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in value.lower()).strip("_") or "scene"


def render_frame(source_visual: Path, frame_png: Path) -> None:
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(source_visual), "-frames:v", "1", str(frame_png)])


def preferred_visual_source(
    episode_dir: Path,
    slide: dict[str, Any],
    scene: dict[str, Any],
    visual_subdir: str = "visuals",
) -> Path:
    visual_dir = episode_dir / "imports" / visual_subdir
    candidates = [
        visual_dir / f"{scene['card_id']}.png",
        visual_dir / f"{scene['card_id']}.jpg",
        visual_dir / f"{scene['card_id']}.jpeg",
        visual_dir / f"{scene['scene_id']}.png",
        visual_dir / f"{scene['scene_id']}.jpg",
        visual_dir / f"{scene['scene_id']}.jpeg",
        visual_dir / f"{scene['card_id']}.svg",
        visual_dir / f"{scene['scene_id']}.svg",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate

    fallback = episode_dir / slide["asset_path"].replace(".png", ".svg")
    if not fallback.exists():
        raise FileNotFoundError(f"Missing generated card SVG and no visual override found: {fallback}")
    return fallback


def synthesize_espeak(scene: dict[str, Any], raw_wav: Path) -> str:
    command = which("espeak-ng") or which("espeak")
    if not command:
        raise RuntimeError("espeak-ng/espeak is not installed.")
    with tempfile.TemporaryDirectory(prefix="knowedge_tts_") as tmp:
        tmp_wav = Path(tmp) / "voice.wav"
        run(
            [
                command,
                "-v",
                "en-us",
                "-s",
                "154",
                "-p",
                "46",
                "-a",
                "160",
                "-w",
                str(tmp_wav),
                scene["voiceover"],
            ]
        )
        shutil.copyfile(tmp_wav, raw_wav)
    return Path(command).name


def synthesize_edge(scene: dict[str, Any], raw_mp3: Path, voice_name: str) -> str:
    command = which("edge-tts")
    if not command:
        raise RuntimeError("edge-tts is not installed.")
    with tempfile.TemporaryDirectory(prefix="knowedge_tts_") as tmp:
        tmp_mp3 = Path(tmp) / "voice.mp3"
        run(
            [
                command,
                "--voice",
                voice_name,
                "--text",
                scene["voiceover"],
                "--write-media",
                str(tmp_mp3),
            ],
            timeout=120,
        )
        shutil.copyfile(tmp_mp3, raw_mp3)
    return Path(command).name


def normalize_voice(source_audio: Path, target_wav: Path, target_seconds: float) -> float:
    raw_seconds = ffprobe_duration(source_audio)
    duration = max(target_seconds, raw_seconds + 0.35, 3.0)
    run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source_audio),
            "-af",
            "apad,aresample=48000",
            "-t",
            f"{duration:.3f}",
            str(target_wav),
        ]
    )
    return duration


def first_imported_music(episode_dir: Path) -> Path | None:
    for name in ["music_bed.wav", "music_bed.mp3", "music_bed.m4a", "music_bed.ogg"]:
        candidate = episode_dir / "imports" / name
        if candidate.exists():
            return candidate
    choices = episode_dir / "imports" / "music_choices"
    if choices.exists():
        for candidate in sorted(choices.iterdir()):
            if candidate.suffix.lower() in {".wav", ".mp3", ".m4a", ".ogg"}:
                return candidate
    return None


def imported_music_provenance(imported_music: Path) -> dict[str, Any]:
    receipt_path = imported_music.parent / "music_choices" / "COMMERCIAL_MUSIC_RECEIPT.json"
    if not receipt_path.exists():
        return {
            "provider": "imported",
            "source": str(imported_music),
            "rights_status": "operator_must_verify",
        }
    receipt = load_json(receipt_path)
    selected = receipt.get("selected", {})
    return {
        "provider": selected.get("provider") or receipt.get("discovery_provider") or "imported",
        "source": str(imported_music),
        "title": selected.get("title"),
        "artist": selected.get("artist"),
        "licence": selected.get("licence_name"),
        "licence_url": selected.get("licence_url"),
        "source_page": selected.get("page_url"),
        "attribution": selected.get("attribution"),
        "rights_status": "commercial_reuse_passed" if selected.get("rights", {}).get("passed") else "blocked",
        "rights_receipt": str(receipt_path),
    }


def build_music_bed(
    target_wav: Path,
    duration: float,
    imported_music: Path | None,
    offset_seconds: float = 0,
) -> dict[str, Any]:
    if imported_music:
        run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-stream_loop",
                "-1",
                "-ss",
                f"{offset_seconds:.3f}",
                "-i",
                str(imported_music),
                "-t",
                f"{duration:.3f}",
                "-af",
                "volume=-9dB,afade=t=in:st=0:d=0.4,afade=t=out:st={:.3f}:d=0.5,aresample=48000".format(max(duration - 0.5, 0)),
                str(target_wav),
            ]
        )
        provenance = imported_music_provenance(imported_music)
        provenance["timeline_offset_seconds"] = round(offset_seconds, 3)
        return provenance

    fade_out_start = max(duration - 0.5, 0)
    expression = (
        "0.09*sin(2*PI*110*t)"
        "+0.045*sin(2*PI*220*t)"
        "+0.035*sin(2*PI*330*t)"
        "+if(lt(mod(t,0.5),0.08),0.05*sin(2*PI*880*t),0)"
        "+if(lt(mod(t+0.25,1.0),0.08),0.035*sin(2*PI*660*t),0)"
    )
    run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"aevalsrc='{expression}':s=48000:d={duration:.3f}",
            "-af",
            f"acompressor=threshold=-20dB:ratio=2.5:attack=10:release=120,alimiter=limit=0.8,afade=t=in:st=0:d=0.4,afade=t=out:st={fade_out_start:.3f}:d=0.5,aresample=48000",
            str(target_wav),
        ]
    )
    return {"provider": "procedural_ffmpeg", "source": "generated_rhythmic_tech_bed", "rights_status": "project_owned_placeholder"}


def motion_crop(index: int, duration: float) -> tuple[str, str, str]:
    frames = max(int(duration * 30), 1)
    progress = f"min(max(n/{frames},0),1)"
    variants = [
        (f"(iw-ow)*{progress}", "(ih-oh)*0.28", "slow_pan_right"),
        (f"(iw-ow)*(1-{progress})", "(ih-oh)*0.34", "slow_pan_left"),
        ("(iw-ow)*0.44", f"(ih-oh)*{progress}", "slow_pan_down"),
        ("(iw-ow)*0.56", f"(ih-oh)*(1-{progress})", "slow_pan_up"),
    ]
    return variants[index % len(variants)]


def mix_scene(
    frame_png: Path,
    voice_wav: Path,
    music_wav: Path,
    output_mp4: Path,
    duration: float,
    fade_in_seconds: float,
    fade_out_seconds: float,
    motion_index: int,
    width: int = 1280,
    height: int = 720,
    crf: int = 28,
    motion_mode: str = "pan",
) -> None:
    if motion_mode == "static_educational":
        video_filters = [
            "fps=30",
            f"scale={width}:{height}:force_original_aspect_ratio=decrease",
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=white",
            "setsar=1",
            "format=yuv420p",
        ]
    else:
        crop_x, crop_y, _motion_name = motion_crop(motion_index, duration)
        scale_width = max(width + 2, int(round(width * 1.067 / 2) * 2))
        scale_height = max(height + 2, int(round(height * 1.067 / 2) * 2))
        video_filters = [
            "fps=30",
            f"scale={scale_width}:{scale_height}:force_original_aspect_ratio=increase",
            f"crop={width}:{height}:x='{crop_x}':y='{crop_y}'",
            "setsar=1",
            "format=yuv420p",
        ]
    if fade_in_seconds > 0:
        video_filters.append(f"fade=t=in:st=0:d={fade_in_seconds:.3f}")
    if fade_out_seconds > 0:
        video_filters.append(f"fade=t=out:st={max(duration - fade_out_seconds, 0):.3f}:d={fade_out_seconds:.3f}")

    audio_filters = [
        "[1:a]volume=1.18[a1]",
        "[2:a]volume=0.34[a2]",
        "[a1][a2]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,"
        "loudnorm=I=-16:TP=-1.5:LRA=9,pan=stereo|c0=c0|c1=c0,alimiter=limit=0.95[a_mix]",
    ]
    final_audio = "a_mix"
    if fade_in_seconds > 0 or fade_out_seconds > 0:
        fade_steps = []
        if fade_in_seconds > 0:
            fade_steps.append(f"afade=t=in:st=0:d={fade_in_seconds:.3f}")
        if fade_out_seconds > 0:
            fade_steps.append(f"afade=t=out:st={max(duration - fade_out_seconds, 0):.3f}:d={fade_out_seconds:.3f}")
        audio_filters.append(f"[a_mix]{','.join(fade_steps)}[a]")
        final_audio = "a"

    run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-loop",
            "1",
            "-i",
            str(frame_png),
            "-i",
            str(voice_wav),
            "-i",
            str(music_wav),
            "-t",
            f"{duration:.3f}",
            "-filter_complex",
            f"[0:v]{','.join(video_filters)}[v];" + ";".join(audio_filters),
            "-map",
            "[v]",
            "-map",
            f"[{final_audio}]",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            str(crf),
            "-r",
            "30",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ar",
            "48000",
            "-movflags",
            "+faststart",
            str(output_mp4),
        ],
        timeout=300,
    )


def concat_segments(segment_paths: list[Path], output_mp4: Path) -> None:
    concat_file = output_mp4.parent / f"{output_mp4.stem}_segments.txt"
    concat_file.write_text("\n".join(f"file '{path.as_posix().replace(chr(39), chr(39) + chr(92) + chr(39) + chr(39))}'" for path in segment_paths) + "\n", encoding="utf-8")
    run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            str(output_mp4),
        ],
        timeout=300,
    )


def concat_segments_with_transitions(segment_paths: list[Path], durations: list[float], output_mp4: Path, transition_seconds: float) -> None:
    concat_segments(segment_paths, output_mp4)


def write_music_search_plan(episode_dir: Path) -> None:
    imports = episode_dir / "imports"
    imports.mkdir(parents=True, exist_ok=True)
    plan = {
        "schema": "knowedge.free_media.music_search_plan.v1",
        "created_at": utc_now(),
        "goal": "Find a cleared instrumental bed for a practical B2B workflow explainer.",
        "search_terms": [
            "corporate technology instrumental",
            "minimal clean focused instrumental",
            "software walkthrough background music",
            "calm productivity electronic instrumental",
            "documentary technology underscore",
        ],
        "drop_in_paths": [
            "imports/music_bed.mp3",
            "imports/music_bed.wav",
            "imports/music_choices/<candidate-file>",
        ],
        "rights_check": [
            "Confirm commercial use is allowed.",
            "Save licence URL or source page.",
            "Save creator/artist attribution.",
            "Avoid copyrighted soundtrack rips and game files.",
        ],
    }
    write_json(imports / "music_search_plan.json", plan)
    (imports / "music_search_plan.md").write_text(
        "# Music Search Plan\n\n"
        "Use this if you want to replace the procedural placeholder bed.\n\n"
        + "\n".join(f"- {term}" for term in plan["search_terms"])
        + "\n\nDrop the chosen cleared file at `imports/music_bed.mp3` or `imports/music_bed.wav`.\n",
        encoding="utf-8",
    )


def build_preview(
    episode_dir: Path,
    provider: str,
    transition_seconds: float,
    *,
    output_name: str = "free_preview.mp4",
    receipt_name: str = "FREE_MEDIA_RECEIPT.json",
    preview_subdir: str = "free_media_preview",
    visual_subdir: str = "visuals",
    width: int = 1280,
    height: int = 720,
    crf: int = 28,
    reuse_audio: bool = False,
    edge_voice: str = "en-US-GuyNeural",
    motion_mode: str = "pan",
) -> dict[str, Any]:
    if not which("ffmpeg") or not which("ffprobe"):
        raise RuntimeError("ffmpeg and ffprobe are required.")

    script_manifest = load_json(episode_dir / "script_manifest.json")
    render_manifest = load_json(episode_dir / "render_manifest.json")
    slides_by_card = {slide["card_id"]: slide for slide in render_manifest["slides"]}

    preview_root = episode_dir / preview_subdir
    frames_dir = preview_root / "frames"
    voice_dir = preview_root / "voice"
    music_dir = preview_root / "music"
    segment_dir = preview_root / "segments"
    for directory in [frames_dir, voice_dir, music_dir, segment_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    imported_music = first_imported_music(episode_dir)
    scene_receipts = []
    segment_paths = []
    segment_durations = []
    selected_provider = provider

    for index, scene in enumerate(script_manifest["scenes"]):
        scene_key = f"{index:02d}_{safe_name(scene['scene_id'])}"
        slide = slides_by_card[scene["card_id"]]
        source_visual = preferred_visual_source(episode_dir, slide, scene, visual_subdir)

        frame_png = frames_dir / f"{scene_key}.png"
        raw_audio = voice_dir / f"{scene_key}_raw.wav"
        raw_edge = voice_dir / f"{scene_key}_raw.mp3"
        voice_wav = voice_dir / f"{scene_key}.wav"
        music_wav = music_dir / f"{scene_key}.wav"
        segment_mp4 = segment_dir / f"{scene_key}.mp4"

        render_frame(source_visual, frame_png)

        provider_used = ""
        existing_audio = episode_dir / "free_media_preview" / "voice" / f"{scene_key}_raw.mp3"
        if reuse_audio and existing_audio.exists():
            source_audio = existing_audio
            provider_used = "reused-edge-tts"
            selected_provider = "reused"
        elif provider in {"auto", "edge"}:
            try:
                provider_used = synthesize_edge(scene, raw_edge, edge_voice)
                selected_provider = "edge"
                source_audio = raw_edge
            except Exception:
                if provider == "edge":
                    raise
                provider_used = synthesize_espeak(scene, raw_audio)
                selected_provider = "espeak"
                source_audio = raw_audio
        elif provider == "espeak":
            provider_used = synthesize_espeak(scene, raw_audio)
            source_audio = raw_audio
        else:
            raise ValueError(f"Unsupported provider: {provider}")

        duration = normalize_voice(source_audio, voice_wav, float(scene.get("duration_seconds", 5)))
        music_receipt = build_music_bed(music_wav, duration, imported_music, sum(segment_durations))
        scene_fade = min(max(transition_seconds / 2, 0), max(duration / 5, 0))
        fade_in = scene_fade if index > 0 else 0
        fade_out = scene_fade if index < len(script_manifest["scenes"]) - 1 else 0
        crop_x, crop_y, motion_name = motion_crop(index, duration)
        mix_scene(
            frame_png,
            voice_wav,
            music_wav,
            segment_mp4,
            duration,
            fade_in,
            fade_out,
            index,
            width,
            height,
            crf,
            motion_mode,
        )
        segment_paths.append(segment_mp4)
        segment_durations.append(duration)
        scene_receipts.append(
            {
                "scene_id": scene["scene_id"],
                "card_id": scene["card_id"],
                "provider": provider_used,
                "duration_seconds": round(duration, 3),
                "fade_in_seconds": round(fade_in, 3),
                "fade_out_seconds": round(fade_out, 3),
                "visual_motion": {
                    "type": "static_educational" if motion_mode == "static_educational" else motion_name,
                    "crop_x": None if motion_mode == "static_educational" else crop_x,
                    "crop_y": None if motion_mode == "static_educational" else crop_y,
                },
                "visual_source": str(source_visual.relative_to(episode_dir)),
                "frame": str(frame_png.relative_to(episode_dir)),
                "voice": str(voice_wav.relative_to(episode_dir)),
                "music": str(music_wav.relative_to(episode_dir)),
                "segment": str(segment_mp4.relative_to(episode_dir)),
                "music_source": music_receipt,
            }
        )

    output_mp4 = episode_dir / output_name
    concat_segments_with_transitions(segment_paths, segment_durations, output_mp4, transition_seconds)
    write_music_search_plan(episode_dir)

    receipt = {
        "schema": "knowedge.free_media_preview.v1",
        "created_at": utc_now(),
        "episode_id": script_manifest["episode_id"],
        "provider_requested": provider,
        "provider_selected": selected_provider,
        "voice_profile": {
            "provider": "Microsoft Edge TTS" if selected_provider in {"edge", "reused"} else selected_provider,
            "voice": edge_voice if selected_provider in {"edge", "reused"} else "en-us",
            "rate": "default",
            "pitch": "default",
            "reused_from_original_preview": bool(reuse_audio and selected_provider == "reused"),
        },
        "music_mode": "imported" if imported_music else "procedural_placeholder",
        "transition": {
            "type": "scene_audio_video_fade" if transition_seconds > 0 else "hard_concat",
            "requested_seconds": transition_seconds,
            "applied_seconds": round(min(max(transition_seconds / 2, 0), max(min(segment_durations or [0]) / 5, 0)), 3) if len(segment_paths) > 1 else 0,
        },
        "visual_motion": {
            "type": motion_mode,
            "note": "Educational static mode preserves complete diagrams and labels." if motion_mode == "static_educational" else "Adds subtle camera movement to reduce static slide-deck feel.",
        },
        "mastering": {
            "resolution": f"{width}x{height}",
            "video_crf": crf,
            "audio": "AAC 192k stereo, -16 LUFS target, -1.5 dBTP target",
            "visual_subdir": visual_subdir,
        },
        "output": str(output_mp4),
        "duration_seconds": round(ffprobe_duration(output_mp4), 3),
        "scene_count": len(scene_receipts),
        "scenes": scene_receipts,
        "note": "Free preview output for editorial review. Replace voice and music with approved assets before public release if needed.",
    }
    write_json(episode_dir / receipt_name, receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a no-paid-token MP4 preview from a NicheFoundry lightweight episode.")
    parser.add_argument("--episode", required=True, help="Path to promoted NicheFoundry episode directory.")
    parser.add_argument("--provider", default="espeak", choices=["espeak", "edge", "auto"])
    parser.add_argument("--transition", type=float, default=0.45, help="Seconds for slide/audio crossfades. Use 0 for hard cuts.")
    parser.add_argument("--output", default="free_preview.mp4", help="Output filename inside the episode directory.")
    parser.add_argument("--receipt", default="FREE_MEDIA_RECEIPT.json", help="Receipt filename inside the episode directory.")
    parser.add_argument("--preview-subdir", default="free_media_preview", help="Intermediate render directory inside the episode.")
    parser.add_argument("--visual-subdir", default="visuals", help="Visual override folder under imports/.")
    parser.add_argument("--motion-mode", default="pan", choices=["pan", "static_educational"], help="Preserve full instructional diagrams or apply the campaign pan treatment.")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--crf", type=int, default=28)
    parser.add_argument("--reuse-audio", action="store_true", help="Reuse the existing Edge TTS scene audio when available.")
    parser.add_argument("--edge-voice", default="en-US-GuyNeural", help="Microsoft Edge TTS voice name.")
    args = parser.parse_args()

    receipt = build_preview(
        Path(args.episode).expanduser().resolve(),
        args.provider,
        args.transition,
        output_name=args.output,
        receipt_name=args.receipt,
        preview_subdir=args.preview_subdir,
        visual_subdir=args.visual_subdir,
        width=args.width,
        height=args.height,
        crf=args.crf,
        reuse_audio=args.reuse_audio,
        edge_voice=args.edge_voice,
        motion_mode=args.motion_mode,
    )
    print(json.dumps({"output": receipt["output"], "duration_seconds": receipt["duration_seconds"], "provider": receipt["provider_selected"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
