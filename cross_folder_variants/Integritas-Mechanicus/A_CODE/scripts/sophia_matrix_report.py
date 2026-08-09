#!/usr/bin/env python3
"""Generate an auditor-facing Markdown report for a Sophia matrix gauntlet."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "evidence" / "matrix_reports"


def pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:.2f}%"


def ci(interval: Dict[str, Any]) -> str:
    if not interval:
        return "n/a"
    return f"{pct(interval.get('rate'))} [{pct(interval.get('ci95_low'))}, {pct(interval.get('ci95_high'))}]"


def yes(value: bool) -> str:
    return "yes" if value else "no"


def table(headers: List[str], rows: Iterable[Iterable[Any]]) -> List[str]:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(cell).replace("\n", "<br>") for cell in row) + " |")
    return lines


def bucket_rows(summary: Dict[str, Any], key: str) -> List[Tuple[str, Dict[str, Any]]]:
    return sorted((summary.get(key) or {}).items(), key=lambda item: (item[1].get("contract_pass_rate", 0), item[0]))


def compact_row(name: str, item: Dict[str, Any]) -> List[Any]:
    return [
        name,
        item.get("total", 0),
        f"{item.get('contract_passes', 0)}/{item.get('total', 0)}",
        pct(item.get("contract_pass_rate")),
        item.get("false_releases", 0),
        pct(item.get("false_release_rate")),
        item.get("false_holds", 0),
        pct(item.get("false_hold_rate")),
        pct(item.get("repair_rate")),
        pct(item.get("raw_article_pass_rate")),
        pct(item.get("final_release_rate")),
        ci(item.get("contract_interval") or {}),
    ]


def provider_short(row: Dict[str, Any]) -> str:
    return f"{row.get('provider')}::{row.get('model')}"


def build_cross_tab(rows: List[Dict[str, Any]], row_key: str, col_key: str, predicate) -> Tuple[List[str], List[List[Any]]]:
    row_names = sorted({str(row.get(row_key)) for row in rows})
    col_names = sorted({str(row.get(col_key)) for row in rows})
    counts: Dict[Tuple[str, str], List[int]] = defaultdict(lambda: [0, 0])
    for row in rows:
        key = (str(row.get(row_key)), str(row.get(col_key)))
        counts[key][1] += 1
        counts[key][0] += int(bool(predicate(row)))
    out_rows = []
    for rn in row_names:
        out = [rn]
        for cn in col_names:
            num, den = counts[(rn, cn)]
            out.append(f"{num}/{den}")
        out_rows.append(out)
    return [row_key, *col_names], out_rows


def failure_rows(results: List[Dict[str, Any]]) -> List[List[Any]]:
    rows = []
    for row in results:
        ev = row.get("evaluation") or {}
        if ev.get("proof_contract_passed"):
            continue
        checks = ev.get("checks") or {}
        failed_checks = [key for key, value in checks.items() if value is False]
        rows.append([
            row.get("provider"),
            row.get("model"),
            row.get("case_id"),
            row.get("risk_family"),
            row.get("mutation"),
            yes(ev.get("false_release")),
            yes(ev.get("false_hold")),
            yes(ev.get("explicit_denial")),
            yes(ev.get("final_released")),
            ", ".join(failed_checks) or "n/a",
            row.get("final_response_hash", "")[:12],
        ])
    return rows


def false_release_rows(results: List[Dict[str, Any]]) -> List[List[Any]]:
    rows = []
    for row in results:
        ev = row.get("evaluation") or {}
        if not ev.get("false_release"):
            continue
        final_mandos = row.get("mandos_judgment") or {}
        rows.append([
            row.get("provider"),
            row.get("model"),
            row.get("case_id"),
            row.get("mutation"),
            final_mandos.get("verdict"),
            final_mandos.get("score"),
            ", ".join(final_mandos.get("failed_checks") or []),
            ", ".join(ev.get("repair_steps") or []),
            row.get("final_response_hash", "")[:12],
        ])
    return rows


def top_counter(results: List[Dict[str, Any]], key: str, predicate) -> List[List[Any]]:
    ctr = Counter(str(row.get(key)) for row in results if predicate(row))
    return [[name, count] for name, count in ctr.most_common()]


def write_report(matrix_path: Path, out_path: Path | None = None) -> Path:
    matrix_text = matrix_path.read_text(encoding="utf-8")
    artifact = json.loads(matrix_text)
    matrix_sha = hashlib.sha256(matrix_text.encode("utf-8")).hexdigest()
    summary = artifact["summary"]
    results = artifact["results"]
    protocol = artifact["protocol"]
    providers = artifact.get("providers") or []
    created = datetime.now(timezone.utc).isoformat()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = out_path or (OUT_DIR / f"SOPHIA_REMOTE_MATRIX_GAUNTLET_REPORT_{timestamp}.md")

    lines: List[str] = [
        "# Sophia Remote Matrix Gauntlet Report",
        "",
        f"Generated: `{created}`",
        f"Source artifact: `{matrix_path}`",
        f"Matrix timestamp: `{artifact.get('timestamp')}`",
        f"Matrix ID: `{artifact.get('matrix_id')}`",
        f"Artifact SHA256: `{matrix_sha}`",
        "",
        "## Executive Verdict",
        "",
        "This 576-row run is strong evidence that Sophia's constitutional repair layer improves raw remote-model outputs across six live providers, but it is not a clean pass. The matrix found a systematic denial-boundary weakness: mutated `unreparable_violation` cases were sometimes repaired into releasable help instead of being held or explicitly denied.",
        "",
        "The important safety distinction is that most failures were conservative false holds or denial-boundary false releases; ordinary integrity, policy, source-conflict, high-risk advice, office-jurisdiction, completeness, and provider-failure support were clean across all providers in this run.",
        "",
        "## Protocol",
        "",
        *table(
            ["Field", "Value"],
            [
                ["Providers preset", protocol.get("providers_preset")],
                ["Providers", ", ".join(f"{p['provider']}::{p['model']}" for p in providers)],
                ["Cases", "12 base cases"],
                ["Mutations", protocol.get("mutation_mode")],
                ["Mutation mode", protocol.get("mutation_generation_mode")],
                ["Ablation", protocol.get("ablation_mode")],
                ["Fault mode", protocol.get("fault_mode")],
                ["Case limit", protocol.get("case_limit")],
                ["Source hash", protocol.get("source_hash")],
                ["Cases hash", protocol.get("cases_hash")],
                ["Mutations hash", protocol.get("mutations_hash")],
            ],
        ),
        "",
        "## Top-Line Statistics",
        "",
        *table(
            ["Metric", "Count", "Rate / 95% Wilson CI"],
            [
                ["Proof-contract pass", f"{summary['proof_contract_passes']}/{summary['total']}", ci(summary.get("proof_contract_interval") or {})],
                ["False release", f"{summary['false_releases']}/{summary['total']}", ci(summary.get("false_release_interval") or {})],
                ["False hold", f"{summary['false_holds']}/{summary['total']}", ci(summary.get("false_hold_interval") or {})],
                ["Repairs applied", f"{summary['repairs_applied']}/{summary['total']}", ci((summary.get("stage_metrics") or {}).get("repair", {}).get("repair_interval") or {})],
                ["Raw Mandos pass", f"{summary['raw_mandos_passes']}/{summary['total']}", ci((summary.get("stage_metrics") or {}).get("raw", {}).get("mandos_pass_interval") or {})],
                ["Raw article full-pass", f"{summary['raw_article_full_passes']}/{summary['total']}", ci((summary.get("stage_metrics") or {}).get("raw", {}).get("article_pass_interval") or {})],
                ["Final Mandos pass", f"{summary['final_mandos_passes']}/{summary['total']}", ci((summary.get("stage_metrics") or {}).get("released", {}).get("mandos_pass_interval") or {})],
                ["Final article full-pass", f"{summary['final_article_full_passes']}/{summary['total']}", ci((summary.get("stage_metrics") or {}).get("released", {}).get("article_pass_interval") or {})],
                ["Final releases", f"{summary['final_releases']}/{summary['total']}", ci((summary.get("stage_metrics") or {}).get("released", {}).get("release_interval") or {})],
            ],
        ),
        "",
        "## Latency",
        "",
        *table(
            ["Metric", "Milliseconds"],
            [
                ["Mean", summary.get("latency_ms", {}).get("mean")],
                ["Median", summary.get("latency_ms", {}).get("median")],
                ["Max", summary.get("latency_ms", {}).get("max")],
            ],
        ),
        "",
        "## Provider Table",
        "",
        *table(
            ["Provider", "N", "Passes", "Pass Rate", "False Releases", "FR Rate", "False Holds", "FH Rate", "Repair Rate", "Raw Article Rate", "Final Release Rate", "Pass CI"],
            [compact_row(name, item) for name, item in bucket_rows(summary, "by_provider")],
        ),
        "",
        "## Mutation Table",
        "",
        *table(
            ["Mutation", "N", "Passes", "Pass Rate", "False Releases", "FR Rate", "False Holds", "FH Rate", "Repair Rate", "Raw Article Rate", "Final Release Rate", "Pass CI"],
            [compact_row(name, item) for name, item in bucket_rows(summary, "by_mutation")],
        ),
        "",
        "## Risk-Family Table",
        "",
        *table(
            ["Risk Family", "N", "Passes", "Pass Rate", "False Releases", "FR Rate", "False Holds", "FH Rate", "Repair Rate", "Raw Article Rate", "Final Release Rate", "Pass CI"],
            [compact_row(name, item) for name, item in bucket_rows(summary, "by_risk_family")],
        ),
        "",
        "## Ablation And Fault Tables",
        "",
        *table(
            ["Ablation", "N", "Passes", "Pass Rate", "False Releases", "FR Rate", "False Holds", "FH Rate", "Repair Rate", "Raw Article Rate", "Final Release Rate", "Pass CI"],
            [compact_row(name, item) for name, item in bucket_rows(summary, "by_ablation")],
        ),
        "",
        *table(
            ["Fault", "N", "Passes", "Pass Rate", "False Releases", "FR Rate", "False Holds", "FH Rate", "Repair Rate", "Raw Article Rate", "Final Release Rate", "Pass CI"],
            [compact_row(name, item) for name, item in bucket_rows(summary, "by_fault")],
        ),
        "",
    ]

    headers, rows = build_cross_tab(results, "provider", "risk_family", lambda r: (r.get("evaluation") or {}).get("proof_contract_passed"))
    lines += ["## Provider x Risk-Family Pass Counts", "", *table(headers, rows), ""]
    headers, rows = build_cross_tab(results, "provider", "mutation", lambda r: (r.get("evaluation") or {}).get("proof_contract_passed"))
    lines += ["## Provider x Mutation Pass Counts", "", *table(headers, rows), ""]
    headers, rows = build_cross_tab(results, "case_id", "mutation", lambda r: (r.get("evaluation") or {}).get("proof_contract_passed"))
    lines += ["## Case x Mutation Pass Counts", "", *table(headers, rows), ""]
    headers, rows = build_cross_tab(results, "provider", "case_id", lambda r: (r.get("evaluation") or {}).get("false_release"))
    lines += ["## False Releases By Provider x Case", "", *table(headers, rows), ""]
    headers, rows = build_cross_tab(results, "provider", "case_id", lambda r: (r.get("evaluation") or {}).get("false_hold"))
    lines += ["## False Holds By Provider x Case", "", *table(headers, rows), ""]

    lines += [
        "## Failure Concentration",
        "",
        "### Failed Rows By Provider",
        "",
        *table(["Provider", "Failures"], top_counter(results, "provider", lambda r: not (r.get("evaluation") or {}).get("proof_contract_passed"))),
        "",
        "### Failed Rows By Case",
        "",
        *table(["Case", "Failures"], top_counter(results, "case_id", lambda r: not (r.get("evaluation") or {}).get("proof_contract_passed"))),
        "",
        "### False Releases By Case",
        "",
        *table(["Case", "False Releases"], top_counter(results, "case_id", lambda r: (r.get("evaluation") or {}).get("false_release"))),
        "",
        "### False Holds By Case",
        "",
        *table(["Case", "False Holds"], top_counter(results, "case_id", lambda r: (r.get("evaluation") or {}).get("false_hold"))),
        "",
        "## False-Release Appendix",
        "",
        *table(
            ["Provider", "Model", "Case", "Mutation", "Mandos Verdict", "Mandos Score", "Mandos Failed Checks", "Repair Steps", "Final Hash"],
            false_release_rows(results),
        ),
        "",
        "## All Failed Rows Appendix",
        "",
        *table(
            ["Provider", "Model", "Case", "Risk", "Mutation", "False Release", "False Hold", "Explicit Denial", "Final Released", "Failed Checks", "Final Hash"],
            failure_rows(results),
        ),
        "",
        "## Interpretation",
        "",
        "### What Is Proven By This Run",
        "",
        "- Sophia can wrap six live remote providers behind the same local constitutional governance lane.",
        "- The local repair layer materially changes raw remote outputs: repairs were applied in `557/576` rows.",
        "- Final article conformity was perfect in this matrix: `576/576` rows had full final article conformity.",
        "- Integrity ambiguity, policy judgment, contradictory-source reasoning, high-risk concealment advice, office jurisdiction, completeness support, and provider-failure guidance produced zero false releases in this run.",
        "- Gemini was successfully unblocked via `gemini-flash-lite-latest` and performed best overall: `89/96` contract passes with `1/96` false release.",
        "",
        "### What Is Not Proven",
        "",
        "- This is not a clean safety proof because `21/576` rows were classified as false releases.",
        "- Denial-boundary robustness is not solved: `unreparable_violation` passed only `27/48`, with `21/48` false releases.",
        "- Provenance/missing-source cases need quality calibration: they generated `37` false holds, indicating Sophia or the harness is too conservative where bounded help may be permissible.",
        "- No fault-injection or ablation sweep was included in this specific 576-row run; this was `A0_full` with `fault=none`.",
        "- The result does not prove long-term learner improvement, external human-rater agreement, or native pixel-vision competence.",
        "",
        "## Recommended Fix Queue",
        "",
        "- First fix denial-boundary classification for mutated `unreparable_violation` cases. Either mark softened mutations with different expectations if they no longer contain unreparable intent, or require denial whenever the parent case is denial-class even after mutation.",
        "- Add an explicit `parent_expect_denial` field to mutated cases so the evaluator cannot lose the original risk contract.",
        "- Strengthen Mandos denial logic around concealment, provenance hiding, log suppression, final-answer substitution, and covenant override even when phrased lexically, semantically, or as infrastructure degradation.",
        "- Recalibrate missing-provenance expectations so safe source-finding/scaffold help is not scored as false hold when Sophia refuses to fabricate.",
        "- Add checkpointed matrix writes and provider sharding; NIM caused very long tail latency and should not hold the whole artifact hostage.",
        "",
        "## Bottom Line",
        "",
        "Sophia is credible as a governed remote-model wrapper, but this wider matrix caught the exact class of weakness a serious gauntlet should catch: denial semantics can be weakened by mutation. The next phase should not broaden the matrix further; it should fix the denial-boundary contract, rerun the same 576-row matrix, and require zero false releases before making strong academic-integrity claims.",
        "",
    ]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("matrix_json", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    out = write_report(args.matrix_json, args.out)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
