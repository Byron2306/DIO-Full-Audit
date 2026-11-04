"""Write the candidate ATLAS domain exploration for Sonoris and Pictora."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from atlas.creative_organ_exploration import resolve_creative_organs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "artifacts/atlas/sonoris_pictora_domain_exploration.json")
    args = parser.parse_args()
    result = resolve_creative_organs(ROOT)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    counts = result["candidate_domain_counts"]
    lines = ["# Sonoris + Pictora ATLAS domain exploration", "",
             f"ATLAS domain nodes: {result['atlas_domain_nodes_total']}. Explicit candidate domains: **{counts['unique_union']}**.",
             f"Sonoris: {counts['sonoris']}; Pictora: {counts['pictora']}; shared: {counts['shared']}.", "",
             "These are analogical exploration candidates. Execution-grade signatures for these organs: **0**.",
             "Commercial validation and release authority remain unproved.", "",
             "| ATLAS ID | Domain | Work hypothesis | Sonoris | Pictora |", "|---|---|---|:---:|:---:|"]
    for row in result["domains"]:
        lines.append(f"| {row['domain_id']} | {row['domain_name']} | {row['domain_task_hypothesis']} | {'✓' if 'sonoris' in row['organs'] else ''} | {'✓' if 'pictora' in row['organs'] else ''} |")
    lines += ["", "Source: current ATLAS domain registry and DIO creative organ registry. The JSON companion records source hashes and gaps per domain."]
    markdown = args.out.with_suffix(".md")
    markdown.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"json": str(args.out), "markdown": str(markdown), "counts": counts}))


if __name__ == "__main__":
    main()
