from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from products.compiler import (
    CompilerError,
    compile_manifest,
    inspect_compilation,
    load_manifest_registry,
    write_compilation,
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


def list_products(root: Path) -> list[dict]:
    rows = []
    registry = load_manifest_registry(root)
    for product_id in sorted(registry):
        row = registry[product_id]
        payload = row["manifest"]
        path = Path(str(row["path"])).resolve()
        rows.append(
            {
                "product_id": product_id,
                "name": payload.get("name"),
                "incarnation": (payload.get("incarnation") or {}).get("id"),
                "surface": (payload.get("incarnation") or {}).get("surface"),
                "maturity": (payload.get("maturity") or {}).get("state"),
                "path": str(path.relative_to(root)),
            }
        )
    return rows


def emit(payload: object, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    if isinstance(payload, list):
        for row in payload:
            print(f"{row['product_id']:<28} {str(row['maturity']):<18} {row['path']}")
        return
    if isinstance(payload, dict):
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(payload)


def main() -> int:
    parser = argparse.ArgumentParser(prog="dio-product", description="Validate, compile and inspect canonical DIO Product Manifests.")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List canonical product manifests.")

    validate_parser = sub.add_parser("validate", help="Validate and resolve a canonical product manifest without writing compiled artifacts.")
    validate_parser.add_argument("product")

    inspect_parser = sub.add_parser("inspect", help="Inspect the resolved canonical product composition without writing artifacts.")
    inspect_parser.add_argument("product")

    compile_parser = sub.add_parser("compile", help="Compile a canonical product manifest into governed runtime plans.")
    compile_parser.add_argument("product")
    compile_parser.add_argument("--output-root", type=Path, default=None)

    args = parser.parse_args()
    root = args.root.resolve()

    try:
        if args.command == "list":
            emit(list_products(root), args.json)
            return 0

        manifest_path = resolve_manifest(args.product, root)
        compiled = compile_manifest(root, manifest_path)

        if args.command == "validate":
            summary = inspect_compilation(compiled)
            summary["validation"] = "ALLOW"
            emit(summary, args.json)
            if not args.json:
                print("DIO_PRODUCT_MANIFEST_VALID")
            return 0

        if args.command == "inspect":
            emit(inspect_compilation(compiled), args.json)
            return 0

        if args.command == "compile":
            output_root = args.output_root.resolve() if args.output_root else None
            target = write_compilation(root, compiled, output_root=output_root)
            result = inspect_compilation(compiled)
            result["compiled_path"] = str(target)
            emit(result, args.json)
            if not args.json:
                print("DIO_PRODUCT_COMPILED")
            return 0

    except (CompilerError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"DIO_PRODUCT_COMPILER_REFUSE: {exc}", file=sys.stderr)
        return 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
