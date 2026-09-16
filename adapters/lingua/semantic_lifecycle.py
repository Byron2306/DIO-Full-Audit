from __future__ import annotations

import sys
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]

BEAST_CODE_ROOT = (
    REPO_ROOT
    / "cross_folder_variants"
    / "EdgeK-BEAST"
    / "A_CODE"
)


def _beast_api() -> dict[str, Any]:
    if str(BEAST_CODE_ROOT) not in sys.path:
        sys.path.insert(
            0,
            str(BEAST_CODE_ROOT),
        )

    from app.kernel.compute.semantic_generalizer import (
        SemanticCrystalLifecycleState,
        SemanticCrystalRegistry,
        SemanticGeneralizer,
    )

    return {
        "SemanticCrystalLifecycleState":
            SemanticCrystalLifecycleState,
        "SemanticCrystalRegistry":
            SemanticCrystalRegistry,
        "SemanticGeneralizer":
            SemanticGeneralizer,
    }


def _authority_true(value: Any) -> bool:
    """Detect authority-bearing truth inside semantic payloads.

    Semantic memory may describe authority boundaries, but it may never
    crystallise a positive grant of execution authority.
    """

    if isinstance(value, Mapping):
        for key, child in value.items():
            name = str(key).casefold()

            if (
                name.endswith("authority")
                or name.endswith("authority_created")
                or name in {
                    "external_effects",
                    "external_send_authority",
                    "quote_issue_authority",
                    "spend_authority",
                    "fulfilment_release_authority",
                }
            ):
                if child is True:
                    return True

            if _authority_true(child):
                return True

        return False

    if isinstance(
        value,
        (list, tuple, set, frozenset),
    ):
        return any(
            _authority_true(item)
            for item in value
        )

    return False


def appraise_candidate(
    *,
    episodes: Iterable[Any],
    crystal_id: str,
    verifier_id: str,
    minimum_verified_episodes: int = 2,
    verifier_version: str = "semantic-generalizer.v1",
    expires_at: str | None = None,
) -> dict[str, Any]:
    """Build and verify a promotion candidate without mutating a registry."""

    api = _beast_api()

    generalizer = api[
        "SemanticGeneralizer"
    ](
        minimum_verified_episodes=
            minimum_verified_episodes
    )

    values = tuple(episodes)

    record = generalizer.promote_record(
        values,
        crystal_id=crystal_id,
        verifier_id=verifier_id,
        verifier_version=verifier_version,
        expires_at=expires_at,
    )

    authority_created = (
        _authority_true(
            record.crystal.meaning.slots
        )
        or _authority_true(
            record.crystal.answer_frame.slots
        )
    )

    if authority_created:
        raise ValueError(
            "semantic candidate attempts to "
            "crystallise positive authority"
        )

    return {
        "schema":
            "dio.vesper.semantic_lifecycle."
            "candidate_appraisal.v1",

        "status":
            "APPROVED_FOR_PROMOTION",

        "record":
            record,

        "crystal_id":
            record.crystal.crystal_id,

        "semantic_key_digest":
            record.semantic_key_digest,

        "promotion_receipt_digest":
            record.promotion_receipt_digest,

        "episode_count":
            len(
                record
                .promotion_receipt
                .episode_digests
            ),

        "provider_calls_observed":
            record
            .promotion_receipt
            .provider_calls_observed,

        "authority_created":
            False,

        "external_effects":
            False,
    }


def promote_candidate(
    *,
    registry_path: Path,
    appraisal: Mapping[str, Any],
) -> dict[str, Any]:
    """Persist an already-appraised semantic candidate."""

    api = _beast_api()

    record = appraisal.get(
        "record"
    )

    if record is None:
        raise ValueError(
            "promotion requires an appraised record"
        )

    if (
        appraisal.get("status")
        != "APPROVED_FOR_PROMOTION"
    ):
        raise ValueError(
            "candidate is not approved for promotion"
        )

    registry = api[
        "SemanticCrystalRegistry"
    ](
        Path(registry_path)
    )

    registry.load()

    existing = registry.get(
        record.crystal.crystal_id
    )

    if existing is not None:
        if (
            existing.record_digest
            != record.record_digest
        ):
            raise ValueError(
                "crystal id already exists with "
                "different semantic record"
            )

        persisted = existing

    else:
        persisted = registry.promote(
            record
        )

    return {
        "schema":
            "dio.vesper.semantic_lifecycle."
            "promotion.v1",

        "status":
            "PROMOTED",

        "crystal_id":
            persisted.crystal.crystal_id,

        "record_digest":
            persisted.record_digest,

        "semantic_key_digest":
            persisted.semantic_key_digest,

        "promotion_receipt_digest":
            persisted.promotion_receipt_digest,

        "authority_created":
            False,

        "external_effects":
            False,
    }


def check_replay_health(
    *,
    record: Any,
    request_key: Any,
    verifier_version: str = "semantic-generalizer.v1",
    now: str | None = None,
) -> dict[str, Any]:
    """Evaluate whether one crystal still applies to current context."""

    api = _beast_api()

    generalizer = api[
        "SemanticGeneralizer"
    ]()

    outcome = generalizer.replay_record(
        record,
        request_key,
        provider_enabled=False,
        verifier_version=verifier_version,
        now=now,
    )

    return {
        "schema":
            "dio.vesper.semantic_lifecycle."
            "replay_health.v1",

        "crystal_id":
            record.crystal.crystal_id,

        "status":
            (
                "HEALTHY"
                if outcome.reused
                else "DRIFTED"
            ),

        "reused":
            bool(
                outcome.reused
            ),

        "provider_called":
            bool(
                outcome.provider_called
            ),

        "refusal_reason":
            str(
                outcome.refusal_reason
                or ""
            ),

        "receipt_digest":
            outcome.receipt_digest,

        "authority_created":
            False,

        "external_effects":
            False,
    }


def detect_drift(
    *,
    record: Any,
    request_key: Any,
    verifier_version: str = "semantic-generalizer.v1",
    now: str | None = None,
) -> dict[str, Any]:
    """Classify replay incompatibility without mutating lifecycle state."""

    health = check_replay_health(
        record=record,
        request_key=request_key,
        verifier_version=verifier_version,
        now=now,
    )

    reason = health[
        "refusal_reason"
    ]

    if health["status"] == "HEALTHY":
        drift_class = "NONE"

    elif "revoked" in reason:
        drift_class = "REVOKED"

    elif "expired" in reason:
        drift_class = "EXPIRED"

    elif "verifier version drift" in reason:
        drift_class = "VERIFIER_DRIFT"

    elif "semantic reuse key mismatch" in reason:
        drift_class = "SEMANTIC_CONTEXT_DRIFT"

    elif "negative applicability" in reason:
        drift_class = "NEGATIVE_APPLICABILITY"

    else:
        drift_class = "OTHER_REFUSAL"

    return {
        **health,

        "schema":
            "dio.vesper.semantic_lifecycle."
            "drift_detection.v1",

        "drift_detected":
            health["status"]
            != "HEALTHY",

        "drift_class":
            drift_class,
    }


def revoke_crystal(
    *,
    registry_path: Path,
    crystal_id: str,
    reason: str,
) -> dict[str, Any]:
    """Durably revoke one semantic crystal."""

    if not str(reason or "").strip():
        raise ValueError(
            "semantic revocation requires a reason"
        )

    api = _beast_api()

    registry = api[
        "SemanticCrystalRegistry"
    ](
        Path(registry_path)
    )

    registry.load()

    record = registry.get(
        crystal_id
    )

    if record is None:
        raise KeyError(
            f"unknown semantic crystal: {crystal_id}"
        )

    revoked = registry.revoke(
        crystal_id,
        reason=reason,
    )

    return {
        "schema":
            "dio.vesper.semantic_lifecycle."
            "revocation.v1",

        "status":
            "REVOKED",

        "crystal_id":
            revoked.crystal.crystal_id,

        "record_digest":
            revoked.record_digest,

        "reason":
            revoked.revoked_reason,

        "authority_created":
            False,

        "external_effects":
            False,
    }


def replace_crystal(
    *,
    registry_path: Path,
    predecessor_crystal_id: str,
    replacement_appraisal: Mapping[str, Any],
    replacement_request_key: Any,
    revocation_reason: str,
    verifier_version: str = "semantic-generalizer.v1",
) -> dict[str, Any]:
    """Promote, prove, then retire a predecessor.

    Order is deliberate:

      1. candidate already appraised
      2. promote replacement
      3. reload and prove replacement replay
      4. revoke predecessor
      5. reload
      6. prove predecessor refuses
      7. prove replacement still reuses

    Semantic replacement never creates authority.
    """

    api = _beast_api()

    registry_path = Path(
        registry_path
    )

    replacement_record = (
        replacement_appraisal.get(
            "record"
        )
    )

    if replacement_record is None:
        raise ValueError(
            "replacement requires an "
            "appraised semantic record"
        )

    replacement_id = (
        replacement_record
        .crystal
        .crystal_id
    )

    if (
        replacement_id
        ==
        predecessor_crystal_id
    ):
        raise ValueError(
            "replacement crystal id must differ "
            "from predecessor"
        )

    # 1 + 2
    promotion = promote_candidate(
        registry_path=registry_path,
        appraisal=replacement_appraisal,
    )

    # 3
    registry = api[
        "SemanticCrystalRegistry"
    ](
        registry_path
    )

    registry.load()

    promoted = registry.get(
        replacement_id
    )

    if promoted is None:
        raise RuntimeError(
            "replacement disappeared after promotion"
        )

    promoted_health = check_replay_health(
        record=promoted,
        request_key=replacement_request_key,
        verifier_version=verifier_version,
    )

    if not promoted_health[
        "reused"
    ]:
        raise RuntimeError(
            "replacement failed replay proof: "
            + promoted_health[
                "refusal_reason"
            ]
        )

    predecessor = registry.get(
        predecessor_crystal_id
    )

    if predecessor is None:
        raise KeyError(
            "predecessor semantic crystal "
            "does not exist"
        )

    # 4
    revocation = revoke_crystal(
        registry_path=registry_path,
        crystal_id=predecessor_crystal_id,
        reason=revocation_reason,
    )

    # 5
    final_registry = api[
        "SemanticCrystalRegistry"
    ](
        registry_path
    )

    final_registry.load()

    old_record = final_registry.get(
        predecessor_crystal_id
    )

    new_record = final_registry.get(
        replacement_id
    )

    if (
        old_record is None
        or new_record is None
    ):
        raise RuntimeError(
            "replacement lifecycle reload incomplete"
        )

    # 6
    old_health = check_replay_health(
        record=old_record,
        request_key=old_record.semantic_reuse_key,
        verifier_version=verifier_version,
    )

    if old_health[
        "reused"
    ]:
        raise RuntimeError(
            "revoked predecessor still replays"
        )

    # 7
    new_health = check_replay_health(
        record=new_record,
        request_key=replacement_request_key,
        verifier_version=verifier_version,
    )

    if not new_health[
        "reused"
    ]:
        raise RuntimeError(
            "replacement failed after predecessor "
            "revocation"
        )

    return {
        "schema":
            "dio.vesper.semantic_lifecycle."
            "replacement.v1",

        "status":
            "REPLACED",

        "predecessor_crystal_id":
            predecessor_crystal_id,

        "replacement_crystal_id":
            replacement_id,

        "promotion_receipt_digest":
            promotion[
                "promotion_receipt_digest"
            ],

        "revoked_predecessor":
            True,

        "predecessor_replay":
            "REFUSED",

        "replacement_replay":
            "VERIFIED",

        "provider_called":
            False,

        "authority_created":
            False,

        "external_effects":
            False,

        "revocation":
            revocation,
    }


def lifecycle_inventory(
    *,
    registry_path: Path,
) -> dict[str, Any]:
    """Return durable semantic lifecycle truth."""

    api = _beast_api()

    registry = api[
        "SemanticCrystalRegistry"
    ](
        Path(registry_path)
    )

    registry.load()

    records = registry.records()

    return {
        "schema":
            "dio.vesper.semantic_lifecycle."
            "inventory.v1",

        "records": [
            {
                "crystal_id":
                    record.crystal.crystal_id,

                "lifecycle_state":
                    record.lifecycle_state.value,

                "semantic_key_digest":
                    record.semantic_key_digest,

                "promotion_receipt_digest":
                    record.promotion_receipt_digest,

                "verifier_version":
                    record.verifier_version,

                "expires_at":
                    record.expires_at,

                "revoked_reason":
                    record.revoked_reason,
            }
            for record in records
        ],

        "active":
            sum(
                record.lifecycle_state
                is api[
                    "SemanticCrystalLifecycleState"
                ].ACTIVE
                for record in records
            ),

        "revoked":
            sum(
                record.lifecycle_state
                is api[
                    "SemanticCrystalLifecycleState"
                ].REVOKED
                for record in records
            ),

        "authority_created":
            False,

        "external_effects":
            False,
    }
