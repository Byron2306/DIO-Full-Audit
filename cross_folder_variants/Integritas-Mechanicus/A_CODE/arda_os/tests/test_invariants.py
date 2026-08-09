"""
Arda Trusted Core: Property-Based Invariant Tests
===================================================
Uses Hypothesis to verify the three formal invariants
across thousands of random inputs.

Invariant 1: No grant without policy match
Invariant 2: No envelope without valid signature
Invariant 3: No audit pass without chain-verified receipt
"""

import hashlib
import hmac
import json
import os
import sys
import tempfile

import pytest
from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.services.policy_engine import (
    generate_policy, load_and_verify_policy, evaluate, _canonical_bytes, _sign
)
from backend.services.attestation_service import (
    create_envelope, verify_envelope, get_envelope_trust_report, _canonical_body, _pae, DSSE_TYPE_URI
)
from backend.services import telemetry_chain


# ============================================================================
# Strategies: random but realistic test data
# ============================================================================

command_st = st.sampled_from(["check_health", "deploy", "delete", "escalate", "reboot"])
principal_st = st.sampled_from(["Magos_Indomitus", "Unknown_Agent", "Rogue_Echo", "Admin"])
lane_st = st.sampled_from(["Shire", "Gondor", "The Void", "Rohan"])
token_st = st.text(min_size=3, max_size=20, alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-")


# ============================================================================
# INVARIANT 1: No grant without policy match
# ============================================================================

class TestInvariant1_NoGrantWithoutPolicy:
    """Only explicitly allowed (command, principal, lane) triples pass policy."""

    @given(command=command_st, principal=principal_st, lane=lane_st)
    @settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_only_allowed_triple_passes(self, command, principal, lane, tmp_path):
        """Policy MUST deny any triple not in the declared rules."""
        policy_path = str(tmp_path / "test_policy.json")
        generate_policy(path=policy_path)

        # The only allowed triple
        allowed = (command == "check_health" and principal == "Magos_Indomitus" and lane == "Shire")

        if allowed:
            result = evaluate.__wrapped__(command, principal, lane) if hasattr(evaluate, '__wrapped__') else None
            # Just verify evaluate doesn't raise for the allowed case
            try:
                from backend.services import policy_engine
                old_path = policy_engine.POLICY_PATH
                policy_engine.POLICY_PATH = policy_path
                result = evaluate(command, principal, lane)
                assert result == "ALLOW"
                policy_engine.POLICY_PATH = old_path
            except Exception:
                policy_engine.POLICY_PATH = old_path
                raise
        else:
            try:
                from backend.services import policy_engine
                old_path = policy_engine.POLICY_PATH
                policy_engine.POLICY_PATH = policy_path
                evaluate(command, principal, lane)
                policy_engine.POLICY_PATH = old_path
                # If we get here without RuntimeError, invariant is broken
                assert False, f"Policy should DENY ({command}, {principal}, {lane})"
            except RuntimeError as e:
                policy_engine.POLICY_PATH = old_path
                assert "DENY" in str(e)

    def test_tampered_policy_rejected(self, tmp_path):
        """A policy with a modified signature MUST be rejected."""
        policy_path = str(tmp_path / "tampered_policy.json")
        generate_policy(path=policy_path)

        # Tamper with the policy
        with open(policy_path, "r") as f:
            policy = json.load(f)
        policy["commands"].append({"name": "evil_cmd", "lanes": ["Shire"], "principals": ["Evil"]})
        with open(policy_path, "w") as f:
            json.dump(policy, f)

        with pytest.raises(RuntimeError, match="INVALID"):
            load_and_verify_policy(path=policy_path)


# ============================================================================
# INVARIANT 2: No envelope without valid signature
# ============================================================================

class TestInvariant2_NoUnsignedEnvelope:
    """Every DSSE envelope must have a verifiable signature."""

    def test_envelope_signature_round_trips(self):
        """A freshly created envelope MUST verify."""
        env = create_envelope(
            command="check_health", principal="Magos_Indomitus",
            token_id="TOK-TEST", lane="Shire",
            policy_id="ARDA-POLICY-V1", policy_version="1.0.0",
            verdict="ALLOW", artifact_digest="abc123",
            policy_verdict="ALLOW",
        )
        assert verify_envelope(env), "Freshly signed envelope must verify"

    def test_tampered_envelope_rejected(self):
        """A tampered envelope MUST fail verification."""
        env = create_envelope(
            command="check_health", principal="Magos_Indomitus",
            token_id="TOK-TEST", lane="Shire",
            policy_id="ARDA-POLICY-V1", policy_version="1.0.0",
            verdict="ALLOW", artifact_digest="abc123",
            policy_verdict="ALLOW",
        )
        # Tamper with the payload
        env["payload"]["verdict"] = "DENY"
        assert not verify_envelope(env), "Tampered envelope must NOT verify"

    def test_hmac_envelope_is_explicitly_local_only(self):
        """Fallback envelopes must honestly declare local-only trust."""
        env = create_envelope(
            command="check_health", principal="Magos_Indomitus",
            token_id="TOK-TEST", lane="Shire",
            policy_id="ARDA-POLICY-V1", policy_version="1.0.0",
            verdict="ALLOW", artifact_digest="abc123",
            policy_verdict="ALLOW", use_sigstore=False,
        )
        assert env["signing_algorithm"] == "HMAC-SHA3-256"
        assert env["trust_mode"] == "local-only"
        assert verify_envelope(env)

    def test_fake_sigstore_envelope_rejected(self):
        """Sigstore-labeled envelopes without real bundle metadata must fail."""
        env = create_envelope(
            command="check_health", principal="Magos_Indomitus",
            token_id="TOK-TEST", lane="Shire",
            policy_id="ARDA-POLICY-V1", policy_version="1.0.0",
            verdict="ALLOW", artifact_digest="abc123",
            policy_verdict="ALLOW", use_sigstore=False,
        )
        env["signing_algorithm"] = "sigstore:fulcio+rekor"
        env["signature"] = "{\"bogus\":true}"
        env["transparency_receipt"] = {"log": "rekor.sigstore.dev", "integrated": True}
        assert not verify_envelope(env), "Bogus Sigstore envelope must NOT verify"

    def test_sigstore_trust_report_requires_real_material(self):
        """Sigstore trust reports must explain why malformed bundles are rejected."""
        env = {
            "payload_type": DSSE_TYPE_URI,
            "payload": {"type": DSSE_TYPE_URI, "artifact_digest": "abc123"},
            "signature": "{\"verificationMaterial\": {}}",
            "signing_algorithm": "sigstore:fulcio+rekor",
            "signing_identity": "OIDC:sigstore",
            "trust_mode": "external-transparency",
            "transparency_receipt": {"log": "rekor.sigstore.dev", "integrated": True, "log_index": 7},
        }
        report = get_envelope_trust_report(env)
        assert not report["verified"]
        assert report["failure_reason"] in {"sigstore_tlog_missing", "sigstore_certificate_missing"}

    def test_denied_request_cannot_be_attested(self):
        """Cannot produce an envelope for a denied request."""
        with pytest.raises(RuntimeError, match="DENY"):
            create_envelope(
                command="check_health", principal="Evil",
                token_id="TOK-TEST", lane="Shire",
                policy_id="ARDA-POLICY-V1", policy_version="1.0.0",
                verdict="DENY", artifact_digest="abc123",
                policy_verdict="DENY",  # This should block envelope creation
            )

    @given(principal=principal_st, command=command_st)
    @settings(max_examples=100, deadline=None)
    def test_random_envelopes_always_verify(self, principal, command):
        """Any honestly-created envelope must verify, regardless of content."""
        env = create_envelope(
            command=command, principal=principal,
            token_id="TOK-FUZZ", lane="Shire",
            policy_id="ARDA-POLICY-V1", policy_version="1.0.0",
            verdict="ALLOW", artifact_digest=hashlib.sha3_256(command.encode()).hexdigest(),
            policy_verdict="ALLOW",
        )
        assert verify_envelope(env)


# ============================================================================
# INVARIANT 3: No audit pass without chain-verified receipt
# ============================================================================

class TestInvariant3_NoAuditWithoutReceipt:
    """Ledger chain must be verifiable and tamper-evident."""

    def test_chain_valid_after_append(self):
        """Recording an audit action must preserve chain integrity."""
        chain = telemetry_chain.TamperEvidentTelemetry()

        env = create_envelope(
            command="check_health", principal="Magos_Indomitus",
            token_id="TOK-TEST", lane="Shire",
            policy_id="ARDA-POLICY-V1", policy_version="1.0.0",
            verdict="ALLOW", artifact_digest="abc123",
            policy_verdict="ALLOW",
        )

        record = chain.record_action(
            principal=env["payload"]["principal"],
            principal_trust_state="verified",
            action=env["payload"]["verdict"],
            targets=[env["payload"]["artifact_digest"]],
            token_id=env["payload"]["token_id"],
            result="allow",
        )

        assert len(record.record_hash) == 64, "Receipt must be SHA-256 hex"
        ok, _ = chain.verify_chain_integrity()
        assert ok

    def test_tampered_ledger_detected(self):
        """Mutating an audit record after append must break integrity verification."""
        chain = telemetry_chain.TamperEvidentTelemetry()
        record = chain.record_action(
            principal="Magos_Indomitus",
            principal_trust_state="verified",
            action="ALLOW",
            targets=["sha256:abc123"],
            token_id="TOK-TEST",
            result="allow",
        )

        chain.audit_chain[-1].action = "TAMPERED"
        ok, _ = chain.verify_chain_integrity()
        assert not ok, "Tampered audit chain must fail verification"

    def test_verify_chain_alias_reports_status(self):
        """The module-level convenience verifier should reflect chain status."""
        original = telemetry_chain.tamper_evident_telemetry
        replacement = telemetry_chain.TamperEvidentTelemetry()
        replacement.event_chain.clear()
        replacement.audit_chain.clear()
        replacement.current_event_hash = replacement.genesis_event_hash
        replacement.current_audit_hash = replacement.genesis_audit_hash
        telemetry_chain.tamper_evident_telemetry = replacement
        try:
            replacement.record_action(
                principal="Magos_Indomitus",
                principal_trust_state="verified",
                action="ALLOW",
                targets=["sha256:abc123"],
                token_id="TOK-TEST",
                result="allow",
            )
            ok, _ = telemetry_chain.verify_chain()
            assert ok
        finally:
            telemetry_chain.tamper_evident_telemetry = original


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
