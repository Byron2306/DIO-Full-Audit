#!/usr/bin/env python3
"""Run and package Sophia's current academic proof gauntlet."""

from __future__ import annotations

import argparse
import csv
import json
import math
import subprocess
import sys
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence"


SUITES = [
    ("phase1_smoke", ["scripts/sophia_writing_desk_phase1_smoke.py", "--out", "evidence/sophia_writing_desk_phase1_smoke_latest.json"]),
    ("phase2_annotations", ["scripts/sophia_writing_desk_phase2_annotations.py", "--out", "evidence/sophia_writing_desk_phase2_annotations_latest.json"]),
    ("phase3_source_support", ["scripts/sophia_writing_desk_phase3_source_support.py", "--out", "evidence/sophia_writing_desk_phase3_source_support_latest.json"]),
    ("phase4_project_store", ["scripts/sophia_writing_desk_phase4_project_store.py", "--out", "evidence/sophia_writing_desk_phase4_project_store_latest.json"]),
    ("phase5_pedagogy", ["scripts/sophia_writing_desk_phase5_pedagogy.py", "--out", "evidence/sophia_writing_desk_phase5_pedagogy_latest.json"]),
    ("phase5_adaptation", ["scripts/sophia_writing_desk_phase5_adaptation_suite.py", "--limit", "100", "--out", "evidence/sophia_writing_desk_phase5_adaptation_suite_latest.json"]),
    ("phase6_similarity", ["scripts/sophia_writing_desk_phase6_similarity_suite.py", "--out", "evidence/sophia_writing_desk_phase6_similarity_latest.json"]),
    ("phase6_provenance_integrity", ["scripts/sophia_phase6_provenance_integrity_hardening.py", "--out", "evidence/sophia_phase6_provenance_integrity_hardening_latest.json"]),
    ("evidence_engine", ["scripts/sophia_evidence_engine_slice1.py", "--out", "evidence/sophia_evidence_engine_slice1_latest.json"]),
    ("phase7_document_inspection", ["scripts/sophia_writing_desk_phase7_document_inspection.py", "--out", "evidence/sophia_writing_desk_phase7_document_inspection_latest.json"]),
    ("phase7_completion", ["scripts/sophia_writing_desk_phase7_completion_suite.py", "--out", "evidence/sophia_writing_desk_phase7_completion_latest.json"]),
    ("phase7_multimodal_disagreement", ["scripts/sophia_phase7_multimodal_disagreement_gates.py", "--out", "evidence/sophia_phase7_multimodal_disagreement_gates_latest.json"]),
    ("native_vision_pdfplumber", ["scripts/sophia_native_vision_pdfplumber_setup.py", "--out", "evidence/sophia_native_vision_pdfplumber_setup_latest.json"]),
    ("academic_claim_quality", ["scripts/sophia_academic_claim_quality_suite.py", "--out", "evidence/sophia_academic_claim_quality_latest.json"]),
    ("response_quality_review", ["scripts/sophia_response_quality_review_suite.py", "--out", "evidence/sophia_response_quality_review_latest.json"]),
    ("human_rater_workflow", ["scripts/sophia_human_rater_workflow_suite.py", "--out", "evidence/sophia_human_rater_workflow_latest.json"]),
    ("phase78_ui_static", ["scripts/sophia_writing_desk_phase78_ui_static.py", "--out", "evidence/sophia_writing_desk_phase78_ui_static_latest.json"]),
    ("phase8_integrity_record", ["scripts/sophia_writing_desk_phase8_integrity_record.py", "--out", "evidence/sophia_writing_desk_phase8_integrity_record_latest.json"]),
    ("contrastive_baseline", ["scripts/sophia_contrastive_baseline_mini_suite.py", "--out", "evidence/sophia_contrastive_baseline_latest.json"]),
    ("hf_nli_support", ["scripts/sophia_hf_nli_support_suite.py", "--out", "evidence/sophia_hf_nli_support_latest.json"]),
]


REPORT_FILES = [
    "evidence/SOPHIA_WORLD_CLASS_WRITING_DESK_IMPLEMENTATION_PLAN_20260802T155106Z.md",
    "evidence/SOPHIA_PHASE6_SIMILARITY_SIDE_BY_SIDE_PUSH_20260803T031305Z.md",
    "evidence/SOPHIA_PHASE7_DOCUMENT_INSPECTION_PUSH_20260803T032036Z.md",
    "evidence/SOPHIA_NEURAL_EVIDENCE_ENGINE_SLICE1_20260803T033247Z.md",
    "evidence/SOPHIA_PHASE6_PHASE7_COMPLETION_PUSH_20260803T034153Z.md",
    "evidence/SOPHIA_PHASE7_PHASE8_COMPLETION_PUSH_20260803T034719Z.md",
    "evidence/SOPHIA_NATIVE_VISION_PDFPLUMBER_SETUP_20260803T035449Z.md",
    "evidence/SOPHIA_PHASE7_PHASE8_UI_USABILITY_PUSH_20260803T040001Z.md",
    "evidence/SOPHIA_PHASE8_REVIEWER_RESEARCH_EXPORT_PUSH_20260803T044940Z.md",
    "evidence/SOPHIA_FINAL_SYSTEM_BREAKDOWN_ASSESSMENT_20260731T1815Z.md",
    "evidence/SOPHIA_THREE_RUN_ACADEMIC_MATRIX_COMPARISON_20260731T1745Z.md",
]


def _run_suite(name: str, cmd: List[str], *, skip_live: bool = False) -> Dict[str, Any]:
    if skip_live and name == "native_vision_pdfplumber":
        cmd = [cmd[0], "--out", cmd[-1]]
    proc = subprocess.run(
        [str(ROOT / ".venv" / "bin" / "python"), *cmd],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "name": name,
        "cmd": " ".join(cmd),
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout": proc.stdout.strip()[-2000:],
        "stderr": proc.stderr.strip()[-2000:],
    }


def _load_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _extract_summary(path: Path) -> Dict[str, Any]:
    data = _load_json(path) or {}
    summary = data.get("summary") or {}
    if "passed" in summary and "total" in summary:
        return {"passed": summary.get("passed"), "total": summary.get("total"), "pass_rate": summary.get("pass_rate")}
    if "failed" in summary and "total" in summary:
        total = int(summary.get("total") or 0)
        failed = int(summary.get("failed") or 0)
        passed = total - failed
        return {"passed": passed, "total": total, "pass_rate": round(passed / total, 4) if total else 0}
    return summary


def _candidate_rater_files() -> List[Path]:
    return [
        path for path in EVIDENCE.rglob("*.csv")
        if any(token in path.name.lower() for token in ("rater", "rating", "human_judgment", "evaluator"))
    ]


def _fleiss_kappa(rows: List[List[str]]) -> Optional[float]:
    complete = [row for row in rows if len(row) >= 2 and all(cell != "" for cell in row)]
    if not complete:
        return None
    n_raters = len(complete[0])
    if n_raters < 2 or any(len(row) != n_raters for row in complete):
        return None
    categories = sorted({cell for row in complete for cell in row})
    if len(categories) < 2:
        return None
    n_items = len(complete)
    p_i = []
    category_totals = Counter()
    for row in complete:
        counts = Counter(row)
        category_totals.update(counts)
        p_i.append((sum(count * count for count in counts.values()) - n_raters) / (n_raters * (n_raters - 1)))
    p_bar = sum(p_i) / n_items
    total_ratings = n_items * n_raters
    p_e = sum((category_totals[cat] / total_ratings) ** 2 for cat in categories)
    if math.isclose(1.0, p_e):
        return None
    return round((p_bar - p_e) / (1 - p_e), 4)


def _reliability_report() -> Dict[str, Any]:
    candidates = _candidate_rater_files()
    analyses = []
    rating_columns = {
        "boundary_integrity_1_5",
        "lawful_helpfulness_1_5",
        "source_grounding_1_5",
        "user_ownership_1_5",
        "overall_pass_y_n",
        "source_support_1_5",
        "authorship_preservation_1_5",
        "warrant_quality_1_5",
        "limitation_quality_1_5",
        "risk_of_substitution_1_5",
        "specificity_1_5",
        "pedagogical_quality_1_5",
        "uncertainty_calibration_1_5",
        "constitutional_leakage_y_n",
        "substitution_risk_y_n",
    }
    for path in candidates:
        try:
            rows = list(csv.DictReader(path.open(encoding="utf-8", errors="ignore")))
        except Exception as exc:
            analyses.append({"path": str(path), "status": "read_error", "error": str(exc)})
            continue
        if rows and {"item_id", "rater_id"}.issubset(set(rows[0].keys())):
            try:
                from scripts.sophia_human_rater_workflow import analyze_packet
                report = analyze_packet(path)
                analyses.append({
                    "path": str(path.relative_to(ROOT)),
                    "status": report.get("status"),
                    "rows": len(rows),
                    "format": "long_form_item_rater",
                    "rating_columns": report.get("rating_columns"),
                    "reason": (
                        "Reliability is computable when at least two completed rater rows exist per item."
                        if report.get("status") != "computable"
                        else "Completed long-form rater responses were available."
                    ),
                })
                continue
            except Exception as exc:
                analyses.append({"path": str(path.relative_to(ROOT)), "status": "long_form_analysis_error", "error": str(exc)})
                continue
        present = [col for col in (rows[0].keys() if rows else []) if col in rating_columns]
        filled = {
            col: sum(1 for row in rows if str(row.get(col) or "").strip())
            for col in present
        }
        analyses.append({
            "path": str(path.relative_to(ROOT)),
            "status": "template_or_partial" if not any(filled.values()) else "ratings_present_unpaired",
            "rows": len(rows),
            "rating_columns": present,
            "filled_rating_cells": filled,
            "kappa": None,
            "reason": "Need at least two completed rater columns per item with aligned rater IDs to compute inter-rater reliability.",
        })
    return {
        "status": "not_computable_without_completed_rater_responses",
        "candidate_files": len(candidates),
        "analyses": analyses,
    }


def _write_markdown_report(artifact: Dict[str, Any], path: Path) -> None:
    lines = [
        "# Sophia Full Academic Proof Gauntlet",
        "",
        f"Generated: {artifact['timestamp']}",
        f"Bundle: `{artifact['bundle_path']}`",
        "",
        "## Suite Results",
        "",
        "| Suite | Passed | Return code | Summary |",
        "|---|---:|---:|---|",
    ]
    for row in artifact["suite_results"]:
        summary = artifact["artifact_summaries"].get(row["name"], {})
        lines.append(f"| {row['name']} | {row['passed']} | {row['returncode']} | `{json.dumps(summary, sort_keys=True)}` |")
    lines.extend([
        "",
        "## Reliability",
        "",
        f"Status: `{artifact['reliability']['status']}`",
        "",
        "Inter-rater reliability was not computed because completed, aligned rater-response files were not present. This is an honest absence, not a failed score.",
        "",
        "## Included Evidence",
        "",
    ])
    for item in artifact["included_files"]:
        lines.append(f"- `{item}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(*, skip_live: bool = False) -> Dict[str, Any]:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = EVIDENCE / "full_academic_proof_gauntlet"
    out_dir.mkdir(parents=True, exist_ok=True)
    suite_results = [_run_suite(name, cmd, skip_live=skip_live) for name, cmd in SUITES]
    artifact_paths = [
        EVIDENCE / "sophia_writing_desk_phase1_smoke_latest.json",
        EVIDENCE / "sophia_writing_desk_phase2_annotations_latest.json",
        EVIDENCE / "sophia_writing_desk_phase3_source_support_latest.json",
        EVIDENCE / "sophia_writing_desk_phase4_project_store_latest.json",
        EVIDENCE / "sophia_writing_desk_phase5_pedagogy_latest.json",
        EVIDENCE / "sophia_writing_desk_phase5_adaptation_suite_latest.json",
        EVIDENCE / "sophia_writing_desk_phase6_similarity_latest.json",
        EVIDENCE / "sophia_phase6_provenance_integrity_hardening_latest.json",
        EVIDENCE / "sophia_evidence_engine_slice1_latest.json",
        EVIDENCE / "sophia_writing_desk_phase7_document_inspection_latest.json",
        EVIDENCE / "sophia_writing_desk_phase7_completion_latest.json",
        EVIDENCE / "sophia_phase7_multimodal_disagreement_gates_latest.json",
        EVIDENCE / "sophia_native_vision_pdfplumber_setup_latest.json",
        EVIDENCE / "sophia_academic_claim_quality_latest.json",
        EVIDENCE / "sophia_response_quality_review_latest.json",
        EVIDENCE / "sophia_human_rater_workflow_latest.json",
        EVIDENCE / "sophia_writing_desk_phase78_ui_static_latest.json",
        EVIDENCE / "sophia_writing_desk_phase8_integrity_record_latest.json",
        EVIDENCE / "sophia_contrastive_baseline_latest.json",
        EVIDENCE / "sophia_hf_nli_support_latest.json",
        EVIDENCE / "human_rater" / "sophia_human_rater_packet_latest.csv",
        EVIDENCE / "human_rater" / "sophia_human_rater_packet_latest_key.json",
        EVIDENCE / "human_rater" / "sophia_human_rater_packet_latest_instructions.md",
        EVIDENCE / "protocol_v1_2_human_judgment_instructions_2026-04-09.md",
        EVIDENCE / "protocol_v1_2_human_judgment_key_2026-04-09.json",
        EVIDENCE / "protocol_v1_2_human_judgment_packet_2026-04-09.csv",
    ]
    artifact_summaries = {
        result["name"]: _extract_summary(path)
        for result, path in zip(suite_results, artifact_paths)
        if path.exists()
    }
    included_files = [str(path.relative_to(ROOT)) for path in artifact_paths if path.exists()]
    included_files.extend(path for path in REPORT_FILES if (ROOT / path).exists())
    reliability = _reliability_report()
    bundle_path = EVIDENCE / f"SOPHIA_FULL_ACADEMIC_PROOF_GAUNTLET_{timestamp}.zip"
    artifact = {
        "schema_version": "sophia.full_academic_proof_gauntlet.v1",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "suite_results": suite_results,
        "artifact_summaries": artifact_summaries,
        "reliability": reliability,
        "included_files": included_files,
        "bundle_path": str(bundle_path.relative_to(ROOT)),
        "overall_passed": all(row["passed"] for row in suite_results),
    }
    json_path = out_dir / f"sophia_full_academic_proof_gauntlet_{timestamp}.json"
    md_path = out_dir / f"SOPHIA_FULL_ACADEMIC_PROOF_GAUNTLET_{timestamp}.md"
    json_path.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    artifact["included_files"].extend([str(json_path.relative_to(ROOT)), str(md_path.relative_to(ROOT))])
    artifact["bundle_path"] = str(bundle_path.relative_to(ROOT))
    _write_markdown_report(artifact, md_path)
    json_path.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for rel in artifact["included_files"]:
            path = ROOT / rel
            if path.exists() and path.is_file():
                zf.write(path, rel)
    return artifact


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-live", action="store_true", help="Do not require live remote probes.")
    args = parser.parse_args()
    artifact = run(skip_live=args.skip_live)
    print(json.dumps({
        "overall_passed": artifact["overall_passed"],
        "suite_count": len(artifact["suite_results"]),
        "bundle_path": artifact["bundle_path"],
        "reliability_status": artifact["reliability"]["status"],
    }, indent=2))
    return 0 if artifact["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
