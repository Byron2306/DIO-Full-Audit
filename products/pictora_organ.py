"""Local ComfyUI adapter for Pictora and DIO visual-media workflows.

This module deliberately accepts ComfyUI API-format workflows. It never selects
models or uploads to a hosted service on the caller's behalf. Inputs, workflow,
seed/model choices, and local review remain explicit.
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Mapping

DEFAULT_URL = "http://127.0.0.1:8188"
ROOT = Path(__file__).resolve().parents[1]


class PictoraError(RuntimeError):
    pass


def _base_url(endpoint: str | None = None) -> str:
    raw = (endpoint or os.environ.get("DIO_COMFYUI_URL") or DEFAULT_URL).rstrip("/")
    parsed = urllib.parse.urlparse(raw)
    if parsed.scheme != "http" or not parsed.hostname or parsed.username or parsed.password:
        raise PictoraError("Pictora only accepts a plain HTTP local ComfyUI endpoint")
    try:
        local = parsed.hostname.lower() == "localhost" or ipaddress.ip_address(parsed.hostname).is_loopback
    except ValueError:
        local = False
    if not local:
        raise PictoraError("ComfyUI endpoint must resolve to localhost/loopback; remote processing is disabled")
    return raw


def _request(base: str, path: str, *, data: bytes | None = None, headers: Mapping[str, str] | None = None,
             timeout: int = 30) -> bytes:
    req = urllib.request.Request(base + path, data=data, headers=dict(headers or {}))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.read()
    except Exception as exc:
        raise PictoraError(f"ComfyUI request failed for {path}: {exc}") from exc


def discover(endpoint: str | None = None) -> dict[str, Any]:
    """Return a live, read-only local capability snapshot without queuing work."""
    base = _base_url(endpoint)
    stats = json.loads(_request(base, "/system_stats"))
    object_info = json.loads(_request(base, "/object_info", timeout=60))
    system = stats.get("system", {})
    nodes = sorted(object_info)
    return {
        "schema": "dio.pictora.capability_snapshot.v1", "endpoint": base,
        "state": "AVAILABLE", "comfyui_version": system.get("comfyui_version"),
        "python_version": system.get("python_version"), "devices": stats.get("devices", []),
        "node_count": len(nodes), "available_nodes": nodes,
        "capability_hints": {
            "text_to_image": any(n in object_info for n in ("KSampler", "SamplerCustomAdvanced")),
            "image_editing": "LoadImage" in object_info,
            "upscaling": any("Upscale" in n for n in nodes),
            "face_geometry": all(n in object_info for n in ("MediaPipeFaceLandmarker", "MediaPipeFaceMask")),
            "depth_or_pose_conditioning": any("Depth" in n or "Pose" in n or "OpenPose" in n for n in nodes),
        },
        "remote_processing": False,
    }


def upload_image(image_path: str | Path, *, endpoint: str | None = None, subfolder: str = "dio-pictora-inputs") -> dict[str, Any]:
    """Upload a caller-authorized image to the local ComfyUI input store."""
    base = _base_url(endpoint)
    path = Path(image_path).resolve()
    if not path.is_file():
        raise PictoraError(f"image input does not exist: {path}")
    boundary = "----DIOPictoraBoundary7MA4YWxkTrZu0gW"
    name = path.name.replace('"', "")
    payload = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{name}\"\r\n"
               f"Content-Type: application/octet-stream\r\n\r\n").encode() + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    query = urllib.parse.urlencode({"subfolder": subfolder, "type": "input", "overwrite": "true"})
    result = json.loads(_request(base, f"/upload/image?{query}", data=payload,
                                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}, timeout=120))
    return {"input": result, "source_path": str(path), "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def submit(workflow: Mapping[str, Any], *, output_dir: str | Path,
           owner_authorized: bool, endpoint: str | None = None, client_id: str = "dio-pictora",
           source_receipts: list[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    """Queue an explicit API-format workflow against local ComfyUI.

    Workflow author controls checkpoint, LoRA, prompt, dimensions and seed. This
    adapter records the exact submitted workflow and makes no release decision.
    """
    if owner_authorized is not True:
        raise PictoraError("owner_authorized=true is required for local source/model processing")
    if not isinstance(workflow, Mapping) or not workflow:
        raise PictoraError("workflow must be a non-empty ComfyUI API-format node mapping")
    if any(not isinstance(node, Mapping) or "class_type" not in node for node in workflow.values()):
        raise PictoraError("workflow must use ComfyUI API format (node entries need class_type)")
    if source_receipts is not None and (not isinstance(source_receipts, list) or any(not isinstance(row, Mapping) for row in source_receipts)):
        raise PictoraError("source_receipts must be a list of source provenance objects")
    out = Path(output_dir).resolve()
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise PictoraError("Pictora output directory must be empty")
    out.mkdir(parents=True, exist_ok=True)
    base = _base_url(endpoint)
    body = json.dumps({"prompt": workflow, "client_id": client_id}, separators=(",", ":")).encode()
    response = json.loads(_request(base, "/prompt", data=body, headers={"Content-Type": "application/json"}, timeout=60))
    prompt_id = response.get("prompt_id")
    if not prompt_id:
        raise PictoraError(f"ComfyUI did not accept workflow: {response}")
    receipt = {
        "schema": "dio.pictora.job_receipt.v1", "job_id": str(prompt_id), "state": "QUEUED",
        "endpoint": base, "workflow_sha256": hashlib.sha256(body).hexdigest(),
        "workflow": workflow, "output_dir": str(out), "owner_authorized": True,
        "execution_location": "local_comfyui", "remote_processing": False,
        "source_receipts": [dict(row) for row in (source_receipts or [])],
        "human_review_required": True, "commercial_validation": "UNPROVED",
        "release_authorized": False,
    }
    (out / "PICTORA_JOB_RECEIPT.json").write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return receipt


def collect(job_id: str, *, output_dir: str | Path, endpoint: str | None = None,
            timeout_seconds: int = 1800, poll_interval: float = 2.0) -> dict[str, Any]:
    """Wait for a queued job and fetch generated image artifacts locally."""
    base = _base_url(endpoint)
    out = Path(output_dir).resolve()
    receipt_path = out / "PICTORA_JOB_RECEIPT.json"
    if not receipt_path.is_file():
        raise PictoraError("missing PICTORA_JOB_RECEIPT.json for this output directory")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if str(receipt.get("job_id")) != str(job_id):
        raise PictoraError("job_id does not match the receipt in this output directory")
    if receipt.get("endpoint") != base:
        raise PictoraError("collection endpoint does not match the endpoint recorded when this job was queued")
    started = time.monotonic()
    history = None
    while time.monotonic() - started <= timeout_seconds:
        data = json.loads(_request(base, "/history/" + urllib.parse.quote(str(job_id), safe=""), timeout=60))
        history = data.get(str(job_id))
        if history:
            break
        time.sleep(max(.2, poll_interval))
    if not history:
        receipt["state"] = "TIMEOUT"
        receipt["error"] = f"No history result after {timeout_seconds}s; queued/running job may continue locally."
        receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return receipt
    status = history.get("status", {})
    if status.get("status_str") == "error" or status.get("completed") is False:
        receipt["state"] = "FAILED"
        receipt["comfy_status"] = status
        receipt["outputs"] = history.get("outputs", {})
    else:
        artifacts = []
        for node_id, node_out in (history.get("outputs") or {}).items():
            for image in node_out.get("images", []):
                query = urllib.parse.urlencode({"filename": image["filename"], "subfolder": image.get("subfolder", ""), "type": image.get("type", "output")})
                payload = _request(base, "/view?" + query, timeout=120)
                suffix = Path(image["filename"]).suffix or ".png"
                filename = f"node-{node_id}-{len(artifacts)+1}{suffix}"
                dest = out / filename
                dest.write_bytes(payload)
                artifacts.append({"path": filename, "sha256": hashlib.sha256(payload).hexdigest(),
                                  "bytes": len(payload), "source_node": str(node_id), "comfy_image": image})
        receipt["state"] = "COMPLETE" if artifacts else "COMPLETE_NO_IMAGES"
        receipt["artifacts"] = artifacts
        receipt["comfy_status"] = status
    receipt["human_review_required"] = True
    receipt["release_authorized"] = False
    receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return receipt
