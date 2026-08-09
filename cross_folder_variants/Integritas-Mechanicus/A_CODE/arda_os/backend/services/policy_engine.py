"""
Arda Policy Engine
==================
Deterministic, fail-closed policy evaluation.

This module is the ONLY trusted decision point for command authorization.
It verifies the policy document signature before trusting any rule,
then evaluates a request strictly against the declared rules.

Honest limitations:
- Signature is HMAC-SHA3-256, not PQC Dilithium (library not available).
- Policy file is local disk; not TPM-sealed (future work).
- boot_context is a software placeholder for future TPM PCR binding.
"""

import hashlib
import hmac
import json
import logging
import os
from typing import Dict, Any

logger = logging.getLogger("ARDA_POLICY")

# The signing secret for the policy document.
# In production this would be released from TPM only when PCR measurements match.
# Here it is an env var with a deterministic default for the trusted core demo.
_POLICY_SIGNING_SECRET = os.getenv(
    "ARDA_POLICY_SECRET", "ARDA-POLICY-SIGNING-SECRET-REPLACE-IN-PRODUCTION"
).encode()

POLICY_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "arda_policy.json")
)


def _canonical_bytes(obj: Dict[str, Any]) -> bytes:
    """Strict canonical JSON serialization for signing."""
    clean = {k: v for k, v in obj.items() if k != "signature"}
    return json.dumps(clean, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sign(body: bytes) -> str:
    return hmac.new(_POLICY_SIGNING_SECRET, body, hashlib.sha3_256).hexdigest()


def generate_policy(path: str = POLICY_PATH) -> Dict[str, Any]:
    """
    Creates and writes a signed policy document to disk.
    This should be run once by a trusted administrator — not at runtime.
    """
    from datetime import datetime, timezone
    policy = {
        "policy_id": "ARDA-POLICY-V1",
        "version": "1.0.0",
        "commands": [
            {
                "name": "check_health",
                "lanes": ["Shire"],
                "principals": ["Magos_Indomitus"]
            }
        ],
        "issued_at": datetime.now(timezone.utc).isoformat(),
    }
    body = _canonical_bytes(policy)
    policy["signature"] = _sign(body)
    with open(path, "w") as f:
        json.dump(policy, f, indent=2)
    logger.info(f"[POLICY] Policy written and signed: {path}")
    return policy


def load_and_verify_policy(path: str = POLICY_PATH) -> Dict[str, Any]:
    """
    Loads the policy document and verifies its signature.
    Raises RuntimeError if the file is missing, corrupt, or tampered with.
    This enforces invariant: no enforcement without a verified policy.
    """
    if not os.path.exists(path):
        raise RuntimeError(f"[POLICY] DENY: Policy file missing at {path}")
    with open(path, "r") as f:
        policy = json.load(f)
    stored_sig = policy.get("signature", "")
    body = _canonical_bytes(policy)
    expected = _sign(body)
    if not hmac.compare_digest(stored_sig, expected):
        raise RuntimeError("[POLICY] DENY: Policy signature INVALID — tamper detected.")
    logger.info(f"[POLICY] Policy {policy['policy_id']} v{policy['version']} verified.")
    return policy


def evaluate(command: str, principal: str, lane: str) -> str:
    """
    Evaluates a request against the verified policy.

    Returns "ALLOW" or raises RuntimeError with DENY reason.
    Default is DENY for any unmatched case (fail-closed).

    Invariant: no positive decision without an explicit policy match.
    """
    policy = load_and_verify_policy()

    for rule in policy.get("commands", []):
        if (
            rule["name"] == command
            and principal in rule["principals"]
            and lane in rule["lanes"]
        ):
            logger.info(
                f"[POLICY] ALLOW: '{command}' for '{principal}' in lane '{lane}' "
                f"(policy {policy['policy_id']} v{policy['version']})"
            )
            return "ALLOW"

    raise RuntimeError(
        f"[POLICY] DENY: '{command}' for '{principal}' in lane '{lane}' "
        f"— no matching rule in {policy['policy_id']} v{policy['version']}"
    )
