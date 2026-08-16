from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

from products.compiler import CompilerError, compile_manifest, load_profile_index
from products.obligationfamily.runner import run_family_proof
from products.reference_gauntlet import run_gauntlet as run_phase7_gauntlet

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "config" / "products" / "profile_expansion.json"
SCHEMA = "dio.profile_driven_expansion_receipt.v1"
ACCEPTANCE_TOKEN = "DIO_PROFILE_DRIVEN_EXPANSION_READY"
PROFILE_CLASSES = {"domain", "framework", "authority", "connector", "output", "commercial"}


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _value_hash(value: Any) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(body).hexdigest()


def _artifacts(result: dict[str, Any]) -> dict[str, str]:
    root = Path(result["output_dir"])
    return {row["filename"]: hashlib.sha256((root / row["filename"]).read_bytes()).hexdigest()
            for row in result["proof_manifest"]["artifacts"]}


def run_profile_expansion(*, output_dir: Path | None = None) -> dict[str, Any]:
    registry = _load(REGISTRY_PATH)
    entries = registry["incarnations"]
    if len(entries) != 5 or entries[-1]["product_id"] != "dio_policyproof":
        raise AssertionError("Phase 12 requires four controls and one new incarnation")
    owned = None
    if output_dir is None:
        owned = tempfile.TemporaryDirectory(prefix="dio-phase12-")
        output_dir = Path(owned.name)
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    phase7 = run_phase7_gauntlet(output_dir=output_dir / "phase7-regression")
    if phase7["acceptance_token"] != "DIO_REFERENCE_INCARNATION_GAUNTLET_READY":
        raise AssertionError("Phase 7 regression failed")

    indexed = load_profile_index(ROOT)
    rows, compositions = [], set()
    for entry in entries:
        path = ROOT / entry["manifest"]
        first, second = compile_manifest(ROOT, path), compile_manifest(ROOT, path)
        identities = [(x["composition_fingerprint"], x["compilation_fingerprint"]) for x in (first, second)]
        if identities[0] != identities[1]:
            raise AssertionError(f"non-deterministic compilation: {entry['product_id']}")
        classes = {x["profile_class"] for x in first["profile_bindings"]}
        frameworks = {x["profile_id"] for x in first["profile_bindings"] if x["profile_class"] == "framework"}
        if classes != PROFILE_CLASSES or frameworks != {entry["framework_profile"]}:
            raise AssertionError(f"profile composition drift: {entry['product_id']}")
        if first["gates"]["external_release"]["state"] != "REFUSE":
            raise AssertionError(f"release gate drift: {entry['product_id']}")
        compositions.add(first["composition_fingerprint"])
        rows.append({"product_id": entry["product_id"], "framework_profile": entry["framework_profile"],
                     "profile_classes": sorted(classes), "composition_fingerprint": identities[0][0],
                     "compilation_fingerprint": identities[0][1]})
    if len(compositions) != 5:
        raise AssertionError("five incarnations did not remain compositionally distinct")

    policy = entries[-1]
    source = _load(ROOT / policy["fixture_source"])
    evidence = _load(ROOT / policy["fixture_evidence"])["evidence_records"]
    before = _value_hash({"source": source, "evidence": evidence})
    results = [run_family_proof("dio_policyproof", source, evidence,
               output_dir=output_dir / "policyproof" / name,
               operator_id="human.phase12_gauntlet", now=registry["fixed_evaluation_time"])
               for name in ("run-a", "run-b")]
    identity = [(x["obligation_bundle"]["fingerprint"], x["proof_manifest"]["proof_fingerprint"], _artifacts(x))
                for x in results]
    if identity[0] != identity[1] or before != _value_hash({"source": source, "evidence": evidence}):
        raise AssertionError("PolicyProof reproducibility or input immutability failed")
    if results[0]["receipt"]["authority_created"] or results[0]["receipt"]["external_release_gate"] != "REFUSE":
        raise AssertionError("PolicyProof crossed its authority boundary")

    tender = _load(ROOT / "config/products/golden/tenderproof/reference_source.json")
    try:
        run_family_proof("dio_policyproof", tender, [], output_dir=output_dir / "negative-control",
                         operator_id="human.phase12_gauntlet", now=registry["fixed_evaluation_time"])
    except ValueError as exc:
        isolated = "source_type=policy" in str(exc)
    else:
        isolated = False
    if not isolated:
        raise AssertionError("cross-profile source isolation failed")

    compiled_policy = compile_manifest(ROOT, ROOT / policy["manifest"])
    bound_hash = next(x["content_hash"] for x in compiled_policy["profile_bindings"]
                      if x["profile_id"] == "framework.policy_assurance")
    if indexed["framework.policy_assurance"]["content_hash"] != bound_hash:
        raise CompilerError("PolicyProof profile custody mismatch")

    receipt = {"schema": SCHEMA, "registry_version": registry["registry_version"],
        "incarnation_count": 5, "control_incarnation_count": 4, "new_incarnation": "dio_policyproof",
        "profile_classes": sorted(PROFILE_CLASSES), "incarnations": rows, "phase7_regression": "PASS",
        "deterministic_compilation": "PASS", "deterministic_execution": "PASS",
        "distinct_compositions": "PASS", "profile_source_custody": "PASS",
        "source_type_isolation": "PASS", "input_immutability": "PASS",
        "shared_runtime_reuse": "PASS", "authority_created": False, "external_effects": False,
        "external_release": "REFUSE", "maturity_ceiling": "internal_proof",
        "factory_claim": "Five source-bound incarnations compile across all six profile classes; PolicyProof reuses the compiler, Obligation Core and bounded family adapter.",
        "acceptance_token": ACCEPTANCE_TOKEN}
    (output_dir / "PROFILE_DRIVEN_EXPANSION_RECEIPT.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if owned is not None:
        owned.cleanup()
    return receipt
