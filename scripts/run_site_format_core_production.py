#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from products.site_full_grade_bridge_v3 import run_site_full_grade_v3  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the full Site Studio customer site through the authoritative DIO Format Core SVG compositor.")
    parser.add_argument("--output", type=Path, default=ROOT / "state" / "site_studio_format_core_production")
    parser.add_argument("--keep", action="store_true", help="Do not remove an existing output directory before rebuilding.")
    args = parser.parse_args()

    output = args.output.resolve()
    if output.exists() and not args.keep:
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)

    receipt = run_site_full_grade_v3(
        manifest_path=ROOT / "config" / "studio_harvest" / "site_studio.json",
        output_dir=output,
        root=ROOT,
    )
    site = output / "customer" / "FULL_GRADE_SITE" / "index.html"
    proof = output / "customer" / "FULL_GRADE_SITE" / "proof" / "SITE_PROOF_MANIFEST.json"
    compositor = output / "customer" / "FULL_GRADE_SITE" / "proof" / "FORMAT_CORE_SITE_VISUAL_COMPOSITOR_RECEIPT.json"

    summary = {
        "site": str(site),
        "site_exists": site.is_file(),
        "proof_manifest": str(proof),
        "proof_manifest_exists": proof.is_file(),
        "format_core_compositor_receipt": str(compositor),
        "format_core_compositor_receipt_exists": compositor.is_file(),
        "format_core_visual_compositor": receipt.get("format_core_visual_compositor"),
        "site_semantic_authority": receipt.get("site_semantic_authority"),
        "visual_projection_authority": receipt.get("visual_projection_authority"),
        "gamma_layout_authority": receipt.get("gamma_layout_authority"),
        "gamma_text_authority": receipt.get("gamma_text_authority"),
        "human_visual_release": receipt.get("human_visual_release", "NEEDS_YOU"),
        "publication": receipt.get("publication", "REFUSE"),
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))

    passed = (
        summary["site_exists"]
        and summary["proof_manifest_exists"]
        and summary["format_core_compositor_receipt_exists"]
        and summary["format_core_visual_compositor"] == "PASS"
        and summary["site_semantic_authority"] == "DIO_SITE_STUDIO"
        and summary["visual_projection_authority"] == "DIO_FORMAT_CORE"
        and summary["gamma_layout_authority"] == "REFUSE"
        and summary["gamma_text_authority"] == "REFUSE"
    )
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
