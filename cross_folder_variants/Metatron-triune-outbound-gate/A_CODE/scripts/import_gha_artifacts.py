#!/usr/bin/env python3
"""
import_gha_artifacts.py
=======================
Imports downloaded GitHub Actions sweep artifacts into the Metatron container
and regenerates TVRs + coverage summary, then reports promotion results.

Workflow:
  1. Download all 3 artifact ZIPs from the GitHub Actions run
  2. Extract them into a single directory (or let this script unzip them)
  3. Run this script pointing at that directory

Usage:
    # Point at a directory containing extracted run_*.json files
    python scripts/import_gha_artifacts.py --artifacts-dir ~/Downloads/sweep-artifacts

    # Or point at a directory of ZIP files to auto-extract
    python scripts/import_gha_artifacts.py --artifacts-dir ~/Downloads/sweep-zips --unzip

    # Dry run — show what would be promoted without writing
    python scripts/import_gha_artifacts.py --artifacts-dir ~/Downloads/sweep-artifacts --dry-run

Options:
    --artifacts-dir PATH   Directory with run_*.json files (or ZIPs if --unzip)
    --container NAME       Docker container name (default: metatron-seraph-v9-backend-1)
    --unzip                Extract *.zip files in artifacts-dir before importing
    --dry-run              Show promotion preview without copying files
    --techniques T1006,... Only import runs for these techniques
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


CONTAINER_RESULTS_DIR = "/var/lib/seraph-ai/artifacts/atomic-validation"
CONTAINER_EVIDENCE_DIR = "/var/lib/seraph-ai/evidence-bundle"


def detect_backend_container(preferred: str | None = None) -> str:
    candidates = []
    if preferred:
        candidates.append(preferred)
    candidates.extend([
        os.environ.get("SERAPH_BACKEND_CONTAINER", "").strip(),
        "seraph-backend",
        "metatron-seraph-v9-backend-1",
    ])
    seen = set()
    for name in candidates:
        if not name or name in seen:
            continue
        seen.add(name)
        result = subprocess.run(
            ["docker", "ps", "--filter", f"name=^/{name}$", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip() == name:
            return name
    return preferred or "seraph-backend"


def find_run_files(directory: Path) -> list[Path]:
    return sorted(directory.rglob("run_*.json"))


def filter_by_techniques(run_files: list[Path], technique_filter: set[str]) -> list[Path]:
    if not technique_filter:
        return run_files
    filtered = []
    for f in run_files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            techs = {t.upper() for t in (data.get("techniques_executed") or data.get("techniques") or [])}
            if techs & technique_filter:
                filtered.append(f)
        except Exception:
            pass
    return filtered


def copy_to_container(run_files: list[Path], container: str, dry_run: bool, local_results_dir: Path | None = None) -> int:
    """Copy run_*.json files into the container's atomic-validation dir or a local directory."""
    if not run_files:
        print("No run files to copy.", flush=True)
        return 0

    if local_results_dir is not None:
        local_results_dir.mkdir(parents=True, exist_ok=True)
        copied = 0
        for run_file in run_files:
            dest = local_results_dir / run_file.name
            if dest.resolve() == run_file.resolve():
                copied += 1
                continue
            if dry_run:
                print(f"  [dry-run] would copy {run_file.name} → {dest}", flush=True)
                copied += 1
                continue
            shutil.copy2(run_file, dest)
            copied += 1
        return copied

    copied = 0
    for run_file in run_files:
        dest = f"{container}:{CONTAINER_RESULTS_DIR}/{run_file.name}"
        if dry_run:
            print(f"  [dry-run] would copy {run_file.name} → container", flush=True)
            copied += 1
            continue
        result = subprocess.run(
            ["docker", "cp", str(run_file), dest],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            copied += 1
        else:
            print(f"  WARN: failed to copy {run_file.name}: {result.stderr.strip()}", flush=True)

    return copied


def docker_exec(container: str, python_code: str, dry_run: bool, local_mode: bool = False) -> str:
    """Run a Python snippet inside the container and return stdout."""
    if dry_run:
        target = "local" if local_mode else "container"
        print(f"  [dry-run] would exec in {target}:\n{python_code[:200]}", flush=True)
        return ""
    if local_mode:
        result = subprocess.run(
            ["python3", "-c", python_code],
            capture_output=True, text=True
        )
    else:
        result = subprocess.run(
            ["docker", "exec", container, "python3", "-c", python_code],
            capture_output=True, text=True
        )
    if result.returncode != 0:
        print(f"  WARN: {'local exec' if local_mode else 'docker exec'} failed: {result.stderr.strip()}", flush=True)
    return result.stdout.strip()


def get_current_scores(container: str, local_mode: bool = False, evidence_root: Path | None = None) -> dict[str, str]:
    """Return technique_id → tier for all techniques currently in the bundle."""
    if local_mode:
        root = evidence_root or EVIDENCE_ROOT
        p = root / "coverage_summary.json"
        if not p.exists():
            return {}
        try:
            data = json.loads(p.read_text())
            return {t['technique_id']: t['tier'] for t in data.get('techniques', [])}
        except Exception:
            return {}
    code = """
import json
from pathlib import Path
p = Path('/var/lib/seraph-ai/evidence-bundle/coverage_summary.json')
data = json.loads(p.read_text())
out = {t['technique_id']: t['tier'] for t in data.get('techniques', [])}
print(json.dumps(out))
"""
    raw = docker_exec(container, code, dry_run=False)
    try:
        return json.loads(raw)
    except Exception:
        return {}


def regenerate_tvrs(container: str, technique_ids: list[str], dry_run: bool, local_mode: bool = False, evidence_root: Path | None = None, results_dir: Path | None = None) -> dict:
    """Regenerate TVRs for the affected techniques and rebuild coverage summary."""
    techs_json = json.dumps(technique_ids)
    if local_mode:
        root = evidence_root or EVIDENCE_ROOT
        results_path = results_dir or Path(os.environ.get("ATOMIC_VALIDATION_RESULTS_DIR", "/var/lib/seraph-ai/atomic-validation"))
        code = f"""
import json, os, sys
from pathlib import Path
sys.path.insert(0, os.getcwd() + '/backend')
os.environ['EVIDENCE_BUNDLE_ROOT'] = {json.dumps(str(root))}
os.environ['ATOMIC_VALIDATION_RESULTS_DIR'] = {json.dumps(str(results_path))}
from evidence_bundle import EvidenceBundleManager
mgr = EvidenceBundleManager(Path({json.dumps(str(root))}))
mgr._atomic_runs_cache = None
results = {{}}
for tid in {techs_json}:
    try:
        record = mgr.generate_tvr_for_technique(tid)
        mgr.write_tvr(tid, record)
        score = record.get('promotion', {{}}).get('score', 0)
        tier = record.get('promotion', {{}}).get('tier_name', 'none')
        results[tid] = {{'score': score, 'tier': tier}}
    except Exception as e:
        results[tid] = {{'score': -1, 'tier': 'error', 'err': str(e)}}
mgr._atomic_runs_cache = None
mgr.build_coverage_summary()
print(json.dumps(results))
"""
        raw = docker_exec(container, code, dry_run, local_mode=True)
    else:
        code = f"""
import json, sys
sys.path.insert(0, '/app/backend')
try:
    from evidence_bundle import EvidenceBundleManager
    mgr = EvidenceBundleManager()
    mgr._atomic_runs_cache = None  # force reload
    results = {{}}
    for tid in {techs_json}:
        try:
            record = mgr.generate_tvr_for_technique(tid)
            mgr.write_tvr(tid, record)
            score = record.get('promotion', {{}}).get('score', 0)
            tier = record.get('promotion', {{}}).get('tier_name', 'none')
            results[tid] = {{'score': score, 'tier': tier}}
        except Exception as e:
            results[tid] = {{'score': -1, 'tier': 'error', 'err': str(e)}}
    mgr._atomic_runs_cache = None
    mgr.build_coverage_summary()
    print(json.dumps(results))
except Exception as e:
    print(json.dumps({{'_fatal': str(e)}}))
"""
        raw = docker_exec(container, code, dry_run)
    if dry_run:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        print(f"  WARN: could not parse TVR regeneration output: {raw[:200]}", flush=True)
        return {}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifacts-dir", required=True)
    parser.add_argument("--container", default="")
    parser.add_argument("--unzip", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--techniques", default="")
    parser.add_argument("--local", action="store_true", help="Run entirely on the local filesystem instead of Docker")
    parser.add_argument("--results-dir", default="", help="Local atomic-validation results directory to use in --local mode")
    parser.add_argument("--evidence-root", default="", help="Local evidence bundle root to use in --local mode")
    args = parser.parse_args()

    artifacts_dir = Path(args.artifacts_dir).expanduser().resolve()
    if not artifacts_dir.exists():
        print(f"ERROR: --artifacts-dir {artifacts_dir} does not exist", flush=True)
        sys.exit(1)

    technique_filter: set[str] = set()
    if args.techniques:
        technique_filter = {t.strip().upper() for t in args.techniques.split(",") if t.strip()}

    # Auto-extract ZIPs if requested
    work_dir = artifacts_dir
    if args.unzip:
        work_dir = Path(tempfile.mkdtemp(prefix="gha_artifacts_"))
        print(f"Extracting ZIPs to {work_dir} ...", flush=True)
        for zf in artifacts_dir.glob("*.zip"):
            with zipfile.ZipFile(zf) as z:
                z.extractall(work_dir)
        print(f"Extracted {len(list(artifacts_dir.glob('*.zip')))} ZIP(s)", flush=True)

    # Find all run_*.json files
    run_files = find_run_files(work_dir)
    if not run_files:
        print(f"ERROR: no run_*.json files found in {work_dir}", flush=True)
        sys.exit(1)

    # Filter by technique if requested
    if technique_filter:
        run_files = filter_by_techniques(run_files, technique_filter)

    # Determine which techniques are covered by these runs
    technique_ids: set[str] = set()
    pass_counts: dict[str, int] = {}
    for f in run_files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if data.get("status") != "success":
                continue
            for t in (data.get("techniques_executed") or []):
                tid = t.upper()
                technique_ids.add(tid)
                pass_counts[tid] = pass_counts.get(tid, 0) + 1
        except Exception:
            pass

    print(f"\nArtifacts dir : {work_dir}", flush=True)
    print(f"Run files found: {len(run_files)}", flush=True)
    print(f"Techniques covered: {len(technique_ids)}", flush=True)
    print(f"Techniques with 3+ passes: {sum(1 for c in pass_counts.values() if c >= 3)}", flush=True)
    if args.dry_run:
        print("\n[DRY RUN] No files will be written.\n", flush=True)

    local_mode = bool(args.local)
    evidence_root = Path(args.evidence_root).expanduser().resolve() if args.evidence_root else None
    results_dir = Path(args.results_dir).expanduser().resolve() if args.results_dir else None
    if not local_mode:
        args.container = detect_backend_container(args.container or None)

    # Snapshot current scores before import
    if not args.dry_run:
        print("\nSnapshotting current scores ...", flush=True)
        before = get_current_scores(args.container, local_mode=local_mode, evidence_root=evidence_root)
    else:
        before = {}

    # Copy run files into container
    print(f"\nCopying {len(run_files)} run files into container ...", flush=True)
    copied = copy_to_container(run_files, args.container, args.dry_run, local_results_dir=results_dir if local_mode else None)
    print(f"Copied: {copied}", flush=True)

    # Regenerate TVRs + coverage summary
    sorted_techs = sorted(technique_ids)
    print(f"\nRegenerating TVRs for {len(sorted_techs)} techniques ...", flush=True)
    results = regenerate_tvrs(args.container, sorted_techs, args.dry_run, local_mode=local_mode, evidence_root=evidence_root, results_dir=results_dir)

    if "_fatal" in results:
        print(f"FATAL during TVR regeneration: {results['_fatal']}", flush=True)
        sys.exit(1)

    # Print promotion report
    promoted = []
    stayed = []
    errors = []

    for tid, r in sorted(results.items()):
        if r.get("score", -1) < 0:
            errors.append((tid, r.get("err", "unknown error")))
            continue
        old_tier = before.get(tid, "unknown")
        new_tier = r["tier"]
        new_score = r["score"]
        if old_tier != new_tier:
            promoted.append((tid, old_tier, new_tier, new_score))
        else:
            stayed.append((tid, new_tier, new_score, pass_counts.get(tid, 0)))

    print("\n" + "=" * 64, flush=True)
    print("PROMOTION REPORT", flush=True)
    print("=" * 64, flush=True)

    if promoted:
        print(f"\nPromoted ({len(promoted)}):", flush=True)
        for tid, old, new, score in sorted(promoted, key=lambda x: x[0]):
            print(f"  {tid:20s}  {old:8s} → {new:8s}  (S{score})", flush=True)

    if stayed:
        print(f"\nUnchanged ({len(stayed)}):", flush=True)
        for tid, tier, score, passes in sorted(stayed, key=lambda x: x[0]):
            print(f"  {tid:20s}  {tier:8s}  S{score}  ({passes} pass(es))", flush=True)

    if errors:
        print(f"\nErrors ({len(errors)}):", flush=True)
        for tid, err in errors:
            print(f"  {tid}: {err}", flush=True)

    print(f"\nSummary: {len(promoted)} promoted, {len(stayed)} unchanged, {len(errors)} errors", flush=True)

    # If 3 passes were provided and techniques still didn't promote, explain why
    stalled = [(tid, passes) for tid, _, _, passes in stayed if passes >= 3]
    if stalled:
        print(f"\nTechniques with 3+ passes that did NOT reach S5 ({len(stalled)}):", flush=True)
        print("  (Check: sigma rules matched? stdout clean? 'Executing test:' present?)", flush=True)
        for tid, passes in stalled[:20]:
            print(f"  {tid} ({passes} passes)", flush=True)

    print("=" * 64, flush=True)


if __name__ == "__main__":
    main()
