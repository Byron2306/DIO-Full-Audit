from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def run(command: list[str], *, cwd: Path) -> None:
    print("- " + " ".join(command), flush=True)
    subprocess.run(command, cwd=str(cwd), check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run DIO META Product Layer acceptance.")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--core", required=True)
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()
    core = Path(args.core).resolve()
    python = sys.executable

    run([
        python, "-m", "py_compile",
        "products/meta.py",
        "scripts/check_meta_product_layer.py",
        "scripts/run_meta_product_layer.py",
    ], cwd=core)

    schema_check = (
        "import json; from pathlib import Path; from jsonschema import Draft202012Validator; "
        "s=json.loads(Path('schemas/dio_meta_products.schema.json').read_text()); "
        "p=json.loads(Path('config/dio_meta_products.json').read_text()); "
        "Draft202012Validator.check_schema(s); Draft202012Validator(s).validate(p); "
        "print('PASS META product registry schema')"
    )
    run([python, "-c", schema_check], cwd=core)

    run([python, "-m", "pytest", "-q", "tests/test_meta_products.py"], cwd=core)

    out = workspace / "receipts" / "meta-product-layer-latest.json"
    run([
        python,
        str(core / "scripts" / "check_meta_product_layer.py"),
        "--workspace", str(workspace),
        "--core", str(core),
        "--out", str(out),
    ], cwd=core)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
