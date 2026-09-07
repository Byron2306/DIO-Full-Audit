import json
import subprocess
import sys

from experiments.metamorphic_adaptation.ecosystem_organ_capability_registry import (
    ECOSYSTEM_ORGAN_CAPABILITY_REGISTRY_READY_TOKEN,
    ECOSYSTEM_ORGAN_CAPABILITY_REGISTRY_VERSION,
    build_ecosystem_organ_capability_registry,
)


def test_ecosystem_organ_registry_declares_real_adaptation_surface(tmp_path):
    receipt = build_ecosystem_organ_capability_registry(output_dir=tmp_path)

    assert receipt.registry_version == ECOSYSTEM_ORGAN_CAPABILITY_REGISTRY_VERSION
    assert receipt.status == ECOSYSTEM_ORGAN_CAPABILITY_REGISTRY_READY_TOKEN
    assert receipt.organs_registered >= 10
    assert "BEAST" in receipt.organ_ids
    assert "SOPHIA" in receipt.organ_ids
    assert "EVIDEX" in receipt.organ_ids
    assert "HIVENANCE" in receipt.organ_ids
    assert "ecosystem adaptability" in receipt.ecosystem_adaptation_hypothesis.lower()
    assert receipt.real_ecosystem_execution_authorized is True
    assert receipt.execute_by_default is False
    assert receipt.adaptive_claim_authorized is False


def test_ecosystem_organ_registry_writes_registry_and_receipt(tmp_path):
    receipt = build_ecosystem_organ_capability_registry(output_dir=tmp_path)

    registry = json.loads((tmp_path / "ecosystem_organ_capability_registry.json").read_text())
    saved = json.loads((tmp_path / "ecosystem_organ_capability_registry_receipt.json").read_text())

    assert registry["registry_version"] == ECOSYSTEM_ORGAN_CAPABILITY_REGISTRY_VERSION
    assert len(registry["organs"]) == receipt.organs_registered
    assert saved["status"] == ECOSYSTEM_ORGAN_CAPABILITY_REGISTRY_READY_TOKEN
    assert len(saved["registry_sha256"]) == 64


def test_ecosystem_organ_registry_keeps_forbidden_claims_locked(tmp_path):
    receipt = build_ecosystem_organ_capability_registry(output_dir=tmp_path)

    assert receipt.commercial_or_world_first_claim_authorized is False
    assert receipt.professional_approval_claim_authorized is False
    assert receipt.publication_authorized is False
    assert receipt.spend_authorized is False
    assert receipt.fulfilment_authorized is False
    assert receipt.authority_expansion_authorized is False
    assert "does not authorize adaptive" in receipt.boundary.lower()
    assert "authority-expansion" in receipt.boundary.lower()


def test_ecosystem_organ_registry_cli_runner(tmp_path):
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_metamorphic_adaptation_ecosystem_organ_capability_registry.py",
            "--output",
            str(tmp_path),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    assert ECOSYSTEM_ORGAN_CAPABILITY_REGISTRY_READY_TOKEN in completed.stdout
    assert (tmp_path / "ecosystem_organ_capability_registry.json").exists()
    assert (tmp_path / "ecosystem_organ_capability_registry_receipt.json").exists()
