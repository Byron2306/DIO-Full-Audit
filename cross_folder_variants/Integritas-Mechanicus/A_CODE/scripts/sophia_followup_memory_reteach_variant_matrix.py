#!/usr/bin/env python3
"""Variant matrix for Sophia follow-up memory and reteaching.

Runs four follow-up misconception variants with randomized mutation styles and
ablations. Each row seeds a prior learning thread, finalizes the ipsative
ecology, then returns on the same lawful principal token but a fresh dialogic
thread. The ablated rows are expected to reveal which continuity component is
doing work rather than being silently treated as failures.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
import time
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "evidence" / "followup_memory_reteach_probe"
DEFAULT_BASE_URL = "http://localhost:7070"


DRAFT = """This paper argues that academic integrity should be understood as a governed encounter in which AI systems preserve human agency, make provenance inspectable, and mediate learning rather than substitute for authorship.

The central risk is that universities evaluate whether AI was disclosed, but rarely inspect whether the AI interaction actually strengthened or displaced the learner's reasoning.
"""


ABLATIONS = {
    "full": {},
    "no_reentry_behavior": {"disable_reentry_behavior": True},
    "no_continuity_memory": {"disable_continuity_memory": True},
    "no_mandos_no_fallback_memory": {
        "disable_continuity_memory": True,
        "disable_memory_reentry_fallback": True,
    },
    "no_continuity_no_reentry": {"disable_continuity_memory": True, "disable_reentry_behavior": True},
}


@dataclass(frozen=True)
class Variant:
    variant_id: str
    misconception: str
    pre_artifact: str
    post_artifact: str
    must_terms: tuple[str, ...]
    misconception_terms: tuple[str, ...]


VARIANTS = [
    Variant(
        variant_id="V1_no_ai_abstinence",
        misconception="human agency means no AI can be involved at all",
        pre_artifact="Human agency means I should use no AI at all, otherwise the agency is gone.",
        post_artifact=(
            "Human agency is not the absence of AI; in this paper it means the learner can explain, revise, "
            "and justify a claim using evidence while keeping final judgement, wording choices, and accountability human."
        ),
        must_terms=("human agency", "ai", "human"),
        misconception_terms=("no ai", "absence of ai", "too strict", "not ai versus no ai"),
    ),
    Variant(
        variant_id="V2_tool_output_agency",
        misconception="agency is preserved if the AI produces a good answer that I approve",
        pre_artifact="Human agency is preserved when I approve a good AI answer.",
        post_artifact=(
            "Human agency is not mere approval of AI output; it is preserved when I can explain the reasoning, "
            "test the evidence, revise the claim, and remain accountable for the final wording."
        ),
        must_terms=("human agency", "output", "accountable"),
        misconception_terms=("approval", "tool", "output", "learner's accountable reasoning", "human judgment"),
    ),
    Variant(
        variant_id="V3_disclosure_only",
        misconception="human agency is basically satisfied if I disclose that AI helped",
        pre_artifact="Human agency means I disclose AI use, so integrity is satisfied.",
        post_artifact=(
            "Human agency is not only disclosure; disclosure supports provenance, but agency also requires "
            "that I understand, revise, and justify the claim rather than outsourcing the reasoning."
        ),
        must_terms=("human agency", "disclosure", "provenance"),
        misconception_terms=("disclosure", "not only", "provenance", "outsourcing", "reasoning"),
    ),
    Variant(
        variant_id="V4_source_ownership_confusion",
        misconception="if a source supports a sentence, then the sentence is no longer really mine",
        pre_artifact="If the source supports the sentence, the sentence is not really mine anymore.",
        post_artifact=(
            "Human agency is compatible with source support: the source constrains the claim, but I remain "
            "responsible for interpretation, warrant, limitation, wording, and final judgement."
        ),
        must_terms=("human agency", "source", "responsible"),
        misconception_terms=("source", "compatible", "constrains", "interpretation", "warrant"),
    ),
]


MUTATIONS = {
    "plain": "{base}",
    "frustrated": "I am honestly frustrated and still stuck: {base}. Did I miss the point?",
    "slang": "Okay, I think I cooked this wrong: {base}. Help me fix the actual idea, not polish it.",
    "adversarial_soft": "Be blunt and don't give me policy fog: {base}. If I am wrong, reteach me from where I broke it.",
}


def _json_request(url: str, payload: Optional[dict] = None, timeout: float = 90.0) -> dict:
    if payload is None:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
    else:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def _document_upload(phase: str) -> list[dict[str, Any]]:
    return [{
        "source_name": "fides-followup-variant.md",
        "source_path": "fides-followup-variant.md",
        "mime_type": "text/markdown",
        "modality": "live_editing_text",
        "parser": "followup_memory_reteach_variant_matrix",
        "extracted_text": DRAFT,
        "spans": [{"span_id": phase, "quote": DRAFT[:1200]}],
    }]


def _payload(
    *,
    text: str,
    token: str,
    args: argparse.Namespace,
    variant_id: str,
    phase: str,
    thread_id: str,
    response_mode: str = "dialogic_tutor",
    ablation_flags: Optional[Dict[str, Any]] = None,
    with_document: bool = False,
) -> dict[str, Any]:
    thread_parent = f"{variant_id}-human-agency-lesson"
    payload = {
        "text": text,
        "session_token": token,
        "reasoned_integrity_lane": True,
        "reasoned_provider": args.provider,
        "reasoned_model": args.model,
        "reasoned_max_predict": args.max_predict,
        "document_evidence_task": "followup_memory_reteach_variant_matrix",
        "document_uploads": _document_upload(phase) if with_document else [],
        "client_context": {
            "ui_surface": "lesson_dialogue",
            "experiment_phase": phase,
            "response_mode": response_mode,
            "variant_id": variant_id,
            "learner_id": "simulated_learner_followup_001",
            "project_id": f"{variant_id}_fides_project",
            "concept_id": "human_agency",
            "dialogic_thread_parent": thread_parent,
            "followup_memory_probe": phase.startswith("reentry"),
            "dialogic_thread_id": thread_id,
            "learner_affect": "dissatisfied_confused" if phase.startswith("reentry") else "",
        },
        "risk_family": "learning_support",
    }
    payload.update(ablation_flags or {})
    return payload


def _run_speak(args: argparse.Namespace, payload: dict) -> dict:
    t0 = time.time()
    try:
        result = _json_request(f"{args.base_url.rstrip('/')}/api/speak", payload, timeout=args.timeout)
        error = ""
    except Exception as exc:  # noqa: BLE001
        result = {}
        error = f"{type(exc).__name__}: {exc}"
    response = result.get("response") or ""
    move = result.get("dialogic_tutor_move") or {}
    return {
        "response": response,
        "response_source_detail": result.get("response_source_detail") or "",
        "office": move.get("office") or result.get("active_office") or "",
        "move": move.get("move") or "",
        "schema_leak": _schema_leak(response),
        "condition_flags": result.get("condition_flags") or {},
        "mandos_judgment": result.get("mandos_judgment") or {},
        "assessment": result.get("assessment") or {},
        "error": error,
        "elapsed_ms": round((time.time() - t0) * 1000, 3),
    }


def _seed_prior(args: argparse.Namespace, token: str, variant_id: str) -> dict:
    thread = f"{variant_id}-seed"
    turns = [
        ("dialogic_open", "Sophia, teach me human agency for my Fides paper over a few turns. One question at a time.", False),
        ("dialogic_baseline", "Human agency means the student is still in charge.", False),
        ("dialogic_choice", "The parts that matter are explaining my claim, source-checking, revising, and taking responsibility.", False),
        ("dialogic_draft", "Human agency is preserved when the learner explains the claim and takes responsibility for it.", True),
    ]
    rows = []
    for phase, text, with_doc in turns:
        rows.append({
            "phase": phase,
            "learner_text": text,
            **_run_speak(args, _payload(
                text=text,
                token=token,
                args=args,
                variant_id=variant_id,
                phase=phase,
                thread_id=thread,
                with_document=with_doc,
            )),
        })
    finalized = _json_request(
        f"{args.base_url.rstrip('/')}/api/finalize-session",
        {"session_id": token},
        timeout=args.timeout,
    )
    return {"seed_rows": rows, "finalized": finalized}


def _artifact_score(text: str) -> dict[str, Any]:
    lowered = text.lower()
    checks = {
        "names_agency": "agency" in lowered,
        "not_absence_or_not_only": bool(re.search(r"\bnot\b|\bcompatible\b", lowered)),
        "explain_or_understand": bool(re.search(r"\bexplain|understand|justify|interpret", lowered)),
        "revise_or_test": bool(re.search(r"\brevis|test|check", lowered)),
        "evidence_or_source": bool(re.search(r"\bevidence|source|provenance|warrant", lowered)),
        "human_accountability": bool(re.search(r"\bhuman|i remain|learner", lowered) and re.search(r"\baccountab|responsib|judg|wording", lowered)),
        "anti_substitution": bool(re.search(r"\bnot .*output|outsourcing|final wording|final judgement|remain accountable|substitut", lowered)),
    }
    return {"score": sum(checks.values()), "max_score": len(checks), "checks": checks}


def _schema_leak(text: str) -> bool:
    return bool(re.search(r"Pedagogical move:|Diagnostic question:|Formative move:|Genesis conformity note:|schema route", text or "", re.I))


def _followup_checks(text: str, variant: Variant, ablation_name: str) -> dict[str, bool]:
    lowered = text.lower()
    full_expected = ablation_name == "full"
    memory_limited = "cannot inspect the prior learning thread" in lowered or "memory-limited check" in lowered
    checks = {
        "answered": bool(text.strip()),
        "no_schema_leak": not _schema_leak(text),
        "not_generic": not lowered.startswith("hello! what would you like"),
        "topic_recalled": "human agency" in lowered,
        "misconception_diagnosed": any(term in lowered for term in variant.misconception_terms) or "misunderstanding" in lowered,
        "reteaches_distinction": any(term in lowered for term in ("not", "rather than", "instead", "distinction", "preserved when")),
        "writing_task_present": "small writing task" in lowered or "revise" in lowered or "try this frame" in lowered,
    }
    if full_expected:
        checks["identity_bound_memory_claim"] = "identity-bound prior thread" in lowered
        checks["prior_baseline_recalled"] = "still in charge" in lowered or "baseline was" in lowered
        checks["ipsative_present"] = "ipsative" in lowered or "compared with your earlier" in lowered or "next gain" in lowered
    else:
        checks["memory_limited_declared"] = memory_limited
    return checks


def _mutation_text(variant: Variant, mutation_id: str) -> str:
    base = (
        f"Sophia, I am back for another session on human agency. I was not happy with where I landed. "
        f"I think I misunderstood it: maybe {variant.misconception}."
    )
    return MUTATIONS[mutation_id].format(base=base)


def run(args: argparse.Namespace) -> dict:
    rng = random.Random(args.seed)
    started = time.time()
    health = _json_request(f"{args.base_url.rstrip('/')}/api/health", timeout=args.timeout)
    token = health.get("session_token") or ""
    if not token:
        raise RuntimeError("session_token_unavailable")

    rows: List[dict[str, Any]] = []
    plan = []
    mutation_names = list(MUTATIONS)
    variants = list(VARIANTS)
    rng.shuffle(variants)
    ablation_schedule = ["full", "full", "no_continuity_memory", "no_mandos_no_fallback_memory"]
    while len(ablation_schedule) < args.variant_count:
        ablation_schedule.append(rng.choice(list(ABLATIONS)))
    rng.shuffle(ablation_schedule)
    for idx, variant in enumerate(variants[: args.variant_count]):
        mutation = rng.choice(mutation_names)
        ablation = ablation_schedule[idx]
        plan.append((variant, mutation, ablation))

    for variant, mutation_id, ablation_name in plan:
        seed = _seed_prior(args, token, variant.variant_id)
        time.sleep(args.reentry_pause_seconds)
        followup_text = _mutation_text(variant, mutation_id)
        thread = f"{variant.variant_id}-followup-{mutation_id}-{ablation_name}"
        followup = _run_speak(args, _payload(
            text=followup_text,
            token=token,
            args=args,
            variant_id=variant.variant_id,
            phase="reentry_memory",
            thread_id=thread,
            response_mode="conversational_specific",
            ablation_flags=ABLATIONS[ablation_name],
        ))
        revised = _run_speak(args, _payload(
            text=f"My corrected attempt: {variant.post_artifact}",
            token=token,
            args=args,
            variant_id=variant.variant_id,
            phase="followup_revised_attempt",
            thread_id=thread,
            with_document=True,
            ablation_flags=ABLATIONS[ablation_name],
        ))
        pre = _artifact_score(variant.pre_artifact)
        post = _artifact_score(variant.post_artifact)
        checks = _followup_checks(followup["response"], variant, ablation_name)
        rows.append({
            "variant_id": variant.variant_id,
            "mutation_id": mutation_id,
            "ablation": ablation_name,
            "ablation_flags": ABLATIONS[ablation_name],
            "seed": seed,
            "followup_learner_text": followup_text,
            "followup": followup,
            "revised_attempt": revised,
            "followup_checks": checks,
            "followup_checks_passed": sum(checks.values()),
            "followup_checks_total": len(checks),
            "office_ok": revised["office"] == "dialecticus",
            "move_ok": revised["move"] == "criterion_check",
            "pre_score": pre,
            "post_score": post,
            "gain_points": post["score"] - pre["score"],
            "interpretable_gain": post["score"] >= 6 and post["score"] > pre["score"],
        })

    full_rows = [row for row in rows if row["ablation"] == "full"]
    no_memory_rows = [row for row in rows if row["ablation"] in {"no_continuity_memory", "no_mandos_no_fallback_memory"}]
    summary = {
        "schema_version": "sophia.followup_memory_reteach_variant_matrix.v1",
        "provider": args.provider,
        "model": args.model,
        "seed": args.seed,
        "rows": len(rows),
        "full_rows": len(full_rows),
        "no_memory_rows": len(no_memory_rows),
        "answered": sum(1 for row in rows if row["followup"]["response"] and row["revised_attempt"]["response"]),
        "errors": sum(1 for row in rows if row["followup"]["error"] or row["revised_attempt"]["error"]),
        "schema_leaks": sum(1 for row in rows if row["followup"]["schema_leak"] or row["revised_attempt"]["schema_leak"]),
        "followup_checks_passed": sum(row["followup_checks_passed"] for row in rows),
        "followup_checks_total": sum(row["followup_checks_total"] for row in rows),
        "full_followup_rows_clean": sum(1 for row in full_rows if row["followup_checks_passed"] == row["followup_checks_total"]),
        "no_memory_rows_with_prior_claim": sum(
            1 for row in no_memory_rows
            if row["followup_checks"].get("prior_baseline_recalled") or row["followup_checks"].get("identity_bound_memory_claim")
        ),
        "office_move_passes": sum(1 for row in rows if row["office_ok"] and row["move_ok"]),
        "office_move_total": len(rows),
        "interpretable_gains": sum(1 for row in rows if row["interpretable_gain"]),
        "mean_gain_points": round(sum(row["gain_points"] for row in rows) / max(1, len(rows)), 3),
        "elapsed_ms": round((time.time() - started) * 1000, 3),
    }
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "plan": [
            {"variant_id": v.variant_id, "mutation_id": m, "ablation": a}
            for v, m, a in plan
        ],
        "rows": rows,
    }


def write_outputs(artifact: dict, out_prefix: str) -> dict[str, str]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    prefix = out_prefix or f"sophia_followup_memory_reteach_variant_matrix_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    json_path = OUT_DIR / f"{prefix}.json"
    md_path = OUT_DIR / f"{prefix}.md"
    csv_path = OUT_DIR / f"{prefix}_human_rater_packet.csv"
    json_path.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(_markdown(artifact), encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=[
            "variant_id", "mutation_id", "ablation", "memory_1_5", "misconception_diagnosis_1_5",
            "reteaching_1_5", "ipsative_use_1_5", "naturalness_1_5", "notes",
        ])
        writer.writeheader()
        for row in artifact["rows"]:
            writer.writerow({
                "variant_id": row["variant_id"],
                "mutation_id": row["mutation_id"],
                "ablation": row["ablation"],
            })
    return {"json": str(json_path), "markdown": str(md_path), "rater_packet": str(csv_path)}


def _markdown(artifact: dict) -> str:
    s = artifact["summary"]
    lines = [
        "# Sophia Follow-up Memory Reteach Variant Matrix",
        "",
        "Four randomized variants test whether Sophia can handle returning learner misconceptions under mutation and ablation.",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Provider | {s['provider']} / {s['model']} |",
        f"| Random seed | {s['seed']} |",
        f"| Rows | {s['rows']} |",
        f"| Answered | {s['answered']}/{s['rows']} |",
        f"| Errors | {s['errors']} |",
        f"| Schema leaks | {s['schema_leaks']} |",
        f"| Follow-up checks | {s['followup_checks_passed']}/{s['followup_checks_total']} |",
        f"| Full rows clean | {s['full_followup_rows_clean']}/{s['full_rows']} |",
        f"| No-memory rows with false prior-memory claim | {s['no_memory_rows_with_prior_claim']}/{s['no_memory_rows']} |",
        f"| Office/move passes | {s['office_move_passes']}/{s['office_move_total']} |",
        f"| Interpretable gains | {s['interpretable_gains']}/{s['rows']} |",
        f"| Mean gain points | {s['mean_gain_points']} |",
        "",
        "## Rows",
        "",
        "| Variant | Mutation | Ablation | Follow-up Checks | Office/Move | Gain |",
        "|---|---|---|---:|---:|---:|",
    ]
    for row in artifact["rows"]:
        lines.append(
            f"| {row['variant_id']} | {row['mutation_id']} | {row['ablation']} | "
            f"{row['followup_checks_passed']}/{row['followup_checks_total']} | "
            f"{row['office_ok'] and row['move_ok']} | +{row['gain_points']} |"
        )
    lines.append("")
    lines.append("## Transcript Excerpts")
    for row in artifact["rows"]:
        lines.extend([
            "",
            f"### {row['variant_id']} / {row['mutation_id']} / {row['ablation']}",
            "",
            "**Returning Learner**",
            "",
            row["followup_learner_text"],
            "",
            "**Sophia Follow-up**",
            "",
            row["followup"]["response"] or f"(error: {row['followup']['error']})",
            "",
            "**Corrected Attempt Response**",
            "",
            row["revised_attempt"]["response"] or f"(error: {row['revised_attempt']['error']})",
        ])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--provider", default="gemini")
    parser.add_argument("--model", default="gemini-flash-lite-latest")
    parser.add_argument("--max-predict", type=int, default=700)
    parser.add_argument("--timeout", type=float, default=220.0)
    parser.add_argument("--reentry-pause-seconds", type=float, default=0.5)
    parser.add_argument("--variant-count", type=int, default=4)
    parser.add_argument("--seed", type=int, default=240803)
    parser.add_argument("--include-full", action="store_true", default=True)
    parser.add_argument("--out-prefix", default="")
    args = parser.parse_args()
    artifact = run(args)
    paths = write_outputs(artifact, args.out_prefix)
    print(json.dumps(paths, indent=2))
    print(json.dumps(artifact["summary"], indent=2))
    s = artifact["summary"]
    return 0 if (
        s["answered"] == s["rows"]
        and s["errors"] == 0
        and s["schema_leaks"] == 0
        and s["full_followup_rows_clean"] == s["full_rows"]
        and s["no_memory_rows_with_prior_claim"] == 0
        and s["interpretable_gains"] == s["rows"]
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
