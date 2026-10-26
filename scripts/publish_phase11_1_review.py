#!/usr/bin/env python3
"""Compile and optionally publish a private GitHub review bundle for Phase 11.1."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any


class ReviewPublishError(RuntimeError):
    pass


TEXT_SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{40,}\b"),
)


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ReviewPublishError(f"JSON object required: {path}")
    return value


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _one(root: Path, pattern: str) -> Path:
    rows = sorted(root.glob(pattern))
    if len(rows) != 1:
        raise ReviewPublishError(f"expected exactly one {pattern}, found {len(rows)}")
    return rows[0]


def _safe_under(path: Path, root: Path) -> Path:
    if path.is_symlink():
        raise ReviewPublishError(f"symlink refused: {path}")
    resolved, boundary = path.resolve(), root.resolve()
    if resolved != boundary and boundary not in resolved.parents:
        raise ReviewPublishError(f"path escapes run root: {path}")
    return resolved


def _scan_secret(path: Path) -> None:
    if path.suffix.lower() not in {".json", ".html", ".md", ".txt"}:
        return
    text = path.read_text(encoding="utf-8", errors="ignore")
    if any(pattern.search(text) for pattern in TEXT_SECRET_PATTERNS):
        raise ReviewPublishError(f"credential-like material refused: {path.name}")


def compile_review_bundle(run_root: Path, destination: Path, *, include_originals: bool = False) -> dict[str, Any]:
    run_root, destination = run_root.resolve(), destination.resolve()
    proof_dir = run_root / "fulfilment" / "proof"
    proof_manifest_path = proof_dir / "PROOF_MANIFEST.json"
    if not proof_manifest_path.exists():
        raise ReviewPublishError("Phase 11.1 proof manifest not found")
    proof_manifest = _load(proof_manifest_path)
    if proof_manifest.get("external_release") is not False or (proof_manifest.get("human_gate") or {}).get("state") != "NEEDS_YOU":
        raise ReviewPublishError("proof manifest does not preserve the human release boundary")
    case_id = str(proof_manifest.get("case_id") or "").strip()
    if not re.fullmatch(r"CASE-[A-Z0-9]{8,40}", case_id):
        raise ReviewPublishError("invalid proof case_id")
    expected = {str(row["filename"]): str(row["sha256"]) for row in proof_manifest.get("artifacts") or []}
    if not expected:
        raise ReviewPublishError("proof manifest contains no artifacts")
    for filename, digest in expected.items():
        path = _safe_under(proof_dir / filename, proof_dir)
        if not path.is_file() or _sha(path) != digest:
            raise ReviewPublishError(f"proof artifact hash mismatch: {filename}")

    attachment_path = _one(run_root, "state/vesper/quarantine/*/ATTACHMENT_INTAKE.json")
    vesper_path = _one(run_root, "state/vesper/intakes/*/VESPER_INTAKE_RECEIPT.json")
    journey_path = _one(run_root, "state/phase11_1/PHASE11_1_JOURNEY.json")
    outlook_path = _one(run_root, "state/outlook_smart_bot/drafts/*.json")
    attachment = _load(attachment_path)
    vesper = _load(vesper_path)
    journey = _load(journey_path)
    outlook = _load(outlook_path)
    if attachment.get("policy") != "quarantine_only" or attachment.get("external_effects") is not False:
        raise ReviewPublishError("Vesper attachment boundary failed")
    if outlook.get("state") != "DRAFT_ONLY" or outlook.get("sent") is not False or outlook.get("send_authorized") is not False:
        raise ReviewPublishError("Outlook draft boundary failed")
    if journey.get("external_delivery") != "REFUSE" or journey.get("human_release") != "NEEDS_YOU":
        raise ReviewPublishError("Phase 11.1 journey release boundary failed")

    if destination.exists():
        raise ReviewPublishError(f"destination already exists: {destination}")
    destination.mkdir(parents=True)
    copied: list[dict[str, Any]] = []
    for filename in sorted(expected):
        source = proof_dir / filename
        target = destination / filename
        shutil.copy2(source, target)
        copied.append({"path": target.name, "sha256": _sha(target), "classification": "proof_artifact"})
    shutil.copy2(proof_manifest_path, destination / "PROOF_MANIFEST.json")
    copied.append({"path": "PROOF_MANIFEST.json", "sha256": _sha(destination / "PROOF_MANIFEST.json"), "classification": "integrity_manifest"})
    for name in ("EVIDENCE_RECONCILIATION.json", "EVIDENCE_RECONCILIATION.html"):
        source = proof_dir / name
        if source.is_file():
            shutil.copy2(source, destination / name)
            copied.append({"path": name, "sha256": _sha(destination / name), "classification": "human_reconciliation_register"})

    sanitized_attachment = json.loads(json.dumps(attachment))
    for row in sanitized_attachment.get("attachments") or []:
        row["quarantine_path"] = Path(str(row.get("quarantine_path") or "")).name
        row["extracted_text"] = "[WITHHELD_FROM_REVIEW_INDEX; inspect original proof/source only]"
    (destination / "VESPER_ATTACHMENT_RECEIPT.json").write_text(json.dumps(sanitized_attachment, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    shutil.copy2(vesper_path, destination / "VESPER_INTAKE_RECEIPT.json")
    shutil.copy2(journey_path, destination / "PHASE11_1_JOURNEY.json")
    outlook_summary = {key: outlook.get(key) for key in ("schema", "draft_id", "state", "human_approval", "send_authorized", "sent", "message_id", "external_effects", "attachments")}
    for row in outlook_summary.get("attachments") or []:
        row["path"] = Path(str(row.get("path") or "")).name
    (destination / "OUTLOOK_DRAFT_REVIEW.json").write_text(json.dumps(outlook_summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    for name, classification in (("VESPER_ATTACHMENT_RECEIPT.json", "custody_receipt"), ("VESPER_INTAKE_RECEIPT.json", "intake_receipt"), ("PHASE11_1_JOURNEY.json", "journey_receipt"), ("OUTLOOK_DRAFT_REVIEW.json", "draft_metadata")):
        copied.append({"path": name, "sha256": _sha(destination / name), "classification": classification})

    if include_originals:
        originals = destination / "original_attachments"
        originals.mkdir()
        for row in attachment.get("attachments") or []:
            source = _safe_under(Path(str(row["quarantine_path"])), run_root)
            if _sha(source) != row.get("sha256"):
                raise ReviewPublishError(f"original attachment hash mismatch: {row.get('filename')}")
            target = originals / source.name
            shutil.copy2(source, target)
            copied.append({"path": f"original_attachments/{target.name}", "sha256": _sha(target), "classification": "sensitive_original"})

    for row in copied:
        _scan_secret(destination / row["path"])
    review_manifest = {
        "schema": "dio.phase11_1.github_review_bundle.v1", "case_id": case_id, "intake_id": journey.get("intake_id"),
        "source_proof_fingerprint": proof_manifest.get("proof_fingerprint"), "include_originals": include_originals,
        "privacy_boundary": "PRIVATE_REPOSITORY_REQUIRED", "external_release": "REFUSE", "human_review": "NEEDS_YOU",
        "files": copied,
    }
    review_manifest["bundle_fingerprint"] = "sha256:" + hashlib.sha256(json.dumps(review_manifest, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    (destination / "REVIEW_MANIFEST.json").write_text(json.dumps(review_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (destination / "REVIEW_INDEX.md").write_text(
        f"# DIO Phase 11.1 review — {case_id}\n\n"
        "Start with `EVIDENCE_RECONCILIATION.html`, then `EVIDENCE_PACK.html` or `EVIDENCE_PACK.pdf`. Verify `PROOF_MANIFEST.json`, then inspect the Vesper and Outlook receipts.\n\n"
        "This bundle is review material, not a finding of contractual fulfilment, legal advice, waiver or external-release authority.\n",
        encoding="utf-8",
    )
    return review_manifest


def _run(args: list[str], *, cwd: Path | None = None) -> str:
    completed = subprocess.run(args, cwd=cwd, check=False, text=True, capture_output=True)
    if completed.returncode:
        raise ReviewPublishError(f"command failed ({args[0]}): {(completed.stderr or completed.stdout).strip()}")
    return completed.stdout.strip()


def publish_private_review(bundle: Path, *, repo: str, branch: str | None = None) -> dict[str, str]:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*", repo):
        raise ReviewPublishError("--repo must be OWNER/REPOSITORY")
    info = json.loads(_run(["gh", "repo", "view", repo, "--json", "visibility,defaultBranchRef,nameWithOwner"]))
    if info.get("visibility") != "PRIVATE":
        raise ReviewPublishError("review publication is permitted only to a PRIVATE GitHub repository")
    manifest = _load(bundle / "REVIEW_MANIFEST.json")
    case_id = str(manifest["case_id"])
    resolved_branch = branch or f"dio-review/{case_id.lower()}"
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{2,119}", resolved_branch) or ".." in resolved_branch:
        raise ReviewPublishError("unsafe branch name")
    with tempfile.TemporaryDirectory(prefix="dio-review-publish-") as temp:
        checkout = Path(temp) / "repo"
        _run(["gh", "repo", "clone", repo, str(checkout), "--", "--depth=1"])
        _run(["git", "switch", "-c", resolved_branch], cwd=checkout)
        target = checkout / "reviews" / case_id
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(bundle, target)
        _run(["git", "add", "--", str(target.relative_to(checkout))], cwd=checkout)
        _run(["git", "commit", "-m", f"Add governed review bundle {case_id}"], cwd=checkout)
        _run(["git", "push", "-u", "origin", resolved_branch], cwd=checkout)
        pr_url = _run(["gh", "pr", "create", "--repo", repo, "--base", info["defaultBranchRef"]["name"], "--head", resolved_branch, "--draft", "--title", f"Review {case_id}", "--body", "Governed Phase 11.1 evidence review bundle. Human review is required; external release remains refused."], cwd=checkout)
    return {"repo": repo, "branch": resolved_branch, "pull_request": pr_url, "case_id": case_id}


def main() -> int:
    parser = argparse.ArgumentParser(description="Compile and safely publish a Phase 11.1 GitHub review bundle.")
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=Path("/tmp/dio-phase11-1-review"))
    parser.add_argument("--repo", help="Required for --publish; must be a private OWNER/REPOSITORY")
    parser.add_argument("--branch")
    parser.add_argument("--include-originals", action="store_true", help="Include sensitive quarantined original bytes")
    parser.add_argument("--publish", action="store_true", help="Push a branch and create a draft PR; omitted means dry-run compilation only")
    args = parser.parse_args()
    manifest = compile_review_bundle(args.run_root, args.output, include_originals=args.include_originals)
    archive = args.output.with_suffix(".zip")
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zipped:
        for path in sorted(args.output.rglob("*")):
            if path.is_file():
                zipped.write(path, path.relative_to(args.output.parent))
    result: dict[str, Any] = {"state": "COMPILED_DRY_RUN", "case_id": manifest["case_id"], "bundle": str(args.output), "archive": str(archive), "fingerprint": manifest["bundle_fingerprint"]}
    if args.publish:
        if not args.repo:
            raise ReviewPublishError("--repo is required with --publish")
        result.update(publish_private_review(args.output, repo=args.repo, branch=args.branch))
        result["state"] = "PUBLISHED_PRIVATE_DRAFT_PR"
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ReviewPublishError as exc:
        raise SystemExit(f"REFUSE: {exc}")
