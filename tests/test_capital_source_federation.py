from pathlib import Path

import pytest

from market_capital.sources import CapitalSource, SourcePolicyBlocked, assert_source_usable, load_capital_sources
from market_capital.adapters.base import DiscoveryBatch, DiscoveryObservation


def test_source_registry_contains_multiple_source_strata():
    sources = load_capital_sources(Path("."))
    classes = {source.source_class for source in sources.values()}
    assert {"OPEN_FUNDING_DATA", "FIRST_PARTY_PROGRAMME", "INVESTOR_ECOSYSTEM", "PHILANTHROPY", "PATRONAGE"} <= classes


def test_blocked_source_cannot_execute_discovery():
    source = CapitalSource(
        source_id="X",
        source_name="Blocked",
        source_class="INVESTOR_ECOSYSTEM",
        access_mode="PUBLIC_WEB",
        status="POLICY_BLOCKED",
    )
    with pytest.raises(SourcePolicyBlocked):
        assert_source_usable(source)


def test_discovery_batch_keeps_source_and_assertion_truth_explicit():
    observation = DiscoveryObservation(
        source_id="SRC-TEST",
        entity_type="OPPORTUNITY",
        source_record_id="CALL-1",
        source_reference="https://example.org/call/1",
        observed_at="2026-09-10T00:00:00Z",
        payload={"title": "Public Call"},
    )
    batch = DiscoveryBatch(
        source_id="SRC-TEST",
        observations=(observation,),
        next_cursor=None,
        source_state="READY",
    )
    assert batch.observations[0].assertion_class == "OBSERVED"
    assert batch.source_id == "SRC-TEST"
