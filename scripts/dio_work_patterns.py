from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from products.compiler import CompilerError, load_manifest_registry
from products.work_pattern_runtime import (
    WorkPatternRuntimeError,
    inspect_summary,
    load_runtime_registry,
    plan_manifest,
)


def resolve_manifest(value: str, root: Path) -> Path:
    registry = load_manifest_registry(root)
    manifest_root = (root / "config" / "products" / "manifests").resolve()
    for row in registry.values():
        manifest = row["manifest"]
        path = Path(str(row["path"])).resolve()
        if value in {
            str(manifest.get("product_id") or ""),
            str((manifest.get("incarnation") or {}).get("id") or ""),
            path.name,
            path.stem,
        }:
            return path
    candidate = Path(value)
    if candidate.suffix == ".json":
        direct = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
        if direct.is_file() and direct.is_relative_to(manifest_root):
            return direct
    raise CompilerError(f"no canonical product manifest found for selector: {value}")


def list_contracts(root: Path) -> list[dict]:
    contracts, _, _ = load_runtime_registry(root)
    return [
        {
            "work_pattern_id": pattern_id,
            "contract_id": contract["contract_id"],
            "runtime_stage": contract["runtime_stage"],
            "operation_count": len(contract.get("operations") or []),
            "human_boundary": contract["human_boundary"],
        }
        for pattern_id, contract in sorted(contracts.items())
    ]


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="dio-work-patterns",
        description="Inspect DIO Work Pattern Runtime contracts without executing side effects.",
    )
    parser.add_argument("--root", type=Path, default=ROOT)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="List the twelve canonical work-pattern runtime contracts.")
    inspect_parser = sub.add_parser("inspect", help="Resolve work-pattern operations for a canonical product manifest.")
    inspect_parser.add_argument("product")
    validate_parser = sub.add_parser("validate", help="Validate runtime contracts and resolve a canonical product manifest.")
    validate_parser.add_argument("product")
    args = parser.parse_args()
    root = args.root.resolve()

    try:
        if args.command == "list":
            print(json.dumps(list_contracts(root), indent=2, sort_keys=True))
            return 0
        manifest_path = resolve_manifest(args.product, root)
        plan = plan_manifest(root, manifest_path)
        print(json.dumps(inspect_summary(plan), indent=2, sort_keys=True))
        if args.command == "validate":
            print("DIO_WORK_PATTERN_PLAN_VALID")
        return 0
    except (CompilerError, WorkPatternRuntimeError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"DIO_WORK_PATTERN_RUNTIME_REFUSE: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
