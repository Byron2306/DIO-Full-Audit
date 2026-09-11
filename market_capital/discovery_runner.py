from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .census import CapitalCensus
from .evidence import EvidenceLedger
from .source_health import SourceHealthLedger
from .sources import SourceCredentialsRequired, SourcePolicyBlocked, SourceUnavailable


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stable(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()[:20].upper()
    return f"{prefix}-{digest}"


def _persist_observation(census: CapitalCensus, ledger: EvidenceLedger, observation: Any) -> tuple[str | None, str]:
    payload = dict(observation.payload or {})
    entity_type = str(observation.entity_type)
    entity_id: str | None = None

    if entity_type == "OPPORTUNITY":
        entity_id = str(payload.get("opportunity_id") or observation.source_record_id or "").strip()
        if not entity_id:
            return None, "MISSING_ID"
        opportunity_type = str(payload.get("opportunity_type") or "").strip().upper()
        title = str(payload.get("title") or "").strip()
        if not opportunity_type or not title:
            return None, "INCOMPLETE_OPPORTUNITY"
        census.upsert_opportunity({
            **payload,
            "opportunity_id": entity_id,
            "opportunity_type": opportunity_type,
            "title": title,
            "observed_at": observation.observed_at,
        })
    elif entity_type == "ORGANISATION":
        entity_id = str(payload.get("organisation_id") or "").strip() or _stable(
            "ORG", observation.source_id, observation.source_record_id
        )
        name = str(payload.get("canonical_name") or payload.get("organisation_name") or "").strip()
        if not name:
            return None, "INCOMPLETE_ORGANISATION"
        census.upsert_organisation({
            **payload,
            "organisation_id": entity_id,
            "canonical_name": name,
            "observed_at": observation.observed_at,
        })
    elif entity_type == "PERSON":
        entity_id = str(payload.get("person_id") or "").strip() or _stable(
            "PER", observation.source_id, observation.source_record_id
        )
        name = str(payload.get("name") or payload.get("person_name") or "").strip()
        if not name:
            return None, "INCOMPLETE_PERSON"
        census.upsert_person({
            **payload,
            "person_id": entity_id,
            "name": name,
            "public_role": payload.get("public_role") or payload.get("role"),
            "observed_at": observation.observed_at,
        })
    elif entity_type == "RELATIONSHIP":
        left_id = str(payload.get("left_id") or payload.get("funder_id") or "").strip()
        right_id = str(payload.get("right_id") or payload.get("recipient_id") or "").strip()
        if not left_id or not right_id:
            return None, "UNRESOLVED_RELATIONSHIP_ENDPOINTS"
        entity_id = census.link_relationship(
            str(payload.get("relationship_type") or "HISTORICAL_AWARD"),
            left_id,
            right_id,
        )
    else:
        return None, "UNSUPPORTED_ENTITY_TYPE"

    ledger.observe(
        entity_id,
        "source_observation",
        payload,
        source_id=observation.source_id,
        source_reference=observation.source_reference,
        observed_at=observation.observed_at,
        assertion_class=str(observation.assertion_class or "OBSERVED"),
    )
    return entity_id, "PERSISTED"


def run_discovery_cycle(
    *,
    root: Path,
    census: CapitalCensus,
    plan: dict[str, Any],
    adapters: dict[str, Any],
) -> dict[str, Any]:
    root = Path(root)
    ledger = EvidenceLedger(census)
    health = SourceHealthLedger(root / "state" / "market_capital" / "census" / "source_health.json")
    source_results: dict[str, dict[str, Any]] = {}
    persisted = 0
    skipped = 0

    for allocation in list(plan.get("source_allocations") or []):
        source_id = str(allocation.get("source_id") or "").strip()
        budget = max(0, int(allocation.get("budget") or 0))
        adapter = adapters.get(source_id)
        if not source_id or budget <= 0:
            continue
        if adapter is None:
            state = "SOURCE_UNAVAILABLE"
            error = "NO_ADAPTER_REGISTERED"
            health.record(source_id, state, error=error)
            source_results[source_id] = {"state": state, "observations": 0, "persisted": 0, "skipped": 0, "error": error}
            continue
        try:
            batch = adapter.discover({**allocation, "limit": budget})
            batch_observations = list(batch.observations)[:budget]
            source_persisted = 0
            source_skipped = 0
            for observation in batch_observations:
                _entity_id, persistence_state = _persist_observation(census, ledger, observation)
                if persistence_state == "PERSISTED":
                    persisted += 1
                    source_persisted += 1
                else:
                    skipped += 1
                    source_skipped += 1
            state = str(batch.source_state or "READY")
            health.record(source_id, state, observations=len(batch_observations))
            source_results[source_id] = {
                "state": state,
                "observations": len(batch_observations),
                "persisted": source_persisted,
                "skipped": source_skipped,
                "error": None,
            }
        except SourcePolicyBlocked as exc:
            health.record(source_id, "POLICY_BLOCKED", error=str(exc))
            source_results[source_id] = {"state": "POLICY_BLOCKED", "observations": 0, "persisted": 0, "skipped": 0, "error": str(exc)}
        except SourceCredentialsRequired as exc:
            health.record(source_id, "NEEDS_CREDENTIALS", error=str(exc))
            source_results[source_id] = {"state": "NEEDS_CREDENTIALS", "observations": 0, "persisted": 0, "skipped": 0, "error": str(exc)}
        except SourceUnavailable as exc:
            health.record(source_id, "SOURCE_UNAVAILABLE", error=str(exc))
            source_results[source_id] = {"state": "SOURCE_UNAVAILABLE", "observations": 0, "persisted": 0, "skipped": 0, "error": str(exc)}
        except Exception as exc:
            health.record(source_id, "SOURCE_UNAVAILABLE", error=f"{type(exc).__name__}: {exc}")
            source_results[source_id] = {"state": "SOURCE_UNAVAILABLE", "observations": 0, "persisted": 0, "skipped": 0, "error": f"{type(exc).__name__}: {exc}"}

    health_payload = health.write()
    receipt = {
        "schema": "dio.market_capital.census_discovery_cycle_receipt.v1",
        "cycle_id": plan.get("cycle_id"),
        "generated_at": _now(),
        "cycle_budget": int(plan.get("cycle_budget") or 0),
        "source_results": source_results,
        "persisted_observations": persisted,
        "skipped_observations": skipped,
        "census_counts": census.snapshot_counts(),
        "source_health": health_payload,
        "synthetic_fallback_records": 0,
        "external_contacts_sent": 0,
        "submission_actions_executed": 0,
        "financial_actions_executed": 0,
        "authority_created": False,
        "external_effects": False,
    }
    receipt_path = root / "state" / "market_capital" / "census" / "LATEST_DISCOVERY_CYCLE.json"
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt
