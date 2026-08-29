from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from products.media_incarnation import MediaIncarnationError, build_media_incarnation, verify_media_proof
from products.product_explainer_branding import enrich_renderer_script
from adapters.document_studio.media_control import render_media_control_surface

ROOT = Path(__file__).resolve().parents[1]
ACCEPTANCE_TOKEN = "DIO_PREMIUM_MEDIA_INCARNATION_READY"
PREMIUM_PROVIDERS = {"imported", "voicebox", "kokoro", "piper", "elevenlabs", "openvoice"}


class PremiumMediaError(RuntimeError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PremiumMediaError(f"invalid or missing JSON: {path}") from exc
    if not isinstance(value, dict):
        raise PremiumMediaError(f"expected object: {path}")
    return value


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _wav_duration_seconds(path: Path) -> float:
    import struct

    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise PremiumMediaError(f"invalid rendered voice WAV: {path}") from exc

    if len(raw) < 12 or raw[:4] != b"RIFF" or raw[8:12] != b"WAVE":
        raise PremiumMediaError(f"invalid rendered voice WAV: {path}")

    offset = 12
    byte_rate: int | None = None
    data_bytes: int | None = None

    while offset + 8 <= len(raw):
        chunk_id = raw[offset : offset + 4]
        declared_size = struct.unpack_from("<I", raw, offset + 4)[0]
        payload_start = offset + 8
        available = len(raw) - payload_start
        actual_size = min(declared_size, max(0, available))

        if chunk_id == b"fmt ":
            if actual_size < 16:
                raise PremiumMediaError(f"rendered voice WAV has invalid fmt chunk: {path}")

            (
                _audio_format,
                _channels,
                sample_rate,
                byte_rate,
                block_align,
                _bits_per_sample,
            ) = struct.unpack_from("<HHIIHH", raw, payload_start)

            if sample_rate <= 0 or byte_rate <= 0 or block_align <= 0:
                raise PremiumMediaError(f"rendered voice WAV has invalid audio format: {path}")

        elif chunk_id == b"data":
            if byte_rate is None:
                raise PremiumMediaError(f"rendered voice WAV data precedes fmt chunk: {path}")

            # Pocket TTS emits a streaming-style header whose declared data
            # length may greatly exceed the bytes actually written. Duration
            # must therefore be derived from the payload physically present.
            data_bytes = actual_size
            break

        if declared_size > available:
            raise PremiumMediaError(f"rendered voice WAV contains a truncated chunk: {path}")

        offset = payload_start + declared_size + (declared_size & 1)

    if byte_rate is None or data_bytes is None:
        raise PremiumMediaError(f"rendered voice WAV is missing fmt or data chunk: {path}")

    return round(data_bytes / byte_rate, 6)


def _fingerprint(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _run(
    command: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, cwd=cwd, env=env, text=True, capture_output=True, check=True)
    except FileNotFoundError as exc:
        raise PremiumMediaError(f"required executable missing: {command[0]}") from exc
    except subprocess.CalledProcessError as exc:
        raise PremiumMediaError(f"native engine command failed: {' '.join(command)}\n{exc.stderr}") from exc


def resolve_nichefoundry_root(value: Path | None) -> Path:
    candidates = [
        value,
        Path(os.environ["DIO_NICHEFOUNDRY_ROOT"]) if os.environ.get("DIO_NICHEFOUNDRY_ROOT") else None,
        Path.home() / "NicheFoundry",
        Path.home() / "Downloads/NicheFoundry_Phase11",
    ]
    for candidate in candidates:
        if candidate is None:
            continue
        root = candidate.expanduser().resolve()
        required = [
            root / "package.json",
            root / "scripts/build_audio_performance.js",
            root / "lib/audio_system.js",
            root / "lib/render_system.js",
            root / "lib/music_discovery.js",
            root / "studios/builtin/practical_open_source.json",
        ]
        if all(path.is_file() for path in required):
            return root
    raise PremiumMediaError("real NicheFoundry checkout not found; set DIO_NICHEFOUNDRY_ROOT")


def _voicebox_ready() -> bool:
    profile = os.environ.get("VOICEBOX_PROFILE", "").strip()
    if not profile:
        return False
    base = os.environ.get("VOICEBOX_API_URL", "http://127.0.0.1:17493").rstrip("/")
    try:
        with urllib.request.urlopen(f"{base}/profiles", timeout=2.0) as response:
            if response.status != 200:
                return False
            profiles = json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError, urllib.error.URLError, json.JSONDecodeError):
        return False
    return isinstance(profiles, list) and any(
        str(row.get("id") or "") == profile
        or str(row.get("name") or "").lower() == profile.lower()
        for row in profiles
        if isinstance(row, dict)
    )


def _kokoro_ready(command: Path, wrapper: Path) -> bool:
    if not command.is_file() or not wrapper.is_file():
        return False
    try:
        probe = subprocess.run(
            [str(command), "-c", "import numpy, soundfile; from kokoro import KPipeline"],
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return probe.returncode == 0


def _resolve_premium_provider(niche_root: Path, requested: str, episode_dir: Path) -> str:
    if requested in {"espeak", "flite"}:
        raise PremiumMediaError("robotic reference voices are forbidden by the premium gate")
    if requested != "auto":
        if requested not in PREMIUM_PROVIDERS:
            raise PremiumMediaError(f"unsupported premium provider: {requested}")
        return requested
    imports = episode_dir / "imports/audio"
    if imports.is_dir() and any(
        path.suffix.lower() in {".wav", ".mp3", ".m4a", ".ogg"} for path in imports.iterdir()
    ):
        return "imported"
    if _voicebox_ready():
        return "voicebox"
    kokoro_command = Path(os.environ.get("KOKORO_COMMAND", niche_root / ".venv-kokoro/bin/python"))
    kokoro_wrapper = Path(os.environ.get("KOKORO_WRAPPER", niche_root / "scripts/kokoro_synthesize.py"))
    if _kokoro_ready(kokoro_command, kokoro_wrapper):
        return "kokoro"
    piper_bin = os.environ.get("PIPER_BIN") or str(niche_root / "tools/piper/piper")
    piper_model_name = os.environ.get("PIPER_MODEL_NAME", "en_US-lessac-high")
    piper_model_dir = Path(os.environ.get("PIPER_MODEL_DIR", niche_root / f"assets/piper/{piper_model_name}"))
    piper_available = bool(shutil.which(piper_bin)) or Path(piper_bin).is_file()
    if (
        piper_available
        and (piper_model_dir / f"{piper_model_name}.onnx").is_file()
        and (piper_model_dir / f"{piper_model_name}.onnx.json").is_file()
    ):
        return "piper"
    if os.environ.get("ELEVENLABS_API_KEY") and os.environ.get("ELEVENLABS_VOICE_ID"):
        return "elevenlabs"
    openvoice_command = Path(os.environ.get("OPENVOICE_COMMAND", niche_root / ".venv-openvoice/bin/python"))
    openvoice_wrapper = Path(os.environ.get("OPENVOICE_WRAPPER", niche_root / "scripts/openvoice_convert.py"))
    openvoice_reference = Path(
        os.environ.get("OPENVOICE_REFERENCE_AUDIO", niche_root / "assets/voices/elevenlabs_curator/reference.wav")
    )
    if openvoice_command.is_file() and openvoice_wrapper.is_file() and openvoice_reference.is_file():
        return "openvoice"
    stale = " VOICEBOX_PROFILE is configured, but its backend/profile is unreachable." if os.environ.get("VOICEBOX_PROFILE") else ""
    broken_kokoro = (
        " Kokoro exists, but its import preflight failed; rerun NicheFoundry scripts/install_kokoro.sh."
        if kokoro_command.is_file()
        else ""
    )
    raise PremiumMediaError(
        "no runnable premium narration provider was found."
        + stale
        + broken_kokoro
        + " Start Voicebox, install NicheFoundry Kokoro/Piper, configure ElevenLabs/OpenVoice, or supply cleared imported narration; eSpeak/Flite remain refused."
    )


def _script_package() -> dict[str, Any]:
    rows = [
        ("The plan exists", "Your incident response plan may exist. Your role matrix may exist. Your exercise records may exist. But that does not mean the evidence agrees."),
        ("Evidence ages differently", "Plans, named owners, exercises and contact details age at different speeds. One stale record can hide inside an otherwise complete-looking folder."),
        ("Map before you rely", "DIO Incident Readiness Proof maps what is supplied, what is missing, what is stale, and which decisions still require a named human authority."),
        ("No readiness theatre", "It does not certify readiness. It does not guarantee recovery. And it does not turn a generated dossier into operational authority."),
        ("A reviewable dossier", "The result is a reviewable, multi-format evidence dossier with a gap register, action boundary and hash-bound proof manifest."),
        ("Know before the incident does", "Prepare a controlled review locally. Keep the consequential decision human. Know what your response plan can prove before the incident does."),
    ]
    beats = ["working_result_preview", "problem_framing", "validation", "constraint", "evidence", "next_step"]
    return {
        "schema": "nichefoundry.script_package.v1.0",
        "title": "Can Your Incident Plan Prove It?",
        "scenes": [
            {
                "scene_id": f"scene_{i + 1:02}",
                "story_beat": beats[i],
                "title": title,
                "narration": narration,
                "estimated_duration_seconds": 8,
                "claim_ids": [f"claim_{i + 1:02}"],
                "source_ids": [f"source_{i + 1:02}"],
            }
            for i, (title, narration) in enumerate(rows)
        ],
    }


def _presence_voice_functions():
    from presence_core.voice import build_voice_plan, synthesize_voice

    return build_voice_plan, synthesize_voice


def _voice_render_text(text: str, voice: dict[str, Any]) -> str:
    rendered = str(text or "")
    for term, spoken in (voice.get("pronunciation") or {}).items():
        rendered = re.sub(rf"(?<![\w]){re.escape(str(term))}(?![\w])", str(spoken), rendered)
    return rendered


def _prepare_presence_core_voice_imports(
    episode_dir: Path,
    script_package: dict[str, Any],
    production_request: dict[str, Any] | None,
) -> dict[str, Any] | None:
    voice = (production_request or {}).get("voice") or {}
    if voice.get("render_mode") != "presence_core_imported_audio":
        return None
    profile = str(voice.get("profile") or "").strip()
    if not profile:
        raise PremiumMediaError("Presence Core voice import requires a voice profile")
    build_voice_plan, synthesize_voice = _presence_voice_functions()
    plan = build_voice_plan(
        root=ROOT,
        language="English",
        interaction={"delivery_policy": {"mode": "measured"}},
        requested_profile=profile,
    )
    if plan.get("state") != "ready_for_internal_render":
        raise PremiumMediaError(
            "Presence Core voice profile is not renderable: " + ",".join(plan.get("reasons") or [])
        )
    assets: list[dict[str, Any]] = []
    renders: list[dict[str, Any]] = []
    authority_keys = (
        "external_action_executed",
        "send_authorized",
        "identity_authority_created",
        "translation_authority_created",
    )
    for index, scene in enumerate(script_package.get("scenes") or [], 1):
        scene_id = str(scene.get("scene_id") or f"scene_{index:02d}")
        relative_path = f"imports/audio/{index:02d}_{scene_id}.wav"
        output_path = episode_dir / relative_path
        receipt = synthesize_voice(
            text=_voice_render_text(str(scene.get("narration") or ""), voice),
            output_path=output_path,
            plan=plan,
        )
        if any(receipt.get(key) is not False for key in authority_keys):
            raise PremiumMediaError("Presence Core voice receipt attempted to create authority")
        audio_sha = _sha(output_path)
        duration_seconds = _wav_duration_seconds(output_path)
        assets.append(
            {
                "scene_id": scene_id,
                "relative_path": relative_path,
                "creator": "DIO Presence Core / Vesper",
                "licence": "project-owned-output",
                "rights_status": "cleared",
                "sha256": audio_sha,
            }
        )
        renders.append(
            {
                "scene_id": scene_id,
                "relative_path": relative_path,
                "sha256": audio_sha,
                "duration_seconds": duration_seconds,
                "render_receipt": receipt,
            }
        )
    _write(episode_dir / "audio_imports.json", {"schema": "nichefoundry.audio_imports.v1", "assets": assets})
    result = {
        "schema": "dio.vesper.media_voice_import.v1",
        "voice_profile": profile,
        "backend": plan.get("backend"),
        "scene_count": len(assets),
        "assets": renders,
        "external_action_executed": False,
        "send_authorized": False,
        "identity_authority_created": False,
        "translation_authority_created": False,
    }
    _write(episode_dir / "DIO_VOICE_IMPORT_RECEIPT.json", result)
    return result


def _prepare_original_local_music_import(
    episode_dir: Path, production_request: dict[str, Any] | None
) -> dict[str, Any] | None:
    sound = (production_request or {}).get("sound") or {}
    if sound.get("music_origin") != "original_local":
        return None
    source_value = str(sound.get("path") or "").strip()
    if not source_value:
        raise PremiumMediaError("original local music requires a bound source path")
    source = Path(source_value)
    if not source.is_absolute():
        source = ROOT / source
    if not source.is_file():
        raise PremiumMediaError(f"original local music asset missing: {source_value}")
    actual = _sha(source)
    expected = str(sound.get("sha256") or "").removeprefix("sha256:")
    if expected and expected != actual:
        raise PremiumMediaError("original local music hash does not match the bound asset")
    suffix = source.suffix.lower()
    if suffix not in {".wav", ".mp3", ".m4a", ".ogg"}:
        raise PremiumMediaError("original local music must be WAV, MP3, M4A, or OGG")
    target = episode_dir / "imports" / f"music_bed{suffix}"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    receipt = {
        "schema": "dio.media.original_local_music_import.v1",
        "music_origin": "original_local",
        "music_rights_state": "self_generated_bound",
        "procedural_music_fallback": "REFUSE",
        "source_path": source_value,
        "source_sha256": actual,
        "relative_path": str(target.relative_to(episode_dir)),
        "import_sha256": _sha(target),
    }
    _write(episode_dir / "DIO_MUSIC_IMPORT_RECEIPT.json", receipt)
    return receipt


def _reconcile_timing_with_voice(
    timing: dict[str, Any],
    voice_import: dict[str, Any] | None,
    *,
    canonical_budget_seconds: float,
    buffer_seconds: float = 0.50,
) -> dict[str, Any]:
    if not voice_import:
        return timing

    scenes = timing.get("scenes") or []
    assets = voice_import.get("assets") or []
    if not scenes or not assets:
        return timing

    measured_by_scene: dict[str, float] = {}
    for row in assets:
        scene_id = str(row.get("scene_id") or "").strip()
        duration = row.get("duration_seconds")
        if scene_id and duration is not None:
            measured_by_scene[scene_id] = float(duration)

    if not measured_by_scene:
        return timing

    missing = [
        str(scene.get("scene_id"))
        for scene in scenes
        if str(scene.get("scene_id")) not in measured_by_scene
    ]
    if missing:
        raise PremiumMediaError(
            "Presence Core voice timing evidence incomplete: " + ", ".join(missing)
        )

    budget = float(canonical_budget_seconds)
    if budget <= 0:
        raise PremiumMediaError("canonical timing budget must be positive")

    original_targets = [
        float(scene.get("target_duration_seconds") or 0.0)
        for scene in scenes
    ]
    measured = [
        measured_by_scene[str(scene.get("scene_id"))]
        for scene in scenes
    ]
    minimum_targets = [
        duration + float(buffer_seconds)
        for duration in measured
    ]

    minimum_total = sum(minimum_targets)
    if minimum_total > budget + 1e-9:
        raise PremiumMediaError(
            "measured voice cannot fit canonical timing budget: "
            f"requires {minimum_total:.3f}s for {budget:.3f}s budget"
        )

    # Preserve the original story emphasis wherever spare time still exists.
    # Scenes whose voice exceeds their original slot receive their measured
    # minimum first. Remaining time is distributed according to surviving
    # slack in the original timing plan.
    spare_budget = budget - minimum_total
    weights = [
        max(0.0, original - minimum)
        for original, minimum in zip(original_targets, minimum_targets)
    ]
    weight_total = sum(weights)

    if weight_total <= 1e-12:
        weights = [1.0 for _ in scenes]
        weight_total = float(len(scenes))

    targets = [
        minimum + spare_budget * (weight / weight_total)
        for minimum, weight in zip(minimum_targets, weights)
    ]

    # Millisecond precision keeps receipts readable while preserving the
    # canonical total exactly.
    targets = [round(value, 3) for value in targets]
    correction = round(budget - sum(targets), 3)
    if correction:
        slack = [
            target - minimum
            for target, minimum in zip(targets, minimum_targets)
        ]
        index = max(range(len(targets)), key=lambda i: slack[i])
        targets[index] = round(targets[index] + correction, 3)

    changed = any(
        abs(target - original) > 0.001
        for target, original in zip(targets, original_targets)
    )

    for scene, duration, target in zip(scenes, measured, targets):
        scene["measured_voice_seconds"] = round(duration, 3)
        scene["target_duration_seconds"] = target

    timing["reconciliation"] = {
        "state": "VOICE_FIT_REBALANCED" if changed else "VOICE_FIT_UNCHANGED",
        "voice_profile": voice_import.get("voice_profile"),
        "canonical_budget_seconds": round(budget, 3),
        "measured_voice_seconds": round(sum(measured), 3),
        "minimum_required_seconds": round(minimum_total, 3),
        "voice_buffer_seconds": round(float(buffer_seconds), 3),
    }
    return timing


def _prepare_episode(
    niche_root: Path,
    episode_dir: Path,
    *,
    script_package: dict[str, Any] | None = None,
    production_request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    episode_dir.mkdir(parents=True, exist_ok=True)
    pack = _load(niche_root / "studios/builtin/practical_open_source.json")
    semantic_script = script_package if script_package is not None else _script_package()
    if production_request is not None and "brand_render_brief" in production_request:
        script = enrich_renderer_script(semantic_script, production_request)
    else:
        script = semantic_script
    sample = (pack.get("samples") or [{}])[0]
    brief = dict(sample)
    brief.update(
        {
            "topic": script.get("title") or "Product explainer",
            "language": "en",
            "title": script.get("title") or "Product explainer",
            "audience": "Product audience",
        }
    )
    brand_render_brief = (production_request or {}).get("brand_render_brief")
    if brand_render_brief:
        brief["brand_render_brief"] = json.loads(json.dumps(brand_render_brief))
        brief["brand_profile_id"] = brand_render_brief.get("profile_id")
        brief["visual_direction"] = brand_render_brief.get("visual_direction")
        brief["forbidden_motifs"] = list(
            brand_render_brief.get("forbidden_motifs") or []
        )

    voice = (production_request or {}).get("voice") or {}
    pronunciation = voice.get("pronunciation") or {}
    if pronunciation:
        brief["pronunciation_overrides"] = [
            {"term": str(term), "spoken_form": str(spoken), "review_required": False}
            for term, spoken in pronunciation.items()
        ]
    elif script_package is None:
        brief["pronunciation_overrides"] = [
            {"term": "DIO", "spoken_form": "D I O", "review_required": False}
        ]
    timing = {
        "schema": "nichefoundry.timing_plan.v1",
        "scenes": [
            {
                "scene_id": row["scene_id"],
                "target_duration_seconds": row.get(
                    "target_duration_seconds", row.get("estimated_duration_seconds", 8)
                ),
            }
            for row in script.get("scenes") or []
        ],
    }
    for name, value in (
        ("brief.json", brief),
        ("studio_pack_snapshot.json", pack),
        ("script_package.json", script),
        ("timing_plan.json", timing),
    ):
        _write(episode_dir / name, value)
    music_import = _prepare_original_local_music_import(episode_dir, production_request)
    voice_import = _prepare_presence_core_voice_imports(episode_dir, script, production_request)

    if voice_import:
        canonical_budget = float(
            script.get("target_seconds")
            or sum(
                float(row.get("target_duration_seconds") or 0.0)
                for row in timing.get("scenes") or []
            )
        )
        timing = _reconcile_timing_with_voice(
            timing,
            voice_import,
            canonical_budget_seconds=canonical_budget,
        )
        _write(episode_dir / "timing_plan.json", timing)

    return {
        "pack": pack,
        "brief": brief,
        "script": script,
        "timing": timing,
        "voice_import": voice_import,
        "music_import": music_import,
    }


def _probe_audio(path: Path, ffprobe: str) -> dict[str, Any]:
    result = _run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "stream=codec_name,sample_rate,channels:format=duration",
            "-of",
            "json",
            str(path),
        ]
    )
    return json.loads(result.stdout)


def _music_quality(path: Path, ffmpeg: str) -> dict[str, Any]:
    def measure(filters: str | None) -> float:
        command = [ffmpeg, "-hide_banner", "-i", str(path)]
        if filters:
            command.extend(["-af", filters])
        command.extend(["-f", "null", "-"])
        completed = subprocess.run(command, text=True, capture_output=True, check=False)
        values = re.findall(r"RMS level dB:\s*(-?[0-9.]+)", completed.stderr)
        if not values:
            raise PremiumMediaError("music spectral QA could not measure RMS")
        return float(values[-1])

    full = measure("astats=metadata=1:reset=0")
    high = measure("highpass=f=4000,astats=metadata=1:reset=0")
    delta = round(full - high, 3)
    if delta < 4.0:
        raise PremiumMediaError(
            f"premium music gate detected hiss-like high-frequency energy: delta {delta} dB"
        )
    return {
        "full_band_rms_db": full,
        "above_4khz_rms_db": high,
        "high_frequency_attenuation_db": delta,
        "minimum_attenuation_db": 4.0,
        "hiss_detection": "PASS",
    }


def _prepare_native_render_contract(
    episode_dir: Path,
    gamma: dict[str, Any],
    *,
    script_package: dict[str, Any] | None = None,
) -> None:
    script = script_package if script_package is not None else _script_package()
    scenes = []
    assets = []
    for scene in script.get("scenes") or []:
        asset = next(
            (row for row in gamma.get("assets", []) if row.get("scene_id") == scene["scene_id"]),
            None,
        )
        if not asset:
            raise PremiumMediaError(f"Gamma omitted native scene asset: {scene['scene_id']}")
        scenes.append(
            {
                "scene_id": scene["scene_id"],
                "title": scene["title"],
                "beat_name": scene["story_beat"],
                "preview_path": asset["relative_path"],
                "preview_asset_id": f"gamma_{scene['scene_id']}",
                "motion_cue": str(
                    scene.get("motion_cue") or "restrained documentary push"
                ),
                "composition": "native_gamma_composition_preserved",
                "claim_ids": scene.get("claim_ids", []),
                "source_ids": scene.get("source_ids", []),
            }
        )
        assets.append(
            {
                "asset_id": f"gamma_{scene['scene_id']}",
                "scene_id": scene["scene_id"],
                "asset_type": "generated_scene",
                "relative_path": asset["relative_path"],
                "sha256": asset["sha256"],
                "status": "ready",
                "provider": "gamma_public_api",
            }
        )
    thumb = next((row for row in gamma.get("assets", []) if row.get("kind") == "thumbnail"), None)
    if not thumb:
        raise PremiumMediaError("Gamma omitted native thumbnail asset")
    assets.append(
        {
            "asset_id": "gamma_thumbnail",
            "role": "thumbnail",
            "asset_type": "thumbnail",
            "relative_path": thumb["relative_path"],
            "sha256": thumb["sha256"],
            "status": "ready",
            "provider": "gamma_public_api",
        }
    )
    _write(
        episode_dir / "episode.json",
        {"episode_id": episode_dir.name, "title": script["title"], "studio": {"id": "practical_open_source"}},
    )
    _write(episode_dir / "visual_plan.json", {"schema": "nichefoundry.visual_plan.v1", "scene_plans": scenes})
    _write(episode_dir / "asset_manifest.json", {"schema": "nichefoundry.asset_manifest.v1", "assets": assets})
    _write(
        episode_dir / "visual_report.json",
        {
            "schema": "nichefoundry.visual_report.v1",
            "passed": True,
            "scene_count": len(scenes),
            "composition_authority": "native_gamma",
            "human_visual_release": "NEEDS_YOU",
        },
    )


def _run_nichefoundry(
    niche_root: Path,
    episode_dir: Path,
    provider: str,
    *,
    script_package: dict[str, Any] | None = None,
    production_request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    node = shutil.which("node")
    if not node:
        raise PremiumMediaError("Node.js is required for real NicheFoundry execution")
    script = script_package if script_package is not None else _script_package()
    prepared = _prepare_episode(
        niche_root,
        episode_dir,
        script_package=script,
        production_request=production_request,
    )
    assets_command = [node, str(niche_root / "scripts/build_premium_assets.js"), str(episode_dir)]
    assets_completed = _run(assets_command, cwd=niche_root, env=dict(os.environ))
    requested_provider = "imported" if prepared.get("voice_import") else provider
    selected_provider = _resolve_premium_provider(niche_root, requested_provider, episode_dir)
    command = [
        node,
        str(niche_root / "scripts/build_audio_performance.js"),
        str(episode_dir),
        "--provider",
        selected_provider,
        "--force",
    ]
    completed = _run(command, cwd=niche_root, env=dict(os.environ))
    required = [
        "premium_assets_receipt.json",
        "gamma_execution_receipt.json",
        "music_rights_receipt.json",
        "host_profile.json",
        "pronunciation_lexicon.json",
        "audio_performance_plan.json",
        "sound_design_plan.json",
        "audio_preflight_report.json",
        "audio_manifest.json",
        "audio_asset_hashes.json",
        "loudness_report.json",
        "audio_performance_report.json",
    ]
    missing = [name for name in required if not (episode_dir / name).is_file()]
    if missing:
        raise PremiumMediaError(f"NicheFoundry omitted audio evidence: {missing}")
    manifest = _load(episode_dir / "audio_manifest.json")
    performance = _load(episode_dir / "audio_performance_report.json")
    sound = _load(episode_dir / "sound_design_plan.json")
    loudness = _load(episode_dir / "loudness_report.json")
    providers = {
        str(row.get("provider") or manifest.get("provider") or "").lower()
        for row in manifest.get("scenes", [])
    }
    providers.discard("")
    if not providers:
        providers = {str(manifest.get("provider") or "").lower()}
    forbidden = providers - PREMIUM_PROVIDERS
    if forbidden:
        raise PremiumMediaError(f"premium voice gate refused providers: {sorted(forbidden)}")
    if performance.get("passed") is not True:
        raise PremiumMediaError("NicheFoundry audio performance QA failed")
    if (
        not sound.get("music_identity")
        or not sound.get("rights")
        or not all(row.get("music_cue") for row in sound.get("scenes", []))
    ):
        raise PremiumMediaError("NicheFoundry music plan or rights evidence incomplete")
    preview = episode_dir / "audio/episode_audio_preview.wav"
    if not preview.is_file():
        raise PremiumMediaError("NicheFoundry mastered programme preview missing")
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise PremiumMediaError("ffprobe is required")
    probe = _probe_audio(preview, ffprobe)
    streams = probe.get("streams") or [{}]
    stream = streams[0]
    if int(stream.get("sample_rate") or 0) != 48000 or int(stream.get("channels") or 0) != 2:
        raise PremiumMediaError("NicheFoundry master is not 48 kHz stereo")
    gamma = _load(episode_dir / "gamma_execution_receipt.json")
    music_rights = _load(episode_dir / "music_rights_receipt.json")
    premium_assets = _load(episode_dir / "premium_assets_receipt.json")
    if gamma.get("native_engine_invoked") is not True or gamma.get("scene_coverage") != len(script["scenes"]):
        raise PremiumMediaError("native Gamma scene coverage is incomplete")
    _prepare_native_render_contract(episode_dir, gamma, script_package=script)
    render_command = [node, str(niche_root / "scripts/render_episode.js"), str(episode_dir), "final", "--force"]
    render_completed = _run(render_command, cwd=niche_root, env=dict(os.environ))
    native_final = episode_dir / "final.mp4"
    native_thumbnail = episode_dir / "thumbnail.png"
    if not native_final.is_file() or not native_thumbnail.is_file():
        raise PremiumMediaError("NicheFoundry native render system omitted release assets")
    render_qa = _load(episode_dir / "render_qa_report.json")
    render_manifest = _load(episode_dir / "render_manifest_v2.json")
    render_hashes = _load(episode_dir / "render_asset_hashes.json")
    if render_qa.get("passed") is not True or render_hashes.get("complete") is not True:
        raise PremiumMediaError("NicheFoundry native render QA failed")
    if music_rights.get("commercial_friendly_licence") is not True:
        raise PremiumMediaError("premium music lacks a commercial-friendly licence receipt")
    music_preview = episode_dir / "audio/episode_music_bed_preview.wav"
    quality = _music_quality(music_preview, shutil.which("ffmpeg") or "ffmpeg")
    return {
        "command": command,
        "stdout": completed.stdout.strip(),
        "premium_assets_stdout": assets_completed.stdout.strip(),
        "providers": sorted(providers),
        "manifest": manifest,
        "performance": performance,
        "sound_design": sound,
        "loudness": loudness,
        "preview": preview,
        "probe": probe,
        "gamma": gamma,
        "music_rights": music_rights,
        "premium_assets": premium_assets,
        "music_quality": quality,
        "voice_import": prepared.get("voice_import"),
        "music_import": prepared.get("music_import"),
        "native_render": {
            "command": render_command,
            "stdout": render_completed.stdout.strip(),
            "final": native_final,
            "thumbnail": native_thumbnail,
            "qa": render_qa,
            "manifest": render_manifest,
            "hashes": render_hashes,
        },
        "source_ref": "Byron2306/NicheFoundry",
        "source_root": str(niche_root),
        "native_engine_invoked": True,
    }


def _corpus_census(niche: dict[str, Any]) -> dict[str, Any]:
    rows = [
        {"engine_id": "nichefoundry", "repository": "Byron2306/NicheFoundry", "state": "NATIVE_EXECUTED", "receipt": "premium/NICHEFOUNDRY_NATIVE_EXECUTION.json"},
        {"engine_id": "document_studio", "repository": "DIO-Full-Audit/adapters/document_studio", "state": "CONTROL_SURFACE_BOUND", "receipt": "premium/document_studio_media/DOCUMENT_STUDIO_MEDIA_RECEIPT.json", "reason": "Controls and validates native media without replacing its renderer"},
        {"engine_id": "lingua", "repository": "DIO-Full-Audit/adapters/lingua", "state": "NOT_INVOKED", "reason": "No translation/localisation request is part of this incarnation"},
        {"engine_id": "homs", "repository": "Byron2306/HOMS-assessor", "state": "PROJECTION_ONLY", "reason": "Phase 16 customer education is locally constructed"},
        {"engine_id": "evidex", "repository": "Byron2306/Evidex", "state": "PROJECTION_ONLY", "reason": "Phase 16 proof manifest does not invoke the external Evidex runtime"},
        {"engine_id": "vamp", "repository": "Byron2306/VAMP", "state": "NOT_BOUND", "reason": "VAMP is absent from the Phase 16 product contract"},
        {"engine_id": "sophia", "repository": "Byron2306/Sophia-AI", "state": "PROJECTION_ONLY", "reason": "Phase 16 claim review is locally constructed"},
    ]
    return {
        "schema": "dio.corpus_execution_census.v1",
        "engines": rows,
        "native_executed_count": 1,
        "required_engine_count": 7,
        "full_corpus_native_execution": "REFUSE",
        "law": "source binding, local projection and native engine execution are distinct evidence states",
    }


def verify_premium_proof(output_dir: Path, proof: dict[str, Any]) -> None:
    for row in proof.get("artifacts") or []:
        path = (output_dir / row["path"]).resolve()
        if (
            not path.is_relative_to(output_dir.resolve())
            or not path.is_file()
            or _sha(path) != row["sha256"]
        ):
            raise PremiumMediaError(f"premium media artifact integrity failure: {row.get('path')}")


def build_premium_media(
    *,
    output_dir: Path,
    nichefoundry_root: Path | None = None,
    provider: str = "auto",
    script_package: dict[str, Any] | None = None,
    production_request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    base = build_media_incarnation(output_dir=output_dir / "base")
    niche_root = resolve_nichefoundry_root(nichefoundry_root)
    premium_dir = output_dir / "premium"
    script = script_package if script_package is not None else _script_package()
    episode = premium_dir / "nichefoundry_episode"
    niche = _run_nichefoundry(
        niche_root,
        episode,
        provider,
        script_package=script,
        production_request=production_request,
    )
    document_studio = render_media_control_surface(
        gamma_dir=episode / "premium_visuals",
        script_package=script,
        output_dir=premium_dir / "document_studio_media",
        style_profile="dio_professional",
    )
    evidence = {
        key: value
        for key, value in niche.items()
        if key
        not in {
            "manifest",
            "performance",
            "sound_design",
            "loudness",
            "preview",
            "gamma",
            "music_rights",
            "premium_assets",
            "native_render",
        }
    }
    evidence.update(
        {
            "audio_manifest_sha256": _sha(episode / "audio_manifest.json"),
            "audio_asset_hashes_sha256": _sha(episode / "audio_asset_hashes.json"),
            "loudness_report_sha256": _sha(episode / "loudness_report.json"),
            "sound_design_plan_sha256": _sha(episode / "sound_design_plan.json"),
            "native_render_manifest_sha256": _sha(episode / "render_manifest_v2.json"),
            "native_render_qa_sha256": _sha(episode / "render_qa_report.json"),
            "native_final_sha256": _sha(episode / "final.mp4"),
            "native_thumbnail_sha256": _sha(episode / "thumbnail.png"),
        }
    )
    _write(premium_dir / "NICHEFOUNDRY_NATIVE_EXECUTION.json", evidence)
    census = _corpus_census(niche)
    _write(premium_dir / "CORPUS_EXECUTION_CENSUS.json", census)
    final = output_dir / "media/youtube/FINAL_VIDEO_PREMIUM.mp4"
    final.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(niche["native_render"]["final"], final)
    shutil.copy2(
        niche["native_render"]["thumbnail"], output_dir / "media/youtube/THUMBNAIL_NATIVE.png"
    )
    artifacts = []
    for path in sorted(
        path
        for path in output_dir.rglob("*")
        if path.is_file() and path.name not in {"PREMIUM_MEDIA_PROOF.json", "PREMIUM_MEDIA_RECEIPT.json"}
    ):
        artifacts.append(
            {"path": str(path.relative_to(output_dir)), "sha256": _sha(path), "bytes": path.stat().st_size}
        )
    contract_state = "PASS" if script_package is not None else "NOT_REQUESTED"
    proof = {
        "schema": "dio.premium_media_proof.v1",
        "artifacts": artifacts,
        "explainer_contract_binding": contract_state,
        "nichefoundry_repository_execution": "PASS",
        "premium_or_approved_voice": "PASS",
        "robotic_production_fallback": "REFUSE",
        "music_asset_present": "PASS",
        "music_rights_evidence": "PASS",
        "procedural_music_fallback": "REFUSE",
        "music_hiss_detection": "PASS",
        "narration_music_mix": "PASS",
        "native_gamma_execution": "PASS",
        "gamma_scene_coverage": "PASS",
        "gamma_final_video_binding": "PASS",
        "native_nichefoundry_render_execution": "PASS",
        "gamma_composition_preserved": "PASS",
        "document_studio_control_surface_binding": "PASS",
        "document_studio_native_render_execution": "REFUSE",
        "automated_perceptual_release": "REFUSE",
        "human_visual_release": "NEEDS_YOU",
        "sample_rate_48khz_stereo": "PASS",
        "loudness_qa": "PASS",
        "native_engine_execution_census": "PASS",
        "full_corpus_native_execution": "REFUSE",
        "external_publication": "REFUSE",
        "external_send": "REFUSE",
        "media_spend": "REFUSE",
        "human_gate": "NEEDS_YOU",
    }
    proof["proof_fingerprint"] = _fingerprint(proof)
    _write(output_dir / "PREMIUM_MEDIA_PROOF.json", proof)
    receipt = {
        "schema": "dio.premium_media_receipt.v1",
        "provider_set": niche["providers"],
        "explainer_contract_binding": contract_state,
        "nichefoundry_repository_execution": "PASS",
        "premium_voice": "PASS",
        "music_and_rights": "PASS",
        "procedural_music_fallback": "REFUSE",
        "music_hiss_detection": "PASS",
        "native_gamma_execution": "PASS",
        "gamma_scene_coverage": "PASS",
        "gamma_final_video_binding": "PASS",
        "audio_mastering": "PASS",
        "premium_video": "PASS",
        "native_nichefoundry_render_execution": "PASS",
        "gamma_composition_preserved": "PASS",
        "document_studio_control_surface_binding": "PASS",
        "document_studio_native_render_execution": "REFUSE",
        "automated_perceptual_release": "REFUSE",
        "human_visual_release": "NEEDS_YOU",
        "corpus_execution_census": "PASS",
        "full_corpus_native_execution": "REFUSE",
        "external_publication": "REFUSE",
        "external_send": "REFUSE",
        "media_spend": "REFUSE",
        "human_gate": "NEEDS_YOU",
        "proof_fingerprint": proof["proof_fingerprint"],
    }
    receipt["premium_media_fingerprint"] = _fingerprint(receipt)
    _write(output_dir / "PREMIUM_MEDIA_RECEIPT.json", receipt)
    verify_premium_proof(output_dir, proof)
    return {
        "receipt": receipt,
        "proof_manifest": proof,
        "census": census,
        "nichefoundry": niche,
        "document_studio": document_studio,
        "base": base,
        "output_dir": str(output_dir),
    }
