#!/usr/bin/env python3
"""
Static governance guardrails for backend control plane.

Checks:
1) Mutating endpoints must require write/admin-equivalent dependency.
2) No shell=True / create_subprocess_shell usage.
3) No direct command queue writes outside governed_dispatch service.
"""

from __future__ import annotations

import re
import sys
import os
from pathlib import Path
from typing import List, Tuple


BACKEND_ROOT = Path(__file__).resolve().parents[1]
ROUTERS_ROOT = BACKEND_ROOT / "routers"
DISPATCH_HELPER = BACKEND_ROOT / "services" / "governed_dispatch.py"
MUTATING_ENDPOINT_SCOPE = {
    "routers/agent_commands.py",
    "routers/enterprise.py",
    "routers/integrations.py",
    "routers/quarantine.py",
    "routers/response.py",
    "routers/sandbox.py",
    "routers/soar.py",
    "routers/swarm.py",
    "routers/unified_agent.py",
    "routers/vpn.py",
    "routers/websocket.py",
    "routers/zero_trust.py",
    "routers/advanced.py",
    "routers/cspm.py",
    "routers/identity.py",
    "routers/kernel_sensors.py",
    "routers/secure_boot.py",
}
SHELL_ALLOWLIST = {
    "threat_response.py",
}


def _iter_python_files(root: Path):
    for path in sorted(root.rglob("*.py")):
        if "tests/" in path.as_posix():
            continue
        yield path


def _check_mutating_endpoint_dependencies() -> List[str]:
    violations: List[str] = []
    route_pattern = re.compile(r"^\s*@router\.(post|put|patch|delete)\(", re.IGNORECASE)
    allowed_dep_markers = (
        "Depends(check_permission(\"write\"))",
        "Depends(check_permission('write'))",
        "Depends(check_permission(\"delete\"))",
        "Depends(check_permission('delete'))",
        "Depends(check_permission(\"admin\"))",
        "Depends(check_permission('admin'))",
        "Depends(check_permission(\"manage_users\"))",
        "Depends(check_permission('manage_users'))",
        "Depends(verify_swarm_agent_token)",
        "Depends(verify_agent_auth)",
        "Depends(verify_integrations_machine_token",
        "Depends(verify_",
        "Depends(require_machine_token",
        "Depends(optional_machine_token",
    )

    for path in _iter_python_files(ROUTERS_ROOT):
        rel = path.relative_to(BACKEND_ROOT).as_posix()
        if rel not in MUTATING_ENDPOINT_SCOPE:
            continue
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        idx = 0
        while idx < len(lines):
            line = lines[idx]
            if not route_pattern.search(line):
                idx += 1
                continue

            fn_idx = idx + 1
            while fn_idx < len(lines) and "def " not in lines[fn_idx]:
                fn_idx += 1
            if fn_idx >= len(lines):
                break

            signature_lines = [lines[fn_idx]]
            sig_end = fn_idx
            while sig_end < len(lines) and not lines[sig_end].strip().endswith("):"):
                sig_end += 1
                if sig_end < len(lines):
                    signature_lines.append(lines[sig_end])
            signature = "\n".join(signature_lines)
            if not any(marker in signature for marker in allowed_dep_markers):
                violations.append(
                    f"{path.relative_to(BACKEND_ROOT)}:{idx+1} mutating endpoint missing write/machine auth dependency"
                )
            idx = sig_end + 1

    return violations


def _check_shell_execution_patterns() -> List[str]:
    violations: List[str] = []
    shell_true_pattern = re.compile(
        r"subprocess\.(?:run|Popen|call|check_call|check_output)\([\s\S]{0,400}?shell\s*=\s*True",
        re.MULTILINE,
    )
    create_shell_pattern = re.compile(r"create_subprocess_shell\(", re.MULTILINE)

    for path in _iter_python_files(BACKEND_ROOT):
        rel = path.relative_to(BACKEND_ROOT).as_posix()
        if rel.startswith("scripts/"):
            continue
        if rel in SHELL_ALLOWLIST:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if shell_true_pattern.search(text):
            violations.append(f"{path.relative_to(BACKEND_ROOT)} uses subprocess(..., shell=True)")
        if create_shell_pattern.search(text):
            violations.append(f"{path.relative_to(BACKEND_ROOT)} uses create_subprocess_shell(...)")
    return violations


def _check_direct_queue_writes() -> List[str]:
    violations: List[str] = []
    direct_patterns: Tuple[str, ...] = (
        "command_queue.insert_one(",
        "agent_commands.insert_one(",
    )

    for path in _iter_python_files(BACKEND_ROOT):
        rel = path.relative_to(BACKEND_ROOT).as_posix()
        if rel.startswith("scripts/"):
            continue
        if path.resolve() == DISPATCH_HELPER.resolve():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in direct_patterns:
            if pattern in text:
                violations.append(
                    f"{path.relative_to(BACKEND_ROOT)} contains direct queue write '{pattern}'"
                )
    return violations


def main() -> int:
    all_violations: List[str] = []
    all_violations.extend(_check_mutating_endpoint_dependencies())
    all_violations.extend(_check_shell_execution_patterns())
    all_violations.extend(_check_direct_queue_writes())

    strict = os.environ.get("GOVERNANCE_GUARDRAILS_STRICT", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if all_violations:
        mode = "strict" if strict else "advisory"
        print(f"Governance guardrail violations detected ({mode} mode):")
        for item in all_violations:
            print(f" - {item}")
        return 1 if strict else 0

    print("Governance guardrails passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
