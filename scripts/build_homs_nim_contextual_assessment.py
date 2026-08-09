#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile
from collections import Counter
from datetime import datetime, timezone
from json import JSONDecodeError
from pathlib import Path
from typing import Any

import requests


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from apply_homs_design_law import (  # noqa: E402
    DEFAULT_ASSESSMENT_DESIGN,
    DEFAULT_DESIGN_LAW,
    apply_design_law,
    assessment_design_for_pack,
    load_json as load_design_json,
    render_docx,
)
from run_hymark_exam_builder import (  # noqa: E402
    DEFAULT_CAPS_ASSESSMENT_DESIGN,
    DEFAULT_CAPS_MANIFEST,
    DEFAULT_CAPS_MATRIX,
    DEFAULT_CAPS_ONTOLOGY,
    DEFAULT_GRADE_LADDER,
    DEFAULT_HYMARK_BACKEND,
    DEFAULT_SECRET_FILE,
    assessment_language_for_request,
    build_visual_blueprint,
    configure_provider,
    load_grade_profile,
    load_hymark_backend,
    load_subject_profile,
    parse_env_file,
    normalize_assessment_pack,
    normalized_request,
    resolve_caps_context,
    sum_question_marks,
    sum_rubric_marks,
    validate_assessment_pack,
)


DEFAULT_OUT = ROOT / "deliverables" / "homs_nim_contextual_assessment"
DEFAULT_SOURCE_MATRIX = ROOT / "deliverables" / "exam_source_matrix_tight8_2025" / "exam_source_matrix.json"
DEFAULT_KNOWLEDGE_BANK = ROOT / "deliverables" / "homs_knowledge_bank" / "HOMS_KNOWLEDGE_BANK_REGISTRY.json"

NO_CONTEXT_PHRASES = [
    "answer the first",
    "complete the applied",
    "using the stimulus",
    "use the provided stimulus",
    "controlled classroom stimulus supplied by the educator",
    "structured task using the stimulus",
    "credit accurate subject knowledge",
    "evidence-based reasoning",
    "identify one important feature of the",
    "strongest assessment question",
]


class ProviderJsonError(RuntimeError):
    def __init__(self, message: str, content: str = "") -> None:
        super().__init__(message)
        self.content = content


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: Path, fallback: Any = None) -> Any:
    if not path.exists():
        return fallback
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").lower()).strip("_") or "item"


def source_matrix_contract(path: Path, subject: str) -> dict[str, Any]:
    data = read_json(path, {}) or {}
    subject_norm = subject.lower().replace("_", " ")
    matched = []
    counts: Counter[str] = Counter()
    evidence = []
    for paper in data.get("papers") or []:
        paper_subject = str(paper.get("subject") or "")
        if subject_norm not in paper_subject.lower() and paper_subject.lower() not in subject_norm:
            continue
        matched.append(
            {
                "title": paper.get("title"),
                "subject": paper_subject,
                "source_type_counts": paper.get("source_type_counts") or {},
                "unique_source_object_count": paper.get("unique_source_object_count"),
                "quality_counts": paper.get("quality_counts") or {},
            }
        )
        counts.update({str(k): int(v) for k, v in (paper.get("source_type_counts") or {}).items()})
        for item in paper.get("source_evidence") or []:
            snippet = str(item.get("snippet") or "")
            if snippet and len(evidence) < 16:
                evidence.append(
                    {
                        "paper": paper.get("title"),
                        "page": item.get("page"),
                        "source_types": item.get("source_types") or [],
                        "snippet": snippet[:280],
                        "mark_hints": item.get("mark_hints") or [],
                    }
                )
    return {
        "schema": "knowedge.homs_exam_source_contract.v1",
        "source_matrix": str(path),
        "subject": subject,
        "paper_count": len(matched),
        "source_type_counts": dict(counts),
        "paper_shapes": matched,
        "evidence_snippets": evidence,
    }


def life_sciences_evolution_visual_facts() -> dict[str, Any]:
    return {
        "figure_1": {
            "title": "Finch beak depth data table and graph",
            "facts": [
                "2019: rainfall 820 mm, hard seeds 24%, mean beak depth 8.7 mm",
                "2020: rainfall 610 mm, hard seeds 37%, mean beak depth 9.1 mm",
                "2021: rainfall 430 mm, hard seeds 58%, mean beak depth 9.8 mm",
                "2022: rainfall 390 mm, hard seeds 64%, mean beak depth 10.2 mm",
            ],
            "valid_question_moves": [
                "calculate change in beak depth",
                "describe the trend",
                "link rainfall/hard seed availability to selection pressure",
                "explain why larger beak depth may become more common",
            ],
        },
        "figure_2": {
            "title": "Investigation method and data sheet",
            "facts": [
                "Must assess aim, independent/dependent variables, controlled variables, reliability, validity, and conclusion.",
                "Questions must ask learners to critique method quality and use recorded observations.",
            ],
        },
        "figure_3": {
            "title": "Hominin skull comparison diagram",
            "facts": [
                "Skull A represents an earlier hominin profile.",
                "Skull B represents a later hominin profile.",
                "Label A indicates cranial capacity.",
                "Label B indicates jaw projection.",
                "Label C indicates foramen magnum position.",
                "Questions may compare cranial capacity, jaw projection and foramen magnum position as evidence for human evolution and bipedalism.",
            ],
        },
    }


def topic_visual_facts(subject_id: str, focus: str) -> dict[str, Any]:
    blob = f"{subject_id} {focus}".lower()
    if "life_sciences" in blob and any(token in blob for token in ["evolution", "natural selection", "hominin"]):
        return life_sciences_evolution_visual_facts()
    return {
        "generic_policy": {
            "facts": [
                "Use only visuals named in the visual blueprint.",
                "Every visual-referenced question must contain concrete observable details, values, labels, or source facts.",
            ]
        }
    }


def build_knowledge_packet(
    *,
    request: dict[str, Any],
    source_contract: dict[str, Any],
    knowledge_bank_path: Path,
    focus: str,
) -> dict[str, Any]:
    caps = request.get("caps_context") or {}
    selected_caps = caps.get("selected") or {}
    subject = request.get("subject_profile") or {}
    grade = request.get("grade_profile") or {}
    knowledge_bank = read_json(knowledge_bank_path, {}) or {}
    renderable_visual_facts = topic_visual_facts(str(subject.get("subject_id") or ""), focus)
    source_drift_bans: list[str] = []
    if renderable_visual_facts.get("figure_1", {}).get("title", "").lower().startswith("finch"):
        source_drift_bans.extend(["beetle", "platynus", "canyon", "shell"])
    if renderable_visual_facts.get("figure_2", {}).get("title", "").lower().startswith("investigation"):
        source_drift_bans.extend(["streptomycin", "escherichia", "e. coli", "bacteria", "agar"])
    if renderable_visual_facts.get("figure_3", {}).get("title", "").lower().startswith("hominin"):
        source_drift_bans.extend(["pelvis", "pan troglodytes", "chimpanzee", "diagram c"])
    return {
        "schema": "knowedge.homs_contextual_knowledge_packet.v1",
        "created_at": utc_now(),
        "purpose": "Prevent generic no-context questions by grounding provider generation in CAPS, old-paper source contracts, visual facts, subject profile and hard bans.",
        "subject_profile": subject,
        "grade_profile": grade,
        "language_of_assessment": assessment_language_for_request(request),
        "focus": focus,
        "visual_blueprint": request.get("visual_blueprint"),
        "renderable_visual_facts": renderable_visual_facts,
        "caps": {
            "selected_title": selected_caps.get("title"),
            "selected_path": selected_caps.get("path"),
            "selected_sha256": selected_caps.get("sha256"),
            "phase": caps.get("phase"),
            "preferred_language": caps.get("preferred_language"),
            "excerpt": str(caps.get("extracted_excerpt") or "")[:1800],
            "ontology": caps.get("assessment_ontology_profile"),
            "assessment_design": caps.get("assessment_design_profile"),
        },
        "official_paper_source_contract": source_contract,
        "knowledge_bank_registry_summary": {
            "path": str(knowledge_bank_path),
            "nvidia_nim_ready": (knowledge_bank.get("provider_support") or {}).get("nvidia_nim_ready"),
            "caps_documents": ((knowledge_bank.get("knowledge_layers") or {}).get("curriculum_authority") or {}).get("document_count"),
            "official_paper_catalogue_papers": ((knowledge_bank.get("knowledge_layers") or {}).get("official_paper_source_catalogue") or {}).get("paper_count"),
        },
        "hard_bans": [
            *NO_CONTEXT_PHRASES,
            "do not ask learners to evaluate whether the generated pack is ready",
            "do not ask learners why official-paper exemplars are stronger than generated visuals",
            "do not include source-quality, pipeline, route, smoke-test, design-law or product-QA questions",
            "do not refer to a figure, table, map, graph or diagram unless concrete figure facts are supplied in this packet",
            "do not invent new figure organisms, labels, datasets, years, diagram panels, tables, maps, chemicals or source facts",
            "do not replace supplied renderable visual facts with a different scenario",
            *[f"do not use source-drift term: {term}" for term in source_drift_bans],
        ],
    }


def configure_context_provider(secret_file: Path, provider_name: str, model: str) -> dict[str, Any]:
    values = parse_env_file(secret_file)
    for key, value in values.items():
        os.environ.setdefault(key, value)

    if provider_name in {"gemini", "google"}:
        key_name = "GEMINI_API_KEY"
        api_key = values.get(key_name) or os.environ.get(key_name)
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY was not found in the provider secret file or environment.")
        selected_model = (
            model
            or os.environ.get("HOMS_GEMINI_MODEL")
            or os.environ.get("BEAST_GEMINI_MODEL")
            or os.environ.get("GEMINI_MODEL")
            or "gemini-3.5-flash"
        )
        return {
            "selected_provider": "gemini",
            "selected_model": selected_model,
            "selected_key_name": key_name,
            "base_url": "https://generativelanguage.googleapis.com/v1beta",
            "available_secret_names": sorted(k for k, v in values.items() if v and ("KEY" in k or "TOKEN" in k or "SECRET" in k)),
            "values_redacted": True,
        }

    if provider_name in {"openrouter", "deepseek", "deepseek_v4"}:
        key_name = "OPENROUTER_API_KEY"
        api_key = values.get(key_name) or os.environ.get(key_name)
        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY was not found in the provider secret file or environment.")
        selected_model = (
            model
            or os.environ.get("HOMS_OPENROUTER_MODEL")
            or os.environ.get("BEAST_OPENROUTER_MODEL")
            or os.environ.get("OPENROUTER_MODEL")
            or "deepseek/deepseek-v4-flash-latest"
        )
        os.environ["OPENAI_API_KEY"] = api_key
        os.environ["OPENAI_BASE_URL"] = "https://openrouter.ai/api/v1"
        os.environ["HOMS_AI_MODEL"] = selected_model
        return {
            "selected_provider": "openrouter",
            "selected_model": selected_model,
            "selected_key_name": key_name,
            "base_url": "https://openrouter.ai/api/v1",
            "available_secret_names": sorted(k for k, v in values.items() if v and ("KEY" in k or "TOKEN" in k or "SECRET" in k)),
            "values_redacted": True,
        }

    return configure_provider(secret_file, provider_name, model)


def nim_prompt(packet: dict[str, Any], *, total_marks: int, duration: str, opportunity: str) -> str:
    subject = packet["subject_profile"]
    grade = packet["grade_profile"]
    visual_facts = packet.get("renderable_visual_facts") or {}
    return f"""You are HyMark's CAPS-aware assessment writer. Create a learner-facing assessment pack as strict JSON.

The previous failure was generic no-context questions. Do not repeat it.

Opportunity: {opportunity}
Subject: {subject.get('display_name')}
Subject ID: {subject.get('subject_id')}
Grade: {grade.get('grade')}
Phase: {grade.get('phase')}
Language of assessment: {packet.get('language_of_assessment')}
Focus: {packet.get('focus')}
Total marks: {total_marks}
Duration: {duration}

LOCKED SOURCE CARDS. These are the only source/figure facts you may assess:
{json.dumps(visual_facts, indent=2, ensure_ascii=False)}

Knowledge packet:
{json.dumps(packet, indent=2, ensure_ascii=False)[:9500]}

Design requirements:
- Use the CAPS ontology and assessment design as authority.
- Use old-paper source contract only to decide source/stimulus types and question moves.
- Use the renderable visual facts when writing questions that refer to figures.
- Treat renderable visual facts as locked source truth: do not invent different figures, organisms, datasets, labels, panels, chemicals or tables.
- If this packet supplies Figure 1, Figure 2 or Figure 3 facts, the assessment questions must use those exact figure identities and facts.
- Figure numbering must remain: Figure 1 = finch beak data, Figure 2 = investigation method/data sheet, Figure 3 = hominin skull comparison.
- Every section must have a concrete, content-specific stimulus or figure reference.
- Every question must test actual subject content, data interpretation, diagram interpretation, investigation design, or CAPS-aligned reasoning.
- Memo bullets must be specific enough for marking, with acceptable alternatives where appropriate.
- Rubric marks must sum exactly to total_marks.
- Question marks must sum exactly to total_marks.
- Do not include internal review, smoke-test, product QA, route, source catalogue, or educator-release questions in learner sections.
- Do not use any hard-ban phrase from the knowledge packet.
- Do not use any source-drift term from hard_bans, even as an example or comparison.

Return strict JSON only:
{{
  "schema": "knowedge.homs_assessment_pack.v1",
  "subject": "{subject.get('display_name')}",
  "grade": {grade.get('grade')},
  "phase": "fet_grade_10_12",
  "assessment_title": "...",
  "canonical_profile_id": "fet.{subject.get('subject_id')}",
  "blueprint": "...",
  "render_shell": "...",
  "duration": "{duration}",
  "total_marks": {total_marks},
  "visual_blueprint": {json.dumps(packet.get('visual_blueprint') or {}, ensure_ascii=False)},
  "sections": [
    {{
      "title": "...",
      "mode": "...",
      "instructions": "...",
      "stimulus": "Concrete context, data, figure reference, diagram reference or source extract.",
      "questions": [
        {{"number": "1.1", "question": "...", "marks": 2, "memo": ["specific memo point"]}}
      ]
    }}
  ],
  "rubric": [
    {{"criterion": "...", "marks": 0, "descriptor": "..."}}
  ],
  "teacher_review_checklist": ["..."]
}}"""


def deep_questions(pack: dict[str, Any]) -> list[dict[str, Any]]:
    return [q for section in pack.get("sections") or [] for q in section.get("questions") or []]


def scrub_provider_artifacts(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: scrub_provider_artifacts(item) for key, item in value.items()}
    if isinstance(value, list):
        return [scrub_provider_artifacts(item) for item in value]
    if isinstance(value, str):
        cleaned = re.sub(r"\bcorrected:\s*", "", value, flags=re.I)
        return re.sub(r"\s{2,}", " ", cleaned).strip()
    return value


def reconcile_question_marks(pack: dict[str, Any], total_marks: int, max_delta: int = 5) -> None:
    questions = deep_questions(pack)
    current = sum_question_marks(pack)
    delta = int(total_marks) - current
    if not questions or delta == 0 or abs(delta) > max_delta:
        return
    candidates = list(reversed(questions))
    if delta < 0:
        needed = abs(delta)
        for question in candidates:
            marks = int(question.get("marks") or 0)
            if marks > needed:
                question["marks"] = marks - needed
                memo = question.get("memo")
                if isinstance(memo, list):
                    memo.append(f"Mark allocation adjusted by {needed} mark(s) during deterministic reconciliation.")
                return
    else:
        question = candidates[0]
        question["marks"] = int(question.get("marks") or 0) + delta
        memo = question.get("memo")
        if isinstance(memo, list):
            memo.append(f"Mark allocation adjusted by {delta} mark(s) during deterministic reconciliation.")


def reconcile_rubric_marks(pack: dict[str, Any], total_marks: int, max_delta: int = 5) -> None:
    rubric = pack.get("rubric") or []
    current = sum_rubric_marks(pack)
    delta = int(total_marks) - current
    if not rubric or delta == 0 or abs(delta) > max_delta:
        return
    item = rubric[-1]
    marks = int(item.get("marks") or 0)
    if delta < 0 and marks <= abs(delta):
        return
    item["marks"] = marks + delta
    descriptor = str(item.get("descriptor") or "")
    item["descriptor"] = f"{descriptor} Mark allocation reconciled by {delta:+d}."


def finalize_pack_candidate(pack: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    pack = scrub_provider_artifacts(pack)
    total_marks = int(pack.get("total_marks") or request.get("total_marks") or 0)
    if total_marks:
        reconcile_question_marks(pack, total_marks)
        reconcile_rubric_marks(pack, total_marks)
    return pack


def context_validation(pack: dict[str, Any], request: dict[str, Any], packet: dict[str, Any]) -> list[str]:
    errors = validate_assessment_pack(pack, request)
    subject_id = str((packet.get("subject_profile") or {}).get("subject_id") or "").lower()
    learner_blob = json.dumps(
        {
            "assessment_title": pack.get("assessment_title"),
            "sections": pack.get("sections"),
            "rubric": pack.get("rubric"),
            "teacher_review_checklist": pack.get("teacher_review_checklist"),
        },
        ensure_ascii=False,
    ).lower()
    section_blob = json.dumps(
        {
            "assessment_title": pack.get("assessment_title"),
            "sections": pack.get("sections"),
        },
        ensure_ascii=False,
    ).lower()
    for phrase in NO_CONTEXT_PHRASES:
        if phrase in learner_blob:
            errors.append(f"no-context phrase found: {phrase}")
    questions = deep_questions(pack)
    if len(questions) < 8:
        errors.append(f"too few questions for contextual assessment: {len(questions)}")
    if len(pack.get("sections") or []) < 3:
        errors.append("too few sections; expected concept/data/diagram/investigation coverage")
    if subject_id == "life_sciences" and "evolution" in str(packet.get("focus") or "").lower():
        concrete_terms = [
            "figure",
            "table",
            "data",
            "beak",
            "rainfall",
            "seed",
            "skull",
            "cranial",
            "jaw",
            "foramen",
            "hominin",
            "natural selection",
            "variable",
            "validity",
            "reliability",
            "evolution",
        ]
        concrete_hits = sum(1 for term in concrete_terms if term in section_blob)
        if concrete_hits < 8:
            errors.append(f"insufficient concrete Life Sciences content terms: {concrete_hits}")
    else:
        stop_terms = {
            "assessment",
            "question",
            "questions",
            "source",
            "sources",
            "figure",
            "table",
            "data",
            "grade",
            "term",
            "learners",
            "answer",
            "explain",
            "describe",
            "compare",
            "using",
            "provided",
            "caps",
            "subject",
            "evidence",
            "reasoning",
        }
        focus_terms = [
            term
            for term in re.findall(r"[a-z][a-z\-]{4,}", str(packet.get("focus") or "").lower())
            if term not in stop_terms
        ]
        profile_terms = [
            term
            for term in re.findall(
                r"[a-z][a-z\-]{4,}",
                json.dumps(
                    {
                        "modes": (packet.get("subject_profile") or {}).get("assessment_modes"),
                        "source_types": (packet.get("subject_profile") or {}).get("source_types"),
                        "question_families": (packet.get("subject_profile") or {}).get("question_families"),
                    }
                ).lower(),
            )
            if term not in stop_terms
        ]
        expected_terms = sorted(set(focus_terms + profile_terms))
        if expected_terms:
            hits = [term for term in expected_terms if term.replace("-", " ") in section_blob or term in section_blob]
            required_hits = min(5, max(3, len(expected_terms) // 5))
            if len(hits) < required_hits:
                errors.append(f"insufficient subject-specific content terms: {len(hits)}, expected at least {required_hits}")
    figure_refs = len(re.findall(r"\bfigure\s+[123]\b", section_blob, flags=re.I))
    if packet.get("renderable_visual_facts", {}).get("figure_1") and figure_refs < 4:
        errors.append(f"too few figure-specific references: {figure_refs}")
    visual_facts = packet.get("renderable_visual_facts") or {}
    if visual_facts.get("figure_1", {}).get("title", "").lower().startswith("finch"):
        required_figure_1_terms = ["finch", "beak", "rainfall", "seed"]
        missing_terms = [term for term in required_figure_1_terms if term not in section_blob]
        if missing_terms:
            errors.append(f"Figure 1 does not use locked finch visual facts; missing: {', '.join(missing_terms)}")
        unsupported = ["beetle", "platynus", "canyon", "shell"]
        for term in unsupported:
            if term in section_blob:
                errors.append(f"unsupported invented Figure 1 scenario term found: {term}")
    if visual_facts.get("figure_2", {}).get("title", "").lower().startswith("investigation"):
        unsupported = ["streptomycin", "escherichia", "e. coli", "bacteria", "agar"]
        for term in unsupported:
            if term in section_blob:
                errors.append(f"unsupported invented investigation scenario term found: {term}")
    if visual_facts.get("figure_3", {}).get("title", "").lower().startswith("hominin"):
        required_figure_3_terms = ["skull a", "skull b", "cranial", "jaw", "foramen"]
        missing_terms = [term for term in required_figure_3_terms if term not in section_blob]
        if missing_terms:
            errors.append(f"Figure 3 does not use locked skull visual facts; missing: {', '.join(missing_terms)}")
        unsupported = ["pelvis", "pan troglodytes", "chimpanzee", "diagram c"]
        for term in unsupported:
            if term in section_blob:
                errors.append(f"unsupported invented Figure 3 scenario term found: {term}")
    section_stimuli = [str(section.get("stimulus") or "").strip() for section in pack.get("sections") or []]
    if any(len(stimulus) < 40 for stimulus in section_stimuli):
        errors.append("one or more sections has weak/missing concrete stimulus text")
    return sorted(set(errors))


def openai_compatible_json(hymark: Any, system: str, prompt: str, max_tokens: int, temperature: float, timeout: float) -> dict[str, Any]:
    response = hymark.openai_client.chat.completions.create(
        model=hymark.AI_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
        timeout=timeout,
    )
    content = response.choices[0].message.content
    if not content:
        raise ValueError("provider returned an empty JSON response")
    try:
        return parse_json_content(content)
    except JSONDecodeError as exc:
        raise ProviderJsonError(f"provider returned invalid JSON: {exc}", content) from exc


def parse_json_content(content: str) -> dict[str, Any]:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.I)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            return json.loads(cleaned[start : end + 1])
        raise


def gemini_json(provider: dict[str, Any], system: str, prompt: str, max_tokens: int, temperature: float, timeout: float) -> dict[str, Any]:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set.")
    model = str(provider["selected_model"])
    model_path = model if model.startswith("models/") else f"models/{model}"
    url = f"https://generativelanguage.googleapis.com/v1beta/{model_path}:generateContent"
    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
            "responseMimeType": "application/json",
        },
    }
    response = None
    for attempt in range(1, 5):
        response = requests.post(url, params={"key": api_key}, json=payload, timeout=timeout)
        if response.status_code != 429 or attempt == 4:
            break
        retry_match = re.search(r"retry in ([0-9.]+)s", response.text, flags=re.I)
        retry_seconds = float(retry_match.group(1)) if retry_match else 65.0
        retry_seconds = max(5.0, min(retry_seconds + 2.0, 75.0))
        print(json.dumps({"stage": "gemini_rate_limited", "attempt": attempt, "sleep_seconds": round(retry_seconds, 2)}), flush=True)
        time.sleep(retry_seconds)
    if response is None:
        raise RuntimeError("Gemini request did not execute.")
    if response.status_code >= 400:
        raise RuntimeError(f"Gemini request failed with HTTP {response.status_code}: {response.text[:500]}")
    data = response.json()
    parts = (((data.get("candidates") or [{}])[0].get("content") or {}).get("parts") or [])
    content = "".join(str(part.get("text") or "") for part in parts).strip()
    if not content:
        raise ValueError("Gemini returned an empty JSON response")
    try:
        return parse_json_content(content)
    except JSONDecodeError as exc:
        raise ProviderJsonError(f"Gemini returned invalid JSON: {exc}", content) from exc


def provider_json(
    hymark: Any,
    provider: dict[str, Any],
    system: str,
    prompt: str,
    max_tokens: int,
    temperature: float,
    timeout: float,
) -> dict[str, Any]:
    if provider["selected_provider"] == "gemini":
        return gemini_json(provider, system, prompt, max_tokens, temperature, timeout)
    return openai_compatible_json(hymark, system, prompt, max_tokens, temperature, timeout)


def call_provider_with_repair(
    hymark: Any,
    provider: dict[str, Any],
    packet: dict[str, Any],
    request: dict[str, Any],
    total_marks: int,
    duration: str,
    opportunity: str,
    *,
    job_dir: Path,
    repair: bool,
    timeout: float,
    max_tokens: int,
) -> tuple[dict[str, Any], list[str], list[dict[str, Any]]]:
    attempts: list[dict[str, Any]] = []
    prompt = nim_prompt(packet, total_marks=total_marks, duration=duration, opportunity=opportunity)
    system = (
        "You are a strict CAPS assessment generator. Return valid JSON only. "
        "You must create concrete, content-specific questions grounded in the provided knowledge packet."
    )
    prompt_path = job_dir / "HOMS_CONTEXTUAL_PROMPT.txt"
    prompt_path.write_text(prompt, encoding="utf-8")
    try:
        raw = provider_json(hymark, provider, system, prompt, max_tokens=max_tokens, temperature=0.25, timeout=timeout)
    except ProviderJsonError as exc:
        (job_dir / "HOMS_CONTEXTUAL_RAW_ATTEMPT_1.txt").write_text(exc.content, encoding="utf-8")
        raise
    write_json(job_dir / "HOMS_CONTEXTUAL_RAW_ATTEMPT_1.json", raw)
    pack = normalize_assessment_pack(raw, request, 1 if "first" in opportunity.lower() else 2)
    pack = finalize_pack_candidate(pack, request)
    errors = context_validation(pack, request, packet)
    attempts.append({"attempt": 1, "errors": errors, "question_count": len(deep_questions(pack))})
    print(json.dumps({"stage": "provider_attempt_1_done", "provider": provider["selected_provider"], "errors": errors, "question_count": len(deep_questions(pack))}), flush=True)
    if errors and repair:
        repair_prompt = (
            prompt
            + "\n\nThe previous JSON failed validation:\n"
            + "\n".join(f"- {error}" for error in errors)
            + "\n\nRepair the JSON. Keep the same schema. Remove generic phrasing. Add concrete source/figure/data context. Reconcile marks exactly."
        )
        (job_dir / "HOMS_CONTEXTUAL_REPAIR_PROMPT.txt").write_text(repair_prompt, encoding="utf-8")
        try:
            raw = provider_json(hymark, provider, system, repair_prompt, max_tokens=max_tokens, temperature=0.2, timeout=timeout)
        except ProviderJsonError as exc:
            (job_dir / "HOMS_CONTEXTUAL_RAW_ATTEMPT_2.txt").write_text(exc.content, encoding="utf-8")
            raise
        write_json(job_dir / "HOMS_CONTEXTUAL_RAW_ATTEMPT_2.json", raw)
        pack = normalize_assessment_pack(raw, request, 1 if "first" in opportunity.lower() else 2)
        pack = finalize_pack_candidate(pack, request)
        errors = context_validation(pack, request, packet)
        attempts.append({"attempt": 2, "errors": errors, "question_count": len(deep_questions(pack))})
        print(json.dumps({"stage": "provider_attempt_2_done", "provider": provider["selected_provider"], "errors": errors, "question_count": len(deep_questions(pack))}), flush=True)
    return pack, errors, attempts


def convert_pdf(docx_path: Path, out_dir: Path) -> Path | None:
    out_dir.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", str(out_dir), str(docx_path)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    pdf_path = out_dir / f"{docx_path.stem}.pdf"
    return pdf_path if result.returncode == 0 and pdf_path.exists() else None


def zip_dir(source: Path, target: Path) -> None:
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in source.rglob("*"):
            if path.is_file() and path.resolve() != target.resolve():
                zf.write(path, path.relative_to(source))


def write_report(job_dir: Path, receipt: dict[str, Any]) -> None:
    lines = [
        "# HOMS Contextual Assessment Run",
        "",
        f"Created: {receipt['created_at']}",
        f"Status: `{receipt['status']}`",
        f"Provider: `{receipt['provider']['selected_provider']}` / `{receipt['provider']['selected_model']}`",
        f"Subject: {receipt['subject']} Grade {receipt['grade']}",
        f"Focus: {receipt['focus']}",
        "",
        "## Validation",
        "",
    ]
    if receipt["validation_errors"]:
        lines.extend(f"- {error}" for error in receipt["validation_errors"])
    else:
        lines.append("- passed")
    lines.extend(
        [
            "",
            "## Outputs",
            "",
            f"- Assessment pack: `{Path(receipt['paths']['assessment_pack']).name}`",
            f"- Full review DOCX: `{Path(receipt['paths']['formatted_review_docx']).name}`",
            f"- Learner DOCX: `{Path(receipt['paths']['learner_docx']).name}`",
            f"- Learner PDF: `{Path(receipt['paths']['learner_pdf']).name if receipt['paths'].get('learner_pdf') else 'not exported'}`",
        f"- Knowledge packet: `{Path(receipt['paths']['knowledge_packet']).name}`",
        ]
    )
    (job_dir / "HOMS_CONTEXTUAL_ASSESSMENT_REPORT.md").write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def run(args: argparse.Namespace) -> dict[str, Any]:
    started = time.perf_counter()
    provider = configure_context_provider(args.secret_file, args.provider, args.model)
    hymark = load_hymark_backend(args.backend)
    subject_profile = load_subject_profile(args.subject, None)
    grade_profile = load_grade_profile(args.grade, args.grade_ladder)
    caps_context = resolve_caps_context(
        subject_profile,
        grade_profile,
        args.caps_manifest,
        args.preferred_language,
        include_policy=False,
        max_chars=args.caps_extract_chars,
        matrix_path=args.caps_matrix,
        ontology_path=args.caps_ontology,
        assessment_design_path=args.caps_assessment_design,
    )
    request = normalized_request(args.request, subject_profile, grade_profile, caps_context, str(args.term))
    request["topics"] = [args.focus, args.secondary_focus]
    request["methodology_topic"] = args.methodology_focus
    request["essay_topic"] = args.extended_focus
    request["total_marks"] = args.total_marks
    request["duration_hours"] = args.duration_hours
    request["visual_blueprint"] = build_visual_blueprint(request)

    source_contract = source_matrix_contract(args.source_matrix, subject_profile["display_name"])
    packet = build_knowledge_packet(
        request=request,
        source_contract=source_contract,
        knowledge_bank_path=args.knowledge_bank,
        focus="; ".join([args.focus, args.secondary_focus, args.methodology_focus, args.extended_focus]),
    )
    out_root = args.out
    out_root.mkdir(parents=True, exist_ok=True)
    job_id = f"{provider['selected_provider']}-context-{subject_profile['subject_id']}-g{args.grade}-t{args.term}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    job_dir = out_root / job_id
    if job_dir.exists():
        shutil.rmtree(job_dir)
    job_dir.mkdir(parents=True)
    write_json(job_dir / "HOMS_CONTEXTUAL_KNOWLEDGE_PACKET.json", packet)
    write_json(job_dir / "HOMS_VISUAL_BLUEPRINT.json", request["visual_blueprint"])
    write_json(job_dir / "exam_builder_request.json", request)

    pack, errors, attempts = call_provider_with_repair(
        hymark,
        provider,
        packet,
        request,
        args.total_marks,
        args.duration,
        args.opportunity,
        job_dir=job_dir,
        repair=args.repair,
        timeout=args.timeout,
        max_tokens=args.max_tokens,
    )
    pack["generation_backend"] = f"{provider['selected_provider']}_contextual_knowledge_packet"
    pack["knowledge_packet_schema"] = packet["schema"]
    pack["validation_errors"] = errors
    write_json(job_dir / "assessment_pack.json", pack)
    write_json(job_dir / "HOMS_CONTEXTUAL_ATTEMPTS.json", attempts)

    design_receipt = apply_design_law(job_dir, args.design_law, args.caps_assessment_design)
    design_law = load_design_json(args.design_law)
    design_payload = load_design_json(args.caps_assessment_design)
    assessment_design = assessment_design_for_pack(pack, design_payload)
    learner_docx = render_docx(
        job_dir,
        pack,
        design_law,
        design_receipt.get("assets") or [],
        assessment_design,
        include_memo_sections=False,
        output_name="ASSESSMENT_LEARNER.docx",
    )
    learner_pdf = convert_pdf(learner_docx, job_dir / "pdf_check")
    review_pdf = convert_pdf(Path(design_receipt["formatted_docx"]), job_dir / "pdf_check")
    zip_path = job_dir / "HOMS_CONTEXTUAL_ASSESSMENT_PACK.zip"
    zip_dir(job_dir, zip_path)

    receipt = {
        "schema": "knowedge.homs_contextual_assessment_receipt.v1",
        "created_at": utc_now(),
        "status": "passed" if not errors else "failed_validation",
        "subject": subject_profile["display_name"],
        "grade": args.grade,
        "term": str(args.term),
        "focus": packet["focus"],
        "provider": provider,
        "question_count": len(deep_questions(pack)),
        "question_marks": sum_question_marks(pack),
        "rubric_marks": sum_rubric_marks(pack),
        "validation_errors": errors,
        "attempts": attempts,
        "elapsed_seconds": round(time.perf_counter() - started, 2),
        "paths": {
            "job_dir": str(job_dir),
            "assessment_pack": str(job_dir / "assessment_pack.json"),
            "knowledge_packet": str(job_dir / "HOMS_CONTEXTUAL_KNOWLEDGE_PACKET.json"),
            "visual_blueprint": str(job_dir / "HOMS_VISUAL_BLUEPRINT.json"),
            "formatted_review_docx": design_receipt["formatted_docx"],
            "learner_docx": str(learner_docx),
            "learner_pdf": str(learner_pdf) if learner_pdf else None,
            "review_pdf": str(review_pdf) if review_pdf else None,
            "zip": str(zip_path),
        },
    }
    write_json(job_dir / "HOMS_CONTEXTUAL_ASSESSMENT_RECEIPT.json", receipt)
    write_report(job_dir, receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a HOMS contextual assessment through a provider-backed knowledge packet.")
    parser.add_argument("--subject", default="life_sciences")
    parser.add_argument("--grade", type=int, default=12)
    parser.add_argument("--term", default="3")
    parser.add_argument("--focus", default="Evolution by natural selection and speciation")
    parser.add_argument("--secondary-focus", default="Human evolution evidence and interpretation")
    parser.add_argument("--methodology-focus", default="Scientific investigation design for natural selection")
    parser.add_argument("--extended-focus", default="Using data and anatomical evidence to support evolutionary explanations")
    parser.add_argument("--total-marks", type=int, default=75)
    parser.add_argument("--duration", default="1.5 hours")
    parser.add_argument("--duration-hours", type=int, default=2)
    parser.add_argument("--opportunity", default="First opportunity")
    parser.add_argument("--request", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--provider", default="gemini", choices=["gemini", "google", "openrouter", "deepseek", "deepseek_v4", "nim", "nvidia", "nvidia_nim", "openai"])
    parser.add_argument("--model", default="")
    parser.add_argument("--secret-file", type=Path, default=DEFAULT_SECRET_FILE)
    parser.add_argument("--backend", type=Path, default=DEFAULT_HYMARK_BACKEND)
    parser.add_argument("--grade-ladder", type=Path, default=DEFAULT_GRADE_LADDER)
    parser.add_argument("--caps-manifest", type=Path, default=DEFAULT_CAPS_MANIFEST)
    parser.add_argument("--caps-matrix", type=Path, default=DEFAULT_CAPS_MATRIX)
    parser.add_argument("--caps-ontology", type=Path, default=DEFAULT_CAPS_ONTOLOGY)
    parser.add_argument("--caps-assessment-design", type=Path, default=DEFAULT_CAPS_ASSESSMENT_DESIGN)
    parser.add_argument("--design-law", type=Path, default=DEFAULT_DESIGN_LAW)
    parser.add_argument("--source-matrix", type=Path, default=DEFAULT_SOURCE_MATRIX)
    parser.add_argument("--knowledge-bank", type=Path, default=DEFAULT_KNOWLEDGE_BANK)
    parser.add_argument("--preferred-language", default="English")
    parser.add_argument("--caps-extract-chars", type=int, default=8000)
    parser.add_argument("--repair", action="store_true", help="Allow a second provider repair call if the first pack fails validation.")
    parser.add_argument("--timeout", type=float, default=45.0, help="Per provider request timeout in seconds.")
    parser.add_argument("--max-tokens", type=int, default=9000, help="Provider output token ceiling.")
    args = parser.parse_args()
    receipt = run(args)
    print(json.dumps(receipt, indent=2))
    return 0 if receipt["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
