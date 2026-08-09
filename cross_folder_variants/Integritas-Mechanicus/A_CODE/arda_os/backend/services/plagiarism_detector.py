"""
Plagiarism & AI-Text Detector — Sophia Sovereign Assessment Layer
=================================================================
Two complementary tools in one module:

  1. PLAGIARISM DETECTION — compare student text against source documents
       Methods: verbatim span detection, char n-gram Jaccard, word n-gram
                Jaccard, Longest Common Subsequence ratio
       Returns:  PlagiarismReport with similarity scores, verbatim spans
                 (phrase + character offsets for UI highlighting), per-source
                 breakdowns, and a plain-English summary.

  2. AI TEXT DETECTION — estimate probability text was machine-generated
       Signals:  sentence burstiness, AI lexical marker density,
                 sentence-start diversity, mean sentence length,
                 vocabulary uniformity (TTR), passive/hedge density
       Returns:  AiDetectionResult with signal breakdown and verdict.

All pure-Python — no external libraries required.
"""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ──────────────────────────────────────────────
# STOP WORDS
# ──────────────────────────────────────────────
_STOP = frozenset(
    "a an the and or but if in on at to for of with by from is are was were "
    "be been being have has had do does did will would could should may might "
    "shall must i me my we our you your he she it its they them their this that "
    "these those which who whom whose what when where how s t ll ve re".split()
)

# ──────────────────────────────────────────────
# AI LEXICAL MARKERS
# Phrases statistically over-represented in LLM output
# ──────────────────────────────────────────────
_AI_MARKERS: List[str] = [
    "furthermore", "moreover", "additionally", "in addition",
    "it is worth noting", "it is important to note", "it is essential to",
    "it should be noted", "it is crucial", "it is clear that",
    "in conclusion", "to summarize", "in summary", "to conclude",
    "overall", "firstly", "secondly", "thirdly", "lastly", "in this context",
    "as mentioned", "as previously mentioned", "as discussed",
    "this demonstrates", "this highlights", "this suggests", "this indicates",
    "this underscores", "this emphasizes", "this shows",
    "delve into", "delve deeper", "it is evident", "it is apparent",
    "needless to say", "rest assured", "suffice it to say",
    "in light of", "it goes without saying", "on the other hand",
    "having said that", "that being said", "with that in mind",
    "at the end of the day", "in the realm of", "in the world of",
]

_AI_MARKER_RE = re.compile(
    r"\b(" + "|".join(re.escape(m) for m in _AI_MARKERS) + r")\b",
    re.IGNORECASE,
)


# ──────────────────────────────────────────────
# DATA CLASSES
# ──────────────────────────────────────────────

@dataclass
class VerbatimSpan:
    """A chunk of text copied verbatim from a source."""
    phrase: str               # the matched phrase (normalised tokens joined)
    original_phrase: str      # best-effort original-case snippet
    source_name: str
    word_count: int
    char_start: int           # character offset in original student text (-1 if unknown)
    char_end: int             # character offset in original student text (-1 if unknown)


@dataclass
class SourceScore:
    source_name: str
    verbatim_ratio: float
    char_ngram_jaccard: float
    word_ngram_jaccard: float
    lcs_ratio: float
    composite: float


@dataclass
class AiSignal:
    name: str
    value: float           # 0–1, higher = more AI-like
    description: str


@dataclass
class AiDetectionResult:
    ai_probability: float          # 0–1
    verdict: str                   # "likely_human" | "uncertain" | "likely_ai" | "almost_certainly_ai"
    signals: List[AiSignal] = field(default_factory=list)
    summary: str = ""


@dataclass
class PlagiarismReport:
    overall_score: float
    risk_level: str
    source_scores: List[SourceScore] = field(default_factory=list)
    verbatim_spans: List[VerbatimSpan] = field(default_factory=list)
    ai_detection: Optional[AiDetectionResult] = None
    summary: str = ""
    details: Dict = field(default_factory=dict)


# ──────────────────────────────────────────────
# TEXT HELPERS
# ──────────────────────────────────────────────

def _normalise(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^\w\s]", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def _tokenise(text: str) -> List[str]:
    return _normalise(text).split()


def _content_tokens(tokens: List[str]) -> List[str]:
    return [t for t in tokens if t not in _STOP and len(t) > 1]


def _char_ngrams(text: str, n: int = 4) -> frozenset:
    t = _normalise(text)
    return frozenset(t[i: i + n] for i in range(max(0, len(t) - n + 1)))


def _word_ngrams(tokens: List[str], n: int = 2) -> frozenset:
    return frozenset(
        " ".join(tokens[i: i + n]) for i in range(max(0, len(tokens) - n + 1))
    )


def _jaccard(a: frozenset, b: frozenset) -> float:
    if not a and not b:
        return 0.0
    u = len(a | b)
    return len(a & b) / u if u else 0.0


def _split_sentences(text: str) -> List[str]:
    """Split on sentence-ending punctuation."""
    raw = re.split(r"(?<=[.!?])\s+", text.strip())
    return [s.strip() for s in raw if len(s.strip()) > 10]


# ──────────────────────────────────────────────
# LCS RATIO
# ──────────────────────────────────────────────

def _lcs_ratio(a_tokens: List[str], b_tokens: List[str]) -> float:
    a, b = a_tokens[:300], b_tokens[:300]
    m, n = len(a), len(b)
    if not m or not n:
        return 0.0
    prev = [0] * (n + 1)
    best = 0
    for i in range(m):
        curr = [0] * (n + 1)
        for j in range(n):
            if a[i] == b[j]:
                curr[j + 1] = prev[j] + 1
                best = max(best, curr[j + 1])
        prev = curr
    return best / max(m, n)


# ──────────────────────────────────────────────
# VERBATIM SPAN DETECTION
# ──────────────────────────────────────────────

def _find_char_offset(original_text: str, phrase_tokens: List[str]) -> Tuple[int, int]:
    """
    Find the character start/end of a token sequence in the original text.
    Returns (-1, -1) if not found.
    """
    if not phrase_tokens:
        return (-1, -1)
    # Build a loose regex: each token separated by non-word chars
    pattern = r"\b" + r"\W+".join(re.escape(t) for t in phrase_tokens) + r"\b"
    m = re.search(pattern, original_text, re.IGNORECASE)
    if m:
        return (m.start(), m.end())
    return (-1, -1)


def _find_verbatim_spans(
    student_text: str,
    student_tokens: List[str],
    source_tokens: List[str],
    source_name: str,
    min_words: int = 6,
) -> List[VerbatimSpan]:
    spans: List[VerbatimSpan] = []
    i = 0
    while i < len(student_tokens):
        best_length = 0
        for j in range(len(source_tokens)):
            if source_tokens[j] != student_tokens[i]:
                continue
            length = 0
            while (
                i + length < len(student_tokens)
                and j + length < len(source_tokens)
                and student_tokens[i + length] == source_tokens[j + length]
            ):
                length += 1
            if length > best_length:
                best_length = length
        if best_length >= min_words:
            phrase_tokens = student_tokens[i: i + best_length]
            phrase = " ".join(phrase_tokens)
            char_start, char_end = _find_char_offset(student_text, phrase_tokens)
            # Best-effort original snippet
            if char_start >= 0:
                original_phrase = student_text[char_start:char_end]
            else:
                original_phrase = phrase
            spans.append(VerbatimSpan(
                phrase=phrase,
                original_phrase=original_phrase,
                source_name=source_name,
                word_count=best_length,
                char_start=char_start,
                char_end=char_end,
            ))
            i += best_length
        else:
            i += 1
    return spans


def _verbatim_ratio(student_tokens: List[str], source_tokens: List[str], min_words: int = 4) -> float:
    if not student_tokens:
        return 0.0
    covered = 0
    i = 0
    while i < len(student_tokens):
        best_length = 0
        for j in range(len(source_tokens)):
            if source_tokens[j] != student_tokens[i]:
                continue
            length = 0
            while (
                i + length < len(student_tokens)
                and j + length < len(source_tokens)
                and student_tokens[i + length] == source_tokens[j + length]
            ):
                length += 1
            best_length = max(best_length, length)
        if best_length >= min_words:
            covered += best_length
            i += best_length
        else:
            i += 1
    return covered / len(student_tokens)


# ──────────────────────────────────────────────
# SCORE AGAINST ONE SOURCE
# ──────────────────────────────────────────────

def _score_against_source(
    student_text: str,
    source_text: str,
    source_name: str,
) -> Tuple[SourceScore, List[VerbatimSpan]]:
    s_tok = _tokenise(student_text)
    r_tok = _tokenise(source_text)
    s_content = _content_tokens(s_tok)
    r_content = _content_tokens(r_tok)

    verb_ratio = _verbatim_ratio(s_tok, r_tok, min_words=4)
    char_j = _jaccard(_char_ngrams(student_text, 4), _char_ngrams(source_text, 4))
    word_j = _jaccard(
        _word_ngrams(s_content, 2) | _word_ngrams(s_content, 3),
        _word_ngrams(r_content, 2) | _word_ngrams(r_content, 3),
    )
    lcs = _lcs_ratio(s_tok, r_tok)
    composite = (verb_ratio * 0.45) + (char_j * 0.20) + (word_j * 0.20) + (lcs * 0.15)

    spans = _find_verbatim_spans(student_text, s_tok, r_tok, source_name, min_words=6)

    score = SourceScore(
        source_name=source_name,
        verbatim_ratio=round(verb_ratio, 4),
        char_ngram_jaccard=round(char_j, 4),
        word_ngram_jaccard=round(word_j, 4),
        lcs_ratio=round(lcs, 4),
        composite=round(composite, 4),
    )
    return score, spans


# ──────────────────────────────────────────────
# RISK CLASSIFICATION
# ──────────────────────────────────────────────

def _classify_risk(score: float) -> str:
    if score >= 0.70:
        return "critical"
    if score >= 0.45:
        return "high"
    if score >= 0.20:
        return "moderate"
    return "low"


def _build_plagiarism_summary(
    overall: float,
    risk: str,
    source_scores: List[SourceScore],
    spans: List[VerbatimSpan],
) -> str:
    pct = round(overall * 100, 1)
    span_count = len(spans)
    top = max(source_scores, key=lambda s: s.composite) if source_scores else None
    top_name = top.source_name if top else "an uploaded source"

    if risk == "low":
        return (
            f"Similarity score: {pct}% — no significant overlap detected. "
            "The submission appears to be in the student's own words."
        )
    if risk == "moderate":
        base = (
            f"Similarity score: {pct}% — moderate overlap with {top_name}. "
            "Some phrases echo the source closely."
        )
        if span_count:
            base += f" {span_count} verbatim phrase(s) of 6+ words detected."
        base += " Review cited and uncited material before submission."
        return base
    if risk == "high":
        return (
            f"Similarity score: {pct}% — high overlap with {top_name}. "
            f"{span_count} verbatim phrase(s) detected. "
            "This level of similarity is likely to trigger academic integrity flags. "
            "Substantial rewriting and proper citation are needed."
        )
    return (
        f"Similarity score: {pct}% — critical overlap with {top_name}. "
        f"{span_count} verbatim phrase(s) of 6+ words copied directly. "
        "This submission would not pass an academic integrity review. "
        "It must be rewritten from scratch using proper citation practice."
    )


# ──────────────────────────────────────────────
# AI TEXT DETECTION
# ──────────────────────────────────────────────

def _burstiness_signal(text: str) -> AiSignal:
    """
    Burstiness = std(sentence_lengths) / mean(sentence_lengths).
    Human writing is bursty (high variance). AI is uniform (low variance).
    Low burstiness → high AI probability.
    """
    sentences = _split_sentences(text)
    if len(sentences) < 3:
        return AiSignal("burstiness", 0.5, "Too few sentences to measure burstiness reliably.")
    lengths = [len(s.split()) for s in sentences]
    mean = sum(lengths) / len(lengths)
    if mean == 0:
        return AiSignal("burstiness", 0.5, "Mean sentence length is zero.")
    variance = sum((l - mean) ** 2 for l in lengths) / len(lengths)
    std = math.sqrt(variance)
    burstiness = std / mean   # high = human, low = AI
    # Normalise: burstiness > 0.8 is very human-like; < 0.25 is very AI-like
    ai_score = max(0.0, min(1.0, 1.0 - (burstiness / 0.8)))
    return AiSignal(
        "burstiness",
        round(ai_score, 3),
        f"Sentence length variation: {round(burstiness, 2)} "
        f"(low = uniform/AI-like, high = varied/human-like). "
        f"Mean sentence length: {round(mean, 1)} words.",
    )


def _marker_density_signal(text: str) -> AiSignal:
    """Density of AI-signature transitional phrases."""
    tokens = text.lower().split()
    if not tokens:
        return AiSignal("ai_markers", 0.0, "No text.")
    matches = _AI_MARKER_RE.findall(text)
    # Per 100 words
    density = len(matches) / (len(tokens) / 100)
    # Threshold: > 3 per 100 words is very AI-like
    ai_score = max(0.0, min(1.0, density / 4.0))
    found = list({m.lower() for m in matches})[:6]
    found_str = ", ".join(f'"{m}"' for m in found) if found else "none"
    return AiSignal(
        "ai_markers",
        round(ai_score, 3),
        f"{len(matches)} AI-signature phrase(s) found ({round(density, 2)} per 100 words). "
        f"Examples: {found_str}.",
    )


def _sentence_start_diversity_signal(text: str) -> AiSignal:
    """
    AI models tend to start sentences with the same words repeatedly.
    Low diversity of first words → higher AI probability.
    """
    sentences = _split_sentences(text)
    if len(sentences) < 4:
        return AiSignal("sentence_starts", 0.4, "Too few sentences to assess start-word diversity.")
    first_words = [s.split()[0].lower() for s in sentences if s.split()]
    unique_ratio = len(set(first_words)) / len(first_words)
    # < 0.5 unique = repetitive (AI-like); > 0.85 = varied (human-like)
    ai_score = max(0.0, min(1.0, 1.0 - ((unique_ratio - 0.3) / 0.55)))
    return AiSignal(
        "sentence_starts",
        round(ai_score, 3),
        f"{len(set(first_words))} unique sentence-opening words out of {len(first_words)} sentences "
        f"({round(unique_ratio * 100)}% diversity). Low diversity suggests AI authorship.",
    )


def _vocabulary_uniformity_signal(text: str) -> AiSignal:
    """
    Type-Token Ratio (TTR) — adjusted for text length.
    AI text at longer lengths tends toward lower TTR (repetitive vocabulary).
    Uses a root-TTR to compensate for length effects.
    """
    tokens = _tokenise(text)
    content = _content_tokens(tokens)
    if len(content) < 20:
        return AiSignal("vocabulary", 0.4, "Text too short for reliable vocabulary analysis.")
    rttr = len(set(content)) / math.sqrt(len(content))
    # rttr > 8 = rich vocabulary (human-ish), < 4 = poor (AI-ish)
    ai_score = max(0.0, min(1.0, 1.0 - ((rttr - 3.0) / 6.0)))
    return AiSignal(
        "vocabulary",
        round(ai_score, 3),
        f"Root type-token ratio: {round(rttr, 2)} "
        f"({len(set(content))} unique / {len(content)} content words). "
        "Lower values suggest repetitive, AI-generated vocabulary.",
    )


def _mean_sentence_length_signal(text: str) -> AiSignal:
    """
    AI models tend to write longer, more complete sentences than average humans.
    Very long average (> 25 words) is suspicious.
    """
    sentences = _split_sentences(text)
    if not sentences:
        return AiSignal("sentence_length", 0.4, "No sentences detected.")
    lengths = [len(s.split()) for s in sentences]
    mean = sum(lengths) / len(lengths)
    # Normal human: 15–20 words. AI: often 22–30+
    # Map 15→0.1, 25→0.6, 35→1.0
    ai_score = max(0.0, min(1.0, (mean - 12) / 22))
    return AiSignal(
        "sentence_length",
        round(ai_score, 3),
        f"Mean sentence length: {round(mean, 1)} words. "
        "AI-generated text often has consistently long, well-formed sentences.",
    )


def detect_ai_text(text: str) -> AiDetectionResult:
    """
    Estimate probability that text was generated by an AI.
    Returns an AiDetectionResult with signal breakdown.
    """
    if not text or len(text.strip()) < 50:
        return AiDetectionResult(
            ai_probability=0.0,
            verdict="insufficient_text",
            summary="Text is too short for AI detection analysis (minimum ~50 characters).",
        )

    signals = [
        _burstiness_signal(text),
        _marker_density_signal(text),
        _sentence_start_diversity_signal(text),
        _vocabulary_uniformity_signal(text),
        _mean_sentence_length_signal(text),
    ]

    # Weighted composite (burstiness and markers are most reliable)
    weights = [0.30, 0.30, 0.15, 0.15, 0.10]
    ai_prob = sum(s.value * w for s, w in zip(signals, weights))
    ai_prob = round(min(1.0, max(0.0, ai_prob)), 3)

    if ai_prob >= 0.75:
        verdict = "almost_certainly_ai"
        summary = (
            f"AI probability: {round(ai_prob * 100, 1)}% — this text shows strong indicators of machine generation. "
            "Low sentence-length variation, AI-signature phrases, and uniform vocabulary suggest it was not written by a human. "
            "Do not submit without substantial rewriting."
        )
    elif ai_prob >= 0.50:
        verdict = "likely_ai"
        summary = (
            f"AI probability: {round(ai_prob * 100, 1)}% — several AI writing patterns detected. "
            "The text may have been generated or heavily edited by an AI tool. "
            "Review for academic integrity requirements before submission."
        )
    elif ai_prob >= 0.30:
        verdict = "uncertain"
        summary = (
            f"AI probability: {round(ai_prob * 100, 1)}% — mixed signals. "
            "Some AI-typical patterns present but not conclusive. "
            "Statistical analysis alone cannot confirm or rule out AI authorship."
        )
    else:
        verdict = "likely_human"
        summary = (
            f"AI probability: {round(ai_prob * 100, 1)}% — text appears predominantly human-authored. "
            "Sentence variation, vocabulary diversity, and natural phrasing are consistent with human writing."
        )

    return AiDetectionResult(
        ai_probability=ai_prob,
        verdict=verdict,
        signals=signals,
        summary=summary,
    )


# ──────────────────────────────────────────────
# PUBLIC API
# ──────────────────────────────────────────────

def check_plagiarism(
    student_text: str,
    sources: List[Dict],
    run_ai_detection: bool = True,
) -> PlagiarismReport:
    """
    Compare student_text against each source in sources.
    sources: list of {"name": str, "text": str}
    Optionally runs AI text detection on the student text.
    """
    if not student_text or not student_text.strip():
        return PlagiarismReport(
            overall_score=0.0,
            risk_level="low",
            summary="No student text provided.",
        )

    ai_result = detect_ai_text(student_text) if run_ai_detection else None

    if not sources:
        return PlagiarismReport(
            overall_score=0.0,
            risk_level="low",
            ai_detection=ai_result,
            summary="No source documents provided for comparison.",
        )

    all_source_scores: List[SourceScore] = []
    all_spans: List[VerbatimSpan] = []

    for src in sources:
        name = src.get("name") or "Unnamed Source"
        text = src.get("text") or ""
        if not text.strip():
            continue
        score, spans = _score_against_source(student_text, text, name)
        all_source_scores.append(score)
        all_spans.extend(spans)

    if not all_source_scores:
        return PlagiarismReport(
            overall_score=0.0,
            risk_level="low",
            ai_detection=ai_result,
            summary="Source documents were empty — no comparison possible.",
        )

    overall = max(s.composite for s in all_source_scores)
    overall = round(min(overall, 1.0), 4)
    risk = _classify_risk(overall)
    summary = _build_plagiarism_summary(overall, risk, all_source_scores, all_spans)

    # Deduplicate verbatim spans
    seen: set = set()
    deduped: List[VerbatimSpan] = []
    for sp in sorted(all_spans, key=lambda x: -x.word_count):
        if sp.phrase not in seen:
            seen.add(sp.phrase)
            deduped.append(sp)

    return PlagiarismReport(
        overall_score=overall,
        risk_level=risk,
        source_scores=all_source_scores,
        verbatim_spans=deduped,
        ai_detection=ai_result,
        summary=summary,
        details={
            "student_word_count": len(_tokenise(student_text)),
            "sources_checked": len(all_source_scores),
            "verbatim_span_count": len(deduped),
        },
    )


def report_to_dict(report: PlagiarismReport) -> Dict:
    """Serialise a PlagiarismReport to a JSON-safe dict."""
    ai = None
    if report.ai_detection:
        a = report.ai_detection
        ai = {
            "ai_probability": a.ai_probability,
            "verdict": a.verdict,
            "summary": a.summary,
            "signals": [
                {
                    "name": s.name,
                    "value": s.value,
                    "description": s.description,
                }
                for s in a.signals
            ],
        }

    return {
        "overall_score": report.overall_score,
        "risk_level": report.risk_level,
        "summary": report.summary,
        "verbatim_spans": [
            {
                "phrase": sp.phrase,
                "original_phrase": sp.original_phrase,
                "source": sp.source_name,
                "word_count": sp.word_count,
                "char_start": sp.char_start,
                "char_end": sp.char_end,
            }
            for sp in report.verbatim_spans
        ],
        "source_scores": [
            {
                "source": ss.source_name,
                "composite": ss.composite,
                "verbatim_ratio": ss.verbatim_ratio,
                "char_ngram_jaccard": ss.char_ngram_jaccard,
                "word_ngram_jaccard": ss.word_ngram_jaccard,
                "lcs_ratio": ss.lcs_ratio,
            }
            for ss in report.source_scores
        ],
        "ai_detection": ai,
        "details": report.details,
    }
