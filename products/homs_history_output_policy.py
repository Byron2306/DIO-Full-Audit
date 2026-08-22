from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from typing import Any


TEACHING_EXTRACT_REPLACEMENTS = (
    ("official defence of apartheid", "defence of apartheid presented in the teaching extract"),
    ("official justification for apartheid", "justification for apartheid presented in the teaching extract"),
    ("official argument in favour of apartheid", "argument in favour of apartheid presented in the teaching extract"),
    ("apartheid government's justification for its policies", "arguments used to justify apartheid policies"),
    ("apartheid government’s justification for its policies", "arguments used to justify apartheid policies"),
    ("apartheid government's justification", "arguments used to justify apartheid"),
    ("apartheid government’s justification", "arguments used to justify apartheid"),
    ("intentions of apartheid policymakers", "arguments used to justify apartheid"),
)

GENERIC_HISTORY_INSTRUCTION = (
    "Show all working where calculations, planning, diagrams or explanations are required."
)
HISTORY_SPECIFIC_INSTRUCTION = (
    "Support answers with evidence from the sources and relevant historical knowledge where required."
)


def hydrate_history_grade(request: dict[str, Any]) -> dict[str, Any]:
    hydrated = dict(request)
    if hydrated.get("grade") not in (None, "", "None"):
        hydrated["grade"] = int(hydrated["grade"])
        return hydrated
    module_name = str(hydrated.get("module_name") or "")
    match = re.search(r"Grade\s+(\d+)", module_name, flags=re.I)
    if not match:
        raise RuntimeError("HOMS History request has no resolvable grade")
    hydrated["grade"] = int(match.group(1))
    return hydrated


def _replace_case_insensitive(text: str, old: str, new: str) -> str:
    return re.sub(re.escape(old), new, str(text), flags=re.I)


def _normalise_text(text: str) -> str:
    value = str(text)
    for old, new in TEACHING_EXTRACT_REPLACEMENTS:
        value = _replace_case_insensitive(value, old, new)
    return value


def _normalised_blob(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip().casefold()


def _sentences(text: str) -> list[str]:
    return [item.strip() for item in re.split(r"(?<=[.!?])\s+", str(text or "")) if item.strip()]


def _tokens(text: str) -> set[str]:
    stop = {
        "according", "source", "show", "that", "this", "from", "what", "does", "quote", "using",
        "explain", "study", "with", "about", "into", "were", "have", "been", "their", "which",
    }
    return {
        token
        for token in re.findall(r"[a-z0-9]{4,}", str(text or "").casefold())
        if token not in stop
    }


def _best_exact_sentence(question: str, stimulus: str) -> str:
    question_tokens = _tokens(question)
    ranked: list[tuple[int, int, str]] = []
    for sentence in _sentences(stimulus):
        overlap = len(question_tokens & _tokens(sentence))
        ranked.append((overlap, -len(sentence), sentence))
    if not ranked:
        raise RuntimeError("quote question has no source sentence available")
    best = max(ranked, key=lambda row: (row[0], row[1]))
    if best[0] <= 0:
        raise RuntimeError("quote question could not bind an exact source sentence")
    return best[2]


def normalise_history_pack(pack: dict[str, Any]) -> dict[str, Any]:
    """Apply deterministic learner-facing truth/format policy without generating new content."""
    cleaned = json.loads(json.dumps(pack))
    title = str(cleaned.get("assessment_title") or "")
    grade = int(cleaned.get("grade") or 11)
    cleaned["assessment_title"] = re.sub(r"Grade\s+None\b", f"Grade {grade}", title, flags=re.I)

    for section in cleaned.get("sections") or []:
        section_title = str(section.get("title") or "")
        provenance = dict(section.get("source_provenance") or {})
        source_title = str(provenance.get("title") or section_title)
        teaching_extract = "teaching extract" in source_title.casefold()
        stimulus = str(section.get("stimulus") or "")
        for question in section.get("questions") or []:
            if teaching_extract:
                question["question"] = _normalise_text(str(question.get("question") or ""))
                question["memo"] = [_normalise_text(str(item)) for item in question.get("memo") or []]

            question_text = str(question.get("question") or "")
            if "quote from" in question_text.casefold():
                source_blob = _normalised_blob(stimulus)
                exact = [
                    str(item).strip()
                    for item in question.get("memo") or []
                    if str(item).strip() and _normalised_blob(item) in source_blob
                ]
                if not exact:
                    exact = [_best_exact_sentence(question_text, stimulus)]
                question["memo"] = exact
    return cleaned


def history_pack_errors(pack: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    title = str(pack.get("assessment_title") or "")
    if re.search(r"Grade\s+None\b", title, flags=re.I):
        errors.append("assessment title contains Grade None")

    for section_index, section in enumerate(pack.get("sections") or [], 1):
        provenance = dict(section.get("source_provenance") or {})
        source_title = str(provenance.get("title") or section.get("title") or "")
        teaching_extract = "teaching extract" in source_title.casefold()
        stimulus_blob = _normalised_blob(section.get("stimulus") or "")
        for question_index, question in enumerate(section.get("questions") or [], 1):
            blob = json.dumps(question, ensure_ascii=False).casefold()
            if teaching_extract:
                for old, _new in TEACHING_EXTRACT_REPLACEMENTS:
                    if old.casefold() in blob:
                        errors.append(
                            f"section {section_index} question {question_index} overstates teaching-extract authority: {old}"
                        )
            if "quote from" in str(question.get("question") or "").casefold():
                memo = [str(item).strip() for item in question.get("memo") or [] if str(item).strip()]
                if not memo:
                    errors.append(f"section {section_index} question {question_index} quote memo is empty")
                for item in memo:
                    if _normalised_blob(item) not in stimulus_blob:
                        errors.append(
                            f"section {section_index} question {question_index} quote memo is not exact source text"
                        )
    return sorted(set(errors))


def replace_docx_instruction(path: Path) -> None:
    """Replace generic cross-subject wording in an already-rendered DOCX without changing layout assets."""
    path = Path(path).resolve()
    temp = path.with_suffix(path.suffix + ".tmp")
    with zipfile.ZipFile(path, "r") as src, zipfile.ZipFile(temp, "w") as dst:
        for item in src.infolist():
            data = src.read(item.filename)
            if item.filename == "word/document.xml":
                data = data.replace(
                    GENERIC_HISTORY_INSTRUCTION.encode("utf-8"),
                    HISTORY_SPECIFIC_INSTRUCTION.encode("utf-8"),
                )
            dst.writestr(item, data)
    temp.replace(path)


__all__ = [
    "GENERIC_HISTORY_INSTRUCTION",
    "HISTORY_SPECIFIC_INSTRUCTION",
    "history_pack_errors",
    "hydrate_history_grade",
    "normalise_history_pack",
    "replace_docx_instruction",
]
