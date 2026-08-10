#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from commerce.mandos import MandosLedger, commercial_outcome, source_state  # noqa: E402
from commerce.mandos_reconcile import reconcile_all  # noqa: E402
from commerce.mandos_recovery import verify_complete_memory  # noqa: E402


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _lineage(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "transaction_id": args.transaction_id,
        "campaign_id": args.campaign_id,
        "lead_id": args.lead_id,
        "conversation_id": args.conversation_id,
        "job_id": args.job_id,
        "order_id": args.order_id,
        "mail_intent_id": args.mail_intent_id,
        "semantic_object_id": args.semantic_object_id,
        "semantic_judgement_id": args.semantic_judgement_id,
    }


def _strategy(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "product": args.product,
        "offer": args.offer,
        "communicative_act": args.communicative_act,
        "channel": args.channel,
        "audience": args.audience,
        "tactic_id": args.tactic_id,
        "proof_family": args.proof_family,
    }


def _source_states(root: Path, values: list[str]) -> list[dict[str, Any]]:
    return [source_state((root / value).resolve(), root) for value in values]


def _intent_strategy(root: Path, intent: dict[str, Any]) -> tuple[dict[str, Any], list[Path]]:
    binding = intent.get("semantic_binding") or {}
    product = None
    offer = None
    source_paths: list[Path] = []
    lead_id = str(intent.get("lead_id") or "").strip()
    if lead_id:
        lead_path = root / "state" / "leads" / f"{lead_id}.json"
        if lead_path.is_file():
            lead = _json(lead_path)
            product = lead.get("product")
            offer = lead.get("offer")
            source_paths.append(lead_path)
    return {
        "product": product,
        "offer": offer,
        "communicative_act": intent.get("communicative_act") or binding.get("communicative_act"),
        "channel": "email",
        "audience": None,
        "tactic_id": binding.get("tactic_id"),
        "proof_family": binding.get("proof_family"),
    }, source_paths


def _parse_required_time(value: str, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{label} must be an ISO-8601 timestamp") from exc
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def add_common_record_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("outcome_type")
    parser.add_argument("--occurred-at", default=datetime.now(timezone.utc).replace(microsecond=0).isoformat())
    parser.add_argument("--polarity", choices=["positive", "negative", "neutral", "mixed"])
    parser.add_argument("--evidence-state", choices=["observed", "verified", "operator_confirmed"], default="operator_confirmed")
    parser.add_argument("--source-ref", action="append", default=[])
    parser.add_argument("--source-class", action="append", default=[])
    parser.add_argument("--source-path", action="append", default=[])
    parser.add_argument("--transaction-id")
    parser.add_argument("--campaign-id")
    parser.add_argument("--lead-id")
    parser.add_argument("--conversation-id")
    parser.add_argument("--job-id")
    parser.add_argument("--order-id")
    parser.add_argument("--mail-intent-id")
    parser.add_argument("--semantic-object-id")
    parser.add_argument("--semantic-judgement-id")
    parser.add_argument("--product")
    parser.add_argument("--offer")
    parser.add_argument("--communicative-act")
    parser.add_argument("--channel")
    parser.add_argument("--audience")
    parser.add_argument("--tactic-id")
    parser.add_argument("--proof-family")
    parser.add_argument("--currency", default="ZAR")
    parser.add_argument("--revenue-minor", type=int, default=0)
    parser.add_argument("--cost-minor", type=int, default=0)
    parser.add_argument("--manual-minutes", type=float, default=0.0)
    parser.add_argument("--detail-json", type=Path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Operate the DIO Mandos commercial outcome memory.")
    parser.add_argument("--root", type=Path, default=ROOT)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("reconcile")
    sub.add_parser("verify")
    record = sub.add_parser("record")
    add_common_record_args(record)

    silence = sub.add_parser("close-silence")
    silence.add_argument("--mail-intent-id", required=True)
    silence.add_argument("--window-start", required=True)
    silence.add_argument("--window-end", required=True)
    silence.add_argument("--actor", required=True)
    silence.add_argument("--reason", required=True)

    nominate = sub.add_parser("nominate")
    nominate.add_argument("pattern_key")
    nominate.add_argument("--actor", required=True)
    nominate.add_argument("--rationale", required=True)

    validate = sub.add_parser("validate")
    validate.add_argument("pattern_key")
    validate.add_argument("--actor", required=True)
    validate.add_argument("--state", choices=["passed", "failed"], required=True)
    validate.add_argument("--receipt-ref", action="append", required=True)
    validate.add_argument("--contradiction-resolution")

    promote = sub.add_parser("promote")
    promote.add_argument("pattern_key")
    promote.add_argument("--actor", required=True)
    promote.add_argument("--rationale", required=True)
    promote.add_argument("--confirmed", action="store_true")

    revoke = sub.add_parser("revoke")
    revoke.add_argument("pattern_key")
    revoke.add_argument("--actor", required=True)
    revoke.add_argument("--reason", required=True)
    revoke.add_argument("--confirmed", action="store_true")

    args = parser.parse_args()
    root = args.root.resolve()
    ledger = MandosLedger(root)

    if args.command == "reconcile":
        result = {
            "reconciliation": reconcile_all(root),
            "memory_verification": verify_complete_memory(root),
        }
        if not result["memory_verification"]["valid"]:
            raise RuntimeError("Mandos reconciliation completed but memory verification failed")
    elif args.command == "verify":
        result = {
            "memory_verification": verify_complete_memory(root),
            "patterns": ledger.refresh_patterns(),
        }
    elif args.command == "record":
        if args.evidence_state in {"verified", "operator_confirmed"} and (not args.source_ref or not args.source_class):
            raise ValueError("Verified/operator-confirmed manual outcomes require --source-ref and --source-class")
        detail = _json(args.detail_json.resolve()) if args.detail_json else {}
        outcome = commercial_outcome(
            outcome_type=args.outcome_type,
            lineage=_lineage(args),
            source_refs=args.source_ref,
            source_classes=args.source_class,
            occurred_at=args.occurred_at,
            polarity=args.polarity,
            evidence_state=args.evidence_state,
            strategy=_strategy(args),
            economics={"currency": args.currency, "revenue_minor": args.revenue_minor, "cost_minor": args.cost_minor, "manual_minutes": args.manual_minutes},
            detail=detail,
            source_states=_source_states(root, args.source_path),
        )
        stored, created = ledger.record(outcome)
        result = {"created": created, "outcome": stored, "memory_verification": verify_complete_memory(root)}
    elif args.command == "close-silence":
        intent_path = root / "state" / "mail_intents" / f"{args.mail_intent_id}.json"
        if not intent_path.is_file():
            raise FileNotFoundError("Mandos silence window requires the exact governed mail intent")
        intent = _json(intent_path)
        if intent.get("send_state") != "sent":
            raise ValueError("Silence cannot be recorded before the governed mail was actually sent")
        start = _parse_required_time(args.window_start, "window-start")
        end = _parse_required_time(args.window_end, "window-end")
        if end > datetime.now(timezone.utc):
            raise ValueError("Silence observation window cannot end in the future")
        if end <= start:
            raise ValueError("Silence observation window end must be after its start")
        sent_at = _parse_required_time(str(intent.get("sent_at") or intent.get("updated_at") or ""), "mail sent_at")
        if start < sent_at:
            raise ValueError("Silence observation window cannot begin before the governed send")

        conversation_id = str(intent.get("conversation_id") or "")
        if conversation_id:
            for path in (root / "state" / "mail_ingress").glob("*.json"):
                ingress = _json(path)
                if str(ingress.get("conversation_id") or "") != conversation_id:
                    continue
                received_value = str(ingress.get("received_at") or ingress.get("captured_at") or "").strip()
                if not received_value:
                    continue
                received = _parse_required_time(received_value, f"mail ingress {path.name} timestamp")
                if start < received <= end:
                    raise ValueError("Silence window is false: an inbound message exists inside the observation window")

        binding = intent.get("semantic_binding") or {}
        judgement = intent.get("semantic_judgement") or {}
        strategy, strategy_sources = _intent_strategy(root, intent)
        outcome = commercial_outcome(
            outcome_type="no_reply_window_closed",
            lineage={
                "campaign_id": intent.get("campaign_id"),
                "lead_id": intent.get("lead_id"),
                "conversation_id": intent.get("conversation_id"),
                "job_id": intent.get("job_id"),
                "order_id": intent.get("order_id"),
                "mail_intent_id": intent.get("mail_intent_id"),
                "semantic_object_id": binding.get("semantic_object_id"),
                "semantic_judgement_id": judgement.get("judgement_id"),
            },
            source_refs=[f"mail_intent:{intent['mail_intent_id']}", f"operator:{args.actor}"],
            source_classes=["outbound_mail_receipt", "operator_observation_window"],
            occurred_at=end.replace(microsecond=0).isoformat(),
            polarity="negative",
            evidence_state="operator_confirmed",
            strategy=strategy,
            detail={
                "window_start": start.replace(microsecond=0).isoformat(),
                "window_end": end.replace(microsecond=0).isoformat(),
                "closed_by": args.actor,
                "reason": args.reason,
                "absence_is_operator_confirmed_not_provider_fact": True,
            },
            source_states=[source_state(intent_path, root), *[source_state(path, root) for path in strategy_sources]],
        )
        stored, created = ledger.record(outcome)
        result = {"created": created, "outcome": stored, "memory_verification": verify_complete_memory(root)}
    elif args.command == "nominate":
        result = ledger.nominate(args.pattern_key, actor=args.actor, rationale=args.rationale)
    elif args.command == "validate":
        result = ledger.validate_adversarially(args.pattern_key, actor=args.actor, state=args.state, receipt_refs=args.receipt_ref, contradiction_resolution=args.contradiction_resolution)
    elif args.command == "promote":
        result = ledger.promote(args.pattern_key, actor=args.actor, confirmed=args.confirmed, rationale=args.rationale)
    else:
        result = ledger.revoke(args.pattern_key, actor=args.actor, confirmed=args.confirmed, reason=args.reason)

    print(json.dumps(result, indent=2, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
