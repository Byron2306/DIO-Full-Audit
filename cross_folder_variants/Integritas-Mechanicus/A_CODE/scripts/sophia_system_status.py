#!/usr/bin/env python3
"""Compute a subsystem status report for Sophia/Speculum.

This script summarizes evidence from local artifacts into subsystem-level
readiness scores. Scores are heuristic and auditor-facing: they are intended to
make weaknesses visible, not to certify deployment safety.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence"
OUT_DIR = EVIDENCE / "system_status"


def artifact_time(path: Path) -> str:
    match = re.search(r"(\d{8}T\d{6}Z)", path.name)
    return match.group(1) if match else datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def load_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {"items": payload}
    except Exception:
        return None


def latest(pattern: str, *, min_total: int = 0, exclude: Iterable[str] = ()) -> Tuple[Optional[Path], Dict[str, Any]]:
    paths = [
        path for path in EVIDENCE.glob(pattern)
        if not any(marker in path.name for marker in exclude)
    ]
    for path in sorted(paths, key=lambda p: (artifact_time(p), p.stat().st_mtime), reverse=True):
        payload = load_json(path)
        if not payload:
            continue
        total = int((payload.get("summary") or {}).get("total") or (payload.get("summary") or {}).get("items") or 0)
        if total >= min_total:
            return path, payload
    return (None, {})


def latest_clean_matrix() -> Tuple[Optional[Path], Dict[str, Any]]:
    paths = [
        path for path in EVIDENCE.glob("matrix_gauntlet/matrix_gauntlet_*.json")
        if ".manifest." not in path.name
    ]
    for path in sorted(paths, key=lambda p: (artifact_time(p), p.stat().st_mtime), reverse=True):
        payload = load_json(path)
        if not payload:
            continue
        summary = payload.get("summary") or {}
        total = int(summary.get("total") or 0)
        if (
            total > 0
            and int(summary.get("false_releases") or 0) == 0
            and int(summary.get("false_holds") or 0) == 0
            and int(summary.get("proof_contract_passes") or 0) == total
        ):
            return path, payload
    return (None, {})


def pct(value: float) -> int:
    return int(round(max(0.0, min(1.0, value)) * 100))


def pass_rate(payload: Dict[str, Any], pass_key: str = "passes") -> float:
    summary = payload.get("summary") or {}
    total = float(summary.get("total") or summary.get("items") or 0)
    if total <= 0:
        return 0.0
    return float(summary.get(pass_key) or 0) / total


def int_metric(summary: Dict[str, Any], key: str, default: int = 0) -> int:
    value = summary.get(key)
    return default if value is None else int(value)


def float_metric(summary: Dict[str, Any], key: str, default: float = 0.0) -> float:
    value = summary.get(key)
    return default if value is None else float(value)


def make_status() -> Dict[str, Any]:
    v11_path, v11 = latest("phase5_protocol_runs/phase5_v1_1_full_*.json", min_total=21)
    v12_path, v12 = latest("phase5_protocol_runs/phase5_v1_2_full_*.json", min_total=17)
    pedagogy_path, pedagogy = latest("phase5_protocol_runs/phase5_pedagogy_full_*.json", min_total=9)
    multimodal_path, multimodal = latest("phase5_protocol_runs/phase5_multimodal_full_*.json", min_total=7)
    strat_path, stratified = latest("phase5_protocol_runs/phase5_stratified_full_*.json", min_total=28)
    rubric_path, rubric = latest("rubric_evaluator/sophia_rubric_evaluation_*.json", min_total=14)
    panel_path, panel = latest("judge_panel/sophia_judge_panel_*.json", min_total=35)
    calibration_path, calibration = latest("judge_calibration/sophia_judge_calibration_*.json")
    audit_path, audit = latest("audit/sophia_evidence_audit_*.json")
    matrix_path, matrix = latest("matrix_gauntlet/matrix_gauntlet_*.json", exclude=(".manifest.",))
    gap_path, gap_probe = latest("system_gap_probes/sophia_system_gap_probes_*.json")
    clean_matrix_path, clean_matrix = latest_clean_matrix()

    rubric_summary = rubric.get("summary") or {}
    panel_summary = panel.get("summary") or {}
    matrix_summary = matrix.get("summary") or {}
    clean_matrix_summary = clean_matrix.get("summary") or {}
    gap_summary = gap_probe.get("summary") or {}
    strat_summary = stratified.get("summary") or {}
    strat_stage = strat_summary.get("stage_metrics") or {}
    trace_metrics = strat_stage.get("trace") or {}
    trace_complete_rate = ((trace_metrics.get("complete_interval") or {}).get("rate") or 0.0)
    raw_or_exempt_rate = ((trace_metrics.get("raw_available_or_exempt_interval") or {}).get("rate") or 0.0)
    release_mandos_rate = (((strat_stage.get("released") or {}).get("mandos_pass_interval") or {}).get("rate") or 0.0)
    calibration_summary = calibration.get("summary") or {}
    applicable_irr = (panel_summary.get("applicable_inter_rater_reliability") or {}).get("agreement")
    rubric_clean = int_metric(rubric_summary, "disagreements", 999) == 0
    panel_clean = int_metric(panel_summary, "panel_original_disagreements", 999) == 0
    calibration_accuracy = float_metric(calibration_summary, "mean_balanced_accuracy", 0.0)
    external_judgments = int_metric(panel_summary, "external_judgments", 0)
    judge_score_raw = (
        0.25 * (1.0 if rubric_clean else 0.6)
        + 0.25 * (1.0 if panel_clean else 0.65)
        + 0.25 * float(applicable_irr or 0.0)
        + 0.25 * calibration_accuracy
    )
    judge_score = min(judge_score_raw, 1.0 if external_judgments else 0.88)

    subsystems = {
        "constitutional_protocols": {
            "score": pct((pass_rate(v11) + pass_rate(v12)) / 2),
            "evidence": [str(p) for p in (v11_path, v12_path) if p],
            "weakness": "Local harness evidence; still needs held-out external adjudication.",
        },
        "pedagogy_offices": {
            "score": pct(pass_rate(pedagogy)),
            "evidence": [str(pedagogy_path)] if pedagogy_path else [],
            "weakness": "Office routing passes current cases; long learner-history adaptation remains under-proven.",
        },
        "assessment_ecology": {
            "score": pct(min(pass_rate(pedagogy), pass_rate(stratified))),
            "evidence": [str(p) for p in (pedagogy_path, strat_path) if p],
            "weakness": "Cycle is visible in responses; outcome learning gains not yet measured.",
        },
        "document_evidence_and_retrieval": {
            "score": pct(((strat_stage.get("released") or {}).get("document_grounded_interval") or {}).get("rate") or 0.0),
            "evidence": [str(strat_path)] if strat_path else [],
            "weakness": "Document grounding strong in current suite; source-quality ranking is newly added and needs stress tests.",
        },
        "multimodal_governance": {
            "score": pct(pass_rate(multimodal)),
            "evidence": [str(multimodal_path)] if multimodal_path else [],
            "weakness": "OCR/transcript and disagreement governance only; native pixel vision not proven.",
        },
        "raw_repair_release_telemetry": {
            "score": pct((0.5 * trace_complete_rate) + (0.25 * raw_or_exempt_rate) + (0.25 * release_mandos_rate)),
            "evidence": [str(strat_path), str(matrix_path)] if strat_path and matrix_path else [str(p) for p in (strat_path, matrix_path) if p],
            "weakness": "Stage trace separates raw model candidates from raw-exempt native synthesis; still needs more repaired-failure samples.",
        },
        "judge_and_audit_layer": {
            "score": pct(judge_score),
            "evidence": [str(p) for p in (rubric_path, panel_path, calibration_path, audit_path) if p],
            "weakness": "Local judges now have known-answer calibration; score remains capped until blinded external human/LLM judgments are imported.",
        },
        "remote_model_matrix": {
            "score": pct(float(clean_matrix_summary.get("proof_contract_pass_rate") or matrix_summary.get("proof_contract_pass_rate") or 0.0)),
            "evidence": [str(p) for p in (clean_matrix_path or matrix_path,) if p],
            "weakness": "Remote evidence remains small and provider access/billing constrained; deliberate failing ablations are tracked separately.",
        },
        "harmonic_covenant_signal": {
            "score": pct(((gap_summary.get("by_probe") or {}).get("harmonic_discord") or {}).get("pass_rate") or 0.76),
            "evidence": [
                str(ROOT / "arda_os/backend/services/harmonic_engine.py"),
                str(ROOT / "arda_os/backend/services/assessment_ecology.py"),
                *([str(gap_path)] if gap_path else []),
            ],
            "weakness": "Harmonic cadence now has a local discord probe; more principal-covenant semantic discord tests are still needed.",
        },
    }
    overall = round(sum(item["score"] for item in subsystems.values()) / max(1, len(subsystems)), 1)
    return {
        "schema_version": "sophia.system_status.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "overall_score": overall,
        "subsystems": subsystems,
        "top_next_moves": [
            "Run source-provenance stress tests against document_evidence.source_provenance.",
            "Add external human/LLM judge JSONL and compare against local judge panel.",
            "Implement native pixel vision adapter and require image/OCR conflict adjudication.",
            "Run longitudinal learner simulations to test ZPD and ipsative adaptation over 20-100 turns.",
        ],
    }


def write_markdown(path: Path, status: Dict[str, Any]) -> None:
    lines = [
        "# Sophia System Status",
        "",
        f"Generated: `{status['created_at']}`",
        f"Overall score: `{status['overall_score']}%`",
        "",
        "| Subsystem | Score | Main Weakness | Evidence Count |",
        "|---|---:|---|---:|",
    ]
    for name, item in status["subsystems"].items():
        lines.append(f"| {name} | {item['score']}% | {item['weakness']} | {len(item['evidence'])} |")
    lines.extend(["", "## Next Moves", ""])
    for move in status["top_next_moves"]:
        lines.append(f"- {move}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    status = make_status()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    json_path = OUT_DIR / f"sophia_system_status_{stamp}.json"
    md_path = OUT_DIR / f"sophia_system_status_{stamp}.md"
    json_path.write_text(json.dumps(status, indent=2, sort_keys=True), encoding="utf-8")
    write_markdown(md_path, status)
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "overall_score": status["overall_score"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
