from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


def _split(value: str | None) -> tuple[str, ...]:
    return tuple(item.strip() for item in str(value or "").split("|") if item.strip())


@dataclass(frozen=True)
class PublicResearchSeed:
    seed_id: str
    source_id: str
    organisation_name: str
    url: str
    capital_types: tuple[str, ...]
    geographies: tuple[str, ...]
    themes: tuple[str, ...]
    evidence_role: str

    def __post_init__(self) -> None:
        if not self.seed_id or not self.source_id or not self.organisation_name:
            raise ValueError("seed_id, source_id and organisation_name are required")
        if not self.url.startswith("https://"):
            raise ValueError(f"Public research seed must use https: {self.seed_id}")
        if not self.capital_types:
            raise ValueError(f"At least one capital type is required: {self.seed_id}")


def load_public_research_registry(root: Path) -> list[PublicResearchSeed]:
    path = Path(root) / "config" / "atlas" / "dio_capital_public_research_registry.csv"
    if not path.is_file():
        raise FileNotFoundError(path)
    seeds: list[PublicResearchSeed] = []
    seen: set[str] = set()
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for raw in csv.DictReader(handle):
            seed = PublicResearchSeed(
                seed_id=str(raw.get("seed_id") or "").strip(),
                source_id=str(raw.get("source_id") or "").strip(),
                organisation_name=str(raw.get("organisation_name") or "").strip(),
                url=str(raw.get("url") or "").strip(),
                capital_types=_split(raw.get("capital_types")),
                geographies=_split(raw.get("geographies")),
                themes=_split(raw.get("themes")),
                evidence_role=str(raw.get("evidence_role") or "DISCOVERY_SEED").strip(),
            )
            if seed.seed_id in seen:
                raise ValueError(f"Duplicate public research seed id: {seed.seed_id}")
            seen.add(seed.seed_id)
            seeds.append(seed)
    return seeds


def pages_for_source(
    rows: Iterable[PublicResearchSeed],
    source_id: str,
    *,
    limit: int,
    theme_terms: Iterable[str] = (),
) -> list[dict]:
    cap = max(0, int(limit))
    wanted = {str(value or "").strip().casefold() for value in theme_terms if str(value or "").strip()}
    candidates = [row for row in rows if row.source_id == source_id]
    if wanted:
        matched = [
            row for row in candidates
            if wanted.intersection({theme.casefold() for theme in row.themes})
        ]
        if matched:
            candidates = matched
    pages: list[dict] = []
    for row in candidates[:cap]:
        pages.append({
            "seed_id": row.seed_id,
            "url": row.url,
            "title": row.organisation_name,
            "policy_state": "READY",
            "seed_evidence_role": row.evidence_role,
            "facts": {
                "organisation_name": row.organisation_name,
                "opportunity_type": row.capital_types[0],
                "candidate_capital_types": list(row.capital_types),
                "candidate_geographies": list(row.geographies),
                "candidate_themes": list(row.themes),
                "route_requires_review": True,
            },
        })
    return pages


def decorate_plan_with_public_research(
    plan: dict,
    rows: Iterable[PublicResearchSeed],
    *,
    theme_terms: Iterable[str] = (),
) -> dict:
    """Attach bounded seed pages only to public-web allocations.

    This does not create observations. It only supplies navigation candidates
    to adapters that must verify the live page before emitting evidence.
    """
    decorated = dict(plan)
    allocations: list[dict] = []
    for raw in list(plan.get("source_allocations") or []):
        allocation = dict(raw)
        source_id = str(allocation.get("source_id") or "").strip()
        budget = max(0, int(allocation.get("budget") or 0))
        pages = pages_for_source(rows, source_id, limit=budget, theme_terms=theme_terms)
        if pages:
            allocation["pages"] = pages
        allocations.append(allocation)
    decorated["source_allocations"] = allocations
    decorated["authority_created"] = False
    decorated["external_effects"] = False
    return decorated
