#!/usr/bin/env python3
"""Loopback Dicere audiovisual studio for local review and renders."""
from __future__ import annotations

import json
import os
import re
import sys
import threading
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "media/dicere/debut"
UI = ROOT / "sites/dicere-studio"
sys.path.insert(0, str(ROOT))
from products import dicere_organ

MAX_BODY = 8192
JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()
RENDER_LOCK = threading.Lock()


def public_job(row: dict) -> dict:
    return {k: v for k, v in row.items() if k != "thread"}


def render(job_id: str, output_name: str) -> None:
    with RENDER_LOCK:
        with JOBS_LOCK:
            JOBS[job_id]["state"] = "RENDERING"
            JOBS[job_id]["started_utc"] = datetime.now(timezone.utc).isoformat()
        result = dicere_organ.run_job(
            {"kind": "debut_explainer", "output_name": output_name},
            execute=True,
            owner_authorized=True,
        )
        with JOBS_LOCK:
            JOBS[job_id].update({"state": result.get("state"), "result": result,
                                 "finished_utc": datetime.now(timezone.utc).isoformat()})


class Handler(BaseHTTPRequestHandler):
    server_version = "DicereStudio/1.0"

    def send_bytes(self, status: int, body: bytes, mime: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, status: int, value: dict) -> None:
        self.send_bytes(status, json.dumps(value, ensure_ascii=False).encode(), "application/json; charset=utf-8")

    def do_GET(self) -> None:
        path = unquote(urlparse(self.path).path)
        if path in {"/", "/index.html"}:
            return self.send_bytes(200, (UI / "index.html").read_bytes(), "text/html; charset=utf-8")
        if path == "/studio.css":
            return self.send_bytes(200, (UI / "studio.css").read_bytes(), "text/css; charset=utf-8")
        if path == "/studio.js":
            return self.send_bytes(200, (UI / "studio.js").read_bytes(), "text/javascript; charset=utf-8")
        if path.startswith("/fonts/"):
            name = Path(path.removeprefix("/fonts/")).name
            if not re.fullmatch(r"[A-Za-z0-9_.-]+\.ttf", name):
                return self.send_json(400, {"error": "Invalid font path."})
            font_file = (UI / "fonts" / name).resolve()
            if font_file.parent != (UI / "fonts").resolve() or not font_file.is_file():
                return self.send_json(404, {"error": "Font not found."})
            return self.send_bytes(200, font_file.read_bytes(), "font/ttf")
        if path == "/api/studio":
            artifacts = dicere_organ.capability_snapshot()
            outputs = []
            for file in sorted(OUT.glob("DICERE_DEBUT_EXPLAINER_*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True):
                outputs.append({"name": file.name, "bytes": file.stat().st_size, "url": "/media/" + file.name,
                                "receipt": "/media/" + file.with_suffix(".receipt.json").name})
            with JOBS_LOCK:
                jobs = [public_job(row) for row in JOBS.values()]
            return self.send_json(200, {"studio": "dicere", "capabilities": artifacts,
                                        "outputs": outputs, "jobs": jobs})
        if path.startswith("/media/"):
            name = Path(path.removeprefix("/media/")).name
            if not re.fullmatch(r"[A-Za-z0-9_.-]+", name):
                return self.send_json(400, {"error": "Invalid media path."})
            file = (OUT / name).resolve()
            if file.parent != OUT.resolve() or not file.is_file():
                return self.send_json(404, {"error": "Media not found."})
            mime = "video/mp4" if file.suffix == ".mp4" else "application/json" if file.suffix == ".json" else "audio/wav" if file.suffix == ".wav" else "image/png" if file.suffix == ".png" else "application/octet-stream"
            data = file.read_bytes()
            range_header = self.headers.get("Range", "")
            match = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header)
            if match:
                start = int(match.group(1) or 0); end = int(match.group(2) or len(data)-1)
                if start >= len(data) or end < start:
                    self.send_response(416); self.send_header("Content-Range", f"bytes */{len(data)}"); self.end_headers(); return
                end = min(end, len(data)-1); chunk = data[start:end+1]
                self.send_response(206); self.send_header("Content-Type", mime)
                self.send_header("Content-Range", f"bytes {start}-{end}/{len(data)}")
                self.send_header("Accept-Ranges", "bytes"); self.send_header("Content-Length", str(len(chunk)))
                self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(chunk); return
            self.send_response(200); self.send_header("Content-Type", mime)
            self.send_header("Accept-Ranges", "bytes"); self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(data); return
        return self.send_json(404, {"error": "Route not found."})

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/render":
            return self.send_json(404, {"error": "Route not found."})
        origin = self.headers.get("Origin")
        if origin and origin not in {"http://127.0.0.1:42155", "http://localhost:42155"}:
            return self.send_json(403, {"error": "Cross-origin render requests are refused."})
        try:
            size = int(self.headers.get("Content-Length") or 0)
            if not 1 <= size <= MAX_BODY:
                return self.send_json(413, {"error": "Invalid request size."})
            payload = json.loads(self.rfile.read(size))
            if payload.get("profile", "debut_1080p") != "debut_1080p":
                return self.send_json(422, {"error": "Unknown local render profile."})
        except (ValueError, json.JSONDecodeError):
            return self.send_json(400, {"error": "Invalid JSON request."})
        job_id = uuid.uuid4().hex[:12]
        output_name = "DICERE_DEBUT_EXPLAINER_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + job_id + ".mp4"
        row = {"job_id": job_id, "state": "QUEUED", "output_name": output_name,
               "publication_authorized": False, "human_review_required": True}
        with JOBS_LOCK:
            JOBS[job_id] = row
        thread = threading.Thread(target=render, args=(job_id, output_name), daemon=True)
        row["thread"] = thread; thread.start()
        return self.send_json(202, public_job(row))

    def log_message(self, fmt: str, *args) -> None:
        print("dicere-studio", self.address_string(), fmt % args, flush=True)


def main() -> int:
    parser = __import__("argparse").ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=int(os.environ.get("DICERE_PORT", "42155")))
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "localhost"}:
        parser.error("Dicere Studio is loopback only")
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Dicere Studio: http://{args.host}:{args.port}/", flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
