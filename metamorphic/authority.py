"""Authority propagation for Metamorphic compositions.

Phase 5 authority is intersection-only. A composition may become narrower than
its parent or children, never wider. Learning, semantic support and historical
success are not authority inputs.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .contracts import MetamorphicUnit, digest_payload


class AuthorityIntersectionError(RuntimeError):
    pass


EFFECT_KEYS = (
    "external_publication",
    "external_send",
    "media_spend",
    "payment",
)


def _load_manifest(root: Path, unit: MetamorphicUnit) -> dict[str, Any]:
    rel = str(unit.input_contract.get("source_manifest") or "").strip()
    if not rel:
        raise AuthorityIntersectionError(f"{unit.unit_id} has no source manifest")
    path = root / rel
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AuthorityIntersectionError(f"cannot load authority source for {unit.unit_id}: {rel}") from exc
    if not isinstance(value, dict) or value.get("studio_id") != unit.unit_id:
        raise AuthorityIntersectionError(f"authority source identity mismatch for {unit.unit_id}")
    return value


@dataclass(frozen=True, slots=True)
class AuthorityIntersection:
    effective_ceiling: str
    source_ceilings: tuple[str, ...]
    human_gate: str
    effect_decisions: Mapping[str, str]
    authority_widened: bool
    external_effects_authorized: bool
    learning_used_as_authority: bool = False

    @property
    def authority_digest(self) -> str:
        return digest_payload(self)

    def to_dict(self) -> dict[str, Any]:
        return {
            "effective_ceiling": self.effective_ceiling,
            "source_ceilings": list(self.source_ceilings),
            "human_gate": self.human_gate,
            "effect_decisions": dict(self.effect_decisions),
            "authority_widened": self.authority_widened,
            "external_effects_authorized": self.external_effects_authorized,
            "learning_used_as_authority": self.learning_used_as_authority,
            "authority_digest": self.authority_digest,
        }


def intersect_authority(
    *,
    repo_root: str | Path,
    units: Sequence[MetamorphicUnit],
    authority_policy: Mapping[str, Any],
) -> AuthorityIntersection:
    root = Path(repo_root).resolve()
    if not units:
        raise AuthorityIntersectionError("authority intersection requires at least one unit")

    order = tuple(str(value) for value in (authority_policy.get("authority_order_narrow_to_wide") or ()))
    if not order or len(set(order)) != len(order):
        raise AuthorityIntersectionError("authority order must be a unique non-empty sequence")
    rank = {value: index for index, value in enumerate(order)}

    parent = str(authority_policy.get("parent_authority_ceiling") or "").strip()
    world = str(authority_policy.get("world_authority_ceiling") or "").strip()
    human = str(authority_policy.get("human_policy_authority_ceiling") or "").strip()
    source_ceilings = (parent, world, human, *(unit.authority_ceiling for unit in units))
    unknown = [value for value in source_ceilings if value not in rank]
    if unknown:
        raise AuthorityIntersectionError(f"unknown authority ceilings: {unknown}")

    effective = min(source_ceilings, key=lambda value: rank[value])
    narrowest_source_rank = min(rank[value] for value in source_ceilings)
    widened = rank[effective] > narrowest_source_rank

    manifests = [_load_manifest(root, unit) for unit in units]
    effect_decisions: dict[str, str] = {}
    for key in EFFECT_KEYS:
        states = [str(authority_policy.get(key) or "REFUSE")]
        for manifest in manifests:
            authority = manifest.get("authority")
            if not isinstance(authority, dict):
                raise AuthorityIntersectionError(f"{manifest.get('studio_id')} has no authority block")
            states.append(str(authority.get(key) or "REFUSE"))
        # Intersection law: every participant must explicitly ALLOW before ALLOW can survive.
        effect_decisions[key] = "ALLOW" if all(state == "ALLOW" for state in states) else "REFUSE"

    human_states = [str(authority_policy.get("human_gate") or "NEEDS_YOU")]
    for manifest in manifests:
        human_states.append(str((manifest.get("authority") or {}).get("human_gate") or "NEEDS_YOU"))
    human_gate = "ALLOW" if all(state == "ALLOW" for state in human_states) else "NEEDS_YOU"

    return AuthorityIntersection(
        effective_ceiling=effective,
        source_ceilings=tuple(source_ceilings),
        human_gate=human_gate,
        effect_decisions=effect_decisions,
        authority_widened=widened,
        external_effects_authorized=any(value == "ALLOW" for value in effect_decisions.values()),
        learning_used_as_authority=False,
    )
