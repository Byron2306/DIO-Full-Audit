#!/usr/bin/env python3
"""
run_aws_cloudtrail_capture.py
=============================
Phase 3: Real AWS CloudTrail execution evidence (L1).

This script uses the configured AWS CLI profile to:
1. Execute a small set of harmless, read-only AWS API calls.
2. Pull the corresponding CloudTrail management events.
3. Write per-technique L1 evidence files as cloud_audit_events.json.

Current safe technique coverage:
  T1526      Cloud Service Discovery
  T1087.004  Account Discovery: Cloud Account
  T1538      Cloud Service Dashboard

These techniques are intentionally limited to read-only API actions under the
current Seraph-Metatron IAM user. Higher-risk cloud mutation techniques can be
added later once the account has the necessary lab-only permissions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


REPO = Path(__file__).resolve().parent.parent
OUT_BASE = REPO / "evidence-bundle" / "integration_evidence"


TECHNIQUES: dict[str, dict[str, Any]] = {
    "T1526": {
        "tactic": "TA0007",
        "tactic_name": "Discovery",
        "description": "Cloud Service Discovery via real AWS control-plane discovery APIs",
        "event_sources": {"sts.amazonaws.com", "cloudtrail.amazonaws.com"},
        "event_names": {"GetCallerIdentity", "DescribeTrails"},
        "actions": [
            ["sts", "get-caller-identity"],
            ["cloudtrail", "describe-trails", "--region", "{region}"],
        ],
        "category": "cloud_discovery",
        "sigma_rule_id": "aws-cloud-discovery-real-001",
    },
    "T1087.004": {
        "tactic": "TA0007",
        "tactic_name": "Discovery",
        "description": "Account Discovery: Cloud Account via real IAM enumeration APIs",
        "event_sources": {"iam.amazonaws.com", "sts.amazonaws.com"},
        "event_names": {
            "GetUser",
            "ListAttachedUserPolicies",
            "ListUserPolicies",
            "ListMFADevices",
            "ListUserTags",
            "GetCallerIdentity",
        },
        "actions": [
            ["iam", "get-user"],
            ["iam", "list-attached-user-policies", "--user-name", "{username}"],
            ["iam", "list-user-policies", "--user-name", "{username}"],
            ["iam", "list-mfa-devices", "--user-name", "{username}"],
            ["iam", "list-user-tags", "--user-name", "{username}"],
        ],
        "category": "cloud_account_discovery",
        "sigma_rule_id": "aws-cloud-account-discovery-real-001",
    },
    "T1538": {
        "tactic": "TA0007",
        "tactic_name": "Discovery",
        "description": "Cloud Service Dashboard via real CloudTrail status and audit queries",
        "event_sources": {"cloudtrail.amazonaws.com"},
        "event_names": {"DescribeTrails", "GetTrailStatus", "LookupEvents"},
        "actions": [
            ["cloudtrail", "describe-trails", "--region", "{region}"],
            ["cloudtrail", "get-trail-status", "--region", "{region}", "--name", "{trail_name}"],
            ["cloudtrail", "lookup-events", "--region", "{region}", "--max-results", "10"],
        ],
        "category": "cloud_dashboard_discovery",
        "sigma_rule_id": "aws-cloud-dashboard-real-001",
    },
}


def run_aws_json(args: list[str]) -> Any:
    result = subprocess.run(
        ["aws"] + args + ["--output", "json"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or f"aws {' '.join(args)} failed")
    return json.loads(result.stdout or "{}")


def run_safe_actions(region: str, trail_name: str, username: str) -> list[dict[str, Any]]:
    executed: list[dict[str, Any]] = []
    for technique_id, config in TECHNIQUES.items():
        for action in config["actions"]:
            rendered = [part.format(region=region, trail_name=trail_name, username=username) for part in action]
            try:
                response = run_aws_json(rendered)
                executed.append(
                    {
                        "technique_id": technique_id,
                        "command": ["aws"] + rendered + ["--output", "json"],
                        "status": "ok",
                        "executed_at": now_iso(),
                        "response_excerpt": json.dumps(response, default=str)[:500],
                    }
                )
            except Exception as exc:
                executed.append(
                    {
                        "technique_id": technique_id,
                        "command": ["aws"] + rendered + ["--output", "json"],
                        "status": "error",
                        "executed_at": now_iso(),
                        "error": str(exc),
                    }
                )
    return executed


def lookup_events(region: str, max_results: int) -> list[dict[str, Any]]:
    payload = run_aws_json(["cloudtrail", "lookup-events", "--region", region, "--max-results", str(max_results)])
    events = payload.get("Events", [])
    parsed: list[dict[str, Any]] = []
    for event in events:
        raw = event.get("CloudTrailEvent")
        raw_json: dict[str, Any] = {}
        if isinstance(raw, str):
            try:
                raw_json = json.loads(raw)
            except json.JSONDecodeError:
                raw_json = {"raw": raw}
        parsed.append({**event, "CloudTrailEventParsed": raw_json})
    return parsed


def match_event(event: dict[str, Any], config: dict[str, Any]) -> bool:
    source = event.get("EventSource") or event.get("CloudTrailEventParsed", {}).get("eventSource")
    name = event.get("EventName") or event.get("CloudTrailEventParsed", {}).get("eventName")
    return source in config["event_sources"] and name in config["event_names"]


def event_to_evidence_item(
    technique_id: str,
    event: dict[str, Any],
    config: dict[str, Any],
    account_id: str,
) -> dict[str, Any]:
    raw = event.get("CloudTrailEventParsed", {})
    actor = raw.get("userIdentity", {}).get("arn") or raw.get("userIdentity", {}).get("principalId") or event.get("Username")
    target_resource = None
    resources = event.get("Resources") or []
    if resources:
        target_resource = resources[0].get("ResourceName") or resources[0].get("ResourceType")
    if not target_resource:
        target_resource = raw.get("eventSource")
    request_id = raw.get("requestID") or raw.get("requestId") or event.get("EventId")
    evidence_hash = hashlib.sha256(json.dumps(raw, sort_keys=True, default=str).encode("utf-8")).hexdigest()
    return {
        "technique_id": technique_id,
        "source": "cloudtrail",
        "actor": actor,
        "target_resource": target_resource,
        "evidence_strength": "HARD_POSITIVE",
        "category": config["category"],
        "sigma_rule_id": config["sigma_rule_id"],
        "captured_at": now_iso(),
        "evidence_hash": evidence_hash,
        "audit_event": {
            "event_id": event.get("EventId"),
            "event_type": event.get("EventName"),
            "source": event.get("EventSource"),
            "timestamp": raw.get("eventTime") or event.get("EventTime"),
            "request_id": request_id,
            "aws_region": raw.get("awsRegion"),
            "source_ip": raw.get("sourceIPAddress"),
            "user_agent": raw.get("userAgent"),
            "recipient_account_id": raw.get("recipientAccountId", account_id),
            "read_only": raw.get("readOnly"),
            "raw_event": raw,
        },
    }


def write_evidence(
    technique_id: str,
    config: dict[str, Any],
    matched_events: list[dict[str, Any]],
    trail_meta: dict[str, Any],
    caller: dict[str, Any],
    executed_actions: list[dict[str, Any]],
) -> Path:
    tech_dir = OUT_BASE / technique_id
    tech_dir.mkdir(parents=True, exist_ok=True)
    data = [event_to_evidence_item(technique_id, event, config, caller.get("Account", "")) for event in matched_events]
    evidence = {
        "schema": "cloud_audit_events.v2",
        "evidence_mode": "L1",
        "evidence_strength": "HARD_POSITIVE",
        "technique": technique_id,
        "source": "cloudtrail",
        "provider": "AWS CloudTrail",
        "collected_at": now_iso(),
        "actor": caller.get("Arn", ""),
        "account_id": caller.get("Account", ""),
        "trail": trail_meta,
        "summary": {
            "matched_events": len(data),
            "event_names": sorted({item["audit_event"]["event_type"] for item in data}),
            "successful_calls": len(data),
            "evidence_items": len(data),
        },
        "executed_actions": [a for a in executed_actions if a["technique_id"] == technique_id],
        "data": data,
        "verdict": "real_cloudtrail_events_recorded",
    }
    out_path = tech_dir / "cloud_audit_events.json"
    out_path.write_text(json.dumps(evidence, indent=2, default=str), encoding="utf-8")
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture real AWS CloudTrail L1 evidence")
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--trail-name", default="metatron-lab-trail")
    parser.add_argument("--max-results", type=int, default=100)
    parser.add_argument("--technique", action="append", choices=sorted(TECHNIQUES))
    parser.add_argument("--no-generate", action="store_true", help="Skip the harmless AWS API calls and only export existing events")
    args = parser.parse_args()

    caller = run_aws_json(["sts", "get-caller-identity"])
    trail_list = run_aws_json(["cloudtrail", "describe-trails", "--region", args.region])
    trail_status = run_aws_json(["cloudtrail", "get-trail-status", "--region", args.region, "--name", args.trail_name])
    trail_meta = {
        "name": args.trail_name,
        "region": args.region,
        "describe": trail_list,
        "status": trail_status,
    }

    username = caller.get("Arn", "").split("/")[-1] if "/" in caller.get("Arn", "") else "Seraph-Metatron"
    executed_actions: list[dict[str, Any]] = []
    if not args.no_generate:
        executed_actions = run_safe_actions(args.region, args.trail_name, username)

    events = lookup_events(args.region, args.max_results)
    selected = args.technique or list(TECHNIQUES)
    written = 0
    for technique_id in selected:
        config = TECHNIQUES[technique_id]
        matched = [event for event in events if match_event(event, config)]
        if not matched:
            print(f"SKIP {technique_id}: no matching CloudTrail events found")
            continue
        out_path = write_evidence(technique_id, config, matched, trail_meta, caller, executed_actions)
        print(f"WROTE {technique_id}: {len(matched)} events -> {out_path}")
        written += 1

    print(f"\nL1 AWS CloudTrail evidence written for {written}/{len(selected)} techniques")
    return 0


if __name__ == "__main__":
    sys.exit(main())
