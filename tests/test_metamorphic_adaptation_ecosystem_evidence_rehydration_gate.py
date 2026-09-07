import json
import subprocess
import sys

from experiments.metamorphic_adaptation.ecosystem_evidence_rehydration_gate import (
    ECOSYSTEM_EVIDENCE_REHYDRATION_READY_TOKEN,
    ECOSYSTEM_EVIDENCE_REHYDRATION_REFUSED_TOKEN,
    ECOSYSTEM_EVIDENCE_REHYDRATION_VERSION,
    rehydrate_ecosystem_adaptive_evidence,
)


def _write_verdict(path, *, ready=True, adaptive=True, tier="T5_BOUNDED_ECOSYSTEM_ADAPTIVE_EVIDENCE_CLAIM"):
    path.write_text(json.dumps({
        "status": (
            "DIO_METAMORPHIC_ADAPTATION_ECOSYSTEM_ADAPTIVE_EVIDENCE_VERDICT_READY"
            if ready
            else "DIO_METAMORPHIC_ADAPTATION_ECOSYSTEM_ADAPTIVE_EVIDENCE_VERDICT_REFUSED"
        ),
        "allowed_claim_tier": tier,
        "real_ecosystem_adaptive_evidence": adaptive,
        "adaptive_claim_authorized": adaptive,
        "baseline_arm": "A_DIO_CORE_ONLY",
        "baseline_arm_mean": 0.673,
        "full_arm": "E_FULL_ECOSYSTEM_ORCHESTRATION",
        "full_arm_mean": 1.0,
        "full_minus_baseline_effect": 0.327,
        "commercial_or_world_first_claim_authorized": False,
        "professional_approval_claim_authorized": False,
        "publication_authorized": False,
        "spend_authorized": False,
        "fulfilment_authorized": False,
        "authority_expansion_authorized": False,
    }, indent=2, sort_keys=True))


def test_rehydration_gate_accepts_source_bound_t5_ecosystem_adaptive_verdict(tmp_path):
    verdict = tmp_path / "ecosystem_adaptive_evidence_verdict.json"
    output = tmp_path / "rehydrated.json"
    _write_verdict(verdict)

    receipt = rehydrate_ecosystem_adaptive_evidence(
        ecosystem_verdict_path=verdict,
        output_path=output,
    )

    assert receipt.gate_version == ECOSYSTEM_EVIDENCE_REHYDRATION_VERSION
    assert receipt.status == ECOSYSTEM_EVIDENCE_REHYDRATION_READY_TOKEN
    assert receipt.ecosystem_verdict_status == "DIO_METAMORPHIC_ADAPTATION_ECOSYSTEM_ADAPTIVE_EVIDENCE_VERDICT_READY"
    assert receipt.source_bound is True
    assert receipt.allowed_claim_tier == "T5_BOUNDED_ECOSYSTEM_ADAPTIVE_EVIDENCE_CLAIM"
    assert receipt.real_ecosystem_adaptive_evidence is True
    assert receipt.adaptive_claim_authorized is True
    assert receipt.baseline_arm == "A_DIO_CORE_ONLY"
    assert receipt.full_arm == "E_FULL_ECOSYSTEM_ORCHESTRATION"
    assert round(receipt.full_minus_baseline_effect, 3) == 0.327
    assert receipt.commercial_or_world_first_claim_authorized is False
    assert output.exists()


def test_rehydration_gate_refuses_non_t5_or_nonadaptive_verdict(tmp_path):
    verdict = tmp_path / "ecosystem_adaptive_evidence_verdict.json"
    output = tmp_path / "rehydrated.json"
    _write_verdict(verdict, adaptive=False, tier="T4_NO_ADAPTIVE_CLAIM")

    receipt = rehydrate_ecosystem_adaptive_evidence(
        ecosystem_verdict_path=verdict,
        output_path=output,
    )

    assert receipt.status == ECOSYSTEM_EVIDENCE_REHYDRATION_REFUSED_TOKEN
    assert receipt.source_bound is True
    assert receipt.real_ecosystem_adaptive_evidence is False
    assert receipt.adaptive_claim_authorized is False
    assert receipt.allowed_claim_tier == "T4_NO_ADAPTIVE_CLAIM"


def test_rehydration_gate_refuses_unready_verdict(tmp_path):
    verdict = tmp_path / "ecosystem_adaptive_evidence_verdict.json"
    output = tmp_path / "rehydrated.json"
    _write_verdict(verdict, ready=False)

    receipt = rehydrate_ecosystem_adaptive_evidence(
        ecosystem_verdict_path=verdict,
        output_path=output,
    )

    assert receipt.status == ECOSYSTEM_EVIDENCE_REHYDRATION_REFUSED_TOKEN
    assert receipt.ecosystem_verdict_status == "DIO_METAMORPHIC_ADAPTATION_ECOSYSTEM_ADAPTIVE_EVIDENCE_VERDICT_REFUSED"
    assert receipt.adaptive_claim_authorized is False


def test_rehydration_gate_writes_hash_and_boundary(tmp_path):
    verdict = tmp_path / "ecosystem_adaptive_evidence_verdict.json"
    output = tmp_path / "rehydrated.json"
    _write_verdict(verdict)

    receipt = rehydrate_ecosystem_adaptive_evidence(
        ecosystem_verdict_path=verdict,
        output_path=output,
    )

    data = json.loads(output.read_text())
    assert data["status"] == receipt.status
    assert len(data["ecosystem_verdict_sha256"]) == 64
    boundary = data["boundary"].lower()
    assert "source-bound" in boundary
    assert "ecosystem adaptive evidence" in boundary
    assert "does not authorize commercial" in boundary
    assert "world-first" in boundary
    assert "authority expansion" in boundary


def test_rehydration_gate_cli_runner(tmp_path):
    verdict = tmp_path / "ecosystem_adaptive_evidence_verdict.json"
    output = tmp_path / "rehydrated.json"
    _write_verdict(verdict)

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_metamorphic_adaptation_ecosystem_evidence_rehydration_gate.py",
            "--ecosystem-verdict",
            str(verdict),
            "--output",
            str(output),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    assert ECOSYSTEM_EVIDENCE_REHYDRATION_READY_TOKEN in completed.stdout
    assert output.exists()
