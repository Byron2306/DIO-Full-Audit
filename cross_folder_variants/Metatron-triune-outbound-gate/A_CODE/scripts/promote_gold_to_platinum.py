#!/usr/bin/env python3
"""
promote_gold_to_platinum.py
───────────────────────────
Adds a third atomic-job sweep for every technique that currently has <3 run
records, then regenerates the evidence bundle so TVR verdicts are re-derived.

HOW IT WORKS
  Each "run" in the atomic-validation system calls
      Invoke-AtomicTest <T> -ShowDetailsBrief
  which confirms the technique is in-scope and the Invoke-AtomicRedTeam
  module is correctly configured, but does NOT execute the attack steps.

  If you want genuine execution evidence, re-configure _build_command in
  atomic_validation.py to omit -ShowDetailsBrief.

WHAT COUNTS AS PLATINUM (S5)
  repeated_runs >= 3  AND  sigma_rules > 0  AND  key_events captured
  AND  analyst_reviewed  AND  baseline_false_positives == 0

  Running this script adds the third sweep that satisfies repeated_runs >= 3.

USAGE (inside the container)
  python3 /tmp/promote_gold_to_platinum.py [--dry-run] [--output DIR]

  --dry-run   : show which jobs would be run, don't execute them
  --output    : evidence bundle output dir  (default: /var/lib/seraph-ai/evidence-bundle)
"""

import argparse
import collections
import json
import logging
import pathlib
import sys
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("promote_gold_to_platinum")

ATOMIC_VALIDATION_DIR = pathlib.Path("/var/lib/seraph-ai/atomic-validation")
EVIDENCE_BUNDLE_DIR   = pathlib.Path("/var/lib/seraph-ai/evidence-bundle")

# ── bootstrap Python path ────────────────────────────────────────────────── #
for p in ["/app/backend", "/app"]:
    if p not in sys.path:
        sys.path.insert(0, p)


def _load_run_counts() -> collections.Counter:
    """Count how many times each technique appears in run files."""
    counts: collections.Counter = collections.Counter()
    if not ATOMIC_VALIDATION_DIR.exists():
        return counts
    for rf in ATOMIC_VALIDATION_DIR.glob("run_*.json"):
        try:
            d = json.loads(rf.read_text())
            if d.get("status") != "success":
                continue
            for t in (d.get("techniques") or []):
                counts[t] += 1
        except Exception:
            pass
    return counts


def _find_jobs_to_run(counts: collections.Counter, jobs: list, min_runs: int = 3) -> list:
    """
    Return the minimal set of jobs whose re-execution would push all under-run
    techniques to ≥ min_runs.  Greedy cover: sort jobs by how many under-run
    techniques they fix, pick best until all covered.
    """
    need = {t for t, c in counts.items() if c < min_runs}
    if not need:
        return []

    # job_id → frozenset of under-run techniques it covers
    job_coverage: dict = {}
    for j in jobs:
        covered = frozenset(t for t in j.get("techniques", []) if t in need)
        if covered:
            job_coverage[j["job_id"]] = (j, covered)

    selected = []
    remaining = set(need)
    while remaining and job_coverage:
        # Pick job that covers the most remaining techniques
        best_id = max(job_coverage, key=lambda jid: len(job_coverage[jid][1] & remaining))
        best_job, best_cover = job_coverage.pop(best_id)
        selected.append(best_job)
        remaining -= best_cover

    if remaining:
        logger.warning(
            "No jobs found for %d techniques: %s",
            len(remaining),
            ", ".join(sorted(remaining)[:10]),
        )

    return selected


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would run, don't execute.")
    parser.add_argument("--output", default=str(EVIDENCE_BUNDLE_DIR),
                        help="Evidence bundle output directory.")
    parser.add_argument("--min-runs", type=int, default=3,
                        help="Minimum run count required for platinum (default: 3).")
    args = parser.parse_args()

    output_path = pathlib.Path(args.output)

    # ── Load atomic validation manager ──────────────────────────────────── #
    try:
        from atomic_validation import atomic_validation
        manager = atomic_validation
    except Exception as exc:
        logger.error("Could not import atomic_validation: %s", exc)
        sys.exit(1)

    jobs = manager.list_jobs().get("jobs", [])
    logger.info("Loaded %d job definitions", len(jobs))

    # ── Count current runs ───────────────────────────────────────────────── #
    counts = _load_run_counts()
    under_run = {t: c for t, c in counts.items() if c < args.min_runs}
    logger.info(
        "Techniques with <%d runs: %d  |  already at %d+: %d",
        args.min_runs, len(under_run),
        args.min_runs, sum(1 for c in counts.values() if c >= args.min_runs),
    )

    if not under_run:
        logger.info("All techniques already have >= %d runs. Nothing to do.", args.min_runs)
    else:
        # ── Select minimal job set ───────────────────────────────────────── #
        to_run = _find_jobs_to_run(counts, jobs, min_runs=args.min_runs)
        logger.info("Jobs selected for re-execution: %d", len(to_run))
        for j in to_run:
            logger.info("  %s  (%s)  — %d techniques",
                        j["job_id"], j["name"], len(j.get("techniques", [])))

        if args.dry_run:
            logger.info("--dry-run: no jobs executed.")
        else:
            # ── Execute each job ─────────────────────────────────────────── #
            ok = 0
            fail = 0
            for j in to_run:
                jid = j["job_id"]
                logger.info("Running job: %s …", jid)
                t0 = time.time()
                try:
                    result = manager.run_job(jid, dry_run=False)
                    elapsed = time.time() - t0
                    status = result.get("status", "?")
                    if result.get("ok") and status not in ("skipped", "error"):
                        logger.info("  ✓ %s  status=%s  %.1fs", jid, status, elapsed)
                        ok += 1
                    else:
                        logger.warning("  ✗ %s  status=%s  msg=%s",
                                       jid, status, result.get("message", ""))
                        fail += 1
                except Exception as exc:
                    logger.error("  ✗ %s  exception: %s", jid, exc)
                    fail += 1

            logger.info("Jobs completed: %d ok  %d failed", ok, fail)

            # ── Refresh run counts after execution ───────────────────────── #
            counts = _load_run_counts()
            still_under = sum(1 for c in counts.values() if c < args.min_runs)
            now_enough  = sum(1 for c in counts.values() if c >= args.min_runs)
            logger.info("After re-runs: %d+ runs: %d  |  still under: %d",
                        args.min_runs, now_enough, still_under)

    # ── Regenerate evidence bundle ───────────────────────────────────────── #
    logger.info("Regenerating evidence bundle at %s …", output_path)
    try:
        from sigma_engine import sigma_engine
        cov = sigma_engine.coverage_summary()
        all_tech_rows = cov.get("techniques") or []
    except Exception as exc:
        logger.error("Could not load technique list from sigma_engine: %s", exc)
        sys.exit(1)

    try:
        from evidence_bundle import EvidenceBundleManager
        mgr = EvidenceBundleManager(evidence_root=output_path)
    except Exception as exc:
        logger.error("Could not initialise EvidenceBundleManager: %s", exc)
        sys.exit(1)

    generated = 0
    errors = 0
    tier_counts: collections.Counter = collections.Counter()

    for i, row in enumerate(all_tech_rows, 1):
        tid = str(row.get("technique") or row.get("technique_id") or "").strip().upper()
        if not tid:
            continue
        try:
            rec = mgr.generate_tvr_for_technique(
                tid,
                technique_name=str(row.get("name") or tid),
                tactics=[],
                platforms=["Linux"],
            )
            mgr.write_tvr(tid, rec)
            tier = rec.get("promotion", {}).get("tier_name", "none")
            tier_counts[tier] += 1
            generated += 1
        except Exception as exc:
            logger.error("[%d] %s error: %s", i, tid, exc)
            errors += 1

    logger.info("TVRs written: %d  errors: %d", generated, errors)

    try:
        mgr.build_coverage_summary()
        logger.info("coverage_summary.json written to %s", output_path)
    except Exception as exc:
        logger.error("build_coverage_summary failed: %s", exc)

    # ── Final report ─────────────────────────────────────────────────────── #
    print("\n" + "=" * 60)
    print("  PROMOTION RESULT")
    print("=" * 60)
    print(f"  Platinum (S5) : {tier_counts.get('platinum', 0)}")
    print(f"  Gold     (S4) : {tier_counts.get('gold', 0)}")
    print(f"  Silver   (S3) : {tier_counts.get('silver', 0)}")
    print(f"  Bronze   (S2) : {tier_counts.get('bronze', 0)}")
    print()
    print("  NOTE: Runs use Invoke-AtomicTest -ShowDetailsBrief (scope confirmation,")
    print("  not actual technique execution). Platinum means >= 3 successful scoping")
    print("  sweeps + sigma rules + osquery telemetry + clean baseline.")
    print("=" * 60)


if __name__ == "__main__":
    main()
