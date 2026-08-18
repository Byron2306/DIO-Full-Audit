"""Canonical Phase 1 contracts for the DIO Metamorphic Spine.

These objects define contract shape only. They do not reimplement LINGUA,
Sensorium, VNS, Harmonics, Seraph, ARDA, or world-state authority.
"""
from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping


PHASE1_EXIT_TOKEN = "DIO_METAMORPHIC_M1_CONTRACTS_READY"
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class MetamorphicRole(str, Enum):
    PRODUCT = "product"
    CAPABILITY = "capability"
    COMPOSITE_NODE = "composite_node"


class LayerWitnessState(str, Enum):
    EXERCISED = "EXERCISED"
    CORROBORATED = "CORROBORATED"
    ARMED = "ARMED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    MISSING = "MISSING"
    FAILED = "FAILED"


class SettlementState(str, Enum):
    SETTLED = "SETTLED"
    PARTIAL = "PARTIAL"
    FRACTURED = "FRACTURED"
    REFUSED = "REFUSED"


def _normalise(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {field.name: _normalise(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        return {str(key): _normalise(item) for key, item in sorted(value.items(), key=lambda row: str(row[0]))}
    if isinstance(value, (tuple, list)):
        return [_normalise(item) for item in value]
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(_normalise(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest_payload(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def require_digest(value: str, *, field_name: str) -> str:
    if not isinstance(value, str) or not DIGEST_RE.fullmatch(value):
        raise ValueError(f"{field_name} must be a sha256: digest")
    return value


def parse_datetime(value: str, *, field_name: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be an ISO-8601 datetime")
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO-8601 datetime") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field_name} must include timezone information")
    return parsed


def _nonempty(value: str, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} is required")
    return value.strip()


def _tuple_strings(values: tuple[str, ...], *, field_name: str, allow_empty: bool = True) -> None:
    if not allow_empty and not values:
        raise ValueError(f"{field_name} requires at least one value")
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise ValueError(f"{field_name} values must be non-empty strings")


@dataclass(frozen=True, slots=True)
class MetamorphicUnit:
    unit_id: str
    version: str
    source_digest: str
    roles: tuple[MetamorphicRole, ...]
    provides: tuple[str, ...]
    requires: tuple[str, ...]
    executor_id: str
    executor_version: str
    executor_digest: str
    input_contract: Mapping[str, Any]
    output_contract: Mapping[str, Any]
    evidence_contract: Mapping[str, Any]
    quality_contract: Mapping[str, Any]
    semantic_contract: Mapping[str, Any]
    buyer_projection: Mapping[str, Any]
    maturity_state: str
    authority_ceiling: str
    applicability_fingerprints: Mapping[str, tuple[str, ...]]
    promotion_rules: Mapping[str, Any]
    negative_capability_refs: tuple[str, ...] = ()
    crystal_refs: tuple[str, ...] = ()
    parent_unit_id: str | None = None
    schema: str = "dio.metamorphic_unit.v1"

    def __post_init__(self) -> None:
        _nonempty(self.unit_id, field_name="unit_id")
        _nonempty(self.version, field_name="version")
        require_digest(self.source_digest, field_name="source_digest")
        require_digest(self.executor_digest, field_name="executor_digest")
        _nonempty(self.executor_id, field_name="executor_id")
        _nonempty(self.executor_version, field_name="executor_version")
        _nonempty(self.maturity_state, field_name="maturity_state")
        _nonempty(self.authority_ceiling, field_name="authority_ceiling")
        if not self.roles:
            raise ValueError("roles requires at least one role")
        normalised_roles = tuple(role if isinstance(role, MetamorphicRole) else MetamorphicRole(role) for role in self.roles)
        if len(set(normalised_roles)) != len(normalised_roles):
            raise ValueError("roles must be unique")
        object.__setattr__(self, "roles", normalised_roles)
        _tuple_strings(self.provides, field_name="provides", allow_empty=False)
        _tuple_strings(self.requires, field_name="requires")
        _tuple_strings(self.negative_capability_refs, field_name="negative_capability_refs")
        _tuple_strings(self.crystal_refs, field_name="crystal_refs")
        if self.parent_unit_id is not None:
            _nonempty(self.parent_unit_id, field_name="parent_unit_id")
        semantic_required = {"denotation", "affordances", "prohibitions", "projections"}
        missing = semantic_required - set(self.semantic_contract)
        if missing:
            raise ValueError(f"semantic_contract missing: {sorted(missing)}")

    @property
    def unit_digest(self) -> str:
        return digest_payload(self)

    def to_dict(self) -> dict[str, Any]:
        payload = _normalise(self)
        payload["identity"] = {
            "unit_id": payload.pop("unit_id"),
            "version": payload.pop("version"),
            "source_digest": payload.pop("source_digest"),
            "parent_unit_id": payload.pop("parent_unit_id"),
        }
        payload["executor"] = {
            "executor_id": payload.pop("executor_id"),
            "executor_version": payload.pop("executor_version"),
            "executor_digest": payload.pop("executor_digest"),
        }
        payload["unit_digest"] = self.unit_digest
        return payload


@dataclass(frozen=True, slots=True)
class WorldLease:
    lease_id: str
    composition_id: str
    snapshot_digest: str
    epoch_id: str
    observed_at: str
    expires_at: str
    policy_generation: str
    facts_refs: tuple[str, ...] = ()
    market_state_refs: tuple[str, ...] = ()
    network_state_refs: tuple[str, ...] = ()
    capability_refs: tuple[str, ...] = ()
    authority_refs: tuple[str, ...] = ()
    customer_refs: tuple[str, ...] = ()
    schema: str = "dio.world_lease.v1"

    def __post_init__(self) -> None:
        _nonempty(self.lease_id, field_name="lease_id")
        _nonempty(self.composition_id, field_name="composition_id")
        require_digest(self.snapshot_digest, field_name="snapshot_digest")
        _nonempty(self.epoch_id, field_name="epoch_id")
        _nonempty(self.policy_generation, field_name="policy_generation")
        observed = parse_datetime(self.observed_at, field_name="observed_at")
        expires = parse_datetime(self.expires_at, field_name="expires_at")
        if expires <= observed:
            raise ValueError("expires_at must be after observed_at")
        for field_name in (
            "facts_refs", "market_state_refs", "network_state_refs",
            "capability_refs", "authority_refs", "customer_refs",
        ):
            _tuple_strings(getattr(self, field_name), field_name=field_name)

    @property
    def lease_digest(self) -> str:
        return digest_payload(self)

    def is_current(self, *, now: datetime | None = None) -> bool:
        current = now or datetime.now(timezone.utc)
        return parse_datetime(self.expires_at, field_name="expires_at") > current

    def to_dict(self) -> dict[str, Any]:
        payload = _normalise(self)
        payload["lease_digest"] = self.lease_digest
        return payload


@dataclass(frozen=True, slots=True)
class WorldSettlement:
    settlement_id: str
    episode_id: str
    pre_world_digest: str
    post_world_digest: str
    expected_effects: tuple[str, ...]
    observed_effects: tuple[str, ...]
    sensorium_receipts: tuple[str, ...]
    vns_receipts: tuple[str, ...]
    arda_receipts: tuple[str, ...]
    seraph_receipts: tuple[str, ...]
    harmonic_before: Mapping[str, Any]
    harmonic_after: Mapping[str, Any]
    authority_preserved: bool
    unexpected_effects: tuple[str, ...]
    settlement_state: SettlementState
    schema: str = "dio.world_settlement.v1"

    def __post_init__(self) -> None:
        _nonempty(self.settlement_id, field_name="settlement_id")
        _nonempty(self.episode_id, field_name="episode_id")
        require_digest(self.pre_world_digest, field_name="pre_world_digest")
        require_digest(self.post_world_digest, field_name="post_world_digest")
        if not isinstance(self.authority_preserved, bool):
            raise ValueError("authority_preserved must be boolean")
        state = self.settlement_state if isinstance(self.settlement_state, SettlementState) else SettlementState(self.settlement_state)
        object.__setattr__(self, "settlement_state", state)
        for field_name in (
            "expected_effects", "observed_effects", "sensorium_receipts",
            "vns_receipts", "arda_receipts", "seraph_receipts", "unexpected_effects",
        ):
            _tuple_strings(getattr(self, field_name), field_name=field_name)

    @property
    def settlement_digest(self) -> str:
        return digest_payload(self)

    def to_dict(self) -> dict[str, Any]:
        payload = _normalise(self)
        payload["settlement_digest"] = self.settlement_digest
        return payload


def phase1_contract_receipt(repo_root: str | Path) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    schema_paths = (
        "schemas/dio.metamorphic_unit.v1.json",
        "schemas/dio.world_lease.v1.json",
        "schemas/dio.world_settlement.v1.json",
    )
    parsed = []
    missing = []
    for relative in schema_paths:
        path = root / relative
        if not path.is_file():
            missing.append(relative)
            continue
        json.loads(path.read_text(encoding="utf-8"))
        parsed.append(relative)

    witness_states = tuple(state.value for state in LayerWitnessState)
    passed = not missing and len(parsed) == 3 and witness_states == (
        "EXERCISED", "CORROBORATED", "ARMED", "NOT_APPLICABLE", "MISSING", "FAILED"
    )
    return {
        "phase": 1,
        "acceptance": PHASE1_EXIT_TOKEN if passed else "DIO_METAMORPHIC_M1_CONTRACTS_BLOCKED",
        "passed": passed,
        "schema_count": len(parsed),
        "schemas": list(parsed),
        "missing": missing,
        "witness_states": list(witness_states),
        "digest_algorithm": "sha256",
        "contracts_are_frozen_dataclasses": True,
        "authority_semantics_reimplemented": False,
    }
