from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .core import MarketSensoriumStore, digest_payload, stable_id, utc_now

MS8_VERIFIED = "DIO_MARKET_SENSORIUM_COMMERCIAL_COCKPIT_VERIFIED"
MS9_VERIFIED = "DIO_MARKET_SENSORIUM_AUTONOMIC_MULTI_CYCLE_SOAK_VERIFIED"
MS2_ACTIVE = {
    "DIO_MARKET_SENSORIUM_COMMERCIAL_TIME_OBSERVATION_ACTIVE",
    "DIO_MARKET_SENSORIUM_COMMERCIAL_TIME_AND_REPLY_TRUTH_VERIFIED",
}
MIN_SOAK_CYCLES = 3

# Strict append-only ledgers. New rows may append during the soak, but the
# pre-soak rowid prefix must remain byte-semantically identical.
PREFIX_LEDGER_SPECS: dict[str, tuple[str, tuple[str, ...]]] = {
    "observations": ("observation_id", ("provenance_digest",)),
    "rank_transitions": (
        "transition_id",
        ("evidence_digest", "world_state_digest", "explanation_factors_json"),
    ),
    "competitive_offer_events": (
        "event_id",
        ("provenance_digest", "price_state", "price_basis"),
    ),
    "habitat_intelligence_events": (
        "event_id",
        ("provenance_digest", "permission_ladder_state", "read_authority"),
    ),
    "learned_query_events": (
        "query_id",
        ("evidence_digest", "query_text", "query_kind"),
    ),
}

# Hivenance intentionally permits deterministic replay of an already-known
# hypothesis/set via INSERT OR REPLACE. Physical rowid movement is therefore not
# itself a semantic rewrite. For these ledgers the guard requires every pre-soak
# semantic member fingerprint to remain present unchanged; additions are allowed.
REPLAY_LEDGER_SPECS: dict[str, tuple[str, tuple[str, ...]]] = {
    "commercial_hypotheses": (
        "hypothesis_id",
        (
            "lineage_key",
            "parent_hypothesis_id",
            "transition_id",
            "hypothesis_type",
            "evidence_digest",
            "world_state_digest",
            "truth_state",
        ),
    ),
    "commercial_hypothesis_sets": (
        "hypothesis_set_id",
        (
            "transition_id",
            "selected_hypothesis_id",
            "selected_hypothesis_type",
            "evidence_digest",
            "world_state_digest",
            "truth_state",
        ),
    ),
}

EVENT_COUNT_TABLES = tuple([*PREFIX_LEDGER_SPECS, *REPLAY_LEDGER_SPECS])


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _table_exists(store: MarketSensoriumStore, table: str) -> bool:
    row = store.connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _count(store: MarketSensoriumStore, table: str) -> int:
    if not _table_exists(store, table):
        return 0
    row = store.connection.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()
    return int(row["n"] or 0) if row else 0


def _prefix(
    store: MarketSensoriumStore,
    table: str,
    id_column: str,
    columns: tuple[str, ...],
    max_rowid: int,
) -> dict[str, Any]:
    if not _table_exists(store, table) or max_rowid <= 0:
        return {
            "guard_kind": "ROWID_PREFIX",
            "max_rowid": max(0, int(max_rowid)),
            "count": 0,
            "digest": digest_payload([]),
        }
    selected = ",".join(["rowid", id_column, *columns])
    rows = store.connection.execute(
        f"SELECT {selected} FROM {table} WHERE rowid<=? ORDER BY rowid",
        (int(max_rowid),),
    ).fetchall()
    payload = [
        {key: row[key] for key in ("rowid", id_column, *columns)}
        for row in rows
    ]
    return {
        "guard_kind": "ROWID_PREFIX",
        "max_rowid": int(max_rowid),
        "count": len(payload),
        "digest": digest_payload(payload),
    }


def _semantic_members(
    store: MarketSensoriumStore,
    table: str,
    id_column: str,
    columns: tuple[str, ...],
) -> dict[str, Any]:
    if not _table_exists(store, table):
        members: list[str] = []
    else:
        selected = ",".join([id_column, *columns])
        rows = store.connection.execute(
            f"SELECT {selected} FROM {table} ORDER BY {id_column}"
        ).fetchall()
        members = sorted(
            digest_payload({key: row[key] for key in (id_column, *columns)})
            for row in rows
        )
    return {
        "guard_kind": "SEMANTIC_MEMBER_SET",
        "count": len(members),
        "member_digests": members,
        "digest": digest_payload(members),
    }


def capture_immutable_baseline(store: MarketSensoriumStore) -> dict[str, Any]:
    ledgers: dict[str, Any] = {}
    for table, (id_column, columns) in PREFIX_LEDGER_SPECS.items():
        if not _table_exists(store, table):
            ledgers[table] = _prefix(store, table, id_column, columns, 0)
            continue
        row = store.connection.execute(f"SELECT MAX(rowid) AS max_rowid FROM {table}").fetchone()
        max_rowid = int((row["max_rowid"] if row else 0) or 0)
        ledgers[table] = _prefix(store, table, id_column, columns, max_rowid)
    for table, (id_column, columns) in REPLAY_LEDGER_SPECS.items():
        ledgers[table] = _semantic_members(store, table, id_column, columns)
    return {
        "schema": "dio.market_sensorium.ms9_immutable_baseline.v2",
        "captured_at": utc_now(),
        "ledgers": ledgers,
        "digest": digest_payload(ledgers),
        "authority_created": False,
    }


def verify_immutable_baseline(store: MarketSensoriumStore, baseline: dict[str, Any]) -> dict[str, Any]:
    results: dict[str, Any] = {}
    intact = True
    for table, expected in (baseline.get("ledgers") or {}).items():
        if table in PREFIX_LEDGER_SPECS:
            id_column, columns = PREFIX_LEDGER_SPECS[table]
            current = _prefix(
                store,
                table,
                id_column,
                columns,
                int(expected.get("max_rowid") or 0),
            )
            same = (
                int(current.get("count") or 0) == int(expected.get("count") or 0)
                and str(current.get("digest") or "") == str(expected.get("digest") or "")
            )
            results[table] = {
                "guard_kind": "ROWID_PREFIX",
                "baseline_count": int(expected.get("count") or 0),
                "current_guarded_count": int(current.get("count") or 0),
                "baseline_digest": expected.get("digest"),
                "current_digest": current.get("digest"),
                "intact": same,
            }
        elif table in REPLAY_LEDGER_SPECS:
            id_column, columns = REPLAY_LEDGER_SPECS[table]
            current = _semantic_members(store, table, id_column, columns)
            baseline_members = set(expected.get("member_digests") or [])
            current_members = set(current.get("member_digests") or [])
            missing = sorted(baseline_members - current_members)
            same = not missing
            results[table] = {
                "guard_kind": "SEMANTIC_MEMBER_SET",
                "baseline_count": len(baseline_members),
                "current_count": len(current_members),
                "missing_baseline_members": len(missing),
                "intact": same,
            }
        else:
            continue
        intact = intact and same
    return {
        "all_prefixes_intact": intact,
        "all_historical_semantics_intact": intact,
        "ledgers": results,
        "authority_created": False,
    }


def _semantic_violation_counts(store: MarketSensoriumStore) -> dict[str, int]:
    checks = {
        "observation_authority": "SELECT COUNT(*) AS n FROM observations WHERE authority_created<>0",
        "rank_history_not_preserved": "SELECT COUNT(*) AS n FROM rank_transitions WHERE history_preserved<>1",
        "rank_truth_or_authority": "SELECT COUNT(*) AS n FROM rank_transitions WHERE authority_created<>0 OR market_demand_claimed<>0",
        "hypothesis_truth_promoted": "SELECT COUNT(*) AS n FROM commercial_hypotheses WHERE truth_state<>'UNPROVED'",
        "hypothesis_authority_or_demand": "SELECT COUNT(*) AS n FROM commercial_hypotheses WHERE authority_created<>0 OR market_demand_claimed<>0 OR execution_performed<>0",
        "hypothesis_set_truth_promoted": "SELECT COUNT(*) AS n FROM commercial_hypothesis_sets WHERE truth_state<>'UNPROVED'",
        "hypothesis_set_authority_or_demand": "SELECT COUNT(*) AS n FROM commercial_hypothesis_sets WHERE authority_created<>0 OR market_demand_claimed<>0 OR external_effects<>0",
        "offer_truth_inflation": "SELECT COUNT(*) AS n FROM competitive_offer_events WHERE authority_created<>0 OR market_demand_claimed<>0 OR realised_price_claimed<>0 OR willingness_to_pay_claimed<>0",
        "habitat_permission_or_authority": "SELECT COUNT(*) AS n FROM habitat_intelligence_events WHERE authority_created<>0 OR external_effects<>0 OR participant_inference_allowed<>0 OR posting_authority<>'NONE' OR dm_authority<>'NONE'",
        "learned_query_truth_or_authority": "SELECT COUNT(*) AS n FROM learned_query_events WHERE authority_created<>0 OR market_demand_claimed<>0",
    }
    counts: dict[str, int] = {}
    for name, sql in checks.items():
        table = sql.split("FROM ", 1)[1].split(" ", 1)[0]
        if not _table_exists(store, table):
            counts[name] = 0
            continue
        row = store.connection.execute(sql).fetchone()
        counts[name] = int(row["n"] or 0) if row else 0
    return counts


def capture_soak_snapshot(
    root: Path,
    store: MarketSensoriumStore,
    *,
    session_id: str,
    iteration: int,
    baseline: dict[str, Any],
    cycle_receipt: dict[str, Any],
    ms7_receipt: dict[str, Any],
    ms8_receipt: dict[str, Any],
) -> dict[str, Any]:
    root = Path(root).resolve()
    batch = _read_json(root / "state" / "market_sensorium" / "DOMAIN_DISCOVERY_QUERY_BATCH.json")
    history = _read_json(root / "state" / "market_sensorium" / "domain_query_history.json")
    cycle_summary = cycle_receipt.get("summary") or {}
    domain_refresh = cycle_summary.get("domain_public_refresh") or {}
    public_refresh = cycle_summary.get("public_refresh") or {}
    mail_refresh = cycle_summary.get("mail_ingress_refresh") or {}
    ms2_truth = cycle_receipt.get("ms2_truth") or {}
    ms8_truth = ms8_receipt.get("ms8_truth") or {}

    batch_domains = [item for item in batch.get("domains") or [] if isinstance(item, dict)]
    learned_batch = [
        item for item in batch_domains
        if item.get("query_origin") == "MS7_LEARNED_DISCOVERY_QUERY"
    ]
    public_execution_succeeded = str(domain_refresh.get("state") or "") == "refreshed"
    learned_executed = len(learned_batch) if public_execution_succeeded else 0
    history_domains = history.get("domains") or {}
    learned_history_bound = sum(
        1
        for item in learned_batch
        if str((history_domains.get(str(item.get("domain_id") or "")) or {}).get("learned_query_id") or "")
        == str(item.get("learned_query_id") or "")
    )

    history_guard = verify_immutable_baseline(store, baseline)
    event_counts = {table: _count(store, table) for table in EVENT_COUNT_TABLES}
    semantic_violations = _semantic_violation_counts(store)
    acceptances = {f"MS-{n}": cycle_receipt.get(f"ms{n}_acceptance") for n in range(1, 7)}
    acceptances["MS-7"] = ms7_receipt.get("ms7_acceptance")
    acceptances["MS-8"] = ms8_receipt.get("ms8_acceptance")
    refused = [key for key, value in acceptances.items() if str(value or "").startswith("REFUSE")]

    mail_state = str(mail_refresh.get("state") or "")
    mail_refresh_ok = mail_state in {"refreshed", "refreshed_after_stale_delta_reset"}

    return {
        "schema": "dio.market_sensorium.ms9_soak_snapshot.v2",
        "session_id": session_id,
        "iteration": int(iteration),
        "captured_at": utc_now(),
        "acceptances": acceptances,
        "refresh": {
            "public_refresh_state": public_refresh.get("state"),
            "domain_public_refresh_state": domain_refresh.get("state"),
            "mail_refresh_state": mail_state,
            "public_read_cycle_complete": str(public_refresh.get("state") or "") == "refreshed" and public_execution_succeeded,
            "mail_read_cycle_complete": mail_refresh_ok,
        },
        "learned_query_execution": {
            "batch_size": len(batch_domains),
            "learned_query_count": len(learned_batch),
            "learned_queries_executed": learned_executed,
            "history_bound_after_execution": learned_history_bound,
            "batch_digest": digest_payload(batch),
            "execution_is_read_only": True,
            "query_execution_is_market_truth": False,
            "search_hit_is_lead": False,
            "authority_created": False,
        },
        "commercial_time": {
            "acceptance": cycle_receipt.get("ms2_acceptance"),
            "coverage_state": ms2_truth.get("coverage_state"),
            "coverage_kind": ms2_truth.get("coverage_kind"),
            "continuous_from": ms2_truth.get("continuous_from"),
            "last_successful_sync_at": ms2_truth.get("last_successful_sync_at"),
            "reply_observed": int(ms2_truth.get("reply_observed") or 0),
            "no_reply_observed": int(ms2_truth.get("no_reply_observed") or 0),
            "temporal_penalized_targets": int(ms2_truth.get("temporal_penalized_targets") or 0),
            "unsupported_no_reply_inferences": int(ms2_truth.get("unsupported_no_reply_inferences") or 0),
            "age_only_silence_inference_used": bool(ms2_truth.get("age_only_silence_inference_used", False)),
            "followup_authority_created": bool(ms2_truth.get("followup_authority_created", False)),
            "market_demand_claimed": bool(ms2_truth.get("market_demand_claimed", False)),
            "authority_created": bool(ms2_truth.get("authority_created", False)),
        },
        "event_counts": event_counts,
        "immutable_prefix": history_guard,
        "semantic_violation_counts": semantic_violations,
        "semantic_violation_total": sum(semantic_violations.values()),
        "cockpit_truth_class_violations": int(ms8_truth.get("truth_class_violations") or 0),
        "cockpit_truth_separation_valid": bool(ms8_truth.get("truth_separation_valid", False)),
        "ms8_verified": ms8_receipt.get("ms8_acceptance") == MS8_VERIFIED,
        "ms2_observation_active_or_verified": cycle_receipt.get("ms2_acceptance") in MS2_ACTIVE,
        "refused_phases": refused,
        "best_target_claimed": False,
        "market_demand_claimed": False,
        "willingness_to_pay_proved": False,
        "commercial_success_proved": False,
        "customer_claimed": False,
        "authority_created": False,
        "external_effects": False,
    }


def evaluate_soak(
    snapshots: list[dict[str, Any]],
    *,
    min_cycles: int = MIN_SOAK_CYCLES,
) -> dict[str, Any]:
    ordered = sorted(snapshots, key=lambda item: int(item.get("iteration") or 0))
    required = max(1, int(min_cycles))
    gate = "PENDING_MINIMUM_AUTONOMIC_SOAK_CYCLES" if len(ordered) < required else ""

    event_count_regressions: list[dict[str, Any]] = []
    for previous, current in zip(ordered, ordered[1:]):
        for table in EVENT_COUNT_TABLES:
            before = int((previous.get("event_counts") or {}).get(table) or 0)
            after = int((current.get("event_counts") or {}).get(table) or 0)
            if after < before:
                event_count_regressions.append({"table": table, "before": before, "after": after})

    history_failures = [
        int(item.get("iteration") or 0)
        for item in ordered
        if not bool((item.get("immutable_prefix") or {}).get("all_historical_semantics_intact", False))
        and not bool((item.get("immutable_prefix") or {}).get("all_prefixes_intact", False))
    ]
    semantic_failures = [
        int(item.get("iteration") or 0)
        for item in ordered
        if int(item.get("semantic_violation_total") or 0) > 0
        or int(item.get("cockpit_truth_class_violations") or 0) > 0
        or not bool(item.get("cockpit_truth_separation_valid", False))
    ]
    authority_or_truth_failures = [
        int(item.get("iteration") or 0)
        for item in ordered
        if bool(item.get("authority_created", False))
        or bool(item.get("external_effects", False))
        or bool(item.get("best_target_claimed", False))
        or bool(item.get("market_demand_claimed", False))
        or bool(item.get("willingness_to_pay_proved", False))
        or bool(item.get("commercial_success_proved", False))
        or bool(item.get("customer_claimed", False))
        or bool((item.get("commercial_time") or {}).get("authority_created", False))
        or bool((item.get("commercial_time") or {}).get("followup_authority_created", False))
        or bool((item.get("commercial_time") or {}).get("market_demand_claimed", False))
    ]
    unsupported_silence = [
        int(item.get("iteration") or 0)
        for item in ordered
        if int((item.get("commercial_time") or {}).get("unsupported_no_reply_inferences") or 0) > 0
        or bool((item.get("commercial_time") or {}).get("age_only_silence_inference_used", False))
    ]
    refused_cycles = [
        {
            "iteration": int(item.get("iteration") or 0),
            "phases": list(item.get("refused_phases") or []),
        }
        for item in ordered
        if item.get("refused_phases")
    ]
    refresh_failures = [
        int(item.get("iteration") or 0)
        for item in ordered
        if not bool((item.get("refresh") or {}).get("public_read_cycle_complete", False))
        or not bool((item.get("refresh") or {}).get("mail_read_cycle_complete", False))
    ]
    ms8_failures = [
        int(item.get("iteration") or 0)
        for item in ordered
        if not bool(item.get("ms8_verified", False))
    ]
    ms2_failures = [
        int(item.get("iteration") or 0)
        for item in ordered
        if not bool(item.get("ms2_observation_active_or_verified", False))
        or str((item.get("commercial_time") or {}).get("coverage_state") or "") != "CONTINUOUS"
    ]
    learned_execution_cycles = sum(
        1
        for item in ordered
        if int((item.get("learned_query_execution") or {}).get("learned_queries_executed") or 0) > 0
        and int((item.get("learned_query_execution") or {}).get("history_bound_after_execution") or 0) > 0
    )

    if history_failures or event_count_regressions:
        gate = "REFUSE_HISTORICAL_EVENT_LEDGER_MUTATION"
    elif semantic_failures or authority_or_truth_failures or unsupported_silence:
        gate = "REFUSE_AUTONOMIC_SEMANTIC_OR_AUTHORITY_DRIFT"
    elif refused_cycles:
        gate = "REFUSE_UPSTREAM_PHASE_REGRESSION"
    elif refresh_failures:
        gate = "PENDING_COMPLETE_READ_ONLY_REFRESH_SOAK"
    elif ms8_failures:
        gate = "PENDING_STABLE_COMMERCIAL_COCKPIT_ACROSS_SOAK"
    elif ms2_failures:
        gate = "PENDING_CONTINUOUS_COMMERCIAL_TIME_ACROSS_SOAK"
    elif learned_execution_cycles < required:
        gate = "PENDING_LEARNED_QUERY_EXECUTION_ACROSS_SOAK"
    elif len(ordered) >= required:
        gate = MS9_VERIFIED

    first_counts = ordered[0].get("event_counts") if ordered else {}
    last_counts = ordered[-1].get("event_counts") if ordered else {}
    growth = {
        table: int((last_counts or {}).get(table) or 0)
        - int((first_counts or {}).get(table) or 0)
        for table in EVENT_COUNT_TABLES
    }
    query_batch_digests = [
        str((item.get("learned_query_execution") or {}).get("batch_digest") or "")
        for item in ordered
    ]
    query_batch_changes = sum(
        1
        for previous, current in zip(query_batch_digests, query_batch_digests[1:])
        if previous and current and current != previous
    )

    return {
        "schema": "dio.market_sensorium.ms9_soak_evaluation.v2",
        "ms9_acceptance": gate,
        "cycles_required": required,
        "cycles_observed": len(ordered),
        "learned_query_execution_cycles": learned_execution_cycles,
        "public_read_cycles": sum(
            bool((item.get("refresh") or {}).get("public_read_cycle_complete", False))
            for item in ordered
        ),
        "mail_read_cycles": sum(
            bool((item.get("refresh") or {}).get("mail_read_cycle_complete", False))
            for item in ordered
        ),
        "ms8_verified_cycles": sum(bool(item.get("ms8_verified", False)) for item in ordered),
        "ms2_continuous_cycles": len(ordered) - len(ms2_failures),
        "immutable_history_failure_cycles": history_failures,
        "event_count_regressions": event_count_regressions,
        "semantic_failure_cycles": semantic_failures,
        "authority_or_truth_failure_cycles": authority_or_truth_failures,
        "unsupported_silence_cycles": unsupported_silence,
        "refused_cycles": refused_cycles,
        "event_growth": growth,
        "query_batch_changes": query_batch_changes,
        "stable_world_allowed": True,
        "query_change_required": False,
        "rank_change_required": False,
        "long_duration_endurance_proved": False,
        "best_target_claimed": False,
        "market_demand_claimed": False,
        "willingness_to_pay_proved": False,
        "commercial_success_proved": False,
        "customer_claimed": False,
        "authority_created": False,
        "external_effects": False,
    }


def new_soak_session_id(baseline: dict[str, Any]) -> str:
    return stable_id("MSSOAK", utc_now(), baseline.get("digest") or digest_payload({}))
