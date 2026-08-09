#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
NICHEFOUNDRY = Path("/home/byron/Downloads/NicheFoundry_Phase11")
PREVIEW_BUILDER = ROOT / "scripts/build_free_media_preview.py"
VISUAL_BUILDER = ROOT / "scripts/build_gamma_video_polish.py"

PRODUCTS: dict[str, dict[str, Any]] = {
    "homs": {
        "episode_dir": NICHEFOUNDRY / "episodes/knowedge-homs-marking-relief-pack-send-the-batch-rubric-memo-and-marksheet-get-structured-marking-s-aec7fc9b",
        "voice": "en-ZA-LeahNeural",
        "title": "HOMS Marking Relief: Turn a Marking Batch into a Review Pack",
        "description": (
            "A marking batch is waiting. HOMS prepares the first structured pass so an educator can review the work instead of rebuilding the workflow from scratch.\n\n"
            "The controlled pilot accepts learner scripts, a rubric or memo, and a marksheet. It prepares draft marks, feedback and review files with an explicit educator approval gate. The educator remains the final assessor.\n\n"
            "Start with one fake, redacted or otherwise non-sensitive batch.\n"
            "Contact: dio_workflows@outlook.com\n\n"
            "Sources and further reading:\n"
            "- DIO controlled HOMS three-script demonstration and educator review outputs.\n"
            "- This video contains illustrative synthetic media; no real learner identity is represented.\n\n"
            "Music: \"Warm Sunset by MusicLFiles\" by MusicLFiles, licensed under CC BY 4.0. "
            "https://creativecommons.org/licenses/by/4.0/"
        ),
        "tags": ["HOMS", "marking support", "educator workflow", "assessment", "rubric", "feedback", "South Africa", "DIO Workflows"],
    },
    "evidex": {
        "episode_dir": NICHEFOUNDRY / "episodes/knowedge-evidex-evidence-pack-send-the-evidence-mess-get-back-a-review-ready-donor-audit-or-complia-b24cd1d6",
        "voice": "en-ZA-LeahNeural",
        "title": "Evidex: Turn Scattered Evidence into One Traceable Review Pack",
        "description": (
            "Receipts, field notes, attendance records, photographs and spreadsheets should not remain a folder hunt. Evidex maps a bounded evidence set into one traceable pack for human review.\n\n"
            "The pack connects claims to source references, preserves provenance and exposes missing evidence. It supports review; it does not guarantee donor, funder, regulator or audit approval.\n\n"
            "Start with one redacted or otherwise non-sensitive evidence folder.\n"
            "Contact: dio_workflows@outlook.com\n\n"
            "Sources and further reading:\n"
            "- DIO controlled Evidex golden-case evidence table, mapped claims and provenance outputs.\n"
            "- This video contains illustrative synthetic media; no real client case is represented.\n\n"
            "Music: \"Soft Corporate by MusicLFiles\" by MusicLFiles, licensed under CC BY 4.0. "
            "https://creativecommons.org/licenses/by/4.0/"
        ),
        "tags": ["Evidex", "evidence pack", "provenance", "monitoring and evaluation", "NGO reporting", "audit trail", "South Africa", "DIO Workflows"],
    },
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def run(command: list[str], timeout: int = 1200) -> None:
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=timeout)
    if result.returncode != 0:
        detail = "\n".join(part for part in [result.stdout.strip(), result.stderr.strip()] if part)
        raise RuntimeError(f"Command failed: {' '.join(command)}\n{detail}")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def srt_timestamp(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d},{milliseconds:03d}"


def build_captions(episode_dir: Path, media_receipt: dict[str, Any]) -> dict[str, Any]:
    script = load_json(episode_dir / "script_manifest.json")
    scenes_by_id = {scene["scene_id"]: scene for scene in script["scenes"]}
    cursor = 0.0
    blocks: list[str] = []
    cues: list[dict[str, Any]] = []
    for index, rendered in enumerate(media_receipt["scenes"], start=1):
        scene = scenes_by_id[rendered["scene_id"]]
        duration = float(rendered["duration_seconds"])
        end = cursor + duration
        text = str(scene["voiceover"]).strip()
        blocks.append(f"{index}\n{srt_timestamp(cursor)} --> {srt_timestamp(end)}\n{text}\n")
        cues.append({"index": index, "scene_id": scene["scene_id"], "start": cursor, "end": end, "text": text})
        cursor = end
    captions = episode_dir / "captions.srt"
    captions.write_text("\n".join(blocks), encoding="utf-8")
    return {"path": str(captions), "sha256": sha256(captions), "cue_count": len(cues), "duration_seconds": round(cursor, 3), "cues": cues}


def build_metadata(episode_id: str, config: dict[str, Any]) -> dict[str, Any]:
    metadata = {
        "schema": "nichefoundry.youtube_metadata.v1",
        "episode_id": episode_id,
        "snippet": {
            "title": config["title"],
            "description": config["description"],
            "tags": config["tags"],
            "categoryId": "27",
            "defaultLanguage": "en",
        },
        "status": {
            "privacyStatus": "private",
            "selfDeclaredMadeForKids": False,
            "containsSyntheticMedia": True,
            "embeddable": True,
            "publicStatsViewable": True,
            "license": "youtube",
        },
        "paidProductPlacementDetails": {"hasPaidProductPlacement": False},
        "upload": {"notifySubscribers": False, "captionLanguage": "en", "captionName": "English", "captionIsDraft": False},
        "disclosures": {"affiliate": None, "sponsorship": None, "sensitive_topic_reviewed": True},
        "generated_at": utc_now(),
    }
    hash_input = {key: metadata[key] for key in ["snippet", "status", "paidProductPlacementDetails", "upload", "disclosures"]}
    metadata["metadata_hash"] = hashlib.sha256(json.dumps(hash_input, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return metadata


def ffprobe(path: Path) -> dict[str, Any]:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration,size,bit_rate:stream=codec_name,codec_type,width,height,r_frame_rate,sample_rate,channels", "-of", "json", str(path)],
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(result.stdout)


def update_manifests(episode_dir: Path, config: dict[str, Any], media_receipt: dict[str, Any]) -> None:
    narration = load_json(episode_dir / "narration_manifest.json")
    narration["voice_id"] = config["voice"]
    narration["model_id"] = "Microsoft Edge TTS"
    narration["finalised_at"] = utc_now()
    write_json(episode_dir / "narration_manifest.json", narration)

    audio = load_json(episode_dir / "audio_manifest.json")
    audio["generated_at"] = utc_now()
    audio["mode"] = "final_edge_tts_with_licensed_music"
    audio["note"] = "Final candidate audio rendered with the selected South African English voice and the rights-cleared music recorded in FINAL_MEDIA_RECEIPT.json."
    rendered_by_scene = {scene["scene_id"]: scene for scene in media_receipt["scenes"]}
    for scene in audio.get("scenes", []):
        rendered = rendered_by_scene.get(scene["scene_id"], {})
        scene["voice"] = config["voice"]
        scene["actual_duration_seconds"] = rendered.get("duration_seconds")
        scene["target_audio"] = rendered.get("voice")
        scene["status"] = "rendered_final_candidate"
    write_json(episode_dir / "audio_manifest.json", audio)


def finalise_product(product_id: str, config: dict[str, Any]) -> dict[str, Any]:
    episode_dir: Path = config["episode_dir"]
    thumbnail_v2 = episode_dir / "thumbnail-youtube-v2.png"
    if not thumbnail_v2.exists():
        raise FileNotFoundError(f"Missing reviewed thumbnail candidate: {thumbnail_v2}")
    legacy_thumbnail = episode_dir / "thumbnail-template-v1.png"
    active_thumbnail = episode_dir / "thumbnail.png"
    if active_thumbnail.exists() and not legacy_thumbnail.exists():
        shutil.copy2(active_thumbnail, legacy_thumbnail)
    shutil.copy2(thumbnail_v2, active_thumbnail)

    run(
        [
            "python3", str(PREVIEW_BUILDER),
            "--episode", str(episode_dir),
            "--provider", "edge",
            "--edge-voice", config["voice"],
            "--transition", "0.55",
            "--output", "final.mp4",
            "--receipt", "FINAL_MEDIA_RECEIPT.json",
            "--preview-subdir", "final_media",
            "--visual-subdir", "visuals_polished",
            "--width", "1920",
            "--height", "1080",
            "--crf", "18",
        ]
    )

    media_receipt = load_json(episode_dir / "FINAL_MEDIA_RECEIPT.json")
    captions = build_captions(episode_dir, media_receipt)
    script = load_json(episode_dir / "script_manifest.json")
    metadata = build_metadata(script["episode_id"], config)
    write_json(episode_dir / "metadata_package.json", metadata)
    update_manifests(episode_dir, config, media_receipt)

    video = episode_dir / "final.mp4"
    candidate = {
        "schema": "dio.nichefoundry.publication_candidate.v1",
        "created_at": utc_now(),
        "product_id": product_id,
        "episode_id": script["episode_id"],
        "channel": {"id": "UCc916iuoPLseg05t5J5leaQ", "title": "DIO workflows", "handle": "@dioworkflows"},
        "status": "human_review_required",
        "voice": {"provider": "Microsoft Edge TTS", "voice": config["voice"]},
        "visuals": {"provider": "Gamma-assisted campaign assets", "receipt": "GAMMA_VIDEO_POLISH_RECEIPT.json", "human_review_required": True},
        "music": media_receipt.get("scenes", [{}])[0].get("music_source", {}),
        "delivery": {
            "video": {"path": "final.mp4", "sha256": sha256(video), "probe": ffprobe(video)},
            "captions": {"path": "captions.srt", "sha256": captions["sha256"], "cue_count": captions["cue_count"]},
            "thumbnail": {"path": "thumbnail.png", "sha256": sha256(active_thumbnail), "source": "thumbnail-youtube-v2.png"},
            "metadata": {"path": "metadata_package.json", "sha256": sha256(episode_dir / "metadata_package.json"), "metadata_hash": metadata["metadata_hash"]},
        },
        "gates": {
            "private_upload_only": True,
            "video_watch_through_approved": False,
            "voice_approved": False,
            "thumbnail_approved": False,
            "metadata_approved": False,
            "youtube_upload_authorised": False,
        },
    }
    write_json(episode_dir / "FINAL_PUBLICATION_CANDIDATE.json", candidate)
    (episode_dir / "approval_checklist.md").write_text(
        "# Final Publication Approval\n\n"
        "- [ ] Watch the complete `final.mp4`.\n"
        f"- [ ] Approve narrator `{config['voice']}`.\n"
        "- [ ] Approve `thumbnail.png` at full and reduced size.\n"
        "- [ ] Confirm captions match every spoken scene.\n"
        "- [ ] Confirm music attribution appears in the YouTube description.\n"
        "- [ ] Confirm no private learner, client or organisation data appears.\n"
        "- [ ] Confirm human authority and claim boundaries remain explicit.\n"
        "- [ ] Authorise private YouTube upload to DIO workflows.\n",
        encoding="utf-8",
    )
    return candidate


def main() -> int:
    run(["python3", str(VISUAL_BUILDER)])
    candidates = [finalise_product(product_id, config) for product_id, config in PRODUCTS.items()]
    summary = {
        "schema": "dio.nichefoundry.finalisation_run.v1",
        "created_at": utc_now(),
        "status": "human_review_required",
        "products": [
            {
                "product_id": candidate["product_id"],
                "episode_id": candidate["episode_id"],
                "video": str(PRODUCTS[candidate["product_id"]]["episode_dir"] / "final.mp4"),
                "candidate": str(PRODUCTS[candidate["product_id"]]["episode_dir"] / "FINAL_PUBLICATION_CANDIDATE.json"),
            }
            for candidate in candidates
        ],
    }
    write_json(ROOT / "deliverables/DIO_VIDEO_FINALISATION_RUN.json", summary)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
