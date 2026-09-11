from __future__ import annotations

import hashlib
import html
import re
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from .base import DiscoveryBatch, DiscoveryObservation, SourceAdapter


FetchText = Callable[[str], tuple[int, str, str]]

_TYPE_TERMS: dict[str, tuple[str, ...]] = {
    "INVESTOR": (
        "we invest", "invest in", "investment", "venture capital", "portfolio companies",
        "back founders", "backing founders", "fund founders", "seed fund", "growth equity",
    ),
    "GRANT": (
        "grant", "grants", "grant funding", "funding call", "call for proposals",
        "request for proposals", "apply for funding", "funding opportunity",
    ),
    "DONOR": (
        "donor", "donation", "philanthropy", "philanthropic", "charitable giving",
        "foundation funding", "giving programme", "giving program",
    ),
    "SPONSOR": (
        "sponsor", "sponsorship", "corporate sponsorship", "partner funding",
    ),
    "PATRONAGE": (
        "patron", "patreon", "membership support", "support our work", "become a supporter",
        "monthly support", "community funding",
    ),
    "ACCELERATOR": (
        "accelerator", "acceleration programme", "acceleration program", "startup programme",
        "startup program", "cohort", "apply to the programme", "apply to the program",
    ),
    "PRIZE": (
        "prize", "challenge award", "competition", "winner receives", "award programme",
        "award program",
    ),
}

_ROUTE_TERMS = (
    "apply", "application", "submit", "funding", "grant", "invest", "investment",
    "accelerator", "programme", "program", "challenge", "prize", "support",
)

_TAG_RE = re.compile(r"<[^>]+>", re.S)
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
_LINK_RE = re.compile(
    r"<a\b[^>]*?href\s*=\s*([\"'])(.*?)\1[^>]*>(.*?)</a>",
    re.I | re.S,
)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stable(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()[:20].upper()
    return f"{prefix}-{digest}"


def _clean_text(raw: str) -> str:
    without_tags = _TAG_RE.sub(" ", raw or "")
    return re.sub(r"\s+", " ", html.unescape(without_tags)).strip()


def _default_fetch(url: str) -> tuple[int, str, str]:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("verified public research requires an https URL")
    request = Request(
        url,
        headers={
            "User-Agent": "DIO-Capital-Census/1.0 (+public-research; read-only)",
            "Accept": "text/html,application/xhtml+xml",
        },
        method="GET",
    )
    with urlopen(request, timeout=20) as response:
        status = int(getattr(response, "status", 200))
        final_url = str(response.geturl() or url)
        body = response.read(2_000_000).decode("utf-8", errors="replace")
    return status, final_url, body


def _confirmed_types(text: str, candidates: list[str]) -> list[str]:
    haystack = text.casefold()
    confirmed: list[str] = []
    for candidate in candidates:
        kind = str(candidate or "").strip().upper()
        if kind not in _TYPE_TERMS:
            continue
        if any(term in haystack for term in _TYPE_TERMS[kind]):
            confirmed.append(kind)
    return confirmed


def _application_route(base_url: str, body: str) -> str | None:
    for _quote, href, anchor_html in _LINK_RE.findall(body or ""):
        anchor = _clean_text(anchor_html).casefold()
        href_text = html.unescape(href).strip()
        combined = f"{anchor} {href_text.casefold()}"
        if not any(term in combined for term in _ROUTE_TERMS):
            continue
        resolved = urljoin(base_url, href_text)
        parsed = urlparse(resolved)
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            return resolved
    return None


class VerifiedPublicResearchAdapter(SourceAdapter):
    """Fetch official public seed pages before emitting capital observations.

    Seed metadata is navigation only. An opportunity is emitted only when the
    fetched page text corroborates one of the seed's candidate capital types.
    Routes are extracted only from explicit links present in the fetched page.
    """

    def __init__(self, fetch_text: FetchText | None = None):
        self.fetch_text = fetch_text or _default_fetch

    def discover(self, plan_slice: dict[str, Any]) -> DiscoveryBatch:
        source_id = str(plan_slice.get("source_id") or "").strip()
        pages = list(plan_slice.get("pages") or [])
        limit = max(0, int(plan_slice.get("limit") or len(pages)))
        observed_at = str(plan_slice.get("observed_at") or _now())
        observations: list[DiscoveryObservation] = []
        failures = 0

        for page in pages[:limit]:
            url = str(page.get("url") or "").strip()
            if not url or str(page.get("policy_state") or "READY").upper() != "READY":
                continue
            try:
                status, final_url, body = self.fetch_text(url)
            except Exception:
                failures += 1
                continue
            if int(status) < 200 or int(status) >= 400 or not str(body or "").strip():
                failures += 1
                continue

            facts = dict(page.get("facts") or {})
            organisation_name = str(facts.get("organisation_name") or page.get("title") or "").strip()
            seed_id = str(page.get("seed_id") or url).strip()
            page_text = _clean_text(body)
            title_match = _TITLE_RE.search(body)
            page_title = _clean_text(title_match.group(1)) if title_match else str(page.get("title") or "").strip()

            if organisation_name:
                org_payload = {
                    "organisation_id": _stable("ORG", source_id, organisation_name.casefold()),
                    "canonical_name": organisation_name,
                    "organisation_name": organisation_name,
                    "title": page_title or organisation_name,
                    "source_url": final_url,
                    "seed_id": seed_id,
                    "truth_class": "PUBLIC_PAGE_PRESENCE_VERIFIED",
                    "funding_intent": "UNPROVED",
                    "authority_created": False,
                    "external_effects": False,
                }
                observations.append(
                    DiscoveryObservation(
                        source_id=source_id,
                        entity_type="ORGANISATION",
                        source_record_id=org_payload["organisation_id"],
                        source_reference=final_url,
                        observed_at=observed_at,
                        payload=org_payload,
                        assertion_class="PUBLIC_PAGE_PRESENCE_VERIFIED",
                    )
                )

            candidates = [
                str(value).strip().upper()
                for value in (facts.get("candidate_capital_types") or [facts.get("opportunity_type")])
                if str(value or "").strip()
            ]
            confirmed = _confirmed_types(page_text, candidates)
            if not confirmed:
                continue

            kind = confirmed[0]
            route = _application_route(final_url, body)
            opportunity_id = _stable("OPP", source_id, seed_id, kind, final_url)
            opportunity_payload = {
                "opportunity_id": opportunity_id,
                "opportunity_type": kind,
                "title": page_title or f"{organisation_name} {kind.title()} opportunity",
                "organisation_name": organisation_name,
                "source_url": final_url,
                "seed_id": seed_id,
                "candidate_geographies": list(facts.get("candidate_geographies") or []),
                "themes": list(facts.get("candidate_themes") or []),
                "public_contact_route": route,
                "route_state": "APPLICATION_ROUTE_VERIFIED" if route else "NO_PUBLIC_ROUTE",
                "route_truth_class": "OBSERVED" if route else None,
                "truth_class": "PUBLIC_CAPITAL_SIGNAL_VERIFIED",
                "funding_intent": "UNPROVED",
                "willingness_to_fund": "UNPROVED",
                "authority_created": False,
                "external_effects": False,
            }
            observations.append(
                DiscoveryObservation(
                    source_id=source_id,
                    entity_type="OPPORTUNITY",
                    source_record_id=opportunity_id,
                    source_reference=final_url,
                    observed_at=observed_at,
                    payload=opportunity_payload,
                    assertion_class="PUBLIC_CAPITAL_SIGNAL_VERIFIED",
                )
            )

        state = "READY" if observations or not failures else "SOURCE_UNAVAILABLE"
        return DiscoveryBatch(source_id, tuple(observations), None, state)
