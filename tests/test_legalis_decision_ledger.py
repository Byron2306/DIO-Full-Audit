from __future__ import annotations

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from adapters.legalis.service import LegalisError, canonical_hash
from adapters.legalis.valinor_bridge import authorize_valinor_boundary

try:
    from adapters.legalis.decision_ledger import issue_decision, verify_decision
except ModuleNotFoundError:
    issue_decision = None
    verify_decision = None


@pytest.fixture(autouse=True)
def _keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "DIO_LEGALIS_HMAC_KEYS_JSON",
        json.dumps({"epoch-0": "o" * 32, "epoch-1": "k" * 32}),
    )
    monkeypatch.setenv("DIO_LEGALIS_HMAC_KEY_EPOCH", "epoch-1")


def _append(state_root: Path, *, suffix: str = "A", epoch: str | None = None):
    if issue_decision is None:
        pytest.fail("authenticated Legalis decision ledger is not implemented")
    request = {
        "capability_id": "public_marketing_release",
        "case_id": "CASE-1",
        "action_id": "ACTION-1",
        "operator_checks": {"public_claim_review_complete": {"value": True, "receipt_ref": f"operator://review/{suffix}"}},
        "valinor": {
            "entity_id": "dio-workflows",
            "operation": "write",
            "target": "public://marketing",
        },
    }
    envelope = issue_decision(
        state_root,
        request=request,
        actor_id="operator-byron",
        policy_version="legalis-policy-2026-10",
    )
    return envelope, request, envelope["evidence_binding"]


def test_authenticated_decision_round_trip_binds_request_and_capability(tmp_path: Path) -> None:
    """Dropping request or capability binding would let one approval authorize another action."""
    envelope, request, evidence = _append(tmp_path)

    verified = verify_decision(
        tmp_path,
        envelope["decision_id"],
        expected_request_digest=canonical_hash(request),
        expected_evidence_digest=canonical_hash(evidence),
        expected_capability="public_marketing_release",
        expected_policy_version="legalis-policy-2026-10",
    )

    assert verified["schema"] == "dio.legalis.authenticated_decision.v1"
    assert verified["decision"]["verdict"] == "ALLOW"
    assert verified["authority_created"] is False
    assert verified["hmac_sha256"].startswith("hmac-sha256:")


def test_caller_supplied_allow_dictionary_is_refused(tmp_path: Path) -> None:
    """Trusting schema plus ALLOW recreates the original authorization bypass."""
    with pytest.raises(LegalisError, match="authenticated decision_id"):
        authorize_valinor_boundary(
            decision={"schema": "dio.legalis.decision_receipt.v1", "verdict": "ALLOW"},
            state_root=tmp_path,
            request={"valinor": {"entity_id": "dio-workflows", "operation": "write", "target": "public://marketing"}},
            evidence={"manifest_digest": "sha256:anything"},
            expected_capability="public_marketing_release",
            expected_policy_version="legalis-policy-2026-10",
            entity_id="dio-workflows",
            operation="write",
            target="public://marketing",
            runtime=FakeRuntime(),
        )


@pytest.mark.parametrize(
    ("request_digest", "capability"),
    [("sha256:wrong", "public_marketing_release"), (None, "contract_or_filing")],
)
def test_verifier_refuses_wrong_request_or_capability(
    tmp_path: Path, request_digest: str | None, capability: str
) -> None:
    """Weak binding would let a valid ledger row cross action or capability boundaries."""
    envelope, request, evidence = _append(tmp_path)
    with pytest.raises(LegalisError):
        verify_decision(
            tmp_path,
            envelope["decision_id"],
            expected_request_digest=request_digest or canonical_hash(request),
            expected_evidence_digest=canonical_hash(evidence),
            expected_capability=capability,
        )


def test_verifier_refuses_tampered_or_broken_chain(tmp_path: Path) -> None:
    """Skipping full-ledger verification would hide modified historical authorization."""
    first, _, _ = _append(tmp_path, suffix="A")
    second, request, evidence = _append(tmp_path, suffix="B")
    ledger = tmp_path / "legalis" / "decision_ledger.jsonl"
    rows = [json.loads(line) for line in ledger.read_text().splitlines()]
    rows[0]["decision"]["verdict"] = "REFUSE"
    ledger.write_text("\n".join(json.dumps(row) for row in rows) + "\n")

    with pytest.raises(LegalisError, match="integrity"):
        verify_decision(
            tmp_path,
            second["decision_id"],
            expected_request_digest=canonical_hash(request),
            expected_evidence_digest=canonical_hash(evidence),
            expected_capability="public_marketing_release",
        )
    assert first["ledger_entry_sha256"] == rows[1]["previous_entry_sha256"]


def test_known_old_epoch_verifies_and_unknown_epoch_fails(tmp_path: Path) -> None:
    """Rotation must retain known history without accepting an attacker-selected key epoch."""
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("DIO_LEGALIS_HMAC_KEY_EPOCH", "epoch-0")
    envelope, request, evidence = _append(tmp_path)
    monkeypatch.setenv("DIO_LEGALIS_HMAC_KEY_EPOCH", "epoch-1")
    verified = verify_decision(
        tmp_path,
        envelope["decision_id"],
        expected_request_digest=canonical_hash(request),
        expected_evidence_digest=canonical_hash(evidence),
        expected_capability="public_marketing_release",
        expected_policy_version="legalis-policy-2026-10",
    )
    assert verified["key_epoch"] == "epoch-0"

    with pytest.raises(LegalisError, match="key epoch is not live"):
        authorize_valinor_boundary(
            decision_id=envelope["decision_id"],
            state_root=tmp_path,
            request=request,
            evidence=evidence,
            expected_capability="public_marketing_release",
            expected_policy_version="legalis-policy-2026-10",
            entity_id="dio-workflows",
            operation="write",
            target="public://marketing",
            runtime=FakeRuntime(),
        )

    ledger = tmp_path / "legalis" / "decision_ledger.jsonl"
    row = json.loads(ledger.read_text())
    row["key_epoch"] = "unknown"
    ledger.write_text(json.dumps(row) + "\n")
    with pytest.raises(LegalisError, match="key epoch"):
        verify_decision(
            tmp_path,
            envelope["decision_id"],
            expected_request_digest=canonical_hash(request),
            expected_evidence_digest=canonical_hash(evidence),
            expected_capability="public_marketing_release",
            expected_policy_version="legalis-policy-2026-10",
        )
    monkeypatch.undo()


def test_concurrent_appends_form_one_unbroken_chain(tmp_path: Path) -> None:
    """Missing writer serialization would fork previous hashes or lose decisions."""
    def write(index: int) -> str:
        envelope, _, _ = _append(tmp_path, suffix=str(index))
        return str(envelope["decision_id"])

    with ThreadPoolExecutor(max_workers=8) as pool:
        ids = list(pool.map(write, range(16)))

    ledger = tmp_path / "legalis" / "decision_ledger.jsonl"
    rows = [json.loads(line) for line in ledger.read_text().splitlines()]
    assert len(rows) == 16
    assert len(set(ids)) == 16
    assert rows[0]["previous_entry_sha256"] is None
    assert all(rows[index]["previous_entry_sha256"] == rows[index - 1]["ledger_entry_sha256"] for index in range(1, 16))


class FakeRuntime:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str | None]] = []

    def write_stream(self, entity_id: str, target: str):
        self.calls.append(("write", entity_id, target))
        return {"allowed": True}


def test_valinor_loads_authenticated_allow_from_ledger(tmp_path: Path) -> None:
    """Bypassing ledger verification would let the bridge trust mutable caller content."""
    envelope, request, evidence = _append(tmp_path)
    runtime = FakeRuntime()

    receipt = authorize_valinor_boundary(
        decision_id=envelope["decision_id"],
        state_root=tmp_path,
        request=request,
        evidence=evidence,
        expected_capability="public_marketing_release",
        expected_policy_version="legalis-policy-2026-10",
        entity_id="dio-workflows",
        operation="write",
        target="public://marketing",
        runtime=runtime,
    )

    assert receipt["state"] == "VALINOR_ALLOW"
    assert receipt["decision_id"] == envelope["decision_id"]
    assert receipt["external_action_executed"] is False
    assert runtime.calls == [("write", "dio-workflows", "public://marketing")]


def test_valinor_refuses_transfer_to_different_effect_target(tmp_path: Path) -> None:
    """Authenticating only capability would let an approved target authorize a new target."""
    envelope, request, evidence = _append(tmp_path)
    with pytest.raises(LegalisError, match="request does not match"):
        authorize_valinor_boundary(
            decision_id=envelope["decision_id"],
            state_root=tmp_path,
            request=request,
            evidence=evidence,
            expected_capability="public_marketing_release",
            expected_policy_version="legalis-policy-2026-10",
            entity_id="dio-workflows",
            operation="write",
            target="public://different-target",
            runtime=FakeRuntime(),
        )


def test_valinor_refuses_different_evidence_binding(tmp_path: Path) -> None:
    """Reusing an authentic decision with substituted evidence would bypass its basis."""
    envelope, request, _ = _append(tmp_path)
    with pytest.raises(LegalisError, match="evidence digest"):
        authorize_valinor_boundary(
            decision_id=envelope["decision_id"],
            state_root=tmp_path,
            request=request,
            evidence={"manifest_digest": "sha256:substituted"},
            expected_capability="public_marketing_release",
            expected_policy_version="legalis-policy-2026-10",
            entity_id="dio-workflows",
            operation="write",
            target="public://marketing",
            runtime=FakeRuntime(),
        )


def test_valinor_consumes_decision_once(tmp_path: Path) -> None:
    envelope, request, evidence = _append(tmp_path)
    arguments = dict(
        decision_id=envelope["decision_id"],
        state_root=tmp_path,
        request=request,
        evidence=evidence,
        expected_capability="public_marketing_release",
        expected_policy_version="legalis-policy-2026-10",
        entity_id="dio-workflows",
        operation="write",
        target="public://marketing",
        runtime=FakeRuntime(),
    )
    authorize_valinor_boundary(**arguments)
    with pytest.raises(LegalisError, match="already consumed"):
        authorize_valinor_boundary(**arguments)


def test_issuer_does_not_accept_a_caller_supplied_decision(tmp_path: Path) -> None:
    with pytest.raises(TypeError):
        issue_decision(
            tmp_path,
            request={"capability_id": "public_marketing_release"},
            decision={"schema": "dio.legalis.decision_receipt.v1", "verdict": "ALLOW"},
            actor_id="operator-byron",
            policy_version="legalis-policy-2026-10",
        )


def test_marketing_capability_cannot_authorize_secret_access(tmp_path: Path) -> None:
    with pytest.raises(LegalisError, match="effect policy"):
        issue_decision(
            tmp_path,
            request={
                "capability_id": "public_marketing_release",
                "operator_checks": {"public_claim_review_complete": True},
                "valinor": {"entity_id": "dio-workflows", "operation": "secret", "target": "AWS_SECRET_ACCESS_KEY"},
            },
            actor_id="operator-byron",
            policy_version="legalis-policy-2026-10",
        )


def test_manage_legalis_persists_authenticated_decision_with_trusted_time(tmp_path: Path) -> None:
    """Writing only the unsigned evaluator result would leave production callers forgeable."""
    root = Path(__file__).resolve().parents[1]
    request = tmp_path / "request.json"
    request.write_text(
        json.dumps(
            {
                "capability_id": "public_marketing_release",
                "case_id": "CASE-CLI",
                "now": "2000-01-01T00:00:00+00:00",
                "operator_checks": {"public_claim_review_complete": True},
                "valinor": {
                    "entity_id": "dio-workflows",
                    "operation": "write",
                    "target": "public://marketing",
                },
            }
        )
    )
    output = tmp_path / "receipt.json"
    env = dict(os.environ)
    env["DIO_LEGALIS_HMAC_KEYS_JSON"] = json.dumps({"cli-epoch": "c" * 32})
    env["DIO_LEGALIS_HMAC_KEY_EPOCH"] = "cli-epoch"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/manage_legalis.py",
            str(request),
            "--state-root",
            str(tmp_path / "state"),
            "--actor-id",
            "operator-cli",
            "--policy-version",
            "test-policy-v1",
            "--out",
            str(output),
        ],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(output.read_text())
    assert payload["authenticated_decision"]["schema"] == "dio.legalis.authenticated_decision.v1"
    assert payload["decision"]["evaluated_at"] != "2000-01-01T00:00:00+00:00"
    assert (tmp_path / "state/legalis/decision_ledger.jsonl").is_file()
