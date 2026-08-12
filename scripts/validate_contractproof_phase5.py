from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from products.compiler import compile_manifest, load_capability_catalog
from products.contractproof.proof import REQUIRED_ARTIFACT_TYPES, verify_integrity
from products.contractproof.runner import EXECUTOR_ID, run_contractproof
from products.work_pattern_runtime import plan_manifest
from validate_product_constitution import validate as validate_constitution
from validate_profiles import validate as validate_profiles


MANIFEST = ROOT / "config" / "products" / "manifests" / "contractproof.json"
GOLDEN_ROOT = ROOT / "config" / "products" / "golden" / "contractproof"
NOW = "2026-08-12T12:00:00+00:00"


class AcceptanceError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AcceptanceError(message)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    try:
        require(bool(validate_constitution(ROOT)), "Phase 0 constitution validation returned no checks")
        print("ALLOW Phase 0 constitution remains valid")
        require(bool(validate_profiles(ROOT)), "Phase 1 profile foundation validation returned no checks")
        print("ALLOW Phase 1 profile foundation remains valid")

        compiled_a = compile_manifest(ROOT, MANIFEST)
        compiled_b = compile_manifest(ROOT, MANIFEST)
        require(compiled_a["compiler_version"] == "1.1.0", "Phase 5 requires human-gated compiler v1.1")
        require(compiled_a["composition_fingerprint"] == compiled_b["composition_fingerprint"], "ContractProof composition is not deterministic")
        require(compiled_a["compilation_fingerprint"] == compiled_b["compilation_fingerprint"], "ContractProof compilation is not deterministic")
        require(all(row["resolution_state"] == "RESOLVED" for row in compiled_a["capability_plan"] if row["required"]), "ContractProof has unresolved required capabilities")
        require(compiled_a["gates"]["planning"]["state"] == "ALLOW", "complete ContractProof planning did not ALLOW")
        require(compiled_a["gates"]["execution"]["state"] == "NEEDS_YOU", "bounded executor must remain human-initiated")
        require(compiled_a["gates"]["human_review"]["state"] == "NEEDS_YOU", "human review boundary drift")
        require(compiled_a["gates"]["external_release"]["state"] == "REFUSE", "internal proof must refuse external release")
        require(compiled_a["maturity"]["state"] == "internal_proof", "ContractProof maturity must be internal_proof")
        flags = compiled_a["maturity"]["operational_flags"]
        require(flags["routable"] and flags["governable"] and flags["executable"], "internal proof operational flags incomplete")
        require(not flags["campaign_enabled"] and not flags["externally_validated"] and not flags["continuous_assurance_ready"] and not flags["revenue_proven"], "internal proof was commercially over-promoted")
        print("ALLOW Product Compiler resolves the complete internal composition with execution NEEDS_YOU, never autonomous ALLOW")

        plan = plan_manifest(ROOT, MANIFEST)
        pattern_states = {row["work_pattern_id"]: row["runtime_state"] for row in plan["patterns"]}
        require(pattern_states == {"WP01": "READY", "WP05": "READY", "WP11": "READY"}, f"ContractProof work-pattern readiness incomplete: {pattern_states}")
        require(plan["planning_gate"]["state"] == "ALLOW", "work-pattern planning did not ALLOW")
        require(plan["execution_gate"]["state"] == "REFUSE", "work-pattern planner itself became executing")
        require(plan["compiler_execution_gate"]["state"] == "NEEDS_YOU", "compiler human execution boundary not propagated")
        require(plan["authority_created"] is False and plan["executor_created"] is False, "work-pattern runtime minted authority/executor")
        require(all(row["human_gate"]["state"] == "NEEDS_YOU" for row in plan["patterns"]), "work-pattern human boundary drift")
        print("ALLOW WP01 Evidence, WP05 Obligation and WP11 Proof are all READY while the planner remains non-executing")

        catalog, _ = load_capability_catalog(ROOT)
        for capability_id in ("evidence.sufficiency", "evidence.gaps"):
            row = catalog[capability_id]
            require(row["status"] == "available", f"evidence capability not earned: {capability_id}")
            require(row["providers"][0]["provider_id"] == "evidence_sufficiency_v1", f"wrong evidence provider: {capability_id}")
            require(row["providers"][0]["execution_capable"] is False, f"evidence capability became execution-capable: {capability_id}")
        room_providers = catalog["proof.room.compile"]["providers"]
        capitalroom = next(row for row in room_providers if row["provider_id"] == "capitalroom_proof_room")
        proof_adapter = next(row for row in room_providers if row["provider_id"] == "contractproof_proof_pack_v1")
        require("dio_contractproof" not in capitalroom["product_scope"], "CapitalRoom scope was broadened")
        require(proof_adapter["product_scope"] == ["dio_contractproof"], "ContractProof proof adapter scope drift")
        for capability_id in ("proof.integrity.verify", "proof.disclosure.prepare"):
            require(catalog[capability_id]["providers"][0]["provider_id"] == "contractproof_proof_pack_v1", f"proof adapter mismatch: {capability_id}")
        executor = catalog["product.executor.contractproof"]
        require(executor["status"] == "available" and len(executor["providers"]) == 1, "bounded ContractProof executor unavailable or ambiguous")
        require(executor["providers"][0]["provider_id"] == EXECUTOR_ID, "wrong ContractProof executor selected")
        require(executor["providers"][0]["product_scope"] == ["dio_contractproof"], "ContractProof executor scope drift")
        require(executor["providers"][0]["execution_capable"] is True, "ContractProof executor is not explicitly execution-capable")
        print("ALLOW evidence is shared, proof is product-scoped, CapitalRoom remains truthful, and the executor is bounded")

        output_rows = compiled_a["output_plan"]["outputs"]
        expected_artifact_types = {str(item) for output in output_rows for item in output.get("artifact_types") or []}
        expected_sections = {str(item) for output in output_rows for item in output.get("required_sections") or []}
        require(expected_artifact_types == set(REQUIRED_ARTIFACT_TYPES), f"output-profile artifact types drift: {expected_artifact_types}")
        require(expected_sections == {
            "requirement_or_obligation_ledger", "evidence_map", "missing_evidence_register",
            "contested_state_register", "deadline_register", "human_review_register", "provenance_manifest",
        }, f"output-profile required sections drift: {expected_sections}")
        print("ALLOW live Evidence Pack profile requires JSON, DOCX, PDF, HTML, proof manifest and all seven semantic sections")

        source = load_json(GOLDEN_ROOT / "reference_contract.json")
        evidence = load_json(GOLDEN_ROOT / "reference_evidence.json")["evidence_records"]
        with tempfile.TemporaryDirectory(prefix="dio-contractproof-phase5-") as temp:
            output_dir = Path(temp) / "proof"
            result = run_contractproof(source, evidence, output_dir=output_dir, operator_id="human.phase5_acceptance_operator", now=NOW, job_id="phase5-golden-acceptance")
            receipt = result["receipt"]
            counts = receipt["obligation_status_counts"]
            expected_counts = {"SATISFIED": 1, "MISSING": 1, "PARTIAL": 1, "EXPIRED": 1, "NOT_YET_DUE": 1, "NEEDS_REVIEW": 1}
            require(counts == expected_counts, f"golden obligation truth drift: {counts}")
            require(receipt["evidence_sufficiency_state"] == "GAPS_PRESENT", "golden case incorrectly claimed evidence sufficiency")
            require(receipt["internal_processing"] == "COMPLETE", "bounded internal processing did not complete")
            require(receipt["proof_integrity_verified"] is True, "proof integrity receipt not verified")
            require(set(receipt["required_artifact_types"]) == expected_artifact_types, "golden artifact profile mismatch")
            require(set(receipt["required_sections"]) == expected_sections, "golden required-section profile mismatch")
            require(receipt["human_fulfilment_gate"] == "NEEDS_YOU" and receipt["human_disclosure_gate"] == "NEEDS_YOU", "human decision boundary lost")
            require(receipt["external_release_gate"] == "REFUSE", "golden proof external release drift")
            require(receipt["authority_created"] is False and receipt["external_effects"] is False and receipt["external_release"] is False, "golden executor claimed forbidden authority/effects")
            verification = verify_integrity(output_dir)
            require(verification["verified"] is True, f"proof pack failed post-run verification: {verification['failures']}")
            proof_manifest = result["proof_manifest"]
            observed_types = {row["artifact_type"] for row in proof_manifest["artifacts"]} | {proof_manifest["artifact_type"]}
            require(observed_types == expected_artifact_types, f"proof manifest artifact type drift: {observed_types}")
            require(set(proof_manifest["required_sections"]) == expected_sections, "proof manifest section coverage drift")
            evidence_pack = load_json(output_dir / "EVIDENCE_PACK.json")
            require(expected_sections.issubset(evidence_pack), "JSON evidence pack omits required semantic sections")
            for filename in ("EVIDENCE_PACK.json", "EVIDENCE_PACK.docx", "EVIDENCE_PACK.pdf", "EVIDENCE_PACK.html", "PROOF_MANIFEST.json"):
                require((output_dir / filename).is_file(), f"required ContractProof output missing: {filename}")
            print("ALLOW golden contract completes end-to-end with mixed truthful states and the exact multi-format Evidence Pack profile")

            pack_path = output_dir / "EVIDENCE_PACK.json"
            pack_payload = load_json(pack_path)
            pack_payload["tampered"] = True
            pack_path.write_text(json.dumps(pack_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            tampered = verify_integrity(output_dir)
            require(tampered["verified"] is False and "hash:JSON" in tampered["failures"], "proof tamper was not detected")
            print("ALLOW proof-pack tampering is detected by hash verification")

        print("ALLOW ContractProof produces internal-proof maturity evidence without claiming fulfilment, legal opinion, waiver or external release")
        print("DIO_CONTRACTPROOF_GOLDEN_READY")
        return 0
    except Exception as exc:
        print(f"DIO_CONTRACTPROOF_GOLDEN_REFUSE: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
