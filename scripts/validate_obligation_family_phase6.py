from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from products.compiler import compile_manifest, load_capability_catalog
from products.obligationfamily.runner import FAMILY_DEFINITIONS, run_family_proof
from products.work_pattern_runtime import plan_manifest


NOW = "2026-08-12T12:00:00+00:00"


def main() -> int:
    catalog, _ = load_capability_catalog(ROOT)
    expected_scope = sorted(FAMILY_DEFINITIONS)
    for capability_id in ("proof.room.compile", "proof.integrity.verify", "proof.disclosure.prepare"):
        provider = next(row for row in catalog[capability_id]["providers"] if row["provider_id"] == "obligation_family_proof_pack_v1")
        assert sorted(provider["product_scope"]) == expected_scope
    with tempfile.TemporaryDirectory(prefix="dio-phase6-") as directory:
        base = Path(directory)
        for product_id, definition in sorted(FAMILY_DEFINITIONS.items()):
            manifest = ROOT / "config" / "products" / "manifests" / f"{definition['slug']}.json"
            compiled = compile_manifest(ROOT, manifest)
            assert compiled["gates"]["execution"]["state"] == "NEEDS_YOU"
            assert compiled["gates"]["external_release"]["state"] == "REFUSE"
            plan = plan_manifest(ROOT, manifest)
            assert all(row["runtime_state"] == "READY" for row in plan["patterns"])
            fixture = ROOT / "config" / "products" / "golden" / definition["slug"]
            source = json.loads((fixture / "reference_source.json").read_text(encoding="utf-8"))
            evidence = json.loads((fixture / "reference_evidence.json").read_text(encoding="utf-8"))["evidence_records"]
            result = run_family_proof(product_id, source, evidence, output_dir=base / definition["slug"], operator_id="human.phase6_validator", now=NOW)
            assert result["receipt"]["external_release"] is False
            print(f"PASS {definition['title']}")
    print("DIO_OBLIGATION_FAMILY_READY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
