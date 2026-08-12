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
            {"clause_id": "4.2", "text": "Supplier shall provide the monthly service report.", "obligation": True, "obligation_kind": "reporting", "responsible_party": "supplier", "due_at": "2026-09-01T12:00:00+00:00", "evidence_requirements": ["delivery_receipt"]},
            {"clause_id": "5.1", "text": "Customer shall pay the accepted invoice.", "obligation": True, "obligation_kind": "payment", "responsible_party": "customer", "due_at": "2026-08-01T12:00:00+00:00", "evidence_requirements": ["payment_receipt"]},
            {"clause_id": "9.2", "text": "Supplier must notify the owner of a material service interruption.", "obligation_kind": "notification", "responsible_party": "supplier", "evidence_requirements": ["incident_notice"]},
            {"clause_id": "10.1", "text": "Supplier should cooperate where practical.", "obligation_kind": "other"},
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
        for law, value in config["laws"].items():
            if law.endswith("required") or law.endswith("forbidden") or law.startswith("semantic_auto_match") or law in {
                "structured_obligations_are_candidates_not_authority",
                "deontic_candidates_require_human_review",
                "evidence_binding_is_explicit",
                "legal_opinion_is_forbidden",
                "compliance_verdict_is_forbidden",
                "authority_creation_is_forbidden",
                "executor_creation_is_forbidden",
                "external_effects_are_forbidden",
            }:
                require(value is True, f"Obligation Core law drift: {law}")
        require(set(config["capabilities"]) == set(CAPABILITY_BINDINGS), "Obligation Core capability binding drift")
        print("ALLOW Obligation Core laws and seven-state vocabulary remain frozen")

        source = reference_source()
        candidates = extract(source)
        by_locator = {row["source_locator"]: row for row in candidates}
        require("10.1" not in by_locator, "weak 'should' clause was promoted into obligation candidate")
        require(by_locator["9.2"]["review_required"] is True, "deontic candidate escaped human review")
        print("ALLOW source-bound extraction remains conservative")

        evidence = [{"evidence_id": "EVID-PHASE4-REPORT", "obligation_ids": [by_locator["4.2"]["obligation_id"]], "evidence_kind": "delivery_receipt", "source_ref": "evidence://phase4-report", "trust_state": "trusted_for_review", "freshness_state": "current"}]
        bundle_a = build(source, evidence_records=evidence, now=NOW)
        bundle_b = build(source, evidence_records=evidence, now=NOW)
        require(bundle_a["fingerprint"] == bundle_b["fingerprint"], "same obligation inputs did not reproduce fingerprint")
        status = {row["source"]["locator"]: row["status"] for row in bundle_a["obligations"]}
        require(status["4.2"] == "SATISFIED" and status["5.1"] == "MISSING" and status["9.2"] == "NEEDS_REVIEW", "bounded evaluation state drift")
        require(bundle_a["human_gate"]["state"] == "NEEDS_YOU", "human fulfilment boundary lost")
        require(bundle_a["authority_created"] is False and bundle_a["executor_created"] is False and bundle_a["external_effects"] is False, "Obligation Core created authority/executor/effect")
        print("ALLOW deterministic evaluation remains bounded and non-authoritative")

        forbidden = copy.deepcopy(bundle_a)
        forbidden["obligations"][0]["compliant"] = True
        try:
            validate_bundle(forbidden)
        except ValueError as exc:
            require("schema validation failed" in str(exc), "compliance field refusal reason drift")
        else:
            raise AcceptanceError("Obligation Core schema accepted compliance verdict leakage")
        print("ALLOW schema refuses compliance-verdict leakage")

        catalog, _ = load_capability_catalog(ROOT)
        provider_ids: set[str] = set()
        for capability_id in CAPABILITY_BINDINGS:
            row = catalog[capability_id]
            require(row["status"] == "available", f"earned obligation capability unavailable: {capability_id}")
            require(len(row["providers"]) == 1, f"obligation capability provider ambiguity: {capability_id}")
            provider = row["providers"][0]
            provider_ids.add(provider["provider_id"])
            require(provider["ref"] == "dio/obligations/engine.py", f"obligation provider ref drift: {capability_id}")
            require(provider["product_scope"] == ["*"], f"Obligation Core lost generic scope: {capability_id}")
            require(provider["execution_capable"] is False, f"Obligation Core became execution-capable: {capability_id}")
        require(provider_ids == {"obligation_core_v1"}, "obligation capabilities no longer share one provider")
        print("ALLOW four Obligation capabilities remain one shared non-executing provider")

        manifest = ROOT / "config" / "products" / "manifests" / "contractproof.json"
        compiled = compile_manifest(ROOT, manifest)
        capabilities = {row["capability_id"]: row for row in compiled["capability_plan"]}
        for capability_id in CAPABILITY_BINDINGS:
            require(capabilities[capability_id]["resolution_state"] == "RESOLVED", f"ContractProof failed to resolve {capability_id}")
            require(capabilities[capability_id]["provider"]["provider_id"] == "obligation_core_v1", f"wrong obligation provider for {capability_id}")
        executor = capabilities.get("product.executor.contractproof") or {}
        if executor.get("resolution_state") == "RESOLVED":
            require(executor["provider"]["provider_id"] != "obligation_core_v1", "Obligation Core was confused with vertical executor")
        require(compiled["gates"]["execution"]["state"] in {"REFUSE", "NEEDS_YOU"}, "product execution became autonomous")
        require(compiled["gates"]["external_release"]["state"] == "REFUSE", "external release boundary drift")
        print("ALLOW Product Compiler reuses Obligation Core without turning it into a vertical executor")

        plan = plan_manifest(ROOT, manifest)
        patterns = {row["work_pattern_id"]: row for row in plan["patterns"]}
        require(patterns["WP05"]["runtime_state"] == "READY", "Obligation work pattern lost READY state")
        require(plan["execution_gate"]["state"] == "REFUSE", "work-pattern planner became executing")
        require(all(row["human_gate"]["state"] == "NEEDS_YOU" for row in plan["patterns"]), "human work-pattern boundary drift")
        print("ALLOW WP05 remains READY while later product phases cannot relax work-pattern authority")

        case = new_case(product="dio_contractproof", job_id="phase4-acceptance-projection", source={"source": {}}, source_path=ROOT / "tests" / "phase4-reference.json", evidence_inputs=[], expected_outputs=["evidence_pack"], required_authorities=["human.contract_owner"], intake_state="approved", now=NOW)
        case_evidence = add_evidence(case, kind="delivery_receipt", source_ref="evidence://phase4-report", trust_state="trusted_for_review", freshness_state="current")
        projection_bundle = build(source, evidence_records=[{"evidence_id": case_evidence["evidence_id"], "obligation_ids": [by_locator["4.2"]["obligation_id"]], "evidence_kind": "delivery_receipt", "source_ref": case_evidence["source_ref"], "trust_state": "trusted_for_review", "freshness_state": "current"}], now=NOW)
        before = json.dumps({key: case[key] for key in ("gates", "actions", "decisions")}, sort_keys=True)
        receipt = project(projection_bundle, case)
        after = json.dumps({key: case[key] for key in ("gates", "actions", "decisions")}, sort_keys=True)
        require(before == after, "Obligation projection mutated authority surfaces")
        require(receipt["authority_created"] is False and receipt["execution_performed"] is False, "projection claims authority/execution")
        print("ALLOW Governed Case projection preserves gates, actions and decisions byte-for-byte")
        print("DIO_OBLIGATION_ENGINE_READY")
        return 0
    except Exception as exc:
        print(f"DIO_OBLIGATION_ENGINE_REFUSE: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
