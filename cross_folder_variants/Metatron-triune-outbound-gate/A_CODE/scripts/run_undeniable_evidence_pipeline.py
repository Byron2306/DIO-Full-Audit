#!/usr/bin/env python3
"""Build a provenance-first evidence run across ARDA, telemetry, Sigma, and TVRs.

This wrapper does not replace the existing collectors. It runs them in a strict
order, records every command and log, then emits a single manifest that
separates:

- observed evidence: direct enforcement or direct detection
- correlated evidence: multi-source joins against real telemetry
- support evidence: catalog coverage, mappings, or historical context

By default the pipeline is conservative and non-mutating:
- it integrates existing evidence where possible
- multi-source correlation runs with --no-upgrade
- bundle reconciliation is dry-run only

Use --profile full-run to re-run heavy collection stages.
Use --promote-detections to allow TVR promotion during multi-source correlation.
Use --allow-reconcile-write to let reconcile_bundle.py patch the bundle.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BUNDLE_DIR = REPO_ROOT / "evidence-bundle"
DEFAULT_PIPELINE_ROOT = REPO_ROOT / "artifacts" / "undeniable_pipeline"
DEFAULT_ANALYTICS_DIR = REPO_ROOT / "analytics"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def slug_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def json_dump(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def pick_python(explicit: str | None) -> str:
    if explicit:
        return explicit
    venv_python = REPO_ROOT / ".venv" / "bin" / "python"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def latest_by_mtime(paths: Iterable[Path]) -> Path | None:
    items = [p for p in paths if p.exists()]
    if not items:
        return None
    return max(items, key=lambda p: p.stat().st_mtime)


def latest_bundle_tar() -> Path | None:
    candidates = list(REPO_ROOT.glob("metatron_evidence_bundle_*.tar.gz"))
    return latest_by_mtime(candidates)


def latest_arda_timestamp() -> str | None:
    arda_dir = REPO_ROOT / "artifacts" / "evidence" / "arda_prevention"
    if not arda_dir.exists():
        return None
    pattern = re.compile(r"_(\d{8}_\d{6})\.json$")
    stamps: list[tuple[float, str]] = []
    for path in arda_dir.glob("arda_prevention_*.json"):
        match = pattern.search(path.name)
        if not match:
            continue
        stamps.append((path.stat().st_mtime, match.group(1)))
    if not stamps:
        return None
    return max(stamps, key=lambda item: item[0])[1]


def canonical_mitre_ids() -> set[str]:
    path = REPO_ROOT / "backend" / "data" / "generated_mitre_techniques.json"
    if not path.exists():
        return set()
    data = read_json(path)
    if isinstance(data, dict) and isinstance(data.get("techniques"), list):
        return {str(item).strip() for item in data["techniques"] if str(item).strip()}
    return set()


@dataclass
class Stage:
    name: str
    argv: list[str]
    required: bool
    description: str
    outputs: list[str]


def run_stage(stage: Stage, run_dir: Path, env: dict[str, str], dry_run: bool) -> dict[str, Any]:
    started = now_iso()
    start_perf = time.perf_counter()
    stdout_path = run_dir / f"{stage.name}.stdout.log"
    stderr_path = run_dir / f"{stage.name}.stderr.log"
    command_text = shlex.join(stage.argv)

    result: dict[str, Any] = {
        "name": stage.name,
        "description": stage.description,
        "command": command_text,
        "required": stage.required,
        "started_at": started,
        "stdout_log": str(stdout_path.relative_to(REPO_ROOT)),
        "stderr_log": str(stderr_path.relative_to(REPO_ROOT)),
        "outputs": stage.outputs,
    }

    if dry_run:
        stdout_path.write_text(f"DRY-RUN: {command_text}\n", encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")
        result.update(
            {
                "finished_at": now_iso(),
                "duration_sec": 0.0,
                "returncode": None,
                "status": "skipped_dry_run",
            }
        )
        return result

    with stdout_path.open("w", encoding="utf-8") as stdout_handle, stderr_path.open("w", encoding="utf-8") as stderr_handle:
        proc = subprocess.run(stage.argv, cwd=str(REPO_ROOT), env=env, stdout=stdout_handle, stderr=stderr_handle)

    duration = round(time.perf_counter() - start_perf, 3)
    result.update(
        {
            "finished_at": now_iso(),
            "duration_sec": duration,
            "returncode": proc.returncode,
            "status": "ok" if proc.returncode == 0 else ("failed" if stage.required else "failed_nonblocking"),
        }
    )
    return result


def build_stages(args: argparse.Namespace, run_dir: Path, python_bin: str) -> list[Stage]:
    bundle_dir = Path(args.bundle_dir)
    classification_out = run_dir / "metatron_honest_tvr_classification.json"
    summary_out = run_dir / "metatron_public_claim_summary.json"
    sigma_rules_out = run_dir / "sigma_rules_snapshot"
    sigma_matches_out = run_dir / "sigma_matches_snapshot"

    bundle_tar = Path(args.bundle_tar) if args.bundle_tar else latest_bundle_tar()
    arda_timestamp = args.arda_timestamp or latest_arda_timestamp()

    stages: list[Stage] = []

    if args.profile == "full-run":
        stages.append(
            Stage(
                name="arda_prevention",
                argv=[python_bin, "scripts/run_arda_prevention_full_v5.py"],
                required=False,
                description="Run the ARDA prevention sweep to refresh direct kernel prevention evidence.",
                outputs=["artifacts/evidence/arda_prevention"],
            )
        )
        live_argv = [python_bin, "scripts/run_live_telemetry_sweep.py"]
        if not args.include_atomics_in_live_sweep:
            live_argv.append("--skip-atomics")
        if not args.include_amass:
            live_argv.append("--skip-amass")
        if not args.include_purplesharp:
            live_argv.append("--skip-purplesharp")
        stages.append(
            Stage(
                name="live_telemetry_sweep",
                argv=live_argv,
                required=False,
                description="Refresh live telemetry artifacts across running sensors and optional integrations.",
                outputs=["artifacts/live"],
            )
        )
        if args.run_integration_sweep:
            integration_argv = [python_bin, "scripts/run_integration_sweep.py"]
            if args.integration_tools:
                integration_argv.extend(["--tools", args.integration_tools])
            stages.append(
                Stage(
                    name="integration_sweep",
                    argv=integration_argv,
                    required=False,
                    description="Write integration-backed run files and optionally regenerate newly covered TVRs.",
                    outputs=["evidence-bundle/coverage_summary.json"],
                )
            )

    # ── Seraph sensor harvest stages ──────────────────────────────────────────
    # These are non-required: a container that isn't running is skipped
    # gracefully by each harvester. They produce run_*.json files that flow
    # into sigma evaluation and multi-source correlation below.

    stages.append(
        Stage(
            name="falco_evidence_harvest",
            argv=[python_bin, "scripts/harvest_falco_evidence.py",
                  "--out-dir", "artifacts/evidence/falco"],
            required=False,
            description="Harvest Falco BPF kernel-level detections as ATT&CK evidence run files.",
            outputs=["artifacts/evidence/falco"],
        )
    )

    stages.append(
        Stage(
            name="unified_agent_harvest",
            argv=[python_bin, "scripts/harvest_unified_agent_monitors.py",
                  "--out-dir", "artifacts/evidence/unified_agent"],
            required=False,
            description="Harvest all 24 Seraph unified-agent monitor detections as ATT&CK evidence.",
            outputs=["artifacts/evidence/unified_agent"],
        )
    )

    stages.append(
        Stage(
            name="deception_evidence_harvest",
            argv=[python_bin, "scripts/harvest_deception_evidence.py",
                  "--out-dir", "artifacts/evidence/deception"],
            required=False,
            description="Harvest deception-layer events (canaries, honeypots, honey tokens) as ATT&CK evidence.",
            outputs=["artifacts/evidence/deception"],
        )
    )

    stages.append(
        Stage(
            name="seraph_integration_harvest",
            argv=[python_bin, "scripts/seraph_integration_harvest.py"],
            required=False,
            description="Comprehensive Seraph integration harvest: SOAR archive augmentation, ARDA BPF, FleetDM osquery, Arkime, Velociraptor, CAS Shield, and deduction-layer stitching.",
            outputs=["evidence-bundle/integration_evidence"],
        )
    )

    stages.append(
        Stage(
            name="enrich_run_telemetry",
            argv=[python_bin, "scripts/enrich_run_telemetry.py",
                  "--results-dir", "/var/lib/seraph-ai/artifacts/atomic-validation"],
            required=False,
            description="Post-sweep enrichment: write per-run Sigma companion files and network anchor extracts for all real atomic executions.",
            outputs=["/var/lib/seraph-ai/artifacts/atomic-validation"],
        )
    )

    # ── Sigma evaluation ───────────────────────────────────────────────────────
    stages.append(
        Stage(
            name="sigma_against_osquery",
            argv=[python_bin, "scripts/run_sigma_against_osquery.py"],
            required=True,
            description="Evaluate real Sigma rules against the live osquery results log.",
            outputs=[
                "analytics/sigma_matches.json",
                "evidence-bundle/sigma_evaluation_report.json",
            ],
        )
    )

    multi_source_argv = [
        python_bin,
        "scripts/run_multi_source_correlation.py",
        "--bundle",
        str(bundle_dir),
    ]
    if not args.promote_detections:
        multi_source_argv.append("--no-upgrade")
    stages.append(
        Stage(
            name="multi_source_correlation",
            argv=multi_source_argv,
            required=True,
            description="Correlate Falco, Zeek, Suricata, osquery, deception, YARA, and allied telemetry into one detection report.",
            outputs=[str(bundle_dir.relative_to(REPO_ROOT) / "multi_source_detection_report.json")],
        )
    )

    stages.append(
        Stage(
            name="mitre_evidence_correlation",
            argv=[
                python_bin,
                "scripts/build_mitre_evidence_correlation.py",
                "--osquery-log",
                str(bundle_dir / "osqueryd.results.log"),
                "--sigma-matches",
                "analytics/sigma_matches.json",
                "--sigma-eval-report",
                str(bundle_dir / "sigma_evaluation_report.json"),
                "--multi-source-report",
                str(bundle_dir / "multi_source_detection_report.json"),
                "--out",
                str(run_dir / "mitre_evidence_correlation.json"),
            ],
            required=True,
            description="Build the canonical MITRE evidence graph from executions, Sigma, telemetry, and response evidence.",
            outputs=[str((run_dir / "mitre_evidence_correlation.json").relative_to(REPO_ROOT))],
        )
    )

    honest_argv = [
        python_bin,
        "scripts/regenerate_public_evidence_report.py",
        "--classification-out",
        str(classification_out),
        "--summary-out",
        str(summary_out),
        "--sigma-rules-out",
        str(sigma_rules_out),
        "--sigma-matches-out",
        str(sigma_matches_out),
    ]
    if bundle_tar:
        honest_argv.extend(["--bundle", str(bundle_tar)])
    if arda_timestamp:
        honest_argv.extend(["--arda-timestamp", arda_timestamp])
    stages.append(
        Stage(
            name="honest_public_report",
            argv=honest_argv,
            required=False,
            description="Generate an honest classification and public claim summary from the current evidence state.",
            outputs=[
                str(classification_out.relative_to(REPO_ROOT)),
                str(summary_out.relative_to(REPO_ROOT)),
            ],
        )
    )

    reconcile_argv = [
        python_bin,
        "scripts/reconcile_bundle.py",
        "--bundle",
        str(bundle_dir),
    ]
    if not args.allow_reconcile_write:
        reconcile_argv.append("--dry-run")
    stages.append(
        Stage(
            name="reconcile_bundle",
            argv=reconcile_argv,
            required=False,
            description="Validate canonical ATT&CK counts and surface bundle consistency drift.",
            outputs=[str(bundle_dir.relative_to(REPO_ROOT) / "canonical_technique_universe.json")],
        )
    )

    # ── SOAR tier promotion ────────────────────────────────────────────────────
    # Runs last so it sees the final evidence state from all prior stages.
    # Only added to the plan when --promote-detections is set, to keep default
    # runs non-mutating for the TVR promotion tier.
    if args.promote_detections:
        stages.append(
            Stage(
                name="soar_s5_promotions",
                argv=[python_bin, "scripts/run_soar_s5_promotions.py"],
                required=False,
                description="Fire SOAR playbooks against real S5 techniques to generate SOAR-linked evidence and upgrade certification tier.",
                outputs=["artifacts/live"],
            )
        )

    return stages


def analyze_false_flags(classification_path: Path) -> dict[str, Any]:
    if not classification_path.exists():
        return {}

    data = read_json(classification_path)
    techniques = data.get("techniques") or {}
    if not isinstance(techniques, dict):
        return {}

    canonical_ids = canonical_mitre_ids()
    false_counts = Counter()
    mode_false: dict[str, set[str]] = {}
    false_techniques: set[str] = set()

    for tid, rec in techniques.items():
        if not isinstance(rec, dict):
            continue
        evidence = rec.get("evidence") or {}
        if evidence.get("can_certify_platinum") is False:
            false_counts["evidence.can_certify_platinum"] += 1
            false_techniques.add(tid)
        if evidence.get("hard_positives_present") is False:
            false_counts["evidence.hard_positives_present"] += 1
            false_techniques.add(tid)
        for idx, mode in enumerate(evidence.get("evidence_modes") or []):
            if not isinstance(mode, dict):
                continue
            if mode.get("can_certify") is False:
                label = str(mode.get("mode") or f"index:{idx}")
                false_counts[f"evidence.evidence_modes.{label}.can_certify"] += 1
                mode_false.setdefault(label, set()).add(tid)
                false_techniques.add(tid)

    extra_ids = sorted(set(techniques.keys()) - canonical_ids) if canonical_ids else []
    missing_ids = sorted(canonical_ids - set(techniques.keys())) if canonical_ids else []

    return {
        "classification_path": str(classification_path.relative_to(REPO_ROOT)),
        "technique_count": len(techniques),
        "canonical_count": len(canonical_ids),
        "extra_vs_canonical": extra_ids,
        "missing_vs_canonical": missing_ids,
        "techniques_with_any_false": len(false_techniques),
        "false_counts": dict(false_counts),
        "false_by_mode": {mode: sorted(items) for mode, items in sorted(mode_false.items())},
        "platinum_false_techniques": sorted(
            tid
            for tid, rec in techniques.items()
            if isinstance(rec, dict)
            and isinstance(rec.get("evidence"), dict)
            and rec["evidence"].get("can_certify_platinum") is False
        ),
    }


def summarize_outputs(run_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    bundle_dir = Path(args.bundle_dir)
    bundle_sigma = bundle_dir / "sigma_evaluation_report.json"
    multi_source = bundle_dir / "multi_source_detection_report.json"
    correlation = run_dir / "mitre_evidence_correlation.json"
    classification = run_dir / "metatron_honest_tvr_classification.json"
    summary = run_dir / "metatron_public_claim_summary.json"

    key_artifacts = {
        "bundle_dir": str(bundle_dir.relative_to(REPO_ROOT)),
        "sigma_evaluation_report": str(bundle_sigma.relative_to(REPO_ROOT)) if bundle_sigma.exists() else None,
        "multi_source_detection_report": str(multi_source.relative_to(REPO_ROOT)) if multi_source.exists() else None,
        "mitre_evidence_correlation": str(correlation.relative_to(REPO_ROOT)) if correlation.exists() else None,
        "honest_classification": str(classification.relative_to(REPO_ROOT)) if classification.exists() else None,
        "public_summary": str(summary.relative_to(REPO_ROOT)) if summary.exists() else None,
    }

    metrics: dict[str, Any] = {
        "canonical_technique_count_local": len(canonical_mitre_ids()),
    }

    if bundle_sigma.exists():
        data = read_json(bundle_sigma)
        metrics["sigma_detection_technique_count"] = len((data.get("detections_by_technique") or {}).keys())
        metrics["sigma_total_matches"] = int(data.get("total_matches") or 0)

    if multi_source.exists():
        data = read_json(multi_source)
        metrics["multi_source_detection_technique_count"] = len((data.get("detections_by_technique") or {}).keys())
        metrics["multi_source_event_count"] = int(data.get("total_events") or 0)

    if summary.exists():
        data = read_json(summary)
        metrics["observed_k0_count"] = int((data.get("summary") or {}).get("observed_k0") or 0)
        metrics["sigma_rules_packaged"] = int((data.get("summary") or {}).get("sigma_rules_packaged") or 0)
        metrics["sigma_match_records"] = int((data.get("summary") or {}).get("sigma_match_records") or 0)

    false_flag_summary = analyze_false_flags(classification)
    if false_flag_summary:
        metrics["honest_classification_technique_count"] = false_flag_summary.get("technique_count")
        metrics["extra_vs_canonical_count"] = len(false_flag_summary.get("extra_vs_canonical") or [])
        metrics["techniques_with_any_false"] = false_flag_summary.get("techniques_with_any_false")

    claim_boundaries = {
        "observed_evidence": [
            "ARDA kernel EPERM denials",
            "Sigma rules fired against osquery telemetry",
            "Falco BPF kernel-level detections (harvest_falco_evidence)",
            "Unified agent monitor detections across all 24 monitors",
            "Deception layer events: canary, honeypot, honey token",
            "Falco/Zeek/Suricata/YARA/deception detections in multi-source report",
            "SOAR playbook executions (when --promote-detections enabled)",
        ],
        "correlated_evidence": [
            "MITRE evidence correlation joins across executions, osquery, Sigma, and response artifacts",
            "seraph_integration_harvest SOAR archive augmentation + ARDA BPF + FleetDM osquery stitching",
            "TVR analytics updated from multi-source detection report when promotion is explicitly enabled",
            "Per-run Sigma companion files and anchor extracts from enrich_run_telemetry",
        ],
        "support_only_evidence": [
            "Sigma ATT&CK tag coverage without direct firing",
            "osquery query mapping without direct event proof",
            "historical or archive-derived SOAR support without direct run linkage",
        ],
        "pipeline_defaults": {
            "promotion_enabled": bool(args.promote_detections),
            "reconcile_write_enabled": bool(args.allow_reconcile_write),
            "profile": args.profile,
        },
    }

    return {
        "key_artifacts": key_artifacts,
        "metrics": metrics,
        "false_flag_summary": false_flag_summary,
        "claim_boundaries": claim_boundaries,
    }


def write_markdown_summary(run_dir: Path, stage_results: list[dict[str, Any]], summary: dict[str, Any]) -> Path:
    lines = [
        "# Undeniable Evidence Pipeline Summary",
        "",
        "## Stage Results",
        "",
    ]
    for stage in stage_results:
        lines.append(
            f"- {stage['name']}: {stage['status']}"
            f" | required={stage['required']}"
            f" | returncode={stage.get('returncode')}"
            f" | command=`{stage['command']}`"
        )
    lines.extend([
        "",
        "## Metrics",
        "",
    ])
    for key, value in sorted((summary.get("metrics") or {}).items()):
        lines.append(f"- {key}: {value}")

    false_flags = summary.get("false_flag_summary") or {}
    if false_flags:
        lines.extend([
            "",
            "## False Flag Audit",
            "",
            f"- techniques_with_any_false: {false_flags.get('techniques_with_any_false')}",
            f"- extra_vs_canonical: {', '.join(false_flags.get('extra_vs_canonical') or []) or 'none'}",
        ])
        for key, value in sorted((false_flags.get("false_counts") or {}).items()):
            lines.append(f"- {key}: {value}")

    lines.extend([
        "",
        "## Claim Boundaries",
        "",
        "Observed evidence should be used for direct claims.",
        "Correlated evidence supports cross-source narratives.",
        "Support-only evidence should never be promoted as direct proof.",
        "",
    ])
    out = run_dir / "README.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the provenance-first undeniable evidence pipeline for the full Seraph/Metatron stack.\n\n"
        "Stages (integrate-existing profile):\n"
        "  falco_evidence_harvest       → artifacts/evidence/falco\n"
        "  unified_agent_harvest        → artifacts/evidence/unified_agent\n"
        "  deception_evidence_harvest   → artifacts/evidence/deception\n"
        "  seraph_integration_harvest   → evidence-bundle/integration_evidence\n"
        "  enrich_run_telemetry         → per-run sigma + anchor companions\n"
        "  sigma_against_osquery        → analytics/sigma_matches.json\n"
        "  multi_source_correlation     → multi_source_detection_report.json\n"
        "  mitre_evidence_correlation   → artifacts/undeniable_pipeline/<run>/mitre_evidence_correlation.json\n"
        "  honest_public_report         → metatron_honest_tvr_classification.json\n"
        "  reconcile_bundle             → canonical_technique_universe.json (dry-run by default)\n\n"
        "Additional stages in full-run profile:\n"
        "  arda_prevention              → artifacts/evidence/arda_prevention\n"
        "  live_telemetry_sweep         → artifacts/live\n"
        "  integration_sweep (opt-in)   → evidence-bundle/coverage_summary.json\n"
        "  soar_s5_promotions (opt-in)  → artifacts/live (requires --promote-detections)\n",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--profile", choices=["integrate-existing", "full-run"], default="integrate-existing")
    parser.add_argument("--python", default="", help="Python interpreter to use for child scripts.")
    parser.add_argument("--bundle-dir", default=str(DEFAULT_BUNDLE_DIR))
    parser.add_argument("--bundle-tar", default="", help="Tarball used by the honest public report stage.")
    parser.add_argument("--arda-timestamp", default="", help="Specific ARDA evidence timestamp for report regeneration.")
    parser.add_argument("--pipeline-root", default=str(DEFAULT_PIPELINE_ROOT))
    parser.add_argument("--run-id", default="", help="Optional custom run id. Default: UTC timestamp slug.")
    parser.add_argument("--dry-run", action="store_true", help="Record planned stages without executing subprocesses.")
    parser.add_argument("--promote-detections", action="store_true", help="Allow multi-source correlation to update TVRs instead of report-only mode.")
    parser.add_argument("--allow-reconcile-write", action="store_true", help="Allow reconcile_bundle.py to patch the bundle instead of dry-run only.")
    parser.add_argument("--include-atomics-in-live-sweep", action="store_true")
    parser.add_argument("--include-amass", action="store_true")
    parser.add_argument("--include-purplesharp", action="store_true")
    parser.add_argument("--run-integration-sweep", action="store_true")
    parser.add_argument("--integration-tools", default="", help="Optional comma-separated tool list for run_integration_sweep.py.")
    args = parser.parse_args()

    python_bin = pick_python(args.python or None)
    run_id = args.run_id or slug_now()
    run_dir = Path(args.pipeline_root).resolve() / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")

    stages = build_stages(args, run_dir, python_bin)
    stage_results: list[dict[str, Any]] = []

    for stage in stages:
        result = run_stage(stage, run_dir, env, args.dry_run)
        stage_results.append(result)
        if result["status"] == "failed" and stage.required:
            break

    summary = summarize_outputs(run_dir, args)
    readme_path = write_markdown_summary(run_dir, stage_results, summary)

    manifest = {
        "schema": "undeniable_evidence_pipeline.v1",
        "generated_at": now_iso(),
        "run_id": run_id,
        "repo_root": str(REPO_ROOT),
        "profile": args.profile,
        "python": python_bin,
        "stages": stage_results,
        **summary,
        "summary_readme": str(readme_path.relative_to(REPO_ROOT)),
    }
    manifest_path = run_dir / "undeniable_evidence_manifest.json"
    json_dump(manifest_path, manifest)

    print(json.dumps({
        "run_id": run_id,
        "manifest": str(manifest_path),
        "summary_readme": str(readme_path),
        "stages_completed": len(stage_results),
        "last_stage_status": stage_results[-1]["status"] if stage_results else "none",
    }, indent=2))

    return 0 if not any(s["status"] == "failed" for s in stage_results if s["required"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
