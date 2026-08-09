"""
Academic Retrieval Engine — Constitutional Self-Teaching
========================================================
When the Diagnostic Classifier detects a KNOWLEDGE_GAP, DOMAIN_TRANSFER,
or EPISTEMIC_OVERREACH, this engine searches trusted academic sources
and injects retrieved knowledge into Sophia's context.

This is NOT pattern matching from training data.
This is Sophia TEACHING HERSELF from real, citable, verifiable sources.

Constitutional Basis:
    Article II:   De Veritate — Evidence, not simulation
    Article VIII: De Memoria et Origine — Provenance is law
    Article XII:  De Finibus Honestis — Know your limits, then learn
    Article XXV:  De Probatione Cognitionis — Testing of thought

Source Governance:
    Only constitutionally approved academic sources are queried.
    Every retrieved fragment carries provenance metadata.
    The BPF LSM substrate guarantees this code hasn't been tampered with.

Zero external dependencies. Python stdlib only (urllib).
"""

from __future__ import annotations

import json
import logging
import hashlib
import time
import re
import html
import urllib.request
import urllib.error
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pathlib import Path

logger = logging.getLogger("arda.academic_retrieval")

# ── Constitutional Source Allowlist ──
# Article VIII: Only sources with verifiable provenance are permitted.
# This is the equivalent of the BPF LSM harmony map — but for knowledge.

APPROVED_SOURCES = {
    "arxiv": {
        "name": "arXiv",
        "base_url": "https://export.arxiv.org/api/query",
        "type": "academic_preprints",
        "trust_level": "high",
        "constitutional_basis": "Article II: Peer-reviewed preprints",
    },
    "google_scholar": {
        "name": "Google Scholar",
        "base_url": "https://scholar.google.com/scholar",
        "type": "academic_papers",
        "trust_level": "high",
        "constitutional_basis": "Article VIII: Citation-visible scholarly provenance",
    },
    "wikipedia": {
        "name": "Wikipedia",
        "base_url": "https://en.wikipedia.org/api/rest_v1/page/summary",
        "type": "encyclopedic",
        "trust_level": "medium",
        "constitutional_basis": "Article XII: Accessible general knowledge",
    },
    "stanford_sep": {
        "name": "Stanford Encyclopedia of Philosophy",
        "base_url": "https://plato.stanford.edu",
        "type": "philosophy",
        "trust_level": "high",
        "constitutional_basis": "Article II: Peer-reviewed philosophical analysis",
    },
    "eric": {
        "name": "ERIC",
        "base_url": "https://api.eric.ed.gov/ERIC",
        "type": "education_research",
        "trust_level": "high",
        "constitutional_basis": "Article II: US Dept of Education peer-reviewed database",
    },
    "openalex": {
        "name": "OpenAlex",
        "base_url": "https://api.openalex.org/works",
        "type": "academic_papers",
        "trust_level": "high",
        "constitutional_basis": "Article VIII: Open scholarly infrastructure with full provenance",
    },
}

# Domains we will NEVER query
DENIED_DOMAINS = [
    "reddit.com", "twitter.com", "x.com", "facebook.com",
    "tiktok.com", "instagram.com", "4chan.org",
    "stackoverflow.com",  # Can add later with governance
]


@dataclass
class RetrievedFragment:
    """A single piece of retrieved knowledge with full provenance."""
    source: str                    # Which approved source
    title: str                     # Paper/article title
    authors: List[str]             # Authors (for citation)
    summary: str                   # Abstract or summary text
    url: str                       # Canonical URL for verification
    retrieved_at: str              # ISO timestamp
    query_used: str                # What we searched for
    content_hash: str              # SHA-256 of retrieved content (for audit)
    relevance_score: float = 0.0   # 0.0-1.0 estimated relevance
    year: str = ""                 # Publication year (if available)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "title": self.title,
            "authors": self.authors,
            "summary": self.summary[:500],  # Truncate for context window
            "url": self.url,
            "year": self.year,
            "retrieved_at": self.retrieved_at,
            "query_used": self.query_used,
            "content_hash": self.content_hash,
            "relevance_score": round(self.relevance_score, 4),
        }

    def to_citation(self) -> str:
        """Generate a proper citation string."""
        author_str = ", ".join(self.authors[:3])
        if len(self.authors) > 3:
            author_str += " et al."
        return f"{author_str}. \"{self.title}\". Source: {self.source}. URL: {self.url}"


@dataclass
class RetrievalResult:
    """Complete result of an academic retrieval attempt."""
    query: str
    domains_searched: List[str]
    fragments: List[RetrievedFragment] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    total_time_ms: int = 0
    constitutional_check: str = "PASSED"  # PASSED / DENIED / PARTIAL
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "domains_searched": self.domains_searched,
            "fragments_found": len(self.fragments),
            "fragments": [f.to_dict() for f in self.fragments],
            "errors": self.errors,
            "total_time_ms": self.total_time_ms,
            "constitutional_check": self.constitutional_check,
            "timestamp": self.timestamp,
        }

    def to_context_injection(self) -> str:
        """
        Format retrieved knowledge for injection into Ollama's system prompt.

        This is the critical bridge: external knowledge becomes
        constitutionally sourced context for Sophia's reasoning.
        """
        if not self.fragments:
            return ""

        lines = [
            "\n[ACADEMIC KNOWLEDGE — Retrieved from approved constitutional sources]",
            f"Query: \"{self.query}\"",
            f"Sources searched: {', '.join(self.domains_searched)}",
            f"Fragments retrieved: {len(self.fragments)}",
            "",
        ]

        for i, frag in enumerate(self.fragments[:5], 1):  # Max 5 fragments
            lines.append(f"--- Source {i}: {frag.source} ---")
            lines.append(f"Title: {frag.title}")
            if frag.authors:
                lines.append(f"Authors: {', '.join(frag.authors[:3])}")
            lines.append(f"Summary: {frag.summary[:400]}")
            lines.append(f"Cite: {frag.url}")
            lines.append("")

        lines.append("[END ACADEMIC KNOWLEDGE]")
        lines.append("")
        lines.append(
            "IMPORTANT: You MUST cite these sources when using this knowledge. "
            "Distinguish between what you know from training and what you learned "
            "from these retrieved sources. If the retrieved knowledge contradicts "
            "your training, state the contradiction honestly."
        )

        return "\n".join(lines)


class AcademicRetrievalEngine:
    """
    Governed academic retrieval for constitutional self-teaching.

    When the diagnostic classifier detects that Sophia lacks knowledge,
    this engine searches trusted academic sources and injects the
    retrieved knowledge into her context window.

    The key insight: instead of pattern-matching from training data,
    Sophia can TEACH HERSELF from real, citable, verifiable sources.

    All retrieval is:
    - Source-governed (only approved academic sources)
    - Provenance-tracked (every fragment has a content hash and URL)
    - Auditable (logged to the forensic evidence chain)
    - Rate-limited (no abuse of external APIs)
    """

    def __init__(self, evidence_dir: Optional[Path] = None):
        self.evidence_dir = evidence_dir
        self._request_count = 0
        self._last_request_time = 0.0
        self._rate_limit_interval = 2.0  # Seconds between requests
        self._timeout = 10  # Seconds per HTTP request
        self._cache: Dict[str, RetrievalResult] = {}  # Simple in-memory cache

    def retrieve(self, query: str, domains: Optional[List[str]] = None) -> RetrievalResult:
        """
        Search approved academic sources for knowledge relevant to the query.

        Args:
            query: The topic to search for (from diagnostic classifier)
            domains: Optional list of specific topics (e.g., ["Hoare logic", "BPF verification"])

        Returns:
            RetrievalResult with fragments and provenance metadata
        """
        start_time = time.perf_counter()

        # Build search query from domains
        search_query = " ".join(domains) if domains else query

        # Check cache
        cache_key = hashlib.sha256(search_query.encode()).hexdigest()[:16]
        if cache_key in self._cache:
            logger.info(f"RETRIEVAL: Cache hit for '{search_query}'")
            return self._cache[cache_key]

        result = RetrievalResult(
            query=search_query,
            domains_searched=[],
        )

        # ── Search each approved source ──
        # Try arXiv first (most likely to have formal CS/math)
        arxiv_fragments = self._search_arxiv(search_query)
        if arxiv_fragments:
            result.fragments.extend(arxiv_fragments)
            result.domains_searched.append("arXiv")

        # Try Google Scholar
        scholar_fragments = self._search_google_scholar(search_query)
        if scholar_fragments:
            result.fragments.extend(scholar_fragments)
            result.domains_searched.append("Google Scholar")

        # Try Wikipedia for general context
        wiki_fragments = self._search_wikipedia(search_query)
        if wiki_fragments:
            result.fragments.extend(wiki_fragments)
            result.domains_searched.append("Wikipedia")

        # Try OpenAlex (broad open scholarly index — 250M+ works, full provenance)
        openalex_fragments = self._search_openalex(search_query)
        if openalex_fragments:
            result.fragments.extend(openalex_fragments)
            result.domains_searched.append("OpenAlex")

        # Sort by relevance
        result.fragments.sort(key=lambda f: f.relevance_score, reverse=True)

        # Limit to top 5
        result.fragments = result.fragments[:5]

        result.total_time_ms = int((time.perf_counter() - start_time) * 1000)

        # Cache result
        self._cache[cache_key] = result

        # Log to forensic evidence
        self._log_retrieval(result)

        logger.info(
            f"RETRIEVAL: Found {len(result.fragments)} fragments for '{search_query}' "
            f"in {result.total_time_ms}ms from {result.domains_searched}"
        )

        return result

    def _rate_limit(self):
        """Enforce rate limiting between requests."""
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self._rate_limit_interval:
            time.sleep(self._rate_limit_interval - elapsed)
        self._last_request_time = time.time()

    def _safe_http_get(self, url: str) -> Optional[bytes]:
        """Safe HTTP GET with timeout and error handling."""
        self._rate_limit()
        self._request_count += 1

        # Constitutional domain check
        parsed = urllib.parse.urlparse(url)
        for denied in DENIED_DOMAINS:
            if denied in parsed.netloc:
                logger.warning(f"RETRIEVAL: DENIED domain {parsed.netloc} (constitutional block)")
                return None

        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "ArdaOS-AcademicRetrieval/1.0 (Constitutional Self-Teaching; contact: sovereign@arda.os)",
                    "Accept": "application/json, application/xml, text/html",
                }
            )
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            logger.warning(f"RETRIEVAL: HTTP {e.code} from {parsed.netloc}")
            return None
        except urllib.error.URLError as e:
            logger.warning(f"RETRIEVAL: URL error from {parsed.netloc}: {e.reason}")
            return None
        except Exception as e:
            logger.warning(f"RETRIEVAL: Error fetching {url}: {e}")
            return None

    def _search_arxiv(self, query: str) -> List[RetrievedFragment]:
        """Search arXiv API for academic papers."""
        fragments = []
        encoded_query = urllib.parse.quote(query)
        url = f"https://export.arxiv.org/api/query?search_query=all:{encoded_query}&start=0&max_results=3"

        data = self._safe_http_get(url)
        if not data:
            return fragments

        # Parse Atom XML response (simple parsing, no lxml needed)
        text = data.decode("utf-8", errors="replace")

        # Extract entries using regex (stdlib XML parsing is heavy)
        entries = re.findall(r"<entry>(.*?)</entry>", text, re.DOTALL)

        for entry in entries[:3]:
            title_match = re.search(r"<title>(.*?)</title>", entry, re.DOTALL)
            summary_match = re.search(r"<summary>(.*?)</summary>", entry, re.DOTALL)
            id_match = re.search(r"<id>(.*?)</id>", entry)
            author_matches = re.findall(r"<name>(.*?)</name>", entry)

            if title_match and summary_match:
                title = re.sub(r"\s+", " ", title_match.group(1)).strip()
                summary = re.sub(r"\s+", " ", summary_match.group(1)).strip()
                url = id_match.group(1).strip() if id_match else ""
                content = f"{title} {summary}"

                fragments.append(RetrievedFragment(
                    source="arXiv",
                    title=title,
                    authors=author_matches[:5],
                    summary=summary,
                    url=url,
                    retrieved_at=datetime.now(timezone.utc).isoformat(),
                    query_used=query,
                    content_hash=hashlib.sha256(content.encode()).hexdigest(),
                    relevance_score=self._estimate_relevance(query, title, summary),
                ))

        return fragments

    def _search_google_scholar(self, query: str) -> List[RetrievedFragment]:
        """Search Google Scholar result pages for scholarly papers."""
        fragments = []
        encoded_query = urllib.parse.quote(query)
        url = f"https://scholar.google.com/scholar?q={encoded_query}&hl=en"

        data = self._safe_http_get(url)
        if not data:
            return fragments

        try:
            page = data.decode("utf-8", errors="replace")

            # Scholar pages are HTML, not a stable API. Parse only the small subset we need.
            blocks = re.findall(
                r'<div class="gs_r gs_or gs_scl"[^>]*>(.*?)</div>\s*</div>',
                page,
                re.DOTALL,
            )

            if not blocks:
                blocks = re.findall(r'<div class="gs_ri">(.*?)</div>\s*</div>', page, re.DOTALL)

            for block in blocks[:3]:
                title_match = re.search(
                    r'<h3 class="gs_rt".*?(?:<a[^>]*href="([^"]+)"[^>]*>)?(.*?)</h3>',
                    block,
                    re.DOTALL,
                )
                snippet_match = re.search(r'<div class="gs_rs"[^>]*>(.*?)</div>', block, re.DOTALL)
                meta_match = re.search(r'<div class="gs_a"[^>]*>(.*?)</div>', block, re.DOTALL)

                if not title_match:
                    continue

                paper_url = html.unescape(title_match.group(1) or "")
                raw_title = title_match.group(2) or ""
                raw_snippet = snippet_match.group(1) if snippet_match else ""
                raw_meta = meta_match.group(1) if meta_match else ""

                title = self._strip_html(raw_title)
                summary = self._strip_html(raw_snippet) or "(No abstract available)"
                meta_text = self._strip_html(raw_meta)
                authors = self._extract_scholar_authors(meta_text)
                year_match = re.search(r"\b(19|20)\d{2}\b", meta_text)
                year = year_match.group(0) if year_match else ""

                if not title:
                    continue

                # Some Scholar results are citations without a direct href.
                if not paper_url:
                    paper_url = f"https://scholar.google.com/scholar?q={urllib.parse.quote(title)}"

                content = f"{title} {summary}"
                fragments.append(RetrievedFragment(
                    source="Google Scholar",
                    title=title,
                    authors=authors,
                    summary=summary[:500],
                    url=paper_url,
                    year=year,
                    retrieved_at=datetime.now(timezone.utc).isoformat(),
                    query_used=query,
                    content_hash=hashlib.sha256(content.encode()).hexdigest(),
                    relevance_score=self._estimate_relevance(query, title, summary),
                ))
        except Exception as e:
            logger.warning(f"RETRIEVAL: Google Scholar parse error: {e}")

        return fragments

    def _strip_html(self, value: str) -> str:
        """Collapse HTML fragments into readable text."""
        value = re.sub(r"<[^>]+>", " ", value or "")
        value = html.unescape(value)
        return re.sub(r"\s+", " ", value).strip()

    def _extract_scholar_authors(self, meta_text: str) -> List[str]:
        """Extract likely author names from the Scholar metadata line."""
        if not meta_text:
            return []
        author_segment = meta_text.split(" - ", 1)[0]
        author_segment = re.sub(r"\bet al\.?\b", "", author_segment, flags=re.IGNORECASE)
        candidates = [part.strip() for part in author_segment.split(",")]
        return [candidate for candidate in candidates[:5] if candidate]

    def _search_wikipedia(self, query: str) -> List[RetrievedFragment]:
        """Search Wikipedia REST API for encyclopedic context."""
        fragments = []

        # Try each multi-word topic as a Wikipedia article
        # "Hoare logic BPF verification" → try "Hoare_logic", then "BPF"
        topics_to_try = []

        # First try two-word combinations (most Wikipedia articles are multi-word)
        words = query.split()
        for i in range(len(words) - 1):
            pair = f"{words[i]}_{words[i+1]}"
            topics_to_try.append(pair)

        # Then try individual significant words
        for word in words:
            if len(word) > 3:
                topics_to_try.append(word)

        for topic in topics_to_try:
            if len(fragments) >= 2:  # Max 2 Wikipedia articles
                break

            wiki_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(topic)}"
            data = self._safe_http_get(wiki_url)
            if not data:
                continue

            try:
                result = json.loads(data)
                if result.get("type") == "standard":
                    title = result.get("title", "")
                    extract = result.get("extract", "")
                    page_url = result.get("content_urls", {}).get("desktop", {}).get("page", "")

                    if title and extract and len(extract) > 50:
                        content = f"{title} {extract}"
                        fragments.append(RetrievedFragment(
                            source="Wikipedia",
                            title=title,
                            authors=["Wikipedia contributors"],
                            summary=extract[:500],
                            url=page_url,
                            retrieved_at=datetime.now(timezone.utc).isoformat(),
                            query_used=query,
                            content_hash=hashlib.sha256(content.encode()).hexdigest(),
                            relevance_score=self._estimate_relevance(query, title, extract) * 0.8,
                        ))
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"RETRIEVAL: Wikipedia parse error: {e}")

        return fragments

    def _search_eric(self, query: str) -> List[RetrievedFragment]:
        """Search ERIC (Education Resources Information Center) — US Dept of Education."""
        fragments = []
        encoded_query = urllib.parse.quote(query)
        url = (
            f"https://api.eric.ed.gov/ERIC"
            f"?search={encoded_query}&fields=id,title,author,description,publicationdate,url"
            f"&rows=3&format=json"
        )
        data = self._safe_http_get(url)
        if not data:
            return fragments
        try:
            result = json.loads(data)
            docs = result.get("response", {}).get("docs", [])
            for doc in docs[:3]:
                title = doc.get("title", "")
                if not title:
                    continue
                authors = doc.get("author") or []
                if isinstance(authors, str):
                    authors = [authors]
                description = doc.get("description") or ""
                pub_date = doc.get("publicationdate") or ""
                year = pub_date[:4] if pub_date else ""
                doc_url = doc.get("url") or f"https://eric.ed.gov/?id={doc.get('id','')}"
                content = f"{title} {description}"
                fragments.append(RetrievedFragment(
                    source="ERIC",
                    title=title,
                    authors=authors[:3],
                    summary=description[:500] if description else "(No abstract available)",
                    url=doc_url,
                    year=year,
                    retrieved_at=datetime.now(timezone.utc).isoformat(),
                    query_used=query,
                    content_hash=hashlib.sha256(content.encode()).hexdigest(),
                    relevance_score=self._estimate_relevance(query, title, description) * 1.1,
                ))
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"RETRIEVAL: ERIC parse error: {e}")
        return fragments

    def _search_openalex(self, query: str) -> List[RetrievedFragment]:
        """Search OpenAlex — open scholarly index covering 250M+ works."""
        fragments = []
        encoded_query = urllib.parse.quote(query)
        url = (
            f"https://api.openalex.org/works"
            f"?search={encoded_query}&per-page=3&sort=relevance_score:desc"
            f"&select=title,authorships,abstract_inverted_index,publication_year,doi,primary_location"
            f"&mailto=sophia@arda-os"
        )
        data = self._safe_http_get(url)
        if not data:
            return fragments
        try:
            result = json.loads(data)
            works = result.get("results", [])
            for work in works[:3]:
                title = work.get("title") or ""
                if not title:
                    continue
                year = str(work.get("publication_year") or "")
                authors = [
                    a.get("author", {}).get("display_name", "")
                    for a in (work.get("authorships") or [])[:3]
                    if a.get("author", {}).get("display_name")
                ]
                doi = work.get("doi") or ""
                loc = work.get("primary_location") or {}
                landing = loc.get("landing_page_url") or doi or ""
                # Reconstruct abstract from inverted index
                abstract = ""
                inv = work.get("abstract_inverted_index") or {}
                if inv:
                    max_pos = max((pos for positions in inv.values() for pos in positions), default=0)
                    words_arr = [""] * (max_pos + 1)
                    for word, positions in inv.items():
                        for pos in positions:
                            if pos <= max_pos:
                                words_arr[pos] = word
                    abstract = " ".join(w for w in words_arr if w)[:500]
                content = f"{title} {abstract}"
                fragments.append(RetrievedFragment(
                    source="OpenAlex",
                    title=title,
                    authors=authors,
                    summary=abstract if abstract else "(No abstract available)",
                    url=landing,
                    year=year,
                    retrieved_at=datetime.now(timezone.utc).isoformat(),
                    query_used=query,
                    content_hash=hashlib.sha256(content.encode()).hexdigest(),
                    relevance_score=self._estimate_relevance(query, title, abstract),
                ))
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"RETRIEVAL: OpenAlex parse error: {e}")
        return fragments

    def _estimate_relevance(self, query: str, title: str, content: str) -> float:
        """
        Estimate how relevant a retrieved fragment is to the query.
        Simple keyword overlap — not ML-based, but honest.
        """
        query_words = set(re.findall(r'\b\w{3,}\b', query.lower()))
        title_words = set(re.findall(r'\b\w{3,}\b', title.lower()))
        content_words = set(re.findall(r'\b\w{3,}\b', content.lower()[:500]))

        if not query_words:
            return 0.0

        title_overlap = len(query_words & title_words) / len(query_words)
        content_overlap = len(query_words & content_words) / len(query_words)

        # Title match is worth more
        return min(1.0, title_overlap * 0.6 + content_overlap * 0.4)

    def _log_retrieval(self, result: RetrievalResult):
        """Log retrieval to the forensic evidence directory."""
        if not self.evidence_dir:
            return

        try:
            log_path = self.evidence_dir / "academic_retrieval_log.jsonl"
            entry = {
                "timestamp": result.timestamp,
                "query": result.query,
                "domains_searched": result.domains_searched,
                "fragments_found": len(result.fragments),
                "sources": [f.source for f in result.fragments],
                "titles": [f.title for f in result.fragments],
                "content_hashes": [f.content_hash for f in result.fragments],
                "total_time_ms": result.total_time_ms,
                "constitutional_check": result.constitutional_check,
            }
            with open(log_path, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.warning(f"RETRIEVAL: Failed to log: {e}")

    def get_status(self) -> Dict[str, Any]:
        """Return engine status for health checks."""
        return {
            "total_requests": self._request_count,
            "cache_size": len(self._cache),
            "approved_sources": list(APPROVED_SOURCES.keys()),
            "denied_domains": DENIED_DOMAINS,
            "rate_limit_interval_s": self._rate_limit_interval,
        }


# ── Singleton ──
_engine: Optional[AcademicRetrievalEngine] = None


def get_academic_retrieval(evidence_dir: Optional[Path] = None) -> AcademicRetrievalEngine:
    global _engine
    if _engine is None:
        _engine = AcademicRetrievalEngine(evidence_dir=evidence_dir)
    return _engine
