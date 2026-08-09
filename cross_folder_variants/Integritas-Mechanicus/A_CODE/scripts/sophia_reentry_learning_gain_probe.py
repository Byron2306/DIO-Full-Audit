#!/usr/bin/env python3
"""Re-entry learning-gain probe for Sophia.

The learner returns dissatisfied and uncertain after an earlier engagement. The
probe tests whether Sophia recalls the pedagogical thread, switches office
appropriately, and helps the learner produce a better concept artifact.
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
OUT_DIR = ROOT / "evidence" / "reentry_learning_gain_probe"
DEFAULT_BASE_URL = "http://localhost:7070"


DRAFT = """Higher-education responses to generative artificial intelligence remain dominated by disclosure, detection, assessment redesign, and post hoc enforcement.

This paper argues that academic integrity should be understood as a governed encounter in which AI systems preserve human agency, make provenance inspectable, and mediate learning rather than substitute for authorship.

The central risk is that universities evaluate whether AI was disclosed, but rarely inspect whether the AI interaction actually strengthened or displaced the learner's reasoning.
"""


@dataclass(frozen=True)
class Turn:
    phase: str
    learner_text: str
    expected: str
    selected_excerpt: str = ""
    document_text: str = ""
    source_task: bool = False
    expect_office: str = ""
    expect_move: str = ""
    expect_reentry: bool = False
    expect_boundary: bool = False


SCRIPT = [
    Turn(
        phase="dialogic_open",
        learner_text="Sophia, teach me human agency for my Fides paper over a few turns. One question at a time.",
        expected="start dialogic lesson and establish baseline",
        expect_office="maieuticus",
        expect_move="baseline_probe",
    ),
    Turn(
        phase="dialogic_baseline",
        learner_text="I think human agency means the student is still in charge.",
        expected="diagnose vague baseline",
        expect_office="maieuticus",
        expect_move="indicator_selection",
    ),
    Turn(
        phase="dialogic_choice",
        learner_text="Revision and responsibility matter most, I think.",
        expected="move learner toward observable draft",
        expect_office="constructor",
        expect_move="draft_attempt",
    ),
    Turn(
        phase="dialogic_draft",
        learner_text="Human agency is preserved when the learner can revise and take responsibility instead of accepting AI output.",
        expected="criterion check of learner draft",
        selected_excerpt=DRAFT,
        document_text=DRAFT,
        expect_office="dialecticus",
        expect_move="criterion_check",
    ),
    Turn(
        phase="source_retrieval",
        learner_text="Find recent sources for human agency, AI literacy, academic integrity, and higher education.",
        expected="source leads for later fit inspection",
        source_task=True,
    ),
    Turn(
        phase="reentry_uncertainty",
        learner_text=(
            "Sophia, I came back because honestly I was not happy after the previous engagement. "
            "I am still uncertain what exactly I can claim about human agency without overclaiming or hiding AI help."
        ),
        expected="affective re-entry, uncertainty diagnosis, office switch before content",
        expect_office="affectus",
        expect_move="affective_reentry_diagnosis",
        expect_reentry=True,
    ),
    Turn(
        phase="dialogic_uncertainty_answer",
        learner_text="The boundary bothers me most: what is my wording, what is source support, and what is AI help?",
        expected="switch from affective regulation to source/boundary pedagogy",
        expect_office="source_librarian",
        expect_move="source_fit_probe",
        expect_reentry=True,
    ),
    Turn(
        phase="post_artifact",
        learner_text=(
            "Here is my improved attempt: Human agency is preserved when the learner can explain the claim, "
            "revise it using source feedback, and take responsibility for the final judgement; this shows accountable authorship, "
            "but it does not by itself prove learning outcomes or institutional scalability."
        ),
        expected="recognize improved operational definition and ask next evidence-fit move",
        selected_excerpt=DRAFT,
        document_text=DRAFT,
        expect_office="dialecticus",
        expect_move="criterion_check",
        expect_reentry=True,
    ),
]


PRE_ARTIFACT = "Human agency means the student is still in charge."
POST_ARTIFACT = SCRIPT[-1].learner_text.replace("Here is my improved attempt: ", "")


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
    if not turn.document_text and not turn.selected_excerpt:
        return []
    text = turn.document_text or turn.selected_excerpt
    return [{
        "source_name": "fides-human-agency-reentry.md",
        "source_path": "fides-human-agency-reentry.md",
        "mime_type": "text/markdown",
        "modality": "live_editing_text",
        "parser": "reentry_learning_gain_probe",
        "extracted_text": text,
        "spans": [{"span_id": turn.phase, "quote": text[:1200]}],
    }]


def _payload(turn: Turn, token: str, args: argparse.Namespace) -> dict[str, Any]:
    return {
        "text": turn.learner_text,
        "session_token": token,
        "reasoned_integrity_lane": True,
        "reasoned_provider": args.provider,
        "reasoned_model": args.model,
        "reasoned_max_predict": args.max_predict,
        "document_evidence_task": "reentry_learning_gain_probe",
        "document_uploads": _document_upload(turn),
        "client_context": {
            "ui_surface": "lesson_dialogue",
            "experiment_phase": turn.phase,
            "response_mode": "conversational_specific" if turn.source_task else "dialogic_tutor",
            "expected_function": turn.expected,
            "learner_affect": "dissatisfied_uncertain" if turn.phase == "reentry_uncertainty" else "",
        },
        "risk_family": "learning_support",
    }


def _schema_leak(text: str) -> bool:
    return bool(re.search(r"Pedagogical move:|Diagnostic question:|Formative move:|Ipsative check:|Constitutional repair:|Genesis conformity note:|schema route", text or "", re.I))


def _artifact_score(text: str) -> Dict[str, Any]:
    lowered = (text or "").lower()
    checks = {
        "names_agency": "agency" in lowered,
        "observable_explain": bool(re.search(r"\bexplain|justify|defend\b", lowered)),
        "observable_revise": bool(re.search(r"\brevis", lowered)),
        "accountability": bool(re.search(r"\bresponsib|accountab|authorship|judgement|judgment\b", lowered)),
        "source_or_evidence": bool(re.search(r"\bsource|evidence|feedback|provenance\b", lowered)),
        "limitation": bool(re.search(r"\bdoes not|not by itself|limitation|scope|not yet|without overclaim", lowered)),
        "anti_substitution": bool(re.search(r"\baccepting ai output|hiding ai|ai help|authorship\b", lowered)),
    }
    score = sum(1 for value in checks.values() if value)
    return {
        "score": score,
        "max_score": len(checks),
        "percentage": round(score / len(checks), 4),
        "checks": checks,
    }


def _learning_gain(pre: str, post: str) -> Dict[str, Any]:
    pre_score = _artifact_score(pre)
    post_score = _artifact_score(post)
    return {
        "pre_artifact": pre,
        "post_artifact": post,
        "pre_score": pre_score,
        "post_score": post_score,
        "gain_points": post_score["score"] - pre_score["score"],
        "gain_percentage_points": round((post_score["percentage"] - pre_score["percentage"]) * 100, 2),
        "interpretable_gain": post_score["score"] > pre_score["score"] and post_score["score"] >= 6,
        "caution": "This is simulated learner-artifact gain, not proof of human classroom learning.",
    }


def run(args: argparse.Namespace) -> Dict[str, Any]:
    started = time.time()
    health = _json_request(f"{args.base_url.rstrip('/')}/api/health", timeout=args.timeout)
    token = health.get("session_token") or ""
    if not token:
        raise RuntimeError("session_token_unavailable")
    rows: List[Dict[str, Any]] = []
    for turn in SCRIPT:
        if turn.phase == "reentry_uncertainty":
            time.sleep(args.reentry_pause_seconds)
        t0 = time.time()
        try:
            result = _json_request(f"{args.base_url.rstrip('/')}/api/speak", _payload(turn, token, args), timeout=args.timeout)
            error = ""
        except Exception as exc:  # noqa: BLE001
            result = {}
            error = f"{type(exc).__name__}: {exc}"
        response = result.get("response") or ""
        move = result.get("dialogic_tutor_move") or {}
        rows.append({
            "phase": turn.phase,
            "learner_text": turn.learner_text,
            "expected": turn.expected,
            "assistant_response": response,
            "response_source_detail": result.get("response_source_detail") or "",
            "dialogic_tutor_move": move,
            "office": move.get("office") or "",
            "move": move.get("move") or "",
            "office_ok": not turn.expect_office or move.get("office") == turn.expect_office,
            "move_ok": not turn.expect_move or move.get("move") == turn.expect_move,
            "reentry_signal": bool(re.search(r"\bprevious|came back|unhappy|uncertain|not happy|bothering|last\b", response, re.I)),
            "schema_leak": _schema_leak(response),
            "word_count": len(re.findall(r"\w+", response)),
            "question_count": response.count("?"),
            "error": error,
            "elapsed_ms": round((time.time() - t0) * 1000, 3),
        })
    learning = _learning_gain(PRE_ARTIFACT, POST_ARTIFACT)
    expected_rows = [row for row in rows if row["phase"] != "source_retrieval"]
    summary = {
        "schema_version": "sophia.reentry_learning_gain_probe.v1",
        "provider": args.provider,
        "model": args.model,
        "turns": len(rows),
        "answered": sum(1 for row in rows if row["assistant_response"]),
        "errors": sum(1 for row in rows if row["error"]),
        "schema_leaks": sum(1 for row in rows if row["schema_leak"]),
        "office_switch_passes": sum(1 for row in expected_rows if row["office_ok"]),
        "office_switch_total": len(expected_rows),
        "move_passes": sum(1 for row in expected_rows if row["move_ok"]),
        "move_total": len(expected_rows),
        "reentry_uncertainty_office": next((row["office"] for row in rows if row["phase"] == "reentry_uncertainty"), ""),
        "learning_gain_points": learning["gain_points"],
        "learning_gain_percentage_points": learning["gain_percentage_points"],
        "interpretable_simulated_gain": learning["interpretable_gain"],
        "elapsed_ms": round((time.time() - started) * 1000, 3),
    }
    return {
        "summary": summary,
        "health": health,
        "learning_gain": learning,
        "transcript": rows,
    }


def write_artifact(artifact: Dict[str, Any], out_prefix: str) -> Dict[str, str]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if not out_prefix:
        out_prefix = f"sophia_reentry_learning_gain_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    json_path = OUT_DIR / f"{out_prefix}.json"
    md_path = OUT_DIR / f"{out_prefix}.md"
    csv_path = OUT_DIR / f"{out_prefix}_human_rater_packet.csv"
    json_path.write_text(json.dumps(artifact, indent=2, ensure_ascii=False), encoding="utf-8")
    s = artifact["summary"]
    gain = artifact["learning_gain"]
    lines = [
        "# Sophia Re-entry Learning-Gain Probe",
        "",
        "This is a simulated learner-artifact gain probe. It does not prove human classroom learning by itself.",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Provider | {s['provider']} / {s['model']} |",
        f"| Turns answered | {s['answered']}/{s['turns']} |",
        f"| Errors | {s['errors']} |",
        f"| Schema leaks | {s['schema_leaks']} |",
        f"| Office switch passes | {s['office_switch_passes']}/{s['office_switch_total']} |",
        f"| Move passes | {s['move_passes']}/{s['move_total']} |",
        f"| Re-entry uncertainty office | {s['reentry_uncertainty_office']} |",
        f"| Learning gain | +{s['learning_gain_points']} points / +{s['learning_gain_percentage_points']} pp |",
        f"| Interpretable simulated gain | {s['interpretable_simulated_gain']} |",
        "",
        "## Learner Artifact Gain",
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
    ]
    for row in artifact["transcript"]:
        lines.extend([
            "",
            f"### {row['phase']}",
            "",
            f"Source: `{row['response_source_detail']}`; office=`{row['office']}`; move=`{row['move']}`; office_ok={row['office_ok']}; move_ok={row['move_ok']}; schema_leak={row['schema_leak']}",
            "",
            "**Learner**",
            "",
            row["learner_text"],
            "",
            "**Sophia**",
            "",
            row["assistant_response"] or f"(error: {row['error']})",
        ])
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=[
            "phase", "naturalness_1_5", "office_fit_1_5", "learning_support_1_5",
            "uncertainty_response_1_5", "artifact_gain_plausible_y_n", "notes",
        ])
        writer.writeheader()
        for row in artifact["transcript"]:
            writer.writerow({"phase": row["phase"]})
    return {"json": str(json_path), "markdown": str(md_path), "rater_packet": str(csv_path)}


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
        s["errors"] == 0
        and s["schema_leaks"] == 0
        and s["office_switch_passes"] == s["office_switch_total"]
        and s["move_passes"] == s["move_total"]
        and s["interpretable_simulated_gain"]
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
