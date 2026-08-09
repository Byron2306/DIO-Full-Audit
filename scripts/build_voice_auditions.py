#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


VOICES = {
    "en-US-GuyNeural": "Current narrator; energetic US news/novel delivery",
    "en-ZA-LukeNeural": "South African English; friendly male delivery",
    "en-ZA-LeahNeural": "South African English; friendly female delivery",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def run(args: list[str], timeout: int = 180) -> None:
    result = subprocess.run(args, text=True, capture_output=True, timeout=timeout)
    if result.returncode != 0:
        detail = "\n".join(part for part in [result.stdout.strip(), result.stderr.strip()] if part)
        raise RuntimeError(f"Command failed: {' '.join(args)}\n{detail}")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        text=True,
        capture_output=True,
        check=True,
    )
    return float(result.stdout.strip())


def audition_text(episode_dir: Path) -> str:
    manifest = json.loads((episode_dir / "narration_manifest.json").read_text(encoding="utf-8"))
    scenes = manifest.get("scenes", [])
    selected = scenes[:2] + scenes[-1:]
    return " ".join(str(scene.get("text") or "").strip() for scene in selected if scene.get("text"))


def build_episode_auditions(episode_dir: Path) -> dict[str, Any]:
    if not shutil.which("edge-tts") or not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise RuntimeError("edge-tts, ffmpeg, and ffprobe are required.")

    text = audition_text(episode_dir)
    if not text:
        raise RuntimeError(f"No narration text found in {episode_dir}")

    output_dir = episode_dir / "imports" / "voice_auditions"
    output_dir.mkdir(parents=True, exist_ok=True)
    samples = []
    for voice, description in VOICES.items():
        raw = output_dir / f"{voice}_raw.mp3"
        target = output_dir / f"{voice}.mp3"
        run(["edge-tts", "--voice", voice, "--text", text, "--write-media", str(raw)])
        run(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(raw),
                "-af", "highpass=f=70,loudnorm=I=-18:TP=-1.5:LRA=8",
                "-ar", "48000", "-ac", "2", "-b:a", "160k", str(target),
            ]
        )
        raw.unlink(missing_ok=True)
        samples.append(
            {
                "voice": voice,
                "description": description,
                "path": str(target.relative_to(episode_dir)),
                "duration_seconds": round(duration(target), 3),
                "sha256": sha256(target),
                "mastering": "48 kHz stereo MP3, 160 kbps, -18 LUFS target, -1.5 dBTP target",
            }
        )

    receipt = {
        "schema": "knowedge.voice_auditions.v1",
        "created_at": utc_now(),
        "episode": episode_dir.name,
        "provider": "Microsoft Edge TTS",
        "text": text,
        "samples": samples,
        "decision": "human_listen_required",
    }
    (output_dir / "VOICE_AUDITION_RECEIPT.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    lines = ["# Voice Auditions", "", f"Audition text: {text}", ""]
    for sample in samples:
        lines.extend([f"## {sample['voice']}", "", sample["description"], "", f"File: `{sample['path']}`", ""])
    (output_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Build short, loudness-matched voice auditions for NicheFoundry episodes.")
    parser.add_argument("episodes", nargs="+", help="One or more NicheFoundry episode directories.")
    args = parser.parse_args()
    receipts = [build_episode_auditions(Path(value).expanduser().resolve()) for value in args.episodes]
    print(json.dumps({"episodes": len(receipts), "samples": sum(len(item["samples"]) for item in receipts)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
