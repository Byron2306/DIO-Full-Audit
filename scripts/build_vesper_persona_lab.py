#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters.lingua.persona_lab import load_persona_lab


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True).encode("utf-8")).hexdigest()


def _avatar_request(lab: dict[str, Any], avatar_id: str, avatar: dict[str, Any]) -> dict[str, Any]:
    identity = lab.get("identity_invariants") or {}
    return {
        "schema": "dio.nichefoundry.vesper_avatar_request.v1",
        "request_id": "VESPER-AVATAR-" + _digest({"experiment": lab["experiment_id"], "avatar": avatar_id})[:16].upper(),
        "created_at": _now(),
        "experiment_id": lab["experiment_id"],
        "product": "vesper",
        "asset_role": "public_presence_avatar_experiment",
        "avatar_id": avatar_id,
        "label": avatar.get("label"),
        "design_class": avatar.get("design_class"),
        "creative_brief": {
            "visual_hypothesis": avatar.get("visual_hypothesis"),
            "expression_policy": avatar.get("expression_policy"),
            "background_policy": avatar.get("background_policy"),
            "photorealism": avatar.get("photorealism"),
            "brand_feel": [
                "clean commercial professional",
                "South African market-native without tourism symbolism",
                "credible in education, SME, NGO, GRC and AI-governance contexts",
                "bright ivory/graphite/teal family with restrained amber accent",
            ],
        },
        "deliverables": [
            {"kind": "profile_avatar", "size": "1024x1024", "format": "png"},
            {"kind": "webchat_portrait", "size": "1024x1280", "format": "png"},
            {"kind": "social_profile", "size": "1080x1080", "format": "png"},
            {"kind": "reel_intro_frame", "size": "1080x1920", "format": "png"},
        ],
        "identity_constraints": {
            "name": identity.get("name", "Vesper"),
            "role": identity.get("role", "DIO Presence Core"),
            "must_disclose_ai": True,
            "must_not_resemble_or_impersonate_specific_real_person": True,
            "must_not_claim_human_identity": True,
            "face_is_rendering_only": True,
        },
        "experiment_constraints": {
            "stable_for_conversation": True,
            "no_mid_conversation_avatar_swap": True,
            "human_review_before_public_default": True,
            "automatic_publication": False,
            "automatic_spend": False,
        },
        "release": {"state": "held", "human_approval_required": True},
    }


def build(root: Path, output: Path) -> dict[str, Any]:
    lab = load_persona_lab(root)
    output.mkdir(parents=True, exist_ok=True)
    avatar_requests = []
    for avatar_id, avatar in (lab.get("avatars") or {}).items():
        request = _avatar_request(lab, avatar_id, avatar)
        folder = output / "avatars" / avatar_id
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / "NICHEFOUNDRY_AVATAR_REQUEST.json"
        path.write_text(json.dumps(request, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
        avatar_requests.append({"avatar_id": avatar_id, "request_path": str(path), "request_id": request["request_id"]})

    matrix = {
        "schema": "dio.vesper.persona_experiment_matrix.v1",
        "experiment_id": lab["experiment_id"],
        "created_at": _now(),
        "cells": lab.get("initial_cells") or [],
        "personas": lab.get("personas") or {},
        "avatars": {key: {"label": value.get("label"), "design_class": value.get("design_class")} for key, value in (lab.get("avatars") or {}).items()},
        "voice_candidates": lab.get("voice_candidates") or {},
        "outcome_metrics": lab.get("outcome_metrics") or [],
        "promotion": lab.get("promotion") or {},
        "real_time_adaptation_boundary": lab.get("real_time_adaptation_boundary") or {},
        "automatic_promotion": False,
        "human_approval_required": True,
    }
    matrix_path = output / "VESPER_PERSONA_EXPERIMENT_MATRIX.json"
    matrix_path.write_text(json.dumps(matrix, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    voice_script = {
        "schema": "dio.vesper.voice_reference_script.v1",
        "experiment_id": lab["experiment_id"],
        "purpose": "Reference and evaluation script for reviewed Vesper voice candidates.",
        "script": [
            "Hello, I’m Vesper, DIO’s AI presence layer. I can help you find the right workflow and explain what happens next.",
            "I can show you the evidence behind a claim, but I will not invent a result or pretend an approval has happened.",
            "If something is unclear, tell me what part is getting in the way and I’ll explain it more simply.",
            "Your request can be captured for human review without creating payment, delivery, legal, academic, or professional authority.",
            "When a deadline matters, I’ll separate what is known, what still needs evidence, and the next action you can take.",
        ],
        "recording_guidance": {
            "environment": "quiet dry room",
            "delivery": "natural professional South African English; no theatrical character voice",
            "pace": "moderate",
            "emotion": "restrained warmth",
            "format": "mono WAV preferred",
            "consent": "explicit speaker consent and provenance receipt required before embedding extraction",
        },
    }
    voice_path = output / "VESPER_VOICE_REFERENCE_SCRIPT.json"
    voice_path.write_text(json.dumps(voice_script, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    registry = {
        "schema": "dio.vesper.persona_lab_build.v1",
        "built_at": _now(),
        "experiment_id": lab["experiment_id"],
        "avatar_request_count": len(avatar_requests),
        "avatar_requests": avatar_requests,
        "matrix_path": str(matrix_path),
        "voice_reference_script_path": str(voice_path),
        "external_actions_executed": False,
        "assets_generated": False,
        "publication_authorized": False,
        "spend_authorized": False,
        "build_sha256": _digest({"avatars": avatar_requests, "matrix": matrix}),
    }
    registry_path = output / "VESPER_PERSONA_LAB_BUILD.json"
    registry_path.write_text(json.dumps(registry, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return registry


def main() -> int:
    parser = argparse.ArgumentParser(description="Build held NicheFoundry briefs for the Vesper Persona Lab.")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, default=ROOT / "state" / "vesper_persona_lab")
    args = parser.parse_args()
    registry = build(args.root.resolve(), args.output.resolve())
    print(json.dumps(registry, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
