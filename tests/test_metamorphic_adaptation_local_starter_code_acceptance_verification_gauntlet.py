import json
import subprocess
import sys
from pathlib import Path

from experiments.metamorphic_adaptation.local_starter_code_acceptance_verification_gauntlet import (
    READY_TOKEN,
    build_local_starter_code_acceptance_verification_gauntlet,
)


def _write_starter_scaffold(root: Path) -> None:
    package = root / "dio_trust_dossier_studio"
    tests = root / "tests"
    package.mkdir(parents=True, exist_ok=True)
    tests.mkdir(parents=True, exist_ok=True)

    (package / "__init__.py").write_text("__all__ = ['check_claim_boundary', 'build_evidence_spine']\n", encoding="utf-8")
    (package / "source_intake.py").write_text("def normalize_source(source):\n    return dict(source)\n", encoding="utf-8")
    (package / "claim_boundary_checker.py").write_text(
        "FORBIDDEN_CLAIM_TERMS = ('product-market fit', 'AGI', 'world-first')\n\n"
        "def check_claim_boundary(text):\n"
        "    lowered = text.lower()\n"
        "    violations = [term for term in FORBIDDEN_CLAIM_TERMS if term.lower() in lowered]\n"
        "    return {'claim_boundary_passed': not violations, 'violations': violations, 'human_review_required': True}\n",
        encoding="utf-8",
    )
    (package / "evidence_spine_builder.py").write_text(
        "def build_evidence_spine(receipts):\n"
        "    bound = list(receipts)\n"
        "    return {'evidence_spine_bound': bool(bound), 'receipt_count': len(bound), 'external_validity_claim_authorized': False}\n",
        encoding="utf-8",
    )
    (package / "dossier_renderer.py").write_text(
        "def render_trust_dossier(claim, evidence_spine):\n"
        "    return '# DIO Trust Dossier Studio Draft\\n\\nInternal controlled evidence only. Human review required before external use.'\n",
        encoding="utf-8",
    )
    (package / "human_gate_policy.py").write_text(
        "def require_human_gate():\n    return {'human_review_required': True, 'external_use_authorized': False}\n",
        encoding="utf-8",
    )
    (package / "receipt_emitter.py").write_text(
        "import json\nfrom pathlib import Path\n\ndef emit_receipt(path, payload):\n"
        "    path = Path(path)\n"
        "    path.parent.mkdir(parents=True, exist_ok=True)\n"
        "    final = dict(payload)\n"
        "    final.setdefault('human_review_required', True)\n"
        "    final.setdefault('external_publication_authorized', False)\n"
        "    path.write_text(json.dumps(final, indent=2, sort_keys=True) + '\\n', encoding='utf-8')\n"
        "    return path\n",
        encoding="utf-8",
    )
    (tests / "test_acceptance_contract.py").write_text(
        "from dio_trust_dossier_studio.claim_boundary_checker import check_claim_boundary\n"
        "from dio_trust_dossier_studio.evidence_spine_builder import build_evidence_spine\n\n"
        "def test_forbidden_product_market_fit_claim_is_blocked():\n"
        "    result = check_claim_boundary('DIO has product-market fit')\n"
        "    assert result['claim_boundary_passed'] is False\n"
        "    assert result['human_review_required'] is True\n\n"
        "def test_evidence_spine_never_authorizes_external_validity():\n"
        "    spine = build_evidence_spine([{'source_id': 'receipt-1'}])\n"
        "    assert spine['evidence_spine_bound'] is True\n"
        "    assert spine['external_validity_claim_authorized'] is False\n",
        encoding="utf-8",
    )
    (root / "README.md").write_text("# DIO_TRUST_DOSSIER_STUDIO Controlled Starter Code\n\nHuman review is required before any external use.\n", encoding="utf-8")


def _write_starter_receipt(path: Path, root: Path) -> Path:
    manifest = []
    for file_path in sorted(p for p in root.rglob("*") if p.is_file()):
        relative = str(file_path.relative_to(root))
        if relative == "README.md":
            kind = "readme"
        elif relative.startswith("tests/"):
            kind = "test"
        elif relative.endswith("receipt_emitter.py"):
            kind = "receipt_schema"
        else:
            kind = "source"
        manifest.append({"relative_path": relative, "kind": kind, "sha256": "test-sha"})

    manifest_path = path.parent / "controlled_starter_code_file_manifest.json"
    manifest_path.write_text(
        json.dumps({"selected_product": "DIO_TRUST_DOSSIER_STUDIO", "files_written": manifest}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    receipt = {
        "status": "DIO_METAMORPHIC_ADAPTATION_CONTROLLED_STARTER_CODE_GENERATION_READY",
        "gauntlet_version": "DIO_METAMORPHIC_ADAPTATION_CONTROLLED_STARTER_CODE_GENERATION_V1",
        "allowed_claim_tier": "T16_CANDIDATE_CONTROLLED_LOCAL_STARTER_CODE_GENERATION_EVIDENCE",
        "selected_product": "DIO_TRUST_DOSSIER_STUDIO",
        "starter_code_root_path": str(root),
        "starter_code_file_manifest_path": str(manifest_path),
        "source_files_written": 6,
        "test_files_written": 1,
        "receipt_schema_files_written": 1,
        "readmes_written": 1,
        "starter_code_written": True,
        "starter_code_claim_authorized": True,
        "product_capability_execution_authorized": False,
        "actual_execution_authorized": False,
        "autonomous_development_authorized": False,
        "commercial_validation_claim_authorized": False,
        "product_market_fit_claim_authorized": False,
        "agi_claim_authorized": False,
        "world_first_claim_authorized": False,
        "authority_expansion_authorized": False,
        "publication_authorized": False,
        "spend_authorized": False,
        "fulfilment_authorized": False,
    }
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def test_build_gauntlet_verifies_starter_code_acceptance_with_locks(tmp_path):
    root = tmp_path / "starter"
    _write_starter_scaffold(root)
    starter_receipt = _write_starter_receipt(tmp_path / "controlled_starter_code_generation_receipt.json", root)

    receipt = build_local_starter_code_acceptance_verification_gauntlet(starter_receipt, tmp_path / "out", execute=True)

    assert receipt.status == READY_TOKEN
    assert receipt.allowed_claim_tier == "T17_CANDIDATE_LOCAL_STARTER_CODE_ACCEPTANCE_VERIFICATION_EVIDENCE"
    assert receipt.selected_product == "DIO_TRUST_DOSSIER_STUDIO"
    assert receipt.local_acceptance_verification_evidence is True
    assert receipt.starter_code_acceptance_verified is True
    assert receipt.acceptance_tests_passed is True
    assert receipt.files_inspected == 9
    assert receipt.source_files_verified == 6
    assert receipt.test_files_verified == 1
    assert receipt.receipt_schema_files_verified == 1
    assert receipt.readmes_verified == 1
    assert receipt.product_capability_execution_authorized is False
    assert receipt.actual_product_execution_authorized is False
    assert receipt.external_use_authorized is False
    assert receipt.autonomous_development_authorized is False
    assert Path(receipt.acceptance_verification_summary_path).exists()
    assert Path(receipt.acceptance_verification_receipt_path).exists()


def test_build_gauntlet_refuses_missing_starter_code_root(tmp_path):
    starter_receipt = _write_starter_receipt(tmp_path / "controlled_starter_code_generation_receipt.json", tmp_path / "missing")

    try:
        build_local_starter_code_acceptance_verification_gauntlet(starter_receipt, tmp_path / "out", execute=True)
    except ValueError as exc:
        assert "starter code root does not exist" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_build_gauntlet_plan_only_does_not_verify(tmp_path):
    root = tmp_path / "starter"
    _write_starter_scaffold(root)
    starter_receipt = _write_starter_receipt(tmp_path / "controlled_starter_code_generation_receipt.json", root)

    receipt = build_local_starter_code_acceptance_verification_gauntlet(starter_receipt, tmp_path / "out", execute=False)

    assert receipt.status == READY_TOKEN
    assert receipt.executed is False
    assert receipt.starter_code_acceptance_verified is False
    assert receipt.acceptance_tests_passed is False
    assert receipt.local_acceptance_verification_evidence is False


def test_cli_runner_writes_receipt(tmp_path):
    root = tmp_path / "starter"
    _write_starter_scaffold(root)
    starter_receipt = _write_starter_receipt(tmp_path / "controlled_starter_code_generation_receipt.json", root)
    output = tmp_path / "gauntlet"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_metamorphic_adaptation_local_starter_code_acceptance_verification_gauntlet.py",
            "--controlled-starter-code-generation",
            str(starter_receipt),
            "--output",
            str(output),
            "--execute",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert READY_TOKEN in result.stdout
    written = output / "local_starter_code_acceptance_verification_receipt.json"
    assert written.exists()
    payload = json.loads(written.read_text(encoding="utf-8"))
    assert payload["status"] == READY_TOKEN
    assert payload["starter_code_acceptance_verified"] is True
    assert payload["product_capability_execution_authorized"] is False
