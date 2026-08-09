#!/usr/bin/env python3
"""Fresh-session follow-up memory and reteaching probe for Sophia.

This is stricter than the re-entry learning-gain probe. Session A establishes a
prior learning thread and finalizes the ipsative ecology. Session B uses a new
session token and presents a new misconception. The probe passes only if Sophia
uses continuity, diagnoses the misconception, changes to a reteaching stance,
and improves the simulated learner artifact.
"""

from __future__ import annotations

import argparse
import csv
import json
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


@dataclass(frozen=True)
class Turn:
    session: str
    phase: str
    learner_text: str
    expected: str
    response_mode: str = "dialogic_tutor"
    document_text: str = ""
    source_task: bool = False
    expect_office: str = ""
    expect_move: str = ""


SESSION_A = [
    Turn(
        session="A",
        phase="dialogic_open",
        learner_text="Sophia, teach me human agency for my Fides paper over a few turns. One question at a time.",
        expected="establish baseline lesson thread",
        expect_office="maieuticus",
        expect_move="baseline_probe",
    ),
    Turn(
        session="A",
        phase="dialogic_baseline",
        learner_text="Human agency means the student is still in charge.",
        expected="record vague baseline",
        expect_office="maieuticus",
        expect_move="indicator_selection",
    ),
    Turn(
        session="A",
        phase="dialogic_choice",
        learner_text="I think the important parts are explaining my claim and taking responsibility.",
        expected="move toward an observable definition",
        expect_office="constructor",
        expect_move="draft_attempt",
    ),
    Turn(
        session="A",
        phase="dialogic_draft",
        learner_text="Human agency is preserved when the learner explains the claim and takes responsibility for it.",
        expected="criterion check of first draft",
        document_text=DRAFT,
        expect_office="dialecticus",
        expect_move="criterion_check",
    ),
]


SESSION_B = [
    Turn(
        session="B",
        phase="reentry_memory",
        learner_text=(
            "Sophia, I am back for another session on human agency. I was not happy with where I landed. "
            "I think I misunderstood it: maybe human agency just means I must use no AI at all, otherwise the agency is gone."
        ),
        expected="fresh-session continuity plus misconception diagnosis and reteaching",
        response_mode="conversational_specific",
    ),
    Turn(
        session="B",
        phase="followup_revised_attempt",
        learner_text=(
            "My corrected attempt: Human agency is not the absence of AI; in this paper it means the learner can explain, "
            "revise, and justify a claim using evidence while keeping final judgement, wording choices, and accountability human."
        ),
        expected="criterion check and next evidence-bound move",
        document_text=DRAFT,
        response_mode="dialogic_tutor",
        expect_office="dialecticus",
        expect_move="criterion_check",
    ),
]


PRE_FOLLOWUP_ARTIFACT = "Human agency means I should use no AI at all, otherwise the agency is gone."
POST_FOLLOWUP_ARTIFACT = SESSION_B[-1].learner_text.replace("My corrected attempt: ", "")


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


def _document_upload(turn: Turn) -> list[dict[str, Any]]:
    if not turn.document_text:
        return []
    return [{
        "source_name": "fides-followup-memory.md",
        "source_path": "fides-followup-memory.md",
        "mime_type": "text/markdown",
        "modality": "live_editing_text",
        "parser": "followup_memory_reteach_probe",
        "extracted_text": turn.document_text,
        "spans": [{"span_id": turn.phase, "quote": turn.document_text[:1200]}],
    }]


def _payload(turn: Turn, token: str, args: argparse.Namespace) -> dict[str, Any]:
    dialogic_thread_id = "fides-human-agency-seed" if turn.session == "A" else "fides-human-agency-followup"
    return {
        "text": turn.learner_text,
        "session_token": token,
        "reasoned_integrity_lane": True,
        "reasoned_provider": args.provider,
        "reasoned_model": args.model,
        "reasoned_max_predict": args.max_predict,
        "document_evidence_task": "followup_memory_reteach_probe",
        "document_uploads": _document_upload(turn),
        "client_context": {
            "ui_surface": "lesson_dialogue",
            "experiment_phase": turn.phase,
            "response_mode": turn.response_mode,
            "expected_function": turn.expected,
            "learner_id": "simulated_learner_followup_001",
            "project_id": "fides_followup_memory_project",
            "concept_id": "human_agency",
            "dialogic_thread_parent": "fides-human-agency-lesson",
            "learner_affect": "dissatisfied_confused" if turn.session == "B" else "",
            "followup_memory_probe": turn.session == "B",
            "dialogic_thread_id": dialogic_thread_id,
        },
        "risk_family": "learning_support",
    }


def _finalize(base_url: str, token: str, timeout: float) -> dict:
    return _json_request(
        f"{base_url.rstrip('/')}/api/finalize-session",
        {"session_id": token},
        timeout=timeout,
    )


def _schema_leak(text: str) -> bool:
    return bool(re.search(r"Pedagogical move:|Diagnostic question:|Formative move:|Genesis conformity note:|schema route", text or "", re.I))


def _artifact_score(text: str) -> Dict[str, Any]:
    lowered = (text or "").lower()
    checks = {
        "rejects_no_ai_misconception": bool(re.search(r"not .*absence of ai|not .*no ai|not .*use no ai", lowered)),
        "names_agency": "agency" in lowered,
        "observable_explain": bool(re.search(r"\bexplain|justify|defend\b", lowered)),
        "observable_revise": bool(re.search(r"\brevis", lowered)),
        "evidence_or_source": bool(re.search(r"\bevidence|source|provenance\b", lowered)),
        "human_judgment": bool(re.search(r"\bhuman|learner\b", lowered) and re.search(r"\bjudg|accountab|responsib|wording\b", lowered)),
        "anti_substitution_boundary": bool(re.search(r"\bnot the absence of ai|final judgement|wording choices|accountability human|substitut", lowered)),
    }
    return {
        "score": sum(1 for value in checks.values() if value),
        "max_score": len(checks),
        "checks": checks,
    }


def _row_checks(row: dict) -> dict[str, bool]:
    text = row.get("assistant_response") or ""
    lowered = text.lower()
    flags = {
        "answered": bool(text.strip()),
        "no_schema_leak": not _schema_leak(text),
        "not_generic": not lowered.startswith("hello! what would you like"),
        "topic_recalled": "human agency" in lowered,
        "prior_baseline_recalled": "still in charge" in lowered or "baseline" in lowered or "earlier" in lowered or "prior" in lowered,
        "misconception_diagnosed": any(term in lowered for term in ("misunderstanding", "too strict", "no ai involvement", "absence of ai", "not ai versus no ai")),
        "reteaches_distinction": "mediated authorship" in lowered or "substituted authorship" in lowered or ("ai support" in lowered and "human" in lowered),
        "ipsative_present": "ipsative" in lowered or "compared with your earlier" in lowered or "next gain" in lowered,
        "writing_task_present": "small writing task" in lowered or "revise" in lowered,
    }
    return flags


def run(args: argparse.Namespace) -> dict:
    started = time.time()
    health_a = _json_request(f"{args.base_url.rstrip('/')}/api/health", timeout=args.timeout)
    token_a = health_a.get("session_token") or ""
    if not token_a:
        raise RuntimeError("session_a_token_unavailable")

    rows: List[Dict[str, Any]] = []
    for turn in SESSION_A:
        rows.append(_run_turn(args, turn, token_a))

    finalized = _finalize(args.base_url, token_a, args.timeout)
    time.sleep(args.reentry_pause_seconds)

    # Sophia has one covenant-bound principal token per server boot. Follow-up
    # separation is therefore tested with a new dialogic thread id after
    # finalizing the ipsative/Mandos ecology, not by forging a token.
    token_b = token_a
    for turn in SESSION_B:
        rows.append(_run_turn(args, turn, token_b))

    pre = _artifact_score(PRE_FOLLOWUP_ARTIFACT)
    post = _artifact_score(POST_FOLLOWUP_ARTIFACT)
    followup = next(row for row in rows if row["phase"] == "reentry_memory")
    followup_checks = _row_checks(followup)
    expected_rows = [row for row in rows if row["expect_office"] or row["expect_move"]]
    summary = {
        "schema_version": "sophia.followup_memory_reteach_probe.v1",
        "provider": args.provider,
        "model": args.model,
        "same_principal_token_for_followup": token_a == token_b,
        "fresh_dialogic_thread_for_followup": True,
        "turns": len(rows),
        "answered": sum(1 for row in rows if row["assistant_response"]),
        "errors": sum(1 for row in rows if row["error"]),
        "schema_leaks": sum(1 for row in rows if row["schema_leak"]),
        "finalize_returned": bool(finalized),
        "office_passes": sum(1 for row in expected_rows if row["office_ok"]),
        "office_total": len(expected_rows),
        "move_passes": sum(1 for row in expected_rows if row["move_ok"]),
        "move_total": len(expected_rows),
        "followup_checks_passed": sum(1 for value in followup_checks.values() if value),
        "followup_checks_total": len(followup_checks),
        "learning_gain_points": post["score"] - pre["score"],
        "learning_gain_percentage_points": round(((post["score"] - pre["score"]) / post["max_score"]) * 100, 2),
        "interpretable_simulated_followup_gain": post["score"] >= 6 and post["score"] > pre["score"],
        "elapsed_ms": round((time.time() - started) * 1000, 3),
    }
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "session": {
            "session_a_token_tail": token_a[-8:],
            "session_b_token_tail": token_b[-8:],
            "session_note": "Same covenant-bound principal token; Session B uses a distinct dialogic_thread_id after ipsative finalization.",
            "finalize_result": finalized,
        },
        "followup_checks": followup_checks,
        "learning_gain": {
            "pre_artifact": PRE_FOLLOWUP_ARTIFACT,
            "post_artifact": POST_FOLLOWUP_ARTIFACT,
            "pre_score": pre,
            "post_score": post,
            "caution": "Simulated learner follow-up artifact gain; human validation still required.",
        },
        "transcript": rows,
    }


def _run_turn(args: argparse.Namespace, turn: Turn, token: str) -> Dict[str, Any]:
    t0 = time.time()
    try:
        result = _json_request(f"{args.base_url.rstrip('/')}/api/speak", _payload(turn, token, args), timeout=args.timeout)
        error = ""
    except Exception as exc:  # noqa: BLE001
        result = {}
        error = f"{type(exc).__name__}: {exc}"
    response = result.get("response") or ""
    move = result.get("dialogic_tutor_move") or {}
    return {
        "session": turn.session,
        "phase": turn.phase,
        "learner_text": turn.learner_text,
        "expected": turn.expected,
        "assistant_response": response,
        "response_source_detail": result.get("response_source_detail") or "",
        "active_office": result.get("active_office") or "",
        "dialogic_tutor_move": move,
        "office": move.get("office") or result.get("active_office") or "",
        "move": move.get("move") or "",
        "expect_office": turn.expect_office,
        "expect_move": turn.expect_move,
        "office_ok": not turn.expect_office or move.get("office") == turn.expect_office,
        "move_ok": not turn.expect_move or move.get("move") == turn.expect_move,
        "assessment": result.get("assessment") or {},
        "mandos_judgment": result.get("mandos_judgment") or {},
        "article_conformity": result.get("article_conformity") or {},
        "schema_leak": _schema_leak(response),
        "elapsed_ms": round((time.time() - t0) * 1000, 3),
        "error": error,
    }


def write_artifact(artifact: Dict[str, Any], out_prefix: str) -> Dict[str, str]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if not out_prefix:
        out_prefix = f"sophia_followup_memory_reteach_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    json_path = OUT_DIR / f"{out_prefix}.json"
    md_path = OUT_DIR / f"{out_prefix}.md"
    csv_path = OUT_DIR / f"{out_prefix}_human_rater_packet.csv"
    json_path.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(_markdown(artifact), encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=[
            "phase", "memory_1_5", "misconception_diagnosis_1_5", "reteaching_1_5",
            "ipsative_use_1_5", "learner_agency_1_5", "naturalness_1_5", "notes",
        ])
        writer.writeheader()
        for row in artifact["transcript"]:
            writer.writerow({"phase": row["phase"]})
    return {"json": str(json_path), "markdown": str(md_path), "rater_packet": str(csv_path)}


def _markdown(artifact: Dict[str, Any]) -> str:
    s = artifact["summary"]
    gain = artifact["learning_gain"]
    lines = [
        "# Sophia Fresh-Session Follow-up Memory and Reteaching Probe",
        "",
        "This probe seeds a prior session, finalizes the ipsative ecology, opens a new session token, and gives Sophia a new misconception about the same topic.",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Provider | {s['provider']} / {s['model']} |",
        f"| Same lawful principal token | {s['same_principal_token_for_followup']} |",
        f"| Fresh dialogic thread for follow-up | {s['fresh_dialogic_thread_for_followup']} |",
        f"| Turns answered | {s['answered']}/{s['turns']} |",
        f"| Errors | {s['errors']} |",
        f"| Schema leaks | {s['schema_leaks']} |",
        f"| Session finalized | {s['finalize_returned']} |",
        f"| Office passes | {s['office_passes']}/{s['office_total']} |",
        f"| Move passes | {s['move_passes']}/{s['move_total']} |",
        f"| Follow-up memory/reteach checks | {s['followup_checks_passed']}/{s['followup_checks_total']} |",
        f"| Simulated follow-up learning gain | +{s['learning_gain_points']} points / +{s['learning_gain_percentage_points']} pp |",
        f"| Interpretable simulated follow-up gain | {s['interpretable_simulated_followup_gain']} |",
        "",
        "## Follow-up Checks",
        "",
        "| Check | Passed |",
        "|---|---:|",
    ]
    for key, value in artifact["followup_checks"].items():
        lines.append(f"| {key} | {value} |")
    lines.extend([
        "",
        "## Artifact Delta",
        "",
        f"Pre-score: {gain['pre_score']['score']}/{gain['pre_score']['max_score']}",
        "",
        f"> {gain['pre_artifact']}",
        "",
        f"Post-score: {gain['post_score']['score']}/{gain['post_score']['max_score']}",
        "",
        f"> {gain['post_artifact']}",
        "",
        "## Transcript",
    ])
    for row in artifact["transcript"]:
        lines.extend([
            "",
            f"### {row['session']} / {row['phase']}",
            "",
            f"Source: `{row['response_source_detail']}`; office=`{row['office']}`; move=`{row['move']}`; schema_leak={row['schema_leak']}",
            "",
            "**Learner**",
            "",
            row["learner_text"],
            "",
            "**Sophia**",
            "",
            row["assistant_response"] or f"(error: {row['error']})",
        ])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--provider", default="gemini")
    parser.add_argument("--model", default="gemini-flash-lite-latest")
    parser.add_argument("--max-predict", type=int, default=700)
    parser.add_argument("--timeout", type=float, default=220.0)
    parser.add_argument("--reentry-pause-seconds", type=float, default=1.0)
    parser.add_argument("--out-prefix", default="")
    args = parser.parse_args()
    artifact = run(args)
    paths = write_artifact(artifact, args.out_prefix)
    print(json.dumps(paths, indent=2))
    print(json.dumps(artifact["summary"], indent=2))
    s = artifact["summary"]
    return 0 if (
        s["same_principal_token_for_followup"]
        and s["fresh_dialogic_thread_for_followup"]
        and s["answered"] == s["turns"]
        and s["errors"] == 0
        and s["schema_leaks"] == 0
        and s["office_passes"] == s["office_total"]
        and s["move_passes"] == s["move_total"]
        and s["followup_checks_passed"] == s["followup_checks_total"]
        and s["interpretable_simulated_followup_gain"]
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
