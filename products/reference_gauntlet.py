from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

from products.compiler import compile_manifest, load_capability_catalog
from products.contractproof.proof import verify_integrity
from products.contractproof.runner import run_contractproof
from products.obligationfamily.runner import FAMILY_DEFINITIONS, run_family_proof
from products.work_pattern_runtime import plan_manifest


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "config" / "products" / "reference_incarnations.json"
SCHEMA = "dio.reference_incarnation_gauntlet_receipt.v1"
ACCEPTANCE_TOKEN = "DIO_REFERENCE_INCARNATION_GAUNTLET_READY"


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _artifact_hashes(output_dir: Path, proof: dict[str, Any]) -> dict[str, str]:
    return {row["artifact_type"]: _sha(output_dir / row["filename"]) for row in proof["artifacts"]}


def _run(entry: dict[str, Any], output_dir: Path, now: str) -> dict[str, Any]:
    source = _load(ROOT / entry["fixture_source"])
    evidence = _load(ROOT / entry["fixture_evidence"])["evidence_records"]
    if source.get("source_type") != entry["source_type"]:
        raise AssertionError(f"registry source-type mismatch for {entry['product_id']}")
    if entry["runner"] == "contractproof":
        return run_contractproof(source, evidence, output_dir=output_dir, operator_id="human.phase7_gauntlet", now=now, job_id=f"phase7-{entry['slug']}")
    return run_family_proof(entry["product_id"], source, evidence, output_dir=output_dir, operator_id="human.phase7_gauntlet", now=now, job_id=f"phase7-{entry['slug']}")


def _assert_provider_isolation(entries: list[dict[str, Any]]) -> None:
    catalog, _ = load_capability_catalog(ROOT)
    products = {entry["product_id"] for entry in entries}
    for entry in entries:
        cap = catalog[f"product.executor.{entry['slug']}"]
        scopes = {scope for provider in cap["providers"] for scope in provider["product_scope"]}
        if scopes != {entry["product_id"]}:
            raise AssertionError(f"executor scope leaked for {entry['product_id']}: {sorted(scopes)}")
    family_scope = set(FAMILY_DEFINITIONS)
    if family_scope != products.difference({"dio_contractproof"}):
        raise AssertionError("family runner and reference registry disagree")


def run_gauntlet(*, output_dir: Path | None = None) -> dict[str, Any]:
    registry = _load(REGISTRY_PATH)
    entries = registry["incarnations"]
    if len(entries) != 4 or len({row["product_id"] for row in entries}) != 4:
        raise AssertionError("reference gauntlet requires exactly four unique incarnations")
    before = {path: _sha(ROOT / path) for path in registry["shared_core_guard"]}
    if before != registry["shared_core_guard"]:
        raise AssertionError("shared Obligation Core drifted from the Phase 7 registry baseline")
    _assert_provider_isolation(entries)
    owned_temp = None
    if output_dir is None:
        owned_temp = tempfile.TemporaryDirectory(prefix="dio-phase7-")
        output_dir = Path(owned_temp.name)
    output_dir = output_dir.resolve(); output_dir.mkdir(parents=True, exist_ok=True)
    results = []
    composition_fingerprints = set()
    for entry in entries:
        manifest = ROOT / entry["manifest"]
        compiled_a = compile_manifest(ROOT, manifest)
        compiled_b = compile_manifest(ROOT, manifest)
        if compiled_a["composition_fingerprint"] != compiled_b["composition_fingerprint"] or compiled_a["compilation_fingerprint"] != compiled_b["compilation_fingerprint"]:
            raise AssertionError(f"non-deterministic compilation for {entry['product_id']}")
        composition_fingerprints.add(compiled_a["composition_fingerprint"])
        gates = compiled_a["gates"]
        if (gates["planning"]["state"], gates["execution"]["state"], gates["human_review"]["state"], gates["external_release"]["state"]) != ("ALLOW", "NEEDS_YOU", "NEEDS_YOU", "REFUSE"):
            raise AssertionError(f"authority gate drift for {entry['product_id']}")
        plan = plan_manifest(ROOT, manifest)
        if {row["work_pattern_id"]: row["runtime_state"] for row in plan["patterns"]} != {"WP01": "READY", "WP05": "READY", "WP11": "READY"} or plan["execution_gate"]["state"] != "REFUSE":
            raise AssertionError(f"work-pattern readiness drift for {entry['product_id']}")
        first = _run(entry, output_dir / entry["slug"] / "run-a", registry["fixed_evaluation_time"])
        second = _run(entry, output_dir / entry["slug"] / "run-b", registry["fixed_evaluation_time"])
        for run in (first, second):
            receipt = run["receipt"]
            if receipt["external_release_gate"] != "REFUSE" or receipt["authority_created"] is not False or receipt["external_effects"] is not False:
                raise AssertionError(f"execution boundary drift for {entry['product_id']}")
        semantic_a = first["obligation_bundle"]["fingerprint"]
        semantic_b = second["obligation_bundle"]["fingerprint"]
        proof_a = first["proof_manifest"]["proof_fingerprint"]
        proof_b = second["proof_manifest"]["proof_fingerprint"]
        artifacts_a = _artifact_hashes(Path(first["output_dir"]), first["proof_manifest"])
        artifacts_b = _artifact_hashes(Path(second["output_dir"]), second["proof_manifest"])
        if (semantic_a, proof_a, artifacts_a) != (semantic_b, proof_b, artifacts_b):
            raise AssertionError(f"non-reproducible reference proof for {entry['product_id']}")
        if entry["runner"] == "contractproof" and not verify_integrity(Path(first["output_dir"]))["verified"]:
            raise AssertionError("ContractProof integrity verification failed")
        counts = first["receipt"]["obligation_status_counts"]
        if not any(state in counts for state in ("MISSING", "PARTIAL", "EXPIRED", "NEEDS_REVIEW")):
            raise AssertionError(f"golden fixture erased inconvenient truth for {entry['product_id']}")
        results.append({"product_id": entry["product_id"], "source_type": entry["source_type"], "composition_fingerprint": compiled_a["composition_fingerprint"], "compilation_fingerprint": compiled_a["compilation_fingerprint"], "obligation_bundle_fingerprint": semantic_a, "proof_fingerprint": proof_a, "artifact_hashes": artifacts_a, "obligation_status_counts": counts, "gates": {key: value["state"] for key, value in gates.items()}, "reproducible": True, "mixed_truth_preserved": True})
    if len(composition_fingerprints) != len(entries):
        raise AssertionError("reference incarnations collapsed to indistinguishable compositions")
    # Cross-incarnation negative control: a tender source must never enter GrantProof.
    tender = next(row for row in entries if row["source_type"] == "tender")
    try:
        run_family_proof("dio_grantproof", _load(ROOT / tender["fixture_source"]), [], output_dir=output_dir / "negative-control", operator_id="human.phase7_gauntlet", now=registry["fixed_evaluation_time"])
    except ValueError as exc:
        source_type_isolation = "source_type=grant" in str(exc)
    else:
        source_type_isolation = False
    if not source_type_isolation:
        raise AssertionError("cross-incarnation source-type negative control did not refuse")
    after = {path: _sha(ROOT / path) for path in registry["shared_core_guard"]}
    if after != before:
        raise AssertionError("reference execution mutated shared Obligation Core")
    receipt = {"schema": SCHEMA, "registry_version": registry["registry_version"], "fixed_evaluation_time": registry["fixed_evaluation_time"], "incarnation_count": len(results), "incarnations": results, "provider_isolation": "PASS", "source_type_isolation": "PASS", "shared_core_integrity": "PASS", "shared_core_hashes": after, "deterministic_compilation": "PASS", "deterministic_execution": "PASS", "authority_boundary": "PASS", "external_release": "REFUSE", "factory_claim": "Four independently composed reference incarnations reuse one unchanged Obligation Core and reproduce their semantic and proof identities under fixed canonical inputs.", "maturity_ceiling": "internal_proof", "acceptance_token": ACCEPTANCE_TOKEN}
    (output_dir / "REFERENCE_INCARNATION_GAUNTLET_RECEIPT.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if owned_temp is not None:
        owned_temp.cleanup()
    return receipt
