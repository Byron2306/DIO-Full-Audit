#!/usr/bin/env python3
"""Serve the Pictora Image Editor UI on loopback only."""
from __future__ import annotations

import base64
import binascii
import json
import mimetypes
import os
import argparse
import re
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
import sys

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from products.pictora_image_editor import discover_capabilities, run_edit
from products.pictora_studio import JOB_ROOT as STUDIO_JOB_ROOT, discover_studio, queue_status, run_studio_job
from products import pictora_master_library
from products import pictora_master_image_control
from products import pictora_character_canon
from atlas.creative_organ_exploration import creative_organ_projection

UI = ROOT / "sites" / "pictora-image-editor" / "index.html"
JOB_ROOT = ROOT / "deliverables" / "pictora_image_editor" / "jobs"
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
WORKFLOW_STORE = ROOT / "deliverables" / "pictora_image_editor" / "workflows" / "PICTORA_STUDIO_WORKFLOWS.json"
MAX_WORKFLOW_BODY_BYTES = 256 * 1024
MAX_SAVED_WORKFLOWS = 30
WORKFLOW_CONTROL_KEYS = {
    "studioMode", "studioCheckpoint", "studioPrompt", "studioNegative", "studioWidth", "studioHeight",
    "studioSteps", "studioCfg", "studioSampler", "studioScheduler", "studioDenoise", "studioMaskGrow",
    "studioMaskBlend", "studioInpaintContext", "studioInpaintWidth", "studioInpaintHeight",
    "studioDifferential", "studioSeed", "poseStrength", "identityStrength", "identityLoraStrength", "faceReferenceStrength",
    "compositionStrength",
}
WORKFLOW_LOCK = threading.Lock()


def _read_workflow_store() -> list[dict]:
    if not WORKFLOW_STORE.is_file():
        return []
    try:
        value = json.loads(WORKFLOW_STORE.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"Saved workflow store could not be read: {exc}") from exc
    if not isinstance(value, dict):
        raise RuntimeError("Saved workflow store has an invalid document shape.")
    if value.get("schema") != "dio.pictora.studio_workflows.v1" or not isinstance(value.get("workflows"), list):
        raise RuntimeError("Saved workflow store has an unsupported schema.")
    return [row for row in value["workflows"] if isinstance(row, dict) and row.get("id") and row.get("name") and isinstance(row.get("controls"), dict)]


def _write_workflow_store(workflows: list[dict]) -> None:
    WORKFLOW_STORE.parent.mkdir(parents=True, exist_ok=True)
    payload = {"schema": "dio.pictora.studio_workflows.v1", "updated_at": datetime.now(timezone.utc).isoformat(), "workflows": workflows}
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=WORKFLOW_STORE.parent, prefix=".workflows-", suffix=".tmp", delete=False) as handle:
            temp_path = Path(handle.name)
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, WORKFLOW_STORE)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def _starter_workflows() -> list[dict]:
    now = datetime.now(timezone.utc).isoformat()
    common = {
        "studioPrompt": "", "studioNegative": "", "studioSampler": "dpmpp_2m", "studioScheduler": "karras",
        "studioDenoise": "1", "studioMaskGrow": "8", "studioMaskBlend": "16", "studioInpaintContext": "2",
        "studioInpaintWidth": "512", "studioInpaintHeight": "512", "studioDifferential": "1", "studioSeed": "0",
        "poseStrength": "0.85", "identityStrength": "0.8", "identityLoraStrength": "0.6", "faceReferenceStrength": "0.65", "compositionStrength": "0.75",
    }
    templates = [
        ("Realism portrait · SD15", {"studioMode":"generate", "studioCheckpoint":"epicrealism_naturalSinRC1VAE.safetensors", "studioWidth":"640", "studioHeight":"896", "studioSteps":"30", "studioCfg":"6.5"}),
        ("Anime portrait · SD15", {"studioMode":"generate", "studioCheckpoint":"meinamix_meinaV11.safetensors", "studioWidth":"512", "studioHeight":"768", "studioSteps":"28", "studioCfg":"7"}),
        ("Anime scene · SDXL composition", {"studioMode":"generate", "studioCheckpoint":"ponyDiffusionV6XL_v6StartWithThisOne.safetensors", "studioWidth":"1024", "studioHeight":"1024", "studioSteps":"30", "studioCfg":"6"}),
        ("Mask and refine · SD15 inpaint", {"studioMode":"inpaint", "studioCheckpoint":"DreamShaper_8_INPAINTING.inpainting.safetensors", "studioWidth":"512", "studioHeight":"512", "studioSteps":"28", "studioCfg":"7", "studioDenoise":"0.78"}),
    ]
    return [{"id": str(uuid.uuid4()), "name": name, "controls": {**common, **controls}, "created_at": now, "updated_at": now, "source": "starter"}
            for name, controls in templates]


class EditorHandler(BaseHTTPRequestHandler):
    server_version = "DIO-PictoraEditor/0.1"

    def _send(self, status: int, payload: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:  # noqa: N802
        route = urlparse(self.path).path
        if route == "/master-library.js":
            return self._send(200, (UI.parent / "master-library.js").read_bytes(), "text/javascript; charset=utf-8")
        if route == "/api/studio/master-library":
            try:
                return self._json(200, pictora_master_library.catalog())
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                return self._json(503, {"error": "Master catalog unavailable: " + str(exc)})
        thumb_match = re.fullmatch(r"/api/studio/master-library/thumb/([a-f0-9]{16})", route)
        if thumb_match:
            image_data = pictora_master_library.thumbnail(thumb_match.group(1))
            if image_data is None:
                return self._json(404, {"error": "Thumbnail not found"})
            return self._send(200, image_data, "image/jpeg")
        if route == "/api/studio/character-canons":
            try:
                return self._json(200, pictora_character_canon.catalog())
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                return self._json(503, {"error": "Character canon unavailable: " + str(exc)})
        # PICTORA_MASTER_IMAGE_CONTROL_V4: local-only original image access, verified by SHA256.
        if route == "/master-image-controls.js":
            return self._send(200, (UI.parent / "master-image-controls.js").read_bytes(), "text/javascript; charset=utf-8")
        original_match = re.fullmatch(r"/api/studio/master-library/source/([a-f0-9]{16})", route)
        if original_match:
            try:
                payload, mime, image_hash, name = pictora_master_image_control.verified_image(original_match.group(1))
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                return self._json(409, {"error": "Master image unavailable or unverified: " + str(exc)})
            return self._send(200, payload, mime)
        if route == "/api/health":
            return self._json(200, {"state": "READY", "service": "pictora-studio"})
        if route == "/api/atlas/domains":
            return self._json(200, creative_organ_projection("pictora"))
        if route == "/" or route == "/index.html":
            return self._send(200, UI.read_bytes(), "text/html; charset=utf-8")
        if route == "/studio.js":
            return self._send(200, (UI.parent / "studio.js").read_bytes(), "text/javascript; charset=utf-8")
        if route == "/studio.css":
            return self._send(200, (UI.parent / "studio.css").read_bytes(), "text/css; charset=utf-8")
        if route == "/api/capabilities":
            try:
                data = json.dumps(discover_capabilities(), ensure_ascii=False).encode()
                return self._send(200, data, "application/json; charset=utf-8")
            except Exception as exc:
                return self._json(503, {"error": f"Local Pictora capability discovery failed: {exc}"})
        if route == "/api/studio/capabilities":
            try:
                return self._json(200, discover_studio())
            except Exception as exc:
                return self._json(503, {"error": f"Local ComfyUI capability discovery failed: {exc}"})
        if route == "/api/studio/queue":
            try:
                return self._json(200, queue_status())
            except Exception as exc:
                return self._json(503, {"error": f"Local ComfyUI queue is unavailable: {exc}"})
        if route == "/api/studio/workflows":
            try:
                with WORKFLOW_LOCK:
                    if not WORKFLOW_STORE.exists():
                        _write_workflow_store(_starter_workflows())
                    workflows = sorted(_read_workflow_store(), key=lambda row: row.get("updated_at", ""), reverse=True)
            except RuntimeError as exc:
                return self._json(503, {"error": str(exc)})
            return self._json(200, {"schema": "dio.pictora.studio_workflows.v1", "workflows": workflows, "storage": "local_service"})
        if route == "/api/studio/jobs":
            jobs = []
            if STUDIO_JOB_ROOT.is_dir():
                for path in sorted(STUDIO_JOB_ROOT.glob("*/PICTORA_STUDIO_RECEIPT.json"), reverse=True)[:30]:
                    try:
                        row = json.loads(path.read_text(encoding="utf-8"))
                        source = (row.get("original_inputs") or {}).get("source") or {}
                        jobs.append({"job_id": row["job_id"], "state": row["state"], "settings": row.get("settings") or {},
                                     "image_url": f"/api/studio/jobs/{row['job_id']}/result",
                                     "source_url": f"/api/studio/jobs/{row['job_id']}/source" if source else None,
                                     "source_sha256": source.get("sha256")})
                    except (OSError, ValueError, KeyError):
                        continue
            return self._json(200, {"jobs": jobs})
        studio_match = re.fullmatch(r"/api/studio/jobs/([A-Za-z0-9_-]{1,80})/(result|receipt|source)", route)
        if studio_match:
            job_id, kind = studio_match.groups()
            base = STUDIO_JOB_ROOT / job_id
            receipt_path = base / "PICTORA_STUDIO_RECEIPT.json"
            if not receipt_path.is_file():
                return self._json(404, {"error": "Pictora studio job was not found."})
            if kind == "receipt":
                return self._send(200, receipt_path.read_bytes(), "application/json; charset=utf-8")
            try:
                receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
                if kind == "source":
                    source = (receipt.get("original_inputs") or {}).get("source")
                    if not source:
                        return self._json(404, {"error": "This render has no source image."})
                    filename = Path(str(source.get("filename") or "")).name
                    if not filename or filename != source.get("filename"):
                        return self._json(422, {"error": "Source filename in the render receipt is invalid."})
                    path = (base / "inputs" / filename).resolve()
                else:
                    path = (base / receipt["final_output"]["path"]).resolve()
                path.relative_to(base.resolve())
                if path.is_file():
                    return self._send(200, path.read_bytes(), mimetypes.guess_type(path.name)[0] or "application/octet-stream")
            except (OSError, ValueError, KeyError, json.JSONDecodeError):
                pass
            return self._json(404, {"error": "Pictora studio image was not found."})
        match = re.fullmatch(r"/api/jobs/([A-Za-z0-9_-]{1,80})/(result|receipt)", route)
        if match:
            job_id, kind = match.groups()
            base = JOB_ROOT / job_id
            if kind == "receipt":
                path = base / "PICTORA_IMAGE_EDIT_RECEIPT.json"
                if path.is_file():
                    return self._send(200, path.read_bytes(), "application/json; charset=utf-8")
            else:
                receipt_path = base / "PICTORA_IMAGE_EDIT_RECEIPT.json"
                if receipt_path.is_file():
                    try:
                        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
                        path = base / str(receipt["final_output"]["path"])
                        path.resolve().relative_to(base.resolve())
                        if path.is_file():
                            return self._send(200, path.read_bytes(), mimetypes.guess_type(path.name)[0] or "application/octet-stream")
                    except (OSError, ValueError, KeyError, json.JSONDecodeError):
                        pass
            return self._json(404, {"error": "Pictora job artifact was not found."})
        return self._json(404, {"error": "Route not found."})

    def _json(self, status: int, value: dict) -> None:
        self._send(status, json.dumps(value, ensure_ascii=False).encode(), "application/json; charset=utf-8")

    def do_POST(self) -> None:  # noqa: N802
        route = urlparse(self.path).path
        if route == "/api/studio/workflows":
            return self._save_workflow()
        if route == "/api/studio/render":
            return self._studio_render()
        if route != "/api/edit":
            return self._json(404, {"error": "Route not found."})
        try:
            length = int(self.headers.get("Content-Length") or 0)
            if length < 1 or length > MAX_UPLOAD_BYTES * 2:
                return self._json(413, {"error": "Upload is empty or exceeds the 20 MB image limit."})
            request = json.loads(self.rfile.read(length))
            if not isinstance(request, dict):
                return self._json(400, {"error": "Edit request must be an object."})
            if request.get("owner_authorized") is not True:
                return self._json(403, {"error": "Confirm image ownership or permission before editing."})
            try:
                image_bytes = base64.b64decode(str(request.get("image_base64") or ""), validate=True)
            except (binascii.Error, ValueError):
                return self._json(400, {"error": "Image data is invalid."})
            if not image_bytes or len(image_bytes) > MAX_UPLOAD_BYTES:
                return self._json(413, {"error": "Image is empty or exceeds the 20 MB limit."})
            filename = Path(str(request.get("filename") or "upload.png")).name
            suffix = Path(filename).suffix.lower()
            if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
                return self._json(415, {"error": "Use a PNG, JPG or WebP image."})
            edits = dict(request.get("edits") or {})
            with tempfile.TemporaryDirectory(prefix="pictora-editor-") as temp:
                temp_dir = Path(temp)
                source = temp_dir / filename
                source.write_bytes(image_bytes)
                try:
                    with Image.open(source) as image:
                        image.verify()
                except Exception:
                    return self._json(415, {"error": "The selected file is not a readable image."})
                mask = request.get("clone_mask_base64")
                if mask:
                    try:
                        mask_bytes = base64.b64decode(str(mask), validate=True)
                        with Image.open(__import__("io").BytesIO(mask_bytes)) as mask_image:
                            mask_image.verify()
                        (temp_dir / "clone-mask.png").write_bytes(mask_bytes)
                        clone_options = dict(edits.get("clone_stamp") or {})
                        clone_options["mask_path"] = "clone-mask.png"
                        edits["clone_stamp"] = clone_options
                    except Exception:
                        return self._json(400, {"error": "Clone brush mask could not be read."})
                result = run_edit(
                    source, JOB_ROOT, edits=edits,
                    ai_operations=list(request.get("ai_operations") or []),
                    owner_authorized=True,
                )
            receipt = result["manifest"]
            return self._json(200, {
                "job_id": result["job_id"],
                "image_url": f"/api/jobs/{result['job_id']}/result",
                "receipt_url": f"/api/jobs/{result['job_id']}/receipt",
                "receipt_sha256": receipt["final_output"]["sha256"],
                "human_review_required": True,
            })
        except Exception as exc:
            return self._json(422, {"error": str(exc)})

    def _studio_render(self) -> None:
        try:
            length = int(self.headers.get("Content-Length") or 0)
            if length < 1 or length > MAX_UPLOAD_BYTES * 6:
                return self._json(413, {"error": "Studio request is empty or too large."})
            request = json.loads(self.rfile.read(length))
            if request.get("owner_authorized") is not True:
                return self._json(403, {"error": "Confirm rights or permission for all source and reference images."})
            inputs = request.get("images") or {}
            if not isinstance(inputs, dict) or set(inputs) - {"source", "mask", "pose", "identity", "composition", "face_reference"}:
                return self._json(400, {"error": "Unsupported reference image role."})
            with tempfile.TemporaryDirectory(prefix="pictora-studio-") as temp:
                references = {}
                for role, image in inputs.items():
                    if not isinstance(image, dict):
                        return self._json(400, {"error": f"{role} image is invalid."})
                    raw = base64.b64decode(str(image.get("base64") or ""), validate=True)
                    if not raw or len(raw) > MAX_UPLOAD_BYTES:
                        return self._json(413, {"error": f"{role} image exceeds the 20 MB limit."})
                    suffix = Path(str(image.get("filename") or "image.png")).suffix.lower()
                    if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
                        return self._json(415, {"error": f"{role} must be PNG, JPG, or WebP."})
                    path = Path(temp) / (role + suffix)
                    path.write_bytes(raw)
                    with Image.open(path) as opened:
                        opened.verify()
                    references[role] = path
                receipt = run_studio_job(dict(request.get("settings") or {}), references, owner_authorized=True)
            job_id = receipt["job_id"]
            source = (receipt.get("original_inputs") or {}).get("source") or {}
            return self._json(200, {"job_id": job_id, "image_url": f"/api/studio/jobs/{job_id}/result",
                                   "source_url": f"/api/studio/jobs/{job_id}/source" if source else None,
                                   "source_sha256": source.get("sha256"),
                                   "receipt_url": f"/api/studio/jobs/{job_id}/receipt", "receipt_sha256": receipt["final_output"]["sha256"], "human_review_required": True})
        except (ValueError, binascii.Error, OSError, KeyError) as exc:
            return self._json(422, {"error": str(exc)})
        except Exception as exc:
            return self._json(503, {"error": f"Local render failed: {exc}"})

    def _save_workflow(self) -> None:
        try:
            length = int(self.headers.get("Content-Length") or 0)
            if not 1 <= length <= MAX_WORKFLOW_BODY_BYTES:
                return self._json(413, {"error": "Workflow settings are empty or too large."})
            request = json.loads(self.rfile.read(length))
            if not isinstance(request, dict):
                return self._json(400, {"error": "Workflow request must be an object."})
            name = str(request.get("name") or "").strip()
            controls = request.get("controls")
            if not name or len(name) > 48:
                return self._json(400, {"error": "Workflow name must contain 1–48 characters."})
            if not isinstance(controls, dict) or not controls:
                return self._json(400, {"error": "Workflow settings are missing."})
            unknown = set(controls) - WORKFLOW_CONTROL_KEYS
            if unknown:
                return self._json(400, {"error": "Workflow contains unsupported settings."})
            clean_controls = {}
            for key, value in controls.items():
                if not isinstance(value, (str, int, float, bool)):
                    return self._json(400, {"error": f"Workflow setting {key} must be a simple value."})
                clean_value = str(value)
                if len(clean_value) > 16000:
                    return self._json(413, {"error": f"Workflow setting {key} is too large."})
                clean_controls[key] = clean_value
            if len(json.dumps(clean_controls, ensure_ascii=False).encode("utf-8")) > MAX_WORKFLOW_BODY_BYTES // 2:
                return self._json(413, {"error": "Workflow settings exceed the saved size limit."})

            with WORKFLOW_LOCK:
                workflows = _read_workflow_store()
                existing = next((row for row in workflows if str(row.get("name", "")).casefold() == name.casefold()), None)
                if existing is None and len(workflows) >= MAX_SAVED_WORKFLOWS:
                    starter = next((row for row in workflows if row.get("source") == "starter"), None)
                    if starter is None:
                        return self._json(409, {"error": f"Pictora stores at most {MAX_SAVED_WORKFLOWS} named workflows."})
                    workflows.remove(starter)
                now = datetime.now(timezone.utc).isoformat()
                workflow = {"id": existing["id"] if existing else str(uuid.uuid4()), "name": name, "controls": clean_controls,
                            "created_at": existing.get("created_at", now) if existing else now, "updated_at": now, "source": "user"}
                workflows = [row for row in workflows if row.get("id") != workflow["id"]]
                workflows.insert(0, workflow)
                _write_workflow_store(workflows)
            return self._json(200, {"workflow": workflow, "storage": "local_service"})
        except (ValueError, json.JSONDecodeError) as exc:
            return self._json(400, {"error": f"Invalid workflow: {exc}"})
        except RuntimeError as exc:
            return self._json(503, {"error": str(exc)})
        except OSError as exc:
            return self._json(503, {"error": f"Could not persist workflow: {exc}"})

    def do_DELETE(self) -> None:  # noqa: N802
        route = urlparse(self.path).path
        match = re.fullmatch(r"/api/studio/workflows/([0-9a-f-]{36})", route)
        if not match:
            return self._json(404, {"error": "Workflow route not found."})
        workflow_id = match.group(1)
        try:
            with WORKFLOW_LOCK:
                workflows = _read_workflow_store()
                kept = [row for row in workflows if row.get("id") != workflow_id]
                if len(kept) == len(workflows):
                    return self._json(404, {"error": "Saved workflow was not found."})
                _write_workflow_store(kept)
        except (OSError, RuntimeError) as exc:
            return self._json(503, {"error": f"Could not delete workflow: {exc}"})
        return self._json(200, {"deleted": workflow_id, "storage": "local_service"})

    def log_message(self, format: str, *args) -> None:
        print("pictora-editor", self.address_string(), format % args)


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve the local Pictora studio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PICTORA_PORT", "42153")))
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "localhost"}:
        parser.error("Pictora studio only binds to loopback")
    server = ThreadingHTTPServer((args.host, args.port), EditorHandler)
    print(f"Pictora Image Editor is local at http://127.0.0.1:{server.server_address[1]}")
    print("Images are processed on this machine; Ctrl+C stops the service.")
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
