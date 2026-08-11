from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


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
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
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


def stable_id(prefix: str, *parts: Any) -> str:
    raw = "\n".join(str(part or "") for part in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16].upper()
    return f"{prefix}-{digest}"


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


def bootstrap_generic_job(
    source_path: Path,
    state_root: Path,
    runs_root: Path,
    portfolio_path: Path = PORTFOLIO_PATH,
) -> dict[str, Any]:
    """Create a safe, non-executing workflow envelope for a registered product profile.

    This deliberately does not invoke a product executor. It gives the commercial
    orchestrator a canonical job with evidence requirements, authority gates, and
    activation boundaries while preserving the truth that the executor is not yet proven.
    """

    source_path = _resolve_source_job(source_path, runs_root)
    source = load_json(source_path)
    product = str((source.get("route") or {}).get("product") or "")
    profile = get_profile(product, portfolio_path)
    job_id = safe_job_id(str(source.get("job_id") or stable_id(product.upper(), source_path)))
    target = state_root / job_id / "JOB.json"
    if target.is_file():
        return load_json(target)

    run_name, mode = _run_context(source_path, runs_root)
    source_approval = source.get("approval") or {}
    intake_state = str(source_approval.get("state") or "pending")
    blocked = intake_state == "rejected"
    created_at = timestamp()
    workflow = {
        "schema": "dio.generic_product_workflow.v1",
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
        "lineage": {
            "source_message_id": (source.get("source") or {}).get("message_id"),
            "lead_id": (source.get("source") or {}).get("lead_id"),
            "conversation_id": (source.get("source") or {}).get("conversation_id") or (source.get("source") or {}).get("thread_ref"),
            "source_evidence_ids": [item.get("evidence_id") for item in source.get("evidence") or [] if item.get("evidence_id")],
        },
        "capability": {
            "classification": "registered",
            "planning": "enabled",
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
            "reason": "No generic executor, completed review, or product-specific release receipt exists.",
        },
        "expected_outputs": profile.get("expected_outputs") or [],
        "activation_gates": profile.get("activation_gates") or [],
        "risk_boundary": profile.get("risk_boundary"),
    }
    _write_json(target, workflow)
    try:
        target.chmod(0o600)
    except OSError:
        pass
    return workflow
