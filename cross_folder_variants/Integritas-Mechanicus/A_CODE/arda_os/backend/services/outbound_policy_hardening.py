"""Fail-closed helpers for consequential egress and break-glass evaluation."""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional, Sequence, Tuple
from urllib.parse import SplitResult, urlsplit, urlunsplit

from backend.services.arda_trust_contracts import parse_utc


class OutboundPolicyError(ValueError):
    pass


@dataclass(frozen=True)
class CanonicalTarget:
    scheme: str
    host: str
    port: int
    path: str
    query: str
    canonical_url: str


def host_matches_allowlist(
    host: str,
    *,
    exact_hosts: Sequence[str] = (),
    allowed_subdomain_roots: Sequence[str] = (),
) -> bool:
    """Match canonical DNS labels, never arbitrary URL substrings."""
    normalized = host.lower().rstrip(".")
    exact = {value.lower().rstrip(".") for value in exact_hosts}
    roots = {value.lower().rstrip(".") for value in allowed_subdomain_roots}
    return normalized in exact or any(
        normalized == root or normalized.endswith("." + root) for root in roots
    )


@dataclass(frozen=True)
class EgressPolicyV1:
    policy_id: str
    allowed_schemes: Tuple[str, ...] = ("https",)
    allowed_ports: Tuple[int, ...] = (443,)
    exact_hosts: Tuple[str, ...] = ()
    allowed_subdomain_roots: Tuple[str, ...] = ()
    allowed_ip_networks: Tuple[str, ...] = ()
    reject_non_public_resolution: bool = True


def canonicalize_target(raw_url: str) -> CanonicalTarget:
    raw = str(raw_url or "").strip()
    if not raw:
        raise OutboundPolicyError("target URL is required")
    parsed = urlsplit(raw)
    if not parsed.scheme or not parsed.netloc:
        raise OutboundPolicyError("target must be an absolute URL")
    if parsed.username is not None or parsed.password is not None:
        raise OutboundPolicyError("userinfo is forbidden in outbound targets")
    if parsed.fragment:
        raise OutboundPolicyError("URL fragments are forbidden in governed targets")
    try:
        host = (parsed.hostname or "").encode("idna").decode("ascii").lower().rstrip(".")
        explicit_port = parsed.port
    except (UnicodeError, ValueError) as exc:
        raise OutboundPolicyError("target host or port is invalid") from exc
    if not host or any(character.isspace() for character in host):
        raise OutboundPolicyError("target host is invalid")
    if host.isdigit():
        raise OutboundPolicyError("non-canonical numeric IP host is forbidden")
    try:
        host = ipaddress.ip_address(host).compressed
    except ValueError:
        labels = host.split(".")
        if any(not label or len(label) > 63 for label in labels):
            raise OutboundPolicyError("target DNS name is invalid")
        if any(not all(char.isalnum() or char == "-" for char in label) for label in labels):
            raise OutboundPolicyError("target DNS name contains forbidden characters")
        if any(label.startswith("-") or label.endswith("-") for label in labels):
            raise OutboundPolicyError("target DNS label is invalid")
    scheme = parsed.scheme.lower()
    default_port = 443 if scheme == "https" else 80 if scheme == "http" else None
    if default_port is None and explicit_port is None:
        raise OutboundPolicyError("target scheme requires an explicit governed port")
    port = int(explicit_port or default_port)
    display_host = f"[{host}]" if ":" in host else host
    netloc = display_host if port == default_port else f"{display_host}:{port}"
    path = parsed.path or "/"
    canonical_url = urlunsplit(SplitResult(scheme, netloc, path, parsed.query, ""))
    return CanonicalTarget(
        scheme=scheme,
        host=host,
        port=port,
        path=path,
        query=parsed.query,
        canonical_url=canonical_url,
    )


def evaluate_target(
    raw_url: str,
    policy: EgressPolicyV1,
    *,
    resolved_addresses: Iterable[str],
) -> CanonicalTarget:
    target = canonicalize_target(raw_url)
    if target.scheme not in {value.lower() for value in policy.allowed_schemes}:
        raise OutboundPolicyError("target scheme is not allowed")
    if target.port not in set(policy.allowed_ports):
        raise OutboundPolicyError("target port is not allowed")
    host_allowed = host_matches_allowlist(
        target.host,
        exact_hosts=policy.exact_hosts,
        allowed_subdomain_roots=policy.allowed_subdomain_roots,
    )
    if not host_allowed:
        raise OutboundPolicyError("target host is not allowed")

    addresses = tuple(str(value).strip() for value in resolved_addresses if str(value).strip())
    if not addresses:
        raise OutboundPolicyError("target has no policy-appraised resolution")
    allowed_networks = tuple(ipaddress.ip_network(value, strict=False) for value in policy.allowed_ip_networks)
    for raw_address in addresses:
        try:
            address = ipaddress.ip_address(raw_address)
        except ValueError as exc:
            raise OutboundPolicyError("resolver returned an invalid address") from exc
        explicitly_allowed = any(address in network for network in allowed_networks)
        non_public = not address.is_global
        if policy.reject_non_public_resolution and non_public and not explicitly_allowed:
            raise OutboundPolicyError("target resolves to a non-public address")
    return target


NON_OVERRIDABLE_VETOES = frozenset(
    {
        "attestation_signature",
        "attestation_nonce",
        "attestation_freshness",
        "attestation_audience",
        "workload_digest",
        "capability_signature",
        "capability_audience",
        "capability_replay",
        "transport_identity",
        "request_digest",
    }
)


@dataclass(frozen=True)
class BreakGlassReceiptV1:
    receipt_id: str
    incident_id: str
    principal_id: str
    approver_ids: Tuple[str, ...]
    reason: str
    action_scope_digest: str
    allowed_soft_vetoes: Tuple[str, ...]
    issued_at: str
    expires_at: str
    signature_algorithm: str
    signature: str

    def validate(self, *, now: Optional[datetime] = None) -> None:
        instant = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        issued = parse_utc(self.issued_at)
        expires = parse_utc(self.expires_at)
        if not self.receipt_id or not self.incident_id or not self.principal_id or not self.reason:
            raise OutboundPolicyError("break-glass identity, incident, principal, and reason are required")
        distinct_approvers = {value for value in self.approver_ids if value}
        if len(distinct_approvers) < 2 or self.principal_id in distinct_approvers:
            raise OutboundPolicyError("break-glass requires two distinct approvers other than the principal")
        if not (issued <= instant < expires):
            raise OutboundPolicyError("break-glass receipt is not currently valid")
        if expires - issued > timedelta(minutes=15):
            raise OutboundPolicyError("break-glass validity exceeds fifteen minutes")
        if not self.signature or not self.signature_algorithm:
            raise OutboundPolicyError("break-glass receipt must be signed")
        forbidden = NON_OVERRIDABLE_VETOES.intersection(self.allowed_soft_vetoes)
        if forbidden:
            raise OutboundPolicyError(
                "break-glass attempts to override hard vetoes: " + ",".join(sorted(forbidden))
            )


def apply_break_glass(
    hard_vetoes: Iterable[str],
    soft_vetoes: Iterable[str],
    receipt: BreakGlassReceiptV1,
    *,
    action_scope_digest: str,
    now: Optional[datetime] = None,
) -> Tuple[str, ...]:
    receipt.validate(now=now)
    if receipt.action_scope_digest != action_scope_digest:
        raise OutboundPolicyError("break-glass action scope does not match")
    hard = tuple(dict.fromkeys(str(value) for value in hard_vetoes if value))
    if hard:
        return hard
    allowed = set(receipt.allowed_soft_vetoes)
    return tuple(
        value for value in dict.fromkeys(str(item) for item in soft_vetoes if item)
        if value not in allowed
    )
