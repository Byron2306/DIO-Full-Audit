from datetime import datetime, timedelta, timezone

import pytest

from backend.services.outbound_policy_hardening import (
    BreakGlassReceiptV1,
    EgressPolicyV1,
    OutboundPolicyError,
    apply_break_glass,
    canonicalize_target,
    evaluate_target,
    host_matches_allowlist,
)


def policy():
    return EgressPolicyV1(
        policy_id="egress-prod-v1",
        exact_hosts=("updates.example.com",),
        allowed_subdomain_roots=("services.example.org",),
    )


def test_target_canonicalization_and_dns_boundary_matching():
    target = evaluate_target(
        "HTTPS://UPDATES.EXAMPLE.COM./packages?q=1",
        policy(),
        resolved_addresses=("93.184.216.34",),
    )
    assert target.canonical_url == "https://updates.example.com/packages?q=1"

    child = evaluate_target(
        "https://api.services.example.org/v1",
        policy(),
        resolved_addresses=("93.184.216.34",),
    )
    assert child.host == "api.services.example.org"

    with pytest.raises(OutboundPolicyError, match="host is not allowed"):
        evaluate_target(
            "https://updates.example.com.evil.invalid/",
            policy(),
            resolved_addresses=("93.184.216.34",),
        )


def test_substring_is_never_a_dns_identity():
    roots = ("updates.debian.org",)
    assert host_matches_allowlist(
        "updates.debian.org", allowed_subdomain_roots=roots
    )
    assert host_matches_allowlist(
        "mirror.updates.debian.org", allowed_subdomain_roots=roots
    )
    assert not host_matches_allowlist(
        "updates.debian.org.attacker.test", allowed_subdomain_roots=roots
    )
    assert not host_matches_allowlist(
        "evil-updates.debian.org", exact_hosts=roots
    )


def test_live_seraph_proxy_uses_canonical_host_boundaries():
    from backend.services.seraph_proxy import SeraphProxy

    proxy = SeraphProxy()
    assert proxy._is_whitelisted("https://arxiv.org/abs/123")
    assert proxy._is_whitelisted("https://export.arxiv.org/api/query")
    assert not proxy._is_whitelisted("https://arxiv.org.attacker.test/")
    assert not proxy._is_whitelisted("https://attacker.test/?next=arxiv.org")


@pytest.mark.parametrize(
    "target",
    [
        "https://user@updates.example.com/",
        "https://updates.example.com/#fragment",
        "http://2130706433/",
        "https://-bad.services.example.org/",
    ],
)
def test_ambiguous_or_smuggled_targets_are_rejected(target):
    with pytest.raises(OutboundPolicyError):
        canonicalize_target(target)


def test_private_resolution_and_redirect_destination_are_reappraised():
    with pytest.raises(OutboundPolicyError, match="non-public"):
        evaluate_target(
            "https://updates.example.com/",
            policy(),
            resolved_addresses=("127.0.0.1",),
        )
    with pytest.raises(OutboundPolicyError, match="host is not allowed"):
        evaluate_target(
            "https://redirect.evil.invalid/",
            policy(),
            resolved_addresses=("93.184.216.34",),
        )


def make_receipt(now, **changes):
    values = {
        "receipt_id": "breakglass-1",
        "incident_id": "incident-1",
        "principal_id": "operator-1",
        "approver_ids": ("approver-1", "approver-2"),
        "reason": "restore critical service",
        "action_scope_digest": "sha256:" + "1" * 64,
        "allowed_soft_vetoes": ("triune_pending",),
        "issued_at": now.isoformat(),
        "expires_at": (now + timedelta(minutes=10)).isoformat(),
        "signature_algorithm": "test",
        "signature": "signed",
    }
    values.update(changes)
    return BreakGlassReceiptV1(**values)


def test_break_glass_can_clear_only_declared_soft_vetoes():
    now = datetime.now(timezone.utc)
    receipt = make_receipt(now)
    remaining = apply_break_glass(
        (),
        ("triune_pending", "change_freeze"),
        receipt,
        action_scope_digest=receipt.action_scope_digest,
        now=now,
    )
    assert remaining == ("change_freeze",)


def test_break_glass_cannot_clear_attestation_transport_or_identity_vetoes():
    now = datetime.now(timezone.utc)
    with pytest.raises(OutboundPolicyError, match="hard vetoes"):
        make_receipt(now, allowed_soft_vetoes=("attestation_signature",)).validate(now=now)

    receipt = make_receipt(now)
    remaining = apply_break_glass(
        ("transport_identity", "workload_digest"),
        ("triune_pending",),
        receipt,
        action_scope_digest=receipt.action_scope_digest,
        now=now,
    )
    assert remaining == ("transport_identity", "workload_digest")


def test_break_glass_requires_two_person_short_lived_scope_bound_approval():
    now = datetime.now(timezone.utc)
    with pytest.raises(OutboundPolicyError, match="two distinct approvers"):
        make_receipt(now, approver_ids=("approver-1", "approver-1")).validate(now=now)
    with pytest.raises(OutboundPolicyError, match="fifteen minutes"):
        make_receipt(now, expires_at=(now + timedelta(minutes=30)).isoformat()).validate(now=now)
    with pytest.raises(OutboundPolicyError, match="scope does not match"):
        apply_break_glass(
            (),
            ("triune_pending",),
            make_receipt(now),
            action_scope_digest="sha256:" + "9" * 64,
            now=now,
        )
