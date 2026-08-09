#!/usr/bin/env python3
"""
Rebuild evidence bundle sigma claims using real SigmaHQ community rules.

Replaces every fabricated sigma_matches.json and tvr.json analytic_evidence.sigma
section with honest, verifiable entries based on real community rules that carry
the technique's ATT&CK tag. Fixes technique_index.json reason strings that
falsely claim sigma rule matches or osquery correlations.

Nothing is deleted — every technique that had fabricated Sigma matches now has
real community rule coverage records labeled accurately as detection_coverage,
not as event matches.
"""

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml required — pip install pyyaml", file=sys.stderr)
    sys.exit(1)

REPO_ROOT = Path(__file__).resolve().parent.parent
SIGMA_RULES_PATH = REPO_ROOT / "backend" / "sigma_rules"
EVIDENCE_BUNDLE = REPO_ROOT / "evidence-bundle"
TECHNIQUE_INDEX = EVIDENCE_BUNDLE / "technique_index.json"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_community_rules(rules_root: Path) -> Dict[str, List[Dict]]:
    """
    Returns {technique_id: [rule_record, ...]} for every real community rule
    that carries an ATT&CK technique tag.
    """
    by_technique: Dict[str, List[Dict]] = {}
    loaded = 0
    errors = 0
    for rule_file in sorted(rules_root.rglob("*.yml")):
        try:
            with rule_file.open("r", encoding="utf-8", errors="replace") as fh:
                docs = list(yaml.safe_load_all(fh))
        except Exception:
            errors += 1
            continue
        for doc in docs:
            if not isinstance(doc, dict) or not doc.get("detection"):
                continue
            tags = [str(t) for t in (doc.get("tags") or []) if isinstance(t, str)]
            techniques = sorted(set(
                t.replace("attack.", "").upper()
                for t in tags
                if re.match(r"attack\.t\d+", t.lower())
            ))
            if not techniques:
                continue
            rule_sha = sha256_file(rule_file)
            record = {
                "rule_id": str(doc.get("id") or rule_file.stem),
                "title": str(doc.get("title") or rule_file.stem),
                "status": str(doc.get("status") or "unknown"),
                "level": str(doc.get("level") or "unknown"),
                "author": str(doc.get("author") or ""),
                "rule_file": rule_file.name,
                "rule_sha256": rule_sha,
                "source": "SigmaHQ/sigma community rules",
                "detection_basis": "rule_covers_technique_by_attack_tag",
                "techniques": techniques,
            }
            for tid in techniques:
                by_technique.setdefault(tid, []).append(record)
            loaded += 1

    print(f"  Loaded {loaded} community rules covering {len(by_technique)} techniques ({errors} parse errors ignored)")
    return by_technique


def build_sigma_matches(technique_id: str, rules: List[Dict]) -> List[Dict]:
    """
    Build an honest sigma_matches.json payload.
    Each entry is a real community rule that covers this technique.
    Nothing claims an event-stream match — only detection coverage by ATT&CK tag.
    """
    return [
        {
            "rule_id": r["rule_id"],
            "title": r["title"],
            "rule_file": r["rule_file"],
            "rule_sha256": r["rule_sha256"],
            "status": r["status"],
            "level": r["level"],
            "author": r["author"],
            "source": r["source"],
            "detection_basis": r["detection_basis"],
        }
        for r in rules[:20]  # cap at 20 per technique in the per-run files
    ]


def fix_reason_string(reason: str, community_count: int) -> str:
    """
    Remove false sigma/osquery match claims from TVR reason strings.
    Replaces with accurate language about community rule coverage.
    """
    # Strip generated-rule match language
    reason = re.sub(
        r"\d+/\d+ Sigma rules? matched with event linkage[,.]?",
        "",
        reason,
        flags=re.IGNORECASE,
    ).strip(", .")

    # Strip false osquery correlation claims (the ndjson files are execution bookkeeping)
    reason = re.sub(
        r"\d+/\d+ osquery correlations? confirmed[,.]?",
        "",
        reason,
        flags=re.IGNORECASE,
    ).strip(", .")

    # Add honest community rule coverage statement
    if community_count > 0:
        reason = reason.rstrip(".").strip()
        reason += f". {community_count} SigmaHQ community rule(s) cover this technique by ATT&CK tag."
    else:
        reason = reason.rstrip(".").strip()
        reason += ". No community Sigma rules mapped to this technique."

    # Normalise double spaces and punctuation
    reason = re.sub(r"\s{2,}", " ", reason).strip()
    return reason


def rewrite_tvr_json(tvr_path: Path, technique_id: str, community_rules: List[Dict]) -> bool:
    try:
        tvr = json.loads(tvr_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"    SKIP {tvr_path.name}: {e}")
        return False

    changed = False

    # Fix analytic_evidence.sigma
    analytic = tvr.get("analytic_evidence")
    if isinstance(analytic, dict):
        old_sigma = analytic.get("sigma")
        if old_sigma is not None:
            new_sigma = build_sigma_matches(technique_id, community_rules)
            analytic["sigma"] = new_sigma
            analytic["sigma_community_rule_count"] = len(community_rules)
            analytic["sigma_note"] = (
                "Coverage records reference real SigmaHQ community rules mapped to this "
                "technique by ATT&CK tag. These are detection coverage indicators, not "
                "live event-stream matches."
            )
            changed = True

    # Fix promotion.reason / quality.reason strings
    for section_key in ("promotion", "quality"):
        section = tvr.get(section_key)
        if isinstance(section, dict):
            for field in ("reason", "notes", "justification"):
                raw = section.get(field)
                if isinstance(raw, str) and (
                    "sigma" in raw.lower() or "osquery correlation" in raw.lower()
                ):
                    section[field] = fix_reason_string(raw, len(community_rules))
                    changed = True

    if changed:
        tvr_path.write_text(
            json.dumps(tvr, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return changed


def rewrite_sigma_matches_json(path: Path, technique_id: str, community_rules: List[Dict]) -> bool:
    try:
        existing = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        existing = []

    # Check if any entry is generated/fabricated
    is_fabricated = any(
        "generated" in str(e.get("title", "")).lower()
        or "generated" in str(e.get("rule_file", "")).lower()
        for e in (existing if isinstance(existing, list) else [])
    )
    if not is_fabricated and existing:
        return False  # already honest, leave it

    new_content = build_sigma_matches(technique_id, community_rules)
    path.write_text(
        json.dumps(new_content, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return True


def fix_technique_index(index_path: Path, rules_by_technique: Dict[str, List[Dict]]) -> int:
    try:
        raw = json.loads(index_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  Could not load technique_index.json: {e}")
        return 0

    techs = raw.get("techniques") or {}
    if not isinstance(techs, dict):
        print("  technique_index.json has unexpected format — skipping")
        return 0

    fixed = 0
    for tid, entry in techs.items():
        if not isinstance(entry, dict):
            continue
        reason = entry.get("reason") or ""
        community_count = len(rules_by_technique.get(tid, []))
        if "sigma" in reason.lower() or "osquery correlation" in reason.lower():
            entry["reason"] = fix_reason_string(reason, community_count)
            fixed += 1
        # Add honest coverage count regardless
        entry["sigma_community_rule_count"] = community_count

    raw["techniques"] = techs
    index_path.write_text(
        json.dumps(raw, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return fixed


def main() -> int:
    print(f"Sigma rules path: {SIGMA_RULES_PATH}")
    if not SIGMA_RULES_PATH.exists():
        print("ERROR: Sigma rules path not found.", file=sys.stderr)
        return 1
    if not EVIDENCE_BUNDLE.exists():
        print("ERROR: Evidence bundle not found.", file=sys.stderr)
        return 1

    print("Loading real community rules...")
    rules_by_technique = load_community_rules(SIGMA_RULES_PATH)

    # --- Fix per-TVR-run files ---
    tvr_runs = sorted(EVIDENCE_BUNDLE.glob("techniques/*/TVR-*/"))
    print(f"\nProcessing {len(tvr_runs)} TVR run folders...")

    tvr_changed = 0
    sigma_changed = 0

    for run_dir in tvr_runs:
        # Extract technique ID from folder structure: techniques/T1001/TVR-...
        parts = run_dir.parts
        try:
            tid = parts[parts.index("techniques") + 1].upper()
        except (ValueError, IndexError):
            continue

        community_rules = rules_by_technique.get(tid, [])

        sigma_file = run_dir / "analytics" / "sigma_matches.json"
        if sigma_file.exists():
            if rewrite_sigma_matches_json(sigma_file, tid, community_rules):
                sigma_changed += 1

        tvr_file = run_dir / "tvr.json"
        if tvr_file.exists():
            if rewrite_tvr_json(tvr_file, tid, community_rules):
                tvr_changed += 1

    print(f"  sigma_matches.json rewritten: {sigma_changed}")
    print(f"  tvr.json records updated:     {tvr_changed}")

    # --- Fix technique_index.json ---
    print(f"\nFixing technique_index.json reason strings...")
    if TECHNIQUE_INDEX.exists():
        fixed = fix_technique_index(TECHNIQUE_INDEX, rules_by_technique)
        print(f"  Reason strings corrected: {fixed}")
    else:
        print("  technique_index.json not found — skipping")

    # --- Fix sigma_engine.py default path ---
    sigma_engine_path = REPO_ROOT / "sigma_engine.py"
    if sigma_engine_path.exists():
        src = sigma_engine_path.read_text(encoding="utf-8")
        old = 'default_path = Path(__file__).parent / "sigma_rules"'
        new = (
            'default_path = Path(__file__).parent / "backend" / "sigma_rules"\n'
            '        # Fallback chain: backend/sigma_rules → sigma_rules\n'
            '        if not default_path.exists():\n'
            '            default_path = Path(__file__).parent / "sigma_rules"'
        )
        if old in src and new not in src:
            src = src.replace(old, new)
            sigma_engine_path.write_text(src, encoding="utf-8")
            print("\nFixed sigma_engine.py default rules path → backend/sigma_rules")
        else:
            print("\nsigma_engine.py path already updated or pattern not found")

    # --- Summary ---
    print("\n=== DONE ===")
    print(f"Community rules loaded: {sum(len(v) for v in rules_by_technique.values())} rule-technique mappings")
    print(f"Techniques with real Sigma coverage: {len(rules_by_technique)}")
    print(f"sigma_matches.json rebuilt: {sigma_changed}")
    print(f"tvr.json records patched: {tvr_changed}")
    print()
    print("All sigma claims now reference real SigmaHQ community rules.")
    print("Detection basis label: 'rule_covers_technique_by_attack_tag' (coverage, not live match).")
    print("No fabricated 'Generated T* Indicator' entries remain.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
