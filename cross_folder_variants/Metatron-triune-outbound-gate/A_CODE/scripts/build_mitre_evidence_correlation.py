#!/usr/bin/env python3
"""
Build a canonical MITRE evidence correlation index.

This intentionally keeps evidence bases separate:
- atomic_execution: real Atomic/atomic-style run artifacts
- osquery_mapping: queries that claim technique coverage
- osquery_event: raw osquery telemetry tagged or matched to a technique
- sigma_coverage: Sigma rule covers technique by ATT&CK tag
- sigma_firing: Sigma rule fired against atomic stdout telemetry, osquery,
                sysmon, Falco, Suricata, Zeek, deception engine, YARA, etc.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List


TECHNIQUE_RE = re.compile(r"\bT\d{4}(?:\.\d{3})?\b", re.IGNORECASE)
IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
PATH_RE = re.compile(r"(?:/[A-Za-z0-9._@%+=:,~-]+)+")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None


def _techniques_from(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        text = " ".join(str(v) for v in value)
    elif isinstance(value, dict):
        text = json.dumps(value, sort_keys=True, default=str)
    else:
        text = str(value)
    return sorted({m.upper() for m in TECHNIQUE_RE.findall(text)})


def _add(index: Dict[str, Dict[str, Any]], tid: str, basis: str, record: Dict[str, Any]) -> None:
    row = index.setdefault(
        tid,
        {
            "technique": tid,
            "atomic_execution": [],
            "osquery_mapping": [],
            "osquery_event": [],
            "sigma_coverage": [],
            "sigma_firing": [],
            "network_telemetry": [],
            "artifact_evidence": [],
            "response_evidence": [],
        },
    )
    row[basis].append(record)


def _iter_json_files(root: Path) -> Iterable[Path]:
    if root.exists():
        yield from sorted(root.rglob("*.json"))


def _dedupe(items: List[str]) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _collect_values(value: Any) -> List[str]:
    values: List[str] = []
    if isinstance(value, dict):
        for child in value.values():
            values.extend(_collect_values(child))
    elif isinstance(value, list):
        for child in value:
            values.extend(_collect_values(child))
    elif value is not None:
        values.append(str(value))
    return values


def _extract_ips(value: Any) -> List[str]:
    hits: List[str] = []
    for text in _collect_values(value):
        hits.extend(IP_RE.findall(text))
    return _dedupe(hits)


def _extract_paths(value: Any) -> List[str]:
    hits: List[str] = []
    for text in _collect_values(value):
        hits.extend(PATH_RE.findall(text))
    return _dedupe(hits)


def ingest_atomic_runs(index: Dict[str, Dict[str, Any]], roots: List[Path]) -> int:
    count = 0
    for root in roots:
        for path in _iter_json_files(root):
            data = _load_json(path)
            if not isinstance(data, dict):
                continue
            techs = sorted(set(_techniques_from(data.get("techniques_executed")) or _techniques_from(data.get("techniques"))))
            if not techs:
                continue
            record = {
                "path": str(path),
                "job_id": data.get("job_id"),
                "run_id": data.get("run_id") or data.get("id"),
                "outcome": data.get("outcome") or data.get("status"),
                "message": data.get("message"),
                "started_at": data.get("started_at") or data.get("timestamp"),
                "completed_at": data.get("completed_at"),
            }
            for tid in techs:
                _add(index, tid, "atomic_execution", record)
                count += 1
    return count


def ingest_osquery_catalog(index: Dict[str, Dict[str, Any]], catalog_path: Path) -> int:
    data = _load_json(catalog_path)
    rows = data if isinstance(data, list) else (data.get("queries") if isinstance(data, dict) else [])
    count = 0
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        techs = _techniques_from(row.get("attack_techniques") or row)
        for tid in techs:
            _add(
                index,
                tid,
                "osquery_mapping",
                {
                    "name": row.get("name"),
                    "description": row.get("description"),
                    "sql": row.get("sql"),
                    "path": str(catalog_path),
                },
            )
            count += 1
    return count


def ingest_osquery_log(index: Dict[str, Dict[str, Any]], log_path: Path) -> int:
    if not log_path.exists():
        return 0
    count = 0
    for line_no, line in enumerate(log_path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        techs = _techniques_from(row)
        if not techs:
            continue
        for tid in techs:
            _add(
                index,
                tid,
                "osquery_event",
                {
                    "path": str(log_path),
                    "line": line_no,
                    "name": row.get("name"),
                    "action": row.get("action"),
                    "calendar_time": row.get("calendarTime"),
                    "unix_time": row.get("unixTime"),
                },
            )
            count += 1
    return count


def ingest_sigma_matches(index: Dict[str, Dict[str, Any]], sigma_path: Path) -> int:
    data = _load_json(sigma_path)
    rows = data if isinstance(data, list) else (data.get("matches") if isinstance(data, dict) else [])
    count = 0
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        techs = _techniques_from(row.get("technique") or row.get("techniques") or row)
        basis = "sigma_firing" if row.get("detection_basis") == "rule_fired_against_osquery_telemetry" else "sigma_coverage"
        record = {
            "path": str(sigma_path),
            "rule_id": row.get("rule_id"),
            "title": row.get("title"),
            "level": row.get("level"),
            "timestamp": row.get("timestamp") or row.get("matched_at"),
            "detection_basis": row.get("detection_basis"),
            "matched_event": row.get("matched_event") if basis == "sigma_firing" else None,
        }
        for tid in techs:
            _add(index, tid, basis, record)
            count += 1
    return count


def ingest_soar_executions(index: Dict[str, Dict[str, Any]], soar_path: Path) -> int:
    data = _load_json(soar_path)
    rows = data if isinstance(data, list) else (data.get("executions") if isinstance(data, dict) else [])
    count = 0
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        trigger = row.get("trigger_event") or {}
        techs = sorted(set(_techniques_from(trigger.get("validated_techniques") or trigger.get("mitre_techniques") or trigger)))
        if not techs:
            continue
        record = {
            "path": str(soar_path),
            "execution_id": row.get("id"),
            "playbook_id": row.get("playbook_id"),
            "playbook_name": row.get("playbook_name"),
            "status": row.get("status"),
            "started_at": row.get("started_at"),
            "completed_at": row.get("completed_at"),
            "host_id": trigger.get("host_id"),
            "source_ip": trigger.get("source_ip"),
            "pid": trigger.get("pid"),
            "file_path": trigger.get("file_path"),
            "actions": [
                {
                    "action": step.get("action"),
                    "status": step.get("status"),
                    "timestamp": (step.get("result") or {}).get("timestamp") or step.get("completed_at"),
                }
                for step in (row.get("step_results") or [])
            ],
        }
        for tid in techs:
            _add(index, tid, "response_evidence", record)
            if record.get("file_path"):
                _add(index, tid, "artifact_evidence", {"path": str(soar_path), "file_path": record.get("file_path"), "execution_id": row.get("id")})
            count += 1
    return count


def ingest_run_sigma_companions(index: Dict[str, Dict[str, Any]], roots: List[Path]) -> int:
    """Scan atomic-validation result dirs for run_*_sigma.json companion files."""
    count = 0
    for root in roots:
        if not root.exists():
            continue
        for sigma_file in sorted(root.rglob("run_*_sigma.json")):
            data = _load_json(sigma_file)
            matches = data if isinstance(data, list) else (data.get("matches") if isinstance(data, dict) else [])
            if not matches:
                continue
            # resolve the parent run file to get technique IDs
            stem = sigma_file.stem  # run_<id>_sigma
            run_id = stem[len("run_"):-len("_sigma")]
            run_file = sigma_file.parent / f"run_{run_id}.json"
            run_data = _load_json(run_file) if run_file.exists() else {}
            run_techs = set(_techniques_from(
                (run_data or {}).get("techniques_executed") or (run_data or {}).get("techniques")
            ))
            for match in matches:
                if not isinstance(match, dict):
                    continue
                # techniques from rule tags, falling back to run techniques
                rule_techs = set(_techniques_from(
                    match.get("attack_techniques") or match.get("technique") or match.get("techniques")
                ))
                techs = (rule_techs & run_techs) or rule_techs or run_techs
                record = {
                    "path": str(sigma_file),
                    "run_id": run_id,
                    "rule_id": match.get("rule_id"),
                    "title": match.get("title"),
                    "level": match.get("level"),
                    "source_file": match.get("source_file"),
                    "detection_basis": "rule_fired_against_atomic_stdout_telemetry",
                    "technique_relevant": match.get("technique_relevant", True),
                    "match_count": match.get("match_count", 1),
                }
                for tid in techs:
                    _add(index, tid, "sigma_firing", record)
                    count += 1
    return count


def ingest_sigma_evaluation_report(index: Dict[str, Dict[str, Any]], report_path: Path) -> int:
    """Ingest sigma_evaluation_report.json — rules fired against osquery/sysmon telemetry."""
    data = _load_json(report_path)
    if not data or not isinstance(data, dict):
        return 0
    count = 0
    for tid, det in (data.get("detections_by_technique") or {}).items():
        tid = tid.upper()
        if not isinstance(det, dict):
            continue
        record = {
            "path": str(report_path),
            "rule_titles": det.get("rule_titles") or [],
            "firing_count": det.get("firing_count", 1),
            "telemetry_source": det.get("telemetry_source"),
            "detection_basis": det.get("detection_basis", "rule_fired_against_telemetry"),
        }
        _add(index, tid, "sigma_firing", record)
        count += 1
    return count


def ingest_multi_source_report(index: Dict[str, Dict[str, Any]], report_path: Path) -> int:
    """Ingest multi_source_detection_report.json — Falco, Suricata, Zeek, deception, YARA, etc."""
    data = _load_json(report_path)
    if not data or not isinstance(data, dict):
        return 0
    count = 0
    for tid, det in (data.get("detections_by_technique") or {}).items():
        tid = tid.upper()
        if not isinstance(det, dict):
            continue
        sources = det.get("sources") or []
        record = {
            "path": str(report_path),
            "detection_count": det.get("detection_count", 1),
            "sources": sources,
            "earliest": det.get("earliest"),
            "latest": det.get("latest"),
            "detection_basis": "multi_source_real_detection",
        }
        # telemetry sources that represent active live detection go to sigma_firing
        # pure mapping sources go to sigma_coverage
        live_sources = {s for s in sources if s not in ("sigma_rule_coverage",)}
        if live_sources:
            _add(index, tid, "sigma_firing", record)
        else:
            _add(index, tid, "sigma_coverage", record)
        count += 1
    return count


def ingest_zeek_conn(index: Dict[str, Dict[str, Any]], conn_path: Path) -> int:
    if not conn_path.exists():
        return 0
    fields: List[str] = []
    rows: List[Dict[str, Any]] = []
    with conn_path.open(encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if line.startswith("#fields\t"):
                fields = line.split("\t")[1:]
                continue
            if line.startswith("#") or not line or not fields:
                continue
            parts = line.split("\t")
            if len(parts) != len(fields):
                continue
            rows.append(dict(zip(fields, parts)))

    count = 0
    ip_to_techniques: Dict[str, set[str]] = defaultdict(set)
    for tid, row in index.items():
        for ip in _extract_ips(row.get("response_evidence") or []):
            ip_to_techniques[ip].add(tid)
        for ip in _extract_ips(row.get("osquery_event") or []):
            ip_to_techniques[ip].add(tid)
        for ip in _extract_ips(row.get("sigma_firing") or []):
            ip_to_techniques[ip].add(tid)

    for row in rows:
        row_ips = {str(row.get("id.orig_h") or ""), str(row.get("id.resp_h") or "")}
        matched_tids = set()
        for ip in row_ips:
            matched_tids.update(ip_to_techniques.get(ip) or set())
        if not matched_tids:
            continue
        record = {
            "path": str(conn_path),
            "timestamp": row.get("ts"),
            "uid": row.get("uid"),
            "src_ip": row.get("id.orig_h"),
            "src_port": row.get("id.orig_p"),
            "dest_ip": row.get("id.resp_h"),
            "dest_port": row.get("id.resp_p"),
            "proto": row.get("proto"),
            "service": row.get("service"),
        }
        for tid in matched_tids:
            _add(index, tid, "network_telemetry", record)
            count += 1
    return count


def summarise(index: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    basis_names = [
        "atomic_execution",
        "osquery_mapping",
        "osquery_event",
        "sigma_coverage",
        "sigma_firing",
        "network_telemetry",
        "artifact_evidence",
        "response_evidence",
    ]
    by_basis = {basis: sum(len(row[basis]) for row in index.values()) for basis in basis_names}
    technique_counts = {
        "total": len(index),
        "with_atomic_execution": sum(1 for row in index.values() if row["atomic_execution"]),
        "with_osquery_mapping": sum(1 for row in index.values() if row["osquery_mapping"]),
        "with_osquery_event": sum(1 for row in index.values() if row["osquery_event"]),
        "with_sigma_coverage": sum(1 for row in index.values() if row["sigma_coverage"]),
        "with_sigma_firing": sum(1 for row in index.values() if row["sigma_firing"]),
        "with_network_telemetry": sum(1 for row in index.values() if row["network_telemetry"]),
        "with_artifact_evidence": sum(1 for row in index.values() if row["artifact_evidence"]),
        "with_response_evidence": sum(1 for row in index.values() if row["response_evidence"]),
    }
    layered_counts = {"all_six_layers": 0, "five_plus_layers": 0}
    enriched: Dict[str, Dict[str, Any]] = {}
    for tid, row in sorted(index.items()):
        layers = {
            "execution": bool(row["atomic_execution"]),
            "host_telemetry": bool(row["osquery_event"]),
            "network_telemetry": bool(row["network_telemetry"]),
            "detection": bool(row["sigma_firing"] or row["sigma_coverage"]),
            "artifact": bool(row["artifact_evidence"]),
            "response": bool(row["response_evidence"]),
        }
        anchors = {
            "ip_addresses": _extract_ips(row),
            "file_paths": _extract_paths(row),
        }
        layer_count = sum(1 for present in layers.values() if present)
        if layer_count == 6:
            layered_counts["all_six_layers"] += 1
        if layer_count >= 5:
            layered_counts["five_plus_layers"] += 1
        enriched[tid] = {
            **row,
            "layers": layers,
            "layer_count": layer_count,
            "correlation_anchors": anchors,
            "perfect_story": layer_count == 6 and any(anchors.values()),
        }
    index.clear()
    index.update(enriched)
    return {"records_by_basis": by_basis, "technique_counts": technique_counts, "layered_counts": layered_counts}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build MITRE evidence correlation index.")
    parser.add_argument("--atomic-root", action="append", default=[], help="Directory containing atomic run JSON files. May repeat.")
    parser.add_argument("--osquery-catalog", default="backend/data/generated_osquery_builtin_queries.json")
    parser.add_argument("--osquery-log", default="evidence-bundle/osqueryd.results.log")
    parser.add_argument("--sigma-matches", default="analytics/sigma_matches.json")
    parser.add_argument("--sigma-eval-report", default="", help="Path to sigma_evaluation_report.json (osquery/sysmon telemetry firings).")
    parser.add_argument("--multi-source-report", default="", help="Path to multi_source_detection_report.json (Falco/Suricata/Zeek/deception/YARA).")
    parser.add_argument("--soar-executions", default="artifacts/soar_executions_archive.json")
    parser.add_argument("--zeek-conn", default="zeek_logs/conn.log")
    parser.add_argument("--out", default="analytics/mitre_evidence_correlation.json")
    args = parser.parse_args()

    repo = Path(__file__).resolve().parent.parent
    atomic_roots = [repo / p for p in args.atomic_root] if args.atomic_root else [
        repo / "artifacts" / "atomic-validation",
        repo / "atomic-validation-results",
        repo / "raw-runs",
    ]

    # Auto-discover sigma_evaluation_report and multi_source_detection_report
    # from the most recent metatron_evidence_bundle_* directory if not specified.
    def _latest_bundle_file(filename: str) -> Path:
        bundles = sorted(repo.glob("metatron_evidence_bundle_*/"), reverse=True)
        for b in bundles:
            p = b / filename
            if p.exists():
                return p
        return repo / filename

    sigma_eval_path = Path(args.sigma_eval_report) if args.sigma_eval_report else _latest_bundle_file("sigma_evaluation_report.json")
    multi_source_path = Path(args.multi_source_report) if args.multi_source_report else _latest_bundle_file("multi_source_detection_report.json")

    index: Dict[str, Dict[str, Any]] = {}
    ingest_counts = {
        "atomic_execution": ingest_atomic_runs(index, atomic_roots),
        "osquery_mapping": ingest_osquery_catalog(index, repo / args.osquery_catalog),
        "osquery_event": ingest_osquery_log(index, repo / args.osquery_log),
        "sigma_flat_matches": ingest_sigma_matches(index, repo / args.sigma_matches),
        "sigma_run_companions": ingest_run_sigma_companions(index, atomic_roots),
        "sigma_eval_report": ingest_sigma_evaluation_report(index, sigma_eval_path),
        "multi_source_detections": ingest_multi_source_report(index, multi_source_path),
        "response_evidence": ingest_soar_executions(index, repo / args.soar_executions),
        "network_telemetry": ingest_zeek_conn(index, repo / args.zeek_conn),
    }

    out = repo / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "mitre_evidence_correlation.v3",
        "generated_at": _now(),
        "inputs": {
            "atomic_roots": [str(p) for p in atomic_roots],
            "osquery_catalog": str(repo / args.osquery_catalog),
            "osquery_log": str(repo / args.osquery_log),
            "sigma_matches": str(repo / args.sigma_matches),
            "sigma_eval_report": str(sigma_eval_path),
            "multi_source_report": str(multi_source_path),
            "soar_executions": str(repo / args.soar_executions),
            "zeek_conn": str(repo / args.zeek_conn),
        },
        "ingest_counts": ingest_counts,
        "summary": summarise(index),
        "techniques": {tid: index[tid] for tid in sorted(index)},
    }
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    print(json.dumps(payload["summary"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
