"""DIO Dicere: bounded local audiovisual performance organ."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any
from datetime import datetime, timezone

BASE = Path("/data/byron/lilith-local/vesper-github-lipsync")

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "media/dicere/debut"
BUILD_SCRIPT = Path(__file__).resolve().parents[1] / "scripts/build_dicere_debut.py"

ARTIFACTS = {
    "musetalk_speech_v15": BASE / "results/v15/VESPER_VERA_V15_SPEECH.mp4",
    "dicere_matched_musetalk": BASE / "results/dicere/v15/DICERE_DEBUT_VERA_MUSETALK.mp4",
    "unified_speech_v2": BASE / (
        "presence/unified-v2/VESPER_UNIFIED_VERA_V2.mp4"
    ),
    "living_presence_v2": BASE / "motion-tests/VESPER_CANONICAL_RGB--vesper_living_presence_v2_12s.mp4",
    "two_blinks_v2": BASE / "motion-tests/VESPER_CANONICAL_RGB--vesper_two_blinks_8s.mp4",
    "debut_narration": OUTPUT_DIR / "dicere_vera_narration.wav",
    "sonoris_darksynth_score": Path(__file__).resolve().parents[1] / "media/product_asset_packs/dio_creative_organs_site_matched_v2/receipts/SONORIS_DARKSYNTH_AMBIENT_V2_45S.wav",
    "gold_vesper_panel": Path(__file__).resolve().parents[1] / "media/product_asset_packs/homs_corpo_cult_v1/vesper/DIO_VESPER_MARKET_PANEL.png",
    "debut_video": OUTPUT_DIR / "DICERE_DEBUT_EXPLAINER_V19.mp4",
    "debut_receipt": OUTPUT_DIR / "DICERE_DEBUT_EXPLAINER_V19.receipt.json",
}

def sha256(path: Path) -> str:
    h = hashlib.sha256()

    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)

    return h.hexdigest()


def capability_snapshot() -> dict[str, Any]:
    artifacts = {}

    for name, path in ARTIFACTS.items():
        if name in {"debut_video", "debut_receipt"}:
            suffix = ".mp4" if name == "debut_video" else ".receipt.json"
            candidates = OUTPUT_DIR.glob("DICERE_DEBUT_EXPLAINER_*" + suffix)
            latest = max(candidates, key=lambda candidate: candidate.stat().st_mtime, default=None)
            if latest is not None:
                path = latest
        present = path.is_file() and path.stat().st_size > 0

        artifacts[name] = {
            "path": str(path),
            "present": present,
            "size": path.stat().st_size if present else 0,
            "sha256": sha256(path) if present else None,
        }

    return {
        "schema": "dio.dicere.capability_snapshot.v1",
        "organ_id": "dicere",
        "state": "LOCAL_REVIEW_CANDIDATE" if any(OUTPUT_DIR.glob("DICERE_DEBUT_EXPLAINER_*.mp4")) else "LOCAL_RENDER_AVAILABLE",
        "runtime": str(BASE),
        "capabilities": [
            "speech_performance",
            "presence_animation",
            "unified_audiovisual_composition",
            "local_debut_video_render",
            "musetalk_speech_source",
            "living_presence_and_blink_performance",
        ],
        "artifacts": artifacts,
        "execution_admitted": True,
        "execution_scope": "local render only; human review required",
        "publication_authorized": False,
        "commercial_validation": "UNPROVED",
    }


def inspect() -> dict[str, Any]:
    return capability_snapshot()


def run_job(
    job: dict[str, Any],
    *,
    execute: bool = False,
    owner_authorized: bool = False,
) -> dict[str, Any]:
    """Render a bounded local Dicere debut candidate; never publish it."""
    receipt: dict[str, Any] = {
        "schema": "dio.dicere.job_receipt.v1",
        "organ_id": "dicere",
        "requested_job": job,
        "execution_requested": execute,
        "owner_authorized": owner_authorized,
        "publication_authorized": False,
    }
    if not execute or not owner_authorized:
        return {**receipt, "state": "REFUSE_EXECUTION_NOT_AUTHORIZED"}

    kind = job.get("kind", "debut_explainer")
    if kind != "debut_explainer":
        return {**receipt, "state": "REFUSE_UNSUPPORTED_JOB_KIND"}

    output_name = str(job.get("output_name") or (
        "DICERE_DEBUT_EXPLAINER_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + ".mp4"
    ))
    if Path(output_name).name != output_name or not output_name.lower().endswith(".mp4"):
        return {**receipt, "state": "REFUSE_INVALID_OUTPUT_NAME"}
    output = OUTPUT_DIR / output_name
    if output.exists():
        return {**receipt, "state": "REFUSE_OUTPUT_ALREADY_EXISTS", "output": str(output)}

    result = subprocess.run(
        [sys.executable, str(BUILD_SCRIPT), "--output", str(output)],
        capture_output=True, text=True, timeout=1500, check=False,
    )
    if result.returncode != 0:
        return {**receipt, "state": "LOCAL_RENDER_FAILED", "stderr": result.stderr[-4000:]}
    try:
        build_result = json.loads(result.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        build_result = {"output": str(output)}
    return {
        **receipt,
        "state": "LOCAL_REVIEW_CANDIDATE",
        "build": build_result,
        "human_review_required": True,
        "publication_authorized": False,
        "authority_created": False,
    }
