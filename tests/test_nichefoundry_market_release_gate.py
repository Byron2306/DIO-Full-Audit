from __future__ import annotations

import json
from pathlib import Path

import pytest

from adapters.legalis.decision_ledger import issue_decision
from adapters.legalis.service import LegalisError
from adapters.nichefoundry.market_release_gate import (
    MarketReleaseError,
    authorize_market_effect,
    market_legalis_request,
)


@pytest.fixture(autouse=True)
def _keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DIO_LEGALIS_HMAC_KEYS_JSON", json.dumps({"market-1": "m" * 32}))
    monkeypatch.setenv("DIO_LEGALIS_HMAC_KEY_EPOCH", "market-1")


def _package(channel_id: str = "LINKEDIN_ORGANIC") -> dict[str, object]:
    return {
        "campaign_id": "CMP-2026-001",
        "channel_id": channel_id,
        "package_sha256": "a" * 64,
    }


def test_organic_publication_requires_exact_human_approval() -> None:
    package = _package()
    approved = authorize_market_effect(
        Path("/tmp/unused"),
        package=package,
        human_approval={
            "approved": True,
            "approval_id": "APR-1",
            "approver_id": "operator-byron",
            **package,
        },
    )

    assert approved["release_requirement"] == "human_publication_approval"
    assert approved["external_action_executed"] is False
    assert approved["provider_execution_enabled"] is False

    with pytest.raises(MarketReleaseError, match="does not bind"):
        authorize_market_effect(
            Path("/tmp/unused"),
            package=package,
            human_approval={
                "approved": True,
                "approval_id": "APR-1",
                "approver_id": "operator-byron",
                **{**package, "campaign_id": "CMP-OTHER"},
            },
        )


def test_paid_spend_requires_exact_campaign_legalis_and_budget_authority(tmp_path: Path) -> None:
    package = {**_package("META_ADS"), "spend_minor": 50000, "currency": "ZAR"}
    request = market_legalis_request(package)
    issued = issue_decision(
        tmp_path,
        request=request,
        actor_id="operator-byron",
        policy_version="market-policy-v1",
    )

    authorized = authorize_market_effect(
        tmp_path,
        package=package,
        legalis_decision_id=issued["decision_id"],
        legalis_evidence_binding=issued["evidence_binding"],
        legalis_policy_version="market-policy-v1",
        budget_authority={
            "authority_id": "BUD-1",
            "approved": True,
            "one_use": True,
            "consumed": False,
            "campaign_id": "CMP-2026-001",
            "channel_id": "META_ADS",
            "package_sha256": "a" * 64,
            "currency": "ZAR",
            "max_spend_minor": 50000,
        },
    )

    assert authorized["legalis_decision_id"] == issued["decision_id"]
    assert authorized["budget_authority_id"] == "BUD-1"
    assert authorized["external_action_executed"] is False

    with pytest.raises(MarketReleaseError, match="[Bb]udget authority"):
        authorize_market_effect(
            tmp_path,
            package=package,
            legalis_decision_id=issued["decision_id"],
            legalis_evidence_binding=issued["evidence_binding"],
            legalis_policy_version="market-policy-v1",
            budget_authority={
                "authority_id": "BUD-2",
                "approved": True,
                "one_use": True,
                "consumed": False,
                "campaign_id": "CMP-2026-001",
                "channel_id": "META_ADS",
                "package_sha256": "a" * 64,
                "currency": "ZAR",
                "max_spend_minor": 49999,
            },
        )


def test_paid_spend_refuses_legalis_decision_for_a_different_package(tmp_path: Path) -> None:
    package = {**_package("GOOGLE_ADS"), "spend_minor": 100, "currency": "ZAR"}
    issued = issue_decision(
        tmp_path,
        request=market_legalis_request({**package, "package_sha256": "b" * 64}),
        actor_id="operator-byron",
        policy_version="market-policy-v1",
    )

    with pytest.raises(LegalisError, match="request digest"):
        authorize_market_effect(
            tmp_path,
            package=package,
            legalis_decision_id=issued["decision_id"],
            legalis_evidence_binding=issued["evidence_binding"],
            legalis_policy_version="market-policy-v1",
            budget_authority={
                "authority_id": "BUD-1", "approved": True, "one_use": True, "consumed": False,
                "campaign_id": "CMP-2026-001", "channel_id": "GOOGLE_ADS", "package_sha256": "a" * 64,
                "currency": "ZAR", "max_spend_minor": 100,
            },
        )
