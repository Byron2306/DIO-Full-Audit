"""Phase 2 registry for same-identity metamorphosis.

A registered unit is stored exactly once. Product and capability views return the
same immutable MetamorphicUnit object. No role projection may clone the unit,
change its executor/evidence contracts, or widen authority.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from .contracts import MetamorphicRole, MetamorphicUnit, digest_payload


PHASE2_EXIT_TOKEN = "DIO_METAMORPHIC_IDENTITY_PROVED"
DEFAULT_CONFIG = "config/metamorphic_phase2_units.json"


class MetamorphicRegistryError(RuntimeError):
    pass


def _file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MetamorphicRegistryError(f"cannot load JSON source: {path}") from exc
    if not isinstance(payload, dict):
        raise MetamorphicRegistryError(f"JSON source must be an object: {path}")
    return payload


def _validate_manifest_authority(manifest: dict[str, Any], required: dict[str, str]) -> None:
    actual = manifest.get("authority")
    if not isinstance(actual, dict):
        raise MetamorphicRegistryError("Studio manifest has no authority block")
    mismatches = {
        key: {"expected": value, "actual": actual.get(key)}
        for key, value in required.items()
        if actual.get(key) != value
    }
    if mismatches:
        raise MetamorphicRegistryError(f"Studio authority is not Phase-2-safe: {mismatches}")


def _validate_required_organs(root: Path, manifest: dict[str, Any]) -> tuple[str, ...]:
    refs: list[str] = []
    rows = manifest.get("required_organs")
    if not isinstance(rows, list) or not rows:
        raise MetamorphicRegistryError("Studio manifest has no required_organs")
    for row in rows:
        if not isinstance(row, dict):
            raise MetamorphicRegistryError("required_organs entries must be objects")
        ref = str(row.get("source_ref") or "").strip()
        if not ref:
            raise MetamorphicRegistryError("required organ has no source_ref")
        if not (root / ref).is_file():
            raise MetamorphicRegistryError(f"required organ source missing: {ref}")
        refs.append(ref)
    return tuple(refs)


def _source_prohibitions(manifest: dict[str, Any]) -> tuple[str, ...]:
    artifact = manifest.get("artifact_contract") or {}
    values: list[str] = []
    for key in ("forbidden_claims", "must_not_invent"):
        raw = artifact.get(key) or []
        if isinstance(raw, list):
            values.extend(str(item).strip() for item in raw if str(item).strip())
    # Phase 2 does not pretend the full semantic-law layer already exists.
    values.append("phase3_semantic_law_required_before_promoted_buyer_projection")
    return tuple(dict.fromkeys(values))


def build_unit_from_spec(
    *,
    repo_root: str | Path,
    spec: dict[str, Any],
    config: dict[str, Any],
) -> MetamorphicUnit:
    root = Path(repo_root).resolve()
    unit_id = str(spec.get("unit_id") or "").strip()
    manifest_rel = str(spec.get("manifest_path") or "").strip()
    if not unit_id or not manifest_rel:
        raise MetamorphicRegistryError("unit_id and manifest_path are required")

    manifest_path = root / manifest_rel
    if not manifest_path.is_file():
        raise MetamorphicRegistryError(f"manifest missing: {manifest_rel}")
    manifest = _load_json(manifest_path)
    if manifest.get("studio_id") != unit_id:
        raise MetamorphicRegistryError(
            f"registry identity mismatch: config={unit_id!r} manifest={manifest.get('studio_id')!r}"
        )

    required_authority = config.get("required_manifest_authority") or {}
    if not isinstance(required_authority, dict) or not required_authority:
        raise MetamorphicRegistryError("required_manifest_authority must be configured")
    _validate_manifest_authority(manifest, required_authority)
    organ_refs = _validate_required_organs(root, manifest)

    executor = config.get("executor") or {}
    executor_rel = str(executor.get("executor_path") or "").strip()
    executor_path = root / executor_rel
    if not executor_path.is_file():
        raise MetamorphicRegistryError(f"native executor missing: {executor_rel}")

    roles = tuple(MetamorphicRole(value) for value in (spec.get("roles") or []))
    if MetamorphicRole.PRODUCT not in roles or MetamorphicRole.CAPABILITY not in roles:
        raise MetamorphicRegistryError(f"{unit_id} must declare both product and capability roles in Phase 2")
    provides = tuple(str(value).strip() for value in (spec.get("provides") or []) if str(value).strip())
    if not provides:
        raise MetamorphicRegistryError(f"{unit_id} has no exported capability")

    artifact = manifest.get("artifact_contract") or {}
    kind = str(artifact.get("kind") or "").strip()
    purpose = str(artifact.get("purpose") or manifest.get("name") or unit_id).strip()
    if not kind:
        raise MetamorphicRegistryError(f"{unit_id} artifact kind is missing")

    return MetamorphicUnit(
        unit_id=unit_id,
        version=str(manifest.get("studio_version") or "1.0.0"),
        source_digest=_file_digest(manifest_path),
        roles=roles,
        provides=provides,
        requires=(),
        executor_id=str(executor.get("executor_id") or "").strip(),
        executor_version=str(executor.get("executor_version") or "").strip(),
        executor_digest=_file_digest(executor_path),
        input_contract={
            "source_manifest": manifest_rel,
            "source_job_request": (manifest.get("job") or {}).get("request"),
        },
        output_contract={
            "artifact_kind": kind,
            "controlled_artifact_only": True,
        },
        evidence_contract={
            "native_executor_path": executor_rel,
            "native_receipts_preserved": True,
            "required_organ_source_refs": organ_refs,
            "native_closure_truth_required": "NATIVE_MULTI_ORGAN_EXECUTION_PROVED",
        },
        quality_contract={
            "native_closure_required": True,
            "all_declared_capabilities_executed": True,
            "phase3_semantic_law_required": True,
        },
        semantic_contract={
            "denotation": [purpose],
            "affordances": list(provides),
            "prohibitions": list(_source_prohibitions(manifest)),
            "projections": {
                "internal": str(manifest.get("name") or unit_id),
                "phase2_status": "buyer projection not promoted until Phase 3 semantic law",
            },
        },
        buyer_projection={
            "default": str(manifest.get("name") or unit_id),
            "variants": {"phase2_status": "semantic_law_pending"},
        },
        maturity_state=str(config.get("maturity_state") or "native_multi_organ_execution_proved"),
        authority_ceiling=str(config.get("authority_ceiling") or "controlled_artifact_only"),
        applicability_fingerprints={
            "policy": (),
            "audience": (),
            "curriculum": (),
            "privacy": (),
            "market": (),
            "runtime": (),
        },
        promotion_rules={
            "human_authority_preserved": True,
            "external_effects_remain_refused": True,
            "role_projection_may_not_widen_authority": True,
            "phase3_semantic_law_required": True,
        },
    )


class MetamorphicRegistry:
    """One-object registry with role and capability indexes."""

    def __init__(self) -> None:
        self._units: dict[str, MetamorphicUnit] = {}
        self._roles: dict[MetamorphicRole, set[str]] = {role: set() for role in MetamorphicRole}
        self._capabilities: dict[str, set[str]] = {}

    def register(self, unit: MetamorphicUnit) -> MetamorphicUnit:
        existing = self._units.get(unit.unit_id)
        if existing is not None:
            if existing.unit_digest != unit.unit_digest:
                raise MetamorphicRegistryError(
                    f"unit identity conflict for {unit.unit_id}: existing and proposed contracts differ"
                )
            return existing

        self._units[unit.unit_id] = unit
        for role in unit.roles:
            self._roles[role].add(unit.unit_id)
        for capability in unit.provides:
            self._capabilities.setdefault(capability, set()).add(unit.unit_id)
        return unit

    def get(self, unit_id: str) -> MetamorphicUnit:
        try:
            return self._units[unit_id]
        except KeyError as exc:
            raise MetamorphicRegistryError(f"unknown metamorphic unit: {unit_id}") from exc

    def as_role(self, unit_id: str, role: MetamorphicRole | str) -> MetamorphicUnit:
        wanted = role if isinstance(role, MetamorphicRole) else MetamorphicRole(role)
        unit = self.get(unit_id)
        if wanted not in unit.roles:
            raise MetamorphicRegistryError(f"{unit_id} does not declare role {wanted.value}")
        # Critical Phase 2 law: return the stored object. Never clone or mutate it.
        return unit

    def units_for_role(self, role: MetamorphicRole | str) -> tuple[MetamorphicUnit, ...]:
        wanted = role if isinstance(role, MetamorphicRole) else MetamorphicRole(role)
        return tuple(self._units[unit_id] for unit_id in sorted(self._roles[wanted]))

    def providers_for(self, capability: str) -> tuple[MetamorphicUnit, ...]:
        ids = sorted(self._capabilities.get(capability, set()))
        return tuple(self._units[unit_id] for unit_id in ids)

    def units(self) -> tuple[MetamorphicUnit, ...]:
        return tuple(self._units[unit_id] for unit_id in sorted(self._units))

    @property
    def registry_fingerprint(self) -> str:
        return digest_payload(
            {
                "units": [
                    {"unit_id": unit.unit_id, "unit_digest": unit.unit_digest}
                    for unit in self.units()
                ]
            }
        )


def build_reference_registry(
    repo_root: str | Path,
    *,
    config_path: str | Path = DEFAULT_CONFIG,
) -> MetamorphicRegistry:
    root = Path(repo_root).resolve()
    config = _load_json(root / config_path)
    if config.get("schema") != "dio.metamorphic_phase2_reference_units.v1":
        raise MetamorphicRegistryError("unsupported Phase 2 registry config schema")
    if config.get("site_studio_reference_excluded") is not True:
        raise MetamorphicRegistryError("Phase 2 must explicitly exclude Site Studio as a reference unit")

    rows = config.get("units")
    if not isinstance(rows, list) or not rows:
        raise MetamorphicRegistryError("Phase 2 registry config has no units")

    registry = MetamorphicRegistry()
    for spec in rows:
        if not isinstance(spec, dict):
            raise MetamorphicRegistryError("unit specs must be objects")
        if spec.get("unit_id") == "site_studio":
            raise MetamorphicRegistryError("Site Studio is not eligible for the Phase 2 reference proof")
        registry.register(build_unit_from_spec(repo_root=root, spec=spec, config=config))
    return registry


def phase2_identity_receipt(repo_root: str | Path) -> dict[str, Any]:
    registry = build_reference_registry(repo_root)
    rows: list[dict[str, Any]] = []
    same_identity = True
    for unit in registry.units():
        product_view = registry.as_role(unit.unit_id, MetamorphicRole.PRODUCT)
        capability_view = registry.as_role(unit.unit_id, MetamorphicRole.CAPABILITY)
        object_same = product_view is capability_view is unit
        digest_same = product_view.unit_digest == capability_view.unit_digest == unit.unit_digest
        contract_same = (
            product_view.executor_digest == capability_view.executor_digest
            and product_view.evidence_contract == capability_view.evidence_contract
            and product_view.quality_contract == capability_view.quality_contract
            and product_view.authority_ceiling == capability_view.authority_ceiling
        )
        same_identity = same_identity and object_same and digest_same and contract_same
        rows.append(
            {
                "unit_id": unit.unit_id,
                "roles": [role.value for role in unit.roles],
                "provides": list(unit.provides),
                "unit_digest": unit.unit_digest,
                "source_digest": unit.source_digest,
                "executor_id": unit.executor_id,
                "executor_digest": unit.executor_digest,
                "same_object_across_roles": object_same,
                "same_digest_across_roles": digest_same,
                "same_executor_evidence_quality_authority": contract_same,
                "authority_ceiling": unit.authority_ceiling,
            }
        )

    expected = {
        "professional_correspondence_studio",
        "finance_readiness_studio",
        "article_publication_studio",
    }
    actual = {unit.unit_id for unit in registry.units()}
    passed = same_identity and actual == expected and "site_studio" not in actual
    return {
        "phase": 2,
        "acceptance": PHASE2_EXIT_TOKEN if passed else "DIO_METAMORPHIC_IDENTITY_BLOCKED",
        "passed": passed,
        "unit_count": len(rows),
        "same_unit_product_and_capability": same_identity,
        "registry_fingerprint": registry.registry_fingerprint,
        "units": rows,
        "site_studio_reference_excluded": True,
        "new_engine_created": False,
        "authority_widened": False,
        "resolver_policy_implemented": False,
        "semantic_law_promoted": False,
    }
