#!/usr/bin/env python3
"""
Run real SigmaHQ community rules against the actual osqueryd telemetry log.

Produces per-technique sigma_matches.json entries that reflect REAL rule firings
against real osquery events — not coverage mappings, not generated stubs.

Output: evidence-bundle/techniques/<TID>/<TVR-run>/analytics/sigma_matches.json
        evidence-bundle/analytics/sigma_matches.json  (legacy global)
        analytics/sigma_matches.json                  (global, consumed by ARDA prevention evidence v2)
        evidence-bundle/sigma_evaluation_report.json
"""

import json
import sys
import argparse
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from sigma_engine import sigma_engine  # noqa: E402  (needs sys.path set first)

OSQUERY_LOG = REPO_ROOT / "evidence-bundle" / "osqueryd.results.log"
EVIDENCE_BUNDLE = REPO_ROOT / "evidence-bundle"
REPO_ANALYTICS_DIR = REPO_ROOT / "analytics"


# ── Osquery → Sigma field normalisation ──────────────────────────────────────

def _iso_from_osquery_event(raw: Dict[str, Any]) -> str | None:
    """
    Prefer unixTime (seconds) when present; fall back to None if missing/invalid.
    This feeds ARDA evidence correlation which filters by ISO timestamps.
    """
    unix_ts = raw.get("unixTime")
    if unix_ts is None:
        return None
    try:
        return datetime.fromtimestamp(int(unix_ts), tz=timezone.utc).isoformat()
    except Exception:
        return None


def normalise_event(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map an osquery event dict to a sigma-compatible field schema.
    Sigma rules for Linux process_creation expect Image, CommandLine, etc.
    """
    name = raw.get("name", "")
    cols = raw.get("columns") or {}
    action = raw.get("action", "")
    ts = raw.get("calendarTime", "")

    ev: Dict[str, Any] = {
        "_osquery_name": name,
        "_osquery_action": action,
        "_timestamp": ts,
        "_raw": json.dumps(raw, default=str),
    }

    if name == "process_events":
        ev["Image"] = cols.get("path", "")
        ev["CommandLine"] = cols.get("cmdline", "")
        ev["ProcessId"] = cols.get("pid", "")
        ev["ParentProcessId"] = cols.get("parent", "")
        ev["OriginalFileName"] = Path(cols.get("path", "")).name
        # Sigma logsource mapping
        ev["_logsource_category"] = "process_creation"
        ev["_logsource_product"] = "linux"

    elif name == "open_files":
        ev["TargetFilename"] = cols.get("path", "")
        ev["ProcessId"] = cols.get("pid", "")
        ev["_logsource_category"] = "file_event"
        ev["_logsource_product"] = "linux"

    elif name == "kernel_modules":
        ev["ImageLoaded"] = cols.get("name", "")
        ev["_logsource_category"] = "driver_load"
        ev["_logsource_product"] = "linux"

    elif name == "suid_bin":
        ev["Image"] = cols.get("path", "")
        ev["FileAttributes"] = cols.get("permissions", "")
        ev["_logsource_category"] = "process_creation"
        ev["_logsource_product"] = "linux"

    elif name in ("pack_seraph_processes",):
        ev["Image"] = f"/usr/bin/{cols.get('name', '')}"
        ev["CommandLine"] = cols.get("cmdline", "")
        ev["ProcessId"] = cols.get("pid", "")
        ev["_logsource_category"] = "process_creation"
        ev["_logsource_product"] = "linux"

    elif name in ("listening_ports", "pack_seraph_listening_ports"):
        ev["DestinationPort"] = cols.get("port", "")
        ev["DestinationIp"] = cols.get("address", "")
        ev["ProcessId"] = cols.get("pid", "")
        ev["_logsource_category"] = "network_connection"
        ev["_logsource_product"] = "linux"

    # All events from this osquery daemon are Linux host events
    if "_logsource_product" not in ev:
        ev["_logsource_product"] = "linux"
    if "_logsource_category" not in ev:
        ev["_logsource_category"] = "unknown"

    # Always carry raw text for keyword-based rules
    cmdline = cols.get("cmdline") or cols.get("cmd", "")
    path_val = cols.get("path", "")
    ev["_text"] = f"{path_val} {cmdline} {json.dumps(cols)}"

    return ev


def load_osquery_events(log_path: Path) -> List[Dict[str, Any]]:
    events = []
    for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except Exception:
            continue
    return events


# ── Main evaluation ───────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--osquery-log", default=str(OSQUERY_LOG))
    parser.add_argument("--max-events", type=int, default=0, help="0 = all events")
    parser.add_argument("--max-rules", type=int, default=0, help="0 = all rules")
    parser.add_argument(
        "--no-legacy-evidence-bundle-output",
        action="store_true",
        help="Only write repo-root analytics output (skip evidence-bundle/analytics legacy copy).",
    )
    args = parser.parse_args()

    osquery_log = Path(args.osquery_log)

    print(f"Sigma rules loaded: {len(sigma_engine.rules)}")
    print(f"Osquery log: {osquery_log}")

    if not osquery_log.exists():
        print(f"ERROR: osquery log not found: {osquery_log}", file=sys.stderr)
        return 1

    raw_events = load_osquery_events(osquery_log)
    if args.max_events and args.max_events > 0:
        raw_events = raw_events[: args.max_events]
    print(f"Osquery events: {len(raw_events)}")

    if args.max_rules and args.max_rules > 0:
        sigma_engine.rules = sigma_engine.rules[: args.max_rules]
        print(f"Sigma rules limited to: {len(sigma_engine.rules)}")

    # Build rule_id → logsource index so the gate can look up logsource from match results
    # (sigma_engine.evaluate_event does not include logsource in match dicts).
    rule_logsource: Dict[str, Dict] = {}
    for rule in sigma_engine.rules:
        rid = str(rule.get("id") or rule.get("title") or "")
        rule_logsource[rid] = rule.get("logsource") or {}

    # Also index by title as fallback (some rules have no id)
    rule_logsource_by_title: Dict[str, Dict] = {
        str(rule.get("title") or ""): rule.get("logsource") or {}
        for rule in sigma_engine.rules
    }

    BLOCKED_PRODUCTS = {"windows", "macos", "osx", "fortinet", "paloalto", "juniper", "checkpoint"}
    BLOCKED_SERVICES = {"cisco", "fortinet", "paloalto"}
    # Categories we have no matching osquery events for
    BLOCKED_CATEGORIES = {"proxy", "webserver", "firewall", "dns", "antivirus"}

    # Also build a rule_id → author index to correctly label experimental rules
    rule_author: Dict[str, str] = {}
    for rule in sigma_engine.rules:
        rid = str(rule.get("id") or rule.get("title") or "")
        rule_author[rid] = str(rule.get("author") or "")

    def _logsource_ok(ev_product: str, match: Dict) -> bool:
        """
        Return False if the rule's logsource is for a clearly incompatible platform
        or log category that we have no matching osquery events for.
        """
        rule_ls = (
            rule_logsource.get(match.get("id", ""))
            or rule_logsource_by_title.get(match.get("title", ""))
            or {}
        )
        rule_product = str(rule_ls.get("product") or "").lower()
        rule_service = str(rule_ls.get("service") or "").lower()
        rule_category = str(rule_ls.get("category") or "").lower()

        # Drop rules for log sources we don't have
        if rule_category in BLOCKED_CATEGORIES:
            return False

        if ev_product == "linux":
            if rule_product in BLOCKED_PRODUCTS:
                return False
            if any(s in rule_product for s in BLOCKED_SERVICES):
                return False
            if any(s in rule_service for s in BLOCKED_SERVICES):
                return False
            # Allow rules targeting linux explicitly or with no product restriction
            if rule_product and rule_product not in ("linux", ""):
                return False

        return True

    def _rule_source_label(match: Dict) -> str:
        """Return honest source label: community vs experimental."""
        author = rule_author.get(match.get("id", ""), "")
        if "seraph" in author.lower() or "experimental" in author.lower():
            return "Seraph AI experimental rules"
        return "SigmaHQ/sigma community rules"

    # Evaluate every event against all loaded rules, with logsource gating
    matches_by_technique: Dict[str, List[Dict]] = defaultdict(list)
    total_firings = 0
    seen: set = set()  # deduplicate rule+event combos

    for raw in raw_events:
        ev = normalise_event(raw)
        matched_at = _iso_from_osquery_event(raw)
        ev_product = ev.get("_logsource_product", "")
        result = sigma_engine.evaluate_event(ev)
        for match in result.get("matches", []):
            # Logsource gate: drop cross-platform false positives
            if not _logsource_ok(ev_product, match):
                continue

            rule_id = match.get("id", match.get("title", ""))
            event_key = f"{rule_id}|{ev.get('CommandLine','')[:80]}|{ev.get('Image','')}"
            if event_key in seen:
                continue
            seen.add(event_key)

            for technique in match.get("attack_techniques", []):
                tid = technique.upper()
                matches_by_technique[tid].append({
                    "timestamp": matched_at,
                    "rule_id": match.get("id", ""),
                    "title": match.get("title", ""),
                    "rule_file": match.get("source_file", ""),
                    "rule_sha256": match.get("rule_sha256", ""),
                    "status": match.get("status", ""),
                    "level": match.get("level", ""),
                    "source": _rule_source_label(match),
                    "detection_basis": "rule_fired_against_osquery_telemetry",
                    "matched_event": {
                        "osquery_pack": raw.get("name", ""),
                        "image": ev.get("Image", ""),
                        "cmdline": ev.get("CommandLine", "")[:200],
                        "timestamp": raw.get("calendarTime", ""),
                        "unix_time": raw.get("unixTime"),
                        "action": raw.get("action", ""),
                    },
                })
                total_firings += 1

    print(f"\nReal sigma firings: {total_firings}")
    print(f"Techniques with real detections: {len(matches_by_technique)}")

    if matches_by_technique:
        print("\nTop detections:")
        for tid, hits in sorted(matches_by_technique.items(), key=lambda x: -len(x[1]))[:15]:
            titles = list({h['title'] for h in hits})[:3]
            print(f"  {tid:<14} {len(hits):>3} hit(s) — {', '.join(titles)}")

    # ── Write global analytics/sigma_matches.json ─────────────────────────────
    global_matches: List[Dict] = []
    for tid, hits in sorted(matches_by_technique.items()):
        for h in hits:
            global_matches.append({"technique": tid, **h})

    # New canonical path (consumed by scripts/run_arda_prevention_evidence.py)
    REPO_ANALYTICS_DIR.mkdir(exist_ok=True)
    repo_global_out = REPO_ANALYTICS_DIR / "sigma_matches.json"
    repo_global_out.write_text(json.dumps(global_matches, indent=2, sort_keys=True) + "\n")
    print(f"\nWrote global sigma_matches.json: {len(global_matches)} entries → {repo_global_out}")

    # Legacy path (kept for compatibility with older evidence-bundle tooling)
    if not args.no_legacy_evidence_bundle_output:
        evidence_analytics_dir = EVIDENCE_BUNDLE / "analytics"
        evidence_analytics_dir.mkdir(exist_ok=True)
        legacy_global_out = evidence_analytics_dir / "sigma_matches.json"
        legacy_global_out.write_text(json.dumps(global_matches, indent=2, sort_keys=True) + "\n")
        print(f"Wrote legacy sigma_matches.json: {len(global_matches)} entries → {legacy_global_out}")

    # ── Update per-TVR-run sigma_matches.json ─────────────────────────────────
    tvr_updated = 0
    for tid, hits in matches_by_technique.items():
        run_dirs = sorted(EVIDENCE_BUNDLE.glob(f"techniques/{tid}/TVR-*/"))
        for run_dir in run_dirs:
            sigma_file = run_dir / "analytics" / "sigma_matches.json"
            if not sigma_file.exists():
                continue
            # Merge: existing coverage records + new real firing records
            try:
                existing = json.loads(sigma_file.read_text())
            except Exception:
                existing = []
            # Separate coverage records from real firing records
            coverage = [e for e in existing if e.get("detection_basis") == "rule_covers_technique_by_attack_tag"]
            # Deduplicate new firings by rule_id
            seen_ids = {e.get("rule_id") for e in coverage}
            real_firings = [h for h in hits if h.get("rule_id") not in seen_ids]
            merged = real_firings + coverage  # real firings first
            sigma_file.write_text(json.dumps(merged, indent=2, sort_keys=True) + "\n")
            tvr_updated += 1

    print(f"TVR run files updated with real firings: {tvr_updated}")

    # ── Write evaluation report ───────────────────────────────────────────────
    report = {
        "schema": "sigma_osquery_evaluation.v1",
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "sigma_rules_loaded": len(sigma_engine.rules),
        "osquery_events_evaluated": len(raw_events),
        "total_real_firings": total_firings,
        "techniques_with_real_detections": len(matches_by_technique),
        "detections_by_technique": {
            tid: {
                "firing_count": len(hits),
                "rule_titles": sorted({h["title"] for h in hits}),
            }
            for tid, hits in sorted(matches_by_technique.items())
        },
    }
    report_out = EVIDENCE_BUNDLE / "sigma_evaluation_report.json"
    report_out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"Evaluation report: {report_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
