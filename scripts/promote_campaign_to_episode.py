#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_NICHEFOUNDRY_ROOT = Path("/home/byron/Downloads/NicheFoundry_Phase11")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def slug(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return cleaned[:90] or "episode"


def stable_id(parts: list[str]) -> str:
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()[:8]


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def card_type(role: str, index: int) -> str:
    if index == 0:
        return "cover"
    if role in {"pain", "workflow"}:
        return "mission_brief"
    if role == "cta":
        return "answer_card"
    return "question_card"


def theme_from_visual_plan(visual_plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "palette": ["sea", "gold", "teal"],
        "backdrop": "clean operator desk with evidence folders, route cards, approval stamps, and delivery ZIP",
        "icon_tags": ["evidence", "route", "review", "zip"],
        "motion_style": "fast desk sweep, card stack reveal, approval stamp, clean output handoff",
        "source_palette": (visual_plan.get("visual_identity") or {}).get("palette", {}),
    }


def build_script_manifest(storyboard: dict[str, Any]) -> dict[str, Any]:
    scenes = []
    for index, scene in enumerate(storyboard["scenes"]):
        card_id = f"{StringNumber(index + 1)}_{slug(scene['role'])}"
        scenes.append(
            {
                "scene_id": scene["scene_id"],
                "card_id": card_id,
                "role": scene["role"],
                "objective": f"Move the buyer from {scene['role']} to the next decision point.",
                "on_screen_text": scene["screen_text"],
                "voiceover": scene["narration"],
                "visual_note": scene["visual"],
                "duration_seconds": scene["duration_seconds"],
            }
        )
    return {
        "episode_id": storyboard["episode_id"],
        "tone": "practical, proof-first, calm, commercial, human-approved",
        "cast": {
            "main_host": "Operator narrator voice",
            "proof_host": "Evidence and boundary voice",
            "cta_host": "Pilot offer voice",
        },
        "scenes": scenes,
    }


def StringNumber(value: int) -> str:
    return str(value).zfill(2)


def build_render_manifest(script_manifest: dict[str, Any]) -> dict[str, Any]:
    slides = []
    narration_order = []
    for index, scene in enumerate(script_manifest["scenes"]):
        slide_type = card_type(scene["role"], index)
        slides.append(
            {
                "card_id": scene["card_id"],
                "type": slide_type,
                "asset_path": f"cards/{StringNumber(index)}_{scene['card_id']}.png",
            }
        )
        narration_order.append(
            {
                "scene_id": scene["scene_id"],
                "card_id": scene["card_id"],
                "duration_seconds": scene["duration_seconds"],
            }
        )
    return {
        "output": {"video": "final.mp4", "captions": "captions.srt", "thumbnail": "thumbnail.png"},
        "video": {"width": 1920, "height": 1080, "fps": 30, "video_codec": "h264", "audio_codec": "aac"},
        "countdown_seconds": 0,
        "slides": slides,
        "narration_order": narration_order,
    }


def build_visual_manifest(script_manifest: dict[str, Any], storyboard: dict[str, Any], visual_plan: dict[str, Any]) -> dict[str, Any]:
    theme = theme_from_visual_plan(visual_plan)
    cards = []
    visuals_by_scene = {item["scene_id"]: item for item in visual_plan.get("scene_visuals", [])}
    for index, scene in enumerate(script_manifest["scenes"]):
        source_scene = storyboard["scenes"][index]
        visual = visuals_by_scene.get(scene["scene_id"], {})
        cards.append(
            {
                "card_id": scene["card_id"],
                "type": card_type(scene["role"], index),
                "headline": source_scene["screen_text"],
                "body": source_scene["narration"],
                "supporting_text": source_scene["visual"],
                "citation": "KnowEdge AutoRelease local pipeline",
                "layout": "workflow_panel",
                "palette": theme["palette"],
                "backdrop": theme["backdrop"],
                "icon_tags": theme["icon_tags"],
                "illustration_prompt": (
                    f"Create a clean B2B workflow slide for {storyboard['product_layer']}. "
                    f"Scene objective: {visual.get('objective', source_scene['visual'])}. "
                    "Show real workflow objects: inbox, files, evidence table, approval receipt, invoice, and delivery ZIP. "
                    "Avoid private data, fake revenue numbers, and exaggerated AI claims."
                ),
                "motion": theme["motion_style"],
            }
        )
    return {
        "episode_id": storyboard["episode_id"],
        "pack": "knowedge_product_launch",
        "theme": theme,
        "cards": cards,
    }


def build_narration_manifest(script_manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "voice_id": "operator-narrator-placeholder",
        "model_id": "eleven_multilingual_v2",
        "scenes": [
            {
                "filename": f"{StringNumber(index)}_{slug(scene['scene_id'])}.mp3",
                "role": scene["role"],
                "text": scene["voiceover"],
            }
            for index, scene in enumerate(script_manifest["scenes"])
        ],
    }


def build_audio_manifest(script_manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "generated_at": utc_now(),
        "mode": "prompt_ready",
        "note": "Audio prompts are ready for ElevenLabs or another TTS provider. MP3 imports should be placed under imports/elevenlabs.",
        "scenes": [
            {
                "scene_id": scene["scene_id"],
                "role": scene["role"],
                "duration_seconds": scene["duration_seconds"],
                "source_text": f"imports/prompts/elevenlabs/{scene['scene_id']}.txt",
                "target_audio": f"audio/{StringNumber(index)}_{slug(scene['scene_id'])}.mp3",
                "voice": "operator-narrator-placeholder",
                "actual_duration_seconds": None,
                "status": "tts_prompt_ready",
            }
            for index, scene in enumerate(script_manifest["scenes"])
        ],
    }


def write_markdown(episode_dir: Path, storyboard: dict[str, Any], metadata: dict[str, Any]) -> None:
    title = (metadata.get("snippet") or {}).get("title", storyboard["episode_id"])
    scene_lines = "\n".join(
        f"## {scene['screen_text']}\n\n{scene['narration']}\n\nVisual: {scene['visual']}\n"
        for scene in storyboard["scenes"]
    )
    (episode_dir / "script.md").write_text(f"# {title}\n\n{scene_lines}", encoding="utf-8")
    (episode_dir / "gamma_input.md").write_text(
        "# Gamma Input\n\n"
        f"Title: {title}\n\n"
        "Style: clean B2B workflow deck, evidence-first, review-safe.\n\n"
        f"{scene_lines}",
        encoding="utf-8",
    )
    (episode_dir / "approval_checklist.md").write_text(
        "# Approval Checklist\n\n"
        "- [ ] No private client data.\n"
        "- [ ] No fabricated metrics or testimonials.\n"
        "- [ ] Human approval boundary is visible.\n"
        "- [ ] Pilot CTA is concrete and fulfilable manually.\n"
        "- [ ] Visual exports match the filenames in imports/canva_export_list.csv.\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Promote a Phase 3 campaign into a NicheFoundry lightweight episode package.")
    parser.add_argument("--campaign", required=True, help="Campaign directory, for example campaigns/phase3/evidex.")
    parser.add_argument("--nichefoundry-root", default=str(DEFAULT_NICHEFOUNDRY_ROOT))
    parser.add_argument("--out", default="", help="Optional explicit episode directory.")
    parser.add_argument("--force", action="store_true", help="Replace an existing generated episode directory.")
    args = parser.parse_args()

    campaign_dir = Path(args.campaign).expanduser().resolve()
    storyboard = load_json(campaign_dir / "storyboard.json")
    visual_plan = load_json(campaign_dir / "visual_plan.json")
    metadata = load_json(campaign_dir / "metadata_package.json")

    if args.out:
        episode_dir = Path(args.out).expanduser().resolve()
    else:
        title = (metadata.get("snippet") or {}).get("title", storyboard["episode_id"])
        episode_dir = Path(args.nichefoundry_root).expanduser().resolve() / "episodes" / f"knowedge-{slug(title)}-{stable_id([storyboard['episode_id'], title])}"

    if episode_dir.exists() and args.force:
        shutil.rmtree(episode_dir)
    episode_dir.mkdir(parents=True, exist_ok=True)

    script_manifest = build_script_manifest(storyboard)
    render_manifest = build_render_manifest(script_manifest)
    visual_manifest = build_visual_manifest(script_manifest, storyboard, visual_plan)
    narration_manifest = build_narration_manifest(script_manifest)
    audio_manifest = build_audio_manifest(script_manifest)

    write_json(episode_dir / "script_manifest.json", script_manifest)
    write_json(episode_dir / "render_manifest.json", render_manifest)
    write_json(episode_dir / "visual_manifest.json", visual_manifest)
    write_json(episode_dir / "narration_manifest.json", narration_manifest)
    write_json(episode_dir / "audio_manifest.json", audio_manifest)
    write_json(episode_dir / "metadata_package.json", metadata)
    write_json(episode_dir / "campaign_source.json", {"campaign_dir": rel(campaign_dir), "promoted_at": utc_now(), "storyboard": storyboard})
    write_markdown(episode_dir, storyboard, metadata)

    receipt = load_json(campaign_dir / "PHASE3_RECEIPT.json")
    receipt["status"] = "episode_packaged"
    receipt["episode"] = {
        "episode_dir": str(episode_dir),
        "episode_id": storyboard["episode_id"],
        "packaged_at": utc_now(),
        "files": [
            "script_manifest.json",
            "render_manifest.json",
            "visual_manifest.json",
            "narration_manifest.json",
            "audio_manifest.json",
            "metadata_package.json",
            "script.md",
            "gamma_input.md",
            "approval_checklist.md",
        ],
    }
    write_json(campaign_dir / "PHASE3_RECEIPT.json", receipt)
    write_json(campaign_dir / "PHASE3_PUSH_RECEIPT.json", {"schema": "knowedge.phase3.push_receipt.v1", **receipt})

    print(json.dumps({"episode_dir": str(episode_dir), "episode_id": storyboard["episode_id"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
