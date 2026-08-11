from __future__ import annotations

from pathlib import Path

import pytest

from products.case_migration import migrate_v1_to_v2
from products.governed_case import CASE_SCHEMA, stable_id, validate_case
from products.registry import get_profile


def legacy_case(product: str, job_id: str) -> dict:
    case_id = stable_id("CASE", product, job_id)
    return {
        "schema": "dio.governed_case.v1",
        "case_id": case_id,
        "product": product,
        "status": "intake_pending",
        "created_at": "2026-08-11T12:00:00+00:00",
        "updated_at": "2026-08-11T12:00:00+00:00",
        "lineage": {
            "lead_id": "LEAD-1",
            "conversation_id": "CONV-1",
            "job_id": job_id,
            "transaction_id": None,
            "campaign_id": "CMP-1",
            "parent_case_id": None,
        },
        "requirements": [],
        "claims": [],
        "evidence": [
            {
                "evidence_id": "EVID-1",
                "kind": "email",
                "source_ref": "mail.json",
                "sha256": None,
                "observed_at": "2026-08-11T12:00:00+00:00",
                "trust_state": "captured_untrusted",
                "freshness_state": "unknown",
            }
        ],
        "gates": [
            {"gate_id": "intake_authority", "state": "needs_you", "reason": "legacy", "required_authority": "system_owner"},
            {"gate_id": "generic_executor", "state": "refuse", "reason": "legacy", "required_authority": None},
            {"gate_id": "external_release", "state": "needs_you", "reason": "legacy", "required_authority": "release_operator"},
        ],
        "decisions": [],
        "outputs": [],
    }


def source(job_id: str) -> dict:
    return {
        "job_id": job_id,
        "route": {"product": "dio_assurance"},
        "source": {"lead_id": "LEAD-1", "conversation_id": "CONV-1"},
        "attribution": {"campaign_id": "CMP-1"},
        "evidence": [
            {
                "evidence_id": "EVID-1",
                "source_type": "email",
                "source_path": "mail.json",
                "date_observed": "2026-08-11T12:00:00+00:00",
            }
        ],
    }


def test_scaffold_only_case_migrates_losslessly(tmp_path: Path) -> None:
    job_id = "dio_assurance-legacy-001"
    source_path = tmp_path / "source.json"
    source_path.write_text("{}", encoding="utf-8")
    migrated, receipt = migrate_v1_to_v2(
        old_case=legacy_case("dio_assurance", job_id),
        source=source(job_id),
        source_path=source_path,
        profile=get_profile("dio_assurance"),
        intake_state="pending",
    )
    assert migrated["schema"] == CASE_SCHEMA
    assert migrated["case_id"] == stable_id("CASE", "dio_assurance", job_id)
    assert migrated["lineage"]["lead_id"] == "LEAD-1"
    assert migrated["gates"][0]["state"] == "needs_you"
    assert receipt["lossless"] is True
    assert len(receipt["case_sha256"]) == 64
    validate_case(migrated)


def test_migration_refuses_legacy_claims_instead_of_flattening_them(tmp_path: Path) -> None:
    job_id = "dio_assurance-legacy-002"
    old = legacy_case("dio_assurance", job_id)
    old["claims"] = [{"claim_id": "OLD-CLAIM"}]
    source_path = tmp_path / "source.json"
    source_path.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="cannot be migrated losslessly"):
        migrate_v1_to_v2(
            old_case=old,
            source=source(job_id),
            source_path=source_path,
            profile=get_profile("dio_assurance"),
            intake_state="pending",
        )
