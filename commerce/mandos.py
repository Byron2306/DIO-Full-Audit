from __future__ import annotations

import fcntl
import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


OUTCOME_SCHEMA = "dio.commercial_outcome.v1"
PATTERN_SCHEMA = "dio.mandos_pattern.v1"
DECISION_SCHEMA = "dio.mandos_pattern_decision.v1"
NEGATIVE_REGISTRY_SCHEMA = "dio.beast_negative_capability_registry.v1"

OUTCOME_TYPES = {
    "outbound_sent",
    "reply_received",
    "no_reply_window_closed",
    "objection_recorded",
    "qualification_changed",
    "revision_requested",
    "approval_recorded",
    "paid_order",
    "payment_failed",
    "delivery_sent",
    "delivery_acknowledged",
    "correction_received",
    "refund_or_cancellation",
    "manual_time_recorded",
    "cost_recorded",
    "revenue_recorded",
    "transaction_closed",
    "campaign_measurement",
}

POLARITIES = {"positive", "negative", "neutral", "mixed"}
EVIDENCE_STATES = {"observed", "verified", "operator_confirmed"}
PROMOTION_ORDER = (
    "observation",
    "repeated_observation",
    "corroborated_pattern",
    "candidate_strategy",
    "adversarial_validated",
    "reusable_crystal",
)

LEARNING_OUTCOMES = {
    "reply_received",
    "no_reply_window_closed",
    "objection_recorded",
    "qualification_changed",
    "revision_requested",
    "approval_recorded",
    "paid_order",
    "payment_failed",
    "delivery_acknowledged",
    "correction_received",
    "refund_or_cancellation",
    "transaction_closed",
    "campaign_measurement",
}

POSITIVE_TYPES = {
    "reply_received",
    "approval_recorded",
    "paid_order",
    "delivery_acknowledged",
}

NEGATIVE_TYPES = {
    "no_reply_window_closed",
    "objection_recorded",
    "payment_failed",
    "correction_received",
    "refund_or_cancellation",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def stable_id(prefix: str, value: Any, length: int = 20) -> str:
    return f"{prefix}-" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()[:length].upper()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        temporary = Path(handle.name)
        json.dump(payload, handle, indent=2, ensure_ascii=True, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _read_json(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _clean_refs(values: Iterable[Any]) -> list[str]:
    """Canonicalize provenance collections because set order is not semantic evidence."""
    return sorted({str(value).strip() for value in values if str(value or "").strip()})


def _normalize_source_states(values: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [
        {
            "path": str(row.get("path") or ""),
            "sha256": str(row.get("sha256") or ""),
            "size": int(row.get("size") or 0),
        }
        for row in values
    ]
    return sorted(rows, key=lambda row: (row["path"], row["sha256"], row["size"]))


def _semantic_value(cso: dict[str, Any], section: str, field: str) -> Any:
    item = (cso.get(section) or {}).get(field)
    return item.get("value") if isinstance(item, dict) else item


def strategy_signature(
    *,
    product: Any = None,
    offer: Any = None,
    communicative_act: Any = None,
    channel: Any = None,
    audience: Any = None,
    tactic_id: Any = None,
    proof_family: Any = None,
) -> dict[str, Any]:
    return {
        "product": str(product or "").strip() or None,
        "offer": str(offer or "").strip() or None,
        "communicative_act": str(communicative_act or "").strip() or None,
        "channel": str(channel or "").strip() or None,
        "audience": str(audience or "").strip() or None,
        "tactic_id": str(tactic_id or "").strip() or None,
        "proof_family": str(proof_family or "").strip() or None,
    }


def strategy_signature_from_cso(
    cso: dict[str, Any],
    *,
    communicative_act: str | None = None,
    channel: str | None = None,
    tactic_id: str | None = None,
    proof_family: str | None = None,
) -> dict[str, Any]:
    audience = None
    market = cso.get("market_context") or {}
    audience_fit = market.get("audience_fit") or {}
    if isinstance(audience_fit, dict):
        persona = audience_fit.get("persona")
        if isinstance(persona, dict):
            audience = persona.get("value") or persona.get("name")
        elif persona:
            audience = persona
    if not audience:
        audience = (cso.get("lineage") or {}).get("campaign_id")
    return strategy_signature(
        product=_semantic_value(cso, "commercial", "product"),
        offer=_semantic_value(cso, "commercial", "offer"),
        communicative_act=communicative_act or _semantic_value(cso, "strategy", "communicative_act"),
        channel=channel or _semantic_value(cso, "strategy", "channel"),
        audience=audience,
        tactic_id=tactic_id,
        proof_family=proof_family,
    )


def pattern_key(signature: dict[str, Any]) -> str | None:
    material = {key: value for key, value in signature.items() if value not in {None, ""}}
    if not material:
        return None
    return stable_id("MANDOS-PAT", material, 20)


def case_id(lineage: dict[str, Any], outcome_id: str | None = None) -> str:
    for field in ("transaction_id", "lead_id", "campaign_id", "order_id", "conversation_id", "job_id"):
        value = str(lineage.get(field) or "").strip()
        if value:
            return f"{field}:{value}"
    return f"outcome:{outcome_id or 'unidentified'}"


def source_state(path: Path, root: Path) -> dict[str, Any]:
    resolved = path.expanduser().resolve()
    root = root.resolve()
    if not resolved.is_relative_to(root):
        raise ValueError(f"Mandos source must remain under DIO root: {resolved}")
    if not resolved.is_file():
        raise FileNotFoundError(f"Mandos source is missing: {resolved}")
    return {
        "path": str(resolved.relative_to(root)),
        "sha256": file_digest(resolved),
        "size": resolved.stat().st_size,
    }


def _economic_event_key(outcome: dict[str, Any]) -> str | None:
    """Identify one worldly economic event independently of how many attestations describe it."""
    economics = outcome.get("economics") or {}
    revenue = int(economics.get("revenue_minor") or 0)
    cost = int(economics.get("cost_minor") or 0)
    minutes = float(economics.get("manual_minutes") or 0.0)
    if revenue == 0 and cost == 0 and minutes == 0.0:
        return None
    lineage = outcome.get("lineage") or {}
    world_lineage = {
        key: lineage.get(key)
        for key in (
            "transaction_id",
            "campaign_id",
            "lead_id",
            "conversation_id",
            "job_id",
            "order_id",
            "mail_intent_id",
        )
    }
    return digest(
        {
            "outcome_type": outcome.get("outcome_type"),
            "occurred_at": outcome.get("occurred_at"),
            "lineage": world_lineage,
            "strategy": {
                key: value
                for key, value in (outcome.get("strategy") or {}).items()
                if key != "pattern_key"
            },
            "economics": economics,
            "detail": outcome.get("detail") or {},
        }
    )


def summarize_economics(outcomes: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Deduplicate attestations and keep unlike currencies partitioned.

    This is a reporting/learning summary only. It never creates accounting authority.
    If multiple currencies are present, top-level monetary totals are deliberately zero
    rather than pretending that minor units can be added across currencies.
    """
    unique_events: dict[str, dict[str, Any]] = {}
    for row in outcomes:
        key = _economic_event_key(row)
        if key and key not in unique_events:
            unique_events[key] = row

    by_currency: dict[str, dict[str, Any]] = {}
    total_minutes = 0.0
    for row in unique_events.values():
        economics = row.get("economics") or {}
        currency = str(economics.get("currency") or "UNKNOWN").strip().upper() or "UNKNOWN"
        bucket = by_currency.setdefault(
            currency,
            {
                "revenue_minor": 0,
                "cost_minor": 0,
                "manual_minutes": 0.0,
                "gross_margin_minor": 0,
                "economic_event_count": 0,
            },
        )
        revenue = int(economics.get("revenue_minor") or 0)
        cost = int(economics.get("cost_minor") or 0)
        minutes = float(economics.get("manual_minutes") or 0.0)
        bucket["revenue_minor"] += revenue
        bucket["cost_minor"] += cost
        bucket["manual_minutes"] = round(bucket["manual_minutes"] + minutes, 3)
        bucket["gross_margin_minor"] = bucket["revenue_minor"] - bucket["cost_minor"]
        bucket["economic_event_count"] += 1
        total_minutes += minutes

    if not by_currency:
        return {
            "currency": None,
            "aggregation_state": "no_economic_events",
            "revenue_minor": 0,
            "cost_minor": 0,
            "manual_minutes": 0.0,
            "gross_margin_minor": 0,
            "economic_event_count": 0,
            "by_currency": {},
            "attestation_deduplication": True,
        }

    if len(by_currency) == 1:
        currency = next(iter(by_currency))
        bucket = by_currency[currency]
        return {
            "currency": currency,
            "aggregation_state": "single_currency",
            "revenue_minor": bucket["revenue_minor"],
            "cost_minor": bucket["cost_minor"],
            "manual_minutes": bucket["manual_minutes"],
            "gross_margin_minor": bucket["gross_margin_minor"],
            "economic_event_count": bucket["economic_event_count"],
            "by_currency": by_currency,
            "attestation_deduplication": True,
        }

    return {
        "currency": None,
        "aggregation_state": "mixed_currency_not_aggregated",
        "revenue_minor": 0,
        "cost_minor": 0,
        "manual_minutes": round(total_minutes, 3),
        "gross_margin_minor": 0,
        "economic_event_count": len(unique_events),
        "by_currency": by_currency,
        "attestation_deduplication": True,
    }


def validate_outcome(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema") != OUTCOME_SCHEMA:
        errors.append(f"schema must equal {OUTCOME_SCHEMA}")
    if payload.get("outcome_type") not in OUTCOME_TYPES:
        errors.append("unsupported outcome_type")
    if payload.get("polarity") not in POLARITIES:
        errors.append("unsupported polarity")
    evidence = payload.get("evidence") or {}
    if evidence.get("state") not in EVIDENCE_STATES:
        errors.append("evidence.state must be observed, verified, or operator_confirmed")
    refs = evidence.get("source_refs") or []
    classes = evidence.get("source_classes") or []
    if evidence.get("state") in {"verified", "operator_confirmed"} and not refs:
        errors.append("verified/operator_confirmed outcome requires source_refs")
    if evidence.get("state") in {"verified", "operator_confirmed"} and not classes:
        errors.append("verified/operator_confirmed outcome requires source_classes")
    lineage = payload.get("lineage") or {}
    if not any(
        str(lineage.get(field) or "").strip()
        for field in ("transaction_id", "lead_id", "campaign_id", "conversation_id", "order_id", "job_id")
    ):
        errors.append("outcome requires commercial lineage")
    economics = payload.get("economics") or {}
    for field in ("revenue_minor", "cost_minor"):
        value = economics.get(field)
        if value is not None and int(value) < 0:
            errors.append(f"economics.{field} cannot be negative")
    if economics.get("manual_minutes") is not None and float(economics["manual_minutes"]) < 0:
        errors.append("economics.manual_minutes cannot be negative")
    authority = payload.get("authority") or {}
    if authority.get("may_expand_execution_authority") is not False:
        errors.append("outcome may not expand execution authority")
    return errors


def assert_valid_outcome(payload: dict[str, Any]) -> None:
    errors = validate_outcome(payload)
    if errors:
        raise ValueError("Invalid commercial outcome: " + "; ".join(errors))


def commercial_outcome(
    *,
    outcome_type: str,
    lineage: dict[str, Any],
    source_refs: Iterable[Any],
    source_classes: Iterable[Any],
    occurred_at: str,
    polarity: str | None = None,
    evidence_state: str = "verified",
    strategy: dict[str, Any] | None = None,
    economics: dict[str, Any] | None = None,
    detail: dict[str, Any] | None = None,
    source_states: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if outcome_type not in OUTCOME_TYPES:
        raise ValueError(f"Unsupported Mandos outcome type: {outcome_type}")
    if polarity is None:
        polarity = "positive" if outcome_type in POSITIVE_TYPES else "negative" if outcome_type in NEGATIVE_TYPES else "neutral"
    signature = strategy_signature(**(strategy or {}))
    pkey = pattern_key(signature) if outcome_type in LEARNING_OUTCOMES else None
    clean_economics = {
        "currency": str((economics or {}).get("currency") or "ZAR").strip().upper() or "ZAR",
        "revenue_minor": int((economics or {}).get("revenue_minor") or 0),
        "cost_minor": int((economics or {}).get("cost_minor") or 0),
        "manual_minutes": float((economics or {}).get("manual_minutes") or 0.0),
    }
    clean_economics["gross_margin_minor"] = clean_economics["revenue_minor"] - clean_economics["cost_minor"]
    source_refs = _clean_refs(source_refs)
    source_classes = _clean_refs(source_classes)
    clean_source_states = _normalize_source_states(source_states or [])
    attestation = {
        "state": evidence_state,
        "source_refs": source_refs,
        "source_classes": source_classes,
        "source_states": clean_source_states,
    }
    identity = {
        "outcome_type": outcome_type,
        "occurred_at": occurred_at,
        "polarity": polarity,
        "lineage": lineage,
        "strategy": signature,
        "evidence": attestation,
        "detail": detail or {},
        "economics": clean_economics,
    }
    outcome_id = stable_id("OUT", identity, 24)
    payload = {
        "schema": OUTCOME_SCHEMA,
        "outcome_id": outcome_id,
        "occurred_at": occurred_at,
        "recorded_at": utc_now(),
        "outcome_type": outcome_type,
        "polarity": polarity,
        "lineage": {
            "transaction_id": lineage.get("transaction_id"),
            "campaign_id": lineage.get("campaign_id"),
            "lead_id": lineage.get("lead_id"),
            "conversation_id": lineage.get("conversation_id"),
            "job_id": lineage.get("job_id"),
            "order_id": lineage.get("order_id"),
            "mail_intent_id": lineage.get("mail_intent_id"),
            "semantic_object_id": lineage.get("semantic_object_id"),
            "semantic_judgement_id": lineage.get("semantic_judgement_id"),
        },
        "strategy": {**signature, "pattern_key": pkey},
        "evidence": attestation,
        "economics": clean_economics,
        "detail": detail or {},
        "authority": {
            "may_expand_execution_authority": False,
            "may_become_reusable_strategy": False,
            "promotion_requires_independent_cases": True,
            "promotion_requires_adversarial_validation": True,
            "promotion_requires_human_confirmation": True,
        },
    }
    payload["case_id"] = case_id(payload["lineage"], outcome_id)
    assert_valid_outcome(payload)
    return payload


@dataclass
class MandosLedger:
    root: Path

    @property
    def state_root(self) -> Path:
        return self.root.resolve() / "state" / "mandos"

    @property
    def outcomes_root(self) -> Path:
        return self.state_root / "outcomes"

    @property
    def patterns_root(self) -> Path:
        return self.state_root / "patterns"

    @property
    def decisions_root(self) -> Path:
        return self.state_root / "decisions"

    @property
    def journal_path(self) -> Path:
        return self.state_root / "JOURNAL.jsonl"

    def _append_journal(self, outcome: dict[str, Any]) -> dict[str, Any]:
        self.state_root.mkdir(parents=True, exist_ok=True)
        with self.journal_path.open("a+", encoding="utf-8") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            handle.seek(0)
            lines = [line for line in handle.read().splitlines() if line.strip()]
            previous = json.loads(lines[-1]) if lines else None
            entry = {
                "schema": "dio.mandos_journal_entry.v1",
                "sequence": len(lines) + 1,
                "outcome_id": outcome["outcome_id"],
                "outcome_sha256": digest(outcome),
                "previous_entry_sha256": (previous or {}).get("entry_sha256"),
            }
            entry["entry_sha256"] = digest(entry)
            handle.seek(0, 2)
            handle.write(canonical_json(entry) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
            fcntl.flock(handle, fcntl.LOCK_UN)
        return entry

    def record(self, outcome: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        assert_valid_outcome(outcome)
        path = self.outcomes_root / f"{outcome['outcome_id']}.json"
        if path.is_file():
            existing = _read_json(path)
            comparable_existing = dict(existing)
            comparable_new = dict(outcome)
            comparable_existing.pop("recorded_at", None)
            comparable_new.pop("recorded_at", None)
            if comparable_existing != comparable_new:
                raise ValueError("Mandos outcome ID collision with different immutable content")
            return existing, False
        _write_json(path, outcome)
        self._append_journal(outcome)
        self.refresh_patterns()
        return outcome, True

    def outcomes(self) -> list[dict[str, Any]]:
        if not self.outcomes_root.exists():
            return []
        return [_read_json(path) for path in sorted(self.outcomes_root.glob("OUT-*.json"))]

    def verify_journal(self) -> dict[str, Any]:
        if not self.journal_path.is_file():
            return {"valid": True, "entries": 0, "errors": []}
        errors: list[str] = []
        previous_hash = None
        lines = [line for line in self.journal_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        for index, line in enumerate(lines, 1):
            entry = json.loads(line)
            stored_hash = entry.get("entry_sha256")
            material = dict(entry)
            material.pop("entry_sha256", None)
            expected_hash = digest(material)
            if entry.get("sequence") != index:
                errors.append(f"journal sequence mismatch at {index}")
            if entry.get("previous_entry_sha256") != previous_hash:
                errors.append(f"journal chain mismatch at {index}")
            if stored_hash != expected_hash:
                errors.append(f"journal entry hash mismatch at {index}")
            outcome_path = self.outcomes_root / f"{entry.get('outcome_id')}.json"
            if not outcome_path.is_file():
                errors.append(f"journal outcome missing at {index}")
            else:
                outcome = _read_json(outcome_path)
                if digest(outcome) != entry.get("outcome_sha256"):
                    errors.append(f"journal outcome hash mismatch at {index}")
            previous_hash = stored_hash
        return {"valid": not errors, "entries": len(lines), "errors": errors, "head": previous_hash}

    def decision(self, pkey: str) -> dict[str, Any]:
        return _read_json(
            self.decisions_root / f"{pkey}.json",
            {
                "schema": DECISION_SCHEMA,
                "pattern_key": pkey,
                "nomination": None,
                "adversarial_validation": None,
                "promotion": None,
                "revocation": None,
                "updated_at": None,
            },
        )

    def _save_decision(self, pkey: str, decision: dict[str, Any]) -> dict[str, Any]:
        decision["schema"] = DECISION_SCHEMA
        decision["pattern_key"] = pkey
        decision["updated_at"] = utc_now()
        _write_json(self.decisions_root / f"{pkey}.json", decision)
        self.refresh_patterns()
        return decision

    def nominate(self, pkey: str, *, actor: str, rationale: str) -> dict[str, Any]:
        pattern = self.pattern(pkey)
        if PROMOTION_ORDER.index(pattern["earned_stage"]) < PROMOTION_ORDER.index("corroborated_pattern"):
            raise ValueError("Mandos pattern must be corroborated before strategy nomination")
        decision = self.decision(pkey)
        decision["nomination"] = {
            "state": "nominated",
            "actor": actor,
            "rationale": rationale,
            "at": utc_now(),
        }
        return self._save_decision(pkey, decision)

    def validate_adversarially(
        self,
        pkey: str,
        *,
        actor: str,
        state: str,
        receipt_refs: Iterable[str],
        contradiction_resolution: str | None = None,
    ) -> dict[str, Any]:
        if state not in {"passed", "failed"}:
            raise ValueError("Adversarial validation state must be passed or failed")
        decision = self.decision(pkey)
        if not decision.get("nomination"):
            raise ValueError("Mandos pattern must be nominated before adversarial validation")
        refs = _clean_refs(receipt_refs)
        if not refs:
            raise ValueError("Adversarial validation requires evidence receipt references")
        decision["adversarial_validation"] = {
            "state": state,
            "actor": actor,
            "receipt_refs": refs,
            "contradiction_resolution": contradiction_resolution,
            "at": utc_now(),
        }
        if state == "failed":
            decision["promotion"] = None
        return self._save_decision(pkey, decision)

    def promote(self, pkey: str, *, actor: str, confirmed: bool, rationale: str) -> dict[str, Any]:
        if not confirmed:
            raise ValueError("Reusable-strategy promotion requires explicit human confirmation")
        decision = self.decision(pkey)
        validation = decision.get("adversarial_validation") or {}
        if validation.get("state") != "passed":
            raise ValueError("Mandos pattern requires passed adversarial validation before promotion")
        pattern = self.pattern(pkey)
        if pattern["evidence_summary"]["positive_cases"] and pattern["evidence_summary"]["negative_cases"]:
            if not str(validation.get("contradiction_resolution") or "").strip():
                raise ValueError("Contested Mandos pattern requires explicit contradiction resolution before promotion")
        decision["promotion"] = {
            "state": "promoted",
            "actor": actor,
            "rationale": rationale,
            "at": utc_now(),
        }
        decision["revocation"] = None
        return self._save_decision(pkey, decision)

    def revoke(self, pkey: str, *, actor: str, confirmed: bool, reason: str) -> dict[str, Any]:
        if not confirmed:
            raise ValueError("Mandos revocation requires explicit human confirmation")
        decision = self.decision(pkey)
        if not (decision.get("promotion") or {}).get("state") == "promoted":
            raise ValueError("Mandos pattern is not currently promoted")
        decision["revocation"] = {
            "state": "revoked",
            "actor": actor,
            "reason": reason,
            "at": utc_now(),
        }
        return self._save_decision(pkey, decision)

    def pattern(self, pkey: str) -> dict[str, Any]:
        path = self.patterns_root / f"{pkey}.json"
        if not path.is_file():
            self.refresh_patterns()
        if not path.is_file():
            raise ValueError("Mandos pattern not found")
        return _read_json(path)

    def _build_pattern(self, pkey: str, outcomes: list[dict[str, Any]]) -> dict[str, Any]:
        verified = [
            row
            for row in outcomes
            if (row.get("evidence") or {}).get("state") in {"verified", "operator_confirmed"}
        ]
        independent: dict[str, list[dict[str, Any]]] = {}
        for row in verified:
            independent.setdefault(str(row.get("case_id") or row["outcome_id"]), []).append(row)
        positive_cases = {
            key
            for key, rows in independent.items()
            if any(row.get("polarity") == "positive" for row in rows)
        }
        negative_cases = {
            key
            for key, rows in independent.items()
            if any(row.get("polarity") == "negative" for row in rows)
        }
        source_classes = sorted(
            {
                source_class
                for row in verified
                for source_class in (row.get("evidence") or {}).get("source_classes") or []
            }
        )
        verified_cases = len(independent)
        earned_stage = "observation"
        if verified_cases >= 2:
            earned_stage = "repeated_observation"
        if verified_cases >= 3 and len(source_classes) >= 2:
            earned_stage = "corroborated_pattern"

        decision = self.decision(pkey)
        current_stage = earned_stage
        historical_max = earned_stage
        if earned_stage == "corroborated_pattern" and decision.get("nomination"):
            current_stage = historical_max = "candidate_strategy"
        validation = decision.get("adversarial_validation") or {}
        if current_stage == "candidate_strategy" and validation.get("state") == "passed":
            current_stage = historical_max = "adversarial_validated"
        promotion = decision.get("promotion") or {}
        revocation = decision.get("revocation") or {}
        if current_stage == "adversarial_validated" and promotion.get("state") == "promoted":
            historical_max = "reusable_crystal"
            current_stage = "adversarial_validated" if revocation.get("state") == "revoked" else "reusable_crystal"

        strategy = dict(outcomes[0].get("strategy") or {})
        direction = "contested"
        if positive_cases and not negative_cases:
            direction = "positive"
        elif negative_cases and not positive_cases:
            direction = "negative"
        elif not positive_cases and not negative_cases:
            direction = "neutral"

        negative_capability_state = "inactive"
        if len(negative_cases) >= 2 and not positive_cases:
            negative_capability_state = "active"
        elif len(negative_cases) >= 2 and positive_cases:
            negative_capability_state = "contested"

        economics = summarize_economics(verified)

        return {
            "schema": PATTERN_SCHEMA,
            "pattern_key": pkey,
            "updated_at": utc_now(),
            "strategy": strategy,
            "direction": direction,
            "earned_stage": earned_stage,
            "current_stage": current_stage,
            "historical_max_stage": historical_max,
            "outcome_ids": [row["outcome_id"] for row in outcomes],
            "case_ids": sorted(independent),
            "evidence_summary": {
                "verified_outcomes": len(verified),
                "verified_cases": verified_cases,
                "positive_cases": len(positive_cases),
                "negative_cases": len(negative_cases),
                "source_classes": source_classes,
                "source_class_count": len(source_classes),
            },
            "economics": economics,
            "decision": decision,
            "negative_capability": {
                "state": negative_capability_state,
                "reason": (
                    "Repeated independent verified negative cases with no verified positive contradiction."
                    if negative_capability_state == "active"
                    else None
                ),
            },
            "reuse_authority": {
                "state": (
                    "revoked"
                    if revocation.get("state") == "revoked"
                    else "active"
                    if current_stage == "reusable_crystal"
                    else "not_earned"
                ),
                "may_expand_execution_authority": False,
                "scope": "strategy_hypothesis_only",
                "exact_outcome_evidence_retained": True,
            },
            "promotion_law": {
                "automatic_crystallization": False,
                "candidate_requires_corroboration": True,
                "adversarial_validation_required": True,
                "human_promotion_required": True,
                "failure_may_narrow_authority_earlier_than_success_expands_reuse": True,
            },
        }

    def refresh_patterns(self) -> list[dict[str, Any]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for outcome in self.outcomes():
            pkey = str((outcome.get("strategy") or {}).get("pattern_key") or "")
            if pkey:
                grouped.setdefault(pkey, []).append(outcome)
        self.patterns_root.mkdir(parents=True, exist_ok=True)
        patterns = []
        for pkey, rows in sorted(grouped.items()):
            pattern = self._build_pattern(pkey, rows)
            _write_json(self.patterns_root / f"{pkey}.json", pattern)
            patterns.append(pattern)
        self._write_feedback(patterns)
        return patterns

    def _write_feedback(self, patterns: list[dict[str, Any]]) -> None:
        hivenance_root = self.state_root / "feedback" / "hivenance"
        niche_root = self.state_root / "feedback" / "nichefoundry"
        hivenance_root.mkdir(parents=True, exist_ok=True)
        niche_root.mkdir(parents=True, exist_ok=True)
        for pattern in patterns:
            common = {
                "pattern_key": pattern["pattern_key"],
                "strategy": pattern["strategy"],
                "direction": pattern["direction"],
                "stage": pattern["current_stage"],
                "evidence_summary": pattern["evidence_summary"],
                "economics": pattern["economics"],
                "outcome_ids": pattern["outcome_ids"],
                "authority": {
                    "execution_authority": False,
                    "reusable_strategy": pattern["reuse_authority"]["state"] == "active",
                },
            }
            _write_json(
                hivenance_root / f"{pattern['pattern_key']}.json",
                {
                    "schema": "dio.mandos_hivenance_feedback.v1",
                    **common,
                    "interpretation": (
                        "Observed commercial outcome evidence for hypothesis testing. "
                        "It is not live-execution authority."
                    ),
                },
            )
            _write_json(
                niche_root / f"{pattern['pattern_key']}.json",
                {
                    "schema": "dio.mandos_nichefoundry_feedback.v1",
                    **common,
                    "signal_state": "observed",
                    "interpretation": (
                        "Verified outcome evidence that may update audience/opportunity hypotheses "
                        "without manufacturing a score."
                    ),
                },
            )
        self._write_negative_capability_registry(patterns)

    def _write_negative_capability_registry(self, patterns: list[dict[str, Any]]) -> None:
        rows = []
        for pattern in patterns:
            negative = pattern.get("negative_capability") or {}
            if negative.get("state") not in {"active", "contested"}:
                continue
            strategy = pattern.get("strategy") or {}
            rows.append(
                {
                    "capability_id": f"mandos:{pattern['pattern_key']}",
                    "pattern_key": pattern["pattern_key"],
                    "state": negative["state"],
                    "selectors": {
                        "product": strategy.get("product"),
                        "offer": strategy.get("offer"),
                        "communicative_act": strategy.get("communicative_act"),
                        "channel": strategy.get("channel"),
                        "tactic_id": strategy.get("tactic_id"),
                    },
                    "negative_cases": pattern["evidence_summary"]["negative_cases"],
                    "positive_cases": pattern["evidence_summary"]["positive_cases"],
                    "evidence_count": pattern["evidence_summary"]["verified_outcomes"],
                    "outcome_ids": pattern["outcome_ids"],
                    "may_veto_semantic_execution": negative["state"] == "active",
                    "may_expand_execution_authority": False,
                }
            )
        path = self.state_root / "beast" / "NEGATIVE_CAPABILITIES.json"
        _write_json(
            path,
            {
                "schema": NEGATIVE_REGISTRY_SCHEMA,
                "updated_at": utc_now(),
                "capabilities": rows,
            },
        )


def active_negative_capabilities_for(
    root: Path,
    cso: dict[str, Any],
    expression: dict[str, Any],
    *,
    execution_kind: str | None = None,
) -> list[dict[str, Any]]:
    registry = _read_json(
        root.resolve() / "state" / "mandos" / "beast" / "NEGATIVE_CAPABILITIES.json",
        {},
    ) or {}
    product = _semantic_value(cso, "commercial", "product")
    offer = _semantic_value(cso, "commercial", "offer")
    plan = expression.get("plan") or {}
    act = expression.get("communicative_act")
    channel = (plan.get("contract") or {}).get("channel") or _semantic_value(cso, "strategy", "channel")
    verified_context = plan.get("verified_context") or {}
    tactic_context = verified_context.get("tactic_id")
    tactic_id = expression.get("tactic_id") or plan.get("tactic_id")
    if not tactic_id and isinstance(tactic_context, dict):
        tactic_id = tactic_context.get("value")
    current = {
        "product": str(product or "").strip() or None,
        "offer": str(offer or "").strip() or None,
        "communicative_act": str(act or "").strip() or None,
        "channel": str(channel or "").strip() or None,
        "tactic_id": str(tactic_id or "").strip() or None,
    }
    matches: list[dict[str, Any]] = []
    for row in registry.get("capabilities") or []:
        if row.get("state") != "active" or row.get("may_veto_semantic_execution") is not True:
            continue
        selectors = row.get("selectors") or {}
        required = {key: value for key, value in selectors.items() if value not in {None, ""}}
        if not required:
            continue
        if all(
            current.get(key) not in {None, ""} and str(current[key]) == str(value)
            for key, value in required.items()
        ):
            matches.append({**row, "execution_kind": execution_kind})
    return matches
