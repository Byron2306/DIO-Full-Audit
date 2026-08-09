"""Sophia Phase 6 similarity and provenance guard.

The guard is intentionally conservative: it reports similarity risk and repair
options, not plagiarism findings, unless a source span is visibly present and
the overlap is strong enough to inspect.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional


STOPWORDS = {
    "the", "and", "for", "that", "this", "with", "from", "into", "onto", "are", "was", "were",
    "has", "have", "had", "not", "but", "its", "their", "there", "where", "which", "while",
    "within", "between", "through", "about", "also", "such", "than", "then", "been", "being",
}

COMMON_ACADEMIC_PHRASES = {
    "higher education",
    "academic integrity",
    "academic integrity matters in higher education",
    "generative artificial intelligence",
    "artificial intelligence",
    "student learning",
    "learning outcomes",
    "self directed learning",
    "critical thinking",
    "literature review",
    "research question",
    "methodological approach",
}

CONSTRUCT_GROUPS = [
    {"higher-education", "higher", "education", "universities", "university", "institutional"},
    {"responses", "respond", "responds", "response"},
    {"disclosure", "disclose", "rules", "policy"},
    {"detection", "detect", "detectors"},
    {"assessment", "assessments", "redesign", "redesigned"},
    {"post", "hoc", "enforcement", "after", "fact", "sanction"},
    {"agency", "authorship", "accountable", "learner", "student"},
]

SEMANTIC_CONCEPTS = {
    "governance": {"governance", "govern", "governs", "governed", "governing", "policy", "rules", "oversight", "control", "regulation", "guardrails"},
    "disclosure": {"disclosure", "disclose", "declaring", "declare", "transparency", "acknowledgement"},
    "detection": {"detection", "detect", "detectors", "monitoring", "screening", "surveillance"},
    "assessment_design": {"assessment", "assessments", "redesign", "rubric", "grading", "evaluation", "tasks"},
    "enforcement": {"enforcement", "sanction", "penalty", "misconduct", "discipline", "post", "hoc"},
    "agency": {"agency", "choice", "control", "autonomy", "authorship", "ownership", "accountability", "judgment"},
    "reflection": {"reflection", "reflective", "self-regulation", "metacognition", "revision", "learning"},
    "method": {"method", "methodology", "design", "iterative", "analysis", "refinement", "intervention"},
    "limits": {"limitation", "limitations", "scope", "scalability", "transfer", "generalization", "boundary"},
    "adversarial": {"adversarial", "evasion", "evade", "manipulate", "degrade", "unsafe", "bypass", "attack"},
    "evidence": {"evidence", "source", "provenance", "warrant", "citation", "support", "claim"},
}


@dataclass
class SimilaritySpan:
    source_name: str
    category: str
    risk_level: str
    similarity_score: float
    exact_ngram_overlap: List[str]
    longest_common_sequence: str
    shared_terms: List[str]
    source_span: str
    selected_span: str
    side_by_side: Dict[str, Any]
    citation_present: bool
    protected_common_phrase: bool
    policy_label: str
    repair_options: List[str]
    rationale: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _tokens(text: str) -> List[str]:
    return [
        token
        for token in re.findall(r"[a-z][a-z0-9'-]{2,}", (text or "").lower())
        if token not in STOPWORDS
    ]


def _ngrams(tokens: List[str], n: int) -> set[str]:
    if len(tokens) < n:
        return set()
    return {" ".join(tokens[i:i + n]) for i in range(0, len(tokens) - n + 1)}


def _citation_present(text: str) -> bool:
    return bool(re.search(
        r"\([A-Z][A-Za-z'’-]+(?:\s+et\s+al\.)?,?\s+\d{4}[a-z]?\)|\bdoi\b|https?://|according to|as [A-Z][A-Za-z'’-]+(?: et al\.)? argues",
        text or "",
        flags=re.I,
    ))


def _longest_common_text(a: str, b: str) -> str:
    a_words = re.findall(r"\S+", a or "")
    b_words = re.findall(r"\S+", b or "")
    match = difflib.SequenceMatcher(None, [w.lower() for w in a_words], [w.lower() for w in b_words]).find_longest_match(
        0, len(a_words), 0, len(b_words)
    )
    if match.size < 4:
        return ""
    return " ".join(a_words[match.a:match.a + match.size])[:360]


def _protected_phrase(overlaps: set[str], selected_tokens: List[str]) -> bool:
    if not overlaps:
        return False
    selected_text = " ".join(selected_tokens)
    if len(selected_tokens) <= 9 and _common_phrase_in_text(selected_text):
        return True
    if all(phrase in COMMON_ACADEMIC_PHRASES for phrase in overlaps):
        return True
    if len(selected_tokens) <= 10 and selected_text in COMMON_ACADEMIC_PHRASES:
        return True
    return False


def _common_phrase_in_text(text: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()
    return any(phrase in normalized for phrase in COMMON_ACADEMIC_PHRASES)


def _construct_overlap_score(selected_terms: set[str], source_terms: set[str]) -> float:
    if not selected_terms or not source_terms:
        return 0.0
    hits = 0
    possible = 0
    for group in CONSTRUCT_GROUPS:
        selected_hit = bool(selected_terms & group)
        source_hit = bool(source_terms & group)
        if selected_hit:
            possible += 1
        if selected_hit and source_hit:
            hits += 1
    return hits / max(1, possible)


def _semantic_fingerprint(tokens: List[str]) -> set[str]:
    terms = set(tokens)
    concepts = set()
    for concept, markers in SEMANTIC_CONCEPTS.items():
        if terms & markers:
            concepts.add(concept)
    return concepts


def _semantic_overlap_score(selected_tokens: List[str], source_tokens: List[str]) -> tuple[float, List[str]]:
    selected = _semantic_fingerprint(selected_tokens)
    source = _semantic_fingerprint(source_tokens)
    if not selected or not source:
        return 0.0, []
    overlap = sorted(selected & source)
    score = len(overlap) / max(1, len(selected | source))
    return score, overlap


def _source_text(source: Dict[str, Any]) -> str:
    parts = [
        source.get("exact_span"),
        source.get("quote"),
        source.get("text"),
        source.get("abstract"),
        source.get("summary"),
        source.get("title"),
    ]
    return re.sub(r"\s+", " ", " ".join(str(part or "") for part in parts)).strip()


def _source_name(source: Dict[str, Any], index: int) -> str:
    return str(source.get("source_name") or source.get("title") or source.get("name") or f"Source {index}")


def _window_around_terms(text: str, terms: List[str], *, fallback: int = 360) -> str:
    compact = re.sub(r"\s+", " ", text or "").strip()
    if not compact:
        return ""
    lowered = compact.lower()
    positions = [lowered.find(term.lower()) for term in terms if term and lowered.find(term.lower()) >= 0]
    if not positions:
        return compact[:fallback]
    center = min(positions)
    start = max(0, center - 120)
    end = min(len(compact), center + fallback)
    prefix = "..." if start else ""
    suffix = "..." if end < len(compact) else ""
    return f"{prefix}{compact[start:end]}{suffix}"


def _side_by_side_payload(
    *,
    selected: str,
    source_text: str,
    shared_terms: List[str],
    exact_overlap: List[str],
    longest: str,
    citation_present: bool,
    risk: str,
    category: str,
    semantic_concepts: Optional[List[str]] = None,
) -> Dict[str, Any]:
    overlap_terms = exact_overlap or shared_terms[:10]
    return {
        "selected_span": _window_around_terms(selected, overlap_terms, fallback=420),
        "source_span": _window_around_terms(source_text, overlap_terms, fallback=520),
        "overlap_terms": shared_terms[:12],
        "semantic_concepts": list(semantic_concepts or [])[:8],
        "overlap_phrases": exact_overlap[:6],
        "longest_common_sequence": longest,
        "citation_present": citation_present,
        "inspection_prompt": "Compare wording, attribution, and warrant before revising; do not replace the learner's prose wholesale.",
        "integrity_action": _primary_integrity_action(category, citation_present, risk),
    }


def _primary_integrity_action(category: str, citation_present: bool, risk: str) -> str:
    if risk == "high" and not citation_present:
        return "quote or paraphrase with explicit attribution before release"
    if category == "near_paraphrase" and not citation_present:
        return "add citation, then change structure and warrant in the learner's own terms"
    if category == "citation_needed_overlap":
        return "verify source relationship and add citation if the claim depends on this source"
    if category == "acceptable_common_phrase":
        return "no accusation; keep phrase if it is ordinary disciplinary language"
    return "inspect provenance and keep authorship with the learner"


def _repair_options(category: str, citation_present: bool) -> List[str]:
    options = []
    if not citation_present:
        options.append("cite")
    if category in {"exact_overlap", "citation_needed_overlap"}:
        options.extend(["quote with attribution", "paraphrase with attribution"])
    if category in {"near_paraphrase", "citation_needed_overlap"}:
        options.extend(["narrow claim", "add limitation"])
    options.append("convert assertion to question")
    return list(dict.fromkeys(options))


def analyze_similarity(
    selected_text: str,
    sources: List[Dict[str, Any]],
    *,
    limit: int = 8,
) -> Dict[str, Any]:
    selected = re.sub(r"\s+", " ", selected_text or "").strip()
    selected_tokens = _tokens(selected)
    citation_present = _citation_present(selected)
    if not selected:
        return {
            "method": "phase6_similarity_guard",
            "status": "no_selection",
            "policy_language": "source support unavailable",
            "summary": {"risk_level": "none", "flagged_spans": 0},
            "spans": [],
            "repair_menu": ["select a passage before checking similarity"],
        }
    if not sources:
        return {
            "method": "phase6_similarity_guard",
            "status": "no_source_corpus",
            "policy_language": "source support unavailable",
            "summary": {"risk_level": "unknown", "flagged_spans": 0},
            "spans": [],
            "repair_menu": ["find sources", "paste source spans", "mark claim as needing verification"],
        }

    rows: List[SimilaritySpan] = []
    selected_4 = _ngrams(selected_tokens, 4)
    selected_6 = _ngrams(selected_tokens, 6)
    selected_terms = set(selected_tokens)
    for idx, source in enumerate(sources[:80], start=1):
        text = _source_text(source)
        if not text:
            continue
        source_tokens = _tokens(text)
        if not source_tokens:
            continue
        shared_terms = sorted((selected_terms & set(source_tokens)))[:18]
        source_terms = set(source_tokens)
        source_4 = _ngrams(source_tokens, 4)
        source_6 = _ngrams(source_tokens, 6)
        exact6 = sorted(selected_6 & source_6)
        exact4 = sorted(selected_4 & source_4)
        longest = _longest_common_text(selected, text)
        jaccard = len(selected_terms & source_terms) / max(1, len(selected_terms | source_terms))
        construct_score = _construct_overlap_score(selected_terms, source_terms)
        semantic_score, semantic_concepts = _semantic_overlap_score(selected_tokens, source_tokens)
        lcs_score = min(1.0, len(longest.split()) / max(1, len(selected.split())))
        ngram_score = min(1.0, (len(exact6) * 0.18) + (len(exact4) * 0.08))
        score = round(max(jaccard, construct_score * 0.72, semantic_score * 0.82, lcs_score, ngram_score), 4)
        overlaps = set(exact6 or exact4)
        short_generic = len(selected_tokens) <= 9 and not exact6 and not exact4 and len(longest.split()) < 6
        protected = _protected_phrase(overlaps, selected_tokens) or (
            short_generic and _common_phrase_in_text(selected)
        )
        if protected:
            category = "acceptable_common_phrase"
            risk = "low"
        elif exact6 or len(longest.split()) >= 9:
            category = "exact_overlap"
            risk = "high" if not citation_present else "medium"
        elif not short_generic and (
            (score >= 0.34 and len(shared_terms) >= 4)
            or construct_score >= 0.62
            or (semantic_score >= 0.42 and len(semantic_concepts) >= 2)
        ):
            category = "near_paraphrase"
            risk = "medium" if not citation_present else "low"
        elif score >= 0.18 and not citation_present:
            category = "citation_needed_overlap"
            risk = "medium"
        elif len(shared_terms) >= 3:
            category = "shared_terminology"
            risk = "low"
        else:
            continue
        policy = "similarity risk" if risk in {"high", "medium"} else "needs verification"
        if category == "acceptable_common_phrase":
            policy = "acceptable common phrase"
        rows.append(SimilaritySpan(
            source_name=_source_name(source, idx),
            category=category,
            risk_level=risk,
            similarity_score=score,
            exact_ngram_overlap=(exact6 or exact4)[:8],
            longest_common_sequence=longest,
            shared_terms=shared_terms,
            source_span=text[:700],
            selected_span=selected[:700],
            side_by_side=_side_by_side_payload(
                selected=selected,
                source_text=text,
                shared_terms=shared_terms,
                exact_overlap=(exact6 or exact4),
                longest=longest,
                citation_present=citation_present,
                risk=risk,
                category=category,
                semantic_concepts=semantic_concepts,
            ),
            citation_present=citation_present,
            protected_common_phrase=protected,
            policy_label=policy,
            repair_options=_repair_options(category, citation_present),
            rationale=(
                "Visible source span overlaps the selected passage; inspect attribution, wording, and semantic dependency."
                if risk in {"high", "medium"}
                else "Overlap appears limited, generic, or terminology-level; avoid false accusation."
            ),
        ))
    risk_order = {"high": 0, "medium": 1, "low": 2}
    rows.sort(key=lambda row: (risk_order.get(row.risk_level, 9), -row.similarity_score))
    top = rows[:limit]
    max_risk = "none"
    if any(row.risk_level == "high" for row in top):
        max_risk = "high"
    elif any(row.risk_level == "medium" for row in top):
        max_risk = "medium"
    elif top:
        max_risk = "low"
    return {
        "method": "phase6_similarity_guard",
        "status": "checked",
        "policy_language": "similarity risk, not plagiarism accusation",
        "source_count": len(sources),
        "summary": {
            "risk_level": max_risk,
            "flagged_spans": len(top),
            "high_risk": sum(1 for row in top if row.risk_level == "high"),
            "medium_risk": sum(1 for row in top if row.risk_level == "medium"),
            "low_risk": sum(1 for row in top if row.risk_level == "low"),
            "citation_present": citation_present,
        },
        "spans": [row.to_dict() for row in top],
        "repair_menu": [
            "cite",
            "quote with attribution",
            "paraphrase with attribution",
            "narrow claim",
            "add limitation",
            "convert assertion to question",
        ],
    }
