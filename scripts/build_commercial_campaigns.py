#!/usr/bin/env python3
"""Validate commercial copy and render human-readable campaign packs."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "commercial_campaigns.json"
LIMITS = {
    "meta.primary_text": 125,
    "meta.headline": 40,
    "meta.description": 30,
    "linkedin.intro": 150,
    "linkedin.headline": 70,
    "linkedin.description": 100,
    "google_rsa.headlines": 30,
    "google_rsa.descriptions": 90,
}


def check(label: str, value: str, limit: int, errors: list[str]) -> None:
    if len(value) > limit:
        errors.append(f"{label}: {len(value)} characters (limit {limit})")


def validate(product_id: str, product: dict) -> list[str]:
    errors: list[str] = []
    channels = product["channels"]
    for index, advert in enumerate(channels["meta"], 1):
        for field in ("primary_text", "headline", "description"):
            check(
                f"{product_id}.meta[{index}].{field}",
                advert[field],
                LIMITS[f"meta.{field}"],
                errors,
            )
    for index, advert in enumerate(channels["linkedin"], 1):
        for field in ("intro", "headline", "description"):
            check(
                f"{product_id}.linkedin[{index}].{field}",
                advert[field],
                LIMITS[f"linkedin.{field}"],
                errors,
            )
    for field in ("headlines", "descriptions"):
        for index, value in enumerate(channels["google_rsa"][field], 1):
            check(
                f"{product_id}.google_rsa.{field}[{index}]",
                value,
                LIMITS[f"google_rsa.{field}"],
                errors,
            )
    return errors


def render(product_id: str, product: dict, contact_email: str) -> str:
    lines = [
        f"# {product['name']} Commercial Campaign",
        "",
        f"**Campaign line:** {product['campaign_line']}",
        f"**Response address:** {contact_email}",
        "",
        "## Buyers",
        "",
        *[f"- {item}" for item in product["audiences"]],
        "",
        "## Offers",
        "",
    ]
    for offer in product["offers"]:
        lines.extend([
            f"### {offer['name']}",
            "",
            offer["promise"],
            "",
            f"Pilot price: **{offer['price']}**",
            "",
        ])
    lines.extend(["## Proof We Can Show", "", *[f"- {item}" for item in product["proof"]], ""])
    lines.extend(["## Meta", ""])
    for advert in product["channels"]["meta"]:
        lines.extend([
            f"### {advert['angle'].replace('_', ' ').title()}",
            "",
            f"**Primary:** {advert['primary_text']}",
            f"**Headline:** {advert['headline']}",
            f"**Description:** {advert['description']}",
            f"**CTA:** {advert['cta']}",
            "",
        ])
    lines.extend(["## LinkedIn", ""])
    for advert in product["channels"]["linkedin"]:
        lines.extend([
            f"### {advert['angle'].replace('_', ' ').title()}",
            "",
            f"**Intro:** {advert['intro']}",
            f"**Headline:** {advert['headline']}",
            f"**Description:** {advert['description']}",
            f"**CTA:** {advert['cta']}",
            "",
        ])
    rsa = product["channels"]["google_rsa"]
    lines.extend(["## Google Search", "", "### Headlines", "", *[f"- {item}" for item in rsa["headlines"]], ""])
    lines.extend(["### Descriptions", "", *[f"- {item}" for item in rsa["descriptions"]], ""])
    lines.extend(["## Claim Boundaries", "", *[f"- {item}" for item in product["claim_boundaries"]], ""])
    lines.extend([
        "## Visual Production",
        "",
        "Gamma creates the campaign source images. Every output must be visually reviewed before publication.",
        "Generated imagery must not be presented as a photograph of a real client or completed client job.",
        "",
    ])
    for asset in product["gamma_assets"]:
        lines.extend([f"- **{asset['title']}**: {asset['purpose']}"])
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    payload = json.loads(CONFIG.read_text(encoding="utf-8"))
    errors: list[str] = []
    for product_id, product in payload["products"].items():
        errors.extend(validate(product_id, product))
    if errors:
        raise SystemExit("Campaign validation failed:\n- " + "\n- ".join(errors))

    for product_id, product in payload["products"].items():
        output_dir = ROOT / "campaigns" / "phase3" / product_id / "campaign_v2"
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "CAMPAIGN_PACK.md").write_text(
            render(product_id, product, payload["contact_email"]), encoding="utf-8"
        )
        (output_dir / "platform_ads.json").write_text(
            json.dumps(product["channels"], indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
        )
        (output_dir / "gamma_visual_request.json").write_text(
            json.dumps({
                "schema": "knowedge.gamma_campaign_request.v1",
                "product_id": product_id,
                "product_name": product["name"],
                "assets": product["gamma_assets"],
            }, indent=2, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
    print(f"Validated and built {len(payload['products'])} campaign packs.")


if __name__ == "__main__":
    main()
