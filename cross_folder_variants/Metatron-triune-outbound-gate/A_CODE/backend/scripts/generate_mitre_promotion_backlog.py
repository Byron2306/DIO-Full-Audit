#!/usr/bin/env python3
"""Generate an actionable MITRE promotion backlog toward full 691 / S5 coverage."""

from __future__ import annotations

import importlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REPORT_DIR = Path(os.environ.get("MITRE_REPORT_DIR", str(ROOT / "test_reports")))
REPORT_DIR.mkdir(parents=True, exist_ok=True)
JSON_REPORT = REPORT_DIR / "mitre_promotion_backlog.json"
MD_REPORT = REPORT_DIR / "mitre_promotion_backlog.md"


def _load_sigma_summary(*, restore_legacy_baseline: bool) -> Dict[str, Any]:
    old_restore = os.environ.get("MITRE_RESTORE_LEGACY_BASELINE")
    old_promote = os.environ.get("MITRE_PROMOTE_S4_TO_S5")
    try:
        os.environ["MITRE_RESTORE_LEGACY_BASELINE"] = "true" if restore_legacy_baseline else "false"
        os.environ["MITRE_PROMOTE_S4_TO_S5"] = "false"
        module = importlib.import_module("backend.sigma_engine")
        module = importlib.reload(module)
        return module.sigma_engine.coverage_summary()
    finally:
        if old_restore is None:
            os.environ.pop("MITRE_RESTORE_LEGACY_BASELINE", None)
        else:
            os.environ["MITRE_RESTORE_LEGACY_BASELINE"] = old_restore

        if old_promote is None:
            os.environ.pop("MITRE_PROMOTE_S4_TO_S5", None)
        else:
            os.environ["MITRE_PROMOTE_S4_TO_S5"] = old_promote


def _rank_key(row: Dict[str, Any]) -> Tuple[int, int, int, str]:
    evidence = row.get("evidence") or {}
    telemetry_count = 0
    for key in ("atomic_validated_runs", "osquery_telemetry_hits", "ebpf_event_count", "soar_execution_count"):
        telemetry_count += 1 if int(evidence.get(key, 0) or 0) > 0 else 0
    return (
        -int(evidence.get("repo_reference_count", 0) or 0),
        -telemetry_count,
        -int(evidence.get("sigma_rule_count", 0) or 0),
        str(row.get("technique") or ""),
    )


def _next_action(row: Dict[str, Any]) -> Tuple[str, str]:
    score = float(row.get("score", 0.0) or 0.0)
    evidence = row.get("evidence") or {}
    sigma_rules = int(evidence.get("sigma_rule_count", 0) or 0)
    atomic_runs = int(evidence.get("atomic_validated_runs", 0) or 0)
    osquery_queries = int(evidence.get("osquery_mapped_queries", 0) or 0)
    osquery_hits = int(evidence.get("osquery_telemetry_hits", 0) or 0)
    ebpf_events = int(evidence.get("ebpf_event_count", 0) or 0)
    soar_playbooks = int(evidence.get("soar_playbook_count", 0) or 0)
    soar_execs = int(evidence.get("soar_execution_count", 0) or 0)
    telemetry_present = osquery_hits > 0 or ebpf_events > 0 or soar_execs > 0

    if score >= 5.0:
        return "already_s5", "Maintain evidence freshness; already at S5."
    if score >= 4.0:
        if atomic_runs < 3 and not telemetry_present:
            return "s4_needs_repeated_runs", "Repeat successful validation to at least 3 reproducible runs and preserve runtime telemetry linkage; repeated runs alone are not enough for S5."
        if atomic_runs < 3:
            return "s4_needs_repeated_runs", "Repeat successful validation until there are at least 3 reproducible runs for S5."
        if not telemetry_present:
            return "s4_needs_telemetry_linkage", "Preserve runtime telemetry and event linkage for existing successful validations."
        return "s4_needs_analyst_verdict", "Complete remaining TVR quality gates and analyst-reviewed verdict packaging for S5."
    if score >= 3.0:
        if sigma_rules <= 0:
            return "s3_needs_sigma_detection", "Add direct Sigma or equivalent analytic detection coverage to promote to S4."
        if atomic_runs <= 0:
            return "s3_needs_atomic_validation", "Add at least one successful atomic or equivalent validation run with preserved artifacts."
        return "s3_needs_direct_detection", "Correlate the successful execution to a direct analytic hit and package a TVR verdict for S4."
    if score >= 2.0:
        if atomic_runs <= 0:
            return "s2_needs_execution_evidence", "Run the technique successfully and preserve telemetry to promote from mapped-only to S3."
        if not telemetry_present:
            return "s2_needs_runtime_telemetry", "Capture raw runtime telemetry and tie it to the mapped technique."
        return "s2_needs_confidence_hardening", "Tighten the mapped analytic coverage into production-quality detection for S3."
    if sigma_rules <= 0 and osquery_queries <= 0 and soar_playbooks <= 0:
        return "s0_needs_analytics", "Create Sigma, osquery, or SOAR analytic mappings so the technique reaches at least S2."
    return "s1_needs_execution_evidence", "Mapped analytics exist, but the technique still needs successful execution evidence and preserved telemetry to move above S1."


def _build_backlog(summary: Dict[str, Any]) -> Dict[str, Any]:
    unified = summary.get("unified_coverage") or {}
    rows = list(unified.get("techniques") or [])
    rows.sort(key=_rank_key)

    actionable_rows: List[Dict[str, Any]] = []
    buckets: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        bucket, next_action = _next_action(row)
        backlog_row = {
            "technique": row.get("technique"),
            "score": row.get("score"),
            "score_level": row.get("score_level"),
            "promotion_tier": row.get("promotion_tier"),
            "sources": row.get("sources") or [],
            "evidence": row.get("evidence") or {},
            "backlog_bucket": bucket,
            "next_action": next_action,
        }
        if bucket != "already_s5":
            actionable_rows.append(backlog_row)
            buckets.setdefault(bucket, []).append(backlog_row)

    for rows_in_bucket in buckets.values():
        rows_in_bucket.sort(key=lambda item: _rank_key(item))

    return {
        "enterprise_technique_total": unified.get("enterprise_technique_total"),
        "enterprise_parent_total": unified.get("enterprise_parent_total"),
        "covered_score_gte3": unified.get("covered_score_gte3"),
        "covered_score_gte4": unified.get("covered_score_gte4"),
        "covered_score_gte5": unified.get("covered_score_gte5"),
        "gap_to_full_catalog_gte3": unified.get("gap_to_full_catalog_gte3"),
        "gap_to_full_catalog_gte4": unified.get("gap_to_full_catalog_gte4"),
        "gap_to_full_catalog_gte5": unified.get("gap_to_full_catalog_gte5"),
        "non_s5_backlog_count": len(actionable_rows),
        "bucket_counts": {bucket: len(items) for bucket, items in sorted(buckets.items())},
        "priority_examples": {bucket: items[:15] for bucket, items in sorted(buckets.items())},
        "top_backlog": actionable_rows[:100],
    }


def _write_markdown(report: Dict[str, Any]) -> None:
    current = report["current_reported"]
    evidence_real = report["evidence_real"]
    lines = [
        "# MITRE Promotion Backlog",
        "",
        f"- Generated: {report['generated_at']}",
        f"- Enterprise technique total: {evidence_real['enterprise_technique_total']}",
        f"- Enterprise parent total: {evidence_real['enterprise_parent_total']}",
        "",
        "## Snapshot",
        "",
        "| View | gte3 | gte4 | gte5 | gap_to_691_gte5 |",
        "|---|---:|---:|---:|---:|",
        f"| reported_now | {current['covered_score_gte3']} | {current['covered_score_gte4']} | {current['covered_score_gte5']} | {current['gap_to_full_catalog_gte5']} |",
        f"| evidence_real | {evidence_real['covered_score_gte3']} | {evidence_real['covered_score_gte4']} | {evidence_real['covered_score_gte5']} | {evidence_real['gap_to_full_catalog_gte5']} |",
        "",
        "## Bucket Counts",
        "",
    ]

    for bucket, count in (evidence_real.get("bucket_counts") or {}).items():
        lines.append(f"- {bucket}: {count}")

    lines.extend([
        "",
        "## Priority Examples",
        "",
    ])

    for bucket, examples in (evidence_real.get("priority_examples") or {}).items():
        lines.append(f"### {bucket}")
        lines.append("")
        lines.append("| Technique | Score | Next Action |")
        lines.append("|---|---:|---|")
        for item in examples[:10]:
            lines.append(
                f"| {item.get('technique')} | {item.get('score')} | {item.get('next_action')} |"
            )
        lines.append("")

    MD_REPORT.write_text("\n".join(lines), encoding="utf-8")


def run() -> int:
    current_summary = _load_sigma_summary(restore_legacy_baseline=True)
    evidence_real_summary = _load_sigma_summary(restore_legacy_baseline=False)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "current_reported": _build_backlog(current_summary),
        "evidence_real": _build_backlog(evidence_real_summary),
        "delta": {
            "legacy_floor_gte3_delta": int((current_summary.get("unified_coverage") or {}).get("covered_score_gte3") or 0)
            - int((evidence_real_summary.get("unified_coverage") or {}).get("covered_score_gte3") or 0),
            "legacy_floor_gte4_delta": int((current_summary.get("unified_coverage") or {}).get("covered_score_gte4") or 0)
            - int((evidence_real_summary.get("unified_coverage") or {}).get("covered_score_gte4") or 0),
            "legacy_floor_gte5_delta": int((current_summary.get("unified_coverage") or {}).get("covered_score_gte5") or 0)
            - int((evidence_real_summary.get("unified_coverage") or {}).get("covered_score_gte5") or 0),
        },
    }

    JSON_REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    _write_markdown(report)
    print(
        json.dumps(
            {
                "generated_at": report["generated_at"],
                "current_reported_gte5": report["current_reported"]["covered_score_gte5"],
                "evidence_real_gte5": report["evidence_real"]["covered_score_gte5"],
                "evidence_real_gap_to_691_gte5": report["evidence_real"]["gap_to_full_catalog_gte5"],
                "top_bucket_counts": report["evidence_real"]["bucket_counts"],
                "report_json": str(JSON_REPORT),
                "report_md": str(MD_REPORT),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())