#!/usr/bin/env python3
"""
generate_evidence_bundle.py
===========================
Standalone generator — run inside the backend container to bootstrap the
full Technique Validation Record (TVR) evidence bundle for all 439 ATT&CK
techniques currently in scope.

Usage (inside container):
    docker exec metatron-seraph-v9-backend-1 python3 /app/scripts/generate_evidence_bundle.py

Usage (host — via docker exec):
    docker exec metatron-seraph-v9-backend-1 \
        python3 /app/scripts/generate_evidence_bundle.py [--techniques T1059,T1190]
"""
import argparse
import json
import logging
import sys
import time
from pathlib import Path

# Ensure backend is on the path
sys.path.insert(0, "/app/backend")
sys.path.insert(0, "/app")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("generate_evidence_bundle")


def load_attack_tactics(attack_json_path: str) -> dict:
    """Load MITRE ATT&CK STIX JSON → {tech_id: [tactic1, tactic2, ...]}."""
    try:
        with open(attack_json_path) as f:
            bundle = json.load(f)
    except Exception as exc:
        logger.warning("Could not load ATT&CK STIX data from %s: %s", attack_json_path, exc)
        return {}

    mapping = {}
    for obj in bundle.get("objects", []):
        if obj.get("type") != "attack-pattern" or obj.get("revoked") or obj.get("x_mitre_deprecated"):
            continue
        refs = obj.get("external_references") or []
        tech_id = None
        for r in refs:
            if r.get("source_name") == "mitre-attack":
                tech_id = r.get("external_id")
                break
        if not tech_id:
            continue
        tactics = [p["phase_name"] for p in (obj.get("kill_chain_phases") or [])]
        mapping[tech_id] = tactics
    return mapping


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate TVR evidence bundle")
    parser.add_argument(
        "--techniques",
        default="",
        help="Comma-separated list of technique IDs to generate (default: all)",
    )
    parser.add_argument(
        "--output",
        default="/var/lib/seraph-ai/evidence-bundle",
        help="Evidence bundle root directory",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List techniques without writing files",
    )
    args = parser.parse_args()

    # Import after path setup
    from evidence_bundle import EvidenceBundleManager

    manager = EvidenceBundleManager(evidence_root=Path(args.output))

    # Load MITRE ATT&CK tactics mapping
    attack_json_candidates = [
        "/opt/atomic-red-team/atomic_red_team/enterprise-attack.json",
        "/app/atomic-red-team/atomic_red_team/enterprise-attack.json",
        str(Path(__file__).resolve().parent.parent / "atomic-red-team" / "atomic_red_team" / "enterprise-attack.json"),
    ]
    tactic_map = {}
    for candidate in attack_json_candidates:
        tactic_map = load_attack_tactics(candidate)
        if tactic_map:
            logger.info("Loaded tactics for %d techniques from %s", len(tactic_map), candidate)
            break
    if not tactic_map:
        logger.warning("No ATT&CK tactic mapping loaded — tactics will be empty")

    # Get technique list from sigma_engine
    logger.info("Loading technique list from sigma_engine...")
    try:
        from sigma_engine import sigma_engine
        cov = sigma_engine.coverage_summary()
        all_tech_rows = cov.get("techniques") or []
    except Exception as exc:
        logger.error("Failed to load sigma_engine coverage: %s", exc)
        sys.exit(1)

    if args.techniques:
        requested = {t.strip().upper() for t in args.techniques.split(",") if t.strip()}
        tech_rows = [r for r in all_tech_rows if str(r.get("technique") or "").upper() in requested]
        logger.info("Filtered to %d requested techniques", len(tech_rows))
    else:
        tech_rows = all_tech_rows
        logger.info("Generating TVRs for all %d techniques", len(tech_rows))

    if args.dry_run:
        for r in tech_rows:
            print(r.get("technique"))
        return

    start = time.time()
    generated = 0
    errors = 0
    tier_counts: dict = {"platinum": 0, "gold": 0, "silver": 0, "bronze": 0, "none": 0}

    for i, row in enumerate(tech_rows, 1):
        tech_id = str(row.get("technique") or "").strip()
        if not tech_id:
            continue

        technique_name = str(row.get("name") or row.get("technique_name") or tech_id)
        # Use real MITRE ATT&CK tactics, falling back to sigma_engine data
        real_tactics = tactic_map.get(tech_id) or row.get("tactics") or []

        try:
            record = manager.generate_tvr_for_technique(
                tech_id,
                technique_name=technique_name,
                tactics=real_tactics,
                platforms=row.get("platforms") or ["Linux"],
            )
            tvr_dir = manager.write_tvr(tech_id, record)
            tier = record.get("promotion", {}).get("tier_name", "none")
            score = record.get("promotion", {}).get("score", 0)
            tier_counts[tier] = tier_counts.get(tier, 0) + 1
            generated += 1

            # Progress every 50
            if i % 50 == 0 or i == len(tech_rows):
                elapsed = time.time() - start
                logger.info(
                    "[%d/%d] last=%s S%s  |  platinum=%d gold=%d silver=%d bronze=%d  |  %.1fs elapsed",
                    i,
                    len(tech_rows),
                    tech_id,
                    score,
                    tier_counts["platinum"],
                    tier_counts["gold"],
                    tier_counts["silver"],
                    tier_counts["bronze"],
                    elapsed,
                )
        except Exception as exc:
            logger.warning("[%d/%d] ERROR %s: %s", i, len(tech_rows), tech_id, exc)
            errors += 1

    # Build derived coverage summary
    logger.info("Building coverage_summary.json from %d TVR verdicts...", generated)
    summary = manager.build_coverage_summary()

    elapsed = time.time() - start
    tb = summary.get("tier_breakdown", {})

    print("\n" + "=" * 60)
    print("  EVIDENCE BUNDLE GENERATION COMPLETE")
    print("=" * 60)
    print(f"  Techniques processed : {generated + errors}")
    print(f"  TVRs written         : {generated}")
    print(f"  Errors               : {errors}")
    print(f"  Output path          : {manager.evidence_root}")
    print(f"  Elapsed              : {elapsed:.1f}s")
    print()
    print("  Tier breakdown (from TVR verdicts):")
    print(f"    Platinum (S5) : {tb.get('platinum', 0)}")
    print(f"    Gold     (S4) : {tb.get('gold', 0)}")
    print(f"    Silver   (S3) : {tb.get('silver', 0)}")
    print(f"    Bronze   (S2) : {tb.get('bronze', 0)}")
    print(f"    None     (S0) : {tb.get('none', 0)}")
    print()
    print("  Derivation source    : technique_validation_records")
    print(f"  TVR count            : {summary.get('derivation', {}).get('source_count', 0)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
