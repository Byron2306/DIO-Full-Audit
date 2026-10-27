#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from market_capital.adapters.cordis import CordisAdapter
from market_capital.adapters.crossref_funders import CrossrefFundersAdapter
from market_capital.adapters.giving360 import Giving360Adapter
from market_capital.adapters.grants_gov import GrantsGovAdapter
from market_capital.adapters.propublica_nonprofits import ProPublicaNonprofitsAdapter
from market_capital.adapters.usaspending import USASpendingAdapter
from market_capital.adapters.verified_public_web import VerifiedPublicResearchAdapter
from market_capital.atlas_search import build_search_signature
from market_capital.census import CapitalCensus
from market_capital.discovery_planner import build_discovery_plan
from market_capital.discovery_runner import run_discovery_cycle
from market_capital.public_research import decorate_plan_with_public_research, load_public_research_registry
from market_capital.sources import load_capital_sources


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _machine_adapters() -> dict[str, Any]:
    return {
        "SRC-GRANTS-GOV": GrantsGovAdapter(),
        "SRC-CORDIS": CordisAdapter(),
        "SRC-360GIVING": Giving360Adapter(),
        "SRC-CROSSREF-FUNDERS": CrossrefFundersAdapter(),
        "SRC-USASPENDING": USASpendingAdapter(),
        "SRC-PROPUBLICA-NONPROFITS": ProPublicaNonprofitsAdapter(),
        "SRC-FIRST-PARTY-PROGRAMME": VerifiedPublicResearchAdapter(),
        "SRC-INVESTOR-PUBLIC-WEB": VerifiedPublicResearchAdapter(),
        "SRC-PHILANTHROPY-PUBLIC-WEB": VerifiedPublicResearchAdapter(),
        "SRC-PATRONAGE-PUBLIC-WEB": VerifiedPublicResearchAdapter(),
    }


def _canonical_product_ids(root: Path) -> list[str]:
    import re

    path = Path(root) / "config" / "atlas" / "dio_meta_incarnation_crosswalk.csv"
    products: list[str] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            name = str(row.get("incarnation") or "").strip()
            if not name:
                continue
            slug = re.sub(r"[^a-z0-9]+", "_", name.casefold()).strip("_")
            if slug and slug not in products:
                products.append(slug)
    # Canon extensions are added by Atlas when their verified aggregate receipt exists.
    # Probe those ids from the receipt without mutating the historical 53-row anchor.
    for receipt_path in (
        Path(root) / "state" / "product_grade" / "canon_extension_aggregate" / "CANON_EXTENSION_PRODUCT_GRADE_RECEIPT.json",
        Path(root) / "state" / "product_grade" / "canon_extensions" / "CANON_EXTENSION_PRODUCT_GRADE_RECEIPT.json",
    ):
        if not receipt_path.is_file():
            continue
        try:
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            break
        extensions = receipt.get("extensions") if isinstance(receipt, dict) else None
        if isinstance(extensions, dict):
            for key, value in extensions.items():
                raw = str((value or {}).get("slug") if isinstance(value, dict) else key or key).strip()
                slug = re.sub(r"[^a-z0-9]+", "_", raw.casefold()).strip("_")
                if slug and slug not in products:
                    products.append(slug)
        break
    return products


def _source_classes(root: Path, discovery_receipts: list[dict[str, Any]]) -> set[str]:
    participating: set[str] = set()
    for receipt in discovery_receipts:
        for source_id, result in dict(receipt.get("source_results") or {}).items():
            if int((result or {}).get("persisted") or 0) > 0:
                participating.add(str(source_id))
    try:
        registry = load_capital_sources(root)
    except (FileNotFoundError, ValueError):
        # Fail closed: source IDs are not source classes.
        return set()
    return {
        registry[source_id].source_class
        for source_id in participating
        if source_id in registry
    }


def build_acceptance_receipt(
    *,
    root: Path,
    census: CapitalCensus,
    discovery_receipts: list[dict[str, Any]],
) -> dict[str, Any]:
    root = Path(root)
    synthetic_records = sum(int(receipt.get("synthetic_fallback_records") or 0) for receipt in discovery_receipts)
    contacts = sum(int(receipt.get("external_contacts_sent") or 0) for receipt in discovery_receipts)
    submissions = sum(int(receipt.get("submission_actions_executed") or 0) for receipt in discovery_receipts)
    financial = sum(int(receipt.get("financial_actions_executed") or 0) for receipt in discovery_receipts)
    classes = _source_classes(root, discovery_receipts)
    counts = census.snapshot_counts()
    if synthetic_records > 0:
        acceptance_state = "SYNTHETIC_RECORDS_PRESENT"
    elif contacts > 0 or submissions > 0 or financial > 0:
        acceptance_state = "EXTERNAL_EFFECTS_DETECTED"
    elif int(counts.get("organisations") or 0) <= 0 or int(counts.get("opportunities") or 0) <= 0:
        acceptance_state = "INSUFFICIENT_CENSUS_DATA"
    elif len(classes) < 3:
        acceptance_state = "INSUFFICIENT_SOURCE_DIVERSITY"
    else:
        acceptance_state = "ACCEPTED"
    receipt = {
        "schema": "dio.market_capital.census_acceptance_receipt.v1",
        "census_version": "1",
        "generated_at": _now(),
        "database": str(census.path),
        "counts": counts,
        "source_classes": sorted(classes),
        "acceptance_state": acceptance_state,
        "acceptance_requirements": {
            "minimum_source_classes": 3,
            "requires_organisations": True,
            "requires_opportunities": True,
            "synthetic_records_allowed": 0,
            "external_contacts_allowed": 0,
            "submission_actions_allowed": 0,
            "financial_actions_allowed": 0,
        },
        "source_class_count": len(classes),
        "discovery_cycle_count": len(discovery_receipts),
        "synthetic_records": synthetic_records,
        "external_contacts_sent": contacts,
        "submission_actions_executed": submissions,
        "financial_actions_executed": financial,
        "authority_created": False,
        "external_effects": False,
    }
    output = root / "state" / "market_capital" / "census" / "CENSUS_RECEIPT.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt


def build_census(*, root: Path, cycle_budget: int, mode: str, global_scope: bool) -> dict[str, Any]:
    root = Path(root).resolve()
    census_root = root / "state" / "market_capital" / "census"
    census = CapitalCensus(census_root / "capital_support.sqlite")
    census.initialize()

    all_products = _canonical_product_ids(root)
    if not all_products:
        raise RuntimeError("No canonical DIO products are available for Atlas capital discovery")
    if global_scope or mode in {"weekly", "monthly"}:
        products = all_products
    else:
        products = all_products[: min(12, len(all_products))]

    signatures: list[dict[str, Any]] = []
    skipped_products: list[dict[str, str]] = []
    for product in products:
        try:
            signatures.append(build_search_signature(root, [product]))
        except (KeyError, ValueError) as exc:
            skipped_products.append({"product_id": product, "reason": str(exc)})

    sources = load_capital_sources(root)
    plan = build_discovery_plan(signatures, sources, max(1, int(cycle_budget)))
    research_rows = load_public_research_registry(root)
    theme_terms = sorted({
        str(term).strip().casefold()
        for signature in signatures
        for term in (
            list(signature.get("impact_themes") or [])
            + list(signature.get("domain_names") or [])
            + list(signature.get("capital_archetypes") or [])
        )
        if str(term or "").strip()
    })
    plan = decorate_plan_with_public_research(plan, research_rows, theme_terms=theme_terms)
    cycle = run_discovery_cycle(
        root=root,
        census=census,
        plan=plan,
        adapters=_machine_adapters(),
    )
    cycle["mode"] = mode
    cycle["global_scope"] = bool(global_scope)
    cycle["atlas_signature_count"] = len(signatures)
    cycle["skipped_products"] = skipped_products
    receipt = build_acceptance_receipt(root=root, census=census, discovery_receipts=[cycle])
    return {"cycle": cycle, "acceptance": receipt}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the governed Atlas-steered Capital & Support census")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--global", dest="global_scope", action="store_true", help="Compile search signatures across the full canonical portfolio")
    parser.add_argument("--cycle-budget", type=int, default=500)
    parser.add_argument("--mode", choices=("daily", "weekly", "monthly"), default="daily")
    args = parser.parse_args()
    result = build_census(root=args.root, cycle_budget=args.cycle_budget, mode=args.mode, global_scope=args.global_scope)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
