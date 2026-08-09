#!/usr/bin/env python3
from __future__ import annotations

import json
import fcntl
import subprocess
from pathlib import Path
from typing import Any

from scripts.build_operator_dashboard import utc_now, write_json
from scripts.manage_mail_intent import emit_event


ROOT = Path(__file__).resolve().parents[1]
NICHEFOUNDRY_ROOT = ROOT.parent / "NicheFoundry_Phase11"
REGISTRY_PATH = ROOT / "deliverables" / "dio_video_candidates" / "DIO_VIDEO_CANDIDATE_REGISTRY.json"
EVENT_LOG = ROOT / "telemetry" / "dio_events.jsonl"
REVIEW_GATES = (
    "video_watch_through_approved",
    "voice_approved",
    "thumbnail_approved",
    "metadata_approved",
)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_candidate(episode_id: str) -> tuple[dict[str, Any], dict[str, Any], Path]:
    if not episode_id or not all(char.isalnum() or char == "-" for char in episode_id):
        raise ValueError("Invalid video candidate id.")
    registry = read_json(REGISTRY_PATH)
    item = next((value for value in registry.get("candidates", []) if value.get("episode_id") == episode_id), None)
    if not item:
        raise ValueError("Video candidate does not exist.")
    candidate_path = Path(str(item.get("candidate") or "")).resolve()
    if not candidate_path.is_file() or NICHEFOUNDRY_ROOT not in candidate_path.parents:
        raise ValueError("Video candidate path is invalid.")
    return registry, item, candidate_path


def refresh_registry_item(registry: dict[str, Any], item: dict[str, Any], candidate: dict[str, Any]) -> None:
    item["status"] = candidate.get("status")
    item["gates"] = candidate.get("gates") or {}
    item["private_upload_ready"] = bool(
        item.get("preflight_passed")
        and all((candidate.get("gates") or {}).get(gate) is True for gate in REVIEW_GATES)
        and not candidate.get("youtube")
    )
    item["youtube"] = candidate.get("youtube")
    registry["generated_at"] = utc_now()
    registry.setdefault("counts", {})["private_upload_ready"] = sum(
        bool(value.get("private_upload_ready")) for value in registry.get("candidates", [])
    )
    registry["counts"]["awaiting_human_review"] = sum(
        value.get("status") == "human_review_required" for value in registry.get("candidates", [])
    )
    registry["counts"]["uploaded_private"] = sum(
        value.get("status") == "uploaded_private_verified" for value in registry.get("candidates", [])
    )
    write_json(REGISTRY_PATH, registry)


def approve_review(episode_id: str, actor: str) -> dict[str, Any]:
    registry, item, candidate_path = resolve_candidate(episode_id)
    candidate = read_json(candidate_path)
    if not item.get("preflight_passed"):
        raise ValueError("Video review cannot be approved until publishing preflight passes.")
    if candidate.get("youtube"):
        raise ValueError("Video has already been uploaded.")
    approved_at = utc_now()
    gates = candidate.setdefault("gates", {})
    for gate in REVIEW_GATES:
        gates[gate] = True
    candidate["review_approval"] = {
        "state": "approved",
        "approved_at": approved_at,
        "approved_by": actor,
        "attestation": "Operator watched the complete film and approved voice, thumbnail, and metadata.",
    }
    candidate["status"] = "review_approved_private_upload_ready"
    write_json(candidate_path, candidate)
    write_json(
        candidate_path.parent / "final_signoff_bundle.json",
        {
            "schema": "dio.campaign_film.final_signoff.v1",
            "episode_id": episode_id,
            "valid": True,
            "approved_at": approved_at,
            "approved_by": actor,
            "approved_gates": list(REVIEW_GATES),
            "release_scope": "private_youtube_upload_only",
        },
    )
    refresh_registry_item(registry, item, candidate)
    emit_event(EVENT_LOG, "video.review_approved", "info", "video", episode_id, {"scope": "private_upload"})
    return candidate


def _upload_private_locked(episode_id: str, actor: str) -> dict[str, Any]:
    registry, item, candidate_path = resolve_candidate(episode_id)
    candidate = read_json(candidate_path)
    if candidate.get("youtube"):
        return candidate
    missing = [gate for gate in REVIEW_GATES if (candidate.get("gates") or {}).get(gate) is not True]
    if missing:
        raise ValueError("Approve the reviewed film before private upload.")
    candidate.setdefault("gates", {})["youtube_upload_authorised"] = True
    candidate["upload_authority"] = {
        "state": "authorised",
        "authorised_at": utc_now(),
        "authorised_by": actor,
        "scope": "private_upload_only",
    }
    candidate["status"] = "private_upload_in_progress"
    write_json(candidate_path, candidate)
    refresh_registry_item(registry, item, candidate)
    emit_event(EVENT_LOG, "video.private_upload_authorised", "action", "video", episode_id, {"scope": "private"})
    command = [
        "npm",
        "run",
        "upload:dio-publication",
        "--",
        "--episode-id",
        episode_id,
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=NICHEFOUNDRY_ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=240,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        candidate = read_json(candidate_path)
        candidate["status"] = "private_upload_failed"
        candidate["last_error"] = (getattr(exc, "stderr", None) or str(exc))[-2000:]
        write_json(candidate_path, candidate)
        registry, item, _ = resolve_candidate(episode_id)
        refresh_registry_item(registry, item, candidate)
        emit_event(EVENT_LOG, "video.private_upload_failed", "critical", "video", episode_id, {"error": candidate["last_error"]})
        raise ValueError(f"Private YouTube upload failed: {candidate['last_error']}") from exc
    candidate = read_json(candidate_path)
    emit_event(EVENT_LOG, "video.private_upload_verified", "info", "video", episode_id, {"youtube": candidate.get("youtube")})
    return {"candidate": candidate, "publisher_output": completed.stdout[-4000:]}


def upload_private(episode_id: str, actor: str) -> dict[str, Any]:
    lock_path = ROOT / "state" / "video_release_locks" / f"{episode_id}.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("This film already has a private upload in progress. Wait for the current request to finish.") from exc
        try:
            return _upload_private_locked(episode_id, actor)
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def release_public(episode_id: str, actor: str) -> dict[str, Any]:
    lock_path = ROOT / "state" / "video_release_locks" / f"{episode_id}.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("This film already has a YouTube operation in progress.") from exc
        registry, item, candidate_path = resolve_candidate(episode_id)
        candidate = read_json(candidate_path)
        if (candidate.get("youtube") or {}).get("privacy_status") == "public":
            return candidate
        if not (candidate.get("youtube") or {}).get("verification_passed"):
            raise ValueError("A verified private upload is required before public release.")
        emit_event(EVENT_LOG, "video.public_release_authorised", "action", "video", episode_id, {"authorised_by": actor})
        command = ["npm", "run", "release:dio-publication", "--", "--episode-id", episode_id]
        try:
            completed = subprocess.run(
                command,
                cwd=NICHEFOUNDRY_ROOT,
                check=True,
                capture_output=True,
                text=True,
                timeout=120,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            error = (getattr(exc, "stderr", None) or str(exc))[-2000:]
            emit_event(EVENT_LOG, "video.public_release_failed", "critical", "video", episode_id, {"error": error})
            raise ValueError(f"Public YouTube release failed: {error}") from exc
        candidate = read_json(candidate_path)
        emit_event(EVENT_LOG, "video.published_public_verified", "info", "video", episode_id, {"youtube": candidate.get("youtube")})
        return {"candidate": candidate, "publisher_output": completed.stdout[-4000:]}
