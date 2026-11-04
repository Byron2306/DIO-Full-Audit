#!/usr/bin/env python3
"""Loopback Sonoris composition and listening-sketch studio."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from products.sonoris_song_engine import OUTPUT_ROOT, SEED_ROOT, _section_performance_audit, compile_song, render_song, studio_catalog
from products.canonical_marketing_media import sonoris_review_music
from atlas.creative_organ_exploration import creative_organ_projection

UI = ROOT / "sites" / "sonoris-studio"
MAX_BODY = 32 * 1024
WORKFLOW_STORE = ROOT / "deliverables" / "sonoris_studio" / "workflows" / "SONORIS_SESSION_RECIPES.json"
MAX_WORKFLOWS = 30
WORKFLOW_BODY_LIMIT = 96 * 1024
WORKFLOW_LOCK = threading.Lock()
STARTER_SESSION_SPECS = (
    ("black_metal", "space", "Black metal · lament and winter", "Winter Without Graves", "icy tremolo, slow dissonance, and a low atmospheric drone"),
    ("thrash_metal", "drive", "Thrash metal · speed assault", "Scars Across the Grid", "urgent downpicking, tight stops, and a hard-driving double-kick pulse"),
    ("death_metal", "fracture", "Death metal · cavernous crush", "Cathedral of Teeth", "chromatic weight, sudden breaks, and a forceful low end"),
    ("power_metal", "drive", "Power metal · heroic gallop", "The Last Starward Oath", "bright gallops, soaring lead answers, and an anthemic lift"),
    ("doom_metal", "fracture", "Doom metal · stoner hypnosis", "Ashes Beneath the Bell", "slow fuzz, spacious drums, and a hypnotic repeated figure"),
    ("glam_metal", "space", "Glam metal · power ballad", "Neon After Midnight", "wide chorus chords, melodic lead responses, and arena-sized dynamics"),
    ("folk_metal", "drive", "Folk metal · festival dance", "Lanterns at the Longhouse", "compound dance pulse, bagpipe melody, and heavy guitar answers"),
    ("prog_metal", "fracture", "Progressive metal · technical dialogue", "Sevenfold Tectonic", "asymmetric meter, interlocking riffs, and a keys-led counterline"),
    ("industrial_metal", "drive", "Industrial metal · machine march", "Factory Saints", "gated guitar, mechanical quarter-note drive, and cold synth texture"),
    ("alternative_metal", "fracture", "Alternative metal · dissonant hook", "Static in the Veins", "angular groove, suspended harmony, and a sudden dissonant hook"),
    ("nu_metal", "space", "Nu metal · quiet impact", "Concrete Halo", "low syncopation, negative space, and a half-time center"),
    ("hard_rock", "drive", "Hard rock · blues riff", "Copperhead Run", "riff-led blues phrasing, punchy drums, and a clear guitar answer"),
    ("math_rock", "fracture", "Math rock · stop start", "Twelve Small Collisions", "asymmetric accents, clean interlock, and deliberate stop-start space"),
    ("post_rock", "drive", "Post-rock · slow crescendo", "The Distance Between Lights", "patient layered growth, open voicings, and a broad release"),
    ("prog_rock", "fracture", "Progressive rock · pastoral arc", "A Map Drawn in Weather", "shifting sections, organ dialogue, and a pastoral-to-electric rise"),
    ("folk_rock", "space", "Folk rock · electric folk", "Where the Pines Bend", "acoustic narrative, folk color, and a restrained electric lift"),
    ("indie_rock", "drive", "Indie rock · jangle hook", "Blue Hour Receiver", "bright interlocking guitars, a compact hook, and an unforced groove"),
    ("grunge", "space", "Grunge · sludge weight", "The Quiet Before the Wall", "low-density verse, heavy entrance, and a raw quiet-loud arc"),
    ("rock", "drive", "Rock · riff drive", "Open Road Signal", "direct riff motion, firm backbeat, and a concise lead response"),
    ("synthwave", "dark_aggro", "Synthwave · dark aggro pursuit", "Chrome Undertow", "dark arpeggiated pulse, saturated synth bass, and an aggressive lift"),
    ("jazz", "drive", "Jazz · swing head", "Afterhours Switchboard", "swinging head, walking bass, and room for a saxophone answer"),
    ("jazz_fusion", "fracture", "Jazz fusion · odd meter exchange", "Glass Meridian", "odd-meter pocket, Rhodes comping, and a saxophone-flute handoff"),
)
WORKFLOW_CONTROL_KEYS = {
    "genre", "songType", "title", "mood", "tempo", "meter", "bars", "key", "mode",
    "tuning", "tone", "drive", "attack", "drumIntensity", "seed", "gain", "preset",
    *(f"module_{role}" for role in ("harmony", "lead", "bass", "drums", "keys", "folk")),
    *(f"mix_{role}" for role in ("harmony", "lead", "bass", "drums", "keys", "folk")),
    "bmPreset", "bmKeysKind", "bmKeysMotion", "bmKeysRegister", "bmKeysDensity", "bmKeysLevel",
}


def _read_workflows() -> list[dict]:
    if not WORKFLOW_STORE.is_file():
        return []
    value = json.loads(WORKFLOW_STORE.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema") != "dio.sonoris.session_recipes.v1" or not isinstance(value.get("recipes"), list):
        raise ValueError("Saved Sonoris recipe store has an unsupported schema.")
    return [row for row in value["recipes"] if isinstance(row, dict) and row.get("id") and row.get("name") and isinstance(row.get("controls"), dict)]


def _write_workflows(recipes: list[dict]) -> None:
    WORKFLOW_STORE.parent.mkdir(parents=True, exist_ok=True)
    document = {"schema": "dio.sonoris.session_recipes.v1", "updated_at": datetime.now(timezone.utc).isoformat(), "recipes": recipes}
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=WORKFLOW_STORE.parent, prefix=".recipes-", suffix=".tmp", delete=False) as handle:
            temp_path = Path(handle.name)
            json.dump(document, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, WORKFLOW_STORE)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def _starter_workflows() -> list[dict]:
    """Build original, editable starting sessions from the live genre catalog."""
    catalog = studio_catalog()
    now = datetime.now(timezone.utc).isoformat()
    mix_defaults = {"harmony": .78, "lead": .58, "bass": .95, "drums": 1.15, "keys": .42, "folk": .8}
    recipes = []
    for index, (genre_key, song_type, name, title, mood) in enumerate(STARTER_SESSION_SPECS, start=1):
        genre = (catalog.get("genres") or {}).get(genre_key)
        if not isinstance(genre, dict):
            continue
        frame = (genre.get("song_type_defaults") or {}).get(song_type) or {}
        tonic, _, mode = str(genre.get("default_tonal_center") or "C-major").partition("-")
        modules = dict(genre.get("default_modules") or {})
        controls = {
            "genre": genre_key,
            "songType": song_type,
            "title": title,
            "mood": mood,
            "tempo": str(frame.get("tempo_bpm") or genre.get("default_tempo_bpm") or ""),
            "meter": str(frame.get("meter") or genre.get("default_meter") or ""),
            "bars": str(frame.get("bars") or genre.get("default_bars") or ""),
            "key": tonic,
            "mode": mode or "minor",
            "tuning": str(genre.get("default_tuning") or "E_standard"),
            "tone": str(genre.get("default_tone") or "clean_chime"),
            "drive": str((catalog.get("tone_profiles") or {}).get(genre.get("default_tone"), {}).get("drive", .6)),
            "attack": "1",
            "drumIntensity": "1",
            "seed": str(23060 + index),
            "gain": "0",
            "preset": "genre",
            "bmPreset": "",
            "bmKeysKind": "NONE",
            "bmKeysMotion": "STATIC",
            "bmKeysRegister": "MID",
            "bmKeysDensity": "LOW",
            "bmKeysLevel": "-18",
        }
        if genre_key == "black_metal":
            controls.update({"bmPreset": "404", "bmKeysKind": "COLD_DRONE", "bmKeysMotion": "PEDAL_SHADOW", "bmKeysRegister": "LOW", "bmKeysDensity": "LOW", "bmKeysLevel": "-22"})
            modules["keys"] = "new_age_pad_sampled"
        for role in ("harmony", "lead", "bass", "drums", "keys", "folk"):
            controls[f"module_{role}"] = str(modules.get(role) or "off")
            controls[f"mix_{role}"] = str(mix_defaults[role])
        recipes.append({"id": str(uuid.uuid4()), "name": name, "controls": controls,
                        "created_at": now, "updated_at": now, "source": "starter"})
    return recipes


def _jobs(root: Path, limit: int = 100) -> list[dict]:
    found = []
    if root.is_dir():
        for file in sorted(root.glob("*/SONORIS_STUDIO_RECEIPT.json"), reverse=True)[:limit]:
            try:
                row = json.loads(file.read_text(encoding="utf-8"))
                found.append({key: row.get(key) for key in ("job_id", "genre", "song_type", "title", "tempo_bpm", "meter", "bars", "gain_db", "tuning", "tone_profile", "guitar_drive", "guitar_attack", "drum_intensity", "modules", "audio_state", "audio_engine")})
            except (ValueError, OSError):
                continue
    return found


class Handler(BaseHTTPRequestHandler):
    def send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def j(self, status: int, obj: dict) -> None:
        self.send(status, json.dumps(obj, ensure_ascii=False).encode(), "application/json; charset=utf-8")

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path in {"/", "/index.html"}:
            return self.send(200, (UI / "index.html").read_bytes(), "text/html; charset=utf-8")
        if path in {"/studio.js", "/studio.css"}:
            return self.send(200, (UI / path[1:]).read_bytes(), "text/javascript; charset=utf-8" if path.endswith("js") else "text/css; charset=utf-8")
        if path == "/api/health":
            return self.j(200, {"state": "READY", "service": "sonoris-studio"})
        if path == "/api/workflows":
            try:
                with WORKFLOW_LOCK:
                    workflows = sorted(_read_workflows(), key=lambda row: row.get("updated_at", ""), reverse=True)
                return self.j(200, {"schema": "dio.sonoris.session_recipes.v1", "recipes": workflows, "storage": "local_service"})
            except (OSError, ValueError) as exc:
                return self.j(503, {"error": f"Saved recipe store is unavailable: {exc}"})
        if path == "/api/catalog":
            return self.j(200, studio_catalog())
        if path == "/api/atlas/domains":
            return self.j(200, creative_organ_projection("sonoris"))
        if path == "/api/jobs":
            return self.j(200, {"jobs": _jobs(OUTPUT_ROOT, 50), "seeds": _jobs(SEED_ROOT, 100)})
        handoff_match = re.fullmatch(r"/api/media-handoffs/(jobs|seeds)/([A-Za-z0-9_-]{1,80})/receipt", path)
        if handoff_match:
            lane, job_id = handoff_match.groups()
            file = ROOT / "deliverables" / "sonoris_studio" / "media_handoffs" / f"{lane}-{job_id}" / "SONORIS_MEDIA_REVIEW_RECEIPT.json"
            if file.is_file():
                return self.send(200, file.read_bytes(), "application/json; charset=utf-8")
            return self.j(404, {"error": "No media review handoff exists for this candidate."})
        match = re.fullmatch(r"/api/(jobs|seeds)/([A-Za-z0-9_-]{1,80})/(receipt|plan|audit|events|midi|audio|wav)", path)
        if match:
            lane, job, kind = match.groups()
            root = OUTPUT_ROOT if lane == "jobs" else SEED_ROOT
            name, mime = {
                "receipt": ("SONORIS_STUDIO_RECEIPT.json", "application/json"),
                "plan": ("COMPOSITION_PLAN.json", "application/json"),
                "audit": ("SECTION_PERFORMANCE_AUDIT.json", "application/json"),
                "events": ("SONG_EVENTS.json", "application/json"),
                "midi": ("SONG_CANDIDATE.mid", "audio/midi"),
                "audio": ("SONG_CANDIDATE.mp3", "audio/mpeg"),
                "wav": ("SONG_CANDIDATE.wav", "audio/wav"),
            }[kind]
            file = root / job / name
            if file.is_file():
                return self.send(200, file.read_bytes(), mime)
            if kind == "audit":
                plan_path = root / job / "COMPOSITION_PLAN.json"
                events_path = root / job / "SONG_EVENTS.json"
                if plan_path.is_file() and events_path.is_file():
                    plan = json.loads(plan_path.read_text(encoding="utf-8"))
                    events = json.loads(events_path.read_text(encoding="utf-8"))
                    audit = _section_performance_audit(plan, events)
                    return self.send(200, json.dumps(audit, ensure_ascii=False).encode(), mime)
            return self.j(404, {"error": "Artifact is unavailable; render audio first if needed."})
        return self.j(404, {"error": "Route not found."})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/workflows/restore-starters":
            try:
                size = int(self.headers.get("Content-Length") or 0)
                if size > 1024:
                    return self.j(413, {"error": "Starter-session request is too large."})
                body = json.loads(self.rfile.read(size) or b"{}")
                if not isinstance(body, dict):
                    return self.j(400, {"error": "Starter-session request must be an object."})
                starters = _starter_workflows()
                with WORKFLOW_LOCK:
                    recipes = _read_workflows()
                    existing_names = {str(row.get("name", "")).casefold() for row in recipes}
                    missing = [row for row in starters if row["name"].casefold() not in existing_names]
                    if len(recipes) + len(missing) > MAX_WORKFLOWS:
                        return self.j(409, {"error": f"Adding {len(missing)} starter sessions would exceed the {MAX_WORKFLOWS}-recipe limit. Delete saved recipes, then retry.", "saved": len(recipes), "to_add": len(missing), "limit": MAX_WORKFLOWS})
                    _write_workflows([*missing, *recipes])
                    count = len(recipes) + len(missing)
                return self.j(200, {"added": len(missing), "total": count, "limit": MAX_WORKFLOWS,
                                    "recipes": sorted([*missing, *recipes], key=lambda row: row.get("updated_at", ""), reverse=True),
                                    "storage": "local_service"})
            except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
                return self.j(503, {"error": f"Could not restore starter sessions: {exc}"})
        if path == "/api/media-handoffs":
            try:
                size = int(self.headers.get("Content-Length") or 0)
                if not 1 <= size <= MAX_BODY:
                    return self.j(413, {"error": "Media handoff request is empty or too large."})
                body = json.loads(self.rfile.read(size))
                if not isinstance(body, dict):
                    return self.j(400, {"error": "Media handoff request must be an object."})
                handoff = sonoris_review_music({
                    "mode": "sonoris_review_candidate",
                    "job_id": body.get("job_id"),
                    "lane": body.get("lane", "jobs"),
                    "volume": body.get("volume", .10),
                })
                return self.j(200, {"handoff": handoff["sonoris_handoff"], "selection": handoff,
                                    "pipeline_environment": {"DIO_SONORIS_REVIEW_JOB": handoff["sonoris_handoff"]["source_job_id"],
                                                             "DIO_SONORIS_REVIEW_LANE": handoff["sonoris_handoff"]["source_lane"]}})
            except (ValueError, KeyError, FileNotFoundError, json.JSONDecodeError) as exc:
                return self.j(422, {"error": str(exc)})
            except OSError as exc:
                return self.j(503, {"error": f"Could not create Sonoris media handoff: {exc}"})
        if path == "/api/workflows":
            try:
                size = int(self.headers.get("Content-Length") or 0)
                if not 1 <= size <= WORKFLOW_BODY_LIMIT:
                    return self.j(413, {"error": "Recipe settings are empty or too large."})
                body = json.loads(self.rfile.read(size))
                if not isinstance(body, dict):
                    return self.j(400, {"error": "Recipe request must be an object."})
                name = str(body.get("name") or "").strip()
                controls = body.get("controls")
                if not name or len(name) > 64:
                    return self.j(400, {"error": "Recipe name must contain 1–64 characters."})
                if not isinstance(controls, dict) or not controls:
                    return self.j(400, {"error": "Recipe settings are missing."})
                if set(controls) - WORKFLOW_CONTROL_KEYS:
                    return self.j(400, {"error": "Recipe contains unsupported settings."})
                clean = {}
                for key, value in controls.items():
                    if not isinstance(value, (str, int, float, bool)) or len(str(value)) > 4096:
                        return self.j(400, {"error": f"Recipe setting {key} must be a short scalar value."})
                    clean[key] = str(value)
                with WORKFLOW_LOCK:
                    recipes = _read_workflows()
                    existing = next((row for row in recipes if str(row.get("name", "")).casefold() == name.casefold()), None)
                    if existing is None and len(recipes) >= MAX_WORKFLOWS:
                        return self.j(409, {"error": f"Sonoris stores at most {MAX_WORKFLOWS} named session recipes."})
                    now = datetime.now(timezone.utc).isoformat()
                    recipe = {"id": existing["id"] if existing else str(uuid.uuid4()), "name": name, "controls": clean,
                              "created_at": existing.get("created_at", now) if existing else now, "updated_at": now}
                    recipes = [row for row in recipes if row.get("id") != recipe["id"]]
                    recipes.insert(0, recipe)
                    _write_workflows(recipes)
                return self.j(200, {"recipe": recipe, "storage": "local_service"})
            except (ValueError, json.JSONDecodeError) as exc:
                return self.j(400, {"error": f"Invalid recipe: {exc}"})
            except OSError as exc:
                return self.j(503, {"error": f"Could not persist recipe: {exc}"})
        if path not in {"/api/compile", "/api/render"}:
            return self.j(404, {"error": "Route not found."})
        try:
            size = int(self.headers.get("Content-Length") or 0)
            if not 1 <= size <= MAX_BODY:
                return self.j(413, {"error": "Invalid request size."})
            body = json.loads(self.rfile.read(size))
            if path == "/api/compile":
                receipt = compile_song(body)
                return self.j(200, {"receipt": receipt, "lane": "jobs"})
            job = str(body.get("job_id") or "")
            lane = str(body.get("lane") or "jobs")
            if lane not in {"jobs", "seeds"}:
                raise ValueError("Unknown lane")
            receipt = render_song(job, output_root=OUTPUT_ROOT if lane == "jobs" else SEED_ROOT,
                                  force=body.get("force") is True)
            return self.j(200, {"receipt": receipt, "lane": lane})
        except (ValueError, KeyError, FileNotFoundError, json.JSONDecodeError) as exc:
            return self.j(422, {"error": str(exc)})
        except Exception as exc:
            return self.j(503, {"error": f"Local Sonoris render failed: {exc}"})

    def do_DELETE(self) -> None:
        path = urlparse(self.path).path
        match = re.fullmatch(r"/api/workflows/([0-9a-f-]{36})", path)
        if not match:
            return self.j(404, {"error": "Saved recipe route not found."})
        try:
            with WORKFLOW_LOCK:
                recipes = _read_workflows()
                kept = [row for row in recipes if row.get("id") != match.group(1)]
                if len(kept) == len(recipes):
                    return self.j(404, {"error": "Saved recipe was not found."})
                _write_workflows(kept)
        except (OSError, ValueError) as exc:
            return self.j(503, {"error": f"Could not delete saved recipe: {exc}"})
        return self.j(200, {"deleted": match.group(1), "storage": "local_service"})

    def log_message(self, fmt: str, *args) -> None:
        print("sonoris-studio", self.address_string(), fmt % args, flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=int(os.environ.get("SONORIS_PORT", "42154")))
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "localhost"}:
        parser.error("Sonoris Studio is loopback only")
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Sonoris Studio: http://{args.host}:{args.port}/", flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
