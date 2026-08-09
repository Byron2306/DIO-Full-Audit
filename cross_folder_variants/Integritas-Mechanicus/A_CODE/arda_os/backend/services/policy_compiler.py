import hashlib
import hmac
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

from backend.services.policy_engine import POLICY_PATH, load_and_verify_policy


POLICY_BUNDLE_SCHEMA = "arda.policy_bundle.v1"
POLICY_BUNDLE_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "arda_policy_bundle.json")
)

_POLICY_BUNDLE_SECRET = os.getenv(
    "ARDA_POLICY_SECRET", "ARDA-POLICY-SIGNING-SECRET-REPLACE-IN-PRODUCTION"
).encode()


def _canonical_bundle_bytes(bundle: Dict[str, Any]) -> bytes:
    clean = {key: value for key, value in bundle.items() if key != "signature"}
    return json.dumps(clean, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sign_bundle(bundle: Dict[str, Any]) -> str:
    return hmac.new(_POLICY_BUNDLE_SECRET, _canonical_bundle_bytes(bundle), hashlib.sha3_256).hexdigest()


def _normalize_command_rules(commands: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for rule in commands:
        normalized.append(
            {
                "command": rule["name"],
                "principals": sorted(set(rule.get("principals", []))),
                "lanes": sorted(set(rule.get("lanes", []))),
                "effect": rule.get("effect", "ALLOW"),
            }
        )
    return sorted(normalized, key=lambda item: item["command"])


def _normalize_legacy_rules(rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for rule in rules:
        command = rule.get("command")
        principal = rule.get("principal")
        lane = rule.get("lane")
        if not command or not principal or not lane:
            continue
        normalized.append(
            {
                "command": command,
                "principals": [principal],
                "lanes": [lane],
                "effect": rule.get("verdict", "ALLOW"),
            }
        )
    return sorted(normalized, key=lambda item: item["command"])


def _normalize_redline_rules(redline_rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for index, rule in enumerate(redline_rules or []):
        normalized.append(
            {
                "rule_id": rule.get("rule_id", f"redline-{index + 1}"),
                "command": rule.get("command"),
                "principal": rule.get("principal"),
                "lane": rule.get("lane"),
                "reason": rule.get("reason", "constitutional_redline"),
                "effect": "DENY",
            }
        )
    return sorted(normalized, key=lambda item: item["rule_id"])


def compile_policy_bundle(policy: Dict[str, Any]) -> Dict[str, Any]:
    normalized_commands = _normalize_command_rules(policy.get("commands", []))
    if not normalized_commands and policy.get("rules"):
        normalized_commands = _normalize_legacy_rules(policy.get("rules", []))
    normalized_redline_rules = _normalize_redline_rules(policy.get("redline_rules", []))
    command_index = {rule["command"]: rule for rule in normalized_commands}

    principal_bindings: Dict[str, List[str]] = {}
    lane_bindings: Dict[str, List[str]] = {}
    for rule in normalized_commands:
        for principal in rule["principals"]:
            principal_bindings.setdefault(principal, []).append(rule["command"])
        for lane in rule["lanes"]:
            lane_bindings.setdefault(lane, []).append(rule["command"])

    principal_bindings = {
        principal: sorted(set(commands))
        for principal, commands in sorted(principal_bindings.items())
    }
    lane_bindings = {
        lane: sorted(set(commands))
        for lane, commands in sorted(lane_bindings.items())
    }

    projections = {
        "command_allow_index": command_index,
        "principal_bindings": principal_bindings,
        "lane_bindings": lane_bindings,
        "redline_rules": normalized_redline_rules,
    }

    source_digest = "sha256:" + hashlib.sha256(
        json.dumps(policy, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    bundle = {
        "schema_version": POLICY_BUNDLE_SCHEMA,
        "compiled_at": datetime.now(timezone.utc).isoformat(),
        "policy_id": policy["policy_id"],
        "policy_version": policy["version"],
        "source_policy_digest": source_digest,
        "compiler": {
            "name": "arda_policy_compiler",
            "version": "phase5-slice1",
        },
        "projections": projections,
    }
    bundle["signature"] = _sign_bundle(bundle)
    return bundle


def evaluate_policy_bundle(bundle: Dict[str, Any], *, command: str, principal: str, lane: str) -> Dict[str, Any]:
    if bundle.get("schema_version") != POLICY_BUNDLE_SCHEMA:
        raise RuntimeError("[POLICY_BUNDLE] DENY: unsupported bundle schema")

    projections = bundle.get("projections", {})
    for rule in projections.get("redline_rules", []):
        command_match = rule.get("command") in (None, command)
        principal_match = rule.get("principal") in (None, principal)
        lane_match = rule.get("lane") in (None, lane)
        if command_match and principal_match and lane_match:
            return {
                "ok": True,
                "policy_id": bundle["policy_id"],
                "policy_version": bundle["policy_version"],
                "decision": "DENY",
                "decision_basis": "redline_rule",
                "matched_rule": rule,
            }

    command_rule = projections.get("command_allow_index", {}).get(command)
    if (
        command_rule
        and principal in command_rule.get("principals", [])
        and lane in command_rule.get("lanes", [])
        and command_rule.get("effect", "ALLOW") == "ALLOW"
    ):
        return {
            "ok": True,
            "policy_id": bundle["policy_id"],
            "policy_version": bundle["policy_version"],
            "decision": "ALLOW",
            "decision_basis": "compiled_allow_rule",
            "matched_rule": command_rule,
        }

    return {
        "ok": True,
        "policy_id": bundle["policy_id"],
        "policy_version": bundle["policy_version"],
        "decision": "DENY",
        "decision_basis": "no_matching_compiled_rule",
        "matched_rule": None,
    }


def compile_projection_plan(
    bundle: Dict[str, Any],
    *,
    executable_paths: List[str],
    enforcement_mode: str = "legacy_inode",
) -> Dict[str, Any]:
    if bundle.get("schema_version") != POLICY_BUNDLE_SCHEMA:
        raise RuntimeError("[POLICY_BUNDLE] DENY: cannot project unsupported bundle schema")
    if not bundle.get("projections", {}).get("redline_rules"):
        raise RuntimeError("[POLICY_BUNDLE] DENY: cannot project empty constitutional redline state")

    canonical_paths = sorted(
        {
            os.path.abspath(path)
            for path in executable_paths
            if path and os.path.exists(os.path.abspath(path)) and os.access(os.path.abspath(path), os.X_OK)
        }
    )

    plan = {
        "schema_version": "arda.policy_projection_plan.v1",
        "policy_id": bundle["policy_id"],
        "policy_version": bundle["policy_version"],
        "source_policy_digest": bundle["source_policy_digest"],
        "bundle_digest": "sha256:" + hashlib.sha256(
            json.dumps(bundle, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
        "targets": {
            "harmony_allow_paths": canonical_paths,
            "enforcement_mode": enforcement_mode,
            "phase3_generation_required": False,
            "redline_rules": bundle.get("projections", {}).get("redline_rules", []),
            "constitutional_state": {
                "policy_generation": f"{bundle['policy_id']}@{bundle['policy_version']}",
                "redline_rule_count": len(bundle.get("projections", {}).get("redline_rules", [])),
            },
        },
        "audit": {
            "requested_path_count": len(executable_paths),
            "usable_path_count": len(canonical_paths),
            "command_count": len(bundle.get("projections", {}).get("command_allow_index", {})),
        },
    }
    return plan


def generate_policy_bundle(policy_path: str = POLICY_PATH, bundle_path: str = POLICY_BUNDLE_PATH) -> Dict[str, Any]:
    policy = load_and_verify_policy(policy_path)
    bundle = compile_policy_bundle(policy)
    with open(bundle_path, "w", encoding="utf-8") as handle:
        json.dump(bundle, handle, indent=2)
        handle.write("\n")
    return bundle


def load_and_verify_policy_bundle(bundle_path: str = POLICY_BUNDLE_PATH) -> Dict[str, Any]:
    if not os.path.exists(bundle_path):
        raise RuntimeError(f"[POLICY_BUNDLE] DENY: bundle missing at {bundle_path}")
    with open(bundle_path, "r", encoding="utf-8") as handle:
        bundle = json.load(handle)
    if bundle.get("schema_version") != POLICY_BUNDLE_SCHEMA:
        raise RuntimeError("[POLICY_BUNDLE] DENY: unsupported schema version")
    stored_signature = bundle.get("signature", "")
    expected_signature = _sign_bundle(bundle)
    if not hmac.compare_digest(stored_signature, expected_signature):
        raise RuntimeError("[POLICY_BUNDLE] DENY: bundle signature INVALID")
    return bundle
