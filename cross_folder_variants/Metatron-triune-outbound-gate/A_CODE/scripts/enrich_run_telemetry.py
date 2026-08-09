#!/usr/bin/env python3
"""
enrich_run_telemetry.py
=======================
Post-sweep enrichment pass.  For each run_*.json with a real atomic execution
it writes three companion files that evidence_bundle.py consumes on the next
TVR regeneration:

  run_<id>_osquery.ndjson   -- synthetic osquery-style events from stdout
  run_<id>_sigma.json       -- sigma rule matches against those events
  run_<id>_anchors.json     -- extracted host / network anchors

Usage:
    python3 scripts/enrich_run_telemetry.py [--results-dir PATH] [--dry-run] [--force]
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


RESULTS_DIR = Path(
    os.environ.get("ATOMIC_VALIDATION_RESULTS_DIR",
                   "/var/lib/seraph-ai/artifacts/atomic-validation")
)

_PATH_RE = re.compile(r"(?:/[A-Za-z0-9._@%+=:,~-]+){2,}")
_IP_RE   = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_HASH_RE = re.compile(r"\b[a-fA-F0-9]{40,64}\b")
_PID_RE  = re.compile(r"\bpid[=:\s]+(\d+)\b", re.IGNORECASE)
_BLOCK_RE = re.compile(r"(?=Executing test:)")

_DOCKER_BRIDGE_CIDR = "172.17.0.0/16"


def _dedupe(items):
    seen, out = set(), []
    for item in items:
        if item and item not in seen:
            seen.add(item); out.append(item)
    return out


def _ts_unix(ts):
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S"):
        try:
            return int(datetime.strptime(ts.strip(), fmt).timestamp())
        except Exception:
            continue
    return 0


def _is_real(run):
    return (
        str(run.get("status") or "") in ("success", "partial")
        and "Executing test:" in str(run.get("stdout") or "")
        and "ShowDetailsBrief" not in str(run.get("command") or "")
    )


def parse_stdout_events(stdout, technique_id, run_id, finished_at):
    unix_t = _ts_unix(finished_at)
    events = []
    for idx, block in enumerate(_BLOCK_RE.split(stdout)):
        if "Executing test:" not in block:
            continue
        m = re.search(r"Executing test:\s*(.+?)(?:\n|$)", block)
        title = m.group(1).strip() if m else f"block-{idx}"
        paths  = _dedupe(_PATH_RE.findall(block))[:10]
        ips    = _dedupe(ip for ip in _IP_RE.findall(block)
                         if not ip.startswith(("127.", "0.")))[:6]
        hashes = _dedupe(_HASH_RE.findall(block))[:6]
        pids   = [int(x) for x in _PID_RE.findall(block)][:4]
        cmd_line = block[block.find("\n")+1 : block.find("\n")+401].strip()
        events.append({
            "unixTime":      unix_t + idx,
            "calendarTime":  finished_at,
            "name":          f"atomic_{technique_id.replace('.','_').lower()}_b{idx}",
            "action":        "added",
            "hostIdentifier": os.environ.get("EVIDENCE_HOSTNAME", "debian-node-01"),
            "technique_id":  technique_id,
            "run_id":        run_id,
            "columns": {
                "test_name":        title,
                "technique_id":     technique_id,
                "run_id":           run_id,
                "CommandLine":      cmd_line[:400],
                "Image":            paths[0] if paths else "",
                "TargetFilename":   paths[0] if paths else "",
                "DestinationIp":    ips[0] if ips else "",
                "SourceIp":         ips[1] if len(ips) > 1 else "",
                "extracted_paths":  json.dumps(paths),
                "extracted_ips":    json.dumps(ips),
                "extracted_hashes": json.dumps(hashes),
                "extracted_pids":   json.dumps(pids),
                "stdout_block":     block[:512],
            },
            "extracted": {"paths": paths, "ips": ips,
                          "hashes": hashes, "pids": pids},
        })
    return events


def extract_anchors(run):
    anchors: Dict[str, Any] = {}
    cmd_str = str(run.get("command") or "")
    sandbox = str(run.get("sandbox") or "")
    stdout  = str(run.get("stdout") or "")

    # cmd_str is str() of a list so "--network bridge" has comma+quote between them.
    # Detect bridge: "bridge" anywhere in cmd OR sandbox has cap-drop but not none.
    uses_bridge = (
        "bridge" in cmd_str
        or ("cap-drop" in sandbox and "none" not in sandbox)
    )
    if uses_bridge:
        anchors["uses_network"]       = True
        anchors["docker_bridge_cidr"] = _DOCKER_BRIDGE_CIDR
        anchors["candidate_ips"]      = [f"172.17.0.{n}" for n in range(1, 5)]

    ips = _dedupe(ip for ip in _IP_RE.findall(stdout)
                  if not ip.startswith(("127.", "0.")))[:8]
    if ips:    anchors["stdout_ips"]    = ips
    paths = _dedupe(_PATH_RE.findall(stdout))[:12]
    if paths:  anchors["stdout_paths"]  = paths
    hashes = _dedupe(_HASH_RE.findall(stdout))[:8]
    if hashes: anchors["stdout_hashes"] = hashes
    pids = [int(x) for x in _PID_RE.findall(stdout)][:6]
    if pids:   anchors["stdout_pids"]   = pids
    return anchors


def _load_sigma_engine():
    repo_root = str(Path(__file__).resolve().parent.parent)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    try:
        from sigma_engine import sigma_engine
        return sigma_engine
    except Exception as exc:
        print(f"  [warn] sigma_engine unavailable: {exc}", flush=True)
        return None


def evaluate_sigma(events, technique_ids, engine):
    if not engine or not events:
        return []
    tech_set = {t.upper() for t in technique_ids}
    tech_set |= {t.split(".")[0] for t in tech_set}
    fired: Dict[str, Dict] = {}
    for evt in events:
        flat = {**evt.get("columns", {}),
                "name": evt.get("name", ""),
                "action": evt.get("action", "")}
        for match in (engine.evaluate_event(flat).get("matches") or []):
            rid = str(match["id"])
            if rid not in fired:
                fired[rid] = {
                    "rule_id":          rid,
                    "title":            match.get("title", ""),
                    "level":            match.get("level", ""),
                    "attack_techniques": match.get("attack_techniques") or [],
                    "source_file":      match.get("source_file", ""),
                    "match_count":      0,
                    "technique_relevant": False,
                }
            fired[rid]["match_count"] += 1
            rule_techs = {t.upper() for t in fired[rid]["attack_techniques"]}
            if rule_techs & tech_set:
                fired[rid]["technique_relevant"] = True
    return list(fired.values())


def enrich_run(run_file, engine, *, dry_run=False, force=False):
    try:
        run = json.loads(run_file.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"  [skip] cannot read {run_file.name}: {exc}", flush=True)
        return None

    if not _is_real(run):
        return None

    run_id = str(run.get("run_id") or run_file.stem.replace("run_", ""))
    techniques = [str(t).strip().upper()
                  for t in (run.get("techniques_executed") or run.get("techniques") or [])
                  if str(t).strip()]
    if not techniques:
        return None

    sigma_path   = run_file.parent / f"run_{run_id}_sigma.json"
    anchors_path = run_file.parent / f"run_{run_id}_anchors.json"
    osquery_path = run_file.parent / f"run_{run_id}_osquery.ndjson"

    if sigma_path.exists() and anchors_path.exists() and not force:
        return None  # already enriched

    finished_at = str(run.get("finished_at") or run.get("started_at") or "")
    stdout      = str(run.get("stdout") or "")

    all_events = []
    for tech in techniques:
        all_events.extend(parse_stdout_events(stdout, tech, run_id, finished_at))

    anchors       = extract_anchors(run)
    sigma_matches = evaluate_sigma(all_events, techniques, engine)

    summary = {
        "run_id":                   run_id,
        "techniques":               techniques,
        "finished_at":              finished_at,
        "osquery_event_count":      len(all_events),
        "sigma_match_count":        len(sigma_matches),
        "technique_relevant_sigma": sum(1 for s in sigma_matches if s.get("technique_relevant")),
        "anchor_keys":              list(anchors.keys()),
    }

    if not dry_run:
        if all_events:
            osquery_path.write_text(
                "\n".join(json.dumps(e) for e in all_events), encoding="utf-8")
        sigma_path.write_text(json.dumps(sigma_matches, indent=2), encoding="utf-8")
        anchors_path.write_text(json.dumps(anchors, indent=2), encoding="utf-8")

    return summary


def main():
    parser = argparse.ArgumentParser(
        description="Enrich atomic run artifacts with sigma matches and network anchors.")
    parser.add_argument("--results-dir", default=str(RESULTS_DIR))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force",   action="store_true",
                        help="Re-enrich even when companion files exist.")
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    if not results_dir.exists():
        print(f"[ERROR] Results dir not found: {results_dir}", flush=True)
        return 1

    engine = _load_sigma_engine()
    if engine:
        print(f"Sigma engine: {len(getattr(engine, 'rules', []))} rules loaded.", flush=True)
    else:
        print("Sigma engine unavailable — sigma files will be empty lists.", flush=True)

    run_files = sorted(
        f for f in results_dir.rglob("run_*.json")
        if not any(tag in f.name for tag in ("_sigma", "_anchors"))
    )
    print(f"Found {len(run_files)} run files in {results_dir}\n", flush=True)

    enriched = skipped = already = 0
    for run_file in run_files:
        result = enrich_run(run_file, engine, dry_run=args.dry_run, force=args.force)
        if result is None:
            rid = run_file.stem.replace("run_", "")
            if (run_file.parent / f"run_{rid}_sigma.json").exists() and not args.force:
                already += 1
            else:
                skipped += 1
        else:
            print(
                f"  {run_file.name}: [{', '.join(result['techniques'])}] "
                f"events={result['osquery_event_count']} "
                f"sigma={result['sigma_match_count']} "
                f"relevant={result['technique_relevant_sigma']} "
                f"anchors={result['anchor_keys']}",
                flush=True,
            )
            enriched += 1

    print(f"\nDone.  Enriched={enriched}  Skipped={skipped}  AlreadyDone={already}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
