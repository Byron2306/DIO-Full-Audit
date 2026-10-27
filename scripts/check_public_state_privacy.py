#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Iterable, Mapping, Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.classify_public_state import classify_path, load_policy


POLICY_PATH = ROOT / "config" / "public_state_policy.json"
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?<![A-Za-z0-9])(?:\+?27|0)[ -]?(?:\d[ -]?){8,10}(?![A-Za-z0-9])")
CUSTOMER_RE = re.compile(r'"(?:customer|conversation|mail|order|transaction)_id"\s*:\s*"(?!\[REDACTED\]|REDACTED|null)[^"]+"', re.I)
HOST_PATH_RE = re.compile(r"(?:/(?:home|Users|data)/[^\s\"']+|[A-Za-z]:(?:\\\\)Users(?:\\\\)[^\s\"']+)")


@dataclass(frozen=True, order=True)
class PrivacyFinding:
    path: str
    rule: str


def scan_content(path: Path, content: bytes, classification: str) -> list[PrivacyFinding]:
    if classification != "redacted_fixture":
        return []
    if b"\x00" in content:
        return [PrivacyFinding(path.as_posix(), "binary_redacted_fixture")]
    text = content.decode("utf-8-sig", errors="replace")
    findings: list[PrivacyFinding] = []
    checks = (
        ("phone", PHONE_RE),
        ("customer_identifier", CUSTOMER_RE),
        ("absolute_host_path", HOST_PATH_RE),
    )
    reserved_domains = {"example.com", "example.org", "example.net"}
    if any(match.group(0).rsplit("@", 1)[-1].lower() not in reserved_domains for match in EMAIL_RE.finditer(text)):
        findings.append(PrivacyFinding(path.as_posix(), "email"))
    for rule, pattern in checks:
        if pattern.search(text):
            findings.append(PrivacyFinding(path.as_posix(), rule))
    return findings


def scan_tracked_paths(
    repo_root: Path,
    paths: Iterable[Path],
    policy: Mapping[str, Any],
    *,
    content_loader: Callable[[Path], bytes],
) -> list[PrivacyFinding]:
    findings: list[PrivacyFinding] = []
    for path in sorted(paths, key=lambda item: item.as_posix()):
        classification = classify_path(path, policy)
        if classification is None:
            findings.append(PrivacyFinding(path.as_posix(), "unclassified_public_state"))
        elif classification == "private_operational_state":
            findings.append(PrivacyFinding(path.as_posix(), "tracked_private_operational_state"))
        elif classification == "generated_output":
            findings.append(PrivacyFinding(path.as_posix(), "tracked_generated_output"))
        elif classification == "redacted_fixture":
            findings.extend(scan_content(path, content_loader(path), classification))
    return sorted(set(findings))


def _tracked_paths(repo_root: Path, roots: Iterable[str]) -> list[Path]:
    command = ["git", "ls-files", "-z", "--", *roots]
    result = subprocess.run(command, cwd=repo_root, check=True, capture_output=True)
    return [Path(item.decode("utf-8")) for item in result.stdout.split(b"\0") if item]


def _indexed_content(repo_root: Path, path: Path) -> bytes:
    result = subprocess.run(
        ["git", "show", f":{path.as_posix()}"],
        cwd=repo_root,
        check=False,
        capture_output=True,
    )
    if result.returncode:
        raise RuntimeError(f"Cannot read indexed content for {path.as_posix()}")
    return result.stdout


def main() -> int:
    policy = load_policy(POLICY_PATH)
    paths = _tracked_paths(ROOT, policy["managed_roots"])
    findings = scan_tracked_paths(ROOT, paths, policy, content_loader=lambda path: _indexed_content(ROOT, path))
    print(json.dumps({"public_state_findings": len(findings), "findings": [asdict(item) for item in findings]}, sort_keys=True))
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
