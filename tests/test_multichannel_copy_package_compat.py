from __future__ import annotations

from scripts.build_multichannel_campaign_factory import copy_package


PRODUCT = {
    "id": "site_studio",
    "name": "DIO Site Studio",
    "short_name": "Site Studio",
    "offer": "controlled_site_pilot",
    "promise": "A reviewable website package with human-held publication authority.",
    "proof": "Controlled Studio composition produces a reviewable website package.",
    "cta": "Prepare a website brief",
}

AUDIENCE = {
    "id": "controlled-buyer",
    "name": "South African research consultancy",
    "pain": "The consultancy needs a credible public presence without fragmented production.",
    "outcome": "A clear, evidence-aware website ready for human review.",
}


def test_copy_package_legacy_three_argument_contract_uses_lingua_projection() -> None:
    package = copy_package(PRODUCT, AUDIENCE, "LINKEDIN_ORGANIC")
    assert package["headline"]
    assert package["body"]
    assert package["cta"] == PRODUCT["cta"]
    assert package["angle"] == "credible_peer"


def test_copy_package_explicit_projection_contract_remains_supported() -> None:
    package = copy_package(
        PRODUCT,
        AUDIENCE,
        "LINKEDIN_ORGANIC",
        {"tone": "explicit_test_tone", "cta_style": "professional_next_step", "density": "medium"},
    )
    assert package["headline"]
    assert package["body"]
    assert package["cta"] == PRODUCT["cta"]
    assert package["angle"] == "explicit_test_tone"
