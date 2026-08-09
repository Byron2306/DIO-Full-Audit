#!/usr/bin/env python3
"""Compile Sophia evidence artifacts into an auditor-facing assessment.

This script does not run Sophia. It audits artifacts already produced by the
protocol harness, matrix gauntlet, Mandos red-team, provider probes, and rubric
evaluator. Its purpose is to preserve negative evidence and prevent small clean
runs from being overstated.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence"
OUT_DIR = EVIDENCE / "audit"


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def load_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {"items": payload}
    except Exception:
        return None


def wilson_interval(successes: int, total: int, z: float = 1.96) -> Dict[str, Any]:
    """Return Wilson score interval for a binomial proportion."""
    if total <= 0:
        return {"successes": successes, "total": total, "rate": None, "ci95_low": None, "ci95_high": None}
    phat = successes / total
    denom = 1 + z * z / total
    centre = phat + z * z / (2 * total)
    margin = z * math.sqrt((phat * (1 - phat) + z * z / (4 * total)) / total)
    return {
        "successes": successes,
        "total": total,
        "rate": round(phat, 4),
        "ci95_low": round(max(0.0, (centre - margin) / denom), 4),
        "ci95_high": round(min(1.0, (centre + margin) / denom), 4),
    }


def artifact_time(path: Path) -> str:
    match = re.search(r"(\d{8}T\d{6}Z)", path.name)
    if match:
        return match.group(1)
    return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def latest_artifact(
    pattern: str,
    *,
    min_total: int = 0,
    exclude_name_contains: Iterable[str] = (),
) -> Optional[Tuple[Path, Dict[str, Any]]]:
    candidates = [
        path
        for path in EVIDENCE.glob(pattern)
        if not any(marker in path.name for marker in exclude_name_contains)
    ]
    candidates = sorted(candidates, key=lambda p: (artifact_time(p), p.stat().st_mtime))
    fallback: Optional[Tuple[Path, Dict[str, Any]]] = None
    for path in reversed(candidates):
        payload = load_json(path)
        if payload is None:
            continue
        if fallback is None:
            fallback = (path, payload)
        summary = payload.get("summary") or {}
        total = int(summary.get("total") or 0)
        if total >= min_total:
            return path, payload
    return fallback


def collect_protocol_runs() -> Dict[str, Any]:
    suites = {
        "protocol_1_1": ("phase5_protocol_runs/phase5_v1_1_full_*.json", 21),
        "protocol_1_2": ("phase5_protocol_runs/phase5_v1_2_full_*.json", 17),
        "mutations": ("phase5_protocol_runs/phase5_mutations_full_*.json", 12),
        "multimodal": ("phase5_protocol_runs/phase5_multimodal_full_*.json", 5),
        "pedagogy": ("phase5_protocol_runs/phase5_pedagogy_full_*.json", 9),
    }
    out: Dict[str, Any] = {}
    for suite, (pattern, min_total) in suites.items():
        found = latest_artifact(pattern, min_total=min_total)
        if not found:
            out[suite] = {"status": "missing"}
            continue
        path, payload = found
        summary = payload.get("summary") or {}
        total = int(summary.get("total") or 0)
        passes = int(summary.get("passes") or 0)
        out[suite] = {
            "status": "present",
            "artifact": str(path),
            "created_at": payload.get("created_at"),
            "summary": summary,
            "pass_interval": wilson_interval(passes, total),
            "claim_strength": claim_strength(passes, total),
        }
    return out


def collect_negative_protocol_runs() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for path in sorted((EVIDENCE / "phase5_protocol_runs").glob("*.json")):
        payload = load_json(path)
        if not payload:
            continue
        summary = payload.get("summary") or {}
        total = int(summary.get("total") or 0)
        passes = int(summary.get("passes") or 0)
        if total and passes < total:
            rows.append({
                "artifact": str(path),
                "suite": payload.get("suite") or infer_suite(path.name),
                "created_at": payload.get("created_at"),
                "summary": summary,
                "failure_count": total - passes,
            })
    return rows[-20:]


def infer_suite(name: str) -> str:
    for suite in ("v1_1", "v1_2", "mutations", "multimodal", "pedagogy"):
        if suite in name:
            return suite
    return "unknown"


def collect_rubric() -> Dict[str, Any]:
    found = latest_artifact("rubric_evaluator/sophia_rubric_evaluation_*.json")
    if not found:
        return {"status": "missing"}
    path, payload = found
    summary = payload.get("summary") or {}
    total = int(summary.get("total") or 0)
    passes = int(summary.get("rubric_passes") or 0)
    disagreements = int(summary.get("disagreements") or 0)
    return {
        "status": "present",
        "artifact": str(path),
        "summary": summary,
        "rubric_pass_interval": wilson_interval(passes, total),
        "agreement_interval": wilson_interval(total - disagreements, total),
        "claim_strength": claim_strength(passes, total),
    }


def collect_mandos_redteam() -> Dict[str, Any]:
    found = latest_artifact("mandos_checker_redteam/mandos_checker_redteam_*.json")
    if not found:
        return {"status": "missing"}
    path, payload = found
    summary = payload.get("summary") or payload
    total = int(summary.get("total") or 0)
    false_passes = int(summary.get("false_passes") or 0)
    false_fails = int(summary.get("false_fails") or 0)
    correct = max(0, total - false_passes - false_fails)
    return {
        "status": "present",
        "artifact": str(path),
        "summary": summary,
        "correctness_interval": wilson_interval(correct, total),
        "false_pass_interval": wilson_interval(false_passes, total),
    }


def collect_matrix() -> Dict[str, Any]:
    found = latest_artifact("matrix_gauntlet/matrix_gauntlet_*.json", exclude_name_contains=(".manifest.",))
    if not found:
        return {"status": "missing"}
    path, payload = found
    summary = payload.get("summary") or {}
    total = int(summary.get("total") or 0)
    passes = int(summary.get("proof_contract_passes") or 0)
    false_releases = int(summary.get("false_releases") or 0)
    return {
        "status": "present",
        "artifact": str(path),
        "matrix_id": payload.get("matrix_id"),
        "protocol": payload.get("protocol") or {},
        "summary": summary,
        "contract_interval": wilson_interval(passes, total),
        "false_release_interval": wilson_interval(false_releases, total),
        "claim_strength": claim_strength(passes, total),
    }


def collect_provider_probe() -> Dict[str, Any]:
    probes = []
    for path in sorted((EVIDENCE / "provider_probe").glob("*.json")):
        payload = load_json(path)
        if payload is None:
            continue
        items = payload.get("items") if isinstance(payload.get("items"), list) else payload
        if isinstance(items, dict):
            items = items.get("results") or [items]
        if not isinstance(items, list):
            items = []
        ok = sum(1 for item in items if isinstance(item, dict) and item.get("ok"))
        total = sum(1 for item in items if isinstance(item, dict))
        probes.append({
            "artifact": str(path),
            "total": total,
            "ok": ok,
            "ok_interval": wilson_interval(ok, total),
        })
    return {"status": "present" if probes else "missing", "artifacts": probes}


def collect_judge_panel() -> Dict[str, Any]:
    found = latest_artifact("judge_panel/sophia_judge_panel_*.json")
    if not found:
        return {"status": "missing"}
    path, payload = found
    summary = payload.get("summary") or {}
    return {
        "status": "present",
        "artifact": str(path),
        "summary": summary,
        "panel_agreement": (summary.get("inter_rater_reliability") or {}).get("agreement"),
        "applicable_panel_agreement": (summary.get("applicable_inter_rater_reliability") or {}).get("agreement"),
        "panel_original_disagreements": summary.get("panel_original_disagreements"),
    }


def claim_strength(successes: int, total: int) -> str:
    """Conservative evidence language based on N and observed failures."""
    if total <= 0:
        return "missing"
    if successes < total:
        return "mixed"
    if total < 10:
        return "clean_micro_probe"
    if total < 30:
        return "clean_engineering_gate"
    if total < 100:
        return "clean_moderate_gate"
    return "clean_large_gate"


def overall_claims(audit: Dict[str, Any]) -> Dict[str, Any]:
    protocol = audit["protocol_runs"]
    rubric = audit["rubric_evaluator"]
    matrix = audit["matrix_gauntlet"]
    return {
        "defensible_primary_claim": (
            "Sophia currently demonstrates controlled, auditable, authorship-preserving academic assistance "
            "under local protocol harnesses, with independent deterministic rubric agreement on the latest "
            "multimodal and pedagogy artifacts."
        ),
        "overclaim_to_avoid": (
            "Do not claim universal policy invalidation, native multimodal competence, classroom learning gains, "
            "or broad provider-agnostic safety from the current evidence alone."
        ),
        "publication_readiness": {
            "engineering_case_study": readiness_score(protocol, rubric, matrix),
            "peer_reviewed_outcomes_claim": "not_ready_without_large_n_blinded_and_longitudinal_study",
        },
    }


def readiness_score(protocol: Dict[str, Any], rubric: Dict[str, Any], matrix: Dict[str, Any]) -> str:
    required = ["protocol_1_1", "protocol_1_2", "pedagogy", "multimodal"]
    clean_required = all((protocol.get(key) or {}).get("summary", {}).get("pass_rate") == 1.0 for key in required)
    rubric_clean = (rubric.get("summary") or {}).get("disagreements") == 0
    if clean_required and rubric_clean:
        if (matrix.get("summary") or {}).get("total", 0) >= 30:
            return "strong_with_limited_external_validity"
        return "credible_but_small_n"
    return "not_ready"


def write_markdown(path: Path, audit: Dict[str, Any]) -> None:
    lines: List[str] = [
        "# Sophia Evidence Audit",
        "",
        f"Generated: `{audit['generated_at']}`",
        f"Repository: `{ROOT}`",
        "",
        "## Bottom Line",
        "",
        audit["claims"]["defensible_primary_claim"],
        "",
        f"Overclaim to avoid: {audit['claims']['overclaim_to_avoid']}",
        "",
        f"Engineering case-study readiness: `{audit['claims']['publication_readiness']['engineering_case_study']}`",
        f"Outcomes-claim readiness: `{audit['claims']['publication_readiness']['peer_reviewed_outcomes_claim']}`",
        "",
        "## Latest Protocol Gates",
        "",
        "| Gate | Passes | Total | Rate | 95% Wilson CI | Claim Strength | Artifact |",
        "|---|---:|---:|---:|---|---|---|",
    ]
    for gate, row in audit["protocol_runs"].items():
        summary = row.get("summary") or {}
        interval = row.get("pass_interval") or {}
        artifact = row.get("artifact") or ""
        artifact_name = Path(artifact).name if artifact else "missing"
        lines.append(
            f"| {gate} | {summary.get('passes', '')} | {summary.get('total', '')} | "
            f"{summary.get('pass_rate', '')} | {interval.get('ci95_low')} to {interval.get('ci95_high')} | "
            f"{row.get('claim_strength')} | `{artifact_name}` |"
        )
    lines.extend([
        "",
        "## Independent Evaluators",
        "",
    ])
    rubric = audit["rubric_evaluator"]
    lines.append(
        f"- Rubric evaluator: `{json.dumps(rubric.get('summary', {}), sort_keys=True)}`; "
        f"claim strength `{rubric.get('claim_strength')}`."
    )
    mandos = audit["mandos_redteam"]
    lines.append(f"- Mandos red-team: `{json.dumps(mandos.get('summary', {}), sort_keys=True)}`.")
    panel = audit.get("judge_panel") or {}
    lines.append(f"- Judge panel: `{json.dumps(panel.get('summary', {}), sort_keys=True)}`.")
    matrix = audit["matrix_gauntlet"]
    lines.extend([
        "",
        "## Remote / Matrix Evidence",
        "",
        f"- Latest matrix artifact: `{Path(matrix.get('artifact', '')).name if matrix.get('artifact') else 'missing'}`.",
        f"- Latest matrix summary: `{json.dumps(matrix.get('summary', {}), sort_keys=True)}`.",
        f"- Matrix claim strength: `{matrix.get('claim_strength')}`.",
        "",
        "## Negative Evidence Preserved",
        "",
    ])
    negative = audit["negative_protocol_runs"]
    if not negative:
        lines.append("- No failing protocol artifacts were found.")
    else:
        for row in negative:
            lines.append(
                f"- `{Path(row['artifact']).name}`: suite `{row.get('suite')}`, "
                f"failures `{row.get('failure_count')}`, summary `{json.dumps(row.get('summary', {}), sort_keys=True)}`."
            )
    lines.extend([
        "",
        "## Methodological Limits",
        "",
        "- Wilson intervals are intentionally conservative reminders that 100% on small N is not universal proof.",
        "- OCR/transcript-mediated multimodal tests do not prove native vision.",
        "- Deterministic judges are useful witnesses but not replacements for blinded expert raters.",
        "- Remote provider evidence remains small and affected by provider access/billing constraints.",
        "- Longitudinal learner adaptation and real classroom outcomes remain unproven.",
        "",
        "## Next Evidence Standard",
        "",
        "- Freeze held-out cases before development.",
        "- Run larger stratified suites with raw/repaired/released metrics separated.",
        "- Add blinded human and LLM-judge panels with inter-rater reliability.",
        "- Add native multimodal tests with OCR disagreement cases.",
        "- Add longitudinal learner simulations and learner-artifact outcome measures.",
    ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = parser.parse_args()

    audit: Dict[str, Any] = {
        "schema_version": "sophia.evidence_audit.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "protocol_runs": collect_protocol_runs(),
        "negative_protocol_runs": collect_negative_protocol_runs(),
        "rubric_evaluator": collect_rubric(),
        "mandos_redteam": collect_mandos_redteam(),
        "matrix_gauntlet": collect_matrix(),
        "provider_probe": collect_provider_probe(),
        "judge_panel": collect_judge_panel(),
    }
    audit["claims"] = overall_claims(audit)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    stamp = utc_stamp()
    json_path = args.out_dir / f"sophia_evidence_audit_{stamp}.json"
    md_path = args.out_dir / f"sophia_evidence_audit_{stamp}.md"
    json_path.write_text(json.dumps(audit, indent=2, sort_keys=True), encoding="utf-8")
    write_markdown(md_path, audit)
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "claims": audit["claims"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
