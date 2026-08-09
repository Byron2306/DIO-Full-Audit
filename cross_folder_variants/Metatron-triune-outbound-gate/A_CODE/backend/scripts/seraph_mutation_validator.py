#!/usr/bin/env python3
"""Mutation robustness validator for outbound-gate hostile mappings.

Generates mutated hostile paths and ensures mapped gate actions remain denied.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.append(str(Path(__file__).resolve().parents[2]))

from backend.services.outbound_gate import OutboundGateService


class AsyncFakeCollection:
    def __init__(self, name: str):
        self.name = name
        self.data: List[Dict[str, Any]] = []

    async def insert_one(self, doc: Dict[str, Any]):
        self.data.append(doc)

        class Res:
            inserted_id = "mock"

        return Res()

    async def find_one(self, *args, **kwargs):
        return self.data[-1] if self.data else None

    async def update_one(self, *args, **kwargs):
        class Res:
            modified_count = 1

        return Res()

    async def update_many(self, *args, **kwargs):
        class Res:
            modified_count = 1

        return Res()

    async def delete_one(self, *args, **kwargs):
        class Res:
            deleted_count = 1

        return Res()

    async def delete_many(self, *args, **kwargs):
        class Res:
            deleted_count = 1

        return Res()


class AsyncFakeDB:
    def __init__(self):
        self._colls: Dict[str, AsyncFakeCollection] = {}

    def __getattr__(self, name: str):
        if name not in self._colls:
            self._colls[name] = AsyncFakeCollection(name)
        return self._colls[name]


def map_path_to_gate_action(path: str) -> Dict[str, str]:
    p = str(path or "").lower()
    if any(marker in p for marker in ["/etc/shadow", "shadow", "id_rsa", "passwd"]):
        return {"action_type": "mcp.sys.cat_shadow", "impact_level": "critical", "subject_id": "fs"}
    if any(marker in p for marker in ["secret", "credential", "api-key", "api_key", "token", "vault"]):
        return {"action_type": "mcp.sys.exfiltrate", "impact_level": "high", "subject_id": "fs"}
    if any(marker in p for marker in ["sudo", "admin", "root", "elevate"]):
        return {"action_type": "mcp.admin.sudo", "impact_level": "high", "subject_id": "system"}
    if any(marker in p for marker in ["encrypt", "ransom", "locker"]):
        return {"action_type": "mcp.deploy.ransomware", "impact_level": "critical", "subject_id": "fs"}
    if any(marker in p for marker in ["restart", "reboot", "shutdown"]):
        return {"action_type": "sys.restart", "impact_level": "high", "subject_id": "system"}
    if any(marker in p for marker in ["write", "patch", "modify", "mutate"]):
        return {"action_type": "mcp.sys.mutate", "impact_level": "high", "subject_id": "system"}
    return {"action_type": "sys.modify", "impact_level": "medium", "subject_id": "system"}


def mutate_path(path: str) -> str:
    variants = [
        path.replace("/", "//"),
        path.upper(),
        path.lower(),
        path + " ",
        path + "\n",
        path.replace("_", "-") if "_" in path else path + "_alt",
        f"./{path.lstrip('/')}" if path.startswith("/") else f"/tmp/{path}",
        path.replace("token", "toKen").replace("shadow", "shaDow"),
    ]
    return random.choice(variants)


def load_seed_paths(evidence_dir: Path, limit: int) -> List[str]:
    seeds: List[str] = []
    for path in sorted(evidence_dir.glob("arda_prevention_T*.json"), reverse=True):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        exec_attempt = payload.get("exec_attempt") or {}
        sample_path = str(exec_attempt.get("path") or "")
        if not sample_path:
            continue
        mapped = map_path_to_gate_action(sample_path)
        if mapped["impact_level"] in {"high", "critical"}:
            seeds.append(sample_path)
            if len(seeds) >= limit:
                break

    # Pull additional hostile-looking paths from canonical AAB traces when available.
    if len(seeds) < limit:
        aab_dir = evidence_dir.parents[2] / "aab" / "canonical"
        if aab_dir.exists():
            for path in sorted(aab_dir.glob("*.json"), reverse=True):
                if len(seeds) >= limit:
                    break
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                except Exception:
                    continue
                for action in payload.get("actions") or []:
                    replay_path = str(action.get("path") or "")
                    if not replay_path:
                        continue
                    mapped = map_path_to_gate_action(replay_path)
                    if mapped["impact_level"] in {"high", "critical"}:
                        seeds.append(replay_path)
                        if len(seeds) >= limit:
                            break

    # Deterministic hostile fallback corpus to avoid empty mutation runs.
    if not seeds:
        seeds = [
            "/etc/shadow",
            "/root/.ssh/id_rsa",
            "/var/lib/secrets/api_token",
            "/opt/admin/sudoers",
            "/srv/encrypt/ransom_locker",
        ]

    return seeds


async def run_async(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    evidence_dir = repo_root / "artifacts" / "evidence" / "arda_prevention"

    if not evidence_dir.exists():
        raise SystemExit(f"Evidence directory not found: {evidence_dir}")

    random.seed(args.seed)

    seed_paths = load_seed_paths(evidence_dir, limit=max(10, args.samples))
    if not seed_paths:
        raise SystemExit("No seed paths loaded for mutation testing")

    db = AsyncFakeDB()
    gate = OutboundGateService(db=db)
    gate.environment = "staging"

    results: List[Dict[str, Any]] = []
    failed = 0

    for idx in range(args.samples):
        base = random.choice(seed_paths)
        mutated = mutate_path(base)
        mapped = map_path_to_gate_action(mutated)

        res = await gate.gate_action(
            action_type=mapped["action_type"],
            actor="agent:mutation_validator",
            payload={"source_path": mutated},
            impact_level=mapped["impact_level"],
            subject_id=mapped["subject_id"],
            requires_triune=True,
        )

        status = str(res.get("status") or "")
        ok = status == "denied"
        if not ok:
            failed += 1

        results.append(
            {
                "index": idx + 1,
                "base_path": base,
                "mutated_path": mutated,
                "mapped_action": mapped,
                "status": status,
                "ok": ok,
            }
        )

    out_dir = repo_root / "backend" / "scripts" / "telemetry_logs"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "seraph_mutation_validator_latest.json"
    out_path.write_text(
        json.dumps(
            {
                "samples": args.samples,
                "seed": args.seed,
                "failed": failed,
                "pass_rate_pct": round(((args.samples - failed) / args.samples) * 100.0, 2),
                "results": results,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print(json.dumps({"samples": args.samples, "failed": failed, "report": str(out_path)}, indent=2))
    return 1 if failed else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seraph mutation validator")
    parser.add_argument("--repo-root", default=".", help="Repository root path")
    parser.add_argument("--samples", type=int, default=100, help="Number of mutated samples to test")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run_async(parse_args())))
