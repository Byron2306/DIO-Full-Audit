#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters.document_studio.pipeline import paragraphs_from_text  # noqa: E402
from adapters.lingua.lifecycle import register_product_source  # noqa: E402
from adapters.sophia.review_pipeline import extract_document_text  # noqa: E402


def load_routes() -> dict[str, Any]:
    return json.loads((ROOT / "config" / "lingua_product_routes.json").read_text(encoding="utf-8"))


def register(args: argparse.Namespace) -> dict[str, Any]:
    routes = load_routes()
    product = str(args.product).casefold()
    profile = (routes.get("products") or {}).get(product)
    if not profile:
        raise ValueError(f"Unsupported Lingua product route: {product}")
    if args.artifact_type not in profile.get("artifact_types", []):
        raise ValueError(f"Unsupported {product} artifact type: {args.artifact_type}")
    source_path = args.source.expanduser().resolve()
    text, extraction_method = extract_document_text(source_path)
    source_rows = paragraphs_from_text(text)
    origin = {
        "product": product,
        "artifact_type": args.artifact_type,
        "artifact_id": args.artifact_id,
        "source_path": str(source_path),
        "extraction_method": extraction_method,
        "audience": args.audience,
        "channel": args.channel,
        "profile": args.profile,
        "privacy_domain": args.privacy_domain,
    }
    semantic, receipt = register_product_source(
        state_root=ROOT / "state" / "lingua",
        object_id=args.semantic_object_id,
        source_version=args.source_version,
        source_language=args.source_language,
        source_rows=source_rows,
        origin=origin,
        domain=args.domain,
        subject=args.subject,
        grade=args.grade,
        curriculum_concept=args.curriculum_concept,
    )
    receipt_path = ROOT / "state" / "lingua" / "registrations" / f"{args.semantic_object_id}__{args.source_version}.json"
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return {
        "status": "registered",
        "semantic_object_id": semantic["object_id"],
        "product": product,
        "artifact_type": args.artifact_type,
        "source_units": len(semantic["source"]["units"]),
        "stale_translation_units": receipt["stale_translation_units"],
        "object_path": receipt["object_path"],
        "receipt_path": str(receipt_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Register any DIO product output in the shared Lingua semantic lifecycle.")
    parser.add_argument("--product", required=True)
    parser.add_argument("--artifact-type", required=True)
    parser.add_argument("--artifact-id", required=True)
    parser.add_argument("--semantic-object-id", required=True)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--source-version", default="1.0.0")
    parser.add_argument("--source-language", default="English")
    parser.add_argument("--domain", default="")
    parser.add_argument("--subject")
    parser.add_argument("--grade")
    parser.add_argument("--curriculum-concept")
    parser.add_argument("--audience", default="")
    parser.add_argument("--channel", default="document")
    parser.add_argument("--profile", default="")
    parser.add_argument("--privacy-domain", default="institutional")
    args = parser.parse_args()
    print(json.dumps(register(args), indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
