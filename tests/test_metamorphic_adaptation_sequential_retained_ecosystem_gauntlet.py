from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

from experiments.metamorphic_adaptation.sequential_retained_ecosystem_gauntlet import (
    SEQUENTIAL_RETAINED_ECOSYSTEM_GAUNTLET_READY_TOKEN,
    SEQUENTIAL_RETAINED_ECOSYSTEM_GAUNTLET_REFUSED_TOKEN,
    run_sequential_retained_ecosystem_gauntlet,
)


def _write_ecosystem_digest(path: Path, *, ready: bool = True) -> None:
    path.write_text(json.dumps({
        "status": (
            "DIO_METAMORPHIC_ADAPTATION_ECOSYSTEM_ADAPTATION_EVIDENCE_DIGEST_READY"
            if ready
            else "DIO_METAMORPHIC_ADAPTATION_ECOSYSTEM_ADAPTATION_EVIDENCE_DIGEST_REFUSED"
        ),
        "real_ecosystem_adaptive_evidence": ready,
        "adaptive_claim_authorized": ready,
        "allowed_claim_tier": (
            "T5_BOUNDED_ECOSYSTEM_ADAPTIVE_EVIDENCE_CLAIM" if ready else "T0_NO_CLAIM"
        ),
        "full_minus_baseline_effect": 0.327 if ready else 0.0,
        "baseline_arm_mean": 0.673 if ready else 0.0,
        "full_arm_mean": 1.0 if ready else 0.0,
        "commercial_or_world_first_claim_authorized": False,
        "professional_approval_claim_authorized": False,
        "publication_authorized": False,
        "spend_authorized": False,
        "fulfilment_authorized": False,
        "authority_expansion_authorized": False,
    }, indent=2, sort_keys=True) + "\n")


def test_refuses_without_explicit_execute(tmp_path):
    digest = tmp_path / "ecosystem_digest.json"
    _write_ecosystem_digest(digest)

    receipt = run_sequential_retained_ecosystem_gauntlet(
        ecosystem_adaptation_digest_path=digest,
        output_dir=tmp_path / "out",
        execute=False,
    )

    assert receipt.status == SEQUENTIAL_RETAINED_ECOSYSTEM_GAUNTLET_REFUSED_TOKEN
    assert receipt.executed is False
    assert receipt.adaptive_claim_authorized is False
    assert receipt.real_retained_adaptive_evidence is False
    assert receipt.encounters_executed == 0


def test_refuses_when_prior_ecosystem_digest_is_not_ready(tmp_path):
    digest = tmp_path / "ecosystem_digest.json"
    _write_ecosystem_digest(digest, ready=False)

    receipt = run_sequential_retained_ecosystem_gauntlet(
        ecosystem_adaptation_digest_path=digest,
        output_dir=tmp_path / "out",
        execute=True,
    )

    assert receipt.status == SEQUENTIAL_RETAINED_ECOSYSTEM_GAUNTLET_REFUSED_TOKEN
    assert receipt.executed is False
    assert receipt.allowed_claim_tier == "T0_NO_CLAIM"


def test_ready_gauntlet_shows_retained_sequential_lift(tmp_path):
    digest = tmp_path / "ecosystem_digest.json"
    output_dir = tmp_path / "out"
    _write_ecosystem_digest(digest)

    receipt = run_sequential_retained_ecosystem_gauntlet(
        ecosystem_adaptation_digest_path=digest,
        output_dir=output_dir,
        execute=True,
    )

    assert receipt.status == SEQUENTIAL_RETAINED_ECOSYSTEM_GAUNTLET_READY_TOKEN
    assert receipt.executed is True
    assert receipt.encounters_executed == 3
    assert receipt.tasks_per_encounter == 5
    assert receipt.outputs_produced == 15
    assert receipt.retention_state_receipts_written == 15
    assert receipt.encounter_1_mean_score == 0.74
    assert receipt.encounter_3_mean_score == 0.9
    assert receipt.encounter_3_minus_encounter_1_effect == 0.16
    assert receipt.retained_adaptive_effect_threshold_met is True
    assert receipt.real_retained_adaptive_evidence is True
    assert receipt.adaptive_claim_authorized is True
    assert receipt.allowed_claim_tier == "T6_CANDIDATE_SEQUENTIAL_RETAINED_ECOSYSTEM_ADAPTATION_EVIDENCE"

    outputs = [json.loads(line) for line in Path(receipt.outputs_path).read_text().splitlines()]
    assert len(outputs) == 15
    first = [item for item in outputs if item["encounter_index"] == 1]
    later = [item for item in outputs if item["encounter_index"] == 3]
    assert all(item["retention_state_used"] is False for item in first)
    assert all(item["retention_state_used"] is True for item in later)
    assert all("prior_retention_receipts" in item for item in later)


def test_claim_locks_remain_closed_except_bounded_adaptive_claim(tmp_path):
    digest = tmp_path / "ecosystem_digest.json"
    _write_ecosystem_digest(digest)

    receipt = run_sequential_retained_ecosystem_gauntlet(
        ecosystem_adaptation_digest_path=digest,
        output_dir=tmp_path / "out",
        execute=True,
    )

    assert receipt.adaptive_claim_authorized is True
    assert receipt.commercial_or_world_first_claim_authorized is False
    assert receipt.professional_approval_claim_authorized is False
    assert receipt.publication_authorized is False
    assert receipt.spend_authorized is False
    assert receipt.fulfilment_authorized is False
    assert receipt.authority_expansion_authorized is False
    assert "candidate" in receipt.boundary.lower()
    assert "world-first" in receipt.boundary


def test_cli_runner(tmp_path):
    digest = tmp_path / "ecosystem_digest.json"
    output_dir = tmp_path / "out"
    _write_ecosystem_digest(digest)

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_metamorphic_adaptation_sequential_retained_ecosystem_gauntlet.py",
            "--ecosystem-adaptation-digest",
            str(digest),
            "--output",
            str(output_dir),
            "--execute",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    assert SEQUENTIAL_RETAINED_ECOSYSTEM_GAUNTLET_READY_TOKEN in completed.stdout
    payload = json.loads(completed.stdout.split("\nDIO_METAMORPHIC_ADAPTATION_")[0])
    assert payload["real_retained_adaptive_evidence"] is True
    assert payload["adaptive_claim_authorized"] is True
