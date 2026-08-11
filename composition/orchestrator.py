from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator

from authority.canonical import (
    AuthorityPlaneError,
    validate_arda_execution_identity,
    validate_authority_receipt,
    validate_capability_lease,
    validate_valinor_authorization,
)
from executors.vertical import load_vertical_executor_registry
from fusion.contracts import validate_assertion
from products.governed_case import validate_case

ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = ROOT / "config" / "dio_composition_profiles.json"
PROFILE_SCHEMA_PATH = ROOT / "schemas" / "dio_composition_profiles.schema.json"
FUSION_BINDINGS_PATH = ROOT / "config" / "dio_fusion_bindings.json"

PLAN_SCHEMA = "dio.composition.plan.v1"
LEDGER_SCHEMA = "dio.composition.ledger.v1"
STAGE_RECEIPT_SCHEMA = "dio.composition.stage_receipt.v1"
FINAL_RECEIPT_SCHEMA = "dio.composition.receipt.v1"
VERTICAL_BUNDLE_SCHEMA = "dio.vertical_execution_bundle.v1"

STAGE_STATES = {"complete", "refuse", "needs_you", "needs_evidence", "skipped"}


class CompositionError(RuntimeError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _fingerprint(value: Mapping[str, Any], *, omit: tuple[str, ...] = ()) -> str:
    body = copy.deepcopy(dict(value))
    for field in omit:
        body.pop(field, None)
    return hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()


def _timestamp(value: str | None = None) -> str:
    if value:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise CompositionError("Composition timestamps must include a timezone.")
        return parsed.astimezone(timezone.utc).isoformat()
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _profile_index(payload: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row["profile_id"]): dict(row) for row in payload.get("profiles") or []}


def _stage_index(profile: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row["stage_id"]): dict(row) for row in profile.get("stages") or []}


def _validate_dag(profile: Mapping[str, Any]) -> None:
    stages = _stage_index(profile)
    if len(stages) != len(profile.get("stages") or []):
        raise CompositionError(f"Duplicate stage IDs in profile {profile.get('profile_id')}.")
    for stage_id, stage in stages.items():
        missing = [dep for dep in stage.get("depends_on") or [] if dep not in stages]
        if missing:
            raise CompositionError(f"Unknown dependencies for {stage_id}: {missing}")
        if stage_id in set(stage.get("depends_on") or []):
            raise CompositionError(f"Stage cannot depend on itself: {stage_id}")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(stage_id: str) -> None:
        if stage_id in visited:
            return
        if stage_id in visiting:
            raise CompositionError(f"Composition profile contains a dependency cycle at {stage_id}.")
        visiting.add(stage_id)
        for dep in stages[stage_id].get("depends_on") or []:
            visit(str(dep))
        visiting.remove(stage_id)
        visited.add(stage_id)

    for stage_id in stages:
        visit(stage_id)


def _validate_profile_semantics(payload: Mapping[str, Any]) -> None:
    laws = payload.get("laws") or {}
    required_laws = {
        "composition_has_no_authority",
        "same_case_required",
        "dependency_receipts_hash_bound",
        "required_stages_cannot_be_skipped",
        "machine_evidence_is_not_human_authority",
        "valinor_remains_sole_kernel_authority",
        "arda_remains_execution_identity_only",
        "external_execution_requires_wave5_bundle",
    }
    disabled = sorted(name for name in required_laws if laws.get(name) is not True)
    if disabled:
        raise CompositionError("Required composition laws are disabled: " + ",".join(disabled))

    bindings_payload = json.loads(FUSION_BINDINGS_PATH.read_text(encoding="utf-8"))
    bindings = bindings_payload.get("bindings") or {}
    profile_ids: set[str] = set()
    for profile in payload.get("profiles") or []:
        profile_id = str(profile.get("profile_id") or "")
        if not profile_id or profile_id in profile_ids:
            raise CompositionError(f"Duplicate or empty composition profile ID: {profile_id!r}")
        profile_ids.add(profile_id)
        _validate_dag(profile)
        for stage in profile.get("stages") or []:
            stage_kind = str(stage.get("stage_kind") or "")
            system_id = str(stage.get("system_id") or "")
            contracts = set(stage.get("accepted_contracts") or [])
            assertion_types = set(stage.get("accepted_assertion_types") or [])
            if "dio.fusion.assertion.v1" in contracts:
                if system_id not in bindings:
                    raise CompositionError(f"Fusion stage system is not bound in Wave 1: {system_id}")
                illegal = assertion_types - set(bindings[system_id])
                if illegal:
                    raise CompositionError(
                        f"Composition stage {stage.get('stage_id')} asks {system_id} for unbound assertion types: {sorted(illegal)}"
                    )
            if stage_kind == "human_authority" and contracts != {"dio.authority.receipt.v1"}:
                raise CompositionError("Human authority stages may accept only canonical authority receipts.")
            if stage_kind == "kernel_authority":
                if system_id != "valinor" or contracts != {"dio.valinor.authorization.v1"}:
                    raise CompositionError("Kernel authority stage must be canonical Valinor authorization only.")
            if stage_kind == "execution_identity":
                if system_id != "arda" or contracts != {"dio.arda.execution_identity.v1"}:
                    raise CompositionError("Execution identity stage must be canonical ARDA identity only.")
            if stage_kind == "vertical_execution" and contracts != {VERTICAL_BUNDLE_SCHEMA}:
                raise CompositionError("Vertical execution stage must accept the Wave 5 execution bundle only.")


def load_composition_profiles(path: Path | None = None) -> dict[str, Any]:
    config_path = path or PROFILE_PATH
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    schema = json.loads(PROFILE_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(payload)
    _validate_profile_semantics(payload)
    return payload


def _case_digest(case: Mapping[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(_canonical(case).encode("utf-8")).hexdigest()


def _validate_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
    if plan.get("schema") != PLAN_SCHEMA:
        raise CompositionError("Unsupported composition plan schema.")
    expected = _fingerprint(plan, omit=("fingerprint", "composition_id"))
    if plan.get("fingerprint") != expected or plan.get("composition_id") != f"COMP-{expected[:16].upper()}":
        raise CompositionError("Composition plan fingerprint mismatch.")
    profiles = load_composition_profiles()
    profile = _profile_index(profiles).get(str(plan.get("profile_id") or ""))
    if profile is None:
        raise CompositionError("Composition plan references an unknown profile.")
    if plan.get("registry_id") != profiles.get("registry_id"):
        raise CompositionError("Composition plan registry binding drifted.")
    if plan.get("stages") != profile.get("stages") or plan.get("final_state") != profile.get("final_state"):
        raise CompositionError("Composition plan no longer matches its registered profile.")
    return profile


def make_composition_ledger(
    case: dict[str, Any],
    *,
    profile_id: str,
    created_at: str | None = None,
) -> dict[str, Any]:
    validate_case(case)
    profiles = load_composition_profiles()
    profile = _profile_index(profiles).get(profile_id)
    if profile is None:
        raise CompositionError(f"Unknown composition profile: {profile_id}")
    created = _timestamp(created_at)
    plan: dict[str, Any] = {
        "schema": PLAN_SCHEMA,
        "registry_id": profiles["registry_id"],
        "profile_id": profile_id,
        "case_id": case["case_id"],
        "case_initial_digest": _case_digest(case),
        "final_state": profile["final_state"],
        "stages": copy.deepcopy(profile["stages"]),
        "created_at": created,
        "authority": {
            "composition_has_authority": False,
            "kernel_authority": "Valinor",
            "execution_identity_authority": "ARDA",
        },
    }
    plan["fingerprint"] = _fingerprint(plan, omit=("fingerprint", "composition_id"))
    plan["composition_id"] = f"COMP-{plan['fingerprint'][:16].upper()}"
    return {
        "schema": LEDGER_SCHEMA,
        "plan": plan,
        "state": "in_progress",
        "stage_receipts": [],
        "final_receipt": None,
    }


def _latest_receipts(ledger: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in ledger.get("stage_receipts") or []:
        latest[str(row["stage_id"])] = dict(row)
    return latest


def ready_stage_ids(ledger: Mapping[str, Any]) -> list[str]:
    validate_composition_ledger(dict(ledger))
    plan = ledger["plan"]
    latest = _latest_receipts(ledger)
    ready: list[str] = []
    for stage in plan.get("stages") or []:
        stage_id = str(stage["stage_id"])
        current = latest.get(stage_id)
        if current and current.get("status") == "complete":
            continue
        if current and current.get("status") in {"refuse", "needs_you", "needs_evidence"}:
            continue
        dependencies = [latest.get(str(dep)) for dep in stage.get("depends_on") or []]
        if all(row and row.get("status") == "complete" for row in dependencies):
            ready.append(stage_id)
    return ready


def _find_prior_artifact(ledger: Mapping[str, Any], schema: str) -> dict[str, Any] | None:
    for receipt in reversed(ledger.get("stage_receipts") or []):
        if receipt.get("status") != "complete":
            continue
        for artifact in reversed(receipt.get("artifacts") or []):
            if isinstance(artifact, Mapping) and artifact.get("schema") == schema:
                return dict(artifact)
    return None


def _validate_vertical_request(request: Mapping[str, Any]) -> None:
    if request.get("schema") != "dio.vertical_execution_request.v1":
        raise CompositionError("Vertical execution bundle contains an invalid request schema.")
    body = dict(request)
    fingerprint = str(body.pop("fingerprint", ""))
    request_id = str(body.pop("vertical_request_id", ""))
    expected = hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()
    if fingerprint != expected or request_id != f"VEXEC-{expected[:16].upper()}":
        raise CompositionError("Vertical execution request fingerprint mismatch.")


def _validate_execution_receipt(receipt: Mapping[str, Any]) -> None:
    if receipt.get("schema") != "dio.execution.receipt.v1":
        raise CompositionError("Vertical execution bundle contains an invalid DIO execution receipt schema.")
    body = dict(receipt)
    fingerprint = str(body.pop("fingerprint", ""))
    receipt_id = str(body.pop("execution_receipt_id", ""))
    expected = hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()
    if fingerprint != expected or receipt_id != f"EXEC-{expected[:16].upper()}":
        raise CompositionError("DIO execution receipt fingerprint mismatch.")


def make_vertical_execution_bundle(result: Mapping[str, Any]) -> dict[str, Any]:
    required = {"request", "specialist_receipt", "execution_receipt", "consumed_lease"}
    missing = sorted(required - set(result))
    if missing:
        raise CompositionError("Wave 5 result is incomplete: " + ",".join(missing))
    return {
        "schema": VERTICAL_BUNDLE_SCHEMA,
        "request": copy.deepcopy(result["request"]),
        "specialist_receipt": copy.deepcopy(result["specialist_receipt"]),
        "execution_receipt": copy.deepcopy(result["execution_receipt"]),
        "consumed_lease": copy.deepcopy(result["consumed_lease"]),
    }


def _validate_vertical_bundle(ledger: Mapping[str, Any], bundle: Mapping[str, Any], *, recorded_at: str) -> None:
    request = bundle.get("request") or {}
    specialist = bundle.get("specialist_receipt") or {}
    execution = bundle.get("execution_receipt") or {}
    consumed = bundle.get("consumed_lease") or {}
    if not all(isinstance(row, Mapping) for row in (request, specialist, execution, consumed)):
        raise CompositionError("Vertical execution bundle members must be mappings.")

    _validate_vertical_request(request)
    _validate_execution_receipt(execution)
    case_id = str(ledger["plan"]["case_id"])
    if request.get("case_id") != case_id or execution.get("case_id") != case_id:
        raise CompositionError("Vertical execution bundle crossed Governed Case boundaries.")

    lease = _find_prior_artifact(ledger, "dio.capability.lease.v1")
    valinor = _find_prior_artifact(ledger, "dio.valinor.authorization.v1")
    arda = _find_prior_artifact(ledger, "dio.arda.execution_identity.v1")
    if lease is None or valinor is None or arda is None:
        raise CompositionError("Vertical execution requires prior lease, Valinor and ARDA stages.")
    try:
        validate_capability_lease(lease, now=recorded_at)
        validate_valinor_authorization(valinor, lease=lease)
        validate_arda_execution_identity(arda, now=recorded_at, require_accepted=True)
    except AuthorityPlaneError as exc:
        raise CompositionError(str(exc)) from exc

    if request.get("lease_id") != lease.get("lease_id") or request.get("lease_fingerprint") != lease.get("fingerprint"):
        raise CompositionError("Vertical request is not bound to the composition lease.")
    if request.get("valinor_authorization_id") != valinor.get("authorization_id"):
        raise CompositionError("Vertical request is not bound to the composition Valinor authorization.")
    if request.get("arda_execution_identity_id") != arda.get("execution_identity_id"):
        raise CompositionError("Vertical request is not bound to the composition ARDA identity.")
    if arda.get("audience") != lease.get("audience"):
        raise CompositionError("ARDA audience does not match the composition lease audience.")

    registry = load_vertical_executor_registry()
    executor = next((row for row in registry.get("executors") or [] if row.get("executor_id") == request.get("executor_id")), None)
    if executor is None:
        raise CompositionError("Vertical request references an unknown executor.")
    capability = next((row for row in executor.get("capabilities") or [] if row.get("capability") == request.get("capability")), None)
    if capability is None or capability.get("binding_state") != "bound" or capability.get("mode") == "hard_locked":
        raise CompositionError("Composition cannot consume an unbound or locked Wave 5 capability.")
    for key in ("entrypoint_kind", "entrypoint_ref", "receipt_prefix", "valinor_operation"):
        if request.get(key) != capability.get(key):
            raise CompositionError(f"Vertical request binding drifted at {key}.")

    if specialist.get("vertical_request_id") != request.get("vertical_request_id"):
        raise CompositionError("Specialist receipt is not bound to the exact vertical request.")
    if specialist.get("payload_digest") != request.get("payload_digest"):
        raise CompositionError("Specialist receipt payload digest does not match the authorized payload.")
    prefix = str(request.get("receipt_prefix") or "")
    receipt_ref = str(specialist.get("receipt_ref") or "")
    if not prefix or not receipt_ref.startswith(prefix):
        raise CompositionError("Specialist receipt prefix does not match the registered executor binding.")
    if specialist.get("success") is not True or execution.get("success") is not True:
        raise CompositionError("A completed composition execution stage requires successful specialist and DIO receipts.")

    authority = execution.get("authority") or {}
    if execution.get("capability") != request.get("capability") or execution.get("executor_system") != request.get("executor_id"):
        raise CompositionError("DIO execution receipt does not match the vertical request.")
    if authority.get("lease_id") != lease.get("lease_id"):
        raise CompositionError("Execution receipt lease binding mismatch.")
    if authority.get("valinor_authorization_id") != valinor.get("authorization_id"):
        raise CompositionError("Execution receipt Valinor binding mismatch.")
    if authority.get("arda_execution_identity_id") != arda.get("execution_identity_id"):
        raise CompositionError("Execution receipt ARDA binding mismatch.")
    if consumed.get("lease_id") != lease.get("lease_id") or consumed.get("fingerprint") != lease.get("fingerprint"):
        raise CompositionError("Consumed lease lost immutable lease identity.")
    if int(consumed.get("used_count", 0)) <= int(lease.get("used_count", 0)):
        raise CompositionError("Vertical execution did not consume a lease use.")


def _validate_stage_artifacts(
    ledger: Mapping[str, Any],
    stage: Mapping[str, Any],
    artifacts: list[dict[str, Any]],
    *,
    recorded_at: str,
) -> None:
    if not artifacts:
        raise CompositionError("A completed composition stage must carry at least one canonical artifact.")
    accepted_contracts = set(stage.get("accepted_contracts") or [])
    accepted_assertion_types = set(stage.get("accepted_assertion_types") or [])
    case_id = str(ledger["plan"]["case_id"])

    for artifact in artifacts:
        schema = str(artifact.get("schema") or "")
        if schema not in accepted_contracts:
            raise CompositionError(
                f"Stage {stage.get('stage_id')} does not accept contract {schema or '<missing>'}."
            )
        if schema == "dio.fusion.assertion.v1":
            try:
                validate_assertion(artifact)
            except ValueError as exc:
                raise CompositionError(str(exc)) from exc
            if (artifact.get("lineage") or {}).get("case_id") != case_id:
                raise CompositionError("Fusion assertion is not bound to this composition case.")
            issuer = str((artifact.get("issuer") or {}).get("system_id") or "")
            if issuer != stage.get("system_id"):
                raise CompositionError(
                    f"Stage {stage.get('stage_id')} expected issuer {stage.get('system_id')}, got {issuer}."
                )
            if artifact.get("assertion_type") not in accepted_assertion_types:
                raise CompositionError("Fusion assertion type is not accepted by this composition stage.")
        elif schema == "dio.authority.receipt.v1":
            try:
                validate_authority_receipt(artifact, now=recorded_at, require_allow=True)
            except AuthorityPlaneError as exc:
                raise CompositionError(str(exc)) from exc
            if artifact.get("case_id") != case_id:
                raise CompositionError("Authority receipt crossed Governed Case boundaries.")
            actor_type = str((artifact.get("actor") or {}).get("actor_type") or "")
            if actor_type not in {"human", "organisation"}:
                raise CompositionError("Composition authority must come from a human or organisation.")
        elif schema == "dio.capability.lease.v1":
            try:
                validate_capability_lease(artifact, now=recorded_at)
            except AuthorityPlaneError as exc:
                raise CompositionError(str(exc)) from exc
            if artifact.get("case_id") != case_id:
                raise CompositionError("Capability lease crossed Governed Case boundaries.")
            authority = _find_prior_artifact(ledger, "dio.authority.receipt.v1")
            if authority is None:
                raise CompositionError("Capability lease stage has no prior human/organisational authority receipt.")
            if artifact.get("authority_receipt_id") != authority.get("authority_receipt_id"):
                raise CompositionError("Capability lease is not bound to the composition authority receipt.")
            if artifact.get("authority_receipt_fingerprint") != authority.get("fingerprint"):
                raise CompositionError("Capability lease authority fingerprint mismatch.")
        elif schema == "dio.valinor.authorization.v1":
            lease = _find_prior_artifact(ledger, "dio.capability.lease.v1")
            if lease is None:
                raise CompositionError("Valinor stage has no prior capability lease.")
            try:
                validate_capability_lease(lease, now=recorded_at)
                validate_valinor_authorization(artifact, lease=lease)
            except AuthorityPlaneError as exc:
                raise CompositionError(str(exc)) from exc
            if artifact.get("case_id") != case_id:
                raise CompositionError("Valinor authorization crossed Governed Case boundaries.")
            if artifact.get("kernel_authority") != "Valinor" or artifact.get("state") != "VALINOR_ALLOW" or artifact.get("allowed") is not True:
                raise CompositionError("Composition requires explicit Valinor ALLOW before execution.")
        elif schema == "dio.arda.execution_identity.v1":
            try:
                validate_arda_execution_identity(artifact, now=recorded_at, require_accepted=True)
            except AuthorityPlaneError as exc:
                raise CompositionError(str(exc)) from exc
            lease = _find_prior_artifact(ledger, "dio.capability.lease.v1")
            if lease is None:
                raise CompositionError("ARDA stage has no prior capability lease.")
            if artifact.get("audience") != lease.get("audience"):
                raise CompositionError("ARDA execution identity audience does not match the composition lease.")
            if artifact.get("kernel_authority") is not False:
                raise CompositionError("ARDA cannot become kernel authority through composition.")
        elif schema == VERTICAL_BUNDLE_SCHEMA:
            _validate_vertical_bundle(ledger, artifact, recorded_at=recorded_at)
        else:
            raise CompositionError(f"Unsupported composition artifact schema: {schema}")

    if stage.get("stage_kind") == "human_authority" and len(artifacts) != 1:
        raise CompositionError("Human authority stage must carry exactly one canonical authority receipt.")
    if stage.get("stage_kind") == "vertical_execution" and len(artifacts) != 1:
        raise CompositionError("Vertical execution stage must carry exactly one Wave 5 execution bundle.")
    if stage.get("stage_kind") == "egress":
        execution = _find_prior_artifact(ledger, VERTICAL_BUNDLE_SCHEMA)
        if execution is not None:
            execution_id = str((execution.get("execution_receipt") or {}).get("execution_receipt_id") or "")
            expected_ref = f"execution://{execution_id}" if execution_id else ""
            if expected_ref and not any(expected_ref in set((row.get("lineage") or {}).get("source_refs") or []) for row in artifacts):
                raise CompositionError("Vesper egress receipt must cite the completed DIO execution receipt.")


def _stage_receipt_fingerprint(row: Mapping[str, Any]) -> str:
    return _fingerprint(row, omit=("fingerprint", "stage_receipt_id"))


def record_composition_stage(
    ledger: dict[str, Any],
    *,
    stage_id: str,
    artifacts: list[dict[str, Any]] | None = None,
    status: str = "complete",
    summary: str = "",
    recorded_at: str | None = None,
) -> dict[str, Any]:
    validate_composition_ledger(ledger)
    if status not in STAGE_STATES:
        raise CompositionError(f"Unsupported composition stage status: {status}")
    plan = ledger["plan"]
    profile = _validate_plan(plan)
    stages = _stage_index(profile)
    stage = stages.get(stage_id)
    if stage is None:
        raise CompositionError(f"Unknown composition stage: {stage_id}")
    latest = _latest_receipts(ledger)
    previous = latest.get(stage_id)
    if previous and previous.get("status") == "complete":
        raise CompositionError(f"Composition stage is already complete: {stage_id}")
    if status == "skipped" and stage.get("required") is True:
        raise CompositionError("Required composition stages cannot be skipped.")

    dependency_receipts: dict[str, str] = {}
    for dep in stage.get("depends_on") or []:
        dep_receipt = latest.get(str(dep))
        if dep_receipt is None or dep_receipt.get("status") != "complete":
            raise CompositionError(f"Composition stage {stage_id} is blocked by dependency {dep}.")
        dependency_receipts[str(dep)] = str(dep_receipt["stage_receipt_id"])

    instant = _timestamp(recorded_at)
    artifact_rows = copy.deepcopy(list(artifacts or []))
    if status == "complete":
        _validate_stage_artifacts(ledger, stage, artifact_rows, recorded_at=instant)
    elif artifact_rows:
        _validate_stage_artifacts(ledger, stage, artifact_rows, recorded_at=instant)

    receipt: dict[str, Any] = {
        "schema": STAGE_RECEIPT_SCHEMA,
        "composition_id": plan["composition_id"],
        "plan_fingerprint": plan["fingerprint"],
        "case_id": plan["case_id"],
        "profile_id": plan["profile_id"],
        "stage_id": stage_id,
        "stage_kind": stage["stage_kind"],
        "system_id": stage["system_id"],
        "status": status,
        "dependency_receipts": dependency_receipts,
        "supersedes_stage_receipt_id": previous["stage_receipt_id"] if previous else None,
        "artifacts": artifact_rows,
        "summary": str(summary),
        "recorded_at": instant,
        "authority": {
            "composition_created_authority": False,
            "kernel_authority": "Valinor",
        },
    }
    receipt["fingerprint"] = _stage_receipt_fingerprint(receipt)
    receipt["stage_receipt_id"] = f"CSTAGE-{receipt['fingerprint'][:16].upper()}"
    ledger["stage_receipts"].append(receipt)
    if status == "refuse":
        ledger["state"] = "blocked"
    elif status == "needs_you":
        ledger["state"] = "needs_you"
    elif status == "needs_evidence":
        ledger["state"] = "needs_evidence"
    else:
        ledger["state"] = "in_progress"
    ledger["final_receipt"] = None
    return receipt


def validate_composition_ledger(ledger: dict[str, Any]) -> None:
    if ledger.get("schema") != LEDGER_SCHEMA:
        raise CompositionError("Unsupported composition ledger schema.")
    plan = ledger.get("plan") or {}
    profile = _validate_plan(plan)
    stages = _stage_index(profile)
    prior_rows: list[dict[str, Any]] = []
    latest: dict[str, dict[str, Any]] = {}

    for receipt in ledger.get("stage_receipts") or []:
        if receipt.get("schema") != STAGE_RECEIPT_SCHEMA:
            raise CompositionError("Unsupported composition stage receipt schema.")
        expected = _stage_receipt_fingerprint(receipt)
        if receipt.get("fingerprint") != expected or receipt.get("stage_receipt_id") != f"CSTAGE-{expected[:16].upper()}":
            raise CompositionError("Composition stage receipt fingerprint mismatch.")
        if receipt.get("composition_id") != plan.get("composition_id") or receipt.get("plan_fingerprint") != plan.get("fingerprint"):
            raise CompositionError("Composition stage receipt is not bound to this plan.")
        if receipt.get("case_id") != plan.get("case_id") or receipt.get("profile_id") != plan.get("profile_id"):
            raise CompositionError("Composition stage receipt crossed plan lineage.")
        stage_id = str(receipt.get("stage_id") or "")
        stage = stages.get(stage_id)
        if stage is None:
            raise CompositionError(f"Composition receipt references an unknown stage: {stage_id}")
        if receipt.get("stage_kind") != stage.get("stage_kind") or receipt.get("system_id") != stage.get("system_id"):
            raise CompositionError("Composition stage identity drifted from its profile.")
        if receipt.get("status") not in STAGE_STATES:
            raise CompositionError("Composition stage receipt has an invalid state.")
        if receipt.get("status") == "skipped" and stage.get("required") is True:
            raise CompositionError("Required composition stage was skipped.")

        dependency_receipts = receipt.get("dependency_receipts") or {}
        expected_dependencies: dict[str, str] = {}
        for dep in stage.get("depends_on") or []:
            dep_row = latest.get(str(dep))
            if dep_row is None or dep_row.get("status") != "complete":
                raise CompositionError(f"Composition receipt advanced before dependency {dep} completed.")
            expected_dependencies[str(dep)] = str(dep_row["stage_receipt_id"])
        if dependency_receipts != expected_dependencies:
            raise CompositionError("Composition dependency receipt binding mismatch.")

        previous = latest.get(stage_id)
        expected_supersedes = previous.get("stage_receipt_id") if previous else None
        if receipt.get("supersedes_stage_receipt_id") != expected_supersedes:
            raise CompositionError("Composition stage revision lineage mismatch.")
        if previous and previous.get("status") == "complete":
            raise CompositionError("A completed composition stage was illegally rewritten.")

        prefix_ledger = {
            "schema": LEDGER_SCHEMA,
            "plan": plan,
            "state": "in_progress",
            "stage_receipts": prior_rows,
            "final_receipt": None,
        }
        artifacts = copy.deepcopy(list(receipt.get("artifacts") or []))
        if receipt.get("status") == "complete":
            _validate_stage_artifacts(prefix_ledger, stage, artifacts, recorded_at=str(receipt.get("recorded_at")))
        elif artifacts:
            _validate_stage_artifacts(prefix_ledger, stage, artifacts, recorded_at=str(receipt.get("recorded_at")))

        latest[stage_id] = dict(receipt)
        prior_rows.append(dict(receipt))

    final_receipt = ledger.get("final_receipt")
    if final_receipt is not None:
        if final_receipt.get("schema") != FINAL_RECEIPT_SCHEMA:
            raise CompositionError("Unsupported final composition receipt schema.")
        expected = _fingerprint(final_receipt, omit=("fingerprint", "composition_receipt_id"))
        if final_receipt.get("fingerprint") != expected or final_receipt.get("composition_receipt_id") != f"COMPR-{expected[:16].upper()}":
            raise CompositionError("Final composition receipt fingerprint mismatch.")
        if final_receipt.get("composition_id") != plan.get("composition_id") or final_receipt.get("case_id") != plan.get("case_id"):
            raise CompositionError("Final composition receipt crossed plan lineage.")


def finalize_composition(ledger: dict[str, Any], *, completed_at: str | None = None) -> dict[str, Any]:
    validate_composition_ledger(ledger)
    if ledger.get("final_receipt"):
        return dict(ledger["final_receipt"])
    plan = ledger["plan"]
    profile = _validate_plan(plan)
    latest = _latest_receipts(ledger)
    missing = [
        str(stage["stage_id"])
        for stage in profile.get("stages") or []
        if stage.get("required") is True and (latest.get(str(stage["stage_id"])) or {}).get("status") != "complete"
    ]
    if missing:
        raise CompositionError("Composition cannot finalize; required stages incomplete: " + ",".join(missing))

    authority = _find_prior_artifact(ledger, "dio.authority.receipt.v1")
    lease = _find_prior_artifact(ledger, "dio.capability.lease.v1")
    valinor = _find_prior_artifact(ledger, "dio.valinor.authorization.v1")
    arda = _find_prior_artifact(ledger, "dio.arda.execution_identity.v1")
    execution_bundle = _find_prior_artifact(ledger, VERTICAL_BUNDLE_SCHEMA)
    execution_receipt = (execution_bundle or {}).get("execution_receipt") or {}

    receipt: dict[str, Any] = {
        "schema": FINAL_RECEIPT_SCHEMA,
        "state": "COMPOSITION_COMPLETE",
        "composition_id": plan["composition_id"],
        "plan_fingerprint": plan["fingerprint"],
        "case_id": plan["case_id"],
        "profile_id": plan["profile_id"],
        "final_state": plan["final_state"],
        "stage_receipt_ids": {
            str(stage["stage_id"]): str(latest[str(stage["stage_id"])]["stage_receipt_id"])
            for stage in profile.get("stages") or []
        },
        "authority_chain": {
            "authority_receipt_id": (authority or {}).get("authority_receipt_id"),
            "lease_id": (lease or {}).get("lease_id"),
            "valinor_authorization_id": (valinor or {}).get("authorization_id"),
            "arda_execution_identity_id": (arda or {}).get("execution_identity_id"),
            "execution_receipt_id": execution_receipt.get("execution_receipt_id"),
        },
        "authority": {
            "composition_created_authority": False,
            "kernel_authority": "Valinor",
            "execution_identity_authority": "ARDA",
        },
        "completed_at": _timestamp(completed_at),
    }
    receipt["fingerprint"] = _fingerprint(receipt, omit=("fingerprint", "composition_receipt_id"))
    receipt["composition_receipt_id"] = f"COMPR-{receipt['fingerprint'][:16].upper()}"
    ledger["state"] = "complete"
    ledger["final_receipt"] = receipt
    validate_composition_ledger(ledger)
    return receipt
