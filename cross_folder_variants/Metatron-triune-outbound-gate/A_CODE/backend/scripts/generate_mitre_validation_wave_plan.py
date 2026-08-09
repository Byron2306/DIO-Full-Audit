#!/usr/bin/env python3
"""Generate concrete validation waves toward full MITRE S5 / 691 coverage."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import yaml


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.scripts.generate_mitre_promotion_backlog import _load_sigma_summary, _next_action, _rank_key


REPORT_DIR = ROOT / "test_reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
JSON_REPORT = REPORT_DIR / "mitre_validation_wave_plan.json"
MD_REPORT = REPORT_DIR / "mitre_validation_wave_plan.md"
ATTACK_PATH = ROOT / "atomic-red-team" / "atomic_red_team" / "enterprise-attack.json"
ATOMIC_CONFIG_PATH = ROOT / "config" / "atomic_powershell.yml"
ATOMICS_ROOT = ROOT / "atomic-red-team" / "atomics"


def _load_attack_lookup() -> Dict[str, Dict[str, Any]]:
    payload = json.loads(ATTACK_PATH.read_text(encoding="utf-8"))
    objects = payload.get("objects") or []
    lookup: Dict[str, Dict[str, Any]] = {}
    for obj in objects:
        if obj.get("type") != "attack-pattern":
            continue
        if obj.get("revoked") or obj.get("x_mitre_deprecated"):
            continue
        attack_id = ""
        for ref in obj.get("external_references") or []:
            if str(ref.get("source_name") or "").lower() == "mitre-attack":
                attack_id = str(ref.get("external_id") or "").strip().upper()
                break
        if not attack_id:
            continue
        tactic_names = [
            phase.get("phase_name", "")
            for phase in (obj.get("kill_chain_phases") or [])
            if str(phase.get("kill_chain_name") or "") == "mitre-attack"
        ]
        lookup[attack_id] = {
            "name": str(obj.get("name") or ""),
            "tactics": tactic_names,
            "is_subtechnique": bool(obj.get("x_mitre_is_subtechnique")),
        }
    return lookup


def _load_job_map() -> Dict[str, Dict[str, Any]]:
    payload = yaml.safe_load(ATOMIC_CONFIG_PATH.read_text(encoding="utf-8")) or {}
    runner_profile_map = {
        profile.get("profile_id"): profile
        for profile in (payload.get("runner_profiles") or [])
        if isinstance(profile, dict) and profile.get("profile_id")
    }

    mapping: Dict[str, Dict[str, Any]] = {}
    for job in payload.get("jobs") or []:
        if not isinstance(job, dict):
            continue
        runner_profile = str(job.get("runner_profile") or payload.get("default_runner_profile") or "")
        runner_meta = runner_profile_map.get(runner_profile) or {}
        for technique in job.get("techniques") or []:
            tech = str(technique or "").strip().upper()
            if not tech:
                continue
            entry = mapping.setdefault(tech, {"jobs": [], "runner_profiles": []})
            entry["jobs"].append(
                {
                    "job_id": str(job.get("job_id") or ""),
                    "priority": str(job.get("priority") or ""),
                    "runner_profile": runner_profile,
                    "platforms": runner_meta.get("platforms") or [],
                }
            )
            if runner_profile and runner_profile not in entry["runner_profiles"]:
                entry["runner_profiles"].append(runner_profile)
    return mapping


def _enrich_rows(rows: List[Dict[str, Any]], attack_lookup: Dict[str, Dict[str, Any]], job_map: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    enriched: List[Dict[str, Any]] = []
    for row in rows:
        technique = str(row.get("technique") or "")
        attack_meta = attack_lookup.get(technique) or {}
        job_meta = job_map.get(technique) or {"jobs": [], "runner_profiles": []}
        enriched.append(
            {
                **row,
                "technique_name": attack_meta.get("name") or "",
                "tactics": attack_meta.get("tactics") or [],
                "has_atomic_dir": (ATOMICS_ROOT / technique).exists(),
                "jobs": job_meta.get("jobs") or [],
                "runner_profiles": job_meta.get("runner_profiles") or [],
            }
        )
    return enriched


def _full_backlog_rows(summary: Dict[str, Any]) -> List[Dict[str, Any]]:
    unified = summary.get("unified_coverage") or {}
    rows = list(unified.get("techniques") or [])
    rows.sort(key=_rank_key)

    actionable: List[Dict[str, Any]] = []
    for row in rows:
        bucket, next_action = _next_action(row)
        if bucket == "already_s5":
            continue
        actionable.append(
            {
                "technique": row.get("technique"),
                "score": row.get("score"),
                "score_level": row.get("score_level"),
                "promotion_tier": row.get("promotion_tier"),
                "sources": row.get("sources") or [],
                "evidence": row.get("evidence") or {},
                "backlog_bucket": bucket,
                "next_action": next_action,
            }
        )
    return actionable


def _split_waves(rows: List[Dict[str, Any]], *, wave_size: int) -> List[Dict[str, Any]]:
    waves: List[Dict[str, Any]] = []
    for index in range(0, len(rows), wave_size):
        chunk = rows[index:index + wave_size]
        waves.append(
            {
                "wave_id": f"wave-{len(waves) + 1:02d}",
                "size": len(chunk),
                "runner_profiles": sorted({profile for row in chunk for profile in row.get("runner_profiles") or []}),
                "job_ids": sorted({job.get("job_id") for row in chunk for job in row.get("jobs") or [] if job.get("job_id")}),
                "techniques": chunk,
            }
        )
    return waves


def _write_markdown(report: Dict[str, Any]) -> None:
    lines = [
        "# MITRE Validation Wave Plan",
        "",
        f"- Generated: {report['generated_at']}",
        f"- Enterprise technique total: {report['enterprise_technique_total']}",
        f"- Current reported S4-needs-repeated-runs: {report['repeat_run_lane']['count']}",
        f"- Current execution-evidence candidates considered: {report['execution_lane']['count']}",
        "",
        "## Lanes",
        "",
        f"- Repeat-run lane: {report['repeat_run_lane']['count']} techniques that are closest to S5 under current scoring.",
        f"- Execution-evidence lane: {report['execution_lane']['count']} techniques selected for immediate validation waves.",
        "",
        "## Repeat-Run Lane",
        "",
        "| Technique | Name | Jobs | Atomic | Next Action |",
        "|---|---|---|---|---|",
    ]

    for item in report["repeat_run_lane"]["techniques"][:25]:
        lines.append(
            f"| {item['technique']} | {item.get('technique_name') or ''} | {', '.join(job.get('job_id') for job in item.get('jobs') or [] if job.get('job_id'))} | {item.get('has_atomic_dir')} | {item.get('next_action')} |"
        )

    for wave in report["execution_lane"]["waves"]:
        lines.extend(
            [
                "",
                f"## {wave['wave_id'].upper()}",
                "",
                f"- Size: {wave['size']}",
                f"- Runner profiles: {', '.join(wave['runner_profiles'])}",
                f"- Job ids: {', '.join(wave['job_ids'])}",
                "",
                "| Technique | Name | Tactics | Atomic | Jobs | Next Action |",
                "|---|---|---|---|---|---|",
            ]
        )
        for item in wave["techniques"]:
            lines.append(
                f"| {item['technique']} | {item.get('technique_name') or ''} | {', '.join(item.get('tactics') or [])} | {item.get('has_atomic_dir')} | {', '.join(job.get('job_id') for job in item.get('jobs') or [] if job.get('job_id'))} | {item.get('next_action')} |"
            )

    MD_REPORT.write_text("\n".join(lines), encoding="utf-8")


def run() -> int:
    summary = _load_sigma_summary(restore_legacy_baseline=True)
    full_backlog = _full_backlog_rows(summary)
    unified = summary.get("unified_coverage") or {}
    attack_lookup = _load_attack_lookup()
    job_map = _load_job_map()

    repeat_run_rows = [row for row in full_backlog if row.get("backlog_bucket") == "s4_needs_repeated_runs"]
    execution_rows = [row for row in full_backlog if row.get("backlog_bucket") == "s1_needs_execution_evidence"]

    repeat_run_enriched = _enrich_rows(repeat_run_rows, attack_lookup, job_map)
    execution_enriched = _enrich_rows(execution_rows[:100], attack_lookup, job_map)
    waves = _split_waves(execution_enriched, wave_size=25)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "enterprise_technique_total": unified.get("enterprise_technique_total"),
        "enterprise_parent_total": unified.get("enterprise_parent_total"),
        "repeat_run_lane": {
            "count": len(repeat_run_enriched),
            "techniques": repeat_run_enriched,
        },
        "execution_lane": {
            "count": len(execution_enriched),
            "waves": waves,
        },
    }

    JSON_REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    _write_markdown(report)
    print(
        json.dumps(
            {
                "generated_at": report["generated_at"],
                "repeat_run_candidates": report["repeat_run_lane"]["count"],
                "execution_wave_candidates": report["execution_lane"]["count"],
                "wave_count": len(report["execution_lane"]["waves"]),
                "report_json": str(JSON_REPORT),
                "report_md": str(MD_REPORT),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())