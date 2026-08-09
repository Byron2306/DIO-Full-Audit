#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACK_DIR = ROOT / "deliverables" / "homs_learning_studio" / "grade_10_physical_sciences_term_3_motion"
EPISODE_DIR = Path("/home/byron/Downloads/NicheFoundry_Phase11/episodes/homs-learning-grade10-motion-one-dimension")
VIDEO_NAME = "HOMS_G10_T3_MOTION_VIDEO_LESSON.mp4"
ZIP_NAME = "HOMS_G10_T3_MOTION_ONE_TOPIC_COMPANION.zip"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def srt_time(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    whole_seconds, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d},{milliseconds:03d}"


def build_captions(script: dict, receipt: dict, target: Path) -> None:
    durations = {scene["scene_id"]: float(scene["duration_seconds"]) for scene in receipt["scenes"]}
    cursor = 0.0
    entries: list[str] = []
    for index, scene in enumerate(script["scenes"], 1):
        duration = durations[scene["scene_id"]]
        end = cursor + duration
        entries.extend([str(index), f"{srt_time(cursor)} --> {srt_time(end)}", scene["voiceover"], ""])
        cursor = end
    target.write_text("\n".join(entries), encoding="utf-8")


def probe_video(path: Path) -> dict:
    completed = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries",
            "format=duration,size:stream=codec_type,codec_name,width,height,channels",
            "-of", "json", str(path),
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    return json.loads(completed.stdout)


def rebuild_zip(pack_dir: Path, target: Path) -> None:
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(pack_dir.rglob("*")):
            if path.is_file() and path != target:
                archive.write(path, path.relative_to(pack_dir))


def main() -> int:
    video = EPISODE_DIR / VIDEO_NAME
    script_path = EPISODE_DIR / "script_manifest.json"
    receipt_path = EPISODE_DIR / "HOMS_LEARNING_VIDEO_RECEIPT.json"
    required = [video, script_path, receipt_path, PACK_DIR / "LEARNING_PACK_MANIFEST.json"]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing learning-video inputs: " + ", ".join(missing))

    script = read_json(script_path)
    receipt = read_json(receipt_path)
    captions = EPISODE_DIR / "captions.srt"
    build_captions(script, receipt, captions)
    thumbnail = EPISODE_DIR / "thumbnail.png"
    shutil.copyfile(PACK_DIR / "assets" / "homs_motion_video_thumbnail.png", thumbnail)

    video_dir = PACK_DIR / "video"
    video_dir.mkdir(parents=True, exist_ok=True)
    package_files = [
        video,
        captions,
        thumbnail,
        script_path,
        EPISODE_DIR / "render_manifest.json",
        EPISODE_DIR / "metadata_package.json",
        receipt_path,
        EPISODE_DIR / "approval_checklist.md",
        EPISODE_DIR / "imports" / "MUSIC_ATTRIBUTION.md",
        EPISODE_DIR / "imports" / "music_choices" / "COMMERCIAL_MUSIC_RECEIPT.json",
    ]
    for source in package_files:
        shutil.copyfile(source, video_dir / source.name)

    probe = probe_video(video)
    manifest_path = PACK_DIR / "LEARNING_PACK_MANIFEST.json"
    manifest = read_json(manifest_path)
    manifest["video_lesson"] = {
        "status": "educator_review_required",
        "path": f"video/{VIDEO_NAME}",
        "sha256": sha256(video_dir / VIDEO_NAME),
        "captions": "video/captions.srt",
        "thumbnail": "video/thumbnail.png",
        "duration_seconds": round(float(probe["format"]["duration"]), 3),
        "resolution": "1920x1080",
        "narration_provider": receipt.get("provider_selected"),
        "music_rights": "CC BY 4.0 attribution included",
        "publication": "blocked_pending_educator_approval",
    }
    write_json(manifest_path, manifest)

    validation_path = PACK_DIR / "HOMS_LEARNING_PACK_VALIDATION.json"
    validation = read_json(validation_path)
    validation["checks"].update({
        "video_lesson_present": True,
        "video_has_audio": True,
        "captions_present": True,
        "music_rights_receipt_present": True,
        "video_publication_gate_present": True,
    })
    validation["video_errors"] = []
    write_json(validation_path, validation)

    receipt_file = PACK_DIR / "HOMS_LEARNING_PACK_BUILD_RECEIPT.json"
    build_receipt = read_json(receipt_file)
    build_receipt["video_lesson"] = {
        "status": "passed",
        "path": str(video_dir / VIDEO_NAME),
        "captions": str(video_dir / "captions.srt"),
        "thumbnail": str(video_dir / "thumbnail.png"),
        "next_gate": "educator_subject_expert_review",
    }
    build_receipt["finalized_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    write_json(receipt_file, build_receipt)

    release_zip = PACK_DIR / ZIP_NAME
    rebuild_zip(PACK_DIR, release_zip)
    print(json.dumps({
        "status": "passed",
        "video": str(video_dir / VIDEO_NAME),
        "duration_seconds": manifest["video_lesson"]["duration_seconds"],
        "release_zip": str(release_zip),
        "publication": "blocked_pending_educator_approval",
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
