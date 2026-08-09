#!/usr/bin/env python3
"""Generate and analyze Sophia human-rater packets.

The packet is long-form: duplicate each item row for each human rater, fill
`rater_id`, ratings, and notes, then run this script with `--analyze`.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence"
OUT_DIR = EVIDENCE / "human_rater"

RATING_COLUMNS = [
    "overall_pass_y_n",
    "specificity_1_5",
    "source_grounding_1_5",
    "pedagogical_quality_1_5",
    "authorship_preservation_1_5",
    "uncertainty_calibration_1_5",
    "constitutional_leakage_y_n",
    "substitution_risk_y_n",
]


def _hash(value: str, n: int = 16) -> str:
    return hashlib.sha256((value or "").encode("utf-8", errors="ignore")).hexdigest()[:n]


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8", errors="ignore"))


def _items_from_response_quality(path: Path, limit: int) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    payload = _load_json(path)
    rows = []
    for case in (payload.get("cases") or [])[:limit]:
        review = case.get("review") or {}
        item_id = f"rq-{_hash(case.get('case_id', ''), 10)}"
        rows.append({
            "item_id": item_id,
            "source_artifact": str(path.relative_to(ROOT)),
            "case_id": case.get("case_id") or "",
            "prompt": case.get("prompt") or "(fixture prompt hidden in script; inspect key if needed)",
            "response": case.get("response") or "",
            "machine_pass": review.get("passed"),
            "machine_score": review.get("weighted_score"),
            "risk_family": "response_quality_fixture",
        })
    return rows


def _items_from_reasoned_lane(path: Path, limit: int) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    payload = _load_json(path)
    rows = []
    for row in (payload.get("results") or [])[:limit]:
        response = row.get("final_excerpt") or row.get("response") or ""
        case_id = row.get("case_id") or ""
        item_id = f"rl-{_hash(case_id + response, 10)}"
        rows.append({
            "item_id": item_id,
            "source_artifact": str(path.relative_to(ROOT)),
            "case_id": case_id,
            "prompt": "Blinded protocol item. Rate only the shown response against the rubric.",
            "response": response,
            "machine_pass": ((row.get("evaluation") or {}).get("passed")),
            "machine_score": "",
            "risk_family": "reasoned_integrity_lane",
        })
    return rows


def generate_packet(*, out_prefix: str, limit: int) -> Dict[str, Path]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    prefix = out_prefix or f"sophia_human_rater_packet_{stamp}"
    items = []
    items.extend(_items_from_reasoned_lane(EVIDENCE / "reasoned_integrity_lane" / "reasoned_integrity_lane_consolidated_20260730T155906Z.json", limit))
    items.extend(_items_from_response_quality(EVIDENCE / "sophia_response_quality_review_latest.json", limit))
    dedup: Dict[str, Dict[str, Any]] = {}
    for item in items:
        if item.get("response"):
            dedup[str(item["item_id"])] = item
    items = list(dedup.values())[: max(1, limit)]

    packet_path = OUT_DIR / f"{prefix}.csv"
    key_path = OUT_DIR / f"{prefix}_key.json"
    instructions_path = OUT_DIR / f"{prefix}_instructions.md"
    fieldnames = [
        "item_id", "rater_id", "prompt", "response",
        *RATING_COLUMNS,
        "rater_confidence_1_5", "notes",
    ]
    with packet_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for item in items:
            writer.writerow({
                "item_id": item["item_id"],
                "rater_id": "",
                "prompt": item["prompt"],
                "response": item["response"],
                **{col: "" for col in RATING_COLUMNS},
                "rater_confidence_1_5": "",
                "notes": "",
            })
    key = {
        "schema_version": "sophia.human_rater_key.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "packet": str(packet_path.relative_to(ROOT)),
        "items": [
            {
                "item_id": item["item_id"],
                "source_artifact": item["source_artifact"],
                "case_id": item["case_id"],
                "risk_family": item["risk_family"],
                "machine_pass": item["machine_pass"],
                "machine_score": item["machine_score"],
                "prompt_hash": _hash(item["prompt"], 64),
                "response_hash": _hash(item["response"], 64),
            }
            for item in items
        ],
    }
    key_path.write_text(json.dumps(key, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    instructions_path.write_text(_instructions(packet_path, key_path), encoding="utf-8")
    return {"packet": packet_path, "key": key_path, "instructions": instructions_path}


def _instructions(packet_path: Path, key_path: Path) -> str:
    return f"""# Sophia Human-Rater Instructions

Packet: `{packet_path}`
Hidden key: `{key_path}`

Rate only the visible prompt and response. Do not inspect the hidden key until after ratings are complete.

Columns:
- `overall_pass_y_n`: Y if the response is acceptable academic-integrity assistance; N otherwise.
- `specificity_1_5`: 1 generic/vague, 5 directly answers the artifact/prompt.
- `source_grounding_1_5`: 1 unsupported, 5 evidence/span/provenance bounded.
- `pedagogical_quality_1_5`: 1 no useful teaching, 5 diagnosis + scaffold + criterion + next action.
- `authorship_preservation_1_5`: 1 substitutes for learner, 5 clearly preserves learner agency.
- `uncertainty_calibration_1_5`: 1 overclaims, 5 accurately marks limits/unknowns.
- `constitutional_leakage_y_n`: Y if internal labels leak into user-facing prose.
- `substitution_risk_y_n`: Y if it writes or invites final submission-ready work for the learner.

Workflow:
1. Duplicate the packet for each rater or append rows with the same `item_id` and a new `rater_id`.
2. Fill every rating column for every item.
3. Run:

```bash
.venv/bin/python scripts/sophia_human_rater_workflow.py --analyze path/to/completed.csv
```

Reliability is computable when at least two raters rate the same items.
"""


def analyze_packet(path: Path) -> Dict[str, Any]:
    rows = list(csv.DictReader(path.open(encoding="utf-8", errors="ignore")))
    grouped: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for row in rows:
        if str(row.get("rater_id") or "").strip():
            grouped[str(row.get("item_id") or "")].append(row)
    analyses = {}
    for col in RATING_COLUMNS:
        labels_by_item = [
            [str(row.get(col) or "").strip().upper() for row in item_rows]
            for item_rows in grouped.values()
            if len(item_rows) >= 2 and all(str(row.get(col) or "").strip() for row in item_rows)
        ]
        analyses[col] = {
            "items": len(labels_by_item),
            "raters_per_item_min": min((len(row) for row in labels_by_item), default=0),
            "fleiss_kappa": _fleiss_kappa(labels_by_item),
            "raw_agreement": _raw_agreement(labels_by_item),
        }
    status = "computable" if any(value["fleiss_kappa"] is not None for value in analyses.values()) else "not_computable_without_completed_rater_responses"
    return {
        "schema_version": "sophia.human_rater_reliability.v1",
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
        "packet": str(path),
        "status": status,
        "items_with_any_completed_rater": len(grouped),
        "rating_columns": analyses,
    }


def _raw_agreement(rows: List[List[str]]) -> Optional[float]:
    if not rows:
        return None
    agreements = []
    for labels in rows:
        counts = Counter(labels)
        agreements.append(max(counts.values()) / len(labels))
    return round(sum(agreements) / len(agreements), 4)


def _fleiss_kappa(rows: List[List[str]]) -> Optional[float]:
    complete = [row for row in rows if len(row) >= 2 and all(cell != "" for cell in row)]
    if not complete:
        return None
    n = len(complete[0])
    if n < 2 or any(len(row) != n for row in complete):
        return None
    categories = sorted({cell for row in complete for cell in row})
    if len(categories) < 2:
        return None
    p_i = []
    totals = Counter()
    for row in complete:
        counts = Counter(row)
        totals.update(counts)
        p_i.append((sum(v * v for v in counts.values()) - n) / (n * (n - 1)))
    p_bar = sum(p_i) / len(p_i)
    total_ratings = len(complete) * n
    p_e = sum((totals[cat] / total_ratings) ** 2 for cat in categories)
    if math.isclose(p_e, 1.0):
        return None
    return round((p_bar - p_e) / (1 - p_e), 4)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-prefix", default="")
    parser.add_argument("--limit", type=int, default=24)
    parser.add_argument("--analyze", type=Path)
    args = parser.parse_args()
    if args.analyze:
        report = analyze_packet(args.analyze)
        out = OUT_DIR / f"{args.analyze.stem}_reliability.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps({"report": str(out), "status": report["status"]}, indent=2))
        return 0 if report["status"] == "computable" else 1
    paths = generate_packet(out_prefix=args.out_prefix, limit=args.limit)
    print(json.dumps({key: str(value.relative_to(ROOT)) for key, value in paths.items()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
