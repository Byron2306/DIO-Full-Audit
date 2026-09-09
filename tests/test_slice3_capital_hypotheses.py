from market_capital.hypotheses import generate_hypotheses, update_hypothesis_state


def test_hypotheses_are_type_aware_and_non_authoritative():
    opportunity = {"opportunity_id": "opp1", "opportunity_type": "DONOR"}
    atlas_fit = {
        "recommended_pitch_family": "EDUCATION_OER_PUBLIC_GOOD",
        "primary_products": ["HOMS Learning Studio"],
        "proof_bundle": ["Prosper"],
    }
    rows = generate_hypotheses(opportunity, atlas_fit)
    assert len(rows) >= 2
    assert all(row["truth_class"] == "HYPOTHESIS" for row in rows)
    assert all(row["state"] == "TEST" for row in rows)
    assert all(row["authority_created"] is False for row in rows)
    assert any("public" in row["statement"].lower() or "impact" in row["statement"].lower() for row in rows)


def test_promote_requires_evidence_refs():
    record = {"state": "TEST", "evidence_refs": []}
    try:
        update_hypothesis_state(record, "PROMOTE", [])
    except ValueError as exc:
        assert "evidence" in str(exc).lower()
    else:
        raise AssertionError("PROMOTE must require evidence")


def test_hypothesis_state_cannot_escape_bounded_vocabulary():
    record = {"state": "TEST", "evidence_refs": []}
    try:
        update_hypothesis_state(record, "SEND_NOW", ["response:1"])
    except ValueError:
        pass
    else:
        raise AssertionError("hypothesis state must remain TEST/REFINE/HOLD/PROMOTE")
