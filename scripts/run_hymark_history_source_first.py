#!/usr/bin/env python3
from __future__ import annotations

"""Production wrapper around the source-first History builder.

The core builder is retained byte-for-byte in run_hymark_history_source_first_core.py.
This wrapper narrows the repair policy without weakening source, mark, or provenance
controls:

* 5-10 source-based subquestions are permitted when the section still totals 30.
* A thin essay memorandum is repaired independently instead of regenerating an
  otherwise-valid source-question plan.
"""

import json
import re
from pathlib import Path
from typing import Any

import run_hymark_history_source_first_core as _core

_ORIGINAL_PLAN_ERRORS = _core._plan_errors
_ORIGINAL_GENERATION_PROMPT = _core._generation_prompt


def _generation_prompt(request: dict[str, Any], sources: list[dict[str, str]], opportunity: int) -> str:
    prompt = _ORIGINAL_GENERATION_PROMPT(request, sources, opportunity)
    prompt = prompt.replace(
        "Each source section should contain 5-8 substantive subquestions",
        "Each source section should contain 5-10 substantive subquestions",
    )
    prompt = prompt.replace(
        "Give a detailed marking outline for both alternatives.",
        "Give a detailed marking outline for both alternatives with at least 8 substantive historical content/argument points per option, plus argument/evidence/analysis/structure guidance.",
    )
    return prompt


def _plan_errors(plan: dict[str, Any], sources: list[dict[str, str]]) -> list[str]:
    """Preserve every core quality check except the arbitrary 8-question ceiling."""
    errors = list(_ORIGINAL_PLAN_ERRORS(plan, sources))
    sections = list(plan.get("source_sections") or [])
    for index, source in enumerate(sources[:3]):
        label = source["label"]
        count = len(list(sections[index].get("questions") or [])) if index < len(sections) else 0
        old_pattern = re.compile(rf"^{re.escape(label)} has \d+ subquestions, expected 5-8$")
        errors = [error for error in errors if not old_pattern.match(error)]
        if index < len(sections) and not 5 <= count <= 10:
            errors.append(f"{label} has {count} subquestions, expected 5-10")
    return sorted(set(errors))


def _essay_errors(errors: list[str]) -> list[str]:
    return [error for error in errors if error.startswith("essay ")]


def _repair_essay_only(
    hymark: Any,
    request: dict[str, Any],
    sources: list[dict[str, str]],
    plan: dict[str, Any],
    opportunity: int,
    opportunity_dir: Path,
) -> dict[str, Any]:
    existing = dict(plan.get("essay") or {})
    prompt = f"""Repair ONLY the essay memorandum of this Grade {request.get('grade')} South African History examination.

Opportunity: {opportunity}
Topics: {'; '.join(request.get('topics') or [])}
The learner essay wording is already accepted and must remain unchanged.

OPTION A:
{existing.get('option_a', '')}

OPTION B:
{existing.get('option_b', '')}

LOCKED CUSTOMER SOURCES FOR CONTEXT ONLY:
{_core._locked_sources_text(sources)}

NON-NEGOTIABLE RULES
- Return the SAME option_a and option_b wording verbatim.
- memo_option_a must contain at least 8 substantive historical content/argument points.
- memo_option_b must contain at least 8 substantive historical content/argument points.
- marking_guidance must address argument, evidence, analysis/synthesis, factual accuracy and structure.
- Do not invent a quotation, historian, author, publication, date, photograph, cartoon, map, graph or source provenance.
- Do not refer to a fictional or reconstructed source.
- Return strict JSON only in the form {{"essay": {{...}}}}.
"""
    repaired = _core.model_json(
        hymark,
        "You are a South African FET History memorandum specialist. Expand the marking outline without changing the learner essay questions. Return JSON only.",
        prompt,
        max_tokens=2800,
        temperature=0.12,
    )
    essay = dict(repaired.get("essay") or repaired)
    essay["option_a"] = str(existing.get("option_a") or "")
    essay["option_b"] = str(existing.get("option_b") or "")
    updated = dict(plan)
    updated["essay"] = essay
    (opportunity_dir / "HOMS_SOURCE_FIRST_ESSAY_REPAIR.json").write_text(
        json.dumps(updated, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return updated


def _generate_plan(
    hymark: Any,
    request: dict[str, Any],
    sources: list[dict[str, str]],
    opportunity: int,
    opportunity_dir: Path,
) -> dict[str, Any]:
    system = (
        "You are an experienced South African FET History examiner. The source texts are immutable evidence objects. "
        "You write only rigorous source-based questions and specific marking memoranda. Return JSON only."
    )
    prompt = _generation_prompt(request, sources, opportunity)
    plan = _core.model_json(hymark, system, prompt, max_tokens=5200, temperature=0.35)
    (opportunity_dir / "HOMS_SOURCE_FIRST_PLAN_ATTEMPT_1.json").write_text(
        json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    errors = _plan_errors(plan, sources)

    non_essay_errors = [error for error in errors if not error.startswith("essay ")]
    if non_essay_errors:
        repair = (
            prompt
            + "\n\nThe previous plan failed these hard checks:\n"
            + "\n".join(f"- {error}" for error in errors)
            + "\nReturn a complete corrected JSON plan only."
        )
        plan = _core.model_json(hymark, system, repair, max_tokens=5600, temperature=0.18)
        (opportunity_dir / "HOMS_SOURCE_FIRST_PLAN_ATTEMPT_2.json").write_text(
            json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        errors = _plan_errors(plan, sources)

    if errors and len(_essay_errors(errors)) == len(errors):
        plan = _repair_essay_only(hymark, request, sources, plan, opportunity, opportunity_dir)
        errors = _plan_errors(plan, sources)

    if errors:
        raise RuntimeError("History source-first provider plan failed after repair: " + "; ".join(errors))
    return plan


# Patch the retained core in-process. run_builder() resolves these names from the
# core module globals, so all of the original rendering/source-lock machinery is
# retained unchanged.
_core._generation_prompt = _generation_prompt
_core._plan_errors = _plan_errors
_core._generate_plan = _generate_plan

# Re-export the core API so existing imports/tests keep working.
for _name, _value in vars(_core).items():
    if not _name.startswith("__") and _name not in globals():
        globals()[_name] = _value

# Explicitly expose the production overrides after the compatibility export.
globals()["_generation_prompt"] = _generation_prompt
globals()["_plan_errors"] = _plan_errors
globals()["_generate_plan"] = _generate_plan
run_builder = _core.run_builder
main = _core.main
ENGINE_IDENTITY = _core.ENGINE_IDENTITY
SCHEMA = _core.SCHEMA


if __name__ == "__main__":
    raise SystemExit(_core.main())
