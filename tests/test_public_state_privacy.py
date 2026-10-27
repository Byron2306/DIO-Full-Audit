from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.classify_public_state import classify_path, load_policy
from scripts.check_public_state_privacy import scan_content, scan_tracked_paths


ROOT = Path(__file__).resolve().parents[1]
POLICY = load_policy(ROOT / "config/public_state_policy.json")


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("deliverables/proof/receipt.json", "retained_proof"),
        ("tests/fixtures/customer.json", "redacted_fixture"),
        ("runs/job-1/output.json", "generated_output"),
        ("state/mail_ingress/message.json", "private_operational_state"),
        ("dashboard/state.json", "private_operational_state"),
    ],
)
def test_policy_classifies_public_state(path: str, expected: str) -> None:
    assert classify_path(Path(path), POLICY) == expected


@pytest.mark.parametrize(
    ("payload", "rule"),
    [
        ({"email": "person@company.co.za"}, "email"),
        ({"phone": "+27 82 555 0199"}, "phone"),
        ({"customer_id": "CUST-839201"}, "customer_identifier"),
        ({"source": "/home/byron/private/input.pdf"}, "absolute_host_path"),
        ({"source": "C:\\Users\\Byron\\private.pdf"}, "absolute_host_path"),
    ],
)
def test_redacted_fixture_rejects_realistic_private_values(payload: dict[str, str], rule: str) -> None:
    findings = scan_content(Path("tests/fixtures/customer.json"), json.dumps(payload).encode(), "redacted_fixture")
    assert any(item.rule == rule for item in findings)


def test_redacted_fixture_accepts_explicit_redaction() -> None:
    findings = scan_content(
        Path("tests/fixtures/customer.json"),
        b'{"email":"[REDACTED]","phone":"[REDACTED]","customer_id":"[REDACTED]"}',
        "redacted_fixture",
    )
    assert findings == []


def test_retained_proof_hash_and_binary_are_allowed() -> None:
    assert scan_content(Path("deliverables/proof/receipt.json"), b'{"sha256":"' + b"a" * 64 + b'"}', "retained_proof") == []
    assert scan_content(Path("deliverables/proof/artifact.pdf"), b"%PDF-1.7\x00binary", "retained_proof") == []


def test_private_generated_and_unclassified_tracked_paths_fail() -> None:
    findings = scan_tracked_paths(
        ROOT,
        [Path("state/mail_ingress/a.json"), Path("runs/job/output.json"), Path("unknown/output.json")],
        POLICY,
        content_loader=lambda _path: b"{}",
    )
    assert {(item.path, item.rule) for item in findings} == {
        ("runs/job/output.json", "tracked_generated_output"),
        ("state/mail_ingress/a.json", "tracked_private_operational_state"),
        ("unknown/output.json", "unclassified_public_state"),
    }
