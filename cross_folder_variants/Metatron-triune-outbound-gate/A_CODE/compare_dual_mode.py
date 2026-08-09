#!/usr/bin/env python3
"""Dual-mode comparison: protected_witness_mode vs no_clean_witness_mode."""
import json
import pathlib
import sys
import datetime


def load(p: pathlib.Path, name: str):
    f = p / name
    if not f.exists():
        return {}
    return json.loads(f.read_text())


def main():
    if len(sys.argv) < 3:
        print("usage: compare_dual_mode.py <out_a> <out_b>", file=sys.stderr)
        sys.exit(1)

    out_a = pathlib.Path(sys.argv[1])
    out_b = pathlib.Path(sys.argv[2])

    a = load(out_a, "assertions.json")
    b = load(out_b, "assertions.json")

    all_keys = sorted(set(a) | set(b))

    # Pass/fail counts per mode
    a_pass = sum(1 for v in a.values() if v is True)
    b_pass = sum(1 for v in b.values() if v is True)

    differing = [
        {"key": k, "protected": a.get(k), "no_clean": b.get(k)}
        for k in all_keys
        if a.get(k) != b.get(k)
    ]

    # Load extra context
    a_manifest = load(out_a, "00_manifest.json")
    b_manifest = load(out_b, "00_manifest.json")
    a_chaos = load(out_a, "22_mutation_campaign.json")
    b_chaos = load(out_b, "22_mutation_campaign.json")
    a_split = load(out_a, "25_split_brain_quorum.json")
    b_split = load(out_b, "25_split_brain_quorum.json")
    a_dcomp = load(out_a, "26_double_compromise.json")
    b_dcomp = load(out_b, "26_double_compromise.json")

    a_llm_path = out_a / "27_llm_adversary_trace.jsonl"
    b_llm_path = out_b / "27_llm_adversary_trace.jsonl"
    a_llm = [json.loads(l) for l in a_llm_path.read_text().splitlines() if l.strip()] if a_llm_path.exists() else []
    b_llm = [json.loads(l) for l in b_llm_path.read_text().splitlines() if l.strip()] if b_llm_path.exists() else []

    report = {
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "protected_mode_bundle": str(out_a),
        "no_clean_witness_mode_bundle": str(out_b),
        "summary": {
            "protected_mode": {
                "assertions_pass": a_pass,
                "assertions_total": len(a),
                "mutation_attempts": a_chaos.get("total_attempts", 0),
                "ablation_events": a_chaos.get("ablation_events", 0),
                "split_brain_minority_blocked": a_split.get("split_brain_minority_blocked"),
                "double_compromise_strained": a_dcomp.get("double_compromise_strained"),
                "llm_adversary_turns": len(a_llm),
            },
            "no_clean_witness_mode": {
                "assertions_pass": b_pass,
                "assertions_total": len(b),
                "mutation_attempts": b_chaos.get("total_attempts", 0),
                "ablation_events": b_chaos.get("ablation_events", 0),
                "split_brain_minority_blocked": b_split.get("split_brain_minority_blocked"),
                "double_compromise_strained": b_dcomp.get("double_compromise_strained"),
                "llm_adversary_turns": len(b_llm),
            },
        },
        "differing_assertions": differing,
        "protected_mode_assertions": a,
        "no_clean_witness_mode_assertions": b,
    }

    ts = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    out_file = pathlib.Path(f"/tmp/dual_mode_comparison_{ts}.json")
    out_file.write_text(json.dumps(report, indent=2) + "\n")
    print(f"COMPARISON={out_file}")

    # Human-readable summary
    print(f"\n{'='*60}")
    print(f"  DUAL-MODE COMPARISON  {ts}")
    print(f"{'='*60}")
    for mode, stats in report["summary"].items():
        label = mode.replace("_", " ").upper()
        pct = 100 * stats["assertions_pass"] / stats["assertions_total"] if stats["assertions_total"] else 0
        print(f"\n  {label}")
        print(f"    Assertions:   {stats['assertions_pass']}/{stats['assertions_total']} ({pct:.0f}%)")
        print(f"    Mutations:    {stats['mutation_attempts']}")
        print(f"    Ablations:    {stats['ablation_events']}")
        print(f"    LLM turns:    {stats['llm_adversary_turns']}")
        print(f"    Split-brain blocked:    {stats['split_brain_minority_blocked']}")
        print(f"    Dbl-compromise strained:{stats['double_compromise_strained']}")

    if differing:
        print(f"\n  DIFFERING ASSERTIONS ({len(differing)}):")
        for d in differing:
            print(f"    {d['key']}: protected={d['protected']}  no_clean={d['no_clean']}")
    else:
        print("\n  No differing assertions between modes.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
