"""Phase 3 LINGUA semantic law for the DIO Metamorphic Spine.

This layer binds meaning to an already-registered MetamorphicUnit. It does not
clone units, resolve compositions, execute BEAST learning, or create authority.

Semantic law is deliberately split into four machine-readable layers:

DENOTATION   what the unit is
AFFORDANCE   what source-bound capabilities it can contribute
PROHIBITION  what it cannot do or truthfully claim
PROJECTION   how the same meaning may be presented by role/context

Learning hooks are declared here, but learning output remains candidate-only and
cannot flow directly into execution. BEAST remains the crystallization authority.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from .contracts import MetamorphicUnit, digest_payload
from .registry import MetamorphicRegistryError, build_reference_registry


PHASE3_EXIT_TOKEN = "DIO_METAMORPHIC_LINGUA_SEMANTIC_LAW_PROVED"
DEFAULT_CONFIG = "config/metamorphic_phase3_semantic_law.json"


class SemanticLawError(RuntimeError):
    pass


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SemanticLawError(f"cannot load semantic-law JSON source: {path}") from exc
    if not isinstance(payload, dict):
        raise SemanticLawError(f"semantic-law JSON source must be an object: {path}")
    return payload


def _file_digest(path: Path) -> str:
    if not path.is_file():
        raise SemanticLawError(f"semantic-law source missing: {path}")
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _slug_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _nonempty(value: Any, *, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise SemanticLawError(f"{field_name} is required")
    return text


@dataclass(frozen=True, slots=True)
class SemanticLaw:
    unit_id: str
    unit_digest: str
    source_digest: str
    lingua_anchor_digests: Mapping[str, str]
    denotation: Mapping[str, Any]
    affordances: tuple[Mapping[str, Any], ...]
    prohibitions: tuple[Mapping[str, Any], ...]
    projections: Mapping[str, Mapping[str, Any]]
    learning_contract: Mapping[str, Any]
    evidence_refs: tuple[str, ...]
    authority_ceiling: str
    schema: str = "dio.lingua.metamorphic_semantic_law.v1"

    @property
    def law_digest(self) -> str:
        return digest_payload(self)

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "schema": self.schema,
            "unit_id": self.unit_id,
            "unit_digest": self.unit_digest,
            "source_digest": self.source_digest,
            "lingua_anchor_digests": dict(self.lingua_anchor_digests),
            "denotation": dict(self.denotation),
            "affordances": [dict(row) for row in self.affordances],
            "prohibitions": [dict(row) for row in self.prohibitions],
            "projections": {key: dict(value) for key, value in self.projections.items()},
            "learning_contract": dict(self.learning_contract),
            "evidence_refs": list(self.evidence_refs),
            "authority_ceiling": self.authority_ceiling,
        }
        payload["law_digest"] = self.law_digest
        return payload


def _lingua_anchors(root: Path, config: dict[str, Any]) -> dict[str, str]:
    anchors = config.get("lingua_anchors")
    if not isinstance(anchors, list) or not anchors:
        raise SemanticLawError("lingua_anchors must be configured")
    result: dict[str, str] = {}
    for relative in anchors:
        rel = _nonempty(relative, field_name="lingua_anchor")
        result[rel] = _file_digest(root / rel)
    return result


def _professional_proof(root: Path, config: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    proof_rel = _nonempty(config.get("professional_proof_path"), field_name="professional_proof_path")
    proof_path = root / proof_rel
    proof = _load_json(proof_path)
    required = _nonempty(
        config.get("required_professional_acceptance_token"),
        field_name="required_professional_acceptance_token",
    )
    if proof.get("acceptance_token") != required or proof.get("all_professional_tasks_verified") is not True:
        raise SemanticLawError("professional proof is not accepted for Phase 3")
    if proof.get("authority_created") is not False or proof.get("external_effects") is not False:
        raise SemanticLawError("professional proof violates semantic authority boundary")
    return proof_rel, proof


def _manifest_for_unit(root: Path, unit: MetamorphicUnit) -> tuple[str, dict[str, Any]]:
    manifest_rel = _nonempty(unit.input_contract.get("source_manifest"), field_name="source_manifest")
    manifest = _load_json(root / manifest_rel)
    if manifest.get("studio_id") != unit.unit_id:
        raise SemanticLawError(f"semantic source identity mismatch for {unit.unit_id}")
    return manifest_rel, manifest


def _denotation(unit: MetamorphicUnit, manifest: dict[str, Any]) -> dict[str, Any]:
    artifact = manifest.get("artifact_contract") or {}
    job = manifest.get("job") or {}
    purpose = _nonempty(
        artifact.get("purpose") or manifest.get("name") or unit.unit_id,
        field_name=f"{unit.unit_id}.purpose",
    )
    return {
        "name": _nonempty(manifest.get("name") or unit.unit_id, field_name=f"{unit.unit_id}.name"),
        "purpose": purpose,
        "buyer": str(job.get("buyer") or "").strip(),
        "source_request": str(job.get("request") or "").strip(),
        "artifact_kind": _nonempty(artifact.get("kind"), field_name=f"{unit.unit_id}.artifact_kind"),
        "maturity_state": unit.maturity_state,
        "authority_ceiling": unit.authority_ceiling,
    }


def _affordances(unit: MetamorphicUnit, manifest: dict[str, Any]) -> tuple[Mapping[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    for capability in unit.provides:
        rows.append(
            {
                "id": f"export.{capability}",
                "capability": capability,
                "scope": "exported_metamorphic_capability",
                "source": "metamorphic_unit.provides",
                "claim_state": "SUPPORTED",
            }
        )
    required_organs = manifest.get("required_organs")
    if not isinstance(required_organs, list) or not required_organs:
        raise SemanticLawError(f"{unit.unit_id} has no source-bound organ capabilities")
    for organ in required_organs:
        if not isinstance(organ, dict):
            raise SemanticLawError(f"{unit.unit_id} required_organs entry is invalid")
        engine_id = _nonempty(organ.get("engine_id"), field_name="engine_id")
        source_ref = _nonempty(organ.get("source_ref"), field_name="source_ref")
        capabilities = organ.get("capabilities") or []
        if not isinstance(capabilities, list) or not capabilities:
            raise SemanticLawError(f"{unit.unit_id}:{engine_id} has no declared capabilities")
        for capability in capabilities:
            cap = _nonempty(capability, field_name=f"{engine_id}.capability")
            rows.append(
                {
                    "id": f"organ.{engine_id}.{cap}",
                    "capability": cap,
                    "engine_id": engine_id,
                    "scope": "source_bound_organ_capability",
                    "source": source_ref,
                    "claim_state": "SUPPORTED_WITHIN_UNIT_CONTRACT",
                }
            )
    return tuple(rows)


def _source_prohibitions(unit: MetamorphicUnit, manifest: dict[str, Any]) -> list[dict[str, Any]]:
    artifact = manifest.get("artifact_contract") or {}
    result: list[dict[str, Any]] = []
    for key in ("forbidden_claims", "must_not_invent"):
        values = artifact.get(key) or []
        if not isinstance(values, list):
            raise SemanticLawError(f"{unit.unit_id}.{key} must be a list")
        for value in values:
            rule = _nonempty(value, field_name=f"{unit.unit_id}.{key}")
            result.append(
                {
                    "id": f"source.{key}.{_slug_digest(rule)}",
                    "kind": key,
                    "rule": rule,
                    "source": f"{unit.unit_id}.artifact_contract.{key}",
                    "claim_state": "REFUSE",
                }
            )
    return result


def _authority_prohibitions(
    unit: MetamorphicUnit,
    manifest: dict[str, Any],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    authority = manifest.get("authority")
    if not isinstance(authority, dict):
        raise SemanticLawError(f"{unit.unit_id} has no authority block")
    result: list[dict[str, Any]] = []
    rows = config.get("authority_prohibitions")
    if not isinstance(rows, list) or not rows:
        raise SemanticLawError("authority_prohibitions must be configured")
    for row in rows:
        if not isinstance(row, dict):
            raise SemanticLawError("authority prohibition must be an object")
        key = _nonempty(row.get("manifest_key"), field_name="manifest_key")
        required = _nonempty(row.get("required_state"), field_name="required_state")
        if authority.get(key) != required:
            raise SemanticLawError(
                f"{unit.unit_id} authority state for {key} is {authority.get(key)!r}, expected {required!r}"
            )
        result.append(
            {
                "id": _nonempty(row.get("id"), field_name="authority_prohibition.id"),
                "kind": "authority_boundary",
                "rule": _nonempty(row.get("rule"), field_name="authority_prohibition.rule"),
                "source": f"{unit.unit_id}.authority.{key}",
                "source_state": required,
                "claim_state": "REFUSE",
            }
        )
    return result


def _professional_prohibitions(
    proof: dict[str, Any],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    rows = config.get("professional_claim_boundaries")
    if not isinstance(rows, list) or not rows:
        raise SemanticLawError("professional_claim_boundaries must be configured")
    for row in rows:
        if not isinstance(row, dict):
            raise SemanticLawError("professional claim boundary must be an object")
        field = _nonempty(row.get("proof_field"), field_name="proof_field")
        blocked = _nonempty(row.get("blocked_state"), field_name="blocked_state")
        if proof.get(field) != blocked:
            raise SemanticLawError(
                f"professional proof field {field} changed from expected Phase-3 boundary {blocked!r}"
            )
        result.append(
            {
                "id": _nonempty(row.get("id"), field_name="professional_claim_boundary.id"),
                "kind": "professional_proof_boundary",
                "rule": _nonempty(row.get("rule"), field_name="professional_claim_boundary.rule"),
                "source": f"professional_task_gauntlet.{field}",
                "source_state": blocked,
                "claim_state": "REFUSE",
            }
        )
    return result


def _verified_case_count(unit_id: str, proof: dict[str, Any]) -> int:
    summary = (proof.get("studio_summary") or {}).get(unit_id)
    if not isinstance(summary, dict):
        raise SemanticLawError(f"professional proof has no studio summary for {unit_id}")
    count = int(summary.get("verified_count") or 0)
    if count < 3:
        raise SemanticLawError(f"{unit_id} has fewer than three verified professional cases")
    return count


def _projections(
    unit: MetamorphicUnit,
    manifest: dict[str, Any],
    denotation: dict[str, Any],
    verified_cases: int,
) -> dict[str, Mapping[str, Any]]:
    name = denotation["name"]
    purpose = denotation["purpose"]
    buyer = denotation["buyer"]
    common = {
        "unit_id": unit.unit_id,
        "unit_digest": unit.unit_digest,
        "authority_ceiling": unit.authority_ceiling,
        "human_authority_required": True,
        "external_authority_created": False,
    }
    return {
        "direct_product": {
            **common,
            "title": name,
            "audience": buyer,
            "meaning": purpose,
            "proof_language": (
                f"Controlled professional-task execution is verified across {verified_cases} "
                "current normal, messy and adversarial fixtures for this Studio."
            ),
            "commercial_boundary": "Professional quality is not customer acceptance, willingness to pay, or commercial validation.",
        },
        "nested_capability": {
            **common,
            "title": f"{name} capability",
            "meaning": f"Contribute {purpose.rstrip('.').lower()} inside a larger governed composition.",
            "identity_rule": "Nested use preserves the same unit identity, executor, evidence contract, quality contract and authority ceiling.",
        },
        "technical_proof": {
            **common,
            "source_manifest": unit.input_contract.get("source_manifest"),
            "executor_id": unit.executor_id,
            "executor_digest": unit.executor_digest,
            "professional_proof_digest": unit.evidence_contract.get("professional_proof_digest"),
            "verified_case_count": verified_cases,
        },
    }


def build_semantic_law(
    repo_root: str | Path,
    unit: MetamorphicUnit,
    *,
    config_path: str | Path = DEFAULT_CONFIG,
) -> SemanticLaw:
    root = Path(repo_root).resolve()
    config = _load_json(root / config_path)
    if config.get("schema") != "dio.metamorphic_phase3_semantic_law_config.v1":
        raise SemanticLawError("unsupported Phase 3 semantic-law config schema")
    if config.get("site_studio_reference_excluded") is not True:
        raise SemanticLawError("Phase 3 must explicitly exclude Site Studio")
    if unit.unit_id == "site_studio":
        raise SemanticLawError("Site Studio is not eligible for the Phase 3 reference proof")

    manifest_rel, manifest = _manifest_for_unit(root, unit)
    proof_rel, proof = _professional_proof(root, config)
    anchors = _lingua_anchors(root, config)
    denotation = _denotation(unit, manifest)
    affordances = _affordances(unit, manifest)
    verified_cases = _verified_case_count(unit.unit_id, proof)

    prohibitions = _source_prohibitions(unit, manifest)
    prohibitions.extend(_authority_prohibitions(unit, manifest, config))
    prohibitions.extend(_professional_prohibitions(proof, config))
    prohibitions.append(
        {
            "id": "semantic.no_authority_minting",
            "kind": "constitutional",
            "rule": "Semantic interpretation, projection, reuse or learning may never mint execution authority.",
            "source": "DIO metamorphic semantic law",
            "claim_state": "REFUSE",
        }
    )

    learning_contract = config.get("learning_contract")
    if not isinstance(learning_contract, dict):
        raise SemanticLawError("learning_contract must be configured")
    required_learning = {
        "semantic_observations_may_be_recorded": True,
        "learning_outputs_are_candidates_only": True,
        "direct_learning_to_execution": False,
        "crystallization_authority": "BEAST",
        "human_approval_required_for_promoted_meaning": True,
        "market_feedback_learning_deferred": True,
    }
    if any(learning_contract.get(key) != value for key, value in required_learning.items()):
        raise SemanticLawError("Phase 3 learning contract violates DIO learning/authority law")

    evidence_refs = (
        manifest_rel,
        proof_rel,
        *tuple(sorted(anchors)),
    )
    return SemanticLaw(
        unit_id=unit.unit_id,
        unit_digest=unit.unit_digest,
        source_digest=unit.source_digest,
        lingua_anchor_digests=anchors,
        denotation=denotation,
        affordances=affordances,
        prohibitions=tuple(prohibitions),
        projections=_projections(unit, manifest, denotation, verified_cases),
        learning_contract=dict(learning_contract),
        evidence_refs=evidence_refs,
        authority_ceiling=unit.authority_ceiling,
    )


def build_reference_semantic_laws(
    repo_root: str | Path,
    *,
    config_path: str | Path = DEFAULT_CONFIG,
) -> dict[str, SemanticLaw]:
    root = Path(repo_root).resolve()
    registry = build_reference_registry(root)
    return {
        unit.unit_id: build_semantic_law(root, unit, config_path=config_path)
        for unit in registry.units()
    }


def project_semantics(law: SemanticLaw, context: str) -> Mapping[str, Any]:
    try:
        return law.projections[context]
    except KeyError as exc:
        raise SemanticLawError(f"unsupported semantic projection context: {context}") from exc


def evaluate_claim(law: SemanticLaw, claim_id: str) -> dict[str, Any]:
    claim = _nonempty(claim_id, field_name="claim_id")
    for row in law.prohibitions:
        if row.get("id") == claim:
            return {
                "claim_id": claim,
                "verdict": "REFUSE",
                "reason": row.get("rule"),
                "unit_id": law.unit_id,
                "unit_digest": law.unit_digest,
                "authority_created": False,
            }
    for row in law.affordances:
        if row.get("id") == claim:
            return {
                "claim_id": claim,
                "verdict": "SUPPORTED",
                "reason": row.get("scope"),
                "unit_id": law.unit_id,
                "unit_digest": law.unit_digest,
                "authority_created": False,
            }
    return {
        "claim_id": claim,
        "verdict": "UNRESOLVED",
        "reason": "No source-bound semantic rule supports or refuses this symbolic claim.",
        "unit_id": law.unit_id,
        "unit_digest": law.unit_digest,
        "authority_created": False,
    }


def phase3_semantic_receipt(repo_root: str | Path) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    try:
        registry = build_reference_registry(root)
        laws = build_reference_semantic_laws(root)
    except (SemanticLawError, MetamorphicRegistryError) as exc:
        return {
            "phase": 3,
            "acceptance": "DIO_METAMORPHIC_LINGUA_SEMANTIC_LAW_BLOCKED",
            "passed": False,
            "error": str(exc),
        }

    units: list[dict[str, Any]] = []
    all_valid = True
    for unit in registry.units():
        law = laws[unit.unit_id]
        prohibition_ids = {str(row.get("id")) for row in law.prohibitions}
        authority_boundaries = {
            "authority.external_publication",
            "authority.external_send",
            "authority.media_spend",
            "authority.payment",
        }
        proof_boundaries = {
            "proof.verified_payment",
            "proof.customers_will_pay",
            "proof.customer_acceptance",
            "proof.commercial_validation",
        }
        same_identity = law.unit_digest == unit.unit_digest and law.source_digest == unit.source_digest
        four_layers = bool(law.denotation and law.affordances and law.prohibitions and law.projections)
        authority_complete = authority_boundaries.issubset(prohibition_ids)
        proof_complete = proof_boundaries.issubset(prohibition_ids)
        projections_same_identity = all(
            projection.get("unit_id") == unit.unit_id
            and projection.get("unit_digest") == unit.unit_digest
            and projection.get("authority_ceiling") == unit.authority_ceiling
            and projection.get("external_authority_created") is False
            for projection in law.projections.values()
        )
        learning_safe = (
            law.learning_contract.get("learning_outputs_are_candidates_only") is True
            and law.learning_contract.get("direct_learning_to_execution") is False
            and law.learning_contract.get("crystallization_authority") == "BEAST"
        )
        unit_valid = all((same_identity, four_layers, authority_complete, proof_complete, projections_same_identity, learning_safe))
        all_valid = all_valid and unit_valid
        units.append(
            {
                "unit_id": unit.unit_id,
                "unit_digest": unit.unit_digest,
                "semantic_law_digest": law.law_digest,
                "same_unit_identity_preserved": same_identity,
                "denotation_bound": bool(law.denotation),
                "affordance_count": len(law.affordances),
                "prohibition_count": len(law.prohibitions),
                "projection_contexts": sorted(law.projections),
                "authority_prohibitions_complete": authority_complete,
                "professional_claim_boundaries_complete": proof_complete,
                "projections_preserve_identity_and_authority": projections_same_identity,
                "learning_candidate_only": law.learning_contract.get("learning_outputs_are_candidates_only") is True,
                "direct_learning_to_execution": law.learning_contract.get("direct_learning_to_execution"),
                "crystallization_authority": law.learning_contract.get("crystallization_authority"),
            }
        )

    expected = {
        "article_publication_studio",
        "finance_readiness_studio",
        "professional_correspondence_studio",
    }
    actual = set(laws)
    passed = all_valid and actual == expected and "site_studio" not in actual
    return {
        "phase": 3,
        "acceptance": PHASE3_EXIT_TOKEN if passed else "DIO_METAMORPHIC_LINGUA_SEMANTIC_LAW_BLOCKED",
        "passed": passed,
        "unit_count": len(units),
        "semantic_law_promoted": passed,
        "four_layer_semantic_model": ["DENOTATION", "AFFORDANCE", "PROHIBITION", "PROJECTION"],
        "same_unit_identity_preserved": all(row["same_unit_identity_preserved"] for row in units),
        "authority_widened": False,
        "new_engine_created": False,
        "site_studio_reference_excluded": True,
        "lingua_existing_organ_reused": True,
        "beast_crystallization_executed": False,
        "market_feedback_learning_executed": False,
        "resolver_policy_implemented": False,
        "composition_dag_implemented": False,
        "units": units,
    }
