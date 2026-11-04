#!/usr/bin/env python3
"""Add source-bound SRT/WebVTT captions to the held Campaign Lab demo videos."""
from __future__ import annotations

import hashlib
import json
import shutil
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "acceptance_runs/68-product-sellability-20261027/CAMPAIGN_LAB_CUSTOMER_EXECUTION_20261102_V2"
FAMILY = RUN / "moya-mobile-care/moya-operations"
PACKAGE = RUN / "CAMPAIGN_LAB_CUSTOMER_RECEIPT.json"
EXPORT = ROOT / "deliverables/campaign_lab_caption_sidecars_20261104"
PAD_SECONDS = 0.30  # build_campaign_media_v3 pads every scene audio by this amount before concat


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def timestamp(seconds: float, *, vtt: bool = False) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, millis = divmod(remainder, 1000)
    separator = "." if vtt else ","
    return f"{hours:02}:{minutes:02}:{whole_seconds:02}{separator}{millis:03}"


def main() -> None:
    package = json.loads(PACKAGE.read_text(encoding="utf-8"))
    artifacts = package.setdefault("artifacts", [])
    artifact_paths = {row.get("path") for row in artifacts}
    receipt = json.loads((FAMILY / "media/CAMPAIGN_MEDIA_RECEIPT.json").read_text(encoding="utf-8"))
    results = []
    for variant, video_name in (("landscape_explainer", "explainer_1920x1080.mp4"),
                                ("vertical_short", "reel_1080x1920.mp4")):
        narration_path = FAMILY / f"media/{variant}/POCKET_TTS_NARRATION_RECEIPT.json"
        narration_receipt = json.loads(narration_path.read_text(encoding="utf-8"))
        scenes = narration_receipt.get("scenes") or []
        if len(scenes) != narration_receipt.get("scene_count") or not scenes:
            raise ValueError(f"Narration receipt scene count is inconsistent: {variant}")

        cues = []
        cursor = 0.0
        for index, scene in enumerate(scenes, 1):
            duration = float(scene["duration_seconds"])
            text = str(scene.get("text") or "").strip()
            audio = Path(scene["audio_path"])
            if not text or not audio.is_file() or sha(audio) != scene.get("sha256"):
                raise ValueError(f"Narration text/audio provenance failed for {variant} scene {index}")
            cues.append({"index": index, "scene_id": scene["scene_id"], "start": cursor,
                         "end": cursor + duration, "text": text, "audio_sha256": scene["sha256"]})
            cursor += duration + PAD_SECONDS

        srt_blocks, vtt_blocks = [], ["WEBVTT", ""]
        for cue in cues:
            wrapped = "\n".join(textwrap.wrap(cue["text"], width=42, break_long_words=False,
                                                 break_on_hyphens=False))
            srt_blocks.append(f"{cue['index']}\n{timestamp(cue['start'])} --> {timestamp(cue['end'])}\n{wrapped}")
            vtt_blocks.append(f"{timestamp(cue['start'], vtt=True)} --> {timestamp(cue['end'], vtt=True)}\n{wrapped}\n")

        base = FAMILY / "assets" / video_name
        srt_path = base.with_suffix(".srt")
        vtt_path = base.with_suffix(".vtt")
        srt_path.write_text("\n\n".join(srt_blocks) + "\n", encoding="utf-8")
        vtt_path.write_text("\n".join(vtt_blocks), encoding="utf-8")
        results.append({"variant": variant, "video": str(base.relative_to(RUN)),
                        "video_sha256": sha(base), "narration_receipt": str(narration_path.relative_to(RUN)),
                        "narration_receipt_sha256": sha(narration_path), "scene_count": len(scenes),
                        "captioned_voice_seconds": round(sum(float(row["duration_seconds"]) for row in scenes), 3),
                        "timeline_end_seconds": round(cursor, 3), "scene_audio_pad_seconds": PAD_SECONDS,
                        "timing_method": "cumulative Pocket TTS source durations; 0.30s per-scene render pad from build_campaign_media_v3.py; no transition overlap",
                        "cues": cues, "srt": {"path": str(srt_path.relative_to(RUN)), "sha256": sha(srt_path)},
                        "vtt": {"path": str(vtt_path.relative_to(RUN)), "sha256": sha(vtt_path)}})
        for path in (srt_path, vtt_path):
            rel = str(path.relative_to(RUN))
            row = {"path": rel, "bytes": path.stat().st_size, "sha256": sha(path)}
            artifacts[:] = [item for item in artifacts if item.get("path") != rel]
            artifacts.append(row)

    receipt_out = FAMILY / "media/CAMPAIGN_CAPTIONS_RECEIPT.json"
    receipt_out.write_text(json.dumps({"schema": "dio.campaign_lab.caption_sidecars.v1",
                                       "status": "generated_held_for_human_caption_review",
                                       "timing_method": "Scene-order cumulative source audio durations plus 0.30-second render padding per scene; cues end at spoken audio duration.",
                                       "limits": ["Timing is derived from renderer inputs and scene order, not phoneme-level forced alignment.",
                                                  "Human review should confirm text, reading speed and synchronization before publication."],
                                       "variants": results}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    rel_receipt = str(receipt_out.relative_to(RUN))
    artifacts[:] = [item for item in artifacts if item.get("path") != rel_receipt]
    artifacts.append({"path": rel_receipt, "bytes": receipt_out.stat().st_size, "sha256": sha(receipt_out)})
    package["artifacts"] = artifacts
    # The family asset index lets downstream consumers locate native caption tracks.
    assets = package.setdefault("customer_family", {}).setdefault("assets", {})
    assets["explainer_captions_srt"] = str((FAMILY / "assets/explainer_1920x1080.srt").relative_to(ROOT))
    assets["explainer_captions_vtt"] = str((FAMILY / "assets/explainer_1920x1080.vtt").relative_to(ROOT))
    assets["reel_captions_srt"] = str((FAMILY / "assets/reel_1080x1920.srt").relative_to(ROOT))
    assets["reel_captions_vtt"] = str((FAMILY / "assets/reel_1080x1920.vtt").relative_to(ROOT))
    PACKAGE.write_text(json.dumps(package, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    EXPORT.mkdir(parents=True, exist_ok=True)
    for row in results:
        for key in ("srt", "vtt"):
            source = RUN / row[key]["path"]
            target = EXPORT / Path(row[key]["path"]).name
            shutil.copyfile(source, target)
    shutil.copyfile(receipt_out, EXPORT / "CAMPAIGN_CAPTIONS_RECEIPT.json")
    (EXPORT / "README.md").write_text(
        "# Campaign Lab caption sidecars\n\n"
        "This portable folder contains English SRT and WebVTT caption tracks for the Campaign Lab landscape explainer and vertical short. "
        "The tracks preserve narration wording from the local Pocket TTS receipts. The adjacent JSON receipt records scene IDs, source audio hashes, "
        "video hashes, cue times, and the 0.30-second per-scene renderer pad. Cues end at the spoken audio duration; the remaining scene pad is silent.\n\n"
        "These tracks are machine-timed from scene durations, not phoneme-level forced alignment. Check wording, synchronization, reading speed, "
        "brand/content, and rights before publication. The example is held for human review and does not authorize publication or spend.\n",
        encoding="utf-8",
    )
    print(json.dumps({"variants": [{"variant": row["variant"], "scene_count": row["scene_count"],
                                     "cue_count": len(row["cues"]), "timeline_end_seconds": row["timeline_end_seconds"],
                                     "srt": row["srt"]["path"], "vtt": row["vtt"]["path"]} for row in results],
                      "caption_receipt": rel_receipt, "portable_export": str(EXPORT.relative_to(ROOT)),
                      "package_artifact_count": len(artifacts)}, indent=2))


if __name__ == "__main__":
    main()
