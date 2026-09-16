from presence_core.llm import (
    commercial_draft_claims_authorized,
)


def resolved_truth(name="ContractProof"):
    return {
        "commercial_truth": {
            "state": "RESOLVED",
            "product": {
                "product_id": name.casefold(),
                "name": name,
            },
            "pricing": None,
        }
    }


def test_resolved_product_cannot_be_denied():
    assert commercial_draft_claims_authorized(
        "There is no product called ContractProof in our current catalog.",
        resolved_truth(),
    ) is False


def test_spaced_resolved_product_name_cannot_be_denied():
    assert commercial_draft_claims_authorized(
        "There is no product called Contract Proof in our current catalogue.",
        resolved_truth(),
    ) is False


def test_resolved_product_may_be_described():
    assert commercial_draft_claims_authorized(
        "ContractProof is a governed DIO workflow for contract obligation assurance.",
        resolved_truth(),
    ) is True


def test_gated_availability_is_not_identity_denial():
    assert commercial_draft_claims_authorized(
        "ContractProof exists, but external fulfilment remains governed.",
        resolved_truth(),
    ) is True


def test_unrelated_product_denial_does_not_mutate_resolved_identity():
    assert commercial_draft_claims_authorized(
        "ContractProof exists. Another unrelated offering may not be in the current catalogue.",
        resolved_truth(),
    ) is True
