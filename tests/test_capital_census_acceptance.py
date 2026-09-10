from __future__ import annotations

import json
from pathlib import Path

from scripts.build_capital_support_census import build_acceptance_receipt
from scripts.export_capital_support_census import export_census


ROOT = Path(__file__).resolve().parents[1]


def _seed_census(tmp_path: Path):
    from market_capital.census import CapitalCensus

    db = tmp_path / "state" / "market_capital" / "census" / "capital_support.sqlite"
    census = CapitalCensus(db)
    census.initialize()
    census.upsert_organisation({
        "organisation_id": "ORG-A",
        "canonical_name": "Alpha Foundation",
        "country": "ZA",
        "observed_at": "2026-09-10T00:00:00Z",
    })
    census.upsert_organisation({
        "organisation_id": "ORG-B",
        "canonical_name": "Beta Ventures",
        "country": "GB",
        "observed_at": "2026-09-10T00:00:00Z",
    })
    for opportunity_id, org_id, typ, source_id in (
        ("OPP-A", "ORG-A", "GRANT", "SRC-GRANTS-GOV"),
        ("OPP-B", "ORG-B", "INVESTOR", "SRC-CORDIS"),
        ("OPP-C", "ORG-A", "PRIZE", "SRC-360GIVING"),
    ):
        census.upsert_opportunity({
            "opportunity_id": opportunity_id,
            "organisation_id": org_id,
            "opportunity_type": typ,
            "title": f"{typ} opportunity",
            "observed_at": "2026-09-10T00:00:00Z",
        })
        census.record_assertion({
            "subject_entity_id": opportunity_id,
            "predicate": "source_observation",
            "value": {"source_id": source_id},
            "assertion_class": "OBSERVED_PUBLIC_SOURCE",
            "source_id": source_id,
            "source_reference": f"https://example.test/{opportunity_id}",
            "observed_at": "2026-09-10T00:00:00Z",
        })
    census.link_relationship("FUNDER_TO_OPPORTUNITY", "ORG-A", "OPP-A")
    return census


def test_acceptance_requires_multi_source_non_synthetic_census(tmp_path):
    census = _seed_census(tmp_path)
    receipt = build_acceptance_receipt(
        root=tmp_path,
        census=census,
        discovery_receipts=[
            {"source_results": {
                "SRC-GRANTS-GOV": {"state": "READY", "persisted": 1},
                "SRC-CORDIS": {"state": "READY", "persisted": 1},
                "SRC-360GIVING": {"state": "READY", "persisted": 1},
            }, "synthetic_fallback_records": 0,
             "external_contacts_sent": 0,
             "submission_actions_executed": 0,
             "financial_actions_executed": 0}
        ],
    )
    assert receipt["counts"]["organisations"] > 0
    assert receipt["counts"]["opportunities"] > 0
    assert receipt["source_class_count"] >= 3
    assert receipt["synthetic_records"] == 0
    assert receipt["external_contacts_sent"] == 0
    assert receipt["submission_actions_executed"] == 0
    assert receipt["financial_actions_executed"] == 0
    assert receipt["authority_created"] is False
    assert receipt["external_effects"] is False


def test_export_writes_required_versioned_no_authority_artifacts(tmp_path):
    census = _seed_census(tmp_path)
    census_root = tmp_path / "state" / "market_capital" / "census"
    (census_root / "source_health.json").write_text(json.dumps({"sources": {}}), encoding="utf-8")
    outputs = export_census(root=tmp_path, census=census)
    required = {
        "organisations.csv",
        "opportunities.csv",
        "relationships.csv",
        "source_health.json",
        "recommendations.json",
    }
    assert required <= {Path(path).name for path in outputs.values()}
    recommendations = json.loads((census_root / "recommendations.json").read_text(encoding="utf-8"))
    assert recommendations["census_version"]
    assert recommendations["generated_at"]
    assert recommendations["authority_created"] is False
    assert recommendations["external_effects"] is False


def test_deployment_has_daily_weekly_and_monthly_bounded_census_timers():
    unit_root = ROOT / "ops" / "systemd" / "user"
    expected = {
        "dio-capital-census-daily.timer": "OnCalendar=*-*-*",
        "dio-capital-census-weekly.timer": "OnCalendar=Sun",
        "dio-capital-census-monthly.timer": "OnCalendar=*-*-01",
    }
    for name, cadence in expected.items():
        text = (unit_root / name).read_text(encoding="utf-8")
        assert cadence in text
        assert "Persistent=true" in text
        assert "WantedBy=timers.target" in text

    for mode in ("daily", "weekly", "monthly"):
        service = (unit_root / f"dio-capital-census-{mode}.service").read_text(encoding="utf-8")
        assert "/srv/dio/control-deck" in service
        assert "build_capital_support_census.py" in service
        assert "--mode" in service
        assert "send" not in service.lower()
        assert "submit" not in service.lower()


def test_slice3_workflow_requires_final_census_gate_and_browser_checks():
    workflow = (ROOT / ".github" / "workflows" / "dio-slice3-capital-support-atlas.yml").read_text(encoding="utf-8")
    assert "DIO_CAPITAL_SUPPORT_INTELLIGENCE_CENSUS_CI_VERIFIED" in workflow
    for script in (
        "dashboard/capital_support_slice3.js",
        "dashboard/goldeneye_capital_slice3.js",
        "dashboard/market_capital_support_slice3.js",
        "dashboard/atlas_capital_census.js",
    ):
        assert f"node --check {script}" in workflow
