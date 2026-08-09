#!/usr/bin/env python3
"""Verify the governed commercial sites and campaign creatives."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN_CONFIG = ROOT / "config" / "commercial_campaigns.json"
CONTACT = "dio_workflows@outlook.com"
FORBIDDEN = (
    "mailto:?",
    "hello@example.com",
    "hello@homs.education",
    "how to sell it",
    "evidence that gets approved",
)


class LocalReferenceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.references: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        for attribute in ("src", "href"):
            value = values.get(attribute)
            if not value or value.startswith(("#", "http://", "https://", "mailto:")):
                continue
            self.references.append(value.split("#", 1)[0])


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_html(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    parser = LocalReferenceParser()
    parser.feed(text)
    missing = [reference for reference in parser.references if reference and not (path.parent / reference).exists()]
    forbidden = [phrase for phrase in FORBIDDEN if phrase in text.lower()]
    return {
        "path": str(path.relative_to(ROOT)),
        "sha256": digest(path),
        "parsed": True,
        "missing_local_references": missing,
        "forbidden_phrases": forbidden,
        "contact_routed": CONTACT in text,
    }


def main() -> None:
    campaign_config = json.loads(CAMPAIGN_CONFIG.read_text(encoding="utf-8"))
    products = tuple(campaign_config["products"])
    checks: list[dict] = []
    for page in (
        ROOT / "sites" / "homs" / "index.html",
        ROOT / "sites" / "evidex" / "index.html",
        ROOT / "sites" / "vamp" / "index.html",
        ROOT / "sites" / "sophia" / "index.html",
        ROOT / "sites" / "document-studio" / "index.html",
        ROOT / "sites" / "evidex" / "golden-case" / "index.html",
    ):
        checks.append(verify_html(page))

    creative_checks: list[dict] = []
    for product in products:
        creative_dir = ROOT / "campaigns" / "phase3" / product / "campaign_v2" / "creatives"
        for image_path in sorted(creative_dir.glob("*.png")):
            with Image.open(image_path) as image:
                dimensions = list(image.size)
            creative_checks.append({
                "path": str(image_path.relative_to(ROOT)),
                "sha256": digest(image_path),
                "dimensions": dimensions,
                "dimensions_valid": dimensions == [1200, 628],
            })

    visual_reviews: list[dict] = []
    for product in products:
        review_path = ROOT / "campaigns" / "phase3" / product / "campaign_v2" / "VISUAL_REVIEW.json"
        review = json.loads(review_path.read_text(encoding="utf-8"))
        visual_reviews.append({
            "product_id": product,
            "review_path": str(review_path.relative_to(ROOT)),
            "approved_count": sum(item["status"].startswith("approved") for item in review["assets"]),
            "rejected_count": sum(item["status"] == "rejected" for item in review["assets"]),
            "all_decided": all(item["status"] != "visual_review_required" for item in review["assets"]),
        })

    links = (ROOT / "sites" / "evidex" / "assets" / "commercial-links.js").read_text(encoding="utf-8")
    google_form_present = bool(re.search(r"https://docs\.google\.com/forms/", links))
    passed = (
        all(not item["missing_local_references"] and not item["forbidden_phrases"] for item in checks)
        and all(item["contact_routed"] for item in checks[:5])
        and all(item["dimensions_valid"] for item in creative_checks)
        and len(creative_checks) == len(json.loads((ROOT / "config" / "campaign_creatives.json").read_text(encoding="utf-8"))["creatives"])
        and all(item["all_decided"] for item in visual_reviews)
        and google_form_present
    )
    receipt = {
        "schema": "knowedge.commercial_release_receipt.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
        "contact_email": CONTACT,
        "google_form_present": google_form_present,
        "html_checks": checks,
        "creative_checks": creative_checks,
        "visual_reviews": visual_reviews,
        "boundaries": [
            "Gamma imagery is published only as illustrative campaign art.",
            "Controlled proof artifacts are not described as live client outcomes.",
            "HOMS retains educator or subject-expert approval.",
            "Evidex does not guarantee donor, auditor, regulator, funder or compliance outcomes.",
            "VAMP prepares evidence but never automates performance ratings or employment decisions.",
            "Sophia remains diagnostic academic review and does not replace authorship.",
            "Document Studio translation remains non-certified and requires target-language, technical and client approval.",
            "NicheFoundry is shared media infrastructure and every publication remains human-gated."
        ],
    }
    output = ROOT / "campaigns" / "phase3" / "COMMERCIAL_CAMPAIGN_RELEASE_RECEIPT.json"
    output.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(f"Commercial release verification: {'PASS' if passed else 'FAIL'}")
    print(f"Receipt: {output}")
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
