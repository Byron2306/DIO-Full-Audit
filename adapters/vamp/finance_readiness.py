from __future__ import annotations

import hashlib
import json
from typing import Any


def _fingerprint(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def map_finance_objectives(manifest: dict[str, Any]) -> dict[str, Any]:
    contract = manifest["artifact_contract"]
    if contract["kind"] != "finance_readiness":
        raise ValueError("VAMP finance objective mapping requires Finance Readiness Studio")
    venture = contract["venture"]
    objectives = []
    for index, use in enumerate(venture.get("use_of_funds") or [], 1):
        row = {
            "objective_id": f"FIN-OBJ-{index:02d}",
            "objective": f"Deploy funding allocation for {use}",
            "milestones": [
                {"milestone_id": f"FIN-OBJ-{index:02d}-M1", "state": "PLANNED", "evidence_required": "authorised purchase or allocation record"},
                {"milestone_id": f"FIN-OBJ-{index:02d}-M2", "state": "PLANNED", "evidence_required": "post-deployment outcome or operational record"},
            ],
            "performance_decision": "NOT_MADE",
        }
        row["fingerprint"] = _fingerprint(row)
        objectives.append(row)
    if not objectives:
        raise ValueError("Finance Readiness Studio requires at least one use-of-funds objective")
    body = {
        "schema": "dio.vamp_finance_objective_map.v1",
        "studio_id": manifest["studio_id"],
        "venture": venture["name"],
        "objectives": objectives,
        "objective_count": len(objectives),
        "boundary": "This map structures proposed objectives and evidence milestones. It is not a lending decision, business-performance rating, affordability conclusion, or guarantee of outcomes.",
        "authority_created": False,
        "source_engine": "vamp",
        "capabilities_executed": ["objective.milestone.map"],
    }
    body["map_fingerprint"] = _fingerprint(body)
    return body
