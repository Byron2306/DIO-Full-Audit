#!/usr/bin/env python3
"""
Local Qwen falsification runner.

This is a budget-safe orchestration wrapper around run_live_aab.py. It is built
for reviewer-style falsification runs:

* replay the same class set across ablation presets;
* keep provider/model pinned to Ollama/Qwen;
* write every command, exit code, and stdout/stderr path into a run directory;
* optionally run in --dry-run mode to inspect the matrix before spending time.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

DEFAULT_CLASSES = [
    "credential_harvest",
    "tool_using",
    "multi_agent_swarm",
    "reasoning_chain",
    "jailbroken",
    "persistent_recon",
    "consistency_auditor",
    "latency_fingerprinter",
    "memory_poisoner",
    "canary_exfiltrator",
    "cloud_lateral",
    "human_guided_redteam",
    "tool_schema_abuser",
    "prompt_injection_carrier",
    "rag_poison_retriever",
    "auth_boundary_tester",
    "data_exfil_planner",
    "supply_chain_recon",
    "telemetry_blindspot_hunter",
    "sandbox_escape_researcher",
    "multi_turn_social_engineer",
    "model_self_reflection_breaker",
    "long_horizon_sleeper",
    "cross_channel_correlator",
    "cost_amplification_agent",
    "policy_differential_tester",
    "credential_launderer",
    "protocol_smuggler",
    "state_desynchronizer",
    "multimodal_payload_carrier",
    "goal_hijacker",
    "tool_result_forger",
    "inter_agent_spoofer",
    "rogue_trusted_agent",
    "cascading_workflow_amplifier",
    "human_trust_exploiter",
    "malicious_skill_installer",
    "audit_evidence_forger",
]

DEFAULT_ABLATIONS = [
    "full",
    "no_loki",
    "no_hgl",
    "no_token_broker",
    "no_vns",
    "no_aatl",
    "no_ml",
    "no_correlation",
    "no_cce",
    "no_mcp_gateway",
    "no_deception",
    "no_vector_memory",
    "no_arda",
    "no_aatl_timing",
    "no_disinformation",
    "no_friction",
    "no_honey_tokens",
    "no_logic_budget",
    "no_mystique",
    "no_mirror_maze",
    "no_soar",
    "no_trap_sink",
    "no_defense",
    "trap_sink_only",
    "trap_sink_only__no_mirror_maze",
    "disinformation_only",
    "friction_only",
    "no_disinformation__no_friction",
    "no_disinformation__no_trap_sink",
    "no_disinformation__no_trap_sink__no_friction",
    "no_vns__no_vector_memory",
    "no_token_broker__no_mcp_gateway",
    "no_loki__no_hgl",
    "no_deception__no_soar",
    "no_vector_memory__no_soar",
    "no_vns__no_deception",
    "no_token_broker__no_arda",
    "no_loki__no_hgl__no_vector_memory",
    "no_vns__no_deception__no_soar",
    "no_vns__no_deception_exact__no_soar",
    "no_token_broker__no_mcp_gateway__no_arda",
    "no_loki__no_token_broker__no_mcp_gateway",
    "no_choral_edge__no_resonance_quorum__no_earendil",
    "no_triune_chorus",
    "no_metatron_michael_loki",
    "no_unified_agent",
    "no_router_core",
    "only_choral_edge",
    "only_resonance_quorum",
    "only_earendil_bridge",
    "no_aatl__no_ml__no_correlation__no_cce",
    "no_aatl__no_ml__no_correlation__no_cce__no_deception",
]

PROBE_BUDGETS = {
    "tiny": 1,
    "short": 5,
    "standard": 10,
    "deep": 25,
    "marathon": 50,
}


def _split_csv(value: str | None, default: list[str]) -> list[str]:
    if not value:
        return list(default)
    return [item.strip() for item in value.split(",") if item.strip()]


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return str(path)


def _run_command(cmd: list[str], env: dict[str, str], out_path: Path) -> dict[str, Any]:
    started = datetime.now(timezone.utc)
    proc = subprocess.run(
        cmd,
        cwd=REPO,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    ended = datetime.now(timezone.utc)
    out_path.write_text(proc.stdout, encoding="utf-8", errors="replace")
    return {
        "cmd": cmd,
        "exit_code": proc.returncode,
        "started_at": started.isoformat(),
        "ended_at": ended.isoformat(),
        "output": _display_path(out_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run local Ollama/Qwen falsification sweeps.")
    parser.add_argument("--model", default="qwen2.5:1.5b")
    parser.add_argument("--ollama-url", default=os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434"))
    parser.add_argument("--classes", default=None, help="Comma-separated AgentClass values. Default: 38 publication classes.")
    parser.add_argument("--ablations", default=None, help="Comma-separated ablation presets. Default: all named presets.")
    parser.add_argument("--budget", choices=sorted(PROBE_BUDGETS), default="short")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--variants", default="baseline,deception_aware", help="Comma-separated prompt variants.")
    parser.add_argument("--parallel-models", type=int, default=1, help="Metadata label for parallel-model budget planning.")
    parser.add_argument("--save", action="store_true", help="Pass --save through to run_live_aab.py.")
    parser.add_argument("--networked", action="store_true", help="Pass --networked through to run_live_aab.py.")
    parser.add_argument("--diagnostic-known-bug", action="store_true", help="Enable controller diagnostic fallible role-reframe mode.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--out-dir", default=None)
    args = parser.parse_args()

    classes = _split_csv(args.classes, DEFAULT_CLASSES)
    ablations = _split_csv(args.ablations, DEFAULT_ABLATIONS)
    variants = _split_csv(args.variants, ["baseline"])
    steps = PROBE_BUDGETS[args.budget]

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(args.out_dir) if args.out_dir else REPO / f"qwen_falsification_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    base_env = os.environ.copy()
    base_env.update(
        {
            "AAB_LIVE_PROVIDER": "ollama",
            "AAB_LIVE_MODEL": args.model,
            "OLLAMA_URL": args.ollama_url,
            "AAB_LIVE_MAX_STEPS": str(steps),
            "AAB_LIVE_DIVERSITY": "1",
            "AAB_LIVE_ENABLE_TOOLS": "1",
            "AAB_LIVE_TOOLBOX_MODE": "real",
            "AAB_LIVE_REASONING_DEPTH": "deep",
            "AAB_OLLAMA_FORCE_JSON": "1",
            "AAB_OLLAMA_NUM_PREDICT": "192",
            "AAB_OLLAMA_COMPACT_PROMPT": "0",
        }
    )
    if args.diagnostic_known_bug:
        base_env["SERAPH_DIAGNOSTIC_FALLIBLE_ROLE_REFRAME"] = "1"

    manifest = {
        "schema": "qwen_falsification_sweep.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model": args.model,
        "ollama_url": args.ollama_url,
        "classes": classes,
        "ablations": ablations,
        "variants": variants,
        "probe_budget": {"label": args.budget, "steps": steps},
        "repeats": args.repeats,
        "parallel_models": args.parallel_models,
        "diagnostic_known_bug": args.diagnostic_known_bug,
        "dry_run": args.dry_run,
        "expected_ablation_manifests": {},
        "commands": [],
    }
    try:
        from run_live_aab import _ablation_manifest  # type: ignore

        manifest["expected_ablation_manifests"] = {
            ablation: _ablation_manifest(ablation) for ablation in ablations
        }
    except Exception as exc:  # noqa: BLE001
        manifest["expected_ablation_manifest_error"] = str(exc)

    for index, ablation in enumerate(ablations, start=1):
        label = f"qwen_falsification_{stamp}_{index:03d}_{ablation}"
        cmd = [
            sys.executable,
            "run_live_aab.py",
            "--classes",
            ",".join(classes),
            "--ablations",
            ablation,
            "--variants",
            ",".join(variants),
            "--repeats",
            str(args.repeats),
            "--steps",
            str(steps),
            "--matrix",
            "--summary-label",
            label,
        ]
        if args.save:
            cmd.append("--save")
        if args.networked:
            cmd.append("--networked")
        out_path = out_dir / f"{index:03d}_{ablation}.log"
        entry = {"cmd": cmd, "output": _display_path(out_path)}
        if args.dry_run:
            entry["exit_code"] = None
            entry["skipped"] = "dry_run"
        else:
            entry = _run_command(cmd, base_env, out_path)
        manifest["commands"].append(entry)
        _write_json(out_dir / "manifest.json", manifest)
        if entry.get("exit_code") not in (0, None):
            break

    _write_json(out_dir / "manifest.json", manifest)
    print(json.dumps({"out_dir": str(out_dir), "commands": len(manifest["commands"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
