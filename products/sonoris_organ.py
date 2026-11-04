"""Governed local job adapter for the experimental Sonoris audio tools."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

SONORIS = Path("/data/byron/sonoris")
DEFAULT_MIDI = Path("/home/byron/sonoris-chimera-recovery/exp002-multigenre/F")
DEFAULT_SF2 = Path("/usr/share/sounds/sf2/FluidR3_GM.sf2")
POLLY_ROOT = Path("/home/byron/polly-music-lab")
ACOUSTIC_IRON_INSTRUMENTS = POLLY_ROOT / "fusion_lab/data/production/instruments.dio-sonoris-acoustic-iron-v001.json"
ACOUSTIC_IRON_TONES = POLLY_ROOT / "fusion_lab/data/production/tone-profiles.dio-sonoris-acoustic-iron-v001.json"


class SonorisError(RuntimeError):
    pass


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _inventory_sources(source: Path) -> list[dict[str, Any]]:
    midi = sorted(source.glob("*.mid"))
    if not midi:
        raise SonorisError(f"no MIDI source files found in {source}")
    return [{"name": file.name, "sha256": _sha(file), "bytes": file.stat().st_size} for file in midi]


def _audio_python() -> tuple[str, dict[str, bool]]:
    candidates = [os.environ.get("DIO_SONORIS_PYTHON"), str(POLLY_ROOT / ".venv/bin/python"), sys.executable]
    for candidate in candidates:
        if not candidate or not Path(candidate).is_file():
            continue
        probe = subprocess.run([candidate, "-c", "import numpy, scipy, soundfile"],
                               capture_output=True, text=True, check=False, timeout=15)
        if probe.returncode == 0:
            return candidate, {name: True for name in ("numpy", "scipy", "soundfile")}
    return sys.executable, {name: importlib.util.find_spec(name) is not None
                            for name in ("numpy", "scipy", "soundfile")}


def capability_snapshot(*, source_dir: str | Path = DEFAULT_MIDI,
                        sf2_path: str | Path = DEFAULT_SF2) -> dict[str, Any]:
    """Read-only local availability and honest readiness status."""
    source, sf2 = Path(source_dir), Path(sf2_path)
    chimera = SONORIS / "tools/CHIMERA_RECONSTRUCTION_V1/chimera_reconstruct.py"
    bass = SONORIS / "tools/SONORIS_BASS_GAUNTLET_V1/bass_gauntlet.py"
    missing = []
    if not source.is_dir(): missing.append(f"MIDI source directory missing: {source}")
    if not sf2.is_file(): missing.append(f"FluidR3 GM soundfont missing: {sf2}")
    if not shutil.which("fluidsynth"): missing.append("fluidsynth executable missing")
    if not chimera.is_file(): missing.append(f"Chimera renderer missing: {chimera}")
    audio_python, deps = _audio_python()
    if not all(deps.values()): missing.append("audio Python dependencies incomplete: " + ", ".join(k for k,v in deps.items() if not v))
    sources = _inventory_sources(source) if source.is_dir() else []
    return {
        "schema": "dio.sonoris.capability_snapshot.v1", "organ": "sonoris",
        "state": "AVAILABLE_FOR_STAGING" if not missing else "BLOCKED_PREFLIGHT",
        "source_dir": str(source.resolve()) if source.exists() else str(source),
        "source_midi": sources, "source_count": len(sources),
        "soundfont": str(sf2), "soundfont_sha256": _sha(sf2) if sf2.is_file() else None,
        "tools": {"chimera": str(chimera), "bass_gauntlet": str(bass),
                  "fluidsynth": shutil.which("fluidsynth"), "python": audio_python},
        "python_dependencies": deps, "preflight_gaps": missing,
        "commercial_clearance": "UNVERIFIED", "human_sonic_review": "REQUIRED",
        "external_effects": False,
    }


def prepare_chimera_job(*, output_dir: str | Path, source_dir: str | Path = DEFAULT_MIDI,
                        sf2_path: str | Path = DEFAULT_SF2, start_seconds: float = 30,
                        duration_seconds: float = 18, control_wav: str | Path | None = None,
                        owner_authorized: bool = False) -> dict[str, Any]:
    """Create an auditable job packet; execution happens only when run_job is called."""
    if owner_authorized is not True:
        raise SonorisError("owner_authorized=true is required to process the owner's musical source")
    if start_seconds < 0 or duration_seconds <= 0:
        raise SonorisError("excerpt start must be nonnegative and duration must be positive")
    snapshot = capability_snapshot(source_dir=source_dir, sf2_path=sf2_path)
    if snapshot["state"] != "AVAILABLE_FOR_STAGING":
        raise SonorisError("Sonoris preflight is blocked: " + "; ".join(snapshot["preflight_gaps"]))
    source, sf2 = Path(source_dir).resolve(), Path(sf2_path).resolve()
    renderer = SONORIS / "tools/CHIMERA_RECONSTRUCTION_V1/chimera_reconstruct.py"
    out = Path(output_dir).resolve()
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise SonorisError("Sonoris output directory must be empty; existing experiment evidence is never overwritten")
    audio_python, _ = _audio_python()
    command = [audio_python, str(renderer), "--source", str(source), "--output", str(out),
               "--sf2", str(sf2), "--start", str(start_seconds), "--seconds", str(duration_seconds)]
    control = Path(control_wav).resolve() if control_wav else None
    if control:
        if not control.is_file(): raise SonorisError(f"control audio missing: {control}")
        command += ["--control", str(control)]
    return {
        "schema": "dio.sonoris.job_spec.v1", "job_type": "chimera_genre_fusion_reconstruction",
        "state": "STAGED_NOT_RUN", "command": command, "output_dir": str(out),
        "source_dir": str(source), "sf2_path": str(sf2), "control_wav": str(control) if control else None,
        "source_midi": snapshot["source_midi"], "soundfont_sha256": snapshot["soundfont_sha256"],
        "control_wav_sha256": _sha(control) if control else None,
        "excerpt": {"start_seconds": start_seconds, "duration_seconds": duration_seconds},
        "instrument_truth": "FluidR3 GM render; not original instrument chain",
        "commercial_clearance": "UNVERIFIED", "human_sonic_review": "REQUIRED",
        "owner_authorized": True, "external_effects": False,
        "release_authorized": False,
    }


def run_job(job: dict[str, Any], *, execute: bool = False, owner_authorized: bool = False) -> dict[str, Any]:
    """Run a previously staged local job only with explicit execute=True."""
    if execute is not True:
        return job
    if job.get("schema") != "dio.sonoris.job_spec.v1" or job.get("owner_authorized") is not True or owner_authorized is not True:
        raise SonorisError("refusing unrecognized or unauthorized Sonoris job")
    command = job.get("command")
    if not isinstance(command, list) or not command:
        raise SonorisError("job has no staged command")
    out = Path(str(job.get("output_dir", ""))).resolve()
    renderer = (SONORIS / "tools/CHIMERA_RECONSTRUCTION_V1/chimera_reconstruct.py").resolve()
    audio_python, _ = _audio_python()
    expected = [audio_python, str(renderer), "--source", str(Path(job["source_dir"]).resolve()),
                "--output", str(out), "--sf2", str(Path(job["sf2_path"]).resolve()),
                "--start", str(job["excerpt"]["start_seconds"]), "--seconds", str(job["excerpt"]["duration_seconds"])]
    if job.get("control_wav"):
        expected += ["--control", str(Path(job["control_wav"]).resolve())]
    if command != expected:
        raise SonorisError("staged command does not match the validated Sonoris job fields")
    source_dir, sf2_path = Path(job["source_dir"]).resolve(), Path(job["sf2_path"]).resolve()
    if _inventory_sources(source_dir) != job.get("source_midi") or _sha(sf2_path) != job.get("soundfont_sha256"):
        raise SonorisError("source MIDI or soundfont changed after staging; create a fresh job spec")
    if job.get("control_wav") and _sha(Path(job["control_wav"]).resolve()) != job.get("control_wav_sha256"):
        raise SonorisError("control audio changed after staging; create a fresh job spec")
    spec_path = out / "DIO_SONORIS_JOB_SPEC.json"
    if (not out.is_dir() or not spec_path.is_file() or spec_path.is_symlink()
            or {p.name for p in out.iterdir()} != {spec_path.name}):
        raise SonorisError("expected only the staged job spec in output directory; refusing to overwrite")
    if json.loads(spec_path.read_text(encoding="utf-8")) != job:
        raise SonorisError("job spec differs from the staged file in its output directory")
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    job = dict(job)
    job["state"] = "COMPLETE" if result.returncode == 0 else "FAILED"
    job["returncode"] = result.returncode
    job["stdout_tail"] = result.stdout[-4000:]
    job["stderr_tail"] = result.stderr[-4000:]
    job["artifacts"] = []
    if result.returncode == 0:
        for file in sorted(out.rglob("*")):
            if file.is_file(): job["artifacts"].append({"path": str(file.relative_to(out)), "bytes": file.stat().st_size, "sha256": _sha(file)})
        job["state"] = "COMPLETE_REVIEW_REQUIRED"
        job["native_receipt"] = str(out / "RECEIPT.json")
    job["human_sonic_review"] = "REQUIRED"
    job["commercial_clearance"] = "UNVERIFIED"
    job["release_authorized"] = False
    out.mkdir(parents=True, exist_ok=True)
    (out / "DIO_SONORIS_JOB_RECEIPT.json").write_text(json.dumps(job, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return job


def polly_compiler_snapshot() -> dict[str, Any]:
    """Inspect DIO's bound Polly composition/render pipeline and experimental SFZ profile."""
    renderer = shutil.which("sfizz_render")
    python = POLLY_ROOT / ".venv/bin/python"
    required = [POLLY_ROOT / "fusion_lab/production_pipeline.py", ACOUSTIC_IRON_INSTRUMENTS, ACOUSTIC_IRON_TONES]
    gaps = [f"missing {path}" for path in required if not path.is_file()]
    if not python.is_file():
        gaps.append(f"missing Polly environment: {python}")
    elif subprocess.run([str(python), "-c", "import mido"], capture_output=True, check=False).returncode:
        gaps.append("Polly virtual environment is missing mido")
    if not renderer: gaps.append("sfizz_render is unavailable on PATH")
    if shutil.which("ffmpeg") is None: gaps.append("ffmpeg is unavailable on PATH")
    sources = {}
    if ACOUSTIC_IRON_INSTRUMENTS.is_file():
        cfg = json.loads(ACOUSTIC_IRON_INSTRUMENTS.read_text(encoding="utf-8"))
        for layer, row in cfg["layers"].items():
            sfz = Path(row["sfz_path"])
            sources[layer] = {"id": row["id"], "source_id": row["source_id"],
                              "version": row["source_version"], "license": row.get("license", "UNSPECIFIED"),
                              "sfz_path": str(sfz), "available": sfz.is_file(),
                              "sfz_sha256": _sha(sfz) if sfz.is_file() else None}
            if not sfz.is_file(): gaps.append(f"missing SFZ for {layer}: {sfz}")
    return {"schema": "dio.sonoris.polly_capability_snapshot.v1", "compiler_root": str(POLLY_ROOT),
            "python": str(python), "sfizz_render": renderer,
            "pipeline": "fusion_lab.production_pipeline.render_chainsaw_production",
            "host": "host-003-chainsaw-diplomacy", "profile": "dio-sonoris-acoustic-iron-v001",
            "instrument_sources": sources, "preflight_gaps": gaps,
            "state": "AVAILABLE_FOR_LOCAL_EXPERIMENT" if not gaps else "BLOCKED_PREFLIGHT",
            "external_effects": False, "human_listening_review": "REQUIRED",
            "commercial_validation": "UNPROVED"}


def bind_polly_render_receipt(output_dir: str | Path) -> dict[str, Any]:
    """Bind an existing Polly render to DIO provenance and review gates."""
    out = Path(output_dir).resolve()
    try:
        out.relative_to((SONORIS / "rendered").resolve())
    except ValueError as exc:
        raise SonorisError("Polly render output must remain under /data/byron/sonoris/rendered") from exc
    native_path = out / "production-manifest.json"
    if not native_path.is_file(): raise SonorisError("Polly output is missing production-manifest.json")
    native = json.loads(native_path.read_text(encoding="utf-8"))
    if native.get("host_id") != "host-003-chainsaw-diplomacy":
        raise SonorisError("Polly manifest does not match the expected Chainsaw Diplomacy host")
    instrument_cfg = json.loads(ACOUSTIC_IRON_INSTRUMENTS.read_text(encoding="utf-8"))
    expected_ids = {layer: row["id"] for layer, row in instrument_cfg["layers"].items()}
    actual_ids = {layer: row["id"] for layer, row in native.get("instruments", {}).items()}
    if actual_ids != expected_ids: raise SonorisError("rendered instrument IDs do not match the pinned profile")
    outputs = []
    declared = [("mix", native.get("mix", {}))]
    declared.extend((f"stem:{name}", row) for name, row in native.get("stems", {}).items())
    for label, row in declared:
        relative = row.get("path")
        if not relative: raise SonorisError(f"Polly manifest has no output path for {label}")
        path = Path(relative).resolve()
        if not path.is_relative_to(out) or not path.is_file():
            raise SonorisError(f"Polly render artifact missing or outside output directory: {relative}")
        digest = _sha(path)
        if digest != row.get("sha256"):
            raise SonorisError(f"Polly render artifact hash mismatch: {relative}")
        outputs.append({"path": str(path.relative_to(out)), "bytes": path.stat().st_size, "sha256": digest})
    preview = out / "LISTENING_PREVIEW.mp3"
    if preview.is_file():
        outputs.append({"path": preview.name, "bytes": preview.stat().st_size, "sha256": _sha(preview),
                        "kind": "loudness_normalized_audition_copy_not_release_master"})
    receipt = {
        "schema": "dio.sonoris.polly_production_receipt.v1", "experiment_id": "dio-sonoris-acoustic-iron-v001",
        "host_id": native["host_id"], "bpm": native.get("bpm"), "meter": native.get("meter"),
        "bars": native.get("bars"), "structural_signature": native.get("structural_signature"),
        "instrument_profile_path": str(ACOUSTIC_IRON_INSTRUMENTS),
        "instrument_profile_sha256": _sha(ACOUSTIC_IRON_INSTRUMENTS),
        "tone_profile_path": str(ACOUSTIC_IRON_TONES), "tone_profile_sha256": _sha(ACOUSTIC_IRON_TONES),
        "instrument_sources": {layer: {"id": row["id"], "source_id": row["source_id"],
            "source_version": row["source_version"], "license": row.get("license"),
            "source_url": row.get("source_url"), "sfz_path": row["sfz_path"],
            "sfz_sha256": _sha(Path(row["sfz_path"]))} for layer, row in instrument_cfg["layers"].items()},
        "native_manifest_sha256": _sha(native_path), "outputs": outputs,
        "human_review_required": True, "musical_acceptance": "PENDING_USER_AUDITION",
        "commercial_validation": "UNPROVED", "release_authorized": False, "external_effects": False,
    }
    quality_path = out / "AUDIO_QUALITY_REVIEW.json"
    if quality_path.is_file():
        receipt["measured_audio_quality"] = json.loads(quality_path.read_text(encoding="utf-8"))
        receipt["audio_quality_review_sha256"] = _sha(quality_path)
    receipt_path = out / "DIO_SONORIS_PRODUCTION_RECEIPT.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return receipt


def run_acoustic_iron_experiment(*, output_dir: str | Path, owner_authorized: bool = False) -> dict[str, Any]:
    """Run the pinned Polly compiler profile as a local, review-held experiment."""
    if owner_authorized is not True:
        raise SonorisError("owner_authorized=true is required to render the owner's musical composition")
    snapshot = polly_compiler_snapshot()
    if snapshot["state"] != "AVAILABLE_FOR_LOCAL_EXPERIMENT":
        raise SonorisError("Polly compiler preflight is blocked: " + "; ".join(snapshot["preflight_gaps"]))
    out = Path(output_dir).resolve()
    try:
        out.relative_to((SONORIS / "rendered").resolve())
    except ValueError as exc:
        raise SonorisError("Polly render output must remain under /data/byron/sonoris/rendered") from exc
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise SonorisError("Polly experiment output must be empty; existing experiment evidence is never overwritten")
    command = [str(POLLY_ROOT / ".venv/bin/python"), "-m", "fusion_lab", "render-host003-production",
               "--out", str(out), "--instrument-config", str(ACOUSTIC_IRON_INSTRUMENTS),
               "--tone-config", str(ACOUSTIC_IRON_TONES), "--seed", "1988", "--sample-rate", "48000",
               "--sfizz-render", str(snapshot["sfizz_render"])]
    result = subprocess.run(command, cwd=POLLY_ROOT, capture_output=True, text=True, check=False)
    if result.returncode:
        out.mkdir(parents=True, exist_ok=True)
        failure = {"schema": "dio.sonoris.polly_run_failure.v1", "command": command,
                   "returncode": result.returncode, "stdout_tail": result.stdout[-4000:],
                   "stderr_tail": result.stderr[-4000:], "release_authorized": False,
                   "external_effects": False}
        (out / "DIO_SONORIS_RUN_FAILURE.json").write_text(json.dumps(failure, indent=2) + "\n", encoding="utf-8")
        raise SonorisError(f"Polly production render failed (exit {result.returncode}); see DIO_SONORIS_RUN_FAILURE.json")
    receipt = bind_polly_render_receipt(out)
    receipt.update({"command": command, "returncode": result.returncode, "stdout_tail": result.stdout[-2000:],
                    "stderr_tail": result.stderr[-2000:], "execution_location": "local_polly_sfizz"})
    (out / "DIO_SONORIS_PRODUCTION_RECEIPT.json").write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return receipt


def run_glass_meridian_experiment(*, output_dir: str | Path, owner_authorized: bool = False) -> dict[str, Any]:
    """Build and render the authored Jazz Synth Fusion grammar prototype locally."""
    if owner_authorized is not True:
        raise SonorisError("owner_authorized=true is required to render a Sonoris composition")
    script = Path(__file__).resolve().parents[1] / "scripts/build_sonoris_glass_meridian.py"
    python = POLLY_ROOT / ".venv/bin/python"
    if not script.is_file(): raise SonorisError(f"missing Sonoris composition script: {script}")
    if not python.is_file(): raise SonorisError(f"missing Polly MIDI/audio environment: {python}")
    if not shutil.which("fluidsynth"): raise SonorisError("fluidsynth is unavailable on PATH")
    if not DEFAULT_SF2.is_file(): raise SonorisError(f"missing FluidR3 GM soundfont: {DEFAULT_SF2}")
    out = Path(output_dir).resolve()
    try:
        out.relative_to((SONORIS / "rendered").resolve())
    except ValueError as exc:
        raise SonorisError("Sonoris composition output must remain under /data/byron/sonoris/rendered") from exc
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise SonorisError("Sonoris composition output must be empty; existing review evidence is never overwritten")
    command = [str(python), str(script), "--out", str(out), "--sf2", str(DEFAULT_SF2)]
    result = subprocess.run(command, cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, check=False)
    if result.returncode:
        out.mkdir(parents=True, exist_ok=True)
        failure = {"schema": "dio.sonoris.composition_failure.v1", "command": command,
                   "returncode": result.returncode, "stdout_tail": result.stdout[-4000:],
                   "stderr_tail": result.stderr[-4000:], "release_authorized": False}
        (out / "DIO_SONORIS_COMPOSITION_FAILURE.json").write_text(json.dumps(failure, indent=2) + "\n", encoding="utf-8")
        raise SonorisError(f"Glass Meridian render failed (exit {result.returncode}); see DIO_SONORIS_COMPOSITION_FAILURE.json")
    return json.loads(result.stdout)


def genre_compiler_snapshot() -> dict[str, Any]:
    """Expose the behavior-first genre grammar catalog through the Sonoris organ."""
    from products.sonoris_genre_compiler import genre_catalog_snapshot
    return genre_catalog_snapshot()


def compile_genre_composition(request: dict[str, Any]) -> dict[str, Any]:
    """Compile a composition brief into a governed, behavior-first plan."""
    from products.sonoris_genre_compiler import compile_composition_request
    return compile_composition_request(request)


def audit_genre_composition(plan: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    """Evaluate measured MIDI/audio evidence without treating a plan as proof."""
    from products.sonoris_genre_compiler import audit_composition_evidence
    return audit_composition_evidence(plan, evidence)
