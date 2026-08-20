from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from products.site_full_grade_bridge_v2 import run_site_full_grade_v2
from products.studio_full_grade_convergence import (
    ACCEPTANCE_TOKEN,
    run_article_full_grade,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the stricter full-grade convergence proof for DIO Site Studio and Article / Publication Studio."
    )
    parser.add_argument("--output", type=Path, default=Path("state/studio_harvest/full_grade"))
    parser.add_argument("--only", choices=["site", "article"], default=None)
    parser.add_argument("--article-manuscript", type=Path, default=None)
    parser.add_argument("--approve-remote-article-review", action="store_true")
    parser.add_argument("--sophia-root", type=Path, default=Path("/home/byron/Integritas-Mechanicus"))
    parser.add_argument("--sophia-base-url", default="http://127.0.0.1:7070")
    parser.add_argument("--gemini-model", default="gemini-flash-lite-latest")
    args = parser.parse_args()

    out = args.output.expanduser().resolve()
    if args.only == "site":
        result = run_site_full_grade_v2(
            manifest_path=ROOT / "config/studio_harvest/site_studio.json",
            output_dir=out / "site_studio",
            root=ROOT,
        )
        passed = result.get("full_grade_state") == "PASS"
    elif args.only == "article":
        result = run_article_full_grade(
            manifest_path=ROOT / "config/studio_harvest/article_publication_studio.json",
            output_dir=out / "article_publication_studio",
            root=ROOT,
            manuscript_path=args.article_manuscript,
            sophia_root=args.sophia_root,
            sophia_base_url=args.sophia_base_url,
            remote_review_approved=args.approve_remote_article_review,
            gemini_model=args.gemini_model,
        )
        passed = result.get("full_grade_state") == "PASS"
    else:
        site = run_site_full_grade_v2(
            manifest_path=ROOT / "config/studio_harvest/site_studio.json",
            output_dir=out / "site_studio",
            root=ROOT,
        )
        article = run_article_full_grade(
            manifest_path=ROOT / "config/studio_harvest/article_publication_studio.json",
            output_dir=out / "article_publication_studio",
            root=ROOT,
            manuscript_path=args.article_manuscript,
            sophia_root=args.sophia_root,
            sophia_base_url=args.sophia_base_url,
            remote_review_approved=args.approve_remote_article_review,
            gemini_model=args.gemini_model,
        )
        result = {
            "schema": "dio.studio_full_grade_convergence_gauntlet_receipt.v2",
            "acceptance_token": ACCEPTANCE_TOKEN,
            "site_studio": site,
            "article_publication_studio": article,
            "site_full_grade": site.get("full_grade_state") == "PASS",
            "article_full_grade": article.get("full_grade_state") == "PASS",
            "external_effects": False,
            "authority_created": False,
        }
        result["passed"] = bool(result["site_full_grade"] and result["article_full_grade"])
        passed = bool(result["passed"])

    print(json.dumps(result, indent=2, sort_keys=True))
    if passed:
        print(ACCEPTANCE_TOKEN)
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
