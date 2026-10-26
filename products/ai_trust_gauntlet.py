from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

from products.ai_trust.runner import EXECUTOR_ID, PRODUCTS, run_ai_trust
from products.compiler import compile_manifest, load_capability_catalog
from products.profile_expansion import run_profile_expansion

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "config/products/ai_digital_trust.json"
ACCEPTANCE_TOKEN = "DIO_AI_DIGITAL_TRUST_READY"
SCHEMA = "dio.ai_digital_trust_gauntlet_receipt.v1"
PROFILE_CLASSES = {"domain", "framework", "authority", "connector", "output", "commercial"}


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _value_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def _artifacts(result: dict[str, Any]) -> dict[str, str]:
    root = Path(result["output_dir"])
    return {row["filename"]: hashlib.sha256((root / row["filename"]).read_bytes()).hexdigest()
            for row in result["proof_manifest"]["artifacts"]}


def _states(envelope: dict[str, Any]) -> dict[str, str]:
    return {row["dimension"]: row["state"] for row in envelope["dimensions"]}


def run_gauntlet(*, output_dir: Path | None = None) -> dict[str, Any]:
    registry = _load(REGISTRY_PATH)
    entries = registry["incarnations"]
    if len(entries) != 3 or set(PRODUCTS) != {row["product_id"] for row in entries}:
        raise AssertionError("Phase 13 requires exactly three registered AI Trust incarnations")
    owned = None
    if output_dir is None:
        owned = tempfile.TemporaryDirectory(prefix="dio-phase13-")
        output_dir = Path(owned.name)
    output_dir = output_dir.resolve(); output_dir.mkdir(parents=True, exist_ok=True)

    phase12 = run_profile_expansion(output_dir=output_dir / "phase12-regression")
    if phase12["acceptance_token"] != "DIO_PROFILE_DRIVEN_EXPANSION_READY":
        raise AssertionError("Phase 12 regression failed")

    catalog, _ = load_capability_catalog(ROOT)
    compositions, results = set(), []
    for entry in entries:
        manifest = ROOT / entry["manifest"]
        compiled_a, compiled_b = compile_manifest(ROOT, manifest), compile_manifest(ROOT, manifest)
        if (compiled_a["composition_fingerprint"], compiled_a["compilation_fingerprint"]) != (
            compiled_b["composition_fingerprint"], compiled_b["compilation_fingerprint"]
        ):
            raise AssertionError(f"non-deterministic compilation: {entry['product_id']}")
        if {row["profile_class"] for row in compiled_a["profile_bindings"]} != PROFILE_CLASSES:
            raise AssertionError(f"incomplete profile axes: {entry['product_id']}")
        if compiled_a["gates"]["execution"]["state"] != "NEEDS_YOU" or compiled_a["gates"]["external_release"]["state"] != "REFUSE":
            raise AssertionError(f"authority boundary drift: {entry['product_id']}")
        compositions.add(compiled_a["composition_fingerprint"])

        cap = catalog[f"product.executor.{entry['slug']}"]
        scopes = {scope for provider in cap["providers"] for scope in provider["product_scope"]}
        if scopes != {entry["product_id"]} or cap["providers"][0]["provider_id"] != EXECUTOR_ID:
            raise AssertionError(f"executor scope leaked: {entry['product_id']}")

        payload = _load(ROOT / entry["fixture"])
        before = _value_hash(payload)
        first = run_ai_trust(entry["product_id"], payload, output_dir=output_dir / entry["slug"] / "run-a",
                             operator_id="human.phase13_gauntlet", now=registry["fixed_evaluation_time"])
        second = run_ai_trust(entry["product_id"], payload, output_dir=output_dir / entry["slug"] / "run-b",
                              operator_id="human.phase13_gauntlet", now=registry["fixed_evaluation_time"])
        if before != _value_hash(payload):
            raise AssertionError(f"input mutation: {entry['product_id']}")
        identities = [(x["envelope"]["envelope_fingerprint"], x["proof_manifest"]["proof_fingerprint"], _artifacts(x))
                      for x in (first, second)]
        if identities[0] != identities[1]:
            raise AssertionError(f"non-deterministic AI Trust proof: {entry['product_id']}")
        if first["receipt"]["external_release_gate"] != "REFUSE" or first["receipt"]["authority_created"]:
            raise AssertionError(f"unsafe AI Trust receipt: {entry['product_id']}")
        results.append({"product_id": entry["product_id"],
                        "composition_fingerprint": compiled_a["composition_fingerprint"],
                        "envelope_fingerprint": first["envelope"]["envelope_fingerprint"],
                        "proof_fingerprint": first["proof_manifest"]["proof_fingerprint"],
                        "states": _states(first["envelope"]),
                        "prompt_injection_signal_count": len(first["envelope"]["prompt_injection_signals"]),
                        "drift_event_count": len(first["envelope"]["drift_events"]),
                        "artifact_hashes": _artifacts(first)})
    if len(compositions) != 3:
        raise AssertionError("AI Trust incarnations collapsed into indistinguishable compositions")

    by_id = {row["product_id"]: row for row in results}
    trust = by_id["dio_aitrustproof"]["states"]
    if trust["identity"] != "SUPPORTED" or trust["evaluation"] != "SUPPORTED" or trust["authority"] != "NEEDS_YOU" or trust["release"] != "REFUSE":
        raise AssertionError("AITrustProof did not preserve independent states")
    agent = by_id["dio_agentauthority"]
    if agent["states"]["tool_safety"] != "REFUSE" or agent["prompt_injection_signal_count"] < 2:
        raise AssertionError("AgentAuthority did not refuse poisoned tool escalation")
    change = by_id["dio_modelchangeproof"]
    if change["states"]["evaluation"] != "STALE" or change["states"]["drift"] != "CONTESTED" or change["states"]["integrity"] != "CONTESTED":
        raise AssertionError("ModelChangeProof erased stale, drift or integrity truth")

    wrong = _load(ROOT / entries[0]["fixture"])
    try:
        run_ai_trust("dio_agentauthority", wrong, output_dir=output_dir / "negative-control",
                     operator_id="human.phase13_gauntlet", now=registry["fixed_evaluation_time"])
    except ValueError as exc:
        isolated = "source_type=ai_agent" in str(exc)
    else:
        isolated = False
    if not isolated:
        raise AssertionError("cross-incarnation source isolation failed")

    receipt = {"schema": SCHEMA, "registry_version": registry["registry_version"],
               "incarnation_count": 3, "incarnations": results, "phase12_regression": "PASS",
               "deterministic_compilation": "PASS", "deterministic_execution": "PASS",
               "profile_source_custody": "PASS", "provider_isolation": "PASS",
               "source_type_isolation": "PASS", "prompt_injection_boundary": "PASS",
               "model_drift_detection": "PASS", "stale_evaluation_detection": "PASS",
               "artifact_integrity": "PASS", "input_immutability": "PASS",
               "human_gate": "NEEDS_YOU", "external_release": "REFUSE",
               "authority_created": False, "external_effects": False,
               "maturity_ceiling": "internal_proof",
               "acceptance_token": ACCEPTANCE_TOKEN}
    (output_dir / "AI_DIGITAL_TRUST_GAUNTLET_RECEIPT.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if owned is not None: owned.cleanup()
    return receipt
