"""Phase 4 reality binding for the DIO Metamorphic Spine.

This module reuses BEAST DAI's canonical WorldStateSnapshot as the deterministic
reality object and binds a short-lived DIO WorldLease to that exact snapshot.
It does not replace Metatron's operational World Manifold and does not create
execution authority.

A lease is valid only while the exact live snapshot digest, epoch, policy
 generation, capability references and authority references remain unchanged.
Semantic similarity, copied digests, historical success, or narrative refresh
cannot renew a lease.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import importlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

from .contracts import WorldLease, digest_payload, parse_datetime
from .registry import build_reference_registry
from .semantic_law import phase3_semantic_receipt


PHASE4_EXIT_TOKEN = "DIO_METAMORPHIC_WORLD_LEASE_READY"
DEFAULT_CONFIG = "config/metamorphic_phase4_world_lease.json"


class WorldLeaseBindingError(RuntimeError):
    pass


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorldLeaseBindingError(f"cannot load Phase 4 source: {path}") from exc
    if not isinstance(value, dict):
        raise WorldLeaseBindingError(f"Phase 4 source must be an object: {path}")
    return value


def _file_digest(path: Path) -> str:
    if not path.is_file():
        raise WorldLeaseBindingError(f"required world-state anchor missing: {path}")
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _utc_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _load_dai_snapshot_class(root: Path, config: Mapping[str, Any]) -> type:
    dai_root = root / str(config["dai_root"])
    if not dai_root.is_dir():
        raise WorldLeaseBindingError(f"DAI root missing: {dai_root}")
    path = str(dai_root)
    if path not in sys.path:
        sys.path.insert(0, path)
    module = importlib.import_module("app.kernel.dai.contracts")
    cls = getattr(module, "WorldStateSnapshot", None)
    if cls is None:
        raise WorldLeaseBindingError("BEAST DAI WorldStateSnapshot is unavailable")
    return cls


def world_anchor_digests(root: Path, config: Mapping[str, Any]) -> dict[str, str]:
    keys = (
        "dai_contract_path",
        "dai_world_state_path",
        "world_manifold_path",
        "world_model_path",
        "seraph_world_recheck_path",
    )
    return {key: _file_digest(root / str(config[key])) for key in keys}


def build_controlled_world_snapshot(
    repo_root: str | Path,
    *,
    now: datetime | None = None,
) -> Any:
    """Create a controlled tested-world snapshot using the canonical DAI class.

    This is a Phase 4 mechanism proof, not a claim that the full operational
    Metatron manifold was executed in this test run.
    """
    root = Path(repo_root).resolve()
    config = _load_json(root / DEFAULT_CONFIG)
    phase3 = phase3_semantic_receipt(root)
    if phase3.get("acceptance") != config.get("required_phase3_acceptance") or phase3.get("passed") is not True:
        raise WorldLeaseBindingError("Phase 3 semantic law is not verified")

    registry = build_reference_registry(root)
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).replace(microsecond=0)
    lease_seconds = int(config.get("lease_seconds") or 0)
    if lease_seconds <= 0:
        raise WorldLeaseBindingError("lease_seconds must be positive")
    expires = current + timedelta(seconds=lease_seconds)

    Snapshot = _load_dai_snapshot_class(root, config)
    facts = {
        "phase3_acceptance": phase3["acceptance"],
        "phase3_semantic_law_digests": {
            row["unit_id"]: row["semantic_law_digest"] for row in phase3["units"]
        },
        "metamorphic_registry_fingerprint": registry.registry_fingerprint,
        "registered_unit_digests": {
            unit.unit_id: unit.unit_digest for unit in registry.units()
        },
        "authority_ceiling": config["authority_ceiling"],
        "external_effects_authority": config["external_effects_authority"],
        "operational_manifold_executed": bool(config.get("operational_manifold_executed", False)),
    }
    return Snapshot(
        snapshot_id=str(config["controlled_snapshot_id"]),
        epoch_id=str(config["controlled_epoch_id"]),
        facts=facts,
        observed_at=_utc_iso(current),
        expires_at=_utc_iso(expires),
        policy_generation=str(config["policy_generation"]),
    )


def _authority_ref(authority_ceiling: str, external_effects_authority: str) -> str:
    return digest_payload(
        {
            "authority_ceiling": authority_ceiling,
            "external_effects_authority": external_effects_authority,
        }
    )


def acquire_world_lease(
    repo_root: str | Path,
    *,
    snapshot: Any,
    composition_id: str,
    capability_refs: Sequence[str] | None = None,
    authority_refs: Sequence[str] | None = None,
) -> WorldLease:
    root = Path(repo_root).resolve()
    config = _load_json(root / DEFAULT_CONFIG)
    if not getattr(snapshot, "is_current")():
        raise WorldLeaseBindingError("cannot acquire lease from expired world snapshot")

    observed = parse_datetime(snapshot.observed_at, field_name="snapshot.observed_at")
    snapshot_expires = parse_datetime(snapshot.expires_at, field_name="snapshot.expires_at")
    requested_expires = observed + timedelta(seconds=int(config["lease_seconds"]))
    lease_expires = min(snapshot_expires, requested_expires)

    registry = build_reference_registry(root)
    caps = tuple(capability_refs or (unit.unit_digest for unit in registry.units()))
    auth = tuple(
        authority_refs
        or (
            _authority_ref(
                str(config["authority_ceiling"]),
                str(config["external_effects_authority"]),
            ),
        )
    )
    lease_id = "lease:" + digest_payload(
        {
            "composition_id": composition_id,
            "snapshot_digest": snapshot.snapshot_digest,
            "epoch_id": snapshot.epoch_id,
            "policy_generation": snapshot.policy_generation,
            "capability_refs": caps,
            "authority_refs": auth,
        }
    ).split(":", 1)[1][:24]

    return WorldLease(
        lease_id=lease_id,
        composition_id=composition_id,
        snapshot_digest=snapshot.snapshot_digest,
        epoch_id=snapshot.epoch_id,
        observed_at=snapshot.observed_at,
        expires_at=_utc_iso(lease_expires),
        policy_generation=snapshot.policy_generation,
        facts_refs=(digest_payload(snapshot.facts),),
        capability_refs=caps,
        authority_refs=auth,
    )


@dataclass(frozen=True, slots=True)
class WorldLeaseValidation:
    valid: bool
    gates: Mapping[str, bool]
    red_gates: tuple[str, ...]
    lease_digest: str
    live_snapshot_digest: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "gates": dict(self.gates),
            "red_gates": list(self.red_gates),
            "lease_digest": self.lease_digest,
            "live_snapshot_digest": self.live_snapshot_digest,
        }


def validate_world_lease(
    lease: WorldLease,
    *,
    live_snapshot: Any,
    live_capability_refs: Sequence[str],
    live_authority_refs: Sequence[str],
    now: datetime | None = None,
) -> WorldLeaseValidation:
    current = now or datetime.now(timezone.utc)
    gates = {
        "lease_not_expired": lease.is_current(now=current),
        "live_snapshot_current": bool(live_snapshot.is_current(now=current)),
        "snapshot_digest_exact": lease.snapshot_digest == live_snapshot.snapshot_digest,
        "epoch_exact": lease.epoch_id == live_snapshot.epoch_id,
        "policy_generation_exact": lease.policy_generation == live_snapshot.policy_generation,
        "facts_exact": tuple(lease.facts_refs) == (digest_payload(live_snapshot.facts),),
        "capability_refs_exact": tuple(lease.capability_refs) == tuple(live_capability_refs),
        "authority_refs_exact": tuple(lease.authority_refs) == tuple(live_authority_refs),
    }
    red = tuple(name for name, passed in gates.items() if not passed)
    return WorldLeaseValidation(
        valid=not red,
        gates=gates,
        red_gates=red,
        lease_digest=lease.lease_digest,
        live_snapshot_digest=live_snapshot.snapshot_digest,
    )


def require_world_lease_current(
    lease: WorldLease,
    *,
    live_snapshot: Any,
    live_capability_refs: Sequence[str],
    live_authority_refs: Sequence[str],
    now: datetime | None = None,
) -> WorldLeaseValidation:
    validation = validate_world_lease(
        lease,
        live_snapshot=live_snapshot,
        live_capability_refs=live_capability_refs,
        live_authority_refs=live_authority_refs,
        now=now,
    )
    if not validation.valid:
        raise WorldLeaseBindingError(f"world lease invalid: {validation.red_gates}")
    return validation


def phase4_world_lease_receipt(repo_root: str | Path) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    config = _load_json(root / DEFAULT_CONFIG)
    anchors = world_anchor_digests(root, config)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    snapshot = build_controlled_world_snapshot(root, now=now)
    registry = build_reference_registry(root)
    caps = tuple(unit.unit_digest for unit in registry.units())
    auth = (
        _authority_ref(str(config["authority_ceiling"]), str(config["external_effects_authority"])),
    )
    lease = acquire_world_lease(
        root,
        snapshot=snapshot,
        composition_id="phase4-controlled-composition",
        capability_refs=caps,
        authority_refs=auth,
    )
    validation = require_world_lease_current(
        lease,
        live_snapshot=snapshot,
        live_capability_refs=caps,
        live_authority_refs=auth,
        now=now,
    )
    passed = validation.valid and len(anchors) == 5
    return {
        "phase": 4,
        "acceptance": PHASE4_EXIT_TOKEN if passed else "DIO_METAMORPHIC_WORLD_LEASE_BLOCKED",
        "passed": passed,
        "world_snapshot_class": "app.kernel.dai.contracts.WorldStateSnapshot",
        "dai_world_state_reused": True,
        "operational_world_manifold_anchor_bound": True,
        "operational_world_manifold_executed": False,
        "world_anchor_digests": anchors,
        "snapshot_digest": snapshot.snapshot_digest,
        "lease_digest": lease.lease_digest,
        "epoch_id": lease.epoch_id,
        "policy_generation": lease.policy_generation,
        "lease_current": validation.valid,
        "exact_snapshot_digest_required": True,
        "exact_epoch_required": True,
        "exact_policy_generation_required": True,
        "capability_and_authority_refs_bound": True,
        "semantic_or_narrative_refresh_authorized": False,
        "authority_widened": False,
        "new_world_state_engine_created": False,
        "resolver_policy_implemented": False,
        "composition_dag_implemented": False,
    }
