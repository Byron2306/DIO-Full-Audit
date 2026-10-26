from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from products.case_migration import LEGACY_SCHEMA, migrate_v1_to_v2
from products.governed_case import CASE_SCHEMA, new_case, stable_id, validate_case


ROOT = Path(__file__).resolve().parents[1]
PORTFOLIO_PATH = ROOT / "config" / "dio_product_portfolio.json"
CONTROLLED_MARKERS = ("demo", "dry_run", "playwright", "check", "golden", "sample", "dummy", "test")


def timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(path)


def load_portfolio(path: Path = PORTFOLIO_PATH) -> dict[str, Any]:
    payload = load_json(path)
    if payload.get("schema") != "dio.product_portfolio.v1":
        raise ValueError("Unsupported DIO product portfolio schema.")
    products = payload.get("products")
    if not isinstance(products, list) or not products:
        raise ValueError("DIO product portfolio must contain product profiles.")
    ids = [str(item.get("id") or "") for item in products]
    if any(not item for item in ids) or len(ids) != len(set(ids)):
        raise ValueError("DIO product IDs must be present and unique.")
    return payload


def product_profiles(path: Path = PORTFOLIO_PATH) -> dict[str, dict[str, Any]]:
    return {str(item["id"]): item for item in load_portfolio(path)["products"]}


def get_profile(product_id: str, path: Path = PORTFOLIO_PATH) -> dict[str, Any]:
    profile = product_profiles(path).get(str(product_id))
    if not profile:
        raise KeyError(f"Unknown governed DIO product profile: {product_id}")
    return profile


def is_registered_product(product_id: str, path: Path = PORTFOLIO_PATH) -> bool:
    return str(product_id) in product_profiles(path)


def safe_job_id(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{2,120}", value):
        raise ValueError("Invalid generic product job ID.")
    return value


def _resolve_source_job(path: Path, runs_root: Path) -> Path:
    resolved = path.expanduser().resolve()
    allowed = runs_root.expanduser().resolve()
    if not resolved.is_relative_to(allowed) or resolved.suffix != ".json" or not resolved.is_file():
        raise ValueError("Generic product workflow source must be an existing JSON job under the DIO runs directory.")
    return resolved


def _run_context(source_path: Path, runs_root: Path) -> tuple[str, str]:
    relative = source_path.relative_to(runs_root.resolve())
    run_name = relative.parts[0]
    mode = "controlled" if any(marker in run_name.lower() for marker in CONTROLLED_MARKERS) else "live"
    return run_name, mode


def _upgrade_existing_case(
    *,
    target: Path,
    case_path: Path,
    source: dict[str, Any],
    source_path: Path,
    profile: dict[str, Any],
    intake_state: str,
) -> dict[str, Any]:
    workflow = load_json(target)
    if not case_path.is_file():
        raise FileNotFoundError(f"Existing product workflow is missing governed case: {case_path}")
    case = load_json(case_path)
    if case.get("schema") == LEGACY_SCHEMA:
        migrated, receipt = migrate_v1_to_v2(
            old_case=case,
            source=source,
            source_path=source_path,
            profile=profile,
            intake_state=intake_state,
        )
        _write_json(case_path, migrated)
        _write_json(case_path.parent / "CASE_MIGRATION.json", receipt)
        case = migrated
    validate_case(case)
    changed = False
    if workflow.get("schema") != "dio.generic_product_workflow.v2":
        workflow["schema"] = "dio.generic_product_workflow.v2"
        changed = True
    if workflow.get("case_schema") != CASE_SCHEMA:
        workflow["case_schema"] = CASE_SCHEMA
        changed = True
    capability = workflow.setdefault("capability", {})
    if capability.get("case_reasoning") != "enabled":
        capability["case_reasoning"] = "enabled"
        changed = True
    if changed:
        workflow["updated_at"] = timestamp()
        _write_json(target, workflow)
    return workflow


def bootstrap_generic_job(
    source_path: Path,
    state_root: Path,
    runs_root: Path,
    portfolio_path: Path = PORTFOLIO_PATH,
) -> dict[str, Any]:
    """Create a safe non-executing workflow plus canonical governed case v2.

    Registration means DIO can classify, stage, reason about evidence, challenge state,
    and enforce authority boundaries. It does not create a product executor or external
    release authority. Existing scaffold-only v1 cases are migrated only when migration
    is lossless; unexpected progressed state is held for human review.
    """
    source_path = _resolve_source_job(source_path, runs_root)
    source = load_json(source_path)
    product = str((source.get("route") or {}).get("product") or "")
    profile = get_profile(product, portfolio_path)
    job_id = safe_job_id(str(source.get("job_id") or stable_id(product.upper(), source_path)))
    target = state_root / job_id / "JOB.json"
    case_path = target.parent / "CASE.json"
    source_approval = source.get("approval") or {}
    intake_state = str(source_approval.get("state") or "pending")
    if target.is_file():
        return _upgrade_existing_case(
            target=target,
            case_path=case_path,
            source=source,
            source_path=source_path,
            profile=profile,
            intake_state=intake_state,
        )

    run_name, mode = _run_context(source_path, runs_root)
    blocked = intake_state == "rejected"
    created_at = timestamp()
    case = new_case(
        product=product,
        job_id=job_id,
        source=source,
        source_path=source_path,
        evidence_inputs=[str(item) for item in profile.get("evidence_inputs") or []],
        expected_outputs=[str(item) for item in profile.get("expected_outputs") or []],
        required_authorities=[str(item) for item in profile.get("required_authorities") or []],
        intake_state=intake_state,
        framework_ids=[str(item) for item in profile.get("framework_ids") or []],
        jurisdiction_ids=[str(item) for item in profile.get("jurisdiction_ids") or []],
        subject_ref=(source.get("request") or {}).get("subject_ref"),
        world_state_ref=(source.get("request") or {}).get("world_state_ref"),
        now=created_at,
    )
    _write_json(case_path, case)

    workflow = {
        "schema": "dio.generic_product_workflow.v2",
        "job_id": job_id,
        "product": product,
        "product_name": profile["name"],
        "state": "blocked" if blocked else "active",
        "mode": mode,
        "runtime_mode": profile.get("runtime_mode", "review_workflow"),
        "maturity": profile.get("status"),
        "created_at": created_at,
        "updated_at": created_at,
        "source_job_path": str(source_path),
        "case_id": case["case_id"],
        "case_path": str(case_path),
        "case_schema": CASE_SCHEMA,
        "lineage": {
            "source_message_id": (source.get("source") or {}).get("message_id"),
            "lead_id": (source.get("source") or {}).get("lead_id"),
            "conversation_id": (source.get("source") or {}).get("conversation_id") or (source.get("source") or {}).get("thread_ref"),
            "source_evidence_ids": [item.get("evidence_id") for item in source.get("evidence") or [] if item.get("evidence_id")],
        },
        "capability": {
            "classification": "registered",
            "planning": "enabled",
            "case_reasoning": "enabled",
            "execution": "not_implemented",
            "external_release": "held",
            "commercial_claim": "architecture_seeded_not_product_proven",
        },
        "intake": {
            "state": intake_state,
            "reviewer": source_approval.get("reviewer"),
            "reviewed_at": source_approval.get("reviewed_at"),
            "required_evidence": profile.get("evidence_inputs") or [],
        },
        "processing": {
            "state": "not_started",
            "profile_state": "registered",
            "runner": "not_implemented",
            "shared_organs": profile.get("shared_organs") or [],
        },
        "output_review": {
            "required": True,
            "state": "not_started",
            "required_authorities": profile.get("required_authorities") or [],
        },
        "delivery": {
            "state": "held",
            "reason": "No product-specific executor, completed review, or release receipt exists.",
        },
        "expected_outputs": profile.get("expected_outputs") or [],
        "activation_gates": profile.get("activation_gates") or [],
        "risk_boundary": profile.get("risk_boundary"),
    }
    _write_json(target, workflow)
    for private_path in (target, case_path):
        try:
            private_path.chmod(0o600)
        except OSError:
            pass
    return workflow
