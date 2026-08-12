from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from products.compiler import compile_manifest
from products.contractproof.proof import verify_integrity
from products.contractproof.runner import run_contractproof
from products.work_pattern_runtime import inspect_summary, plan_manifest


MANIFEST = ROOT / "config" / "products" / "manifests" / "contractproof.json"
GOLDEN_ROOT = ROOT / "config" / "products" / "golden" / "contractproof"
DEFAULT_OUTPUT = ROOT / "state" / "golden_proofs" / "dio_contractproof" / "reference"
GOLDEN_NOW = "2026-08-12T12:00:00+00:00"


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="DIO ContractProof internal golden-proof operator")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("inspect", help="Inspect current compiler/work-pattern readiness")
    golden = sub.add_parser("golden", help="Run the canonical internal golden ContractProof case")
    golden.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    golden.add_argument("--operator", default="human.phase5_golden_operator")
    verify = sub.add_parser("verify", help="Verify an existing ContractProof proof pack")
    verify.add_argument("path", type=Path, nargs="?", default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    if args.command == "inspect":
        compiled = compile_manifest(ROOT, MANIFEST)
        plan = plan_manifest(ROOT, MANIFEST)
        payload = {
            "product_id": compiled["product_id"],
            "maturity": compiled["maturity"],
            "compiler_gates": compiled["gates"],
            "work_pattern_plan": inspect_summary(plan),
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    if args.command == "verify":
        result = verify_integrity(args.path)
        print(json.dumps(result, indent=2, sort_keys=True))
        if result["verified"]:
            print("DIO_CONTRACTPROOF_PROOF_VERIFIED")
            return 0
        return 1

    source = _load(GOLDEN_ROOT / "reference_contract.json")
    evidence_payload = _load(GOLDEN_ROOT / "reference_evidence.json")
    result = run_contractproof(
        source,
        evidence_payload["evidence_records"],
        output_dir=args.output,
        operator_id=args.operator,
        now=GOLDEN_NOW,
        job_id="phase5-golden-reference",
    )
    print(json.dumps(result["receipt"], indent=2, sort_keys=True))
    print(f"WROTE {result['output_dir']}")
    print("DIO_CONTRACTPROOF_GOLDEN_WRITTEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
