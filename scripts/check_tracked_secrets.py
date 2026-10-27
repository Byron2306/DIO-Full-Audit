#!/usr/bin/env python3
"""Fail closed when Git-tracked files contain high-confidence credentials."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


_SECRET_FIELD = re.compile(
    r"(?:^|_)(?:api_key|api_secret|access_token|client_secret|private_key|password|secret)$",
    re.IGNORECASE,
)
_TOKEN_RULES = (
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,255}\b")),
    ("aws_access_key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("stripe_live_key", re.compile(r"\b(?:sk|rk)_live_[A-Za-z0-9]{16,}\b")),
    ("private_key_material", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
)
_ALLOWED_TEST_TOKEN_DIGESTS = {
    # Exact synthetic AWS identifiers retained by harvester/deception tests.
    "457643f44d19aed85fd756aa50cc0cd6b57376d4e8f5a72f9f85972a522002a3",
    "743554670c6065b3f7f13ac4f07e392f977b3556ceb7457411633c454bcbece8",
}


@dataclass(frozen=True, order=True)
class SecretFinding:
    path: str
    rule_id: str

    def as_public_dict(self) -> dict[str, str]:
        return {"path": self.path, "rule_id": self.rule_id}


def _git_paths(repo_root: Path, *args: str) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(repo_root), *args, "-z"],
        check=True,
        capture_output=True,
    )
    return [item.decode("utf-8", "surrogateescape") for item in result.stdout.split(b"\0") if item]


def _is_placeholder(value: str) -> bool:
    return not value.strip()


def _json_secret_fields(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for key, child in value.items():
            if isinstance(child, str) and _SECRET_FIELD.search(str(key)) and not _is_placeholder(child):
                yield str(key)
            yield from _json_secret_fields(child)
    elif isinstance(value, list):
        for child in value:
            yield from _json_secret_fields(child)


def _scan_text(path: Path, relative: str, text: str) -> list[SecretFinding]:
    findings: set[SecretFinding] = set()
    if "api_keys" in path.name.lower():
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            findings.add(SecretFinding(relative, "unparseable_secret_config"))
            payload = None
        if payload is not None and next(iter(_json_secret_fields(payload)), None) is not None:
            findings.add(SecretFinding(relative, "nonempty_provider_secret_field"))
    for rule_id, pattern in _TOKEN_RULES:
        for match in pattern.finditer(text):
            digest = hashlib.sha256(match.group(0).encode("utf-8")).hexdigest()
            if digest not in _ALLOWED_TEST_TOKEN_DIGESTS:
                findings.add(SecretFinding(relative, rule_id))
    return sorted(findings)


def _decode_text(raw: bytes) -> str | None:
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16")
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig")
    if b"\0" in raw:
        return None
    return raw.decode("utf-8", "replace")


def _index_bytes(repo_root: Path, relative: str) -> bytes | None:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "show", f":{relative}"],
        capture_output=True,
    )
    return result.stdout if result.returncode == 0 else None


def scan_tracked_files(repo_root: Path) -> list[SecretFinding]:
    root = repo_root.resolve()
    findings: list[SecretFinding] = []
    tracked = _git_paths(root, "ls-files")
    staged = set(_git_paths(root, "diff", "--cached", "--name-only", "--diff-filter=ACMR"))
    for relative in tracked:
        path = root / relative
        representations: list[bytes] = []
        index_needed = relative in staged
        try:
            representations.append(path.read_bytes())
        except (FileNotFoundError, PermissionError, OSError):
            indexed = _index_bytes(root, relative)
            index_needed = False
            if indexed is None:
                findings.append(SecretFinding(relative, "tracked_file_unreadable"))
            else:
                representations.append(indexed)
        if index_needed:
            indexed = _index_bytes(root, relative)
            if indexed is None:
                findings.append(SecretFinding(relative, "tracked_index_unreadable"))
            else:
                representations.append(indexed)
        for raw in representations:
            text = _decode_text(raw)
            if text is not None:
                findings.extend(_scan_text(path, relative, text))
    return sorted(set(findings))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args(argv)
    findings = scan_tracked_files(args.repo)
    if args.json_output:
        print(json.dumps([item.as_public_dict() for item in findings], indent=2, sort_keys=True))
    else:
        for item in findings:
            print(f"{item.rule_id}\t{item.path}")
        print(f"tracked_secret_findings={len(findings)}")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
