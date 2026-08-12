from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from products.compiler import CompilerError, compile_manifest, inspect_compilation, write_compilation


MANIFEST_ROOT = ROOT / "config" / "products" / "manifests"


def resolve_manifest(value: str, root: Path) -> Path:
    candidate = Path(value)
    if candidate.suffix == ".json":
        if not candidate.is_absolute():
            direct = (root / candidate).resolve()
            if direct.is_file():
                return direct
        elif candidate.is_file():
            return candidate.resolve()

    manifest_root = root / "config" / "products" / "manifests"
    by_filename = manifest_root / f"{value}.json"
    if by_filename.is_file():
        return by_filename.resolve()

    matches = []
    for path in sorted(manifest_root.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("product_id") == value or (payload.get("incarnation") or {}).get("id") == value:
            matches.append(path)
    if len(matches) == 1:
        return matches[0].resolve()
    if len(matches) > 1:
        raise CompilerError(f"ambiguous product selector {value}: {[str(path) for path in matches]}")
    raise CompilerError(f"no product manifest found for selector: {value}")


def list_products(root: Path) -> list[dict]:
    rows = []
    manifest_root = root / "config" / "products" / "manifests"
    for path in sorted(manifest_root.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows.append(
            {
                "product_id": payload.get("product_id"),
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
    parser = argparse.ArgumentParser(prog="dio-product", description="Validate, compile and inspect DIO Product Manifests.")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List canonical product manifests.")

    validate_parser = sub.add_parser("validate", help="Validate and resolve a product manifest without writing compiled artifacts.")
    validate_parser.add_argument("product")

    inspect_parser = sub.add_parser("inspect", help="Inspect the resolved product composition without writing artifacts.")
    inspect_parser.add_argument("product")

    compile_parser = sub.add_parser("compile", help="Compile a product manifest into governed runtime plans.")
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
            emit(inspect_compilation(compiled), True if args.json else False)
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
