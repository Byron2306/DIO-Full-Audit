#!/usr/bin/env python3
"""Review an identity-preserving covenant migration, then seal only after assent.

The review command writes a draft only. Historical seals are evidence, never
current consent. The seal command invokes the native CoronationService.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import shlex
import sys

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "cross_folder_variants/Integritas-Mechanicus/A_CODE/arda_os"
DEFAULT_DATA = BACKEND.parent / "evidence/mandos"


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def review_digest(review):
    return digest({k: v for k, v in review.items() if k != "review_sha256"})


def native_types():
    sys.path.insert(0, str(BACKEND))
    from backend.services.coronation_service import CoronationService
    from backend.services.coronation_schemas import CovenantTerms, PrincipalIdentity
    for cls, filename in [(CoronationService, "coronation_service.py"), (CovenantTerms, "coronation_schemas.py"), (PrincipalIdentity, "coronation_schemas.py")]:
        actual = Path(sys.modules[cls.__module__].__file__).resolve()
        if actual != (BACKEND / "backend/services" / filename).resolve():
            raise ValueError("Refuse unrelated backend already imported into this process")
    return CoronationService, CovenantTerms, PrincipalIdentity


def build_review(identity_file, data_root=DEFAULT_DATA):
    service_cls, terms_cls, identity_cls = native_types()
    identity_file = Path(identity_file).resolve()
    source = json.loads(identity_file.read_text())
    offered = source.get("payload", source)
    migrated = dict(offered)
    migrations = {}
    if "register" in migrated:
        if "identity_register" in migrated and migrated["identity_register"] != migrated["register"]:
            raise ValueError("Conflicting identity register fields require explicit migration review")
        migrated["identity_register"] = migrated.pop("register")
        migrations["register"] = "identity_register"
    identity = identity_cls(**migrated)
    current = identity.model_dump(mode="json")
    # An unknown field or coercion must never silently discard offered semantics.
    for key, value in migrated.items():
        if key not in current or current[key] != value:
            raise ValueError(f"Identity field needs explicit migration review: {key}")
    terms = terms_cls(constitutional_refusal_acknowledged=True)
    service = service_cls()
    review = {
        "schema": "dio.sophia_covenant_review.v1",
        "state": "pending_principal_review",
        "sealed": False,
        "runtime": {"backend_root": str(BACKEND.resolve()), "data_root": str(Path(data_root).resolve()), "native_url": "http://127.0.0.1:7070"},
        "source_hashes": {name: hashlib.sha256((BACKEND / "backend/services" / name).read_bytes()).hexdigest() for name in ["coronation_service.py", "coronation_schemas.py"]},
        "principal": {
            "source_identity_path": str(identity_file),
            "source_identity_sha256": hashlib.sha256(identity_file.read_bytes()).hexdigest(),
            "offered_identity": offered,
            "current_identity": current,
            "field_migrations": migrations,
            "historical_identity_hash": source.get("record", {}).get("principal_identity_hash") or identity_file.stem.removesuffix("_identity"),
            "current_identity_hash": identity.identity_hash(),
            "schema_added_defaults": {k: v for k, v in current.items() if k not in offered},
        },
        "articles": {"genesis": service.get_genesis_articles(), "presence": service.get_presence_articles(), "officers": service.get_officer_schema()},
        "article_hashes": {"genesis": service.get_genesis_hash(), "presence": service.get_presence_articles_hash(), "officers": service.get_officer_schema_hash()},
        "terms": terms.model_dump(mode="json"),
        "terms_hash": terms.terms_hash(),
        "assent_scope": "Accept the current Genesis and Presence Articles, officer schema, unchanged offered identity with declared schema defaults and hash migration, and all listed operational terms; seal a new local covenant for the specified runtime.",
        "pending_step": "Principal affirmation of this exact review hash is required before seal_covenant. No historical seal establishes that affirmation.",
    }
    review["review_sha256"] = review_digest(review)
    return review


def seal_review(review, accepted_hash, affirmed):
    if not affirmed:
        raise ValueError("Explicit principal affirmation is required")
    if accepted_hash != review.get("review_sha256") or accepted_hash != review_digest(review):
        raise ValueError("Accepted review hash does not match the exact draft")
    source = Path(review["principal"]["source_identity_path"])
    if hashlib.sha256(source.read_bytes()).hexdigest() != review["principal"]["source_identity_sha256"]:
        raise ValueError("Offered identity source changed; prepare and review a new draft")
    fresh = build_review(source, review["runtime"]["data_root"])
    if fresh != review:
        raise ValueError("Current source or review has changed; prepare a new draft")
    target = Path(review["runtime"]["data_root"])
    if list((target / "covenants/constitutional").glob("*_manifest.json")):
        raise ValueError("An existing covenant must be inspected; refusing replacement")
    service_cls, terms_cls, identity_cls = native_types()

    async def run():
        service = service_cls()
        await service.begin_coronation()
        await service.offer_identity(identity_cls(**review["principal"]["current_identity"]))
        negotiated = await service.negotiate_terms(terms_cls(**review["terms"]))
        if negotiated.get("terms_hash") != review["terms_hash"] or negotiated.get("principal_hash") != review["principal"]["current_identity_hash"]:
            raise ValueError("Native negotiated covenant differs from the accepted review")
        return await service.seal_covenant()

    previous = os.environ.get("ARDA_DATA_DIR")
    os.environ["ARDA_DATA_DIR"] = str(target)
    try:
        return asyncio.run(run())
    finally:
        if previous is None:
            os.environ.pop("ARDA_DATA_DIR", None)
        else:
            os.environ["ARDA_DATA_DIR"] = previous


def markdown_review(review):
    principal = review["principal"]
    lines = ["# Sophia covenant review", "", "Status: **UNSEALED — principal affirmation pending**", "", f"Review SHA-256: `{review['review_sha256']}`", "", review["assent_scope"], "", "## Principal identity", "", f"Historical hash: `{principal['historical_identity_hash']}`", "", f"Current schema hash: `{principal['current_identity_hash']}`", "", "The offered values below are preserved. Additional schema defaults and field renames are shown separately.", "", "```json", json.dumps(principal["offered_identity"], indent=2), "```", "", "Field renames (values preserved):", "", "```json", json.dumps(principal["field_migrations"], indent=2), "```", "", "Schema defaults:", "", "```json", json.dumps(principal["schema_added_defaults"], indent=2), "```", "", "## Runtime", "", "```json", json.dumps(review["runtime"], indent=2), "```"]
    for kind, articles in review["articles"].items():
        lines.extend(["", f"## {kind.title()}", "", f"SHA-256: `{review['article_hashes'][kind]}`", "", "```json", json.dumps(articles, indent=2), "```"])
    lines.extend(["", "## Operational terms", "", f"SHA-256: `{review['terms_hash']}`", "", "```json", json.dumps(review["terms"], indent=2), "```", "", "## Pending principal action", "", review["pending_step"], "", "After the principal explicitly accepts the review hash, the operator may run:", "", "```bash", f".venv/bin/python scripts/manage_sophia_covenant.py seal --review REVIEW.json --accepted-review-sha256 {review['review_sha256']} --principal-affirmation", "```", "", "The native flow obtains the current machine measurements and writes the real manifest and witness events at sealing. It does not reuse a development seal or alter calibration records.", ""])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    prepare = sub.add_parser("review")
    prepare.add_argument("--identity-file", type=Path, required=True)
    prepare.add_argument("--data-root", type=Path, default=DEFAULT_DATA)
    prepare.add_argument("--output", type=Path, required=True)
    seal = sub.add_parser("seal")
    seal.add_argument("--review", type=Path, required=True)
    seal.add_argument("--accepted-review-sha256", required=True)
    seal.add_argument("--principal-affirmation", action="store_true")
    args = parser.parse_args()
    try:
        if args.action == "review":
            review = build_review(args.identity_file, args.data_root)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(review, indent=2) + "\n")
            args.output.with_suffix(".md").write_text(markdown_review(review).replace("--review REVIEW.json", "--review " + shlex.quote(str(args.output))))
            args.output.with_suffix(".sha256").write_text(review["review_sha256"] + "\n")
            print(json.dumps({"state": review["state"], "review": str(args.output), "review_sha256": review["review_sha256"]}))
        else:
            print(json.dumps(seal_review(json.loads(args.review.read_text()), args.accepted_review_sha256, args.principal_affirmation), indent=2, default=str))
    except (ValueError, OSError) as exc:
        parser.exit(2, f"REFUSE: {exc}\n")


if __name__ == "__main__":
    main()
