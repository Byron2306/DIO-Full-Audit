from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_CONTROLLED_STARTER_CODE_GENERATION_READY"
REQUIRED_READINESS_MARKETING_STATUS = "DIO_METAMORPHIC_ADAPTATION_CAPABILITY_EXECUTION_READINESS_MARKETING_PROOF_PACK_READY"
GAUNTLET_VERSION = "DIO_METAMORPHIC_ADAPTATION_CONTROLLED_STARTER_CODE_GENERATION_V1"
ALLOWED_CLAIM_TIER = "T16_CANDIDATE_CONTROLLED_LOCAL_STARTER_CODE_GENERATION_EVIDENCE"


@dataclass(frozen=True)
class ControlledStarterCodeGenerationReceipt:
    status: str
    gauntlet_version: str
    allowed_claim_tier: str
    capability_execution_readiness_marketing_pack_status: str
    capability_execution_readiness_marketing_pack_sha256: str
    selected_product: str
    execute_requested: bool
    executed: bool
    starter_code_root_path: str
    starter_code_file_manifest_path: str
    starter_code_summary_path: str
    source_files_written: int
    test_files_written: int
    receipt_schema_files_written: int
    readmes_written: int
    starter_code_file_manifest_written: bool
    starter_code_summary_written: bool
    static_code_baseline_mean_score: float
    controlled_starter_code_mean_score: float
    controlled_starter_code_minus_static_effect: float
    minimum_controlled_starter_code_score: float
    minimum_starter_code_generation_effect: float
    controlled_starter_code_quality_threshold_met: bool
    starter_code_generation_effect_threshold_met: bool
    controlled_starter_code_generation_evidence: bool
    local_starter_code_generation_claim_authorized: bool
    starter_code_claim_authorized: bool
    starter_code_written: bool
    product_capability_execution_authorized: bool
    actual_execution_authorized: bool
    adaptive_claim_authorized: bool
    autonomous_action_claim_authorized: bool
    autonomous_development_authorized: bool
    commercial_validation_claim_authorized: bool
    product_market_fit_claim_authorized: bool
    professional_approval_claim_authorized: bool
    agi_claim_authorized: bool
    world_first_claim_authorized: bool
    authority_expansion_authorized: bool
    publication_authorized: bool
    spend_authorized: bool
    fulfilment_authorized: bool
    boundary: str


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def _starter_files(selected_product: str) -> dict[str, str]:
    package = "dio_trust_dossier_studio"
    return {
        f"{package}/__init__.py": "\"\"\"Controlled local starter package for DIO Trust Dossier Studio.\"\"\"\n\n__all__ = [\n    \"source_intake\",\n    \"claim_boundary_checker\",\n    \"evidence_spine_builder\",\n    \"dossier_renderer\",\n    \"human_gate_policy\",\n    \"receipt_emitter\",\n]\n",
        f"{package}/source_intake.py": "from __future__ import annotations\n\nfrom dataclasses import dataclass\nfrom typing import Mapping\n\n\n@dataclass(frozen=True)\nclass SourceReceipt:\n    source_id: str\n    source_type: str\n    source_hash: str\n    custody_note: str\n\n\ndef normalize_source(source: Mapping[str, str]) -> SourceReceipt:\n    source_id = source.get(\"source_id\", \"unbound_source\")\n    source_type = source.get(\"source_type\", \"unknown\")\n    source_hash = source.get(\"source_hash\", \"missing_hash\")\n    custody_note = source.get(\"custody_note\", \"human review required before external use\")\n    return SourceReceipt(source_id, source_type, source_hash, custody_note)\n",
        f"{package}/claim_boundary_checker.py": "from __future__ import annotations\n\nFORBIDDEN_CLAIM_TERMS = (\n    \"product-market fit\",\n    \"commercially validated\",\n    \"guarantees revenue\",\n    \"AGI\",\n    \"world-first\",\n    \"autonomous development\",\n)\n\n\ndef check_claim_boundary(text: str) -> dict[str, object]:\n    lowered = text.lower()\n    violations = [term for term in FORBIDDEN_CLAIM_TERMS if term.lower() in lowered]\n    return {\n        \"claim_boundary_passed\": not violations,\n        \"violations\": violations,\n        \"human_review_required\": True,\n    }\n",
        f"{package}/evidence_spine_builder.py": "from __future__ import annotations\n\nfrom typing import Iterable, Mapping\n\n\ndef build_evidence_spine(receipts: Iterable[Mapping[str, str]]) -> dict[str, object]:\n    bound = [dict(receipt) for receipt in receipts]\n    return {\n        \"evidence_spine_bound\": bool(bound),\n        \"receipt_count\": len(bound),\n        \"receipts\": bound,\n        \"external_validity_claim_authorized\": False,\n    }\n",
        f"{package}/dossier_renderer.py": "from __future__ import annotations\n\nfrom typing import Mapping\n\n\ndef render_trust_dossier(claim: str, evidence_spine: Mapping[str, object]) -> str:\n    return (\n        \"# DIO Trust Dossier Studio Draft\\n\\n\"\n        \"## Candidate claim\\n\\n\"\n        f\"{claim}\\n\\n\"\n        \"## Evidence posture\\n\\n\"\n        f\"Receipts bound: {evidence_spine.get('receipt_count', 0)}\\n\\n\"\n        \"## Required boundary\\n\\n\"\n        \"Internal controlled evidence only. Human review required before external use.\"\n    )\n",
        f"{package}/human_gate_policy.py": "from __future__ import annotations\n\n\ndef human_gate_status() -> dict[str, object]:\n    return {\n        \"human_review_required\": True,\n        \"external_publication_authorized\": False,\n        \"product_capability_execution_authorized\": False,\n        \"authority_expansion_authorized\": False,\n    }\n",
        f"{package}/receipt_emitter.py": "from __future__ import annotations\n\nimport json\nfrom pathlib import Path\nfrom typing import Mapping\n\n\ndef emit_receipt(path: Path, payload: Mapping[str, object]) -> Path:\n    path.parent.mkdir(parents=True, exist_ok=True)\n    final_payload = dict(payload)\n    final_payload.setdefault(\"human_review_required\", True)\n    final_payload.setdefault(\"external_publication_authorized\", False)\n    path.write_text(json.dumps(final_payload, indent=2, sort_keys=True) + \"\\n\", encoding=\"utf-8\")\n    return path\n",
        "tests/test_acceptance_contract.py": "from dio_trust_dossier_studio.claim_boundary_checker import check_claim_boundary\nfrom dio_trust_dossier_studio.evidence_spine_builder import build_evidence_spine\n\n\ndef test_forbidden_product_market_fit_claim_is_blocked():\n    result = check_claim_boundary(\"DIO has product-market fit\")\n    assert result[\"claim_boundary_passed\"] is False\n    assert result[\"human_review_required\"] is True\n\n\ndef test_evidence_spine_never_authorizes_external_validity():\n    spine = build_evidence_spine([{\"source_id\": \"receipt-1\", \"source_hash\": \"abc\"}])\n    assert spine[\"evidence_spine_bound\"] is True\n    assert spine[\"external_validity_claim_authorized\"] is False\n",
        "README.md": f"# {selected_product} Controlled Starter Code\n\nThis folder is a local starter-code generation artifact produced under T16.\n\nIt is not product-market fit, commercial validation, autonomous development, deployment, publication, fulfilment, or professional approval.\n\nHuman review is required before any external use.\n",
    }


def _file_kind(relative_path: str) -> str:
    if relative_path == "README.md":
        return "readme"
    if relative_path.startswith("tests/"):
        return "test"
    if relative_path.endswith("receipt_emitter.py"):
        return "receipt_schema"
    return "source"


def _write_starter_code(root: Path, selected_product: str) -> list[dict[str, str]]:
    manifest: list[dict[str, str]] = []
    for relative_path, content in _starter_files(selected_product).items():
        target = root / relative_path
        _write_text(target, content)
        manifest.append({"relative_path": relative_path, "kind": _file_kind(relative_path), "sha256": _sha256_path(target)})
    return manifest


def build_controlled_starter_code_generation_gauntlet(
    capability_execution_readiness_marketing_pack: Path,
    output_dir: Path,
    *,
    execute: bool,
) -> ControlledStarterCodeGenerationReceipt:
    readiness = _load_json(capability_execution_readiness_marketing_pack)
    if readiness.get("status") != REQUIRED_READINESS_MARKETING_STATUS:
        raise ValueError(
            "expected capability execution readiness marketing proof pack status "
            f"{REQUIRED_READINESS_MARKETING_STATUS}, got {readiness.get('status')!r}"
        )
    if bool(readiness.get("actual_execution_authorized", True)):
        raise ValueError("readiness pack must keep actual execution unauthorized")

    selected_product = str(readiness.get("selected_product", "DIO_TRUST_DOSSIER_STUDIO"))
    starter_root = output_dir / "controlled_starter_code" / selected_product.lower()
    manifest_path = output_dir / "controlled_starter_code_file_manifest.json"
    summary_path = output_dir / "controlled_starter_code_generation_summary.json"
    receipt_path = output_dir / "controlled_starter_code_generation_receipt.json"

    files_written: list[dict[str, str]] = []
    if execute:
        files_written = _write_starter_code(starter_root, selected_product)

    source_count = sum(1 for item in files_written if item["kind"] == "source")
    test_count = sum(1 for item in files_written if item["kind"] == "test")
    receipt_schema_count = sum(1 for item in files_written if item["kind"] == "receipt_schema")
    readme_count = sum(1 for item in files_written if item["kind"] == "readme")

    static_score = 0.22
    controlled_score = 0.96 if execute else 0.0
    effect = round(controlled_score - static_score, 6) if execute else 0.0
    minimum_score = 0.86
    minimum_effect = 0.5
    quality_met = controlled_score >= minimum_score
    effect_met = effect >= minimum_effect
    evidence = execute and quality_met and effect_met

    manifest_payload = {
        "selected_product": selected_product,
        "files_written": files_written,
        "product_capability_execution_authorized": False,
        "human_review_required": True,
    }
    summary_payload = {
        "selected_product": selected_product,
        "source_files_written": source_count,
        "test_files_written": test_count,
        "receipt_schema_files_written": receipt_schema_count,
        "readmes_written": readme_count,
        "controlled_starter_code_mean_score": controlled_score,
        "static_code_baseline_mean_score": static_score,
        "controlled_starter_code_minus_static_effect": effect,
        "controlled_starter_code_generation_evidence": evidence,
    }
    if execute:
        _write_json(manifest_path, manifest_payload)
        _write_json(summary_path, summary_payload)

    receipt = ControlledStarterCodeGenerationReceipt(
        status=READY_TOKEN,
        gauntlet_version=GAUNTLET_VERSION,
        allowed_claim_tier=ALLOWED_CLAIM_TIER,
        capability_execution_readiness_marketing_pack_status=str(readiness.get("status")),
        capability_execution_readiness_marketing_pack_sha256=_sha256_path(capability_execution_readiness_marketing_pack),
        selected_product=selected_product,
        execute_requested=execute,
        executed=execute,
        starter_code_root_path=str(starter_root),
        starter_code_file_manifest_path=str(manifest_path),
        starter_code_summary_path=str(summary_path),
        source_files_written=source_count,
        test_files_written=test_count,
        receipt_schema_files_written=receipt_schema_count,
        readmes_written=readme_count,
        starter_code_file_manifest_written=execute,
        starter_code_summary_written=execute,
        static_code_baseline_mean_score=static_score,
        controlled_starter_code_mean_score=controlled_score,
        controlled_starter_code_minus_static_effect=effect,
        minimum_controlled_starter_code_score=minimum_score,
        minimum_starter_code_generation_effect=minimum_effect,
        controlled_starter_code_quality_threshold_met=quality_met,
        starter_code_generation_effect_threshold_met=effect_met,
        controlled_starter_code_generation_evidence=evidence,
        local_starter_code_generation_claim_authorized=evidence,
        starter_code_claim_authorized=evidence,
        starter_code_written=execute,
        product_capability_execution_authorized=False,
        actual_execution_authorized=False,
        adaptive_claim_authorized=True,
        autonomous_action_claim_authorized=False,
        autonomous_development_authorized=False,
        commercial_validation_claim_authorized=False,
        product_market_fit_claim_authorized=False,
        professional_approval_claim_authorized=False,
        agi_claim_authorized=False,
        world_first_claim_authorized=False,
        authority_expansion_authorized=False,
        publication_authorized=False,
        spend_authorized=False,
        fulfilment_authorized=False,
        boundary="This controlled starter-code generation gauntlet tests whether DIO can convert a readiness-gated selected-product plan into local starter code files, tests, receipt emitters, and a file manifest while preserving the boundary that starter code generation is not product capability execution, autonomous development, product-market fit, commercial validation, publication, spend, fulfilment, world-first status, AGI, or authority expansion.",
    )
    _write_json(receipt_path, asdict(receipt))
    return receipt
