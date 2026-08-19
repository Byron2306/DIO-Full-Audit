from __future__ import annotations

import csv
import hashlib
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .core import SeedCandidate, stable_id

TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokens(value: str) -> set[str]:
    return {
        token
        for token in TOKEN_RE.findall(str(value or "").lower())
        if len(token) > 2 and token not in {"and", "the", "for", "with", "services", "operations", "management"}
    }


def split_pipe(value: str) -> set[str]:
    return {item.strip() for item in str(value or "").split("|") if item.strip()}


def load_domains(path: Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return [
        row
        for row in rows
        if row.get("domain_type") == "DOMAIN"
        and row.get("atlas_status") != "UNKNOWN_DOMAIN_TEST_ONLY"
    ]


def load_seed_organisations(path: Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def candidate_score(domain: dict[str, str], candidate: dict[str, str]) -> tuple[float, str]:
    domain_id = domain["domain_id"]
    family = domain["domain_family"]
    name_tokens = tokens(domain["domain_name"])
    explicit = split_pipe(candidate.get("domain_ids", ""))
    families = split_pipe(candidate.get("domain_families", ""))
    tags = tokens(candidate.get("tags", ""))
    exclusions = split_pipe(candidate.get("exclude_domain_ids", ""))
    if domain_id in exclusions:
        return -1000.0, "EXCLUDED"
    priority = float(candidate.get("priority") or 50)
    if domain_id in explicit:
        return 1000.0 + priority, "EXPLICIT_DOMAIN"
    overlap = len(name_tokens & tags)
    if overlap:
        return 300.0 + overlap * 35.0 + priority, "TAG_MATCH"
    if family in families:
        return 100.0 + priority, "FAMILY_FALLBACK"
    return -1.0, "NO_MATCH"


def compile_baselines(
    domain_registry: Path,
    organisation_registry: Path,
    *,
    per_domain: int = 5,
) -> tuple[list[SeedCandidate], dict[str, Any]]:
    domains = load_domains(domain_registry)
    organisations = load_seed_organisations(organisation_registry)
    rows: list[SeedCandidate] = []
    coverage: dict[str, int] = {}
    basis_counts = {"EXPLICIT_DOMAIN": 0, "TAG_MATCH": 0, "FAMILY_FALLBACK": 0}
    weak_domains: list[str] = []

    for domain in domains:
        ranked: list[tuple[float, str, dict[str, str]]] = []
        for organisation in organisations:
            score, basis = candidate_score(domain, organisation)
            if score >= 0:
                ranked.append((score, basis, organisation))
        ranked.sort(
            key=lambda item: (
                -item[0],
                item[2].get("organisation", "").lower(),
                item[2].get("website", ""),
            )
        )
        selected: list[tuple[float, str, dict[str, str]]] = []
        seen: set[str] = set()
        for entry in ranked:
            key = entry[2].get("organisation", "").strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            selected.append(entry)
            if len(selected) == per_domain:
                break
        if len(selected) < per_domain:
            raise ValueError(
                f"{domain['domain_id']} {domain['domain_name']}: only {len(selected)} baseline candidates available; need {per_domain}"
            )
        coverage[domain["domain_id"]] = len(selected)
        if all(basis == "FAMILY_FALLBACK" for _, basis, _ in selected):
            weak_domains.append(domain["domain_id"])
        for rank, (_, basis, org) in enumerate(selected, start=1):
            basis_counts[basis] = basis_counts.get(basis, 0) + 1
            rationale = (org.get("rationale") or "").strip()
            if basis == "FAMILY_FALLBACK":
                rationale = (
                    f"Family-level bootstrap for {domain['domain_name']}. "
                    f"{rationale} This is a baseline prior, not a claim that the organisation is a top buyer."
                ).strip()
            elif basis == "TAG_MATCH":
                rationale = (
                    f"Domain-tag bootstrap for {domain['domain_name']}. {rationale}"
                ).strip()
            else:
                rationale = (
                    f"Explicit domain bootstrap for {domain['domain_name']}. {rationale}"
                ).strip()
            rows.append(
                SeedCandidate(
                    seed_id=stable_id("SEED", domain["domain_id"], rank, org["organisation"]),
                    domain_id=domain["domain_id"],
                    domain_name=domain["domain_name"],
                    rank=rank,
                    organisation=org["organisation"],
                    organisation_kind=org.get("organisation_kind") or "organisation",
                    geography=org.get("geography") or "South Africa",
                    website=org.get("website") or "",
                    engagement_mode=org.get("engagement_mode") or "RESEARCH_FIRST",
                    rationale=f"{rationale} fit_basis={basis}",
                    provenance_kind=org.get("provenance_kind") or "CURATED_BASELINE_PRIOR",
                    evidence_state=org.get("evidence_state") or "SEED_PRIOR_REQUIRES_REFRESH",
                    authority_created=False,
                )
            )

    summary = {
        "schema": "dio.market_sensorium.baseline_compiler_receipt.v1",
        "domain_count": len(domains),
        "per_domain": per_domain,
        "candidate_count": len(rows),
        "coverage_ratio": 1.0 if domains and len(coverage) == len(domains) else 0.0,
        "basis_counts": basis_counts,
        "family_fallback_only_domain_count": len(weak_domains),
        "family_fallback_only_domains": weak_domains,
        "authority_created": False,
        "market_demand_claimed": False,
        "best_target_claimed": False,
        "baseline_priors_only": True,
    }
    summary["digest"] = "sha256:" + hashlib.sha256(
        repr([(row.domain_id, row.rank, row.organisation) for row in rows]).encode("utf-8")
    ).hexdigest()
    return rows, summary


def write_baselines(path: Path, rows: list[SeedCandidate]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "seed_id",
        "domain_id",
        "domain_name",
        "rank",
        "organisation",
        "organisation_kind",
        "geography",
        "website",
        "engagement_mode",
        "rationale",
        "provenance_kind",
        "evidence_state",
        "authority_created",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for item in rows:
            payload = asdict(item)
            payload["authority_created"] = str(payload["authority_created"]).lower()
            writer.writerow(payload)
