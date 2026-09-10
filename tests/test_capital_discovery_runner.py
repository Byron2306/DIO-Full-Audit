from pathlib import Path

from market_capital.adapters.base import DiscoveryBatch, DiscoveryObservation
from market_capital.census import CapitalCensus
from market_capital.discovery_runner import run_discovery_cycle
from market_capital.sources import SourceUnavailable


class OneOpportunityAdapter:
    def discover(self, plan_slice):
        return DiscoveryBatch(
            source_id="SRC-GRANTS-GOV",
            observations=(DiscoveryObservation(
                source_id="SRC-GRANTS-GOV",
                entity_type="OPPORTUNITY",
                source_record_id="CALL-1",
                source_reference="https://example.org/call/1",
                observed_at="2026-09-10T08:00:00Z",
                payload={
                    "opportunity_id": "CALL-1",
                    "opportunity_type": "GRANT",
                    "title": "Education Innovation Call",
                    "truth_class": "LIVE_OPPORTUNITY_OBSERVATION",
                },
            ),),
            next_cursor=None,
            source_state="READY",
        )


class RaisingUnavailableAdapter:
    def discover(self, plan_slice):
        raise SourceUnavailable("temporarily unavailable")


def test_runner_persists_real_observation_without_external_actions(tmp_path: Path):
    census = CapitalCensus(tmp_path / "capital.sqlite")
    census.initialize()
    plan = {
        "cycle_id": "CYCLE-1",
        "source_allocations": [{"source_id": "SRC-GRANTS-GOV", "budget": 5}],
        "novelty_budget": 1,
        "reverification_budget": 1,
        "cycle_budget": 7,
    }
    receipt = run_discovery_cycle(
        root=tmp_path,
        census=census,
        plan=plan,
        adapters={"SRC-GRANTS-GOV": OneOpportunityAdapter()},
    )
    assert receipt["source_results"]["SRC-GRANTS-GOV"]["state"] == "READY"
    assert census.snapshot_counts()["opportunities"] == 1
    assert receipt["synthetic_fallback_records"] == 0
    assert receipt["external_contacts_sent"] == 0
    assert receipt["submission_actions_executed"] == 0
    assert receipt["financial_actions_executed"] == 0


def test_unavailable_source_is_recorded_not_replaced(tmp_path: Path):
    census = CapitalCensus(tmp_path / "capital.sqlite")
    census.initialize()
    plan = {
        "cycle_id": "CYCLE-2",
        "source_allocations": [{"source_id": "SRC-X", "budget": 5}],
        "novelty_budget": 1,
        "reverification_budget": 1,
        "cycle_budget": 7,
    }
    receipt = run_discovery_cycle(
        root=tmp_path,
        census=census,
        plan=plan,
        adapters={"SRC-X": RaisingUnavailableAdapter()},
    )
    assert receipt["source_results"]["SRC-X"]["state"] == "SOURCE_UNAVAILABLE"
    assert receipt["synthetic_fallback_records"] == 0
    assert census.snapshot_counts()["opportunities"] == 0
