#!/usr/bin/env python3
"""Blinded learner-production gauntlet for Sophia.

Unlike the follow-up scripted gain probes, this harness does not predefine the
post artifact. It supplies an unseen pre-artifact, obtains an intervention from
one condition, then asks a separate learner simulator to produce the post
artifact from the intervention. The output is packaged for blinded human rating.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import random
import re
import sys
import time
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "evidence" / "blinded_learner_production_gauntlet"
DEFAULT_BASE_URL = "http://localhost:7070"
if str(ROOT / "arda_os") not in sys.path:
    sys.path.insert(0, str(ROOT / "arda_os"))

try:
    from backend.services.presence_server import remote_chat_generate  # type: ignore
except Exception:  # pragma: no cover
    remote_chat_generate = None  # type: ignore[assignment]


@dataclass(frozen=True)
class ConceptCase:
    case_id: str
    concept_label: str
    paper_context: str
    misconception_artifact: str
    target_features: tuple[str, ...]
    hidden_cause: str = ""
    learner_profile: str = "novice_unsure"
    transfer_task: str = ""


@dataclass(frozen=True)
class LearnerProfile:
    profile_id: str
    description: str
    affect: str
    prior_knowledge: str
    hidden_cause: str
    likely_failure_mode: str


CASES = [
    ConceptCase(
        case_id="C1_human_agency",
        concept_label="human agency in AI academic-integrity writing",
        paper_context="A paper argues that AI academic-integrity governance should preserve learner agency without banning all AI mediation.",
        misconception_artifact="Human agency means the student should use no AI at all, because any AI help removes the student's agency.",
        target_features=("not absence of AI", "explain", "revise", "evidence", "accountability", "human judgment"),
        hidden_cause="Learner treats agency as purity from tools rather than accountable control over reasoning.",
        learner_profile="novice_unsure",
        transfer_task="A learner uses AI to compare two outlines, rejects one, revises the other, and explains why. Is agency necessarily lost?",
    ),
    ConceptCase(
        case_id="C2_feedback_literacy",
        concept_label="feedback literacy in AI-supported writing",
        paper_context="A paper discusses how learners use feedback from teachers, sources, and AI systems while retaining responsibility for revision.",
        misconception_artifact="Feedback literacy means accepting the best feedback quickly, especially when the AI suggestion sounds more academic than mine.",
        target_features=("evaluate feedback", "learner judgment", "revise", "criteria", "not automatic acceptance"),
        hidden_cause="Learner confuses fluent feedback with valid feedback and needs criteria-based evaluation.",
        learner_profile="correct_reasoning_poor_expression",
        transfer_task="An AI gives a smoother paragraph that weakens the evidence. What should a feedback-literate writer do?",
    ),
    ConceptCase(
        case_id="C3_construct_validity",
        concept_label="construct validity in AI-era assessment",
        paper_context="A paper claims universities must assess the intended construct rather than only detect whether AI was used.",
        misconception_artifact="Construct validity means the assessment is valid if it catches AI use and prevents cheating.",
        target_features=("intended construct", "evidence", "assessment inference", "not detection only", "limitations"),
        hidden_cause="Learner collapses integrity enforcement into measurement quality.",
        learner_profile="polished_expression_faulty_reasoning",
        transfer_task="A viva detects AI use well but cannot show whether students understand the concept. Is the assessment construct-valid?",
    ),
    ConceptCase(
        case_id="C4_source_provenance",
        concept_label="source provenance in academic argument",
        paper_context="A paper argues that source trails should make evidence, inference, and limitation inspectable.",
        misconception_artifact="Source provenance means having enough citations in the paragraph so the claim looks well supported.",
        target_features=("traceable source", "claim support", "warrant", "limitation", "not citation density"),
        hidden_cause="Learner mistakes citation density for inspectable evidence trails.",
        learner_profile="knowledgeable_confused",
        transfer_task="A paragraph has eight citations but none directly support the causal claim. Is provenance strong?",
    ),
    ConceptCase(
        case_id="C5_transfer",
        concept_label="transfer of learning in academic writing",
        paper_context="A paper discusses whether learners can reuse a reasoning strategy across new writing tasks.",
        misconception_artifact="Transfer means I can copy the same definition template into another paper if the topic is similar.",
        target_features=("adapt strategy", "new context", "conditions", "not copying", "reflection"),
        hidden_cause="Learner confuses template reuse with conditional strategy adaptation.",
        learner_profile="novice_overconfident",
        transfer_task="A learner moves from AI-integrity writing to assessment design. What would count as transfer rather than repetition?",
    ),
    ConceptCase(
        case_id="C6_epistemic_humility",
        concept_label="epistemic humility in AI-supported scholarship",
        paper_context="A paper argues that AI-supported scholarship must distinguish evidence, inference, uncertainty, and unknowns.",
        misconception_artifact="Epistemic humility means adding a limitations sentence so reviewers know I am careful.",
        target_features=("uncertainty", "evidence limit", "calibrated claim", "unknowns", "not cosmetic limitation"),
        hidden_cause="Learner treats humility as rhetorical hedging rather than calibrated knowledge control.",
        learner_profile="expert_seeking_challenge",
        transfer_task="A paper reports perfect protocol scores but no classroom outcome data. What would epistemic humility require?",
    ),
]


SAME_SURFACE_CASES = [
    ConceptCase(
        case_id="C7A_same_surface_accountability",
        concept_label="human agency in AI academic-integrity writing",
        paper_context="A paper argues that disclosure is necessary but insufficient for preserving agency in AI-supported academic work.",
        misconception_artifact="Using AI preserves agency as long as the student discloses it.",
        target_features=("disclosure insufficient", "accountability", "explain", "revise", "evidence"),
        hidden_cause="Learner understands accountability but confuses disclosure with sufficient evidence.",
        learner_profile="knowledgeable_confused",
        transfer_task="A student discloses AI use but cannot explain why the final claim follows from the sources. Is agency preserved?",
    ),
    ConceptCase(
        case_id="C7B_same_surface_authorship",
        concept_label="human agency in AI academic-integrity writing",
        paper_context="A paper argues that disclosure is necessary but insufficient for preserving agency in AI-supported academic work.",
        misconception_artifact="Using AI preserves agency as long as the student discloses it.",
        target_features=("authorship", "judgment", "responsibility", "not checklist", "explain"),
        hidden_cause="Learner treats authorship as moral compliance with a checklist and does not understand judgment ownership.",
        learner_profile="novice_overconfident",
        transfer_task="A student uses a fully disclosed AI paragraph, agrees with it, but cannot reproduce the reasoning. Is agency preserved?",
    ),
]


LEARNER_PROFILES = {
    "novice_unsure": LearnerProfile("novice_unsure", "Novice and unsure", "low confidence, mild anxiety", "fragmentary", "concept compressed into surface rule", "asks for reassurance"),
    "novice_overconfident": LearnerProfile("novice_overconfident", "Novice and overconfident", "high confidence, low monitoring", "shallow", "moral checklist replaces conceptual reasoning", "resists nuance"),
    "knowledgeable_confused": LearnerProfile("knowledgeable_confused", "Knowledgeable but conceptually confused", "moderate confidence, genuine uncertainty", "partial", "nearby constructs are conflated", "uses correct words with wrong relation"),
    "expert_seeking_challenge": LearnerProfile("expert_seeking_challenge", "Expert seeking challenge", "stable confidence", "advanced", "needs counterexample and qualification", "overcompresses edge cases"),
    "frustrated_returning": LearnerProfile("frustrated_returning", "Frustrated returning learner", "frustrated but persistent", "partial", "prior scaffold did not resolve boundary", "needs affective re-entry plus reteach"),
    "correct_reasoning_poor_expression": LearnerProfile("correct_reasoning_poor_expression", "Correct reasoning but poor expression", "moderate confidence", "emerging", "expression obscures reasoning", "needs constructor/writing scaffold"),
    "polished_expression_faulty_reasoning": LearnerProfile("polished_expression_faulty_reasoning", "Polished expression but faulty reasoning", "high confidence", "fragile", "surface polish masks conceptual error", "needs dialectical challenge"),
}


CONDITIONS = {
    "plain_generic_remote_tutor": {"plain_generic_remote": True},
    "generic_remote_tutor": {"generic_remote": True},
    "pedagogy_matched_remote_tutor": {"pedagogy_matched_remote": True},
    "sophia_runtime_full": {"full_runtime": True},
    "sophia_full": {},
    "sophia_telemetry_recorded_not_used": {"telemetry_recorded_not_used": True},
    "sophia_pedagogy_no_mandos_assessment": {"disable_mandos_assessment_control": True},
    "sophia_no_memory": {"disable_continuity_memory": True, "disable_memory_reentry_fallback": True},
    "sophia_no_document": {"disable_document_evidence": True},
    "baseline_remote_tutor": {"baseline_remote": True},
}


def _load_env(path: str) -> list[str]:
    if not path:
        return []
    p = Path(path).expanduser()
    if not p.exists():
        return []
    loaded = []
    for raw in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip().removeprefix("export ").strip()
        v = v.strip().strip('"').strip("'")
        if k and v and k not in os.environ:
            os.environ[k] = v
            loaded.append(k)
    return loaded


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


def _hash(value: Any, n: int = 16) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:n]


def _document_upload(case: ConceptCase) -> list[dict[str, Any]]:
    text = f"{case.paper_context}\n\nCurrent learner artifact:\n{case.misconception_artifact}"
    return [{
        "source_name": f"{case.case_id}-learner-artifact.md",
        "source_path": f"{case.case_id}-learner-artifact.md",
        "mime_type": "text/markdown",
        "modality": "live_editing_text",
        "parser": "blinded_learner_production_gauntlet",
        "extracted_text": text,
        "spans": [{"span_id": case.case_id, "quote": text[:1200]}],
    }]


def _diagnostic_prompt(case: ConceptCase) -> str:
    return (
        f"A learner is writing about {case.concept_label}.\n\n"
        f"Paper context: {case.paper_context}\n\n"
        f"Learner's current attempt:\n{case.misconception_artifact}\n\n"
        "Ask exactly one discriminating diagnostic question that would help reveal why the learner holds this misconception. "
        "Do not teach yet. Do not reveal a diagnosis. Do not mention hidden profiles."
    )


def _intervention_prompt(case: ConceptCase, diagnostic_exchange: Optional[dict[str, str]] = None, reveal_hidden: bool = False) -> str:
    profile = LEARNER_PROFILES.get(case.learner_profile)
    profile_hint = ""
    if reveal_hidden and profile:
        profile_hint = (
            f"\nHidden learner profile for this trial: {profile.description}; affect={profile.affect}; "
            f"prior_knowledge={profile.prior_knowledge}; hidden_cause={case.hidden_cause or profile.hidden_cause}; "
            f"likely_failure_mode={profile.likely_failure_mode}.\n"
        )
    diagnostic_hint = ""
    if diagnostic_exchange:
        diagnostic_hint = (
            "\nDiagnostic turn already completed:\n"
            f"Tutor question: {diagnostic_exchange.get('question', '').strip()}\n"
            f"Learner answer: {diagnostic_exchange.get('answer', '').strip()}\n\n"
        )
    return (
        f"A learner is writing about {case.concept_label}.\n\n"
        f"Paper context: {case.paper_context}\n\n"
        f"Learner's current attempt:\n{case.misconception_artifact}\n\n"
        f"{profile_hint}"
        f"{diagnostic_hint}"
        "Diagnose the misconception and teach toward a better second attempt. "
        "Use the diagnostic answer if available; if still ambiguous, name what remains uncertain and ask one follow-up question before reteaching. "
        "Choose a pedagogical office implicitly through behavior: maieutic questioning, dialectical counterexample, constructor scaffold, affective re-entry, expert challenge, source constraint, or integrity audit. "
        "Use scaffold fading: modelled, prompted, cued, or independent. "
        "Do not write the final answer for the learner. Give a compact scaffold and one learner-owned revision task."
    )


def _presence_payload(
    case: ConceptCase,
    condition: str,
    token: str,
    args: argparse.Namespace,
    text: Optional[str] = None,
    diagnostic_exchange: Optional[dict[str, str]] = None,
) -> dict[str, Any]:
    flags = dict(CONDITIONS[condition])
    flags.pop("baseline_remote", None)
    flags.pop("generic_remote", None)
    flags.pop("plain_generic_remote", None)
    flags.pop("pedagogy_matched_remote", None)
    full_runtime = bool(flags.pop("full_runtime", False))
    experiment_phase = "full_runtime_learner_production" if full_runtime else "learner_production_intervention"
    response_mode = "full_runtime_adaptive_pedagogy" if full_runtime else "adaptive_pedagogical_intervention"
    return {
        "text": text or _intervention_prompt(case, diagnostic_exchange=diagnostic_exchange),
        "session_token": token,
        "reasoned_integrity_lane": True,
        "reasoned_provider": args.provider,
        "reasoned_model": args.model,
        "reasoned_max_predict": args.max_predict,
        "document_evidence_task": "blinded_learner_production_gauntlet",
        "document_uploads": _document_upload(case) if args.attach_document and not flags.get("disable_document_evidence") else [],
        "client_context": {
            "ui_surface": "learner_production_gauntlet",
            "experiment_phase": experiment_phase,
            "response_mode": response_mode,
            "learner_id": "simulated_blinded_learner",
            "project_id": f"{case.case_id}_project",
            "concept_id": case.concept_label.lower().replace(" ", "_"),
            "dialogic_thread_parent": f"{case.case_id}_production_study",
            "expected_function": "diagnose misconception, adapt office, fade scaffold, preserve learner authorship, prepare transfer",
        },
        "risk_family": "learning_support",
        "suppress_academic_retrieval_fastpaths": True,
        **flags,
    }


def _get_presence_response(
    case: ConceptCase,
    condition: str,
    token: str,
    args: argparse.Namespace,
    text: str,
    diagnostic_exchange: Optional[dict[str, str]] = None,
) -> dict[str, Any]:
    started = time.time()
    try:
        result = _json_request(
            f"{args.base_url.rstrip('/')}/api/speak",
            _presence_payload(case, condition, token, args, text=text, diagnostic_exchange=diagnostic_exchange),
            timeout=args.timeout,
        )
        error = ""
    except Exception as exc:  # noqa: BLE001
        result = {}
        error = f"{type(exc).__name__}: {exc}"
    return {
        "condition": condition,
        "response": result.get("response") or "",
        "response_source_detail": result.get("response_source_detail") or "",
        "provider": result.get("reasoned_provider") or args.provider,
        "model": result.get("model") or args.model,
        "active_office": result.get("active_office"),
        "mandos_context": result.get("mandos_context"),
        "assessment": result.get("assessment"),
        "pedagogy_control": result.get("pedagogy_control"),
        "response_release_ledger": result.get("response_release_ledger"),
        "mandos_passed": (result.get("mandos_judgment") or {}).get("passed"),
        "mandos_judgment": result.get("mandos_judgment"),
        "article_all_passed": ((result.get("article_conformity") or {}).get("summary") or {}).get("all_passed"),
        "article_conformity": result.get("article_conformity"),
        "condition_flags": result.get("condition_flags"),
        "pedagogical_attribution": result.get("pedagogical_attribution"),
        "repair_steps": result.get("repair_steps") or [],
        "error": error,
        "elapsed_ms": round((time.time() - started) * 1000, 3),
    }


def _get_intervention(
    case: ConceptCase,
    condition: str,
    token: str,
    args: argparse.Namespace,
    diagnostic_exchange: Optional[dict[str, str]] = None,
) -> dict[str, Any]:
    started = time.time()
    if any(CONDITIONS[condition].get(k) for k in ("baseline_remote", "generic_remote", "plain_generic_remote", "pedagogy_matched_remote")):
        text = _remote_tutor_intervention(case, condition, args, diagnostic_exchange=diagnostic_exchange)
        return {
            "condition": condition,
            "response": text["response"],
            "response_source_detail": text["source"],
            "provider": text["provider"],
            "model": text["model"],
            "error": text.get("error", ""),
            "elapsed_ms": round((time.time() - started) * 1000, 3),
        }
    return _get_presence_response(
        case,
        condition,
        token,
        args,
        _intervention_prompt(case, diagnostic_exchange=diagnostic_exchange),
        diagnostic_exchange=diagnostic_exchange,
    )


def _remote_tutor_intervention(
    case: ConceptCase,
    condition: str,
    args: argparse.Namespace,
    diagnostic_exchange: Optional[dict[str, str]] = None,
) -> dict[str, str]:
    if remote_chat_generate is None:
        return {
            "response": _fallback_generic_tutor(case),
            "source": "fallback_generic_tutor",
            "provider": "fallback",
            "model": "deterministic",
            "error": "remote_chat_generate_unavailable",
        }
    if CONDITIONS[condition].get("pedagogy_matched_remote"):
        system = (
            "You are an academic writing tutor using strong learning-science pedagogy: diagnose misconception, "
            "ask discriminating questions when uncertain, use calibrated scaffolding, preserve authorship, and prepare transfer. "
            "Do not use Sophia's constitution, Mandos memory, runtime offices, document engine, or covenant architecture."
        )
        prompt = _intervention_prompt(case, diagnostic_exchange=diagnostic_exchange)
        source = "pedagogy_matched_remote_tutor"
    elif CONDITIONS[condition].get("plain_generic_remote"):
        system = (
            "You are a helpful academic writing tutor. Respond naturally and briefly. "
            "Help the learner improve their understanding without writing the learner's final answer."
        )
        diagnostic_hint = ""
        if diagnostic_exchange:
            diagnostic_hint = (
                "\nA previous tutor question and learner answer are available:\n"
                f"Question: {diagnostic_exchange.get('question', '').strip()}\n"
                f"Answer: {diagnostic_exchange.get('answer', '').strip()}\n"
            )
        prompt = (
            f"The learner is writing about {case.concept_label}.\n\n"
            f"Context: {case.paper_context}\n\n"
            f"Learner draft:\n{case.misconception_artifact}\n"
            f"{diagnostic_hint}\n"
            "Help the learner make a better second attempt."
        )
        source = "plain_generic_remote_tutor"
    else:
        system = (
            "You are a task-matched academic writing tutor. Help the learner improve their concept definition. "
            "Be useful, but do not use Sophia's constitution, Mandos memory, or compiled pedagogy."
        )
        prompt = _intervention_prompt(case, diagnostic_exchange=diagnostic_exchange)
        source = "generic_remote_tutor" if CONDITIONS[condition].get("generic_remote") else "baseline_remote_tutor"
    result = remote_chat_generate(
        prompt,
        system_prompt=system,
        provider=args.baseline_provider,
        model=args.baseline_model,
        max_predict=args.max_predict,
        temperature=0.35,
    )
    if result.get("status") == "ok" and str(result.get("response") or "").strip():
        return {
            "response": str(result.get("response") or "").strip(),
            "source": source,
            "provider": args.baseline_provider,
            "model": args.baseline_model,
        }
    return {
        "response": _fallback_generic_tutor(case),
        "source": "fallback_generic_tutor",
        "provider": args.baseline_provider,
        "model": args.baseline_model,
        "error": str(result.get("error") or "baseline_unavailable"),
    }


def _remote_diagnostic_question(case: ConceptCase, condition: str, token: str, args: argparse.Namespace) -> dict[str, Any]:
    if condition.startswith("sophia_"):
        return _get_presence_response(case, condition, token, args, _diagnostic_prompt(case))
    if remote_chat_generate is None:
        return {"response": "What makes you think this is the main issue?", "response_source_detail": "fallback_diagnostic"}
    if CONDITIONS[condition].get("pedagogy_matched_remote"):
        system = "Ask one discriminating diagnostic question before tutoring. No teaching yet."
    else:
        system = "Ask one brief clarifying question before tutoring. No teaching yet."
    result = remote_chat_generate(
        _diagnostic_prompt(case),
        system_prompt=system,
        provider=args.baseline_provider,
        model=args.baseline_model,
        max_predict=120,
        temperature=0.25,
    )
    return {
        "response": str(result.get("response") or "What makes you think this?").strip(),
        "response_source_detail": "diagnostic_question_remote",
        "provider": args.baseline_provider,
        "model": args.baseline_model,
        "error": str(result.get("error") or ""),
    }


def _learner_answer_diagnostic(case: ConceptCase, question: str, args: argparse.Namespace) -> dict[str, str]:
    profile = LEARNER_PROFILES.get(case.learner_profile)
    prompt = (
        "You are simulating the learner answering a tutor's diagnostic question. "
        "Answer in the learner's voice in 1-2 sentences. Do not reveal that you are simulated. "
        "Do not repeat the hidden cause wording; transform it into what this learner would naturally say.\n\n"
        f"Learner profile: {profile.description if profile else case.learner_profile}\n"
        f"Hidden cause: {case.hidden_cause or (profile.hidden_cause if profile else '')}\n"
        f"Original attempt: {case.misconception_artifact}\n"
        f"Tutor question: {question}\n\n"
        "Learner answer:"
    )
    if remote_chat_generate is not None:
        result = remote_chat_generate(
            prompt,
            system_prompt="You are only the learner. Answer the diagnostic question naturally.",
            provider=args.learner_provider,
            model=args.learner_model,
            max_predict=140,
            temperature=0.58,
        )
        text = str(result.get("response") or "").strip()
        if result.get("status") == "ok" and text:
            cleaned = _clean_artifact(text)
            if case.hidden_cause and _token_overlap(case.hidden_cause, cleaned) > 0.72:
                cleaned = _natural_hidden_cause_answer(case)
            return {"answer": cleaned, "source": "remote_learner_model"}
    return {"answer": case.hidden_cause or "I thought the surface rule was enough.", "source": "deterministic_fallback_learner"}


def _natural_hidden_cause_answer(case: ConceptCase) -> str:
    lowered = (case.hidden_cause or "").lower()
    if "fluent" in lowered or "valid feedback" in lowered:
        return "I guess I tend to trust the version that sounds more polished, because it feels like that must be the better feedback."
    if "disclosure" in lowered:
        return "I thought that if the student is honest about using AI, that honesty shows they are still responsible for the work."
    if "checklist" in lowered:
        return "I was treating authorship like following the rule correctly, not really thinking about who owned the reasoning."
    if "citation density" in lowered:
        return "I thought more citations made the evidence trail stronger, even if I had not checked exactly which claim each source supports."
    return "I was relying on the surface rule because it seemed like the safest way to explain the idea."


def _fallback_generic_tutor(case: ConceptCase) -> str:
    return (
        f"Your current definition of {case.concept_label} is too narrow. "
        "Revise it by naming what the concept is, what it is not, and one example. "
        "Make sure your wording is clear and your claim is not too broad."
    )


def _produce_post_artifact(case: ConceptCase, intervention: str, args: argparse.Namespace) -> dict[str, str]:
    prompt = (
        "You are simulating a postgraduate learner after receiving tutoring. "
        "Write only the learner's revised concept artifact in 1-2 sentences. "
        "Do not copy the tutor verbatim; produce the learner's own second attempt.\n\n"
        f"Concept: {case.concept_label}\n"
        f"Paper context: {case.paper_context}\n"
        f"Original attempt: {case.misconception_artifact}\n\n"
        f"Tutor intervention:\n{intervention[:2400]}\n\n"
        "Learner revised artifact:"
    )
    if remote_chat_generate is not None:
        result = remote_chat_generate(
            prompt,
            system_prompt="You are only the learner. Output only the revised artifact.",
            provider=args.learner_provider,
            model=args.learner_model,
            max_predict=args.learner_max_predict,
            temperature=0.55,
        )
        text = str(result.get("response") or "").strip()
        if result.get("status") == "ok" and text:
            return {
                "artifact": _clean_artifact(text),
                "source": "remote_learner_model",
                "provider": args.learner_provider,
                "model": args.learner_model,
            }
    return {
        "artifact": _fallback_revised_artifact(case, intervention),
        "source": "deterministic_fallback_learner",
        "provider": "fallback",
        "model": "heuristic",
    }


def _produce_transfer_artifact(case: ConceptCase, post_artifact: str, intervention: str, args: argparse.Namespace) -> dict[str, str]:
    task = case.transfer_task or _default_transfer_task(case)
    if args.unaided_transfer:
        return _produce_unaided_transfer_artifact(case, intervention, args)
    prompt = (
        "You are simulating the same learner on a novel transfer task after tutoring. "
        "Write only the learner's independent answer in 2-3 sentences. "
        "Do not ask the tutor for help and do not use a sentence frame.\n\n"
        f"Original concept: {case.concept_label}\n"
        f"Earlier revised artifact: {post_artifact}\n"
        f"Novel transfer task: {task}\n\n"
        "Independent learner answer:"
    )
    if remote_chat_generate is not None:
        result = remote_chat_generate(
            prompt,
            system_prompt="You are only the learner completing an independent transfer task.",
            provider=args.learner_provider,
            model=args.learner_model,
            max_predict=args.learner_max_predict,
            temperature=0.58,
        )
        text = str(result.get("response") or "").strip()
        if result.get("status") == "ok" and text:
            return {
                "artifact": _clean_artifact(text),
                "task": task,
                "source": "remote_learner_model",
                "provider": args.learner_provider,
                "model": args.learner_model,
            }
    return {
        "artifact": _fallback_transfer_artifact(case, post_artifact),
        "task": task,
        "source": "deterministic_fallback_learner",
        "provider": "fallback",
        "model": "heuristic",
    }


def _produce_unaided_transfer_artifact(case: ConceptCase, intervention: str, args: argparse.Namespace) -> dict[str, str]:
    task = case.transfer_task or _default_transfer_task(case)
    prompt = (
        "You are simulating the same learner later, after a short distractor task. "
        "The learner remembers the tutoring imperfectly, but cannot see their corrected answer. "
        "Write only the learner's independent answer to the novel transfer task in 2-3 sentences.\n\n"
        "Distractor task completed: the learner briefly organized references for an unrelated paragraph.\n\n"
        f"Original concept: {case.concept_label}\n"
        f"Original attempt before tutoring: {case.misconception_artifact}\n"
        f"Tutoring received earlier:\n{intervention[:1800]}\n\n"
        f"Novel transfer task: {task}\n\n"
        "Independent transfer answer:"
    )
    if remote_chat_generate is not None:
        result = remote_chat_generate(
            prompt,
            system_prompt="You are only the learner completing an unaided transfer task. You cannot see the corrected answer.",
            provider=args.learner_provider,
            model=args.learner_model,
            max_predict=args.learner_max_predict,
            temperature=0.62,
        )
        text = str(result.get("response") or "").strip()
        if result.get("status") == "ok" and text:
            return {
                "artifact": _clean_artifact(text),
                "task": task,
                "source": "remote_learner_model_unaided_transfer",
                "provider": args.learner_provider,
                "model": args.learner_model,
            }
    return {
        "artifact": _fallback_transfer_artifact(case, ""),
        "task": task,
        "source": "deterministic_fallback_learner",
        "provider": "fallback",
        "model": "heuristic",
    }


def _default_transfer_task(case: ConceptCase) -> str:
    return f"Apply the underlying idea behind {case.concept_label} to a new academic-writing case without repeating the original wording."


def _fallback_transfer_artifact(case: ConceptCase, post_artifact: str) -> str:
    return (
        f"In the new case, the important issue is whether the learner can apply the same reasoning strategy, not copy the wording. "
        f"The concept may be present if the learner can justify the decision with evidence and limits; it fails if the learner only repeats a surface rule."
    )


def _clean_artifact(text: str) -> str:
    text = text.strip().strip('"')
    for prefix in ("Learner revised artifact:", "Revised artifact:", "Artifact:"):
        if text.lower().startswith(prefix.lower()):
            text = text[len(prefix):].strip()
    return " ".join(text.split())[:1200]


def _fallback_revised_artifact(case: ConceptCase, intervention: str) -> str:
    lowered = intervention.lower()
    features = [feature for feature in case.target_features if feature.split()[0].lower() in lowered]
    if not features:
        features = list(case.target_features[:3])
    return (
        f"{case.concept_label.title()} is not simply {case.misconception_artifact.split(' means ', 1)[-1].rstrip('.')}. "
        f"In this paper, it means a learner can use {', '.join(features[:3])} while keeping responsibility for the final academic judgment."
    )


def _score_artifact(case: ConceptCase, artifact: str) -> dict[str, Any]:
    lowered = artifact.lower()
    misconception_overlap = _token_overlap(case.misconception_artifact, artifact)
    feature_hits = {
        feature: _feature_present(feature, lowered)
        for feature in case.target_features
    }
    checks = {
        "names_concept": any(part in lowered for part in case.concept_label.lower().split()[:2]),
        "rejects_or_refines_misconception": bool(re.search(r"\bnot\b|\brather than\b|\binstead\b|\bmore than\b|\bnot simply\b", lowered)),
        "has_target_features": sum(feature_hits.values()) >= max(2, min(3, len(feature_hits))),
        "has_boundary_or_limit": bool(re.search(r"\bnot\b|\blimit|scope|while|without|rather than\b", lowered)),
        "learner_accountability": bool(re.search(r"\blearner|student|human|i\b", lowered) and re.search(r"\bresponsib|judg|accountab|revise|explain\b", lowered)),
        "not_verbatim_misconception": misconception_overlap < 0.72,
    }
    return {
        "score": sum(checks.values()),
        "max_score": len(checks),
        "checks": checks,
        "target_feature_hits": feature_hits,
        "misconception_overlap": round(misconception_overlap, 4),
    }


def _score_intervention(case: ConceptCase, intervention: str) -> dict[str, Any]:
    lowered = intervention.lower()
    checks = {
        "diagnoses_misconception": any(term in lowered for term in ("misconception", "confus", "collaps", "too narrow", "not sufficient", "not simply")),
        "diagnostic_uncertainty_or_discrimination": any(term in lowered for term in ("if", "suppose", "question", "distinguish", "ambiguous", "which")),
        "pedagogical_office_signal": any(term in lowered for term in ("counterexample", "question", "frame", "scaffold", "criterion", "source", "authorship", "confidence")),
        "scaffold_fading_signal": any(term in lowered for term in ("try", "your own", "without", "revise", "next attempt", "one sentence", "independent")),
        "authorship_preserved": any(term in lowered for term in ("do not write", "your wording", "your own", "final judgment", "you decide", "learner-owned")),
        "transfer_prepared": any(term in lowered for term in ("next time", "novel", "another case", "transfer", "apply", "new context")),
    }
    office = _infer_office_signal(lowered)
    scaffold = _infer_scaffold_level(lowered)
    return {
        "score": sum(checks.values()),
        "max_score": len(checks),
        "checks": checks,
        "inferred_office": office,
        "inferred_scaffold_level": scaffold,
    }


def _infer_office_signal(lowered: str) -> str:
    if any(term in lowered for term in ("not failed", "frustrated", "slow down", "confidence")):
        return "affectus"
    if "counterexample" in lowered or "suppose" in lowered or "contradiction" in lowered:
        return "dialecticus"
    if "source" in lowered or "evidence" in lowered or "provenance" in lowered:
        return "source_librarian"
    if "authorship" in lowered or "accountability" in lowered or "integrity" in lowered:
        return "integrity_auditor"
    if "frame" in lowered or "structure" in lowered or "blank" in lowered:
        return "constructor"
    if "question" in lowered:
        return "maieuticus"
    return "undetermined"


def _infer_scaffold_level(lowered: str) -> str:
    if any(term in lowered for term in ("worked example", "for example", "model")):
        return "stage_1_modelled"
    if any(term in lowered for term in ("blank", "frame", "fill in")):
        return "stage_2_prompted"
    if "question" in lowered and not any(term in lowered for term in ("frame", "blank")):
        return "stage_3_cued"
    if any(term in lowered for term in ("independent", "without a frame", "novel task")):
        return "stage_4_independent"
    return "stage_2_prompted"


def _concept_state(case: ConceptCase, pre: str, post: str, transfer: str, intervention_score: dict[str, Any]) -> dict[str, Any]:
    post_score = _score_artifact(case, post)
    transfer_score = _score_artifact(case, transfer)
    feature_confidence = round(sum(post_score["target_feature_hits"].values()) / max(1, len(post_score["target_feature_hits"])), 3)
    transfer_confidence = round(transfer_score["score"] / max(1, transfer_score["max_score"]), 3)
    return {
        "concept_id": case.concept_label.lower().replace(" ", "_"),
        "learner_profile": case.learner_profile,
        "hidden_cause": case.hidden_cause,
        "knowledge_components": {
            "repairs_initial_misconception": {
                "state": _state_label(post_score["checks"]["rejects_or_refines_misconception"], post_score["score"], post_score["max_score"]),
                "confidence": round(post_score["score"] / post_score["max_score"], 3),
                "evidence": ["post_artifact"],
            },
            "uses_target_features": {
                "state": "secure" if feature_confidence >= 0.6 else "emerging" if feature_confidence >= 0.35 else "fragile",
                "confidence": feature_confidence,
                "evidence": ["post_artifact", "target_feature_hits"],
            },
            "transfers_to_novel_case": {
                "state": "secure" if transfer_confidence >= 0.75 else "emerging" if transfer_confidence >= 0.5 else "fragile",
                "confidence": transfer_confidence,
                "evidence": ["transfer_artifact"],
            },
        },
        "support_history": {
            "inferred_office": intervention_score["inferred_office"],
            "last_scaffold_level": intervention_score["inferred_scaffold_level"],
            "successful_prompts": [k for k, v in intervention_score["checks"].items() if v],
            "failed_prompts": [k for k, v in intervention_score["checks"].items() if not v],
        },
    }


def _state_label(repaired: bool, score: int, max_score: int) -> str:
    ratio = score / max(1, max_score)
    if repaired and ratio >= 0.75:
        return "secure"
    if repaired and ratio >= 0.5:
        return "emerging"
    return "fragile"


def _feature_present(feature: str, lowered_artifact: str) -> bool:
    terms = [term.strip().lower() for term in re.split(r"\W+", feature) if len(term.strip()) > 2]
    return any(term in lowered_artifact for term in terms)


def _token_overlap(a: str, b: str) -> float:
    ta = {t for t in re.findall(r"[a-z]{3,}", a.lower())}
    tb = {t for t in re.findall(r"[a-z]{3,}", b.lower())}
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _condition_codes(conditions: list[str], rng: random.Random) -> dict[str, str]:
    codes = [f"Condition {chr(65 + i)}" for i in range(len(conditions))]
    rng.shuffle(codes)
    return dict(zip(conditions, codes))


def run(args: argparse.Namespace) -> dict[str, Any]:
    started = time.time()
    loaded_env = _load_env(args.env_file)
    rng = random.Random(args.seed)
    cases = list(CASES) + (list(SAME_SURFACE_CASES) if args.include_same_surface else [])
    rng.shuffle(cases)
    cases = cases[: args.case_count]
    conditions = args.conditions.split(",")
    blind_codes = _condition_codes(conditions, rng)
    health = _json_request(f"{args.base_url.rstrip('/')}/api/health", timeout=args.timeout)
    token = health.get("session_token") or ""
    if not token:
        raise RuntimeError("session_token_unavailable")

    rows: List[Dict[str, Any]] = []
    for case in cases:
        pre_score = _score_artifact(case, case.misconception_artifact)
        for condition in conditions:
            diagnostic_question: dict[str, Any] = {}
            diagnostic_answer: dict[str, str] = {}
            diagnostic_exchange: Optional[dict[str, str]] = None
            if args.two_turn_diagnosis:
                diagnostic_question = _remote_diagnostic_question(case, condition, token, args)
                diagnostic_answer = _learner_answer_diagnostic(case, diagnostic_question.get("response") or "", args)
                diagnostic_exchange = {
                    "question": diagnostic_question.get("response") or "",
                    "answer": diagnostic_answer.get("answer") or "",
                }
            intervention = _get_intervention(case, condition, token, args, diagnostic_exchange=diagnostic_exchange)
            post = _produce_post_artifact(case, intervention["response"], args)
            transfer = _produce_transfer_artifact(case, post["artifact"], intervention["response"], args)
            post_score = _score_artifact(case, post["artifact"])
            transfer_score = _score_artifact(case, transfer["artifact"])
            intervention_score = _score_intervention(case, intervention["response"])
            rows.append({
                "case_id": case.case_id,
                "concept_label": case.concept_label,
                "learner_profile": case.learner_profile,
                "hidden_cause": case.hidden_cause,
                "condition": condition,
                "blind_condition": blind_codes[condition],
                "paper_context": case.paper_context,
                "pre_artifact": case.misconception_artifact,
                "diagnostic_question": diagnostic_question,
                "diagnostic_answer": diagnostic_answer,
                "post_artifact": post["artifact"],
                "transfer_task": transfer["task"],
                "transfer_artifact": transfer["artifact"],
                "intervention": intervention,
                "learner_production": post,
                "transfer_production": transfer,
                "pre_score": pre_score,
                "post_score": post_score,
                "transfer_score": transfer_score,
                "intervention_score": intervention_score,
                "concept_state": _concept_state(case, case.misconception_artifact, post["artifact"], transfer["artifact"], intervention_score),
                "gain_points": post_score["score"] - pre_score["score"],
                "gain_pp": round(((post_score["score"] - pre_score["score"]) / max(1, post_score["max_score"])) * 100, 2),
            })
    summary = _summary(args, rows, blind_codes, loaded_env, round((time.time() - started) * 1000, 3))
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "schema_version": "sophia.blinded_learner_production_gauntlet.v1",
        "summary": summary,
        "truth_boundary": (
            "Post-artifacts are produced after the intervention by a learner simulator or declared fallback, not predefined by the harness. "
            "Hidden learner causes are withheld from tutors when two-turn diagnosis is enabled. "
            "This is still not human classroom learning proof; it is a blinded learner-production simulation for expert rating."
        ),
        "blind_code_key": blind_codes,
        "cases": [case.__dict__ for case in cases],
        "rows": rows,
    }


def _summary(args: argparse.Namespace, rows: list[dict[str, Any]], blind_codes: dict[str, str], loaded_env: list[str], elapsed_ms: float) -> dict[str, Any]:
    by_condition = {}
    for condition in sorted({row["condition"] for row in rows}):
        subset = [row for row in rows if row["condition"] == condition]
        by_condition[condition] = {
            "blind_condition": blind_codes[condition],
            "rows": len(subset),
            "mean_pre_score": round(sum(row["pre_score"]["score"] for row in subset) / max(1, len(subset)), 3),
            "mean_post_score": round(sum(row["post_score"]["score"] for row in subset) / max(1, len(subset)), 3),
            "mean_gain_points": round(sum(row["gain_points"] for row in subset) / max(1, len(subset)), 3),
            "mean_transfer_score": round(sum(row["transfer_score"]["score"] for row in subset) / max(1, len(subset)), 3),
            "mean_intervention_score": round(sum(row["intervention_score"]["score"] for row in subset) / max(1, len(subset)), 3),
            "positive_gain_rows": sum(1 for row in subset if row["gain_points"] > 0),
            "transfer_secure_or_emerging": sum(
                1 for row in subset
                if row["concept_state"]["knowledge_components"]["transfers_to_novel_case"]["state"] in {"secure", "emerging"}
            ),
            "interventions_answered": sum(1 for row in subset if row["intervention"]["response"]),
            "remote_learner_rows": sum(1 for row in subset if row["learner_production"]["source"] == "remote_learner_model"),
            "fallback_learner_rows": sum(1 for row in subset if row["learner_production"]["source"] != "remote_learner_model"),
        }
    return {
        "provider": args.provider,
        "model": args.model,
        "baseline_provider": args.baseline_provider,
        "baseline_model": args.baseline_model,
        "learner_provider": args.learner_provider,
        "learner_model": args.learner_model,
        "seed": args.seed,
        "case_count": len({row["case_id"] for row in rows}),
        "include_same_surface": args.include_same_surface,
        "two_turn_diagnosis": args.two_turn_diagnosis,
        "unaided_transfer": args.unaided_transfer,
        "conditions": list(blind_codes),
        "rows": len(rows),
        "elapsed_ms": elapsed_ms,
        "env_keys_loaded": sorted(loaded_env),
        "by_condition": by_condition,
    }


def write_outputs(artifact: dict[str, Any], out_prefix: str) -> dict[str, str]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    prefix = out_prefix or f"sophia_blinded_learner_production_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    json_path = OUT_DIR / f"{prefix}.json"
    md_path = OUT_DIR / f"{prefix}.md"
    csv_path = OUT_DIR / f"{prefix}_blinded_rater_packet.csv"
    outcome_csv_path = OUT_DIR / f"{prefix}_blinded_outcome_packet.csv"
    process_csv_path = OUT_DIR / f"{prefix}_blinded_process_packet.csv"
    key_path = OUT_DIR / f"{prefix}_condition_key.json"
    instructions_path = OUT_DIR / f"{prefix}_rater_instructions.md"
    json_path.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(_markdown(artifact), encoding="utf-8")
    _write_rater_packet(artifact, csv_path)
    _write_outcome_packet(artifact, outcome_csv_path)
    _write_process_packet(artifact, process_csv_path)
    key_path.write_text(json.dumps(artifact["blind_code_key"], indent=2) + "\n", encoding="utf-8")
    instructions_path.write_text(_instructions(), encoding="utf-8")
    return {
        "json": str(json_path),
        "markdown": str(md_path),
        "rater_packet": str(csv_path),
        "outcome_packet": str(outcome_csv_path),
        "process_packet": str(process_csv_path),
        "condition_key": str(key_path),
        "instructions": str(instructions_path),
    }


def _markdown(artifact: dict[str, Any]) -> str:
    s = artifact["summary"]
    lines = [
        "# Sophia Blinded Learner-Production Gauntlet",
        "",
        f"Truth boundary: {artifact['truth_boundary']}",
        "",
        "## Summary",
        "",
        "| Condition | Blind Code | Rows | Mean Pre | Mean Post | Mean Gain | Mean Transfer | Mean Intervention | Transfer Emerging+ | Remote Learner | Fallback Learner |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for condition, item in s["by_condition"].items():
        lines.append(
            f"| {condition} | {item['blind_condition']} | {item['rows']} | {item['mean_pre_score']} | "
            f"{item['mean_post_score']} | {item['mean_gain_points']} | {item['mean_transfer_score']} | "
            f"{item['mean_intervention_score']} | {item['transfer_secure_or_emerging']} | "
            f"{item['remote_learner_rows']} | {item['fallback_learner_rows']} |"
        )
    lines.extend(["", "## Blinded Rows"])
    for row in artifact["rows"]:
        lines.extend([
            "",
            f"### {row['case_id']} / {row['blind_condition']}",
            "",
            f"Concept: {row['concept_label']}",
            "",
            f"Learner profile: {row['learner_profile']}; hidden cause: {row['hidden_cause'] or '(not supplied)'}",
            "",
            "**Pre Artifact**",
            "",
            row["pre_artifact"],
            "",
            "**Tutor Intervention**",
            "",
            row["intervention"]["response"],
            "",
            "**Diagnostic Exchange**",
            "",
            f"Q: {(row.get('diagnostic_question') or {}).get('response') or '(not used)'}",
            "",
            f"A: {(row.get('diagnostic_answer') or {}).get('answer') or '(not used)'}",
            "",
            "**Learner Post Artifact**",
            "",
            row["post_artifact"],
            "",
            "**Independent Transfer Task**",
            "",
            row["transfer_task"],
            "",
            "**Independent Transfer Artifact**",
            "",
            row["transfer_artifact"],
            "",
            f"Automated score delta: {row['pre_score']['score']}/{row['pre_score']['max_score']} -> {row['post_score']['score']}/{row['post_score']['max_score']} ({row['gain_points']:+d})",
            "",
            f"Transfer score: {row['transfer_score']['score']}/{row['transfer_score']['max_score']}; inferred office={row['intervention_score']['inferred_office']}; scaffold={row['intervention_score']['inferred_scaffold_level']}",
        ])
    return "\n".join(lines) + "\n"


def _write_rater_packet(artifact: dict[str, Any], path: Path) -> None:
    rows = list(artifact["rows"])
    random.Random(artifact["summary"]["seed"]).shuffle(rows)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=[
            "item_id", "case_id", "blind_condition", "concept_label", "paper_context",
            "learner_profile", "hidden_cause", "pre_artifact", "diagnostic_question", "diagnostic_answer",
            "tutor_intervention", "post_artifact",
            "transfer_task", "transfer_artifact",
            "diagnostic_accuracy_0_4", "pedagogical_fit_0_4", "contingency_0_4",
            "cognitive_activation_0_4", "scaffold_calibration_0_4", "scaffold_fading_0_4",
            "transfer_0_4", "authorship_preservation_0_4",
            "guardrail_fabricated_memory_y_n", "guardrail_answer_substitution_y_n",
            "guardrail_theory_dumping_y_n", "guardrail_unexplained_office_switch_y_n",
            "overall_learning_support_1_5", "notes",
        ])
        writer.writeheader()
        for idx, row in enumerate(rows, start=1):
            writer.writerow({
                "item_id": f"BLP-{idx:03d}",
                "case_id": row["case_id"],
                "blind_condition": row["blind_condition"],
                "concept_label": row["concept_label"],
                "paper_context": row["paper_context"],
                "learner_profile": row["learner_profile"],
                "hidden_cause": row["hidden_cause"],
                "pre_artifact": row["pre_artifact"],
                "diagnostic_question": (row.get("diagnostic_question") or {}).get("response") or "",
                "diagnostic_answer": (row.get("diagnostic_answer") or {}).get("answer") or "",
                "tutor_intervention": row["intervention"]["response"],
                "post_artifact": row["post_artifact"],
                "transfer_task": row["transfer_task"],
                "transfer_artifact": row["transfer_artifact"],
            })


def _write_outcome_packet(artifact: dict[str, Any], path: Path) -> None:
    rows = list(artifact["rows"])
    random.Random(artifact["summary"]["seed"] + 11).shuffle(rows)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=[
            "item_id", "case_id", "blind_condition", "concept_label", "paper_context",
            "pre_artifact", "post_artifact", "transfer_task", "transfer_artifact",
            "conceptual_improvement_0_4", "transfer_quality_0_4", "authorship_preservation_0_4",
            "overall_learning_gain_1_5", "notes",
        ])
        writer.writeheader()
        for idx, row in enumerate(rows, start=1):
            writer.writerow({
                "item_id": f"OUT-{idx:03d}",
                "case_id": row["case_id"],
                "blind_condition": row["blind_condition"],
                "concept_label": row["concept_label"],
                "paper_context": row["paper_context"],
                "pre_artifact": row["pre_artifact"],
                "post_artifact": row["post_artifact"],
                "transfer_task": row["transfer_task"],
                "transfer_artifact": row["transfer_artifact"],
            })


def _write_process_packet(artifact: dict[str, Any], path: Path) -> None:
    rows = list(artifact["rows"])
    random.Random(artifact["summary"]["seed"] + 23).shuffle(rows)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=[
            "item_id", "case_id", "blind_condition", "concept_label", "paper_context",
            "learner_initial_artifact", "diagnostic_question", "diagnostic_answer", "tutor_intervention",
            "diagnostic_accuracy_0_4", "pedagogical_fit_0_4", "contingency_0_4",
            "cognitive_activation_0_4", "scaffold_calibration_0_4", "scaffold_fading_0_4",
            "authorship_preservation_0_4", "format_reveals_condition_y_n", "notes",
        ])
        writer.writeheader()
        for idx, row in enumerate(rows, start=1):
            writer.writerow({
                "item_id": f"PROC-{idx:03d}",
                "case_id": row["case_id"],
                "blind_condition": row["blind_condition"],
                "concept_label": row["concept_label"],
                "paper_context": row["paper_context"],
                "learner_initial_artifact": row["pre_artifact"],
                "diagnostic_question": (row.get("diagnostic_question") or {}).get("response") or "",
                "diagnostic_answer": (row.get("diagnostic_answer") or {}).get("answer") or "",
                "tutor_intervention": row["intervention"]["response"],
            })


def _instructions() -> str:
    return """# Blinded Rater Instructions

Rate each row without looking at the condition key.

Primary question: did the learner's post artifact improve after the tutor intervention?

Use 0-4 scales for the eight main dimensions:

- 0 = absent or harmful
- 1 = weak / mostly generic
- 2 = partial
- 3 = strong with minor limits
- 4 = excellent

Also give one overall_learning_support_1_5 score.

Do not reward polished prose alone. Reward diagnostic accuracy, pedagogical fit,
contingency, cognitive activation, scaffold calibration, scaffold fading,
transfer, authorship preservation, evidence/provenance awareness, and appropriate
limits.
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--env-file", default="/home/byron/EdgeK-BEAST/.beast/provider_secrets.env")
    parser.add_argument("--provider", default="gemini")
    parser.add_argument("--model", default="gemini-flash-lite-latest")
    parser.add_argument("--baseline-provider", default="gemini")
    parser.add_argument("--baseline-model", default="gemini-flash-lite-latest")
    parser.add_argument("--learner-provider", default="mistral")
    parser.add_argument("--learner-model", default="mistral-small-latest")
    parser.add_argument("--max-predict", type=int, default=700)
    parser.add_argument("--learner-max-predict", type=int, default=260)
    parser.add_argument("--timeout", type=float, default=220.0)
    parser.add_argument("--case-count", type=int, default=6)
    parser.add_argument(
        "--conditions",
        default="sophia_full,sophia_telemetry_recorded_not_used,sophia_pedagogy_no_mandos_assessment,plain_generic_remote_tutor",
    )
    parser.add_argument("--seed", type=int, default=260803)
    parser.add_argument("--include-same-surface", action="store_true", default=True)
    parser.add_argument("--attach-document", action="store_true", default=False)
    parser.add_argument("--two-turn-diagnosis", action="store_true", default=False)
    parser.add_argument("--unaided-transfer", action="store_true", default=False)
    parser.add_argument("--out-prefix", default="")
    args = parser.parse_args()
    artifact = run(args)
    paths = write_outputs(artifact, args.out_prefix)
    print(json.dumps(paths, indent=2))
    print(json.dumps(artifact["summary"], indent=2))
    return 0 if artifact["summary"]["rows"] > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
