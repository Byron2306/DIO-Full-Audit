from __future__ import annotations

import copy
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from dio.obligations.engine import CAPABILITY_BINDINGS, build, project, validate_bundle
from dio.obligations.extractor import extract
from dio.obligations.models import CANONICAL_STATES, RESERVED_VERDICTS
from products.compiler import compile_manifest, load_capability_catalog, load_json
from products.governed_case import add_evidence, new_case
from products.work_pattern_runtime import plan_manifest
from validate_product_constitution import validate as validate_constitution
from validate_profiles import validate as validate_profiles


NOW = "2026-08-12T12:00:00+00:00"


class AcceptanceError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AcceptanceError(message)


def reference_source() -> dict:
    return {
        "source_id": "phase4-reference-contract",
        "source_type": "contract",
        "source_ref": "contract://phase4-reference",
        "sha256": "c" * 64,
        "effective_at": "2026-07-01T00:00:00+00:00",
        "expires_at": None,
        "clauses": [
            {
                "clause_id": "4.2",
                "text": "Supplier shall provide the monthly service report.",
                "obligation": True,
                "obligation_kind": "reporting",
                "responsible_party": "supplier",
                "due_at": "2026-09-01T12:00:00+00:00",
                "evidence_requirements": ["delivery_receipt"],
            },
            {
                "clause_id": "5.1",
                "text": "Customer shall pay the accepted invoice.",
                "obligation": True,
                "obligation_kind": "payment",
                "responsible_party": "customer",
                "due_at": "2026-08-01T12:00:00+00:00",
                "evidence_requirements": ["payment_receipt"],
            },
            {
                "clause_id": "9.2",
                "text": "Supplier must notify the owner of a material service interruption.",
                "obligation_kind": "notification",
                "responsible_party": "supplier",
                "evidence_requirements": ["incident_notice"],
            },
            {
                "clause_id": "10.1",
                "text": "Supplier should cooperate where practical.",
                "obligation_kind": "other",
            },
        ],
    }


def main() -> int:
    try:
        require(bool(validate_constitution(ROOT)), "Phase 0 constitution validation returned no checks")
        print("ALLOW Phase 0 constitution remains valid")
        require(bool(validate_profiles(ROOT)), "Phase 1 profile validation returned no checks")
        print("ALLOW Phase 1 profile foundation remains valid")

        config = load_json(ROOT / "config" / "portfolio" / "obligation_engine.json")
        require(config["schema"] == "dio.obligation_engine.config.v1", "unexpected Obligation Core config schema")
        require(config["engine_version"] == "0.1.0", "unexpected Obligation Core version")
        require(set(config["canonical_states"]) == CANONICAL_STATES, "canonical obligation state vocabulary drift")
        require(set(config["reserved_authority_or_legal_verdicts"]) == RESERVED_VERDICTS, "reserved verdict vocabulary drift")
        laws = config["laws"]
        for law in (
            "source_binding_required",
            "structured_obligations_are_candidates_not_authority",
            "deontic_candidates_require_human_review",
            "evidence_binding_is_explicit",
            "semantic_auto_match_is_forbidden_v0_1",
            "legal_opinion_is_forbidden",
            "compliance_verdict_is_forbidden",
            "authority_creation_is_forbidden",
            "executor_creation_is_forbidden",
            "external_effects_are_forbidden",
            "human_fulfilment_boundary_required",
        ):
            require(laws[law] is True, f"Obligation Core law drift: {law}")
        require(set(config["capabilities"]) == set(CAPABILITY_BINDINGS), "Obligation Core capability binding drift")
        print("ALLOW Obligation Core laws and seven-state vocabulary are frozen")

        source = reference_source()
        candidates = extract(source)
        by_locator = {row["source_locator"]: row for row in candidates}
        require("10.1" not in by_locator, "weak 'should' clause was promoted into an obligation candidate")
        require(by_locator["9.2"]["review_required"] is True, "deontic candidate escaped human review")
        require(by_locator["4.2"]["extraction_basis"] == "explicit_structured_obligation", "explicit structured extraction basis drift")
        print("ALLOW source-bound extraction is conservative and deontic candidates stay NEEDS_REVIEW")

        evidence = [
            {
                "evidence_id": "EVID-PHASE4-REPORT",
                "obligation_ids": [by_locator["4.2"]["obligation_id"]],
                "evidence_kind": "delivery_receipt",
                "source_ref": "evidence://phase4-report",
                "trust_state": "trusted_for_review",
                "freshness_state": "current",
            }
        ]
        bundle_a = build(source, evidence_records=evidence, now=NOW)
        bundle_b = build(source, evidence_records=evidence, now=NOW)
        require(bundle_a["fingerprint"] == bundle_b["fingerprint"], "same obligation inputs did not reproduce the same fingerprint")
        status = {row["source"]["locator"]: row["status"] for row in bundle_a["obligations"]}
        require(status["4.2"] == "SATISFIED", "trusted explicit evidence did not satisfy bounded evidence requirements")
        require(status["5.1"] == "MISSING", "overdue missing evidence did not remain visible")
        require(status["9.2"] == "NEEDS_REVIEW", "heuristic deontic candidate was allowed to self-adjudicate")
        require(bundle_a["human_gate"]["state"] == "NEEDS_YOU", "human fulfilment boundary lost")
        require(bundle_a["authority_created"] is False and bundle_a["executor_created"] is False and bundle_a["external_effects"] is False, "Obligation Core created authority/executor/effect")
        print("ALLOW deterministic evaluation emits bounded evidence states without authority")

        forbidden = copy.deepcopy(bundle_a)
        forbidden["obligations"][0]["compliant"] = True
        try:
            validate_bundle(forbidden)
        except ValueError as exc:
            require("schema validation failed" in str(exc), "reserved compliance field refusal reason drift")
        else:
            raise AcceptanceError("Obligation Core schema accepted a compliance verdict field")
        print("ALLOW schema refuses compliance-verdict leakage")

        catalog, _ = load_capability_catalog(ROOT)
        provider_ids: set[str] = set()
        for capability_id in CAPABILITY_BINDINGS:
            row = catalog[capability_id]
            require(row["status"] == "available", f"earned obligation capability not available: {capability_id}")
            require(len(row["providers"]) == 1, f"obligation capability provider ambiguity: {capability_id}")
            provider = row["providers"][0]
            provider_ids.add(provider["provider_id"])
            require(provider["ref"] == "dio/obligations/engine.py", f"obligation provider ref drift: {capability_id}")
            require(provider["product_scope"] == ["*"], f"Obligation Core is not declared reusable: {capability_id}")
            require(provider["execution_capable"] is False, f"Obligation Core capability became execution-capable: {capability_id}")
        require(provider_ids == {"obligation_core_v1"}, "four obligation capabilities must resolve through one shared provider")
        require(catalog["product.executor.contractproof"]["status"] == "planned", "ContractProof executor was smuggled into Phase 4")
        print("ALLOW four Obligation capabilities are earned through one shared non-executing provider")

        manifest = ROOT / "config" / "products" / "manifests" / "contractproof.json"
        compiled = compile_manifest(ROOT, manifest)
        capabilities = {row["capability_id"]: row for row in compiled["capability_plan"]}
        for capability_id in CAPABILITY_BINDINGS:
            require(capabilities[capability_id]["resolution_state"] == "RESOLVED", f"ContractProof failed to resolve {capability_id}")
            require(capabilities[capability_id]["provider"]["provider_id"] == "obligation_core_v1", f"ContractProof resolved wrong obligation provider for {capability_id}")
        require(capabilities["proof.room.compile"]["resolution_state"] == "UNAVAILABLE", "CapitalRoom scope was silently broadened to ContractProof")
        require(capabilities["product.executor.contractproof"]["resolution_state"] == "PLANNED", "ContractProof executor should remain unearned")
        require(compiled["gates"]["planning"]["state"] == "NEEDS_IMPLEMENTATION", "ContractProof planning gate should remain incomplete outside WP05")
        require(compiled["gates"]["execution"]["state"] == "REFUSE", "ContractProof execution refusal was relaxed")
        require(compiled["gates"]["external_release"]["state"] == "REFUSE", "ContractProof external-release refusal was relaxed")
        print("ALLOW Product Compiler earns WP05 capability without inventing ContractProof execution")

        plan = plan_manifest(ROOT, manifest)
        patterns = {row["work_pattern_id"]: row for row in plan["patterns"]}
        require(patterns["WP05"]["runtime_state"] == "READY", "Obligation work pattern did not become READY")
        require(patterns["WP11"]["runtime_state"] == "BLOCKED", "Proof work pattern should remain blocked for ContractProof")
        require(plan["planning_gate"]["state"] == "NEEDS_IMPLEMENTATION", "overall planning gate should still expose remaining frontier")
        require(plan["execution_gate"]["state"] == "REFUSE" and plan["compiler_execution_gate"]["state"] == "REFUSE", "work-pattern runtime relaxed execution")
        require(all(row["human_gate"]["state"] == "NEEDS_YOU" for row in plan["patterns"]), "human work-pattern boundary drift")
        print("ALLOW WP05 is READY while proof, execution and human authority boundaries remain intact")

        case = new_case(
            product="dio_contractproof",
            job_id="phase4-acceptance-projection",
            source={"source": {}},
            source_path=ROOT / "tests" / "phase4-reference.json",
            evidence_inputs=[],
            expected_outputs=["evidence_pack"],
            required_authorities=["human.contract_owner"],
            intake_state="approved",
        )
        case_evidence = add_evidence(
            case,
            kind="delivery_receipt",
            source_ref="evidence://phase4-report",
            trust_state="trusted_for_review",
            freshness_state="current",
        )
        projection_bundle = build(
            source,
            evidence_records=[
                {
                    "evidence_id": case_evidence["evidence_id"],
                    "obligation_ids": [by_locator["4.2"]["obligation_id"]],
                    "evidence_kind": "delivery_receipt",
                    "source_ref": case_evidence["source_ref"],
                    "trust_state": "trusted_for_review",
                    "freshness_state": "current",
                }
            ],
            now=NOW,
        )
        authority_before = json.dumps({key: case[key] for key in ("gates", "actions", "decisions")}, sort_keys=True)
        receipt = project(projection_bundle, case)
        authority_after = json.dumps({key: case[key] for key in ("gates", "actions", "decisions")}, sort_keys=True)
        require(authority_before == authority_after, "Obligation projection mutated Governed Case authority surfaces")
        require(receipt["authority_created"] is False and receipt["execution_performed"] is False and receipt["external_release"] is False, "projection receipt claims authority/effect")
        require(len(receipt["requirement_map"]) == len(projection_bundle["obligations"]), "not all obligations projected into Governed Case requirements")
        print("ALLOW Governed Case projection preserves gates, actions and decisions byte-for-byte")

        print("DIO_OBLIGATION_ENGINE_READY")
        return 0
    except Exception as exc:
        print(f"DIO_OBLIGATION_ENGINE_REFUSE: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
