"""Sophia source-support utilities inspired by KnowEdge Merger.

The bridge keeps Merger's useful tri-artifact pattern without making Sophia
depend on the separate TypeScript app:

- source artifact: the learner's selected claim/passage
- target artifact: a candidate source span
- reference artifact: provenance/citation/style rules
"""

from __future__ import annotations

import re
import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict
from typing import Any, Iterable

try:
    from backend.services.sophia_academic_claim_tools import source_quality_rubric
except Exception:  # pragma: no cover - optional integration
    source_quality_rubric = None  # type: ignore[assignment]


STOPWORDS = {
    "about", "above", "after", "again", "against", "also", "because", "being",
    "between", "could", "does", "doing", "during", "each", "from", "have",
    "into", "more", "most", "only", "other", "over", "should", "some",
    "such", "than", "that", "their", "there", "these", "this", "those",
    "through", "under", "very", "what", "when", "where", "which", "while",
    "with", "would", "paper", "article", "claim", "source", "study",
    "and", "are", "but", "can", "for", "not", "the", "was", "were", "will",
}


CONSTRUCT_FAMILIES: dict[str, set[str]] = {
    "academic_integrity_policy": {
        "academic integrity", "ai policy", "artificial intelligence policy",
        "disclosure", "detection", "assessment redesign", "post hoc enforcement",
        "misconduct", "governance", "citation practice", "authorship policy",
    },
    "human_agency": {
        "agency", "human agency", "learner agency", "authorship", "autonomy",
        "self-regulation", "self regulated", "reflective control",
        "accountable choice", "intentional action", "participation",
    },
    "constitutional_governance": {
        "constitutional ai", "constitutional rules", "auditability", "provenance",
        "verification", "release decision", "governance", "inspectable rules",
        "bounded assistance", "integrity mandate",
    },
    "pedagogical_mediation": {
        "vygotsky", "zpd", "zone of proximal development", "feuerstein",
        "mediated learning", "scaffolding", "formative assessment",
        "ipsative", "diagnostic", "self-directed learning",
    },
    "adversarial_ai": {
        "adversarial ai", "adversarial machine learning", "prompt injection",
        "model evasion", "runtime deception", "threat model", "malicious agent",
        "attack", "red team", "benchmarking",
    },
    "education_learning_sciences": {
        "education", "pedagogy", "learning", "curriculum", "teaching",
        "assessment", "formative", "summative", "feedback", "student",
        "learner", "instruction", "classroom", "self-directed learning",
    },
    "psychology_cognition": {
        "psychology", "cognition", "cognitive", "metacognition", "motivation",
        "self-efficacy", "behaviour", "behavior", "memory", "attention",
        "decision-making", "affect", "emotion", "identity",
    },
    "computer_science_ai": {
        "computer science", "artificial intelligence", "machine learning",
        "large language model", "llm", "algorithm", "software", "data science",
        "natural language processing", "nlp", "agentic", "automation",
    },
    "cybersecurity": {
        "cybersecurity", "security", "malware", "vulnerability", "exploit",
        "threat", "mitre", "attack", "defence", "defense", "incident response",
        "telemetry", "intrusion", "adversary", "zero trust",
    },
    "medicine_health": {
        "medicine", "clinical", "health", "healthcare", "patient", "diagnosis",
        "treatment", "therapy", "epidemiology", "public health", "disease",
        "intervention", "trial", "symptom", "outcome",
    },
    "biology_life_sciences": {
        "biology", "genetics", "genomics", "cell", "molecular", "organism",
        "ecology", "evolution", "protein", "neuroscience", "physiology",
        "biodiversity", "microbiology",
    },
    "physical_sciences_engineering": {
        "physics", "chemistry", "engineering", "materials", "energy",
        "mechanical", "electrical", "civil", "thermodynamics", "quantum",
        "simulation", "manufacturing", "robotics",
    },
    "mathematics_statistics": {
        "mathematics", "statistics", "statistical", "probability", "regression",
        "bayesian", "model", "measurement", "effect size", "confidence interval",
        "p-value", "variance", "correlation", "causal inference",
    },
    "social_sciences": {
        "sociology", "anthropology", "political science", "economics",
        "social", "community", "institution", "policy", "governance",
        "inequality", "culture", "survey", "qualitative", "interview",
    },
    "law_ethics_policy": {
        "law", "legal", "ethics", "policy", "regulation", "compliance",
        "rights", "privacy", "consent", "liability", "governance",
        "accountability", "justice", "standard",
    },
    "business_management": {
        "business", "management", "organization", "organisation", "strategy",
        "market", "finance", "accounting", "operations", "leadership",
        "innovation", "entrepreneurship", "supply chain",
    },
    "arts_humanities": {
        "philosophy", "history", "literature", "language", "rhetoric",
        "theology", "theological", "religion", "art", "music", "media studies",
        "cultural studies", "narrative", "hermeneutics", "hermeneutic",
    },
    "environment_sustainability": {
        "environment", "climate", "sustainability", "ecology", "carbon",
        "biodiversity", "conservation", "agriculture", "water", "energy",
        "pollution", "resilience",
    },
}


FIELD_FAMILIES = {
    "education_learning_sciences",
    "psychology_cognition",
    "computer_science_ai",
    "cybersecurity",
    "medicine_health",
    "biology_life_sciences",
    "physical_sciences_engineering",
    "mathematics_statistics",
    "social_sciences",
    "law_ethics_policy",
    "business_management",
    "arts_humanities",
    "environment_sustainability",
}


@dataclass
class CitationCheck:
    compliance_score: float
    errors: list[dict[str, str]]
    warnings: list[str]
    pass_count: int
    fail_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SourceSupportResult:
    source_name: str
    support_label: str
    confidence: float
    relevance: float
    quality_score: float
    source_quality_rubric: dict[str, Any]
    ranking_score: float
    source_type: str
    source_role: str
    overlap_terms: list[str]
    exact_span: str
    authors: list[str]
    year: str
    container_title: str
    publisher: str
    volume: str
    issue: str
    pages: str
    doi: str
    url: str
    apa_candidate: str
    bibtex_candidate: str
    ris_candidate: str
    csl_json_candidate: dict[str, Any]
    page_status: str
    page_locator: str
    citation_status: str
    metadata_status: str
    metadata_chain: list[str]
    provenance_status: str
    rationale: str
    entailment_status: str
    entailment_warnings: list[str]
    entailment_score: float
    lexical_vector_score: float
    semantic_overlap: list[str]
    broad_field_overlap: list[str]
    semantic_score: float
    citation_check: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _tokens(text: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-z][a-z0-9'-]{2,}", (text or "").lower())
        if token not in STOPWORDS
    ]


def _normalize_construct(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def _term_in_text(term: str, text: str) -> bool:
    normalized = _normalize_construct(term)
    if not normalized:
        return False
    if re.search(r"[^\w\s-]", normalized):
        return normalized in text
    pattern = r"(?<![a-z0-9])" + re.escape(normalized).replace(r"\ ", r"\s+") + r"(?![a-z0-9])"
    return bool(re.search(pattern, text))


def _construct_hits(text: str) -> set[str]:
    normalized = _normalize_construct(text)
    hits: set[str] = set()
    for family, terms in CONSTRUCT_FAMILIES.items():
        if any(_term_in_text(term, normalized) for term in terms):
            hits.add(family)
    return hits


def _semantic_overlap(claim: str, source_text: str) -> tuple[float, list[str], list[str]]:
    claim_hits = _construct_hits(claim)
    source_hits = _construct_hits(source_text)
    if not claim_hits or not source_hits:
        return 0.0, [], []
    shared = sorted(claim_hits & source_hits)
    narrow_shared = [family for family in shared if family not in FIELD_FAMILIES]
    broad_shared = [family for family in shared if family in FIELD_FAMILIES]
    # Broad disciplinary overlap is useful for retrieval/ranking context, but
    # it must not by itself convert a background source into direct evidence.
    score = (len(narrow_shared) + min(1, len(broad_shared)) * 0.10) / max(len(claim_hits), 1)
    return round(min(1.0, score), 3), narrow_shared, broad_shared


def _jaccard(left: Iterable[str], right: Iterable[str]) -> float:
    a = set(left)
    b = set(right)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _term_frequency(tokens: Iterable[str]) -> dict[str, int]:
    freq: dict[str, int] = {}
    for token in tokens:
        freq[token] = freq.get(token, 0) + 1
    return freq


def _cosine_score(left: str, right: str) -> float:
    a = _term_frequency(_tokens(left))
    b = _term_frequency(_tokens(right))
    if not a or not b:
        return 0.0
    shared = set(a) & set(b)
    dot = sum(a[token] * b[token] for token in shared)
    norm_a = sum(value * value for value in a.values()) ** 0.5
    norm_b = sum(value * value for value in b.values()) ** 0.5
    if not norm_a or not norm_b:
        return 0.0
    return round(dot / (norm_a * norm_b), 4)


def _best_span(claim: str, source_text: str) -> tuple[str, float, list[str]]:
    claim_terms = _tokens(claim)
    chunks = [
        chunk.strip()
        for chunk in re.split(r"(?<=[.!?])\s+|\n{2,}", source_text or "")
        if chunk.strip()
    ]
    if not chunks and source_text.strip():
        chunks = [source_text.strip()]
    best = ("", 0.0, [])
    for chunk in chunks[:80]:
        chunk_terms = _tokens(chunk)
        lexical = _jaccard(claim_terms, chunk_terms)
        semantic, _, _ = _semantic_overlap(claim, chunk)
        score = min(1.0, lexical + semantic * 0.18)
        overlap = sorted(set(claim_terms) & set(chunk_terms))[:12]
        if score > best[1]:
            best = (chunk[:900], score, overlap)
    return best


def _extract_doi(*values: Any) -> str:
    joined = " ".join(str(value or "") for value in values)
    match = re.search(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", joined, flags=re.I)
    if not match:
        return ""
    return match.group(0).rstrip(".,;)").lower()


def _extract_url(*values: Any) -> str:
    joined = " ".join(str(value or "") for value in values)
    doi = _extract_doi(joined)
    if doi:
        return f"https://doi.org/{doi}"
    match = re.search(r"https?://[^\s)>\"]+", joined, flags=re.I)
    if not match:
        return ""
    return match.group(0).rstrip(".,;)")


def _source_authors(source: dict[str, Any]) -> list[str]:
    raw = source.get("authors") or source.get("author") or []
    if isinstance(raw, str):
        raw = [part.strip() for part in re.split(r",|;|\band\b", raw) if part.strip()]
    return [str(author).strip() for author in list(raw)[:6] if str(author).strip()]


def _source_year(source: dict[str, Any], text: str) -> str:
    raw = str(source.get("year") or source.get("publication_year") or "").strip()
    if re.fullmatch(r"(19|20)\d{2}", raw):
        return raw
    match = re.search(r"\b(19|20)\d{2}\b", text or "")
    return match.group(0) if match else "n.d."


def _source_title(source: dict[str, Any]) -> str:
    return str(source.get("name") or source.get("title") or "Untitled source").strip()


def _source_field(source: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = source.get(key)
        if isinstance(value, list):
            value = next((item for item in value if str(item).strip()), "")
        if value not in (None, ""):
            return str(value).strip()
    return ""


def enrich_crossref_metadata(source: dict[str, Any], *, timeout: float = 2.5) -> dict[str, Any]:
    """Best-effort DOI metadata enrichment with explicit failure status."""
    enriched = dict(source)
    doi = _extract_doi(source.get("doi"), source.get("url"), source.get("text"), source.get("name"), source.get("title"))
    if not doi:
        enriched["metadata_status"] = "no DOI available for live metadata enrichment"
        return enriched
    url = f"https://api.crossref.org/works/{urllib.parse.quote(doi)}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Sophia-Arda-OS/1.0 (mailto:sophia@arda-os)"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="replace"))
        message = payload.get("message") or {}
        if not enriched.get("title"):
            titles = message.get("title") or []
            if titles:
                enriched["title"] = str(titles[0])
        if not enriched.get("name") and enriched.get("title"):
            enriched["name"] = enriched["title"]
        if not enriched.get("year"):
            date_parts = (
                (message.get("published-print") or {}).get("date-parts")
                or (message.get("published-online") or {}).get("date-parts")
                or (message.get("issued") or {}).get("date-parts")
                or []
            )
            if date_parts and date_parts[0]:
                enriched["year"] = str(date_parts[0][0])
        if not enriched.get("authors"):
            authors = []
            for author in (message.get("author") or [])[:6]:
                given = str(author.get("given") or "").strip()
                family = str(author.get("family") or "").strip()
                full = " ".join(part for part in (given, family) if part)
                if full:
                    authors.append(full)
            if authors:
                enriched["authors"] = authors
        if not enriched.get("source_type"):
            enriched["source_type"] = str(message.get("type") or "crossref metadata")
        container = message.get("container-title") or []
        if container and not enriched.get("container_title"):
            enriched["container_title"] = str(container[0])
        for source_key, target_key in (
            ("publisher", "publisher"),
            ("volume", "volume"),
            ("issue", "issue"),
            ("page", "pages"),
        ):
            if message.get(source_key) and not enriched.get(target_key):
                enriched[target_key] = str(message.get(source_key))
        enriched["doi"] = doi
        enriched["url"] = enriched.get("url") or f"https://doi.org/{doi}"
        enriched["metadata_status"] = "crossref metadata verified"
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        enriched["metadata_status"] = f"crossref enrichment failed: {exc.__class__.__name__}"
    return enriched


def _apply_openalex_work(enriched: dict[str, Any], work: dict[str, Any]) -> dict[str, Any]:
    title = work.get("title") or ""
    if title:
        enriched["title"] = enriched.get("title") or title
        enriched["name"] = enriched.get("name") or title
    year = work.get("publication_year")
    if year and not enriched.get("year"):
        enriched["year"] = str(year)
    authors = [
        author.get("author", {}).get("display_name", "")
        for author in (work.get("authorships") or [])[:6]
        if author.get("author", {}).get("display_name")
    ]
    if authors and not enriched.get("authors"):
        enriched["authors"] = authors
    doi = _extract_doi(work.get("doi"), enriched.get("doi"), enriched.get("url"))
    if doi:
        enriched["doi"] = doi
    location = work.get("primary_location") or {}
    source = location.get("source") or {}
    if source.get("display_name") and not enriched.get("container_title"):
        enriched["container_title"] = str(source.get("display_name"))
    landing = location.get("landing_page_url") or ""
    if landing and not enriched.get("url"):
        enriched["url"] = landing
    elif doi and not enriched.get("url"):
        enriched["url"] = f"https://doi.org/{doi}"
    if not enriched.get("source_type"):
        enriched["source_type"] = "OpenAlex scholarly metadata"
    biblio = work.get("biblio") or {}
    for source_key, target_key in (
        ("volume", "volume"),
        ("issue", "issue"),
        ("first_page", "page_start"),
        ("last_page", "page_end"),
    ):
        if biblio.get(source_key) and not enriched.get(target_key):
            enriched[target_key] = str(biblio.get(source_key))
    if (enriched.get("page_start") or enriched.get("page_end")) and not enriched.get("pages"):
        start = str(enriched.get("page_start") or "").strip()
        end = str(enriched.get("page_end") or "").strip()
        enriched["pages"] = f"{start}-{end}" if start and end and start != end else (start or end)
    inv = work.get("abstract_inverted_index") or {}
    if inv and not any(enriched.get(key) for key in ("text", "abstract", "summary")):
        max_pos = max((pos for positions in inv.values() for pos in positions), default=0)
        words_arr = [""] * (max_pos + 1)
        for word, positions in inv.items():
            for pos in positions:
                if pos <= max_pos:
                    words_arr[pos] = word
        abstract = " ".join(word for word in words_arr if word).strip()
        if abstract:
            enriched["abstract"] = abstract[:2000]
    return enriched


def enrich_openalex_metadata(source: dict[str, Any], *, timeout: float = 3.0) -> dict[str, Any]:
    """Best-effort OpenAlex enrichment by DOI first, then title search."""
    enriched = dict(source)
    doi = _extract_doi(source.get("doi"), source.get("url"), source.get("text"), source.get("name"), source.get("title"))
    title = _source_title(source)
    if doi:
        query = f"filter=doi:{urllib.parse.quote(doi)}"
    elif title and title != "Untitled source":
        query = f"search={urllib.parse.quote(title)}"
    else:
        enriched["metadata_status"] = "openalex enrichment skipped: no DOI or title"
        return enriched
    url = (
        "https://api.openalex.org/works"
        f"?{query}&per-page=1"
        "&select=title,authorships,abstract_inverted_index,publication_year,doi,primary_location"
        ",biblio"
        "&mailto=sophia@arda-os"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Sophia-Arda-OS/1.0 (mailto:sophia@arda-os)"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="replace"))
        results = payload.get("results") or []
        if not results:
            enriched["metadata_status"] = "openalex enrichment found no matching work"
            return enriched
        enriched = _apply_openalex_work(enriched, results[0])
        enriched["metadata_status"] = "openalex metadata verified"
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        enriched["metadata_status"] = f"openalex enrichment failed: {exc.__class__.__name__}"
    return enriched


def enrich_source_metadata(source: dict[str, Any], *, timeout: float = 3.0) -> dict[str, Any]:
    """Best-effort metadata chain: Crossref by DOI, then OpenAlex fallback."""
    doi = _extract_doi(source.get("doi"), source.get("url"), source.get("text"), source.get("name"), source.get("title"))
    if doi:
        crossref = enrich_crossref_metadata(source, timeout=min(timeout, 2.5))
        if crossref.get("metadata_status") == "crossref metadata verified":
            crossref["metadata_chain"] = ["crossref"]
            return crossref
        openalex = enrich_openalex_metadata(source, timeout=timeout)
        openalex["metadata_chain"] = ["crossref_failed", "openalex"]
        openalex["metadata_status"] = (
            "openalex metadata verified after crossref fallback"
            if openalex.get("metadata_status") == "openalex metadata verified"
            else f"{crossref.get('metadata_status')}; {openalex.get('metadata_status')}"
        )
        return openalex
    openalex = enrich_openalex_metadata(source, timeout=timeout)
    openalex["metadata_chain"] = ["openalex"]
    return openalex


def _apa_author_string(authors: list[str]) -> str:
    if not authors:
        return "Unknown author"
    formatted = []
    for author in authors[:6]:
        bits = author.replace(".", "").split()
        if len(bits) >= 2:
            surname = bits[-1]
            initials = " ".join(f"{part[0]}." for part in bits[:-1] if part)
            formatted.append(f"{surname}, {initials}".strip())
        else:
            formatted.append(author)
    if len(authors) > 6:
        formatted.append("...")
    if len(formatted) == 1:
        return formatted[0]
    return ", ".join(formatted[:-1]) + f", & {formatted[-1]}"


def _apa_candidate(
    source_name: str,
    authors: list[str],
    year: str,
    doi: str,
    url: str,
    source_type: str,
    *,
    container_title: str = "",
    volume: str = "",
    issue: str = "",
    pages: str = "",
) -> str:
    author_text = _apa_author_string(authors)
    title = re.sub(r"\s+", " ", source_name or "Untitled source").strip().rstrip(".")
    locator = f"https://doi.org/{doi}" if doi else url
    suffix = f" {locator}" if locator else ""
    if "wikipedia" in source_type.lower() or "encyclopedia" in source_type.lower():
        return f"{author_text}. ({year}). {title}. {suffix}".strip()
    if container_title:
        vol_issue = ""
        if volume and issue:
            vol_issue = f", {volume}({issue})"
        elif volume:
            vol_issue = f", {volume}"
        page_text = f", {pages}" if pages else ""
        return f"{author_text}. ({year}). {title}. {container_title}{vol_issue}{page_text}.{suffix}".strip()
    return f"{author_text}. ({year}). {title}.{suffix}".strip()


def _citation_key(authors: list[str], year: str, title: str) -> str:
    first = "unknown"
    if authors:
        first = re.sub(r"[^A-Za-z0-9]", "", authors[0].split()[-1]).lower() or "unknown"
    title_word = next((token for token in _tokens(title) if token not in {"untitled"}), "source")
    return f"{first}{year if year != 'n.d.' else 'nd'}{title_word}"


def _bibtex_candidate(
    source_name: str,
    authors: list[str],
    year: str,
    doi: str,
    url: str,
    source_type: str,
    *,
    container_title: str = "",
    publisher: str = "",
    volume: str = "",
    issue: str = "",
    pages: str = "",
) -> str:
    entry_type = "misc"
    lowered = source_type.lower()
    if any(term in lowered for term in ("journal", "scholarly", "openalex", "doi", "article")):
        entry_type = "article"
    elif any(term in lowered for term in ("book", "chapter")):
        entry_type = "incollection"
    elif any(term in lowered for term in ("report", "policy", "guidance", "institutional")):
        entry_type = "techreport"
    fields = [
        f"  title = {{{source_name}}}",
        f"  year = {{{year}}}",
    ]
    if authors:
        fields.insert(0, f"  author = {{{' and '.join(authors)}}}")
    if container_title:
        fields.append(f"  journal = {{{container_title}}}" if entry_type == "article" else f"  booktitle = {{{container_title}}}")
    if publisher:
        fields.append(f"  publisher = {{{publisher}}}")
    if volume:
        fields.append(f"  volume = {{{volume}}}")
    if issue:
        fields.append(f"  number = {{{issue}}}")
    if pages:
        fields.append(f"  pages = {{{pages}}}")
    if doi:
        fields.append(f"  doi = {{{doi}}}")
    if url:
        fields.append(f"  url = {{{url}}}")
    return f"@{entry_type}{{{_citation_key(authors, year, source_name)},\n" + ",\n".join(fields) + "\n}"


def _ris_candidate(
    source_name: str,
    authors: list[str],
    year: str,
    doi: str,
    url: str,
    source_type: str,
    *,
    container_title: str = "",
    publisher: str = "",
    volume: str = "",
    issue: str = "",
    pages: str = "",
) -> str:
    lowered = source_type.lower()
    ty = "GEN"
    if any(term in lowered for term in ("journal", "scholarly", "openalex", "doi", "article")):
        ty = "JOUR"
    elif any(term in lowered for term in ("book", "chapter")):
        ty = "CHAP"
    elif any(term in lowered for term in ("report", "policy", "guidance", "institutional")):
        ty = "RPRT"
    lines = [f"TY  - {ty}", f"TI  - {source_name}"]
    for author in authors:
        lines.append(f"AU  - {author}")
    if container_title:
        lines.append(f"JO  - {container_title}")
    if publisher:
        lines.append(f"PB  - {publisher}")
    if volume:
        lines.append(f"VL  - {volume}")
    if issue:
        lines.append(f"IS  - {issue}")
    if pages:
        lines.append(f"SP  - {pages.split('-', 1)[0]}")
        if "-" in pages:
            lines.append(f"EP  - {pages.split('-', 1)[1]}")
    if year != "n.d.":
        lines.append(f"PY  - {year}")
    if doi:
        lines.append(f"DO  - {doi}")
    if url:
        lines.append(f"UR  - {url}")
    lines.append("ER  -")
    return "\n".join(lines)


def _csl_json_candidate(
    source_name: str,
    authors: list[str],
    year: str,
    doi: str,
    url: str,
    source_type: str,
    *,
    container_title: str = "",
    publisher: str = "",
    volume: str = "",
    issue: str = "",
    pages: str = "",
) -> dict[str, Any]:
    lowered = source_type.lower()
    csl_type = "article-journal" if any(term in lowered for term in ("journal", "scholarly", "openalex", "doi", "article")) else "document"
    if any(term in lowered for term in ("book", "chapter")):
        csl_type = "chapter"
    elif any(term in lowered for term in ("report", "policy", "guidance", "institutional")):
        csl_type = "report"
    item: dict[str, Any] = {
        "type": csl_type,
        "title": source_name,
    }
    if year != "n.d.":
        item["issued"] = {"date-parts": [[int(year)]]}
    if authors:
        item["author"] = []
        for author in authors:
            bits = author.split()
            if len(bits) >= 2:
                item["author"].append({"given": " ".join(bits[:-1]), "family": bits[-1]})
            else:
                item["author"].append({"literal": author})
    if doi:
        item["DOI"] = doi
    if url:
        item["URL"] = url
    if container_title:
        item["container-title"] = container_title
    if publisher:
        item["publisher"] = publisher
    if volume:
        item["volume"] = volume
    if issue:
        item["issue"] = issue
    if pages:
        item["page"] = pages
    return item


def _page_locator_from_source(source: dict[str, Any], source_text: str, span: str = "") -> str:
    for key in ("page", "page_number", "page_start", "page_label", "locator"):
        value = source.get(key)
        if value not in (None, ""):
            return f"p. {value}" if str(value).isdigit() else str(value)
    for container in (source.get("span"), source.get("best_span")):
        if isinstance(container, dict):
            for key in ("page", "page_number", "page_start", "page_label", "locator"):
                value = container.get(key)
                if value not in (None, ""):
                    return f"p. {value}" if str(value).isdigit() else str(value)
    for candidate in (span, source_text):
        match = re.search(r"\b(?:p\.|pp\.|page|pages)\s*(\d+(?:\s*[-–]\s*\d+)?)", candidate or "", flags=re.I)
        if match:
            prefix = "pp." if re.search(r"[-–]", match.group(1)) else "p."
            return f"{prefix} {match.group(1).replace(' ', '')}"
    return ""


def _page_status(page_locator: str) -> str:
    if page_locator:
        return "page/span marker visible"
    return "no page number visible; do not invent one"


def _claim_scope_warnings(claim: str, source_text: str, label: str) -> tuple[str, list[str]]:
    warnings: list[str] = []
    claim_l = (claim or "").lower()
    source_l = (source_text or "").lower()
    universal_markers = (
        "all ", "every ", "always", "never", "proves", "proof", "establishes",
        "guarantees", "causes", "eliminates", "solves", "across classrooms",
        "institutional-scale", "all contexts", "definitively",
    )
    limited_markers = (
        "pilot", "preliminary", "limited", "small sample", "may", "might",
        "suggests", "associated", "correlat", "not establish", "does not establish",
        "future research", "cannot determine", "context-specific", "case study",
    )
    if any(marker in claim_l for marker in universal_markers):
        if not any(marker in source_l for marker in universal_markers):
            warnings.append("claim uses proof/universal/causal scope not visible in the source span")
    if any(marker in source_l for marker in limited_markers):
        warnings.append("source span contains limitation or uncertainty language")
    if re.search(r"\bcaus(?:e|es|al|ation)\b|\bimpact\b|\beffect\b", claim_l) and not re.search(r"\btrial\b|\bexperiment\b|\bcausal\b|\brandomi[sz]ed\b|\bintervention\b", source_l):
        warnings.append("causal or impact wording needs stronger method evidence")
    if label == "supports" and warnings:
        return "support_with_scope_limit", warnings
    if label in {"partially supports", "background only"} and warnings:
        return "partial_or_contextual_only", warnings
    if label in {"contradicts", "does not support", "insufficient text"}:
        return "not_entailed", warnings
    return ("entailed_by_visible_span" if label == "supports" else "bounded_lead"), warnings


def _entailment_score(label: str, relevance: float, lexical_vector_score: float, semantic_score: float, warnings: list[str]) -> float:
    base = {
        "supports": 0.78,
        "partially supports": 0.58,
        "background only": 0.34,
        "contradicts": 0.18,
        "does not support": 0.08,
        "insufficient text": 0.02,
    }.get(label, 0.1)
    score = base + relevance * 0.12 + lexical_vector_score * 0.08 + semantic_score * 0.06
    score -= min(0.22, 0.07 * len(warnings))
    return round(max(0.0, min(1.0, score)), 4)


def _source_text(source: dict[str, Any]) -> str:
    direct = str(source.get("text") or source.get("summary") or source.get("abstract") or "").strip()
    spans = source.get("spans")
    if isinstance(spans, list):
        parts = []
        for span in spans[:80]:
            if isinstance(span, dict):
                quote = str(span.get("quote") or span.get("text") or "").strip()
                page = span.get("page") or span.get("page_number") or span.get("page_start") or span.get("page_label")
                if quote:
                    parts.append(f"page {page}: {quote}" if page not in (None, "") else quote)
        if parts:
            return "\n".join(parts)
    return direct


def citation_check(text: str) -> CitationCheck:
    errors: list[dict[str, str]] = []
    warnings: list[str] = []
    pass_count = 0
    fail_count = 0

    def run_check(passed: bool, type_: str, message: str, suggestion: str, rule: str) -> None:
        nonlocal pass_count, fail_count
        if passed:
            pass_count += 1
        else:
            fail_count += 1
            errors.append({"type": type_, "text": message, "suggestion": suggestion, "rule": rule})

    sample = (text or "")[:5000]
    run_check(
        not re.match(
            r"^\s*(?:\[?\d+[.\]]?\s+)?[A-Z][A-Za-z'\u2019-]+\s+"
            r"[A-Z][A-Za-z'\u2019-]+(?:,|\s*\()",
            sample,
        ),
        "NAME_ORDER",
        "Detected possible FirstName LastName reference pattern.",
        "Check whether the reference list needs Last, F. M. ordering.",
        "APA author format",
    )
    run_check(
        bool(re.search(r"\(\d{4}[a-z]?\)", text or "") or re.search(r"\b20\d{2}\b", text or "")),
        "YEAR_FORMAT",
        "No clear year marker detected.",
        "Add or verify publication year before treating this as citation-ready.",
        "APA year/provenance",
    )
    run_check(
        "dx.doi.org" not in (text or "").lower(),
        "DOI_FORMAT",
        "Legacy dx.doi.org DOI form detected.",
        "Use https://doi.org/ where a DOI is available.",
        "APA DOI format",
    )
    run_check(
        not re.search(r"\([A-Za-z,\s]+ and [A-Za-z,\s]+,\s*\d{4}\)", text or ""),
        "AMPERSAND",
        "Found 'and' inside parenthetical citation.",
        "Use '&' inside parentheses if this is APA style.",
        "APA in-text citation",
    )
    run_check(
        not re.search(r"\bet al(?!\.)", text or "", flags=re.I),
        "ET_AL_PUNC",
        "Detected 'et al' without a period.",
        "Use 'et al.'",
        "APA in-text citation",
    )

    if "retrieved from" in (text or "").lower() and not re.search(r"retrieved\s+\w+\s+\d{1,2},\s+\d{4}", text or "", flags=re.I):
        warnings.append("Dynamic web sources may need an access date.")

    total = pass_count + fail_count
    score = round((pass_count / total) * 100, 1) if total else 0.0
    return CitationCheck(score, errors, warnings, pass_count, fail_count)


def source_quality_score(source: dict[str, Any]) -> tuple[float, str]:
    joined = " ".join(str(source.get(key) or "") for key in ("name", "source_type", "category", "evidence_tier")).lower()
    if any(term in joined for term in ("systematic review", "meta-analysis", "scoping review")):
        return 0.93, "review-level scholarly synthesis"
    if any(term in joined for term in ("peer", "journal", "openalex", "doi", "scholarly")):
        return 0.86, "scholarly/citation-indexed lead"
    if re.search(r"\beric\b|education_index", joined):
        return 0.84, "education research index"
    if any(term in joined for term in ("policy", "guidance", "institutional", "standard")):
        return 0.78, "policy/guidance source"
    if any(term in joined for term in ("book", "chapter", "theory", "philosophy")):
        return 0.74, "theoretical/book source"
    if any(term in joined for term in ("preprint", "arxiv")):
        return 0.66, "preprint/technical lead"
    if any(term in joined for term in ("uploaded", "session_supplied", "document")):
        return 0.68, "session-supplied document span"
    if any(term in joined for term in ("wikipedia", "encyclopedia")):
        return 0.48, "background/encyclopedic source"
    return 0.55, "unclassified source lead"


def source_role_for_claim(claim: str, source: dict[str, Any], source_text: str) -> str:
    joined = " ".join(
        str(part or "")
        for part in (
            claim,
            source.get("name"),
            source.get("source_type"),
            source.get("category"),
            source_text[:1200],
        )
    ).lower()
    if any(term in joined for term in ("policy", "guidance", "responsible use", "compliance", "disclosure", "detection", "assessment redesign", "misconduct", "academic integrity")):
        return "policy/integrity context"
    if any(term in joined for term in ("agency", "authorship", "autonomy", "self-regulated", "mediated learning", "vygotsky", "feuerstein")):
        return "theory/construct definition"
    if any(term in joined for term in ("method", "sample", "participants", "dataset", "protocol", "evaluation", "instrument", "analysis")):
        return "method/evaluation evidence"
    if any(term in joined for term in ("governance", "audit", "provenance", "constitutional", "assurance", "verification")):
        return "governance/assurance evidence"
    broad_hits = sorted(_construct_hits(joined) & FIELD_FAMILIES)
    if broad_hits:
        return f"disciplinary context: {broad_hits[0].replace('_', ' ')}"
    return "background/context"


def _ranking_score(label: str, confidence: float, relevance: float, quality: float, citation_score: float) -> float:
    label_weight = {
        "supports": 1.0,
        "partially supports": 0.78,
        "contradicts": 0.72,
        "background only": 0.42,
        "does not support": 0.18,
        "insufficient text": 0.05,
    }.get(label, 0.2)
    citation_component = max(0.0, min(1.0, citation_score / 100))
    score = (
        label_weight * 0.38
        + confidence * 0.24
        + relevance * 0.2
        + quality * 0.13
        + citation_component * 0.05
    )
    return round(score, 4)


def classify_source_support(claim: str, source: dict[str, Any], *, enrich_metadata: bool = False) -> SourceSupportResult:
    if enrich_metadata:
        source = enrich_source_metadata(source)
    source_text = _source_text(source)
    source_name = _source_title(source)
    source_type = str(source.get("source_type") or source.get("source") or source.get("category") or "unclassified").strip()
    authors = _source_authors(source)
    year = _source_year(source, f"{source_name} {source_text}")
    container_title = _source_field(source, "container_title", "container-title", "journal", "publication", "venue")
    publisher = _source_field(source, "publisher")
    volume = _source_field(source, "volume")
    issue = _source_field(source, "issue", "number")
    pages = _source_field(source, "pages", "page")
    if not pages and (_source_field(source, "page_start") or _source_field(source, "page_end")):
        start = _source_field(source, "page_start")
        end = _source_field(source, "page_end")
        pages = f"{start}-{end}" if start and end and start != end else (start or end)
    doi = _extract_doi(source.get("doi"), source.get("url"), source_text, source_name)
    url = _extract_url(source.get("url"), source.get("doi"), source_text)
    apa_candidate = _apa_candidate(source_name, authors, year, doi, url, source_type, container_title=container_title, volume=volume, issue=issue, pages=pages)
    bibtex_candidate = _bibtex_candidate(source_name, authors, year, doi, url, source_type, container_title=container_title, publisher=publisher, volume=volume, issue=issue, pages=pages)
    ris_candidate = _ris_candidate(source_name, authors, year, doi, url, source_type, container_title=container_title, publisher=publisher, volume=volume, issue=issue, pages=pages)
    csl_json_candidate = _csl_json_candidate(source_name, authors, year, doi, url, source_type, container_title=container_title, publisher=publisher, volume=volume, issue=issue, pages=pages)
    span, relevance, overlap = _best_span(claim, source_text)
    lexical_vector_score = _cosine_score(claim, span or source_text)
    page_locator = _page_locator_from_source(source, source_text, span)
    page_status = _page_status(page_locator)
    quality, quality_label = source_quality_score(source)
    rubric = source_quality_rubric(source) if source_quality_rubric else {}
    source_role = source_role_for_claim(claim, source, source_text)
    semantic_score, semantic_terms, broad_terms = _semantic_overlap(claim, source_text)
    blended_relevance = min(1.0, relevance + semantic_score * 0.12)
    lower = f"{source_name} {source_text}".lower()
    contradiction_patterns = (
        r"\bcontrary to\b",
        r"\bcontradict(?:s|ed|ory)?\b",
        r"\bno evidence that\b",
        r"\bfailed to (?:show|demonstrate|establish|support|improve)\b",
        r"\bdid not (?:show|demonstrate|establish|support|improve|preserve)\b",
        r"\bdoes not (?:show|demonstrate|establish|support|prove|preserve)\b",
        r"\breduced control\b",
    )
    has_contradiction = any(re.search(pattern, lower) for pattern in contradiction_patterns)
    has_partial_caveat = bool(re.search(
        r"\b(?:but|however|although)\b.{0,90}\b(?:does not|did not|without|not evaluate|not assess|not measure)\b",
        lower,
    ))

    if not source_text:
        label = "insufficient text"
        confidence = 0.25
    elif has_contradiction and blended_relevance >= 0.08:
        label = "contradicts"
        confidence = min(0.88, 0.48 + blended_relevance + quality / 5)
    elif blended_relevance >= 0.22 and not has_partial_caveat:
        label = "supports"
        confidence = min(0.95, 0.52 + blended_relevance + quality / 4)
    elif blended_relevance >= 0.12:
        label = "partially supports"
        confidence = min(0.82, 0.42 + blended_relevance + quality / 5)
    elif blended_relevance >= 0.055:
        label = "background only"
        confidence = min(0.72, 0.34 + blended_relevance + quality / 6)
    elif broad_terms and blended_relevance >= 0.035 and source_role.startswith("disciplinary context:"):
        label = "background only"
        confidence = min(0.64, 0.34 + blended_relevance + quality / 8)
    elif quality >= 0.70 and source_role != "background/context":
        label = "background only"
        confidence = min(0.68, 0.38 + quality / 6)
    else:
        label = "does not support"
        confidence = min(0.8, 0.45 + quality / 8)

    entailment_status, entailment_warnings = _claim_scope_warnings(claim, source_text, label)
    entailment_score = _entailment_score(label, blended_relevance, lexical_vector_score, semantic_score, entailment_warnings)
    cite = citation_check(f"{source_name}\n{source_text[:1500]}")
    citation_status = "citation-ready lead" if cite.compliance_score >= 80 else "needs citation cleanup"
    metadata_status = str(source.get("metadata_status") or ("doi metadata present" if doi else "basic metadata only; verify before final citation"))
    metadata_chain = [str(item) for item in (source.get("metadata_chain") or []) if str(item).strip()]
    ranking_score = _ranking_score(label, confidence, blended_relevance, quality, cite.compliance_score)
    provenance_status = str(source.get("evidence_tier") or source.get("source_type") or source.get("source") or "session lead")
    rationale = (
        f"{label}: lexical/construct relevance={blended_relevance:.2f}; "
        f"semantic families={', '.join(semantic_terms) or 'none'}; "
        f"quality={quality:.2f} ({quality_label}); lexical terms={', '.join(overlap[:6]) or 'none'}."
    )
    return SourceSupportResult(
        source_name=source_name,
        support_label=label,
        confidence=round(confidence, 3),
        relevance=round(blended_relevance, 3),
        quality_score=round(quality, 3),
        source_quality_rubric=rubric,
        ranking_score=ranking_score,
        source_type=source_type,
        source_role=source_role,
        overlap_terms=overlap,
        exact_span=span,
        authors=authors,
        year=year,
        container_title=container_title,
        publisher=publisher,
        volume=volume,
        issue=issue,
        pages=pages,
        doi=doi,
        url=url,
        apa_candidate=apa_candidate,
        bibtex_candidate=bibtex_candidate,
        ris_candidate=ris_candidate,
        csl_json_candidate=csl_json_candidate,
        page_status=page_status,
        page_locator=page_locator,
        citation_status=citation_status,
        metadata_status=metadata_status,
        metadata_chain=metadata_chain,
        provenance_status=provenance_status,
        rationale=rationale,
        entailment_status=entailment_status,
        entailment_warnings=entailment_warnings,
        entailment_score=entailment_score,
        lexical_vector_score=lexical_vector_score,
        semantic_overlap=semantic_terms,
        broad_field_overlap=broad_terms,
        semantic_score=semantic_score,
        citation_check=cite.to_dict(),
    )


def map_claim_to_sources(
    claim: str,
    sources: list[dict[str, Any]],
    *,
    limit: int = 6,
    enrich_metadata: bool = False,
) -> dict[str, Any]:
    results = [
        classify_source_support(claim, source, enrich_metadata=enrich_metadata).to_dict()
        for source in sources
        if isinstance(source, dict)
    ]
    order = {
        "supports": 0,
        "partially supports": 1,
        "contradicts": 2,
        "background only": 3,
        "does not support": 4,
        "insufficient text": 5,
    }
    results.sort(key=lambda row: (order.get(row["support_label"], 9), -row.get("ranking_score", 0), -row["confidence"], -row["relevance"]))
    top = results[:limit]
    direct_support = sum(1 for row in top if row["support_label"] == "supports")
    partial_support = sum(1 for row in top if row["support_label"] == "partially supports")
    return {
        "method": "knowedge_tri_artifact_bridge",
        "claim": claim[:900],
        "sources_considered": len(sources),
        "sources_returned": len(top),
        "direct_support_count": direct_support,
        "partial_support_count": partial_support,
        "provenance_rule": "No source is treated as supporting unless its visible span overlaps the selected claim.",
        "ranking_rule": "Sources are ordered by support class, then ranking score built from confidence, lexical/construct relevance, quality, and citation hygiene.",
        "export_rule": "APA, BibTeX, RIS, and CSL-JSON/Zotero-importable records are citation leads for verification, not final references unless metadata has been checked.",
        "semantic_rule": "Broad disciplinary overlap can inform role/ranking, but direct support still requires visible span overlap or narrower construct alignment.",
        "metadata_enrichment": "crossref_then_openalex_best_effort" if enrich_metadata else "local_metadata_only",
        "results": top,
    }
