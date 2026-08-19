"""DIO ATLAS source-bound semantic registry.

ATLAS is deliberately separate from the execution-grade Metamorphic Registry.
External taxonomy nodes, portfolio incarnations, and analogical relationships are
knowledge. Only capability signatures that bind back to a verified MetamorphicUnit
may be used as execution-corroborated mechanical coverage.
"""
from __future__ import annotations

from dataclasses import dataclass
import csv
from pathlib import Path
from typing import Any, Iterable, Mapping

from metamorphic.registry import build_reference_registry
from products.funding_proposal_studio import build_funding_proposal_metamorphic_unit


ATLAS_FOUNDATION_TOKEN = "DIO_ATLAS_M4_FOUNDATION_READY"
ATLAS_BLOCKED_TOKEN = "DIO_ATLAS_M4_FOUNDATION_BLOCKED"
ATLAS_CONFIG_ROOT = "config/atlas"

SOURCE_FILE = "dio_atlas_source_federation.csv"
PRIMITIVE_FILE = "dio_atlas_work_primitives.csv"
PATTERN_FILE = "dio_atlas_work_pattern_crosswalk.csv"
DOMAIN_FILE = "dio_atlas_universal_domain_registry.csv"
INCARNATION_FILE = "dio_meta_incarnation_crosswalk.csv"
SIGNATURE_FILE = "dio_atlas_capability_signatures.csv"
PIVOT_GAUNTLET_FILE = "dio_atlas_pivot_gauntlet.csv"

CANONICAL_WORK_PATTERNS = tuple(f"WP{index:02d}" for index in range(1, 13))
CANDIDATE_WORK_PATTERNS = ("WP13",)
EXPECTED_M1_CAPABILITIES = {
    "professional_correspondence": "professional_correspondence_studio",
    "finance_readiness": "finance_readiness_studio",
    "article_publication": "article_publication_studio",
    "funding_proposal_pack": "funding_proposal_studio",
}


class AtlasRegistryError(RuntimeError):
    pass


def _split(value: str | None) -> tuple[str, ...]:
    return tuple(item.strip() for item in str(value or "").split("|") if item.strip())


def _read_csv(path: Path) -> tuple[dict[str, str], ...]:
    if not path.is_file():
        raise AtlasRegistryError(f"ATLAS source missing: {path}")
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise AtlasRegistryError(f"ATLAS CSV has no header: {path}")
        rows = tuple({str(key): str(value or "") for key, value in row.items()} for row in reader)
    if not rows:
        raise AtlasRegistryError(f"ATLAS CSV has no rows: {path}")
    return rows


def _require_unique(rows: Iterable[Mapping[str, str]], key: str, *, label: str) -> None:
    values = [str(row.get(key) or "").strip() for row in rows]
    if any(not value for value in values):
        raise AtlasRegistryError(f"{label} contains empty {key}")
    if len(values) != len(set(values)):
        raise AtlasRegistryError(f"{label} contains duplicate {key}")


def _cost_category(score: float) -> str:
    if score < 1.5:
        return "LOW"
    if score < 2.5:
        return "LOW_MEDIUM"
    if score < 3.5:
        return "MEDIUM"
    if score < 4.5:
        return "HIGH"
    return "VERY_HIGH"


@dataclass(frozen=True, slots=True)
class AtlasCapabilitySignature:
    signature_id: str
    capability_id: str
    unit_id: str
    work_pattern_ids: tuple[str, ...]
    primitive_ids: tuple[str, ...]
    authority_ceiling: str
    execution_truth_class: str
    registry_binding: str
    analogy_state: str

    @property
    def primitive_set(self) -> frozenset[str]:
        return frozenset(self.primitive_ids)


@dataclass(frozen=True, slots=True)
class AtlasRegistry:
    repo_root: Path
    sources: tuple[dict[str, str], ...]
    primitives: tuple[dict[str, str], ...]
    work_patterns: tuple[dict[str, str], ...]
    domains: tuple[dict[str, str], ...]
    incarnations: tuple[dict[str, str], ...]
    signatures: tuple[AtlasCapabilitySignature, ...]
    pivot_tasks: tuple[dict[str, str], ...]

    @classmethod
    def load(cls, repo_root: str | Path) -> "AtlasRegistry":
        root = Path(repo_root).resolve()
        cfg = root / ATLAS_CONFIG_ROOT
        sources = _read_csv(cfg / SOURCE_FILE)
        primitives = _read_csv(cfg / PRIMITIVE_FILE)
        work_patterns = _read_csv(cfg / PATTERN_FILE)
        domains = _read_csv(cfg / DOMAIN_FILE)
        incarnations = _read_csv(cfg / INCARNATION_FILE)
        signature_rows = _read_csv(cfg / SIGNATURE_FILE)
        pivot_tasks = _read_csv(cfg / PIVOT_GAUNTLET_FILE)
        signatures = tuple(
            AtlasCapabilitySignature(
                signature_id=row["signature_id"],
                capability_id=row["capability_id"],
                unit_id=row["unit_id"],
                work_pattern_ids=_split(row.get("work_pattern_ids")),
                primitive_ids=_split(row.get("primitive_ids")),
                authority_ceiling=row.get("authority_ceiling", ""),
                execution_truth_class=row.get("execution_truth_class", ""),
                registry_binding=row.get("registry_binding", ""),
                analogy_state=row.get("analogy_state", ""),
            )
            for row in signature_rows
        )
        registry = cls(
            repo_root=root,
            sources=sources,
            primitives=primitives,
            work_patterns=work_patterns,
            domains=domains,
            incarnations=incarnations,
            signatures=signatures,
            pivot_tasks=pivot_tasks,
        )
        registry.validate_structure()
        return registry

    @property
    def source_ids(self) -> frozenset[str]:
        return frozenset(row["source_id"] for row in self.sources)

    @property
    def primitive_ids(self) -> frozenset[str]:
        return frozenset(row["primitive_id"] for row in self.primitives)

    @property
    def work_pattern_ids(self) -> frozenset[str]:
        return frozenset(row["work_pattern_id"] for row in self.work_patterns)

    @property
    def domain_ids(self) -> frozenset[str]:
        return frozenset(row["domain_id"] for row in self.domains)

    @property
    def capability_ids(self) -> frozenset[str]:
        return frozenset(row.capability_id for row in self.signatures)

    @property
    def verified_primitive_ids(self) -> frozenset[str]:
        merged: set[str] = set()
        for signature in self.signatures:
            if signature.analogy_state != "EXECUTION_CORROBORATED":
                continue
            merged.update(signature.primitive_ids)
        return frozenset(merged)

    def domain(self, domain_id: str) -> Mapping[str, str]:
        for row in self.domains:
            if row["domain_id"] == domain_id:
                return row
        raise AtlasRegistryError(f"unknown ATLAS domain: {domain_id}")

    def task(self, task_id: str) -> Mapping[str, str]:
        for row in self.pivot_tasks:
            if row["task_id"] == task_id:
                return row
        raise AtlasRegistryError(f"unknown ATLAS pivot task: {task_id}")

    def validate_structure(self) -> None:
        _require_unique(self.sources, "source_id", label="source federation")
        _require_unique(self.primitives, "primitive_id", label="work primitives")
        _require_unique(self.work_patterns, "work_pattern_id", label="work-pattern crosswalk")
        _require_unique(self.domains, "domain_id", label="universal domain registry")
        _require_unique(self.incarnations, "incarnation", label="DIO META incarnation crosswalk")
        _require_unique(self.pivot_tasks, "task_id", label="pivot gauntlet")
        if len(self.sources) < 12:
            raise AtlasRegistryError("ATLAS source federation is too small")
        if len(self.primitives) < 50:
            raise AtlasRegistryError("ATLAS universal primitive vocabulary is too small")
        if len(self.domains) < 120:
            raise AtlasRegistryError("ATLAS broad domain seed must contain at least 120 nodes")
        if len(self.incarnations) != 53:
            raise AtlasRegistryError(f"DIO META crosswalk must contain exactly 53 incarnations, got {len(self.incarnations)}")
        if len(self.pivot_tasks) < 30:
            raise AtlasRegistryError("ATLAS pivot gauntlet requires at least 30 target jobs")

        source_ids = self.source_ids
        primitive_ids = self.primitive_ids
        pattern_ids = self.work_pattern_ids
        domain_ids = self.domain_ids

        canonical = tuple(
            row["work_pattern_id"]
            for row in self.work_patterns
            if row.get("canonical_status") == "CANONICAL"
        )
        if canonical != CANONICAL_WORK_PATTERNS:
            raise AtlasRegistryError(f"canonical work-pattern order diverged: {canonical}")
        candidate = tuple(
            row["work_pattern_id"]
            for row in self.work_patterns
            if row.get("canonical_status") == "CANDIDATE_EXTENSION"
        )
        if candidate != CANDIDATE_WORK_PATTERNS:
            raise AtlasRegistryError(f"candidate work-pattern set diverged: {candidate}")

        for row in self.sources:
            if row.get("capability_effect") != "NONE":
                raise AtlasRegistryError(f"external/source knowledge may not create capability: {row['source_id']}")

        for row in self.work_patterns:
            unknown = set(_split(row.get("primitive_ids"))) - primitive_ids
            if unknown:
                raise AtlasRegistryError(f"work pattern {row['work_pattern_id']} references unknown primitives: {sorted(unknown)}")

        for row in self.domains:
            parent = row.get("parent_domain_id", "").strip()
            if parent and parent not in domain_ids:
                raise AtlasRegistryError(f"domain {row['domain_id']} has unknown parent {parent}")
            unknown_sources = set(_split(row.get("source_systems"))) - source_ids
            if unknown_sources:
                raise AtlasRegistryError(f"domain {row['domain_id']} references unknown sources: {sorted(unknown_sources)}")
            unknown_patterns = set(_split(row.get("default_work_pattern_ids"))) - pattern_ids
            if unknown_patterns:
                raise AtlasRegistryError(f"domain {row['domain_id']} references unknown patterns: {sorted(unknown_patterns)}")
        if "D1800" not in domain_ids or self.domain("D1800").get("atlas_status") != "UNKNOWN_DOMAIN_TEST_ONLY":
            raise AtlasRegistryError("ATLAS unknown-domain proof node is missing")

        learning_rows = 0
        for row in self.incarnations:
            canonical_ids = set(_split(row.get("canonical_work_pattern_ids")))
            candidate_ids = set(_split(row.get("candidate_work_pattern_ids")))
            if canonical_ids - set(CANONICAL_WORK_PATTERNS):
                raise AtlasRegistryError(f"incarnation {row['incarnation']} launders a noncanonical work pattern")
            if candidate_ids - set(CANDIDATE_WORK_PATTERNS):
                raise AtlasRegistryError(f"incarnation {row['incarnation']} has unknown candidate pattern")
            source_labels = {item.strip() for item in row.get("source_work_patterns", "").split(";") if item.strip()}
            if "Learning" in source_labels:
                learning_rows += 1
                if "WP13" not in candidate_ids or "WP13" in canonical_ids:
                    raise AtlasRegistryError(f"Learning gap not explicitly preserved for {row['incarnation']}")
            build = float(row["build_burden"])
            validation = float(row["validation_burden"])
            score = float(row["capability_cost_score"])
            expected_score = (build + validation) / 2.0
            if abs(score - expected_score) > 1e-9:
                raise AtlasRegistryError(f"capability cost score drift for {row['incarnation']}")
            if row.get("capability_cost") != _cost_category(score):
                raise AtlasRegistryError(f"capability cost category drift for {row['incarnation']}")
            unknown_domains = set(_split(row.get("atlas_domain_ids"))) - domain_ids
            if unknown_domains:
                raise AtlasRegistryError(f"incarnation {row['incarnation']} references unknown domains: {sorted(unknown_domains)}")
        if learning_rows < 4:
            raise AtlasRegistryError("expected portfolio Learning-label gap is not represented")

        if {signature.capability_id for signature in self.signatures} != set(EXPECTED_M1_CAPABILITIES):
            raise AtlasRegistryError("ATLAS execution-grade signature set must match the four M1 reference capabilities")
        _require_unique(
            ({"signature_id": signature.signature_id} for signature in self.signatures),
            "signature_id",
            label="capability signatures",
        )
        for signature in self.signatures:
            if signature.unit_id != EXPECTED_M1_CAPABILITIES[signature.capability_id]:
                raise AtlasRegistryError(f"signature unit mismatch: {signature.capability_id}")
            if not signature.primitive_ids or set(signature.primitive_ids) - primitive_ids:
                raise AtlasRegistryError(f"signature primitive binding invalid: {signature.signature_id}")
            if set(signature.work_pattern_ids) - pattern_ids:
                raise AtlasRegistryError(f"signature work-pattern binding invalid: {signature.signature_id}")
            if signature.authority_ceiling != "controlled_artifact_only":
                raise AtlasRegistryError(f"ATLAS signature widened authority: {signature.signature_id}")
            if signature.analogy_state != "EXECUTION_CORROBORATED":
                raise AtlasRegistryError(f"M1 signature must remain execution-corroborated: {signature.signature_id}")

        for row in self.pivot_tasks:
            if row.get("domain_id") not in domain_ids:
                raise AtlasRegistryError(f"pivot task {row['task_id']} references unknown domain")
            if set(_split(row.get("required_work_pattern_ids"))) - pattern_ids:
                raise AtlasRegistryError(f"pivot task {row['task_id']} references unknown work pattern")
            if set(_split(row.get("required_primitive_ids"))) - primitive_ids:
                raise AtlasRegistryError(f"pivot task {row['task_id']} references unknown primitive")
            if row.get("external_effect_intent") not in {"NONE", "PUBLISH", "SEND", "SPEND", "PURCHASE", "DEPLOY", "DELIVER"}:
                raise AtlasRegistryError(f"pivot task {row['task_id']} has unknown external effect intent")

    def bind_execution_signatures(self) -> dict[str, dict[str, Any]]:
        """Bind ATLAS signatures back to exact runtime MetamorphicUnit identities.

        This is the constitutional bridge: ATLAS knowledge can describe a capability,
        but execution coverage exists only when the signature resolves to a current
        immutable MetamorphicUnit with the same exact exported capability and a
        non-widened authority ceiling.
        """
        base = build_reference_registry(self.repo_root)
        units = {unit.unit_id: unit for unit in base.units()}
        composite = build_funding_proposal_metamorphic_unit(self.repo_root)
        units[composite.unit_id] = composite
        bindings: dict[str, dict[str, Any]] = {}
        for signature in self.signatures:
            unit = units.get(signature.unit_id)
            if unit is None:
                raise AtlasRegistryError(f"signature runtime unit missing: {signature.unit_id}")
            if signature.capability_id not in unit.provides:
                raise AtlasRegistryError(
                    f"ATLAS signature {signature.signature_id} does not match runtime provides={unit.provides}"
                )
            if unit.authority_ceiling != signature.authority_ceiling:
                raise AtlasRegistryError(f"ATLAS signature authority ceiling drift: {signature.signature_id}")
            bindings[signature.capability_id] = {
                "signature_id": signature.signature_id,
                "capability_id": signature.capability_id,
                "unit_id": unit.unit_id,
                "unit_digest": unit.unit_digest,
                "executor_id": unit.executor_id,
                "executor_digest": unit.executor_digest,
                "authority_ceiling": unit.authority_ceiling,
                "roles": [role.value for role in unit.roles],
                "provides": list(unit.provides),
                "requires": list(unit.requires),
                "execution_truth_class": signature.execution_truth_class,
                "analogy_state": signature.analogy_state,
                "authority_created": False,
            }
        if set(bindings) != set(EXPECTED_M1_CAPABILITIES):
            raise AtlasRegistryError("execution-signature binding incomplete")
        return bindings


def atlas_foundation_receipt(repo_root: str | Path, *, verify_m2_parent: bool = True) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    registry = AtlasRegistry.load(root)
    bindings = registry.bind_execution_signatures()

    parent: dict[str, Any] = {
        "passed": False,
        "acceptance": "NOT_CHECKED",
        "m1_verified": False,
        "m2_final_verified": False,
        "m3_boundary_preserved": False,
    }
    if verify_m2_parent:
        from commercial_metabolism.final_verification import phase9_final_verification_receipt

        parent = phase9_final_verification_receipt(root)

    parent_ok = (
        (not verify_m2_parent)
        or (
            parent.get("passed") is True
            and parent.get("acceptance") == "DIO_METAMORPHIC_COMMERCIAL_METABOLISM_VERIFIED"
            and parent.get("m1_verified") is True
            and parent.get("m2_final_verified") is True
            and parent.get("m3_boundary_preserved") is True
            and parent.get("content_transform_dataflow_proved") is False
        )
    )
    all_source_knowledge_only = all(row.get("capability_effect") == "NONE" for row in registry.sources)
    learning_gap_preserved = all(
        "WP13" in _split(row.get("candidate_work_pattern_ids"))
        for row in registry.incarnations
        if "Learning" in {item.strip() for item in row.get("source_work_patterns", "").split(";") if item.strip()}
    )
    passed = (
        parent_ok
        and len(registry.incarnations) == 53
        and len(registry.primitives) >= 50
        and len(registry.domains) >= 120
        and len(registry.signatures) == 4
        and len(bindings) == 4
        and all_source_knowledge_only
        and learning_gap_preserved
    )
    return {
        "phase": "M4-0",
        "acceptance": ATLAS_FOUNDATION_TOKEN if passed else ATLAS_BLOCKED_TOKEN,
        "passed": passed,
        "parent_acceptance": parent.get("acceptance"),
        "m1_verified": parent.get("m1_verified") is True,
        "m2_verified": parent.get("m2_final_verified") is True,
        "m3_boundary_preserved": parent.get("m3_boundary_preserved") is True,
        "content_transform_dataflow_proved": False,
        "source_federation_count": len(registry.sources),
        "work_primitive_count": len(registry.primitives),
        "canonical_work_pattern_count": len(CANONICAL_WORK_PATTERNS),
        "candidate_work_pattern_count": len(CANDIDATE_WORK_PATTERNS),
        "learning_gap_preserved": learning_gap_preserved,
        "domain_seed_count": len(registry.domains),
        "portfolio_incarnation_crosswalk_count": len(registry.incarnations),
        "capability_signature_count": len(registry.signatures),
        "execution_signature_binding_count": len(bindings),
        "execution_signature_bindings": bindings,
        "pivot_gauntlet_task_count": len(registry.pivot_tasks),
        "all_external_taxonomy_knowledge_capability_effect_none": all_source_knowledge_only,
        "knowledge_is_capability": False,
        "similarity_is_equivalence": False,
        "analogy_is_evidence": False,
        "domain_adjacency_is_market_demand": False,
        "task_match_is_execution_proof": False,
        "taxonomy_membership_mints_authority": False,
        "authority_created": False,
        "authority_widened": False,
        "external_effects": False,
        "new_runtime_engine_created": False,
        "m4_final_verified": False,
    }


__all__ = [
    "ATLAS_BLOCKED_TOKEN",
    "ATLAS_CONFIG_ROOT",
    "ATLAS_FOUNDATION_TOKEN",
    "AtlasCapabilitySignature",
    "AtlasRegistry",
    "AtlasRegistryError",
    "CANONICAL_WORK_PATTERNS",
    "CANDIDATE_WORK_PATTERNS",
    "EXPECTED_M1_CAPABILITIES",
    "atlas_foundation_receipt",
]
