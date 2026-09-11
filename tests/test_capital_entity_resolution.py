from market_capital.entity_resolution import resolve_organisation


def test_official_domain_can_resolve_same_organisation():
    decision = resolve_organisation(
        existing={
            "organisation_id": "ORG-1",
            "canonical_domain": "example.org",
            "canonical_name": "Example Foundation",
        },
        incoming={
            "canonical_domain": "example.org",
            "canonical_name": "Example Fdn",
        },
    )
    assert decision.state == "MATCH"
    assert decision.matched_entity_id == "ORG-1"
    assert decision.basis == "OFFICIAL_DOMAIN"


def test_stable_source_identifier_has_highest_priority():
    decision = resolve_organisation(
        existing={"organisation_id": "ORG-1", "source_ids": {"crossref": "100004440"}, "canonical_name": "Old Name"},
        incoming={"source_ids": {"crossref": "100004440"}, "canonical_name": "New Name"},
    )
    assert decision.state == "MATCH"
    assert decision.basis == "SOURCE_NATIVE_IDENTIFIER"


def test_registry_identifier_can_resolve_same_organisation():
    decision = resolve_organisation(
        existing={"organisation_id": "ORG-1", "registry_ids": {"ein": "142007220"}, "canonical_name": "Example Inc"},
        incoming={"registry_ids": {"ein": "142007220"}, "canonical_name": "Example Incorporated"},
    )
    assert decision.state == "MATCH"
    assert decision.basis == "PUBLIC_REGISTRY_IDENTIFIER"


def test_fuzzy_name_alone_never_finalizes_merge():
    decision = resolve_organisation(
        existing={"organisation_id": "ORG-1", "canonical_name": "Global Innovation Fund"},
        incoming={"canonical_name": "Global Innovation Foundation"},
    )
    assert decision.state == "NEEDS_REVIEW"
    assert decision.matched_entity_id is None


def test_normalized_name_and_jurisdiction_can_match_exact_identity():
    decision = resolve_organisation(
        existing={"organisation_id": "ORG-1", "canonical_name": "Example Foundation", "jurisdiction": "ZA"},
        incoming={"canonical_name": " example foundation ", "jurisdiction": "ZA"},
    )
    assert decision.state == "MATCH"
    assert decision.basis == "NORMALIZED_NAME_JURISDICTION"
