from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "config" / "launch" / "dio_launch_registry_v2.json"
ALLOWED = {
    "AVAILABLE_CONTROLLED_PILOT",
    "PROOF_RUN_REQUIRED",
    "ARTIFACT_GATE_PENDING",
    "COMPOSITION_PROOF_REQUIRED",
    "EXTERNAL_AUTHORITY_REVIEW_REQUIRED",
    "CANDIDATE",
}


class LaunchRegistryError(RuntimeError):
    pass


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != "dio.launch_registry.v2":
        raise LaunchRegistryError("unexpected launch registry schema")
    return payload


def _repo_file(value: str, *, field: str, product: str) -> Path:
    raw = str(value or "").strip()
    if not raw:
        raise LaunchRegistryError(f"{product}: missing {field}")
    path = (ROOT / raw).resolve()
    if ROOT.resolve() not in path.parents and path != ROOT.resolve():
        raise LaunchRegistryError(f"{product}: {field} escapes repository root")
    if not path.is_file():
        raise LaunchRegistryError(f"{product}: {field} does not exist: {raw}")
    return path


def validate(path: Path) -> dict[str, Any]:
    registry = _load(path)
    errors: list[str] = []
    warnings: list[str] = []
    ids: set[str] = set()

    groups = (
        ("launch_ready", registry.get("launch_ready") or []),
        ("near_launch", registry.get("near_launch") or []),
        ("commercial_compositions_held", registry.get("commercial_compositions_held") or []),
    )
    for group_name, rows in groups:
        for row in rows:
            product = str(row.get("name") or row.get("id") or "unnamed")
            product_id = str(row.get("id") or "")
            status = str(row.get("status") or "")
            if not product_id:
                errors.append(f"{product}: missing id")
            elif product_id in ids:
                errors.append(f"duplicate product id: {product_id}")
            else:
                ids.add(product_id)
            if status not in ALLOWED:
                errors.append(f"{product}: unsupported status {status!r}")

            for field in ("proof_ref", "manifest_ref", "registry_ref", "public_surface"):
                if row.get(field):
                    try:
                        _repo_file(str(row[field]), field=field, product=product)
                    except LaunchRegistryError as exc:
                        errors.append(str(exc))

            if status == "AVAILABLE_CONTROLLED_PILOT":
                if not row.get("proof_ref"):
                    errors.append(f"{product}: launch-ready product lacks proof_ref")
                artifacts = [str(value).strip() for value in row.get("customer_artifacts") or [] if str(value).strip()]
                if not artifacts:
                    errors.append(f"{product}: launch-ready product lacks customer-visible artifact contract")
                if row.get("artifact_openable") is not True:
                    errors.append(f"{product}: launch-ready product must assert artifact_openable=true")
                if row.get("evidence_embedded_or_linked") is not True:
                    errors.append(f"{product}: launch-ready product must embed or link evidence")
                if row.get("human_gate") != "NEEDS_YOU":
                    errors.append(f"{product}: human gate drifted")
                if row.get("external_release") != "REFUSE":
                    errors.append(f"{product}: external release must remain REFUSE")

    laws = registry.get("laws") or {}
    required_laws = (
        "receipt_alone_is_not_product",
        "registered_is_not_available",
        "launch_ready_requires_execution_proof",
        "launch_ready_requires_customer_visible_artifact",
        "external_release_remains_human_held",
        "canonical_53_is_not_the_complete_product_universe",
    )
    for law in required_laws:
        if laws.get(law) is not True:
            errors.append(f"launch law missing or false: {law}")

    truth = registry.get("truth") or {}
    actual_ready = len(registry.get("launch_ready") or [])
    if truth.get("available_product_count") != actual_ready:
        errors.append(
            f"truth.available_product_count={truth.get('available_product_count')} but registry has {actual_ready} launch-ready rows"
        )
    if truth.get("market_validation_claimed") is not False:
        errors.append("market validation must remain explicitly false")
    if truth.get("commercial_validation_claimed") is not False:
        errors.append("commercial validation must remain explicitly false")
    if truth.get("autonomous_external_release") is not False:
        errors.append("autonomous external release must remain explicitly false")

    result = {
        "schema": "dio.launch_registry_validation.v2",
        "registry": str(path.relative_to(ROOT)),
        "launch_ready_count": actual_ready,
        "near_launch_count": len(registry.get("near_launch") or []),
        "held_composition_count": len(registry.get("commercial_compositions_held") or []),
        "errors": errors,
        "warnings": warnings,
        "passed": not errors,
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate DIO Launch Registry v2 truth and artifact contracts.")
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    args = parser.parse_args()
    path = args.registry if args.registry.is_absolute() else (ROOT / args.registry)
    result = validate(path.resolve())
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
