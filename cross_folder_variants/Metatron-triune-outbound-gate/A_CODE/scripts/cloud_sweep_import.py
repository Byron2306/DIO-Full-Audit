#!/usr/bin/env python3
"""
cloud_sweep_import.py
=====================
End-to-end pipeline: poll a GHA run → download artifacts → import to container → regen TVRs → report promotions.

Usage:
    python3 scripts/cloud_sweep_import.py --run-id 24977672695
    python3 scripts/cloud_sweep_import.py --run-id 24977672695 --import-only  # skip polling
    python3 scripts/cloud_sweep_import.py --run-id 24977672695 --dry-run

Auto-detects the seraph-backend container and uses `gh` CLI for artifact download.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

REPO = "Byron2306/Metatron"
CONTAINER = os.environ.get("SERAPH_BACKEND_CONTAINER", "seraph-backend")
CONTAINER_ATOMIC = "/var/lib/seraph-ai/atomic-validation"
CONTAINER_BUNDLE = "/var/lib/seraph-ai/evidence-bundle"
POLL_INTERVAL_S = 30
POLL_TIMEOUT_S = 3600  # 1 hour max


def _run(cmd: list[str], check: bool = True, capture: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=check, capture_output=capture, text=True)


def _utc_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


# ── Polling ───────────────────────────────────────────────────────────────────

def poll_run(run_id: str, timeout_s: int = POLL_TIMEOUT_S) -> str:
    """Poll until the run is no longer in_progress. Returns final status."""
    deadline = time.time() + timeout_s
    prev_status = None
    while time.time() < deadline:
        r = _run(["gh", "run", "view", run_id, "-R", REPO, "--json", "status,conclusion,name"], check=False)
        if r.returncode != 0:
            print(f"  [poll] gh run view failed: {r.stderr.strip()}")
            time.sleep(POLL_INTERVAL_S)
            continue
        data = json.loads(r.stdout)
        status = data.get("status", "unknown")
        conclusion = data.get("conclusion") or ""
        name = data.get("name", "")
        if status != prev_status:
            print(f"  [{_utc_ts()}] Run {run_id} — status={status} conclusion={conclusion} ({name})")
            prev_status = status
        if status not in ("queued", "in_progress", "waiting", "requested", "pending"):
            print(f"  Run finished: status={status} conclusion={conclusion}")
            return conclusion or status
        time.sleep(POLL_INTERVAL_S)
    raise TimeoutError(f"Run {run_id} still in progress after {timeout_s}s")


# ── Artifact download ─────────────────────────────────────────────────────────

def list_artifacts(run_id: str) -> list[dict]:
    r = _run(["gh", "run", "view", run_id, "-R", REPO, "--json", "artifactUrl,databaseId"], check=False)
    # Use gh api instead for reliable artifact listing
    r = _run(["gh", "api", f"repos/{REPO}/actions/runs/{run_id}/artifacts", "--paginate"])
    data = json.loads(r.stdout)
    return data.get("artifacts", [])


def download_artifacts(run_id: str, outdir: Path) -> list[Path]:
    """Download all artifacts for the run into outdir. Returns list of extracted dirs."""
    outdir.mkdir(parents=True, exist_ok=True)
    artifacts = list_artifacts(run_id)
    if not artifacts:
        print("  [download] No artifacts found.")
        return []

    print(f"  [download] {len(artifacts)} artifacts to download...")
    extracted = []

    for art in artifacts:
        art_id = art["id"]
        art_name = art["name"]
        zip_path = outdir / f"{art_name}.zip"
        extract_path = outdir / art_name

        if extract_path.exists():
            print(f"  [download] Already exists: {art_name}, skipping")
            extracted.append(extract_path)
            continue

        print(f"  [download] {art_name} ({art.get('size_in_bytes', 0)//1024}KB)...")
        r = _run([
            "gh", "api",
            f"repos/{REPO}/actions/artifacts/{art_id}/zip",
            "--header", "Accept: application/vnd.github+json",
        ], capture=True, check=False)

        if r.returncode != 0:
            print(f"  [download] WARN: failed to download {art_name}: {r.stderr[:100]}")
            continue

        zip_path.write_bytes(r.stdout.encode("latin-1") if isinstance(r.stdout, str) else r.stdout)

        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(extract_path)
            extracted.append(extract_path)
            print(f"  [download] Extracted {len(list(extract_path.rglob('run_*.json')))} run files from {art_name}")
        except zipfile.BadZipFile:
            print(f"  [download] WARN: bad zip for {art_name}")

    return extracted


def download_artifacts_gh_cli(run_id: str, outdir: Path) -> Path:
    """Use `gh run download` — simpler, handles auth automatically."""
    outdir.mkdir(parents=True, exist_ok=True)
    print(f"  [download] Using gh run download for run {run_id}...")
    r = _run([
        "gh", "run", "download", run_id,
        "-R", REPO,
        "-D", str(outdir),
    ], check=False)
    if r.returncode != 0:
        print(f"  [download] WARN: {r.stderr.strip()}")
    return outdir


# ── Container import ──────────────────────────────────────────────────────────

def find_run_files(base_dir: Path) -> list[Path]:
    return sorted(base_dir.rglob("run_*.json"))


def import_to_container(run_files: list[Path], container: str = CONTAINER) -> int:
    """Copy run JSON files into the container's atomic-validation directory."""
    if not run_files:
        print("  [import] No run files to import.")
        return 0

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir) / "gha_import"
        tmppath.mkdir()
        for f in run_files:
            dest = tmppath / f.name
            # Avoid collision by prefixing with parent dir name
            dest = tmppath / f"{f.parent.name}__{f.name}"
            dest.write_bytes(f.read_bytes())

        # Copy into container
        r = _run(["docker", "cp", str(tmppath) + "/.", f"{container}:{CONTAINER_ATOMIC}/"], check=False)
        if r.returncode != 0:
            print(f"  [import] WARN docker cp failed: {r.stderr.strip()}")
            return 0

    print(f"  [import] Copied {len(run_files)} run files into {container}:{CONTAINER_ATOMIC}/")
    return len(run_files)


# ── TVR regen ─────────────────────────────────────────────────────────────────

def regen_tvrs(techniques: list[str], container: str = CONTAINER) -> dict:
    """Regenerate evidence bundle TVRs for specified techniques."""
    if not techniques:
        print("  [regen] No techniques to regenerate.")
        return {}

    tech_str = ",".join(sorted(set(techniques)))
    print(f"  [regen] Regenerating TVRs for {len(techniques)} techniques...")

    regen_script = f"""
import sys, json
sys.path.insert(0, '/app/backend')
from evidence_bundle import EvidenceBundleManager
m = EvidenceBundleManager()

techs = {json.dumps(sorted(set(techniques)))}
results = {{}}
for t in techs:
    try:
        tvr = m.generate_tvr(t)
        cert = (tvr or {{}}).get('promotion', {{}}).get('certification_tier', 'unknown')
        direct = (tvr or {{}}).get('execution', {{}}).get('direct_run_count', 0)
        results[t] = {{'cert': cert, 'direct': direct, 'ok': True}}
    except Exception as e:
        results[t] = {{'cert': 'error', 'direct': 0, 'ok': False, 'error': str(e)}}

print(json.dumps(results))
"""

    r = _run([
        "docker", "exec", container,
        "python3", "-c", regen_script,
    ], check=False)

    if r.returncode != 0:
        print(f"  [regen] WARN: exit {r.returncode}: {r.stderr[:200]}")
        return {}

    # Parse results (skip log lines)
    for line in r.stdout.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                pass
    return {}


def regen_via_script(techniques: list[str], container: str = CONTAINER) -> bool:
    """Use the existing generate_evidence_bundle.py script in the container."""
    tech_str = ",".join(sorted(set(techniques)))
    print(f"  [regen] Running generate_evidence_bundle.py for {len(techniques)} techniques...")
    r = _run([
        "docker", "exec", container,
        "python3", "/tmp/generate_evidence_bundle.py",
        "--techniques", tech_str,
    ], check=False)
    if r.returncode not in (0, 1):
        print(f"  [regen] WARN: exit {r.returncode}")
    # Print key output lines
    for line in r.stdout.splitlines():
        if any(k in line for k in ["COMPLETE", "Tier", "processed", "Errors", "platinum"]):
            print(f"    {line.strip()}")
    return r.returncode in (0, 1)


# ── Tier comparison ───────────────────────────────────────────────────────────

def get_tier_snapshot(container: str = CONTAINER) -> dict:
    script = """
import sys, json
sys.path.insert(0, '/app/backend')
from evidence_bundle import EvidenceBundleManager
m = EvidenceBundleManager()
tiers = {}
perfect = 0
for tech in m.list_technique_ids():
    tvr = m.load_latest_tvr(tech)
    if not tvr: continue
    cert = tvr.get('promotion', {}).get('certification_tier', 'unknown')
    tiers[cert] = tiers.get(cert, 0) + 1
    if tvr.get('story', {}).get('assessment', {}).get('perfect_story'): perfect += 1
print(json.dumps({'tiers': tiers, 'perfect': perfect}))
"""
    r = _run(["docker", "exec", container, "python3", "-c", script], check=False)
    for line in r.stdout.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                pass
    return {}


def print_tier_diff(before: dict, after: dict) -> None:
    btiers = before.get("tiers", {})
    atiers = after.get("tiers", {})
    all_keys = sorted(set(list(btiers.keys()) + list(atiers.keys())))

    print("\n=== TIER PROMOTION REPORT ===")
    for k in all_keys:
        b = btiers.get(k, 0)
        a = atiers.get(k, 0)
        diff = a - b
        diff_str = f" (+{diff})" if diff > 0 else (f" ({diff})" if diff < 0 else "")
        print(f"  {k:25s}: {b:3d} → {a:3d}{diff_str}")

    b_cert = sum(v for k, v in btiers.items() if k.startswith("S5-C"))
    a_cert = sum(v for k, v in atiers.items() if k.startswith("S5-C"))
    print(f"\n  S5-C Total: {b_cert} → {a_cert} ({'+' if a_cert >= b_cert else ''}{a_cert - b_cert})")
    print(f"  Perfect stories: {before.get('perfect', 0)} → {after.get('perfect', 0)}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="GHA sweep artifact import + TVR promotion pipeline")
    parser.add_argument("--run-id", required=True, help="GitHub Actions run ID")
    parser.add_argument("--repo", default=REPO, help="GitHub repo (owner/name)")
    parser.add_argument("--container", default=CONTAINER, help="Docker container name")
    parser.add_argument("--outdir", default=None, help="Artifact download directory")
    parser.add_argument("--import-only", action="store_true", help="Skip polling, go straight to download+import")
    parser.add_argument("--dry-run", action="store_true", help="Download but don't import")
    parser.add_argument("--no-regen", action="store_true", help="Import but skip TVR regen")
    parser.add_argument("--techniques", default="", help="Override technique list for regen (comma-separated)")
    args = parser.parse_args()

    global REPO, CONTAINER
    REPO = args.repo
    CONTAINER = args.container

    outdir = Path(args.outdir) if args.outdir else Path("downloaded_artifacts") / f"gha_{args.run_id}"
    ts = _utc_ts()

    print(f"\n{'='*60}")
    print(f"  Cloud Sweep Import Pipeline")
    print(f"  Run: {args.run_id} @ {REPO}")
    print(f"  Container: {CONTAINER}")
    print(f"  Output: {outdir}")
    print(f"{'='*60}\n")

    # ── Step 1: Poll until complete ──
    if not args.import_only:
        print("[1/4] Polling for run completion...")
        try:
            conclusion = poll_run(args.run_id)
        except TimeoutError as e:
            print(f"  TIMEOUT: {e}")
            return 1
        if conclusion not in ("success", "failure"):
            print(f"  Run ended with: {conclusion} — proceeding anyway")
    else:
        print("[1/4] Skipping poll (--import-only)")

    # ── Step 2: Download artifacts ──
    print(f"\n[2/4] Downloading artifacts to {outdir}...")
    download_artifacts_gh_cli(args.run_id, outdir)
    run_files = find_run_files(outdir)
    print(f"  Found {len(run_files)} run_*.json files")

    if not run_files:
        print("  No run files found. Aborting.")
        return 1

    if args.dry_run:
        print("\n  DRY RUN — not importing. Files are in:", outdir)
        return 0

    # ── Step 3: Import into container ──
    print(f"\n[3/4] Importing {len(run_files)} run files into {CONTAINER}...")
    imported = import_to_container(run_files, CONTAINER)
    if imported == 0:
        print("  Import failed. Aborting.")
        return 1

    if args.no_regen:
        print("\n  --no-regen set, skipping TVR regen.")
        return 0

    # ── Step 4: Regen TVRs ──
    print(f"\n[4/4] Regenerating TVRs...")

    # Take before snapshot
    print("  Taking before snapshot...")
    before = get_tier_snapshot(CONTAINER)

    # Extract unique technique IDs from run files
    if args.techniques:
        techniques = [t.strip() for t in args.techniques.split(",") if t.strip()]
    else:
        techniques = set()
        for f in run_files:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                for t in data.get("techniques", []):
                    techniques.add(t)
                for t in data.get("techniques_executed", []):
                    techniques.add(t)
            except Exception:
                pass
        techniques = sorted(techniques)

    print(f"  Techniques to regen: {len(techniques)}")
    regen_via_script(techniques, CONTAINER)

    # Take after snapshot
    after = get_tier_snapshot(CONTAINER)
    print_tier_diff(before, after)

    print(f"\n  Pipeline complete. Artifacts in: {outdir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
